"""The desk's engine — the one way the desk reads the book.

Everything the desk reads comes through here, for the same reason `engine.load_store()`
is the build's single seam: two ways into one record is two chances to disagree with it.

THE RECORD'S REFUSAL IS CAUGHT HERE, NOT SOFTENED. `record/rules.py` calls `sys.exit()` at
import time if the book's store is absent or incomplete. That is right for a build — refuse to
run rather than produce a plausible wrong page — and it is fatal for a long-lived server, which
would die on import with no way to say why. `SystemExit` is catchable, so the desk catches it and
renders the record's own message as a page. The refusal does not change; the caller adapts.
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import sys

#: THE APP'S OWN FOLDER, the package this module is in: its source, its fonts and icons.
ROOT = pathlib.Path(__file__).resolve().parent.parent

class RecordUnavailable(Exception):
    """The record could not be loaded. Carries the guard's own message verbatim.

    Never paraphrase it — those messages name the exact file that was missing or the exact
    wrong path that was imported, and that is the whole value of them.
    """


def _the_records(e: BaseException) -> bool:
    """Was this raised inside the record's own modules — a cell the schema refuses, a rule the
    record asserts — as it loaded? Anything raised elsewhere is a fault, not the record."""
    tb = e.__traceback__
    while tb is not None:
        if "/portfusion/record/" in tb.tb_frame.f_code.co_filename.replace("\\", "/"):
            return True
        tb = tb.tb_next
    return False


def _guarded(fn):
    """Run something that imports the record, turning the record's refusal to load into a typed
    error: its guard's exit, or a cell or a rule it refuses on load."""
    try:
        return fn()
    except SystemExit as e:                     # rules's own: the store is not whole
        raise RecordUnavailable(str(e) or "the record refused to load, without a message") from e
    except (ValueError, AssertionError) as e:
        if not _the_records(e):
            raise
        raise RecordUnavailable(f"{type(e).__name__}: {e}") from e


# --- the engine ----------------------------------------------------------------------------
# Book() loads the whole store on construction, and re-reading the record first is the cheap
# part of that. Cached per REQUEST rather than per panel, because a page with four panels would
# otherwise pay for four engines. Keyed on the store's own modification time, so an edit to any
# CSV invalidates it without anyone having to remember to say so.
#
# NO MEASURED DURATION IS WRITTEN HERE. A typed timing outlives the code it measured.
_cache: dict = {"key": None, "book": None}


def store_mtime() -> float:
    """Newest modification time across the store the record reads (`schema.STORE`, which
    follows PORTFUSION_BOOK). The cache key, and the freshness line."""
    from portfusion.record import schema
    return max((p.stat().st_mtime for p in schema.STORE.glob("*.csv")), default=0.0)


def book():
    """The engine, cached until the store changes underneath it.

    REBUILDING THE ENGINE IS NOT ENOUGH ON ITS OWN. `Book()` reads rules' module-level tables
    rather than the files, and those are read ONCE, at import. A rebuild alone would produce a
    NEW ENGINE OVER THE SAME CACHED ROWS, and the header would call the desk current while it
    served a figure the store no longer held. So the record is reloaded first.

    The doors call `reload_store()` after their own writes, which covers a write made THROUGH
    the desk. This covers every other way the store moves: a hand edit, a git pull, a checkout,
    a revert.

    THE CHECK AND THE REBUILD ARE ONE STEP, under `schema.LOCK`: two rebuilds at once would
    reload the record over each other, and one could cache a Book over a half-read record. A
    door's write holds the same lock, so a rebuild never reads a store a door is part-way
    through. The Book, once built, needs no lock: it pins the record it was built from.
    """
    from portfusion.record import schema
    with schema.LOCK:
        key = store_mtime()
        if _cache["key"] != key:
            def _load():
                from portfusion import engine as _engine
                from portfusion.record import rules as _rules
                _rules.reload_store()
                return _engine.Book()
            _cache["book"] = _guarded(_load)
            _cache["key"] = key
        return _cache["book"]


_reports: dict = {"key": None, "value": None}


def reports() -> dict:
    """Every quarter the record has closed, the one it closes next, and each year: whether each
    quarter's report can be shown now, and what stops it. Newest first.

    THE REPORT'S OWN GATE DECIDES, never the desk: `report.gate.completeness()`, which
    `portfusion report --check` also asks, so the two cannot disagree about whether a quarter is
    ready. Cached on the store's mtime, as the engine is, and asked under `schema.LOCK` after
    `book()`, so the gate reads the record the Book was built from, or the refusal is raised.
    """
    from portfusion.record import schema
    key = store_mtime()
    if _reports["key"] == key:
        return _reports["value"]

    def _run():
        from portfusion.report.gate import completeness
        from portfusion.report.page import first_reported
        b = book()
        first = first_reported()
        closed = [str(q)[:10] for q in b.quarter_returns()["quarter_end"]]
        to_close = str(b.quarter_to_close().date())
        ends = closed + ([to_close] if to_close not in closed else [])
        quarters = [{"quarter": b.quarter_label(q, b.quarter_opens(q)), "quarter_end": q,
                     "reported": q >= first, "closed": q in closed,
                     "ended": q <= b.valued_at(), "gaps": completeness(q)} for q in ends]
        years = sorted({q[:4] for q in ends}, reverse=True)
        # A YEAR IS ITS NAME AND WHETHER ITS REPORT IS BUILT.
        return {"quarters": quarters[::-1], "first_reported": first,
                "years": [{"year": y, "built": False} for y in years]}

    with schema.LOCK:
        _reports.update(key=key, value=_guarded(_run))
    return _reports["value"]


