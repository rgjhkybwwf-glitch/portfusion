"""THE COMPANY LIFE — a company's shares and spread bets, first purchase to final sale.

The first half holds any book: the lives add up to the book's own realised and unrealised gain,
every sale and buy sits in exactly one life, and a company's lives follow one another. The second
half builds lives on a copy of the store, from a company invented for each test, so each shape —
the owner's own example among them — is held whatever book is loaded.
"""
from __future__ import annotations

import csv

import pandas as pd
import pytest

from harness import an_account, free_id, needs
from portfusion.engine import BASELINE, Book


def ties(mine, theirs, what, tol=0.005):
    assert mine is not None and mine == mine, f"{what}: blank"
    assert abs(mine - theirs) < tol, f"{what}: {mine:,.6f} vs {theirs:,.6f}"


# ---- ANY BOOK ------------------------------------------------------------------------------

@needs("buys")
def test_the_lives_add_up_to_the_books_gain(book):
    """Reached by company rather than by line, realised gain is realised() and unrealised gain is
    unrealised(): a life that dropped or doubled a sale, or a line still held, parts them."""
    totals = book.company_life_totals()
    ties(totals["realised"], book.realised(), "lives' realised vs the book's")
    ties(totals["unrealised"], book.unrealised(), "open lives' unrealised vs the book's")
    ties(totals["life_gain"], totals["realised"] + totals["unrealised"] + totals["dividends"]
         + totals["funding_interest"], "total vs its parts")


@needs("buys")
def test_every_dividend_and_funding_charge_is_one_lifes_or_named(book):
    """A dividend or a funding charge is taken by exactly one life, or is left over by name: the
    lives' dividends and funding and what no life took add up to the income table's own."""
    taken, loose = book._life_income()
    for category, key in (("Dividend", "dividends"), ("Funding interest", "funding_interest")):
        rows = sum(r.amount for r in book.D.ci_rows if r.category == category)
        lives = sum(a for v in taken.values() for _, a in v[key])
        left = sum(r.amount for r in loose if r.category == category)
        ties(lives + left, rows, f"{category}: lives plus left over vs the table")


@needs("buys")
def test_every_deal_sits_in_exactly_one_life(book):
    """Each buy and each sale belongs to one life, and every company held now to one open life."""
    lives = book._lives()
    deals = [r["id"] for lv in lives for r in lv["buys"] + lv["sales"]]
    L = book.ledger
    assert sorted(deals) == sorted(L.loc[L["direction"].isin(("Buy", "Sell")), "id"])
    held = set(book.holdings(by="ticker")["company"])
    open_ = [lv["company"] for lv in lives if lv["closed"] is None]
    assert sorted(open_) == sorted(held), "a company held now has no open life, or two"


@needs("buys")
def test_a_companys_lives_follow_one_another(book):
    """A life ends before the company's next one opens, and a closed life holds nothing at its
    close: its sales took everything its buys brought in."""
    by_company: dict[str, list] = {}
    for lv in book._lives():
        by_company.setdefault(lv["company"], []).append(lv)
    for company, lives in by_company.items():
        for one, two in zip(lives, lives[1:]):
            assert one["closed"] is not None and one["closed"] < two["opened"], company
    for lv in book._lives():
        if lv["closed"] is None:
            continue
        shares = sum((r["qty"] if r["direction"] == "Buy" else -r["qty"])
                     for r in lv["buys"] + lv["sales"] if r["held_as"] == "shares")
        assert shares == 0, f"{lv['company']}: {shares} shares left at the close"


@needs("buys")
def test_a_lifes_figures_are_shown_only_where_they_mean_something(book):
    """A life cost per share only while something is held; unrealised gain only while the life is
    open; the record's start marks a life opened before it."""
    for r in book.company_lives().to_dict("records"):
        if pd.isna(r["qty"]) or not r["qty"]:
            assert pd.isna(r["life_cost_per_share"]), r["life"]
        if r["state"] == "closed":
            assert pd.isna(r["unrealised"]), r["life"]
        assert r["pre_baseline"] == (r["opened"] < book.baseline), r["life"]


# ---- BUILT ON A COPY -----------------------------------------------------------------------

def _on(days: int) -> str:
    """`days` after the scenarios' start: inside the loaded book's record, and past."""
    start = max(BASELINE, pd.Timestamp.today().normalize() - pd.Timedelta(days=150))
    return (start + pd.Timedelta(days=days)).date().isoformat()


def _write(store, table: str, *rows: dict) -> None:
    """Append `rows` to the copy's `table`, each in the table's own column order."""
    from portfusion.record import schema
    header = schema.TABLES[table].header
    with (store / f"{table}.csv").open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        for r in rows:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in header])


