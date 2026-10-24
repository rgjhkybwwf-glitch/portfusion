"""The FastAPI application: routes, and nothing else.

THIS FILE IS THE SWAP POINT. It is the only module that knows the desk is served over HTTP —
`engine.py`, `actions.py` and `panels/` would be unchanged if this became stdlib http.server,
or grew a login. A framework writes the plumbing once; the layout churns, so the churn must
not live here.

IT COMPUTES NOTHING. Every figure comes from a panel, every panel from `desk.engine`, and
`desk.engine` from `engine.py`.
"""
from __future__ import annotations

import os
import pathlib
import time

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from portfusion.desk import actions, bundle, panels, engine
from portfusion.desk.intake import (bench as _bench, dropoff as _dropoff, propose as _propose,
                         withdraw as _withdraw)

app = FastAPI(title="PortFusion — the desk", docs_url=None, redoc_url=None)

#: The names this desk answers to. `own_page_only()` refuses every other.
LOOPBACK = ("127.0.0.1", "localhost", "[::1]")


@app.middleware("http")
async def own_page_only(request: Request, call_next):
    """ONLY THE DESK'S OWN PAGE MAY ASK IT ANYTHING.

    Any web page open in the same browser can send a request to 127.0.0.1, so without this a
    page could start a feed fetch or commit an approved bench item. Two checks close it:

    THE HOST. A page that points a name of its own at this machine (DNS rebinding) is talking
    to the desk as its own origin, so the browser would also let it READ the answers. A request
    for any name but `LOOPBACK` is refused.

    THE ORIGIN, on anything but a read. A browser names the page a write comes from, and only
    the desk's own address may write. A request with no Origin did not come from a page — a
    script on this Mac, which could open the files directly anyway.
    """
    host = request.headers.get("host", "")
    if host.rsplit(":", 1)[0] not in LOOPBACK:
        return JSONResponse(status_code=403, content={
            "error": "refused", "detail": f"the desk answers to 127.0.0.1, not to {host!r}"})
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD") and origin not in (None, f"http://{host}"):
        return JSONResponse(status_code=403, content={
            "error": "refused", "detail": f"a write from {origin!r}, which is not this desk"})
    return await call_next(request)


@app.get("/")
def index():
    """The shell, built by `desk/bundle.py` — the same bytes the hosted desk is published from.

    `no-store` on the responses is not enough on its own: a browser holds a script it already
    parsed, so a page can go on running an app.js rewritten on disk minutes earlier. So every
    asset URL in the page carries its own content hash, and A CHANGED FILE GETS A CHANGED URL.
    `no-store` still stops the SHELL being cached; the stamp stops a stale asset being served
    into a fresh shell.
    """
    return Response(bundle.index(), media_type="text/html", headers=NO_STORE)


# A cached stylesheet or script runs a copy from before a change while the API serves the new
# one.
NO_STORE = {"Cache-Control": "no-store, must-revalidate"}

#: WHEN THIS PROCESS IMPORTED THE CODE IT IS SERVING. Whole seconds, so a shell can compare it
#: with a file mtime using `-gt` and no arithmetic.
#:
#: A RUNNING DESK SERVES WHAT IT IMPORTED AT STARTUP and has no idea the source has moved on.
#: After a restart the page polls /api/health until this moves, which is how it knows the
#: replacement has started rather than guessing at a delay.
STARTED = int(time.time())


@app.get("/api/health")
def health():
    """Who is answering on this port, and when it loaded its code.

    IDENTIFYING OURSELVES IS THE POINT, not the timestamp alone: a caller polling the port after
    a restart can tell the desk from anything else that happens to be listening on it.
    """
    return JSONResponse({"desk": True, "started": STARTED, "pid": os.getpid()},
                        headers=NO_STORE)


#: What each kind of shell file is served as. Netlify sends the same types by extension, all but
#: the manifest's, which `desk/publish.py`'s `_HEADERS` sets and says why.
MEDIA = {".css": "text/css", ".js": "text/javascript", ".png": "image/png",
         ".woff2": "font/woff2", ".webmanifest": "application/manifest+json"}


