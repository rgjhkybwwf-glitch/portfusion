"""THE REMOTE DOOR — the desk as the hosted page reaches it, through the tunnel.

    portfusion desk --remote-port 8768     # the Mac's door on 8765, and this one on 8768

ONE PROCESS, TWO DOORS. `desk/__main__.py` serves `desk.app:app` and this `door` from the same
process, so a restart moves both and neither can be running older code than the other. The tunnel
(Tailscale Funnel) forwards only this port, and Netlify proxies the hosted page's /api/* and /auth/*
to the tunnel, so to the browser this door is the hosted page's own origin.

READ ONLY, AND PINNED. `REMOTE_ROUTES` is every route this door has, and `REMOTE_PANELS` every
page it will draw. Bench, Price Refresh and Access hold the desk's buttons, so they stay on the
Mac. Opening one more is a line in a pinned list that `tests/desk/test_remote.py` names, never a
quiet change.

THE SAME ANSWERS AS THE MAC'S. Each route is the local door's own function, or a narrowing of its
answer, so the two doors cannot disagree about a figure.

ONLY NETLIFY MAY KNOCK. Every request must carry Netlify's signature (`signed_by_netlify`), made
with a secret only Netlify and this Mac hold (`auth.PROXY_SECRET`), so a caller who finds the
tunnel and goes round the hosted page is refused before anything else is asked. With no secret on
the Mac, every request is refused: the door fails shut, never open.

NOTHING ANSWERS A STRANGER. Every request but signing in needs a session (`desk/auth.py`), and
anything but a read must come from the hosted page's own origin. Every answer is `no-store`, so
nothing on the way — Netlify least of all — keeps a copy.

EACH READER IS ANSWERED AT THEIR LEVEL, decided here on every request and never in the page:
`OPENS` says which pages a level draws and whether it reads the holders' names. A level that does
not has every answer renamed by `desk/naming.py` on its way out, and an answer the renaming could
not clear is refused rather than sent.

SIGNING IN IS LIMITED PER ADDRESS, so a stranger who uses up their own share keeps nobody else
out, and every attempt is written to the sign-in log the Mac's Access page reads.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from portfusion.desk import app as local, auth, bundle, engine, naming
from portfusion.record import schema


def _settings() -> dict:
    """The book's settings, read alone, so a record that will not load leaves the door's own
    readable; none when they cannot be read, and the door stays shut."""
    try:
        return dict(schema.load("settings"))
    except (OSError, ValueError):
        return {}


_SETTINGS = _settings()
#: Where the hosted desk lives, the book's `hosted_origin`: the only page whose writes this door
#: accepts.
ORIGIN: str | None = _SETTINGS.get("hosted_origin") or None
#: Whose passkeys these are, the book's `passkey_domain`: the book's domain rather than the desk's
#: host, so one enrolment holds wherever under it the desk is served; `ORIGIN` is still checked
#: exactly.
RP_ID: str | None = _SETTINGS.get("passkey_domain") or None


def unconfigured() -> list[str]:
    """The settings the door needs and the book does not give. While any is missing the door
    refuses every request, as it does with no proxy secret: it fails shut, never open."""
    return [key for key, value in (("hosted_origin", ORIGIN), ("passkey_domain", RP_ID))
            if not value]

#: The port this process opened the door on, set by `desk/__main__.py`; None when it is shut.
#: `desk/restart.py` reads it so a restart brings the door back where it was.
PORT: int | None = None

#: The pages a hosted desk may draw, in the Mac desk's own order.
REMOTE_PANELS = ("dashboard", "what-changed", "reconcile", "performance", "holdings",
                 "round-trips", "trades", "reports")


@dataclass(frozen=True)
class Opens:
    """What one level opens: the pages it may draw, and whether it reads the holders' names or
    every account by its code with the holders taken out of every word (`desk/naming.py`)."""
    pages: tuple[str, ...]
    names: bool


#: WHAT EACH LEVEL OPENS. The principal reads every page the owner reads here, and every account,
#: with no holder in it; no level has a button. Narrowing one is a line here that
#: `tests/desk/test_remote.py` names.
OPENS = {
    "owner": Opens(pages=REMOTE_PANELS, names=True),
    "principal": Opens(pages=REMOTE_PANELS, names=False),
}
assert set(OPENS) == set(auth.LEVELS), "a level with nothing said about what it opens"

#: Every route this door answers.
REMOTE_ROUTES = {
    ("GET", "/api/health"), ("GET", "/api/state"), ("GET", "/api/panel/{name}"),
    ("GET", "/api/holdings"), ("GET", "/api/round-trips"), ("GET", "/api/trades"),
    ("GET", "/api/report/{quarter_end}"),
    ("POST", "/auth/options"), ("POST", "/auth/verify"), ("POST", "/auth/enrol/options"),
    ("POST", "/auth/enrol/verify"), ("POST", "/auth/sign-out"),
}

#: Signing in is the one thing a stranger may ask, so it is limited: this many /auth/ requests a
#: minute from one address. Past it, that address waits a minute and nobody else does.
AUTH_PER_MINUTE = 30

#: WHERE A REQUEST CAME FROM, as the proxy in front of this door says: Netlify names the browser's
#: address in its own header. The tunnel's own connection is always this Mac, so it is the last
#: resort. Read only once the request is signed, so the address is Netlify's word and not the
#: caller's. NOT `X-Forwarded-For`: its first entry is whatever the caller sent, so a caller
#: could name a fresh address on every request and step round the limit.
ADDRESS_HEADERS = ("x-nf-client-connection-ip",)

#: Netlify's signature on a proxied request: a JWS, HS256, over issuer, deploy context and expiry.
SIGNATURE = "x-nf-sign"
#: Clock difference forgiven between Netlify and this Mac when reading the expiry, in seconds.
SIGNATURE_LEEWAY = 30

#: Whose answers no other cache may keep, and no search engine may list. NETLIFY ADDS NOTHING
#: TO A PROXIED ANSWER — its `_headers` (desk/publish.py) reach only the files it serves — so the
#: door sends the shell's own headers as well, the policy aside: a policy is a page's.
PRIVATE = {"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex",
           **{k: v for k, v in bundle.SHELL_HEADERS.items() if k != "Content-Security-Policy"}}

door = FastAPI(title="PortFusion — the desk, remote", docs_url=None, redoc_url=None,
               openapi_url=None)


def _unpadded(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def signed_by_netlify(token: str | None, secret: bytes | None,
                      now: float | None = None) -> str | None:
    """None when `token` is Netlify's signature over this request; otherwise why it is not.

    The checks Netlify's signed proxy allows: HS256 under the shared secret, issued by Netlify,
    not expired, and from the production deploy, so no preview or branch deploy can reach the
    Mac. The algorithm is read from nowhere but here: a token naming another is refused."""
    if not secret:
        return "the Mac holds no proxy secret"
    if not token:
        return "unsigned"
    try:
        head, body, sig = token.split(".")
        header, claims = json.loads(_unpadded(head)), json.loads(_unpadded(body))
        given = _unpadded(sig)
    except ValueError:
        return "a signature that does not parse"
    if not (isinstance(header, dict) and isinstance(claims, dict)) or header.get("alg") != "HS256":
        return "a signature that is not HS256"
    want = hmac.new(secret, f"{head}.{body}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(want, given):
        return "a signature that does not verify"
    if claims.get("iss") != "netlify":
        return "a signature not issued by Netlify"
    exp = claims.get("exp")
    now = time.time() if now is None else now
    if not isinstance(exp, (int, float)) or exp + SIGNATURE_LEEWAY < now:
        return "an expired signature"
    if claims.get("deploy_context") != "production":
        return "a signature from a deploy that is not production"
    return None


#: When the last unsigned request was logged, so a flood writes one line a minute.
_unsigned_logged = [0.0]


def _unsigned(request: Request, why: str) -> JSONResponse:
    now = time.time()
    if now - _unsigned_logged[0] >= 60:
        _unsigned_logged[0] = now
        host = request.client.host if request.client else ""
        auth.log("refused", host, detail=f"not through the hosted desk: {why}", now=now)
    return JSONResponse(status_code=403, content={
        "error": "refused", "detail": "not through the hosted desk"})


def address(request: Request) -> str:
    """The caller's address, for the sign-in limit and the log."""
    for name in ADDRESS_HEADERS:
        if request.headers.get(name):
            return request.headers[name].split(",")[0].strip()
    return request.client.host if request.client else ""