class _Company:
    """An invented company on the copy: a share line and a spread-bet line on its London listing,
    priced at `price` today. Deals are added in date order and the record reloaded once."""
    SOURCE = "Not on file: invented for a test"

    def __init__(self, store, root: str, price: float):
        self.store, self.root = store, root
        self.name, self.share, self.bet = f"{root.title()} Mills plc", f"{root}.L", f"{root} SB"
        self.trades, self.exits = 0, 0
        _write(store, "companies", {"company": self.name, "sector": "Industrials", "region": "UK"})
        _write(store, "securities",
               {"ticker": self.share, "company": self.name, "held_as": "shares", "currency": "GBP",
                "symbol": f"XLON:{root}", "quote_unit": "GBX"},
               {"ticker": self.bet, "company": self.name, "held_as": "spread bet", "currency": "GBP",
                "symbol": f"XLON:{root}", "points_per_unit": 100})
        _write(store, "current-prices", {"mark_key": self.share, "price": price, "currency": "GBP",
                                         "as_of": _on(58), "source": self.SOURCE,
                                         "struck": "close"})

    def buy(self, day, qty, price, account=None) -> str:
        tid = free_id("buys", self.trades)
        self.trades += 1
        _write(self.store, "buys", {
            "trade_id": tid, "date": day, "source": self.SOURCE, "account": account or an_account("shares"),
            "ticker": self.share, "cur": "GBP", "qty": qty, "cost": round(qty * price, 2),
            "traded_price": price})
        return tid

    def sell(self, day, qty, price, parcel, account=None) -> str:
        eid = free_id("sales", self.exits)
        self.exits += 1
        _write(self.store, "sales", {
            "sale_id": eid, "date": day, "account": account or an_account("shares"),
            "ticker": self.share, "qty": qty, "traded_price": price, "cur": "GBP",
            "proceeds": round(qty * price, 2), "source": self.SOURCE, "realisation_id": parcel})
        return eid

    def bet_open(self, day, stake, level, contract, mark=None) -> str:
        tid = free_id("buys", self.trades)
        self.trades += 1
        _write(self.store, "contracts", {"contract": contract, "epic": "" if mark is None else
                                         f"IX.D.{self.root}.TEST.IP", "funding": "dated",
                                         "ticker": self.bet})
        if mark is not None:
            _write(self.store, "current-prices", {
                "mark_key": contract, "price": mark, "currency": "GBP", "as_of": _on(58),
                "source": self.SOURCE, "struck": "live", "at": f"{_on(58)}T15:00Z"})
        _write(self.store, "buys", {
            "trade_id": tid, "date": day, "source": self.SOURCE, "account": an_account("spread bet"),
            "ticker": self.bet, "cur": "GBP", "stake": stake, "level_points": level, "contract": contract})
        return tid

    def bet_close(self, day, stake, level, leg, parcel) -> str:
        eid = free_id("sales", self.exits)
        self.exits += 1
        _write(self.store, "sales", {
            "sale_id": eid, "date": day, "account": an_account("spread bet"), "ticker": self.bet,
            "stake": stake, "traded_price": level, "cur": "GBP", "proceeds": round(stake * level, 2),
            "source": self.SOURCE, "realisation_id": parcel, "closes": leg})
        return eid


def _reloaded() -> Book:
    from portfusion.record import rules
    rules.reload_store()
    return Book()


def _lives(book, company):
    return book.company_lives(company=company).sort_values("opened").to_dict("records")


@needs("accounts")
def test_the_owners_example_reads_both_ways(store_copy):
    """THE OWNER'S EXAMPLE, exactly. 100 shares at 100p; in a dip, a £1-per-point bet at 80p, so
    while both are held the company is 200 share-equivalents at 90p. The bet closes at 110p for
    £30. By holding the shares still cost 100p and stand £10 up; by company life £30 is realised,
    the life is £40 up to date, and the life cost per share is 70p."""
    if an_account("spread bet") is None:
        pytest.skip("the book has no spread-bet account")
    co = _Company(store_copy, "HRWG", price=1.10)
    co.buy(_on(0), 100, 1.00)
    leg = co.bet_open(_on(7), 1, 80.0, "HRWG-DEC26", mark=95.0)
    book = _reloaded()
    row = book.holdings(by="issuer").set_index("company").loc[co.name]
    assert row["qty"] == 200 and abs(row["entry_price"] - 0.90) < 1e-9, row[["qty", "entry_price"]]
    [life] = _lives(book, co.name)
    assert life["qty"] == 200, "the open bet counts as share-equivalents"
    ties(life["life_cost_per_share"], 0.90, "with nothing taken yet, the life cost is the entry")

    co.bet_close(_on(29), 1, 110.0, leg, "R-HRWGSB")
    # The contract is closed: nothing reads its level again.
    (store_copy / "current-prices.csv").write_text(
        "".join(line for line in (store_copy / "current-prices.csv").read_text().splitlines(True)
                if not line.startswith("HRWG-DEC26,")))
    book = _reloaded()
    share = book.holdings(by="ticker").set_index("ticker").loc[co.share]
    ties(share["entry_price"], 1.00, "by holding, the shares' entry")
    ties(share["unrealised"], 10.0, "by holding, the shares' gain")
    [life] = _lives(book, co.name)
    assert life["held_as"] == "mixed" and life["state"] == "part closed", life
    ties(life["realised"], 30.0, "realised")
    ties(life["unrealised"], 10.0, "unrealised gain")
    ties(life["life_gain"], 40.0, "the life to date")
    ties(life["life_cost_per_share"], 0.70, "life cost per share")
    ties(life["life_pct"], 40 / 180, "£40 over £100 of shares and an £80 bet at entry")