def _shell(path: str) -> Response:
    """One of the shell's files, from `desk/bundle.py`. A path that is not part of the shell is a
    404, and `bundle.asset()` says why nothing can traverse out."""
    try:
        body = bundle.asset(path)
    except KeyError:
        raise HTTPException(404, "no such file")
    return Response(body, media_type=MEDIA[pathlib.PurePosixPath(path).suffix],
                    headers=NO_STORE)


@app.get("/static/{name}")
def static(name: str):
    return _shell(f"/static/{name}")


@app.get("/fonts/{name}")
def fonts(name: str):
    """The book's typefaces, which /tokens.css declares. They live in house/fonts/ because the
    report embeds the same files; served from disk, so the desk never waits on a network."""
    return _shell(f"/fonts/{name}")


@app.get("/favicon.png")
def favicon():
    """THE DESK'S MARK IN A TAB — the small mark, the form the design system keeps for below 20px.

    A browser tab with the generic page icon is one you lose among twenty others.

    The book's `brand/` icon, or `desk.icon.png()` drawn in its palette on request rather than
    committed, so a palette change reaches the tab with the pages. The Dock's icon is the next
    route's.
    """
    return _shell("/favicon.png")


@app.get("/apple-touch-icon.png")
def apple_touch_icon():
    """THE DOCK AND HOME-SCREEN ICON — LOAD-BEARING. What this returns is what sits in the Dock
    (`desk/bundle.py` says which surface reads which icon), and a break degrades to a generic
    mark silently, so a test holds both ends."""
    return _shell("/apple-touch-icon.png")


@app.get("/icon-{size}.png")
def app_icon(size: str):
    """The full mark at 192 and 512, for the manifest and, at 512, the Dock's magnification. Any
    other size is not part of the shell, and `bundle.asset()` answers 404 for it."""
    return _shell(f"/icon-{size}.png")


@app.get("/manifest.webmanifest")
def manifest():
    """What Chrome, Android and Safari read to make the desk an app: `bundle.manifest()`."""
    return _shell("/manifest.webmanifest")


@app.get("/tokens.css")
def tokens():
    """The book's own colours as CSS custom properties, DERIVED not retyped.

    Generated rather than written down, so a colour changed in `house/palette.py` reaches the
    desk on the next reload. `app.css` is the design system and consumes these; replacing it
    is how a different design system drops in.
    """
    return _shell("/tokens.css")


@app.post("/api/enrol")
def enrol(body: dict = Body(...)):
    """A one-time code for enrolling a passkey on the hosted desk, asked of THIS door, so only
    someone at the Mac can make one. The Access page's button and `portfusion desk --enrol <name>`
    ask it; the code is typed into the hosted sign-in page. A new reader's level comes with it.
    Writes nothing: the code lives in memory, for ten minutes."""
    from portfusion.desk import auth
    try:
        return auth.enrol_code(str(body.get("who", "")), body.get("level") or None)
    except auth.Refused as e:
        raise HTTPException(400, str(e))


@app.get("/api/state")
def state():
    """Everything the shell needs to draw itself: the panels, the buttons, the freshness line.

    A RECORD THAT WILL NOT LOAD is a 503 carrying its own message, which the shell shows: some
    panels read the record on import, so the list itself cannot be drawn."""
    try:
        listed = panels.all_panels()
    except engine.RecordUnavailable as e:
        return JSONResponse(status_code=503,
                            content={"error": "record unavailable", "detail": str(e)})
    return {
        "panels": [{"name": m.NAME, "title": m.TITLE, "order": m.ORDER,
                    "apart": getattr(m, "APART", False)} for m in listed],
        "actions": [a.as_json() for a in actions.all_actions()],
        "freshness": engine.freshness(),
    }


#: A QUARTER END, and nothing else: the four month-ends a quarterly report can be for.
REPORT_DATE = r"^\d{4}-(03-31|06-30|09-30|12-31)$"

#: THE REPORT'S OWN POLICY. It stands on its own — its face embedded and its style inline — so it
#: may use those two and nothing else: no script, no request to anywhere, no frame around it.
REPORT_CSP = ("default-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:; "
              "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")


