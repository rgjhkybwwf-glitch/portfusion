"""
THE DESK TIES — every page shows exactly what the engine computed, in the engine's order.

The desk's pages are tied here field by field, not cell by cell, so a tie cannot drift from a
layout: a page that stopped showing the engine's figure, showed it on the
wrong row, or re-sorted what the engine ordered, fails. Nothing here asks whether the engine is
right — tests/test_engine_invariants.py does.
"""
import pandas as pd
import pytest

from portfusion.desk import engine
from portfusion.desk.panels import accounts, holdings, performance, reconcile, round_trips, trades
from harness import needs

PENNY = 0.01
RATE = 1e-6


@pytest.fixture(scope="module")
def b():
    return engine.book()


def _same(mine, theirs, tol=PENNY):
    if mine is None or theirs is None or theirs != theirs:
        return mine is None and (theirs is None or theirs != theirs)
    return abs(mine - theirs) < tol


@pytest.mark.parametrize("by", holdings.GROUPINGS)
def test_holdings_rows_are_the_engines(b, by):
    rows, frame = holdings.query(by=by)["rows"], b.holdings(by=by).to_dict("records")
    assert len(rows) == len(frame)
    for r, f in zip(rows, frame):
        assert r["company"] == f["company"]
        for c in ("cost", "value", "gain", "entry_price"):
            assert _same(r[c], f.get(c)), (by, f["company"], c, r[c], f.get(c))
        assert _same(r["weight"], f.get("weight"), RATE)


def test_the_allocation_is_the_engines(b):
    for dim, shown in holdings.data()["allocation"].items():
        engine_dim = b.allocation(by=dim).set_index(dim)["value"]
        assert {a["key"] for a in shown} == set(engine_dim.index), dim
        for a in shown:
            assert _same(a["value"], engine_dim[a["key"]]), (dim, a["key"])


def test_the_quarter_series_is_the_engines(b):
    d = performance.data()
    for shown, frame in ((d["firm"], b.quarter_returns(include_open=True)),
                         (d["accounts"], b.account_quarter_returns(include_open=True))):
        frame = frame.to_dict("records")
        assert [r["quarter"] for r in shown] == [f["quarter"] for f in frame]
        for r, f in zip(shown, frame):
            for c in ("opening_nav", "capital_deployed", "closing_nav", "gain"):
                assert _same(r[c], f[c]), (r.get("account", "firm"), r["quarter"], c)
            assert _same(r["return"], f["return"], RATE)


def test_the_year_so_far_is_the_engines(b):
    year, frame = performance.data()["year"], b.by_account().to_dict("records")
    # THE BOOK LEADS: the engine's all-accounts row, and the book's exposure.
    firm, shown = year[0], year[1:]
    assert firm["account"] == "The book"
    for c, v in b.totals().items():
        if c in performance.YEAR_COLUMNS:
            assert _same(firm[c], v, RATE) if c == "ytd" else _same(firm[c], v), ("The book", c)
    assert _same(firm["exposure"], b.total_exposure()), ("The book", "exposure")
    assert [r["account"] for r in shown] == [f["account"] for f in frame] == b.account_order()
    for r, f in zip(shown, frame):
        for c in ("exposure", "nav", "opening_capital", "capital_deployed", "return_income"):
            assert _same(r[c], f[c]), (f["account"], c)
        assert _same(r["ytd"], f["ytd"], RATE)


def test_round_trips_are_the_engines_newest_first(b):
    rows, frame = round_trips.data()["rows"], b.round_trips().to_dict("records")
    assert [r["realisation_id"] for r in rows] == [f["realisation_id"] for f in frame], \
        "the page re-sorted what the engine ordered"
    for r, f in zip(rows, frame):
        assert _same(r["gain"], f["gain"]), f["realisation_id"]
    closed = [r["closed"] for r in rows]
    assert closed == sorted(closed, reverse=True), "Round Trips is not newest first"


def test_round_trips_for_a_company_are_the_engines_and_list_its_tickers(b):
    """S8 (14 Oct 2026): narrowed to a company, the rows and the four figures are the engine's,
    and the Ticker box offers that company's codes alone."""
    for company in round_trips.data()["companies"]:
        d = round_trips.query(company=company)
        frame = b.round_trips(company=company)
        assert [r["realisation_id"] for r in d["rows"]] == list(frame["realisation_id"]), company
        assert _same(d["totals"]["gain"], b.round_trip_totals(company=company)["gain"]), company
        assert d["tickers"] == sorted(set(frame["ticker"])) and d["narrowed"], company


def test_the_trades_ticker_box_is_the_chosen_companys(b):
    """S8 (14 Oct 2026): each company's codes as the ledger holds them, so the Ticker box beside
    the Company box cannot name a line the company rules out."""
    d = trades.data()
    assert set(d["company_tickers"]) == set(d["companies"])
    for company, codes in d["company_tickers"].items():
        assert codes == sorted(set(trades.tickers_for_company(company)) & set(d["tickers"])), company


