"""PERFORMANCE — how the book has done, per quarter, for the book and for each account.

EVERY RETURN HERE IS ON NET ASSET VALUE, never on exposure, and the panel says so in the payload
rather than trusting a reader to remember. Dividing a gain that includes spread-bet movement by a
total that includes spread-bet notional is the arithmetic the whole basis split exists to
prevent — the two figures answer different questions and a ratio across them is meaningless.

NOTHING IS COMPUTED HERE. `book.quarter_returns()` and `book.account_quarter_returns()` are
the engine's, and a percentage worked out in this module — or in the browser — would be a
second calculation of a figure the engine already answers.

AN ACCOUNT FUNDED INSIDE A QUARTER OPENS IT ON ZERO, and its return is then on the money put in,
weighted by the days it was in. The engine flags the row (`opened_in_period`) and words it once
(`Book.OPENED_IN_PERIOD`); `_caveats()` prints it, because a figure like that is exactly what
gets mistaken for a defect later.
"""
from __future__ import annotations

from portfusion.desk import engine
from portfusion.desk.panels import _shape

NAME = "performance"
TITLE = "Performance"
ORDER = 30

#: ONE SET OF COLUMNS FOR THE BOOK AND FOR EVERY ACCOUNT, named alike
#: and read left to right: what it opened at, what went in, what it earned, what it closed at,
#: and the gain and return those make.
#:
#: THE ACCOUNT IS A COLUMN, as on every other page that lists accounts, and leads both tables
#: (13 Oct 2026, the first formatting pass): it was a title row per group, bold on a band, six
#: rows of the table that carried no figure.
#:
#: NO START OR END DATE, as the report has none: the Quarter names the span ("Q4 2026 to date"
#: for the open one), and a "Quarter start" column showed the previous quarter's END.
COLUMNS = ("account", "quarter", "opening_nav", "capital_deployed", "return_income",
           "closing_nav", "gain", "return")

#: WHAT AN ACCOUNT'S QUARTER-END NAV RESTS ON, under the row's detail link: the source the record
#: took it from and whether it is sourced or derived (`Book.quarter_nav_rows()`). A frozen quarter
#: end has one; the open quarter, valued at today's marks, does not.
DETAIL_COLUMNS = ("source", "quality")

#: THE YEAR SO FAR, PER ACCOUNT — `Book.by_account()`. Exposure and net asset value sit side by
#: side and are never divided: for a spread-bet account the first is notional and the second
#: equity.
#:
#: ITS INCOME IS THE RETURN'S, as the quarter table's is: dividends and funding interest, which is
#: what YTD return is built on, so a row rebuilds its own return. The whole year's income, fees
#: and cash interest included, is the Dashboard's YTD income.
#:
#: IN THE QUARTER TABLE'S ORDER (the first formatting pass): what it opened at, what went in,
#: what it earned, where it stands, and the growth and return those make — then what only the
#: year carries: capital employed, market exposure and the account's kind.
YEAR_COLUMNS = ("account", "opening_capital", "capital_deployed", "return_income", "nav",
                "capital_growth", "ytd", "capital_employed", "exposure", "held_as")


def data() -> dict:
    b = engine.book()
    return {
        # THE OPEN QUARTER TOO: the engine's series, as it gives it.
        "firm": [dict(r, account="The book")
                 for r in _shape.rows(b.quarter_returns(include_open=True), COLUMNS)],
        "accounts": _rests_on(b, b.account_quarter_returns(include_open=True)),
        "detail": list(DETAIL_COLUMNS),
        "columns": list(COLUMNS),
        # THE BOOK FIRST, as the quarter table puts it: the engine's all-accounts row
        # (`Book.totals()`, money only) beside the book's total market exposure. Its YTD return
        # is the Dashboard's, and no row of this page carried it.
        "year": [{c: _shape.plain(v) for c, v in
                  {"account": "The book", "held_as": None, "exposure": b.total_exposure(),
                   **b.totals()}.items() if c in YEAR_COLUMNS}]
                + _shape.rows(b.by_account(), YEAR_COLUMNS),
        "year_columns": list(YEAR_COLUMNS),
        "year_opens": b.ytd_opens(),
        "measure": "net asset value",
        # EACH QUARTER'S REPORT THE GATE ALLOWS, oldest first, as the table reads.
        "reports": [q for q in engine.reports()["quarters"][::-1] if q["closed"] and not q["gaps"]],
        "caveats": _caveats(b),
    }


def _rests_on(b, frame) -> list[dict]:
    """Each account's quarter rows, a frozen quarter's carrying its closing NAV's source and
    quality from the record's quarter end, read through the engine."""
    frozen = {d: b.quarter_nav_rows(d).set_index("account") for d in b.quarter_nav_total().index}
    rows = _shape.rows(frame, COLUMNS)
    for row, end in zip(rows, frame["quarter_end"].astype(str).str[:10]):
        if end in frozen and row["account"] in frozen[end].index:
            row.update({c: frozen[end].loc[row["account"], c] for c in DETAIL_COLUMNS})
    return rows


def _caveats(b) -> list[dict]:
    """What a reader must know before quoting one of these numbers. Stated, not implied."""
    out = [{
        # ONE STATEMENT OF THE RETURN: the renderer typed a second one beside this until 13 Oct
        # 2026, saying half of it again.
        "scope": "The return",
        "detail": ("Modified Dietz, day-weighted, on net asset value against capital deployed "
                   "into positions, each flow weighted by the days after it: "
                   "purchases less sale proceeds for shares, funds for spread bets. A deposit or "
                   "withdrawal moves nothing, and the numerator takes dividends and funding "
                   "interest only. Money-weighted, so no index sits beside it. Never divide one "
                   "of these gains by market exposure, which includes spread-bet notional."),
    }]

    # THE ENGINE'S FLAG, so an account wears this caveat only while a quarter of its actually
    # opens on a zero balance, and stops on its own when one opens on a real balance.
    # Column access by name, never itertuples: `return` is a Python keyword and would be renamed.
    frame = b.account_quarter_returns(include_open=True)
    for account in sorted({str(a) for a in frame.loc[frame["opened_in_period"], "account"]}):
        out.append({"scope": f"{account}, its first quarter", "detail": b.OPENED_IN_PERIOD})
    return out