@needs("accounts")
def test_a_full_exit_then_a_new_purchase_is_a_second_life(store_copy):
    co = _Company(store_copy, "PNMR", price=1.50)
    co.buy(_on(0), 100, 1.00)
    co.sell(_on(17), 100, 1.20, "R-PNMR")
    co.buy(_on(30), 50, 1.40)
    first, second = _lives(_reloaded(), co.name)
    assert first["state"] == "closed" and first["closed"] == pd.Timestamp(_on(17))
    ties(first["realised"], 20.0, "the first life's realised")
    ties(first["life_pct"], 0.20, "the first life's percentage")
    assert second["state"] == "open" and second["opened"] == pd.Timestamp(_on(30))
    ties(second["unrealised"], 5.0, "the second life's unrealised gain")
    ties(second["life_cost_per_share"], 1.40, "a life with no sale: its cost per share")


@needs("accounts")
def test_a_dividend_is_its_lifes_even_when_paid_after_the_final_sale(store_copy):
    """A dividend counts in the life open on its date, or, paid after the line was sold out, in
    the life it was earned in; it lowers the life cost of what is still held."""
    co = _Company(store_copy, "DVDN", price=1.00)
    co.buy(_on(0), 100, 1.00)
    co.sell(_on(17), 100, 1.00, "R-DVDN")
    co.buy(_on(30), 100, 1.00)
    _write(store_copy, "income",
           {"date": _on(22), "account": an_account("shares"), "category": "Dividend",
            "detail": "DVDN final dividend", "amount": 4.0, "source": co.SOURCE,
            "ticker": co.share},
           {"date": _on(48), "account": an_account("shares"), "category": "Dividend",
            "detail": "DVDN interim dividend", "amount": 5.0, "source": co.SOURCE,
            "ticker": co.share})
    first, second = _lives(_reloaded(), co.name)
    ties(first["dividends"], 4.0, "paid after the first life's final sale")
    ties(first["life_gain"], 4.0, "a life sold at cost, plus its dividend")
    ties(second["dividends"], 5.0, "paid while the second life is open")
    ties(second["life_cost_per_share"], 0.95, "£100 less a £5 dividend, over 100")


@needs("accounts")
def test_a_sale_and_a_purchase_on_one_day_are_one_life(store_copy):
    """A day's buys come before its sales, as a share pool walks them, so a line sold out and
    bought back the same day is never empty."""
    co = _Company(store_copy, "SMDY", price=1.00)
    co.buy(_on(0), 100, 1.00)
    co.buy(_on(17), 100, 1.10)
    co.sell(_on(17), 100, 1.10, "R-SMDY")
    [life] = _lives(_reloaded(), co.name)
    assert life["state"] == "part closed" and life["shares_held"] == 100


@needs("accounts")
def test_one_account_trimming_while_another_holds_keeps_one_life(store_copy):
    accounts = [a for a in Book().account_order() if Book().D.ACCOUNT_KIND[a] == "shares"]
    if len(accounts) < 2:
        pytest.skip("the book has fewer than two share accounts")
    co = _Company(store_copy, "TWAC", price=1.00)
    co.buy(_on(0), 100, 1.00, account=accounts[0])
    co.buy(_on(1), 100, 2.00, account=accounts[1])
    co.sell(_on(17), 50, 1.30, "R-TWAC", account=accounts[0])
    [life] = _lives(_reloaded(), co.name)
    assert life["state"] == "part closed" and life["shares_held"] == 150
    assert life["accounts"] == f"{accounts[0]} · {accounts[1]}"
    # EACH POOL AT ITS OWN AVERAGE: £50 + £200 held, less £15 realised, over 150.
    ties(life["life_cost_per_share"], 235 / 150, "the life's cost per share")


@needs("accounts")
def test_a_life_of_bets_alone_has_no_cost_per_share(store_copy):
    if an_account("spread bet") is None:
        pytest.skip("the book has no spread-bet account")
    co = _Company(store_copy, "BTSO", price=1.00)
    leg = co.bet_open(_on(7), 2, 90.0, "BTSO-DEC26")
    co.bet_close(_on(29), 2, 100.0, leg, "R-BTSOSB")
    [life] = _lives(_reloaded(), co.name)
    assert life["held_as"] == "spread bet" and life["state"] == "closed"
    ties(life["realised"], 20.0, "two pounds a point over ten points")
    assert pd.isna(life["life_cost_per_share"]), "nothing is held"
    ties(life["life_pct"], 20 / 180, "£20 over a £180 bet at entry")