@door.middleware("http")
async def signed_in_from_the_hosted_page(request: Request, call_next):
    """A request Netlify did not sign is refused before anything else. Then a write from any page
    but the hosted desk is refused, and so is anything at all from a caller who has not signed
    in, signing in aside. A reader signed in is answered at their level, read afresh on every
    request, so a level changed or a reader revoked on the Mac holds from the next one."""
    missing = unconfigured()
    if missing:
        response = JSONResponse(status_code=503, content={
            "error": "refused", "detail": f"the book's settings name no {', '.join(missing)}"})
        response.headers.update(PRIVATE)
        return response
    unsigned = signed_by_netlify(request.headers.get(SIGNATURE), auth.proxy_secret())
    if unsigned:
        response = _unsigned(request, unsigned)
        response.headers.update(PRIVATE)
        return response
    signing_in = request.url.path.startswith("/auth/")
    who = None if signing_in else auth.signed_in(request.cookies.get(auth.COOKIE))
    if request.method not in ("GET", "HEAD") and request.headers.get("origin") != ORIGIN:
        response = JSONResponse(status_code=403, content={
            "error": "refused", "detail": "a write from a page that is not the hosted desk"})
    elif signing_in and not _ration(address(request)):
        response = JSONResponse(status_code=429, content={
            "error": "refused", "detail": "too many sign-ins; wait a minute"})
    elif not signing_in and who is None:
        response = JSONResponse(status_code=401, content={
            "error": "sign in", "detail": "the desk needs your passkey"})
    elif not signing_in and auth.level(who) not in OPENS:
        auth.close(request.cookies.get(auth.COOKIE))
        response = JSONResponse(status_code=401, content={
            "error": "sign in", "detail": f"{who} has no level on the desk"})
    else:
        if who is not None:
            request.state.who, request.state.opens = who, OPENS[auth.level(who)]
        response = await call_next(request)
    response.headers.update(PRIVATE)
    return response


