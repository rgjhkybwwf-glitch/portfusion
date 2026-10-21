"""ACCOUNTS — who each account is, and the money that crossed its boundary.

The register, each account's cash, external capital, and the year's income and costs, each the
engine's frame. The reconciliation has a page of its own (Reconcile).
NOTHING IS SUMMED HERE. The year's income by account is `Book.income_summary()`'s, the report's
table for a quarter, and its firm row is the Dashboard's YTD income; a total worked out of these
rows would be a second answer to both.

THE MAC ONLY, the owner's decision (13 Oct 2026): the register names holders and account
numbers, which the hosted desk's readers are shown as codes (`desk/naming.py`), and a register of
codes tells its reader nothing. It is not in `remote.REMOTE_PANELS`.
"""
from __future__ import annotations

from portfusion.desk import engine
from portfusion.desk.panels import _shape

NAME = "accounts"
TITLE = "Accounts"
ORDER = 65

#: ONE ROW PER ACCOUNT: who it is, then its cash. The register and the cash were two tables of the
#: same accounts in the same order (13 Oct 2026).
#:
#: THE FEED KEY names the block of credentials.json a feed reads the account with, blank for an
#: account no feed reads. It was recorded and shown on no page (13 Oct 2026).
#:
#: CASH IS RECORDED, NEVER IN NET ASSET VALUE: a broker's total is positions plus cash, so the
#: reconciliation needs it. ONE FIGURE PER ACCOUNT, its newest on file from either kind of reading
#: (`Book.newest_cash()`), and what it was read from in Reconcile's words. It was two figures with
#: two dates (13 Oct 2026), which could disagree, and the one headed "now" could be the
#: older.
REGISTER_COLUMNS = ("code", "account", "holder", "broker", "number", "feed_key", "cash",
                    "cash_read")
#: Newest first, as the engine returns it: a log is scanned for what happened lately.
MOVEMENT_COLUMNS = ("date", "account", "amount", "source", "detail")
#: THE YEAR'S INCOME AND COSTS BY ACCOUNT, as the report has a quarter's: one row per account and
#: one column per category, the categories `Book.income_summary()` gives, which head themselves as
#: they do on the report (an income category is data), then the total. THE BOOK LEADS, as on
#: Performance (13 Oct 2026): the engine's closing "Total" row, named as that page names it.
SUMMARY_COLUMNS = ("account", "total")
#: AN ACCOUNT'S OWN ROWS, under its summary line's detail link: every account's rows in one table
#: filled the page (13 Oct 2026). The summary line names the account, so a row does not.
#:
#: In the engine's order: newest first within each account.
#:
#: NO RUNNING TOTAL AND NO QUARTER (13 Oct 2026): the account's total is the year's own figure,
#: and the date says the quarter, which this column spelled "2026Q3" where every other page
#: says "Q3 2026".
#:
#: A FOREIGN ROW READS AS ITS CONVERSION, left to right (13 Oct 2026): the currency it was
#: paid in, the amount in it, the day of the rate that converted it, then the sterling the book
#: adds up. Blank on a sterling row, and left out of an account none of whose rows was converted:
#: three empty columns wrapped a share account's rows onto two lines (13 Oct 2026).
INCOME_COLUMNS = ("date", "category", "detail", "currency", "local_amount", "rate_date", "amount",
                  "source", "note")
CONVERSION = ("currency", "local_amount", "rate_date")


def data() -> dict:
    b = engine.book()
    year = b.ytd_year()
    return {
        "register": _register(b),
        "movements": _shape.rows(b.capital_movements(), MOVEMENT_COLUMNS, dates=("date",)),
        **_income(b, year),
        "year": year,
    }


def _register(b) -> list[dict]:
    """The register as filed, each account's row carrying its newest cash and what it was read
    from."""
    cash = {r["account"]: {"cash": _shape.money(r["cash"]),
                           "cash_read": _shape.reading(r["document"], r["as_of"]) if r["as_of"]
                           else None}
            for r in _shape.rows(b.newest_cash(), ("account", "cash", "as_of", "document"))}
    return [dict(r, **cash.get(r["account"], {}))
            for r in _shape.rows(b.account_register(), REGISTER_COLUMNS)]


def _income(b, year: int) -> dict:
    """The year's summary by account, the book first, each account's line carrying its own rows."""
    frame = b.income_summary(year=year)
    categories = [c for c in frame.columns if c not in SUMMARY_COLUMNS]
    rows = b.income_rows(year)
    lines = []
    for line in _shape.rows(frame, ("account", *categories, "total")):
        mine = _shape.rows(rows[rows["account"] == line["account"]], INCOME_COLUMNS,
                           dates=("date", "rate_date"))
        converted = any(r["currency"] for r in mine)
        lines.append(dict(line, rows=mine, columns=[c for c in INCOME_COLUMNS
                                                    if converted or c not in CONVERSION]))
    firm = [dict(line, account="The book") for line in lines if line["account"] == "Total"]
    return {
        "income": firm + [line for line in lines if line["account"] != "Total"],
        "categories": categories,
        "columns": {"register": list(REGISTER_COLUMNS), "movements": list(MOVEMENT_COLUMNS),
                    "summary": ["account", *categories, "total"]},
    }