def report_page(quarter_end: str) -> tuple[str | None, list[str]]:
    """One quarter's report, or what stops it. Nothing is written: the page is rendered for the
    request and handed back, the only way a report is made.

    FROM `book()`'S BOOK, UNDER `schema.LOCK`, as `reports()` asks: a record that refuses to
    reload refuses the report too, rather than a page drawn from the tables it refused."""
    from portfusion.record import schema

    def _run():
        from portfusion.report.gate import completeness
        from portfusion.report.page import render
        b = book()
        gaps = completeness(quarter_end)
        return (None, gaps) if gaps else (render(quarter_end, b), [])
    with schema.LOCK:
        return _guarded(_run)


def palette() -> dict:
    """The house style — DELEGATED to `desk/theme.py`, never re-derived here.

    Two routes to one answer can disagree. `engine.py` stays the one way the desk reads; the
    derivation lives in `theme.py`.
    """
    from portfusion.desk import theme
    return theme.palette()


def tokens_css() -> str:
    """The palette as CSS custom properties. Same delegation, same reason."""
    from portfusion.desk import theme
    return theme.tokens_css()


def precision() -> dict:
    """The places the page prints, house/precision.py's: sent with every panel, beside its heads,
    so app.js types none of its own — a percentage's, and a local price's per currency, with
    which fields are local prices."""
    from portfusion.house import precision as P
    return {"pct_dp": P.PCT_DP, "local_price_dp": dict(P.LOCAL_PRICE_DP),
            "local_price_default": P.DEFAULT_LOCAL_PRICE_DP,
            "local_price_fields": list(P.LOCAL_PRICE_FIELDS),
            "months": list(P.MONTHS)}


def lockup() -> str:
    """The book's lockup for the desk's header, `portfusion.brand`'s."""
    from portfusion import brand
    return brand.lockup()


# --- is this desk running the code that is on disk? ----------------------------------------
#
# A RUNNING SERVER SERVES WHAT IT IMPORTED, and without this the page has no way to say so.
#
# THE MIXTURE IS THE DANGEROUS PART. A wholly stale desk shows an old page and looks old. A
# desk with fresh static files and a stale engine renders new markup against old data and
# looks CONFIDENTLY WRONG.
#
# WHAT IS SCANNED IS WHAT THIS PROCESS ACTUALLY IMPORTED — `sys.modules` filtered to files
# under ROOT — so a module joins the check by being imported and there is no list to maintain.
#
# TWO THINGS ARE DELIBERATELY OUT OF SCOPE because they are already fresh, and flagging them
# would send the owner to the restart button when a browser refresh is enough — or when nothing
# at all is needed:
#   desk/static/*   served from disk per request
#   store/*.csv     the engine is cached on the store's own mtime, above
_source_seen: dict[str, float] = {}


def _repo_modules() -> dict[str, float]:
    """This project's own modules, as imported by this process, and their mtimes NOW: those under
    ROOT, the package. A dependency is outside it, and a dependency changing is a real event but
    not the one this signal reports."""
    out = {}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if not path:
            continue
        try:
            resolved = pathlib.Path(path).resolve()
            resolved.relative_to(ROOT)              # ValueError if outside the package
            out[str(resolved)] = resolved.stat().st_mtime
        except (ValueError, OSError):
            continue                                # not ours, or gone from disk
    return out


def source_stale() -> dict:
    """Which imported files have changed since this desk imported them.

    THE BASELINE IS PER FILE, RECORDED WHEN THAT FILE IS FIRST SEEN — not the process start
    time. The panels are imported lazily, on the first request that needs one, so against a
    process clock a panel edited BEFORE startup and imported AFTER it would report as stale
    when it is the newest thing in the building. A file first seen now is by definition the
    version this process is running.
    """
    changed = []
    for path, mtime in _repo_modules().items():
        first_seen = _source_seen.setdefault(path, mtime)
        if mtime > first_seen:
            changed.append((mtime, str(pathlib.Path(path).relative_to(ROOT))))
    changed.sort(reverse=True)
    return {"stale": bool(changed),
            "changed_at": changed[0][0] if changed else None,
            "files": [name for _, name in changed]}


def freshness() -> dict:
    """When the store last changed, the date the prices stand at, whether the desk's own code has
    moved under it, and the hosted desk's state. Every page carries this line.

    THE CODE IS THE SIGNAL A READER ACTS ON HERE — see `source_stale()` — and it is what says when
    the restart button on this line is needed.
    """
    s = store_mtime()

    from portfusion.house.precision import day, moment

    def _stamp(t):
        return None if not t else moment(_dt.datetime.fromtimestamp(t))

    # THE PRICE DATE. Book.valued_at() is the newest mark, which the Dashboard and What Changed
    # already share — one answer to "what does now mean", stated where the refresh starts from.
    try:
        prices_as_at = book().valued_at()
    except Exception:                       # noqa: BLE001 — a header must not take the page down
        prices_as_at = None

    src = source_stale()
    # THE HOSTED DESK — its tunnel, and whether what is published is what is on disk.
    # None unless this process opened the remote door. desk/publish.py reads it locally.
    try:
        from portfusion.desk import publish
        hosted = publish.status()
    except Exception:                       # noqa: BLE001 — as the price date above
        hosted = None
    return {"store_changed": _stamp(s),
            "prices_as_at": day(prices_as_at) if prices_as_at else None,
            "source_stale": src["stale"],
            "source_changed": _stamp(src["changed_at"]),
            # NAMED, NOT COUNTED. "3 files changed" sends you looking; "engine.py" tells you
            # what moved. Capped so a rebase does not fill the header line, with the full
            # count beside it so the cap is visible rather than silent.
            "source_files": src["files"][:4],
            "source_count": len(src["files"]),
            "hosted": hosted}
