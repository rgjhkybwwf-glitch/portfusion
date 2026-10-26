"""TRADES — every buy and sale on file, for open positions and closed, interrogable.

Any span, account, company, ticker or direction of them can be asked for.

FILTERING IS THE ENGINE'S, NOT THIS MODULE'S. `book.activity(start, end, account)` already takes
exactly those arguments; re-implementing a date comparison here would be a second answer to a
question the engine answers. Ticker and direction are narrowed on the returned frame, which is
selection rather than calculation.

A TRADE LOG, READ BACK: each line is the deal as struck, and everything else the record holds
on it — why, what happened, where it came from — is in its detail.
"""
from __future__ import annotations


from portfusion.desk import engine
from portfusion.desk.panels import _shape
from portfusion.record import schema

NAME = "trades"
TITLE = "Trades"
ORDER = 60

#: THE DEAL AS STRUCK, IN HOLDINGS' ORDER: what the line is, how much and at what price, the money,
#: then the date. Direction stands where Holdings has Type. No Company (the ticker names the
#: line; the Company filter still finds both legs), no Type (every bet's code ends "SB"), no
#: Ownership, and no realised gain (Round Trips', one click away).
COLUMNS = ("ticker", "direction", "account", "currency", "qty", "traded_price", "value", "date")

#: A SPREAD BET IN ITS OWN TERMS, for the Quantity and Traded price cells: a stake per point at
#: a level in points, as the record keeps them.
BET_COLUMNS = ("stake", "level_points")

#: WHAT A ROW'S DETAIL OPENS, under kit.js's one desk-wide order: the whys on the trade, the
#: note, then where it came from and what it belongs to — a bet leg's contract and how IG funds
#: it among them (schema.FUNDINGS), the fact its funding-interest rows rest on — and a foreign
#: deal's rate with whose it is.
DETAIL_COLUMNS = ("why_entered", "why_exited", "note", "source", "broker_ref", "trade_id",
                  "sale_id", "realisation_id", "contract", "funding", "fx_at_trade", "fx_from")


def data() -> dict:
    b = engine.book()
    frame = b.activity()
    return {
        "rows": _rows(b, frame),
        "total": int(len(frame)),
        "accounts": _shape.accounts(frame, "account", b.account_order()),
        "tickers": _shape.uniques(frame, "ticker"),
        "companies": _companies(frame),
        # EACH COMPANY'S CODES IN THE LEDGER: the Ticker box lists the chosen company's alone, so
        # it cannot name a line the Company box has ruled out.
        "company_tickers": _shape.company_codes(_with_company(frame)),
        "directions": _shape.uniques(frame, "direction"),
        "columns": list(COLUMNS),
        "detail": list(DETAIL_COLUMNS),
        "span": {"first": _shape.iso(frame["date"].min()), "last": _shape.iso(frame["date"].max())},
    }


def tickers_for_company(company: str) -> list[str]:
    """Every code this company is held under — SHARES AND SPREAD BETS BOTH.

    Orlant is ORLA and ORLA SB, and the whole point of asking for a company's trade history is
    that you want both legs of it. From store/securities.csv rather than from the open holdings,
    because a closed position still has a history and would be missing from the latter.
    """
    return sorted(r[0] for r in schema.load("securities") if r[1] == company)


def query(start=None, end=None, account=None, ticker=None, direction=None,
          company=None) -> dict:
    """Interrogate the ledger. Dates and account go to the engine; the rest narrow the result."""
    b = engine.book()
    frame = b.activity(start=start or None, end=end or None, account=account or None)
    if company:
        # ONE CLICK FROM HOLDINGS SHOWS BOTH LEGS. A company filter rather than a ticker one,
        # because "the trade history for a company" means ORLA and ORLA SB together — asking by
        # ticker would answer half the question and look complete.
        frame = frame[frame["ticker"].isin(tickers_for_company(company))]
    if ticker:
        frame = frame[frame["ticker"] == ticker]
    if direction:
        frame = frame[frame["direction"] == direction]
    return {"rows": _rows(b, frame), "total": int(len(frame)),
            "span": {"first": _shape.iso(frame["date"].min()), "last": _shape.iso(frame["date"].max())}}


def _rows(b, frame) -> list[dict]:
    """The rows, each with THE WHYS ON THE TRADE: reasoning.csv's rows for its ticker dated on its
    day, which is the date a why is filed under (`Book.with_reasoning()`, its window shut to the
    one day). Only the whys: whether one is owed, and the research notes, are the position's,
    on Holdings and Round Trips."""
    frame = b.with_reasoning(frame, opened="date", closed="date")
    fields = COLUMNS + BET_COLUMNS + tuple(c for c in DETAIL_COLUMNS if c in frame) + ("whys",)
    return _shape.rows(frame, fields, dates=("date",))


def _with_company(frame):
    """The ledger's rows with each code's company beside it, from the securities register."""
    by_code = {r[0]: r[1] for r in schema.load("securities")}
    return frame.assign(company=frame["ticker"].map(by_code))


def _companies(frame) -> list[str]:
    """The companies that actually appear in the ledger, in name order. A register entry with
    no trade behind it would be an option that returns nothing."""
    by_code = {r[0]: r[1] for r in schema.load("securities")}
    return sorted({by_code[c] for c in _shape.uniques(frame, "ticker") if c in by_code})


