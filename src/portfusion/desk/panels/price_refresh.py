"""PRICE REFRESH — the sweep as a screen.

`feeds/refresh.py:sweep()` fetches and prints; this panel is where the lines are reviewed. Its
fetch is `desk/intake/sweep.py`'s and its write the marks door's `refresh()`, where its two rules
— bank before replacing, and the levels with the equity — are structural rather than remembered.

    1  BANK     the outgoing marks, before anything replaces them
    2  FETCH    one sweep — `feeds/refresh.py:sweep()`, the same one the terminal prints
    3  REVIEW   every line ticked, each with a source AND a date
    4  WRITE    marks and IG readings together, banked first, in one operation

THE CLICK OPENS THE BAY; IT DOES NOT FIRE A REFRESH. A refresh is slow, reaches the network and
replaces data, and a bare button that acts on click is the wrong shape for all three. Nothing
leaves the machine and nothing is written until the owner has seen what will be fetched and ticked
what will land — the same gate the bench uses for a document, for the same reason.

THIS PANEL DECIDES NOTHING. Which marks can be replaced and which are carried is
`Book.marks_replaceable()`; whether the outgoing set is on file is `marks.banked()`; what may
be written and what must be refused is `marks.write()` and `observations.write()`. A panel that classified a mark here
would be the third place that answers a question the record already answers.
"""
from __future__ import annotations

import pandas as pd

from portfusion.desk import engine
from portfusion.desk.actions import Action, register
from portfusion.desk.doors import marks
from portfusion.desk.intake import sweep
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
    """The bay's state. Every figure is the engine's or the door's; nothing is decided here."""
    # ONE BOOK FOR THE WHOLE BAY, the desk's, so the outgoing marks are the record the figures
    # below are drawn from, and a store that will not load answers "record unavailable".
    b = engine.book()
    can = b.marks_replaceable()
    return {
        "steps": [{"key": k, "label": lb, "detail": d} for k, lb, d in STEPS],
        "today": can["today"],
        # THE THRESHOLD TRAVELS WITH THE ROWS, so the label can say how many are actually old
        # without the panel holding an opinion about what old is.
        "age_limit": can["age_limit"],
        "banked": _banked(),
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
        "lacking": b.rate_gaps(),
        "valued_at": b.valued_at(),
        # THE MARKS' AGE, the engine's and the Dashboard's one figure (`Book.price_ageing()`).
        "age_days": b.price_ageing()["age_days"],
    }


#: THE MARK KEY, as the grid heads it: a share's ticker, or an IG contract for a bet,
#: whose price is a level in points (`contract`, the engine's word on the row).
PRICE_COLUMNS = ("mark_key", "price", "currency", "as_of", "age_days", "stale", "contract")

#: The refresh grid's heads, one row per line: the mark on file, then the one fetched.
GRID_COLUMNS = ("mark_key", "was", "was_at", "new", "new_at", "source", "origin", "take")


def _frame(rows: list[dict]):
    """A list of dicts as something `_shape.rows` can take. The engine already shaped these; the
    mark's key is named for what it is here."""
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _banked() -> dict:
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

register(Action(
    name="refresh-fetch-all", label="Fetch everything", panel=NAME,
    writes=None, reaches="network",
    gate="The owner clicks it. Nothing is fetched when the bay is merely opened.",
    summary=("One sweep: IG's contract levels and each account's equity, then TradingView's "
             "shares and rates, and the Live List checked against the book. It fills the form "
             "and writes nothing. A vendor that fails is named and the rest still lands."),
    run=sweep.prices,
))


register(Action(
    name="refresh-write-marks", label="Write the ticked marks", panel=NAME,
    writes="marks", reaches=None,
    gate=("The owner ticks each line. Nothing is written until they have, and a line without a "
          "source and a date cannot be ticked at all."),
    summary=("Bank the outgoing marks and IG readings, replace them with the ticked ones, then "
             "bank those. One operation: if any part of it is refused, every file is left exactly "
             "as it was. A feed may write a mark — a price, a rate, live "
             "equity — on the owner's tick, and never an event."),
    run=marks.refresh,
))
