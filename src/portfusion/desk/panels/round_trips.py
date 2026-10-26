"""ROUND TRIPS — every position that has been closed, and what it did.

Round trips can be narrowed to a company, a ticker, an account or a range of EXIT dates, which is
what you actually want when asking "how has PENR gone for us" — the answer is several round trips
across several years, and reading them together is the point. A company is every code it is held
under, its share and its spread bet in one choice, as on Trades. THE HEADLINE FIGURES FOLLOW THE
SELECTION: narrowing to an account and leaving the whole book's realisations, proceeds and gain on
screen answers a question nobody asked.

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
#: it cost and brought in, then its dates.
COLUMNS = ("ticker", "company", "held_as", "account", "currency", "qty", "entry_price",
           "exit_price", "cost", "proceeds", "realised", "realised_pct", "opened", "closed", "days_held",
           "fully_closed")

#: THE ROW'S KEY, carried and not drawn: R- and the ticker repeats the Ticker column, and Trades'
#: detail shows it beside each sale it joins.
KEY = "realisation_id"

#: A SPREAD BET IN ITS OWN TERMS, for the Quantity and the two price cells, as Trades reads
#: one: a stake per point, entered and exited at levels in points.
BET_COLUMNS = ("stake", "entry_level_points", "exit_level_points")

#: THE JUDGEMENT, in the row's detail with its note: `Book.with_reasoning()`'s — every why dated
#: between the parcel's entry and its last sale, oldest first, each half owed from its own date:
#: the thesis from the entry, the exit reason from the exit.
REASON_COLUMNS = ("whys", "research_notes")
OWED = ("why_entered_owed", "why_exited_owed")

#: WHAT A ROW'S DETAIL OPENS, under kit.js's one desk-wide order: the whys, the research notes,
#: then the note, which says what happened.
DETAIL_COLUMNS = ("why_entered", "why_exited", "research_notes", "note")


#: TWO VIEWS, kept apart: each holding's own sales at its own cost, or each company's life,
#: shares and bets in every account from the first purchase to the final sale (`company_lives()`).
VIEWS = ("holding", "life")
VIEW_WORDS = {"holding": "holding", "life": "company life"}

#: A COMPANY LIFE IN ITS OWN TERMS: what it is, when, what it made and how, then what is held and
#: at what life cost. Its round trips and lines open in the detail.
LIFE_COLUMNS = ("company", "held_as", "accounts", "state", "opened", "closed", "days_held",
                "realised", "unrealised", "dividends", "funding_interest", "life_gain", "life_pct", "qty",
                "life_cost_per_share", "price", "currency")
LIFE_DETAIL_COLUMNS = ("realisations", "lines")


def data() -> dict:
    return query()


def query(ticker: str | None = None, account: str | None = None,
          start: str | None = None, end: str | None = None, company: str | None = None,
          view: str = VIEWS[0]) -> dict:
    """Narrow the closed positions. SELECTION, and the ENGINE does it.

    THE TOTALS FOLLOW THE SELECTION: narrowing to an account must change the
    realisations, proceeds and gain shown, not only the table beneath them.

    NOTHING IS SUMMED HERE. Adding up the filtered rows would be a second calculation of
    something `book.round_trip_totals()` answers, and this panel has no place on
    `tests/test_figures.py`'s ALLOWED list. The engine takes ticker, account, start and end,
    and both the rows and the totals come back from it.

    `whole` is still carried so the screen can say what the selection is a part of.
    """
    if view not in VIEWS:
        raise ValueError(f"view {view!r}; Round Trips reads {VIEWS}")
    if view == "life":
        return _lives(start=start, end=end, company=company)
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
        # THE HALVES A ROW MAY OWE: a row owing either wears the "owed" tag.
        "owed": list(OWED),
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
        **_views("holding"),
    }


def _views(view: str) -> dict:
    return {"view": view, "views": list(VIEWS), "view_words": VIEW_WORDS}


def _lives(start=None, end=None, company=None) -> dict:
    """THE LIFE VIEW. A life spans accounts and codes, so it is narrowed by company and by the
    day it closed only; the engine selects and totals."""
    b = engine.book()
    pick = dict(start=start, end=end, company=company)
    frame = b.company_lives(**pick)
    every = b.company_lives()
    return {
        "rows": _shape.rows(frame, ("life",) + LIFE_COLUMNS + LIFE_DETAIL_COLUMNS + ("pre_baseline",),
                            dates=("opened", "closed")),
        "columns": list(LIFE_COLUMNS),
        "detail": list(LIFE_DETAIL_COLUMNS),
        "totals": {k: _shape.plain(v) for k, v in b.company_life_totals(**pick).items()},
        "whole": {k: _shape.plain(v) for k, v in b.company_life_totals().items()},
        "narrowed": any(pick.values()),
        "company": company or "",
        "start": start or "",
        "end": end or "",
        "companies": sorted(set(every["company"])),
        "span": {"first": _shape.iso(every["closed"].min()),
                 "last": _shape.iso(every["closed"].max())},
        "total": len(frame),
        **_views("life"),
    }