#: What every remote reader is told when the record on the Mac will not load. The record's own
#: words name the Mac's folders, so they stay on the Mac's desk.
UNAVAILABLE = "the record on the Mac will not load: see the Mac's desk"


@door.exception_handler(engine.RecordUnavailable)
def unavailable(request: Request, e: Exception) -> JSONResponse:
    return JSONResponse(status_code=503,
                        content={"error": "record unavailable", "detail": UNAVAILABLE})


@door.exception_handler(HTTPException)
def renamed_refusal(request: Request, e: HTTPException) -> Response:
    """A refusal's words are read as an answer is: renamed for a level that reads no names."""
    answer = JSONResponse({"detail": e.detail}, status_code=e.status_code, headers=e.headers)
    if getattr(request.state, "opens", None) is None:          # signing in: no level yet
        return answer
    try:
        return _as_read(request, answer)
    except engine.RecordUnavailable as unloaded:
        return unavailable(request, unloaded)


def _as_read(request: Request, answer):
    """An answer as this reader may read it: as it is for a level that reads names, renamed and
    checked for one that does not. Refused, never sent, if the renaming could not clear it."""
    if request.state.opens.names:
        return answer
    n = naming.of(engine.book())
    try:
        if isinstance(answer, JSONResponse):
            return JSONResponse(status_code=answer.status_code,
                                content=n.apply(json.loads(answer.body)))
        if isinstance(answer, Response):
            n.check(answer.body.decode("utf-8", "replace"))
            return answer
        return n.apply(answer)
    except naming.Withheld as e:
        return JSONResponse(status_code=500, content={"error": "withheld", "detail": str(e)})


@door.get("/api/health")
def health():
    """Who is answering, when it loaded its code, WHICH SET OF SHELL FILES the Mac would serve
    now, and whether its code is still the code on disk. A desk running older code works its
    version out partly from what it loaded before, so no publish can match it: `stale` says the
    fix is a restart. The hosted page reads the same from `/api/state`'s freshness."""
    return {"desk": True, "started": local.STARTED, "version": bundle.version(),
            "stale": engine.source_stale()["stale"], "remote": True}


@door.get("/api/state")
def state(request: Request):
    """The Mac desk's state, narrowed: the pages this reader's level draws, and no buttons at all.
    With the version of the shell files the Mac would serve now, which the hosted page holds
    against its own before drawing anything."""
    s, opens = local.state(), request.state.opens
    return _as_read(request, {
        **s, "panels": [p for p in s["panels"] if p["name"] in opens.pages], "actions": [],
        "remote": True, "version": bundle.version(), "level": auth.level(request.state.who)})


@door.get("/api/panel/{name}")
def panel(name: str, request: Request):
    if name not in request.state.opens.pages:
        raise HTTPException(404, f"{name!r} is worked on the Mac's own desk")
    return _as_read(request, local.panel(name))


def _account(request: Request, sent: str) -> str:
    """The register's account for the one the page sent: a label or a code for a level that
    does not read names, which is all such a page was ever shown."""
    if request.state.opens.names:
        return sent
    try:
        return naming.of(engine.book()).account(sent)
    except ValueError as e:
        raise HTTPException(400, str(e))