@app.get("/api/report/{quarter_end}")
def report(quarter_end: str):
    """ONE QUARTER'S REPORT, rendered for the request: the report's page, and
    nothing is written. A quarter the report's gate refuses is a 409 carrying the gate's words,
    which the Reports page has already shown beside it."""
    import re
    if not re.match(REPORT_DATE, quarter_end):
        raise HTTPException(400, f"{quarter_end!r} is not the end of a quarter")
    try:
        html, gaps = engine.report_page(quarter_end)
    except engine.RecordUnavailable as e:
        return JSONResponse(status_code=503,
                            content={"error": "record unavailable", "detail": str(e)})
    if gaps:
        return JSONResponse(status_code=409, content={"error": "not ready",
                                                      "detail": " · ".join(gaps)})
    return Response(html, media_type="text/html",
                    headers={**NO_STORE, "Content-Security-Policy": REPORT_CSP})


@app.get("/api/panel/{name}")
def panel(name: str):
    try:
        try:
            mod = panels.get(name)
        except KeyError:
            raise HTTPException(404, f"no panel named {name!r}")
        return {"name": mod.NAME, "title": mod.TITLE, "heads": panels.heads(mod),
                "precision": engine.precision(), "data": mod.data()}
    except engine.RecordUnavailable as e:
        # The record refused to load. Hand its own message through verbatim — it names the
        # exact file that was missing, and paraphrasing it would throw away the useful half.
        return JSONResponse(status_code=503,
                            content={"error": "record unavailable", "detail": str(e)})


# =================================================================================================
# THE BENCH. Everything here works on an item in `_inbox/.bench/`; NOTHING touches store/.
# The one write path this file has is to a work-in-progress note, not to the record.
# =================================================================================================
@app.get("/api/bench/{item_id}")
def bench_item(item_id: str):
    from portfusion.desk.panels import bench as panel
    try:
        return panel.detail(item_id)
    except KeyError:
        raise HTTPException(404, f"no bench item {item_id!r}")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/bench")
def bench_new(body: dict = Body(default={})):
    """Open a bench item. FOR A DOCUMENT THIS IS IDEMPOTENT — see `bench.for_document()`.

    Clicking "work it" twice must not leave two identical empty items on the bench with no way
    to tell them apart. One document is one piece of evidence and one item works it.
    """
    name = (body.get("document") or {}).get("name")
    if name:
        try:
            return _bench.for_document(name, origin=body.get("origin", "document"))
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
    return _bench.new_item(origin=body.get("origin", "manual"),
                           title=body.get("title", ""),
                           document=None)


@app.put("/api/bench/{item_id}")
def bench_save(item_id: str, body: dict = Body(...)):
    """Save an item and hand back its gates, so the screen shows what is still blocking.

    THE PAGE SAYS WHICH REVISION IT DREW, and a save from an older one is refused (409), never
    written over the newer: `bench.save()` says why."""
    from portfusion.desk.panels import bench as panel
    try:
        item = _bench.get(item_id)
    except (KeyError, ValueError):
        raise HTTPException(404, f"no bench item {item_id!r}")
    drawn = body.get("revision")
    for key in ("title", "evidence_class", "evidence", "why", "rows", "acknowledged"):
        if key in body:
            item[key] = body[key]
    # THE RECORD'S OWN CONTRIBUTION FOLLOWS THE EVIDENCE. `source` is the three limbs joined,
    # and the limbs are typed AFTER the document is read — so it is re-derived on every save
    # rather than only at read time, when the limbs were still blank.
    try:
        _bench.save(_propose.refresh_derived(item), drawn=drawn)
    except _bench.Stale:
        raise HTTPException(409, "the item changed after this page drew it")
    return panel.detail(item_id)


@app.post("/api/bench/{item_id}/read")
def bench_read(item_id: str):
    """READ the item's document ON THIS MACHINE — a kind `read_rows.LOCAL` reads. Nothing leaves.
    What is read, and what is reported rather than proposed, is `bench.read_here()`'s."""
    try:
        _bench.read_here(_bench.get(item_id))
    except KeyError:
        raise HTTPException(404, f"no bench item {item_id!r}")
    except ValueError as e:
        raise HTTPException(409, str(e))
    from portfusion.desk.panels import bench as panel
    return panel.detail(item_id)


