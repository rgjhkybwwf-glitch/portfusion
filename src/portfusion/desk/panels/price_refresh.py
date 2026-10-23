"""PRICE REFRESH — the sweep as a screen, and the one door every mark it fetches comes through.

`feeds/refresh.py:sweep()` fetches and prints; this panel is where the lines are reviewed and
written. Its two rules — bank before replacing, and the levels with the equity — are structural
here rather than remembered.

    1  BANK     the outgoing marks, before anything replaces them
    2  FETCH    one sweep — `feeds/refresh.py:sweep()`, the same one the terminal prints
    3  REVIEW   every line ticked, each with a source AND a date
    4  WRITE    marks and IG readings together, banked first, in one operation

THE CLICK OPENS THE BAY; IT DOES NOT FIRE A REFRESH. A refresh is slow, reaches the network and
replaces data, and a bare button that acts on click is the wrong shape for all three. Nothing
leaves the machine and nothing is written until the owner has seen what will be fetched and ticked
what will land — the same gate the bench uses for a document, for the same reason.

THIS PANEL DECIDES NOTHING. Which marks can be replaced and which are carried is
`engine.marks_replaceable()`; whether the outgoing set is on file is `marks.banked()`; what may
be written and what must be refused is `marks.write()` and `observations.write()`. A panel that classified a mark here
would be the third place that answers a question the record already answers.
"""
from __future__ import annotations

import contextlib
import traceback

from portfusion.desk import engine
from portfusion.desk.actions import Action, register
from portfusion.desk.panels import _shape

NAME = "price-refresh"
TITLE = "Price Refresh"

#: THE ORDER OF THE WORK, not of the reading. This sits BEFORE What Changed
#: because that is the loop as it is actually run: the header says the marks are stale, you run
#: the refresh here, and then you read what it did. What tells you to refresh is the freshness
#: line in the header, not a report on the previous refresh.
ORDER = 25

#: The four steps, in `feeds/refresh.py`'s own order. The order is the point of the panel, and
#: it is why `feeds/refresh.py` is one command rather than two: two commands are two chances to
#: forget one.
STEPS = (
    ("bank", "Bank", "The outgoing marks go to their histories before anything replaces them. "
                     "A refresh done without this is a data point that cannot be recovered."),
    ("fetch", "Fetch", "One sweep: IG's contract levels and each account's equity, read back "
                       "to back, then TradingView's shares and rates, each at its own instant. "
                       "Nothing is ticked for you. With a date, that day's closes instead: the "
                       "write banks them into the histories and leaves the live marks alone."),
    ("review", "Review", "Every line ticked, and no line accepted without a source and a date "
                         "together."),
    ("write", "Write", "Marks and IG readings replaced, then banked, in one operation. Refused "
                       "entirely if any line is incomplete or is one the book carries."),
)

def data() -> dict:
    return query()


def query() -> dict:
    """The bay's state. Every figure is the engine's or the door's; nothing is decided here."""
    from portfusion.desk.doors import marks

    # THE ENGINE THROUGH THE DESK'S GUARD, not imported with the module: a store that would not
    # load stopped the import, and the page answered a bare 500 rather than "record unavailable".
    def _replaceable():
        from portfusion.engine import marks_replaceable
        return marks_replaceable()
    can = engine._guarded(_replaceable)
    return {
        "steps": [{"key": k, "label": lb, "detail": d} for k, lb, d in STEPS],
        "today": can["today"],
        # THE THRESHOLD TRAVELS WITH THE ROWS, so the label can say how many are actually old
        # without the panel holding an opinion about what old is.
        "age_limit": can["age_limit"],
        "banked": _banked(marks),
        # A CARRIED LINE IS LEFT OFF THE SCREEN, not listed: it is a
        # decision, not work, and offering it would invite undoing that decision by accident.
        # `marks.write()` refuses one by name either way.
        # EACH GROUP RUNS A-Z BY ITS LINE, which puts an IG contract beside its company.
        "prices": sorted(_shape.rows(_frame(can["replaceable"]), PRICE_COLUMNS),
                         key=lambda r: str(r["mark_key"]).upper()),
        # THE OUTGOING MARK'S SOURCE STAYS HOME: a line's banked marks, sources and all, are its
        # Holdings detail's Mark history. A carried rate is left off, so `carried` says nothing.
        "rates": sorted(({k: v for k, v in r.items() if k not in ("source", "carried", "why")}
                         for r in can["fx"] if not r["carried"]), key=lambda r: r["currency"]),
        "readings": sorted(can["readings"], key=lambda r: r["account"]),
        # THE DATED RATES THE RECORD LACKS, each with the rate its date converts at
        # today: the fetch below reads their closes, and the write banks them into the history.
        "lacking": engine.book().rate_gaps(),
        "valued_at": engine.book().valued_at(),
        # THE MARKS' AGE, the engine's and the Dashboard's one figure (`Book.price_ageing()`).
        "age_days": engine.book().price_ageing()["age_days"],
    }


#: THE MARK KEY, as the grid heads it: a share's ticker, or an IG contract for a bet,
#: whose price is a level in points (`contract`, the engine's word on the row).
PRICE_COLUMNS = ("mark_key", "price", "currency", "as_of", "age_days", "stale", "contract")

#: The refresh grid's heads, one row per line: the mark on file, then the one fetched.
GRID_COLUMNS = ("mark_key", "was", "was_at", "new", "new_at", "source", "origin", "take")