@door.get("/api/holdings")
def holdings(request: Request, by: str = "", account: str = ""):
    return _as_read(request, local.holdings(by=by, account=_account(request, account)))


@door.get("/api/round-trips")
def round_trips(request: Request, ticker: str = "", account: str = "", start: str = "",
                end: str = "", company: str = "", view: str = "holding"):
    return _as_read(request, local.round_trips(ticker=ticker, account=_account(request, account),
                                               start=start, end=end, company=company, view=view))


@door.get("/api/trades")
def trades(request: Request, start: str = "", end: str = "", account: str = "",
           ticker: str = "", direction: str = "", company: str = ""):
    return _as_read(request, local.trades(
        start=start, end=end, account=_account(request, account), ticker=ticker,
        direction=direction, company=company))


@door.get("/api/report/{quarter_end}")
def report(quarter_end: str, request: Request):
    """The report names accounts by code for everyone; a level that reads no names has the
    page checked before it is sent, all the same."""
    return _as_read(request, local.report(quarter_end))


# =================================================================================================
# SIGNING IN. `desk/auth.py` holds the ceremonies; these carry them over HTTP and set the cookie.
# Each refusal is a 403 carrying auth.Refused's own words, which the sign-in page shows as they are.
# =================================================================================================
_asked: dict[str, list[float]] = {}

#: At most this many callers remembered at once: beyond it the longest quiet is forgotten, so a
#: flood of fresh networks cannot grow the table without end.
MAX_ASKED = 10_000


def _ration(where: str, now: float | None = None) -> bool:
    """Whether this address may ask again this minute. The first refusal in a minute is logged;
    the rest of a flood is not, so the log stays readable."""
    now = time.time() if now is None else now
    where = auth.limit_key(where)                   # an IPv6 caller is its /64
    for a in [a for a, ts in _asked.items() if not ts or now - ts[-1] >= 60]:
        del _asked[a]
    while len(_asked) >= MAX_ASKED and where not in _asked:
        del _asked[min(_asked, key=lambda a: _asked[a][-1])]
    mine = [t for t in _asked.get(where, []) if now - t < 60]
    if len(mine) >= AUTH_PER_MINUTE:
        if len(mine) == AUTH_PER_MINUTE:
            auth.log("limited", where, detail=f"over {AUTH_PER_MINUTE} a minute", now=now)
            mine.append(now)
        _asked[where] = mine
        return False
    _asked[where] = [*mine, now]
    return True


def _refused(request: Request, e: Exception) -> JSONResponse:
    why = getattr(e, "detail", "")
    auth.log("refused", address(request), detail=f"{e}: {why}" if why else str(e))
    return JSONResponse(status_code=403, content={"error": "refused", "detail": str(e)})


def _signed_in_as(request: Request, who: str, token: str, result: str) -> JSONResponse:
    device = auth.device_name(request.headers.get("user-agent"))
    auth.log(result, address(request), who=who, device=device)
    response = JSONResponse({"who": who, "level": auth.level(who)})
    response.headers["set-cookie"] = auth.cookie(token)
    return response


@door.post("/auth/options")
def sign_in_options(request: Request):
    try:
        return Response(auth.sign_in_options(RP_ID, address=address(request)),
                        media_type="application/json")
    except auth.Refused as e:
        return _refused(request, e)


@door.post("/auth/verify")
def sign_in(request: Request, credential: dict = Body(...)):
    try:
        who, token = auth.sign_in_verify(credential, RP_ID, ORIGIN)
    except auth.Refused as e:
        return _refused(request, e)
    return _signed_in_as(request, who, token, "signed in")


@door.post("/auth/enrol/options")
def enrol_options(request: Request, body: dict = Body(...)):
    try:
        return Response(auth.enrol_options(str(body.get("code", "")), RP_ID,
                                           address=address(request)),
                        media_type="application/json")
    except auth.Refused as e:
        return _refused(request, e)


@door.post("/auth/enrol/verify")
def enrol(request: Request, credential: dict = Body(...)):
    try:
        who, token = auth.enrol_verify(credential, RP_ID, ORIGIN, device=auth.device_name(
            request.headers.get("user-agent")))
    except auth.Refused as e:
        return _refused(request, e)
    return _signed_in_as(request, who, token, "enrolled")


@door.post("/auth/sign-out")
def sign_out(request: Request):
    auth.close(request.cookies.get(auth.COOKIE))
    response = JSONResponse({"signed_out": True})
    response.headers["set-cookie"] = auth.cookie("", max_age=0)
    return response
