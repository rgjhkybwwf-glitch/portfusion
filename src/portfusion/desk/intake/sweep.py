"""THE SWEEPS — every read the desk asks of the feeds: the Price Refresh's sweep, the Bench's IG
event sweep, and a new contract's first level. Every action that reaches the network runs a
function here (`tests/desk/test_boundaries.py`); `feeds/` may not import the desk, so what a read
needs of the desk is handed to it from here.

IT WRITES NOTHING. A sweep fills a form or opens a Bench item; the marks door and the commit write.
"""
from __future__ import annotations

from portfusion.desk import engine
from portfusion.desk.intake import bench


def prices(on=None, lacking=False):
    """THE SWEEP, as `feeds/refresh.py` takes it; with `on`, one past day's closes, which the
    write then banks into the histories rather than over the live marks; with `lacking`, the
    closes of the dated rates the record lacks (`Book.rate_gaps()`), one TradingView read per
    currency, banked the same way under the newest of their days.

    ONE GESTURE AND A REVIEW. Each vendor reports separately, so a failure names its vendor and
    the rest still lands. The far contracts' past levels come off the filed IG statements, read
    here because `feeds/` may not import the desk.
    """
    if lacking:
        return _lacking()
    try:
        from portfusion.feeds import refresh
        from portfusion.desk.intake import statement_closes
    except Exception as e:                          # noqa: BLE001
        return {"ok": False, "error": f"the sweep could not be imported: {e}"}
    return {"ok": True, **_with_sources(refresh.sweep(on, filed=statement_closes.closes))}


def _lacking() -> dict:
    """The dated rates the record lacks, read from TradingView: the sweep's shape, with only its
    `tv` part, `lacking` set, and `on` the newest session read — the day the write banks under."""
    wanted: dict[str, list] = {}
    for g in engine.book().rate_gaps():
        wanted.setdefault(g["currency"], []).append(g["date"])
    try:
        from portfusion.feeds import tv
        got = {"ok": True, **tv.rate_closes(wanted)}
    except Exception as e:                          # noqa: BLE001 — the vendor, named
        got = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    days = [r["as_of"] for r in got.get("rates", [])]
    return {"ok": True, "lacking": True, "on": max(days) if days else None, "tv": got}


def _with_sources(swept: dict) -> dict:
    """Each IG account's row, given the provenance line its reading will be filed under: the
    record's own words for the reading's evidence and reference (`rules.evidence_source()`),
    so the review shows what the write records and nothing the record will not keep."""
    D = engine.book().D
    eq = swept.get("ig_equity") or {}
    line = {r["account"]: D.evidence_source(r["evidence"], reference=r["reference"],
                                            account=r["account"])
            for r in eq.get("readings") or []}
    for row in eq.get("rows") or []:
        row["source"] = line.get(row["account"], "")
    return swept


def _ig(fn, *a):
    """Run an IG read, turning the ways it can legitimately fail into something renderable.

    A broker being down, or credentials not being present, is an ORDINARY outcome for a panel
    and must not look like a bug. The message is passed through as-is: `load_credentials` says
    exactly which file is missing, and paraphrasing would throw that away.
    """
    try:
        from portfusion.feeds import ig
    except Exception as e:
        return {"ok": False, "error": f"feeds/ig.py could not be imported: {e}"}
    try:
        return {"ok": True, "result": fn(ig, *a)}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"no credentials: {e}",
                "hint": "credentials.json is gitignored and is not present until you create it."}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def ig_events(since=None):
    """IG's events over the look-back the Bench chose (`feeds/ig.ig_events()`'s `since`), each
    checked against the book."""
    return _ig(lambda ig, s: ig.ig_events(s, book=engine.book()), since)


def set_up(event: dict) -> dict:
    """Read the new contract's live level from IG, then carry the event and its set-up across."""
    new = [r["values"] for r in event.get("with") or [] if r.get("table") == "contracts"]
    if len(new) != 1 or not str(new[0].get("epic") or "").strip():
        return {"ok": False, "error": "a set-up carries one new contract, with its epic"}
    contract, epic = str(new[0]["contract"]).strip(), str(new[0]["epic"]).strip()
    got = _ig(lambda ig: ig.contract_levels({contract: (None, epic)}))
    if not got["ok"]:
        return {"ok": False, "error": got["error"]}
    level = got["result"]["rows"][0]
    if not level["priced"]:
        return {"ok": False, "error": f"IG gave no level for {epic}: {level['status']}"}
    mark = {"mark_key": contract, "price": level["level"], "currency": level["currency"],
            "as_of": level["as_of"], "source": level["source"], "struck": level["struck"],
            "at": level["at"]}
    return bench.to_bench(event, marks=[mark])