@app.post("/api/bench/{item_id}/commit")
def bench_commit(item_id: str):
    """WRITE an approved item's rows into the store, then archive it.

    THE GATE IS `commit.commit()`, not this route — it re-runs every bench gate from scratch
    and never trusts the stored state. So this function does no permission thinking of its own,
    for the same reason `run_action` does none: a second place holding the answer is a second
    place for it to be wrong.
    """
    from portfusion.desk.doors import commit as _commit
    try:
        return _commit.commit(item_id)
    except KeyError:
        raise HTTPException(404, f"no bench item {item_id!r}")
    except _commit.Refused as e:
        raise HTTPException(409, str(e))


@app.post("/api/bench/notes/{ref}")
def bench_research_note(ref: str):
    """WRITE a published research note's rows, one per code it covers, on the Bench's press.

    The gate is `research_notes.write()`, which answers from the research repo and the book
    afresh, as `bench_commit` leaves its gate to `commit.commit()`."""
    from portfusion.desk.doors import research_notes
    try:
        return research_notes.write(ref)
    except research_notes.Refused as e:
        raise HTTPException(409, str(e))


@app.delete("/api/bench/{item_id}")
def bench_discard(item_id: str):
    """Remove a work-in-progress note. It has written nothing, so nothing is lost.

    NOT the same as deleting a document, which `docs/intake.md` forbids — this never
    touches one.

    AN ITEM THAT IS NOT THERE IS A 404, as it is on every other bench route.
    """
    try:
        _bench.get(item_id)
    except KeyError:
        raise HTTPException(404, f"no bench item {item_id!r}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    _bench.discard(item_id)
    return {"discarded": item_id}


@app.delete("/api/inbox/{name}")
def inbox_withdraw(name: str, destination: str | None = None, why: str = ""):
    """Send a document that was not needed back out of the workbench, closing its note too.

    The other ending. `bench_commit` is the one where the document produced rows and goes to
    `_archive/statements/` as evidence; this is the one where it produced none. Every rule —
    the destination outside the repo, the refusal to overwrite, what happens when an identical
    copy is already there — lives in `desk/intake/withdraw.py`, and this carries a refusal back as a
    409 exactly as the commit route does.

    A DELETE ON THE DOCUMENT, and the verb is honest: from the workbench's point of view the
    document goes. Where it goes is the module's business and it never goes nowhere.
    """
    try:
        return _withdraw.withdraw(name, destination, why)
    except _dropoff.Refused as e:
        raise HTTPException(409, str(e))


@app.post("/api/inbox")
async def inbox_drop(name: str, request: Request, modified: float | None = None):
    """Land a dropped document on the intake workbench. THE ONLY ROUTE THAT ACCEPTS A FILE.

    IT DECIDES NOTHING. Every rule about what may land — the extensions, the size, the leading
    dot, the refusal to overwrite — lives in `desk/intake/dropoff.py`, the one door into `_inbox/`.
    This function carries bytes to it and turns its refusal into a 400, exactly as `run_action`
    carries a name to the registry.

    RAW BODY, NOT MULTIPART, and that is a dependency decision rather than a style one.
    FastAPI's `UploadFile` needs `python-multipart` — another package, for a form encoding this
    desk has exactly one use for. A browser `File` IS a `Blob`, so `fetch(url, {body: file})`
    sends the bytes unwrapped and nothing has to be decoded here. The name rides in the query
    string, where `dropoff.safe_name` treats it as untrusted whichever way it arrived.
    """
    try:
        return _dropoff.accept(name, await request.body(), modified)
    except _dropoff.Refused as e:
        raise HTTPException(400, str(e))


@app.get("/api/document/{name}")
def document(name: str):
    """A document's text, to read BESIDE the form. Extracted, never interpreted."""
    try:
        return _bench.document_text(name)
    except FileNotFoundError:
        raise HTTPException(404, f"no document {name!r} on the workbench")
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/document/{name}/raw")
def document_raw(name: str):
    """The document ITSELF, for reading beside the form. Bytes, not text.

    THE EXTRACTED TEXT IS NOT THE DOCUMENT. It is what the quote check runs against, and it is
    the right thing to show when a refusal needs explaining — but a contract note's figures sit
    in a table, and pypdf hands that back as a column of numbers with the headings somewhere
    else. Cross-referencing a quote against THAT is a different and much worse job than
    cross-referencing it against the page.

    SERVED FROM `_inbox/` ONLY, by basename, with the same containment rule as `/static`: a
    name that does not resolve inside the workbench is a 404 rather than a traversal.
    """
    inbox = _dropoff.INBOX.resolve()
    path = (inbox / pathlib.Path(name).name).resolve()
    if path.parent != inbox or not path.is_file():
        raise HTTPException(404, f"no document {name!r} on the workbench")
    kind = {".pdf": "application/pdf", ".csv": "text/plain; charset=utf-8",
            ".tsv": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8"}
    return FileResponse(path, media_type=kind.get(path.suffix.lower(), "application/octet-stream"),
                        headers=NO_STORE)


@app.post("/api/action/{name}")
def run_action(name: str, body: dict = Body(default={})):
    """Run a declared action.

    THE REGISTRY IS THE GATE, not this route. An action that writes is refused here until its
    `enabled_from` date, and an action that writes EVENTS cannot exist — `Action` refuses to be
    constructed. So this function does no permission thinking of its own; if it did, that would
    be a second place where the answer lives.
    """
    try:
        action = actions.get(name)
    except KeyError:
        raise HTTPException(404, f"no action named {name!r}")
    if not action.available:
        raise HTTPException(
            409, f"{action.label!r} writes {action.writes!r} and is not enabled until "
                 f"{action.as_json()['enabled_from']}")
    try:
        return {"action": name, "ran": True, "result": action.run(**(body or {}))}
    except engine.RecordUnavailable as e:
        return JSONResponse(status_code=503,
                            content={"error": "record unavailable", "detail": str(e)})


@app.post("/api/sweep-status")
def sweep_status(body: dict = Body(default={})):
    """Which swept deal references are already in the record, or already on the bench.

    The sweep's own result is held in the browser so that coming back to the Bench does not mean
    another call to the broker. This is the half that must NOT be cached: what has happened to
    those events since.
    """
    # The status lives on the Bench panel, with the sweep it belongs to.
    from portfusion.desk.panels import bench as panel
    try:
        return panel.sweep_status(body.get("refs") or [])
    except engine.RecordUnavailable as e:
        return JSONResponse(status_code=503,
                            content={"error": "record unavailable", "detail": str(e)})


@app.get("/api/holdings")
def holdings(by: str = "", account: str = ""):
    """Interrogate the holdings. Both arguments go to the engine; nothing is narrowed here."""
    from portfusion.desk.panels import holdings as panel
    try:
        return panel.query(account=account or None, by=by or panel.GROUPINGS[0])
    except ValueError as e:
        raise HTTPException(400, str(e))
    except engine.RecordUnavailable as e:
        return JSONResponse(status_code=503,
                            content={"error": "record unavailable", "detail": str(e)})


@app.get("/api/round-trips")
def round_trips(ticker: str = "", account: str = "", start: str = "", end: str = "",
                company: str = "", view: str = "holding"):
    """Narrow the closed positions to one company, one name, one account, or a range of exit
    dates, by holding or by company life."""
    from portfusion.desk.panels import round_trips as panel
    try:
        return panel.query(ticker=ticker or None, account=account or None,
                           start=start or None, end=end or None, company=company or None,
                           view=view)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except engine.RecordUnavailable as e:
        return JSONResponse(status_code=503,
                            content={"error": "record unavailable", "detail": str(e)})


@app.get("/api/trades")
def trades(start: str = "", end: str = "", account: str = "",
           ticker: str = "", direction: str = "", company: str = ""):
    """Interrogate the ledger: a date range, an account, a ticker, a direction, a company.

    `company` is what the Holdings link uses: it covers every code the company is held under,
    so one click gives the shares AND the spread bet rather than half the history.
    """
    from portfusion.desk.panels import trades as panel
    try:
        return panel.query(start, end, account, ticker, direction, company or None)
    except engine.RecordUnavailable as e:
        return JSONResponse(status_code=503,
                            content={"error": "record unavailable", "detail": str(e)})