def _frame(rows: list[dict]):
    """A list of dicts as something `_shape.rows` can take. The engine already shaped these; the
    mark's key is named for what it is here."""
    import pandas as pd
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _banked(marks) -> dict:
    """Step 1's state, and it must not take the panel down with it.

    `marks.banked()` imports `history/`, which is a tool ALONGSIDE the build and can be absent
    or broken without the desk being wrong about anything else. A panel that raised here would
    hide the whole refresh behind a missing sibling.
    """
    try:
        state = marks.banked()
    except Exception as e:                          # noqa: BLE001 — reported, never swallowed
        return {"ok": False, "unavailable": str(e), "prices": 0, "rates": 0}
    return {"ok": state["ok"], "unavailable": None,
            "prices": len(state["prices_unbanked"]), "rates": len(state["rates_unbanked"])}


# ---- THE ACTIONS ----------------------------------------------------------------------------
#
# TWO KINDS, ON DIFFERENT AXES. The fetches REACH the network and write nothing; the write
# WRITES MARKS and reaches nothing. The marks rule's two fields, each doing its own job — see
# desk/actions.py for why that is two fields and not a fourth value on one.

def _fetch_all(on=None, lacking=False):
    """THE SWEEP, as `feeds/refresh.py` takes it; with `on`, one past day's closes, which the
    write then banks into the histories rather than over the live marks; with `lacking`, the
    closes of the dated rates the record lacks (`Book.rate_gaps()`), one TradingView read per
    currency, banked the same way under the newest of their days.

    ONE GESTURE AND A REVIEW. Each vendor reports separately, so a failure names its vendor and
    the rest still lands. The far contracts' past levels come off the filed IG statements, read
    here because `feeds/` may not import the desk.
    """
    if lacking:
        return _fetch_lacking()
    try:
        from portfusion.feeds import refresh
        from portfusion.desk.intake import statement_closes
    except Exception as e:                          # noqa: BLE001
        return {"ok": False, "error": f"the sweep could not be imported: {e}"}
    return {"ok": True, **_with_sources(refresh.sweep(on, filed=statement_closes.closes))}


def _fetch_lacking() -> dict:
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
    from portfusion.record import rules as D
    eq = swept.get("ig_equity") or {}
    line = {r["account"]: D.evidence_source(r["evidence"], reference=r["reference"],
                                            account=r["account"])
            for r in eq.get("readings") or []}
    for row in eq.get("rows") or []:
        row["source"] = line.get(row["account"], "")
    return swept


register(Action(
    name="refresh-fetch-all", label="Fetch everything", panel=NAME,
    writes=None, reaches="network",
    gate="The owner clicks it. Nothing is fetched when the bay is merely opened.",
    summary=("One sweep: IG's contract levels and each account's equity, then TradingView's "
             "shares and rates, and the Live List checked against the book. It fills the form "
             "and writes nothing. A vendor that fails is named and the rest still lands."),
    run=_fetch_all,
))


def _write(prices=None, rates=None, readings=None, close_of=None):
    """Bank the outgoing marks and IG readings, and replace them: ONE operation, or none of it.

    THE LEVELS AND THE EQUITY ARE ONE OBSERVATION, so they land or fail together. The two doors
    each hold only their own files, so this holds the union, and a refusal from either rolls both
    back; `D.reload_store()` runs on that path because the files go back and the record in memory
    has to follow them.

    `close_of` is a past day's closes: `marks.bank_closes()` files them into the histories and the
    live marks are left as they are. A past day has no reading.

    THE REFUSAL IS THE FEATURE. Either door refuses the whole operation, leaving every file
    byte-identical, if any line lacks a source or a date, names a carried line, or names a row
    that is not there.
    """
    from portfusion.record import rules as D
    from portfusion.desk.doors import commit, marks, observations
    prices, rates, readings = list(prices or []), list(rates or []), list(readings or [])
    contracts = set(D.LEG_CONTRACT.values())
    try:
        if not (prices or rates or readings):
            raise marks.Refused("nothing to write — no line was ticked.")
        if close_of:
            if readings:
                raise marks.Refused("a past day's closes carry no account reading: equity is "
                                    "read live, with the levels, or not at all")
            return {"ok": True, **marks.bank_closes(close_of, prices=prices, rates=rates)}
        if readings and not any(p.get("mark_key") in contracts for p in prices):
            raise marks.Refused("an IG account's equity is written with the contract levels "
                                "read in the same pass, and none is among the ticked lines")
        with commit.atomic(*marks.paths(), *observations.paths()):
            written = marks.write(prices=prices, rates=rates) if (prices or rates) else {}
            read = observations.write(readings=readings) if readings else {}
    except (marks.Refused, observations.Refused) as e:
        D.reload_store()
        return {"ok": False, "refused": str(e)}
    except Exception as e:                          # noqa: BLE001 — reported, never swallowed
        # A FAULT, NOT A REFUSAL, and the files are back just the same: `atomic()` restored them.
        # The record in memory follows them, or it would go on serving marks the files no longer
        # hold; and the page says what failed, where it had a bare 500 until 14 Oct 2026. The
        # trace goes to the desk's log.
        traceback.print_exc()
        with contextlib.suppress(Exception):
            D.reload_store()
        return {"ok": False, "refused": f"the write failed, and every file is as it was: "
                                        f"{type(e).__name__}: {e}"}
    return {"ok": True, **written, "readings": read.get("written", 0),
            "accounts": read.get("accounts", [])}


register(Action(
    name="refresh-write-marks", label="Write the ticked marks", panel=NAME,
    writes="marks", reaches=None,
    gate=("The owner ticks each line. Nothing is written until they have, and a line without a "
          "source and a date cannot be ticked at all."),
    summary=("Bank the outgoing marks and IG readings, replace them with the ticked ones, then "
             "bank those. One operation: if any part of it is refused, every file is left exactly "
             "as it was. A feed may write a mark — a price, a rate, live "
             "equity — on the owner's tick, and never an event."),
    run=_write,
))