def test_trades_are_the_engines(b):
    rows, frame = trades.data()["rows"], b.activity().to_dict("records")
    assert [r["trade_id"] for r in rows] == [f["trade_id"] for f in frame]
    for r, f in zip(rows, frame):
        assert _same(r["value"], f["value"]), f["trade_id"]


def test_the_accounts_page_keeps_the_engines_order(b):
    """The register in the record's account order; external capital newest first, as a log is
    read; income in account order, then each account's rows newest first too (the owner, 14 Oct
    2026: they ran oldest first, as a broker's statement lists them)."""
    d = accounts.data()
    assert [r["account"] for r in d["register"]] == b.account_order()
    moves = [r["date"] for r in d["movements"]]
    assert moves == sorted(moves, reverse=True)
    assert [r["account"] for r in d["income"][1:]] == b.account_order(), \
        "the year's income is not one line per account, in the record's order, after the book"
    for line in d["income"]:
        dates = [r["date"] for r in line["rows"]]
        assert dates == sorted(dates, reverse=True), f"{line['account']}'s income is not newest first"


@needs("accounts")
def test_the_register_is_the_records(b):
    """Every field the register records reaches the page, as filed (the feed key included); the
    kind is Performance's."""
    reg = b.account_register().to_dict("records")
    rows = accounts.data()["register"]
    shown = set(accounts.REGISTER_COLUMNS)
    assert set(reg[0]) - {"holder_names", "kind"} <= shown, set(reg[0]) - shown
    for r, f in zip(rows, reg):
        assert all(r[c] == (None if f[c] != f[c] else f[c]) for c in shown & set(f)), f["account"]


def test_each_accounts_cash_is_the_engines(b):
    """The register's cash is `Book.newest_cash()`'s, row for row, named by what it was read from
    and on which day."""
    held = b.newest_cash().set_index("account")
    for r in accounts.data()["register"]:
        e = held.loc[r["account"]]
        assert _same(r["cash"], e["cash"]), r["account"]
        assert r["cash_read"] == (None if e["as_of"] is None
                                  else f"{e['document']}, {_day(e['as_of'])}"), r["account"]


def _day(iso) -> str:
    import datetime as _dt
    return f"{_dt.date.fromisoformat(str(iso)[:10]):%-d %b %Y}"


def test_the_years_income_is_the_engines_summary(b):
    """The year's income by account is `Book.income_summary()`'s, figure for figure; the book's
    line is the Dashboard's YTD income; and the rows under each account's line are that
    account's rows of the year, every one of them, adding up to its total."""
    d = accounts.data()
    year = d["year"]
    frame = b.income_summary(year=year).set_index("account")
    firm, *lines = d["income"]
    assert firm["account"] == "The book" and not firm["rows"]
    assert _same(firm["total"], b.totals()["income"]), (firm["total"], b.totals()["income"])
    for line in [dict(firm, account="Total"), *lines]:
        for c in [*d["categories"], "total"]:
            assert _same(line[c], frame.loc[line["account"], c]), (line["account"], c)
    rows = b.income_rows(year)
    for line in lines:
        mine = rows[rows["account"] == line["account"]]
        assert len(line["rows"]) == len(mine), line["account"]
        assert _same(sum(r["amount"] for r in line["rows"]), line["total"]), line["account"]


def test_a_foreign_income_row_shows_its_conversion(b):
    """A row paid in another currency carries that currency, its amount in it and the day of
    its rate, the same day the audit's conversions check reads (`Book.conversions()`); a
    sterling row carries none of them."""
    d = accounts.data()
    rows = [r for line in d["income"] for r in line["rows"]]
    conv = b.conversions()
    year = conv[conv["date"].astype(str).str[:4] == str(d["year"])]
    foreign = [r for r in rows if r["currency"]]
    assert len(foreign) == len(year), (len(foreign), len(year))
    for r, c in zip(sorted(foreign, key=lambda r: (r["date"], r["amount"])),
                    year.sort_values(["date", "amount"]).to_dict("records")):
        # A broker's rate is the row's own conversion and has no close's date (`conversions()`).
        want = None if pd.isna(c["rate_date"]) else str(c["rate_date"])[:10]
        assert (r["currency"], r["local_amount"], r["rate_date"]) == \
            (c["currency"], c["local_amount"], want), (r, c)
    assert not [r for r in rows if not r["currency"]
                and (r["local_amount"] is not None or r["rate_date"] is not None)]
    # AN ACCOUNT NONE OF WHOSE ROWS WAS CONVERTED LEAVES THE THREE COLUMNS OUT.
    for line in d["income"]:
        has = any(r["currency"] for r in line["rows"])
        assert has == ("currency" in line.get("columns", [])) or not line["rows"], line["account"]


def test_reconcile_shows_the_engines_book_and_broker(b):
    rows, frame = reconcile.data()["rows"], b.reconciliation().to_dict("records")
    assert [r["account"] for r in rows] == [f["account"] for f in frame]
    for r, f in zip(rows, frame):
        assert _same(r["book"], f["book"]) and _same(r["broker"], f["statement"]), f["account"]
