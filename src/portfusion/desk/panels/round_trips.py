"""ROUND TRIPS — every position that has been closed, and what it did.

Round trips can be narrowed to a company,
a ticker, an account or a range of EXIT dates, which is what you actually want when asking "how
has PENR gone for us" — the answer is several round trips across several years, and reading them
together is the point. A company is every code it is held under, its share and its spread bet in one
choice, as on Trades (14 Oct 2026). THE HEADLINE FIGURES FOLLOW THE SELECTION: narrowing to an account and
leaving the whole book's realisations, proceeds and gain on screen answers a question nobody
asked.

REALISED GAIN IS NET OF COMMISSION, and that is not an oversight to be corrected here: proceeds
are recorded net, so the dealing cost is already inside the gain. `store/income.csv` carries
NON-TRANSACTION costs only. Adding commission again would double-count it.

A ROUND TRIP THE BOOK CANNOT FULLY SOURCE opened before the record begins, so its entry side is
carried rather than evidenced. Its Entry date says so, and the row is shown, never quietly
dropped; the engine's `pre_baseline` flag is not a column of its own.
"""
from __future__ import annotations


from portfusion.desk import engine
from portfusion.desk.panels import _shape

NAME = "round-trips"
TITLE = "Round Trips"
ORDER = 50

#: IN HOLDINGS' ORDER: what the line is, how much and at what prices, in its own currency, what
#: it cost and brought in, then its dates. The per-share prices were sterling until 14 Oct 2026.
COLUMNS = ("ticker", "company", "held_as", "account", "currency", "qty", "entry_price",
           "exit_price", "cost", "proceeds", "gain", "gain_pct", "opened", "closed", "held_days",
           "fully_closed")

#: THE ROW'S KEY, carried and not drawn: R- and the ticker repeats the Ticker column, and Trades'
#: detail shows it beside each sale it joins.
KEY = "realisation_id"

#: A SPREAD BET IN ITS OWN TERMS, for the Quantity and the two price cells, as Trades reads
#: one: a stake per point, entered and exited at levels in points.
BET_COLUMNS = ("stake_per_point", "entry_level_points", "exit_level_points")

#: THE JUDGEMENT, in the row's detail with its note: `Book.with_reasoning()`'s — every why dated
#: between the parcel's entry and its last sale, oldest first, each half owed from its own date:
#: the thesis from the entry, the exit reason from the exit.
REASON_COLUMNS = ("whys", "research_notes")
OWED = ("why_entered_owed", "why_exited_owed")

#: WHAT A ROW'S DETAIL OPENS, under app.js's one desk-wide order: the whys, the research notes,
#: then the note, which says what happened.
DETAIL_COLUMNS = ("why_entered", "why_exited", "research_notes", "note")


def data() -> dict:
    return query()


def query(ticker: str | None = None, account: str | None = None,
          start: str | None = None, end: str | None = None, company: str | None = None) -> dict:
    """Narrow the closed positions. SELECTION, and the ENGINE does it.

    THE TOTALS FOLLOW THE SELECTION: narrowing to an account must change the
    realisations, proceeds and gain shown, not only the table beneath them.

    NOTHING IS SUMMED HERE. Adding up the filtered rows would be a second calculation of
    something `book.round_trip_totals()` answers, and this panel has no place on
    `tests/test_figures.py`'s ALLOWED list. The engine takes ticker, account, start and end,
    and both the rows and the totals come back from it.

    `whole` is still carried so the screen can say what the selection is a part of.
    """
    b = engine.book()
    pick = dict(ticker=ticker, account=account, start=start, end=end, company=company)
    frame = b.with_reasoning(b.round_trips(**pick), opened="opened", closed="closed")
    selected = b.round_trip_totals(**pick)
    whole = b.round_trip_totals()
    narrowed = any(pick.values())
    every = b.round_trips()
    codes = _shape.company_codes(every)

    return {
        "rows": _shape.rows(frame, (KEY,) + COLUMNS + BET_COLUMNS + REASON_COLUMNS + ("note",) + OWED,
                            dates=("closed", "opened")),
        "columns": list(COLUMNS),
        "detail": list(DETAIL_COLUMNS),
        # THE FIGURES ON SCREEN ARE THE SELECTION'S. `whole` sits beside them when one is on.
        "totals": {k: _shape.plain(v) for k, v in selected.items()},
        "whole": {k: _shape.plain(v) for k, v in whole.items()},
        "narrowed": narrowed,
        "ticker": ticker or "",
        "company": company or "",
        "account": account or "",
        "start": start or "",
        "end": end or "",
        # THE TICKER LIST IS THE CHOSEN COMPANY'S, so the two boxes cannot contradict each other.
        "tickers": codes.get(company, []) if company else _shape.uniques(every, "ticker"),
        "companies": sorted(codes),
        "accounts": _shape.accounts(every, "account", b.account_order()),
        # The span the record actually covers, so the date inputs can bound themselves rather
        # than offering a range with nothing in it.
        "span": {"first": _shape.iso(every["closed"].min()),
                 "last": _shape.iso(every["closed"].max())},
        "total": len(frame),
    }
