"""
THE TIES — the engine's figures against one another and against the record.

The desk's pages are tied to the engine in tests/desk/test_ties.py. This file holds the engine's
own arithmetic seen from more than one side — net asset value against exposure, the issuer
roll-up against the book, a quarter's label against its date, the reasoning against its one
store. `test_engine_invariants.py` asks whether the engine agrees with itself; `docs/testing.md`
sets out the difference.

TOLERANCE. Money ties to the penny; a return, being a rate, to a millionth of a point.
"""
import math
import pathlib

import pandas as pd
import pytest

from portfusion.record import rules as D
from portfusion.engine import BASELINE, BASELINE_ASOF, Book
from harness import an_account, needs
from quarter_support import book_in_the_next_year

REASONING = D.REASONING

PENNY = 0.01
RATE = 1e-6          # a return is a rate, not money; ties to a millionth of a point


@pytest.fixture(scope="module")
def book():
    return Book()


def ties(mine, theirs, what, tol=PENNY):
    assert theirs is not None, f"{what}: not found"
    assert isinstance(theirs, (int, float)), f"{what}: {theirs!r} is not a number"
    assert abs(mine - theirs) < tol, \
        f"{what}: {mine:,.6f} vs {theirs:,.6f} (out by {mine - theirs:,.6f})"


# =====================================================================================
# ACCOUNT LEVEL  —  every metric, per account, rolling up to a parent total
# =====================================================================================

def test_a_spread_bet_account_contributes_equity_to_nav_and_notional_to_exposure(book):
    """The rule, stated as an inequality rather than as prose.

    If these two ever come out equal for a spread-bet account, something has started
    treating notional as money — which is the most expensive mistake available against
    this record.
    """
    by = book.by_account().set_index("account")
    for account in D.ACCOUNT_ORDER:
        row = by.loc[account]
        if row["held_as"] == "spread bet":
            assert row["exposure"] > row["nav"], \
                f"{account}: exposure {row['exposure']:,.2f} is not above equity {row['nav']:,.2f}"
        else:
            assert abs(row["exposure"] - row["nav"]) < PENNY, \
                f"{account}: a share account's exposure and NAV are the same figure"


# =====================================================================================
# THE QUARTER-END SERIES
# =====================================================================================

@needs("trades")
def test_quarter_end_navs_are_per_account_and_roll_up(book):
    """Per account AND in total, from one set of numbers.

    The share accounts' contributions are also on Performance's SNAPSHOT COMPONENTS
    block, which is tied separately by tests/test_quarter_nav.py; what this asserts is
    that the engine's roll-up equals the sum of its own parts, so the total can never
    be a figure somebody typed.
    """
    q = book.quarter_nav()
    assert set(q["as_of"]) == {BASELINE_ASOF, *D.QSNAP_FROZEN}, (
        "quarter-nav and quarter-snapshots must hold the same quarter ends, from the baseline on")
    for date, rows in q.groupby("as_of"):
        assert set(rows["account"]) == set(D.ACCOUNT_ORDER), f"{date}: not every account contributes"
        # PER BASIS. The unfiltered sum is what put the spread-bet notional into a
        # quarter's NAV the moment the notional rows landed, and this line is where it surfaced.
        # Each series rolls up against its own total, so the two can never be added together
        # by accident again.
        nav = rows[rows["contribution"].isin(book.NAV_BASES)]
        exp = rows[rows["contribution"].isin(book.EXPOSURE_BASES)]
        ties(nav["amount"].sum(), book.quarter_nav_total()[date], f"NAV roll-up at {date}")
        ties(exp["amount"].sum(), book.quarter_exposure_total()[date],
             f"exposure roll-up at {date}")
        assert set(nav["account"]) == set(D.ACCOUNT_ORDER), (
            f"{date}: an account contributes nothing to NAV, which understates it silently")


@needs("trades")
def test_exposure_and_nav_are_the_same_at_every_date_but_one(book):
    """The two quarter series differ ONLY where a spread bet was open, and by exactly its
    notional less its equity. Anywhere else a difference appears, a securities account has
    picked up a second basis and one of the two series is wrong."""
    nav, exp = book.quarter_nav_total(), book.quarter_exposure_total()
    assert list(nav.index) == list(exp.index)
    for date in nav.index:
        rows = book.quarter_nav().query("as_of == @date")
        notional = rows[rows["contribution"] == "notional"]["amount"].sum()
        equity = rows[rows["contribution"] == "account equity"]["amount"].sum()
        ties(exp[date] - nav[date], notional - equity, f"the gap at {date}")
    levered = [d for d in nav.index if book.quarter_nav().query(
        "as_of == @d and contribution == 'notional'")["amount"].sum() > 0]
    assert levered, "no quarter end carries a notional — the leverage premise is gone"
    assert any(exp[d] > nav[d] for d in levered), "exposure exceeds money once leverage is on"


@needs("trades")
def test_the_baseline_nav_is_the_opening_capital_the_return_measures_from(book):
    """One number, reached two ways. The quarter series' baseline total and the
    account block's opening capital are the same money and must agree exactly."""
    ties(book.quarter_nav_total()[BASELINE_ASOF], book.totals()["opening_capital"],
         "baseline NAV vs opening capital")


# =====================================================================================
# INCOME
# =====================================================================================

# =====================================================================================
# ROUND TRIPS
# =====================================================================================

def test_a_company_narrows_round_trips_to_every_code_it_is_held_under(book):
    """S8 (14 Oct 2026): Round Trips narrows by company, as Trades does, so a share and its spread
    bet are read in one choice. The engine selects, so the page's totals still come from here: a
    company's are its codes' together."""
    every = book.round_trips()
    for company, rows in every.groupby("company"):
        got = book.round_trips(company=company)
        assert sorted(got["realisation_id"]) == sorted(rows["realisation_id"]), company
        whole = book.round_trip_totals(company=company)
        parts = [book.round_trip_totals(ticker=t) for t in set(rows["ticker"])]
        assert whole["realisations"] == sum(p["realisations"] for p in parts), company
        assert abs(whole["gain"] - sum(p["gain"] for p in parts)) <= 0.005 * len(parts), company
    assert book.round_trips(company="no such company").empty


def test_round_trip_totals_reach_the_realised_figure_twice(book):
    """Summed per realisation, and summed over the raw exits. If the two disagree the
    apportionment of pooled and leg-exact cost is wrong."""
    t = book.round_trip_totals()
    ties(t["gain"], book.realised(), "round-trip gain vs realised")
    ties(t["proceeds"] - t["cost"], t["gain"], "proceeds less cost")
    assert t["realisations"] == len(set(D.REALISATION_BY_EXIT.values()))
    assert t["sells"] == len(D.exits)


def test_round_trips_reproduce_the_closed_table(book):
    """THE ENTRY DATE ON EVERY ROW, derived rather than read.

    A typed date label asserted against the ledger drifted three times; this derives the same
    fact from the events — a share's holding opening (`share_pools()`), a spread bet's earliest
    named leg — and compares it with the `closed` record, which is where the pre-2026 entry dates
    live. Quantity and exit date are not kept there to compare: `round_trips()` derives them, and
    the copy was overwritten by every sale that joined its parcel.

    A position opened before the 2026 baseline and closed during 2026 is a complete round trip
    and must read as one — entry date, price paid, exit, holding period. Most of the rows are
    exactly that.
    """
    rt = book.round_trips().set_index("realisation_id")
    for c in D.closed:
        row = rt.loc[c.realisation]
        assert row["ticker"] == c.ticker, f"{c.realisation}: the row names {c.ticker}"
        assert row["opened"].date() == c.open_date, f"{c.realisation}: open date"


def test_no_round_trip_is_missing_its_entry_date(book):
    """The entry date and the price paid are what demonstrate the return on a particular
    investment (the owner). a holding of many years; throwing its entry away would throw the point of
    the record away with it."""
    rt = book.round_trips()
    assert rt["opened"].notna().all(), \
        f"undated entries: {rt.loc[rt['opened'].isna(), 'realisation_id'].tolist()}"
    assert (rt["held_days"] > 0).all()


# =====================================================================================
# AS OF
# =====================================================================================

def test_as_of_today_ties_to_portfolio_cost(book):
    """The reconstruction at a date, checked at the one date it can be: today, against the
    engine's cost over both kinds of line."""
    import datetime as _dt
    today = book.as_of(_dt.date.today().isoformat())
    ties(today["cost"].sum(), book.portfolio_cost(), "as_of(today) portfolio cost")


@needs("trades")
def test_as_of_answers_the_opening_day_and_refuses_any_before_it(book):
    """The book does not claim to know what was held in 2025: answering would be a guess wearing a
    number's clothes. Except at the opening day's close, which is what the record opened with —
    every pre-baseline leg — so the opening can be valued at its own closes."""
    import datetime as _dt
    eve = (_dt.date.fromisoformat(BASELINE_ASOF) - _dt.timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="baseline"):
        book.as_of(eve)
    opening = book.as_of(BASELINE_ASOF)
    assert not opening.empty, "the record opened holding nothing"
    if not (book.ledger["date"] == BASELINE).any():
        first = book.as_of(BASELINE.date().isoformat())
        assert opening.equals(first), "nothing dealt on the first day, so it opens as it began"


# =====================================================================================
# THE BOUNDARY  —  which way the dependency runs
# =====================================================================================

def test_the_build_does_not_import_the_broker_feed(build_imports):
    """THE RULE THAT SURVIVED, and the one that did not.

    The build was once forbidden to import `engine.py` too — the engine stood beside the build as
    a SECOND calculator, and a rebuild was not allowed to fail because of anything only the
    engine needed.

    THAT HALF IS RETIRED: the engine produces the data and a renderer renders it. A
    renderer has to read what it renders, so the build importing the engine is the design, not
    a violation; keeping the test would have kept a rule that outlived its reason.

    WHAT STILL HOLDS is the part that was always about risk rather than architecture: the
    build must not import `feeds/ig.py`. That module talks to a broker over the network,
    and a report build that can fail because IG is down is a worse book. pandas is a
    library on disk; a broker is not.
    """
    imports = build_imports
    assert "feeds" not in imports, (
        "the build imports the broker feed — a rebuild must not be able to fail because a "
        "broker is offline")


def test_holdings_by_issuer_merges_each_company_once(book):
    """ONE COMPANY, ONE POSITION. Orlant is ORLA and ORLA SB, and at company level they are one
    holding. If the merge ever stops happening the count rises and the total is unchanged — so
    the count is asserted, derived from the companies held, and not just the money."""
    mine = book.holdings(by="issuer").set_index("company")["value"]
    by_ticker = book.holdings(by="ticker")
    companies = by_ticker["company"].nunique()
    assert len(mine) == companies, (
        f"the engine reports {len(mine)} issuers for {companies} companies — the merge stopped")
    if companies < len(by_ticker):
        assert len(mine) < len(by_ticker), "two instruments of one company did not merge"
    for company, total in by_ticker.groupby("company")["value"].sum().items():
        ties(mine[company], total, f"issuer {company} vs its tickers")
    ties(mine.sum(), book.total_exposure(), "issuer roll-up vs total exposure")


def test_holdings_by_ticker_ties_to_the_book(book):
    """The unmerged view. Same money, one more row, and a real quantity on each."""
    t = book.holdings(by="ticker")
    assert len(t) == t["ticker"].nunique(), "an instrument appears on two rows of the ticker view"
    ties(t["value"].sum(), book.total_exposure(), "ticker holdings vs total exposure")
    ties(t["cost"].sum(), book.portfolio_cost(), "ticker holdings vs portfolio cost")
    assert "qty" in t.columns and (t["qty"] > 0).all()


def test_the_live_position_count_is_the_ledgers_open_lines(book):
    """OPEN POSITIONS, REACHED A SECOND WAY. The live count is `holdings(by="ticker")`'s rows, the
    valued legs grouped; here it is the tickers with a buy leg still open, which the ledger marks
    as each sale consumes one. Of the sixteen registered figures it was the one held by the
    registry's guards alone until step 5."""
    L = book.ledger
    assert book.headline()["Open positions"] == L.loc[L["open_leg"], "ticker"].nunique()


def test_allocation_refuses_a_dimension_it_does_not_have(book):
    with pytest.raises(KeyError):
        book.allocation(by="theme")


def test_activity_is_every_buy_and_every_sale(book):
    """A POOL'S RELEASE IS NOT AN ACTION ANYBODY TOOK. It is derived from the sale, so activity is
    the trade rows and the exit rows, each once, and nothing else."""
    a = book.activity()
    assert set(a["direction"]) <= {"Buy", "Sell", "Adjustment"}
    assert len(a) == len(D.trades) + len(D.exits)


@needs("trades")
def test_a_corporate_action_reads_as_an_adjustment_and_moves_no_money(book):
    """A share row of nil cost is a split or consolidation: Trades calls it an Adjustment, and
    only it. A buy of money is never one, and a sale never."""
    a = book.activity()
    nil = {t.id for t in D.trades if t.mode == "cost" and t.val == 0}
    assert nil, "the loaded book holds no split or consolidation; this asserts nothing"
    assert set(a.loc[a["direction"] == "Adjustment", "trade_id"]) == nil
    assert (a.loc[a["direction"] == "Adjustment", "value"] == 0).all()


@needs("trades")
def test_activity_reports_money_not_a_contract_level(book):
    """On a spread-bet buy the record stores the entry LEVEL in points, not a total. One column
    must mean one thing, so activity() reconstructs the money: stake x level."""
    a = book.activity().set_index("trade_id")
    sb = next(t for t in D.trades if t.mode == "sb")
    ties(a.loc[sb.id, "value"], sb.stake * sb.val, f"{sb.id} value is stake x level")
    assert a.loc[sb.id, "value"] > 1000, "a spread-bet notional should not read as a level"


@needs("trades")
def test_a_spread_bet_reads_as_its_stake_and_level_and_they_tie_to_its_money(book):
    """stake x level = the money, on every spread-bet row, buy and sale alike; and the stake
    agrees with the one trades.csv records wherever it records one. A share carries neither."""
    a = book.activity()
    sb, shares = a[a["held_as"] == "spread bet"], a[a["held_as"] != "spread bet"]
    assert not sb.empty and sb["direction"].eq("Sell").any(), "no spread-bet sale to check"
    for r in sb.to_dict("records"):
        assert abs(r["stake_per_point"] * r["level_points"] - r["value"]) < 0.02, r["trade_id"]
        if r["stake"] is not None and r["stake"] == r["stake"]:
            assert abs(r["stake_per_point"] - float(r["stake"])) < 1e-9, r["trade_id"]
    assert shares["stake_per_point"].isna().all() and shares["level_points"].isna().all()


def test_a_quarter_with_no_opening_nav_gets_no_return(book):
    """NEVER ZERO, which is a claim. The rule the retired report tab broke."""
    q = book.quarter_returns()
    for _, row in q.iterrows():
        if row["opening_nav"] == 0 and row["capital_deployed"] == 0:
            assert pd.isna(row["return"]), (
                f"period to {row['quarter_end']} has nothing to measure from but reports "
                f"{row['return']}")


def test_no_holding_is_split_across_two_currencies(book):
    """THE DEFECT THIS REPLACES, and the rule that stops it returning.

    ONE holding was once booked into TWO currency buckets. STRM.DE is Stormvik on Xetra, quoted in
    EUR — but its S.104 pool adjustment row carried the code GBP, and the currency decides the
    VALUATION ROUTE, so the pool was undervalued and part of it leaked into the GBP
    bucket. BOTH TOTALS STILL TIED, which is why it survived. Fixed by one field: a holding's
    currency comes from IDENTITY, never from whichever ledger row happens to be first.
    """
    cur = book.allocation(by="currency")
    ties(cur["value"].sum(), book.total_exposure(), "currency buckets vs total exposure")
    ident = book._identity().set_index("code")["currency"]
    for _, row in book.holdings(by="ticker").iterrows():
        assert row["currency"] == ident[row["ticker"]], (
            f"{row['ticker']} is reported as {row['currency']} but securities.csv says "
            f"{ident[row['ticker']]}")


@needs("trades")
def test_gbp_exposure_equals_uk_exposure(book):
    """A corroboration, not a coincidence. Every GBP-quoted holding in this book is a UK
    issuer, so the two figures must agree — and they did NOT while the Stormvik adjustment was
    leaking into GBP. It is the cheapest available check that the leak has not returned."""
    cur = book.allocation(by="currency").set_index("currency")["value"]
    reg = book.allocation(by="region").set_index("region")["value"]
    ties(cur["GBP"], reg["UK"], "GBP exposure vs UK exposure")


def test_the_account_blocks_roll_up_to_the_portfolio_table(book):
    """Account detail, without the trap the old indented sub-rows came with.

    Sub-rows inside the main table had to be excluded from every roll-up by hand — "never sum a
    column here, it would count them twice". Holdings puts each account in its OWN table, so
    there is nothing to exclude.

    The check that matters is that they still add up.
    """
    port = book.holdings(by="ticker")["value"].sum()
    blocks = sum(book.holdings(account=a, by="ticker")["value"].sum()
                 for a in D.ACCOUNT_ORDER)
    ties(blocks, port, "account blocks vs the portfolio table")
    ties(port, book.total_exposure(), "portfolio table vs total exposure")


@needs("trades")
def test_the_two_populations_stay_apart(book):
    """A trim is not a round trip. The realised total spans both; the trade count does not.
    Collapsing them would overstate how many trades the book has completed."""
    rt = book.round_trips()
    assert rt["fully_closed"].any() and (~rt["fully_closed"]).any(), \
        "both populations must exist, or this asserts nothing"
    ties(rt["gain"].sum(), book.realised(), "realised spans BOTH populations")


def test_an_accounts_cash_is_its_newest_reading_of_either_kind(book):
    """`Book.newest_cash()` takes the newer of an account's newest cash reading and the cash its
    own reading states, the cash reading on a tie, and never a cash figure beside a reading
    whose document states none (ii's holdings export). Decided 13 Oct 2026, when both IG
    accounts' cash readings were six weeks older than their account readings."""
    held = book.newest_cash().set_index("account")
    assert list(held.index) == list(D.ACCOUNT_ORDER)
    for a in D.ACCOUNT_ORDER:
        o = D.cash_latest().get(a)
        r = next((x for x in D.ac_rows if x.acct == a), None)
        own = (r.funds if book.is_spread_bet(a) else r.recon_cash) if r is not None else None
        stated = (own is not None
                  and (book.is_spread_bet(a) or D.states_cash(D.EVIDENCE_BY_KEY.get(r.evidence))))
        if stated and (o is None or r.as_of > o.as_of):
            want = (own, r.as_of.isoformat(), r.evidence)
        elif o is not None:
            want = (o.cash, o.as_of.isoformat(), o.evidence)
        else:
            want = (None, None, None)
        label = D.EVIDENCE_BY_KEY[want[2]].label if want[2] else None
        assert (held.loc[a, "cash"], held.loc[a, "as_of"], held.loc[a, "document"]) == \
            (want[0], want[1], label), a


def test_a_reading_that_states_its_cash_keeps_its_own(book):
    """Where the document gives the cash — HL's does — the reconciliation shows the reading's
    own cash and total, dated to it, never a cash reading of another day swapped in."""
    rc = book.reconciliation().set_index("account")
    for r in D.ac_rows:
        if book.is_spread_bet(r.acct) or not D.states_cash(D.EVIDENCE_BY_KEY.get(r.evidence)):
            continue
        row = rc.loc[r.acct]
        assert (row["cash_at_recon"], row["statement"]) == (r.recon_cash, r.stmt_value), r.acct
        assert row["cash_at_recon_at"] == row["struck_on"], r.acct


@pytest.mark.audit
def test_every_share_reading_rests_on_units_that_still_agree(book):
    """A SHARE ACCOUNT IS CHECKED ON UNITS (the owner, 30 Sep 2026), and this is the audit's half.

    The door refuses a holdings export whose units are not the book's, so a reading on file
    agreed when it was written. What can change since is the BOOK: an event entered later and
    dated before the reading moves the book's units at that date, and not the document's. So
    this re-reads each share account's filed export and asks `Book.units_check()` again. A
    reading resting on no export — a screenshot — is work owed as well.

    WHAT CLEARS IT: the missing event, entered on the Bench; or, for a reading with no export,
    one holdings export, filed on the Bench, which writes the reading. Never a time of day.
    """
    from portfusion.desk.intake import read_document, read_rows
    folder = D.schema.STATEMENTS
    filed = [p.name for p in folder.iterdir()] if folder.is_dir() else []
    owed = []
    for r in D.ac_rows:
        if book.is_spread_bet(r.acct):
            continue
        if r.evidence not in D.HOLDINGS_COLUMNS:
            owed.append(f"{r.acct} — its reading rests on {r.evidence}, which lists no units: "
                        f"a holdings export is owed")
            continue
        source = D.evidence_source(r.evidence, reference=r.reference, account=r.acct)
        names = D.filed_as(source, filed) or []
        if len(names) != 1:
            owed.append(f"{r.acct} — \"{source}\" matches {len(names)} filed document(s)")
            continue
        text = read_document.extract_file(folder / names[0])["text"]
        check = book.units_check(r.acct, str(r.as_of)[:10], read_rows.holdings(text, r.evidence))
        owed += [f"{r.acct} — {x.ticker}: book {x.book:,.0f}, {names[0]} {x.broker:,.0f}"
                 for x in check[~check["agrees"]].itertuples(index=False)]
    assert not owed, ("share accounts whose units are not shown to agree:\n    "
                      + "\n    ".join(owed))


@pytest.mark.audit
def test_every_reconcilable_account_still_agrees_with_its_broker(book):
    """Does the RECORD tie today — asked through the engine's verdict, never a second band.

    It belongs in the audit set. A price sweep moves the book's marks while broker-side
    readings stay where they were struck, and the rows go red with no code defect and no code
    change that could make them green. That is the audit's question by definition.

    `reconciliation_verdict()` owns the band. This asserts only that it reached a verdict it
    is content with, so a change to the band rule lands here without editing this file.
    """
    rc = book.reconciliation().set_index("account")
    out = []
    for account, row in rc.iterrows():
        v = book.reconciliation_verdict(row["statement"], row["difference"], row["evidence"],
                                        row["comparable"], row["comparability"])
        if v["checkable"] and not v["ties"]:
            out.append(f"{account} is out by {row['difference']:,.2f} against the broker "
                       f"— {v['rule']}")
    # EVERY ACCOUNT, NOT THE FIRST ONE. An audit is a report; stopping at the first row hides
    # the rest behind it.
    assert not out, "accounts no longer agree with their broker:\n    " + "\n    ".join(out)


def test_the_spread_bet_reconciliation_is_not_comparing_a_figure_with_itself(book):
    """THE DEFECT THIS BLOCK SHIPPED WITH, and it read as a clean bill of health.

    book_total for a spread-bet account was `r.equity` — and `stmt_value` on the same ac_rows
    row IS that equity. So the difference column printed 0.00 for the spread-bet accounts, for
    weeks, while comparing the statement figure with itself. A reconciliation that cannot
    fail is not a reconciliation.

    The book's own number for those accounts is the DERIVED nav — capital in, plus realised,
    plus unrealised, plus income — which is computed from the ledger and knows nothing about
    what the broker said. THAT is what has something to prove.

    Asserting the two are not the same object is not enough: they would coincide by accident
    on a day the derivation happened to land exactly on the broker's figure. So this checks
    the SOURCE — reconciliation()'s book column must equal the engine's nav.
    """
    rc = book.reconciliation().set_index("account")
    for account, row in rc.iterrows():
        if D.ACCOUNT_KIND.get(account) != "spread bet":
            continue
        # AT THE READING'S OWN DATE. The book's side is pinned to the instant the broker's figure
        # was struck at; asking the live NAV here would assert the very floating that pinning
        # stopped.
        day = row["struck_on"] or None
        nav = book.by_account(day).set_index("account")["nav"].to_dict()
        assert abs(row["book"] - nav[account]) < 1e-9, (
            f"{account}: the reconciliation's book figure is not the engine's derived NAV at "
            f"{day} — {row['book']:,.2f} against {nav[account]:,.2f}")
        # NOT "THE TWO FIGURES MUST DIFFER". That cheap proxy fitted a book_total copied from the
        # broker; a reading that strikes the marks and the equity in ONE PASS makes the two
        # sides agree — a spread bet's by 7e-12, which is floating point, not agreement by accident —
        # and a correct reconciliation could not satisfy it. The assertion above is the guard
        # actually wanted: the book's side is DERIVED, which is a property of the code and
        # holds whatever the market did.


@needs("trades")
def test_an_account_a_day_cannot_value_is_blank_and_never_zero(monkeypatch):
    """by_account()'s dated branch left out an account `holdings_at()` could not value, and its
    comment said "left absent rather than guessed at zero"; then `per_account()` filled it with
    0.0, and the account was worth nothing that day (the code review of 2 Oct 2026).
    It happens at an opening, where a share account holds a line with no mark that early.
    A blank, which every sum it reaches carries."""
    from portfusion.engine import MissingMark
    b = Book()
    day = max(D.QSNAP_FROZEN)
    blind = next(a for a in D.ACCOUNT_ORDER if not b.is_spread_bet(a))
    real = b.holdings_at

    def holdings_at(as_of, account, **kw):
        if account == blind:
            raise MissingMark(["TEST.L"], f"no price for TEST.L on or before {as_of}")
        return real(as_of, account, **kw)
    monkeypatch.setattr(b, "holdings_at", holdings_at)

    by = b.by_account(day).set_index("account")
    assert pd.isna(by.loc[blind, "exposure"]) and pd.isna(by.loc[blind, "nav"]), \
        f"{blind} was valued at {by.loc[blind, 'nav']} on a day nothing could value it"
    others = [a for a in D.ACCOUNT_ORDER if a != blind]
    assert by.loc[others, "nav"].notna().all(), "the other accounts lost their value too"


def test_income_rows_sum_to_the_book_income(book):
    """The Accounts tab's income block must still total what the book publishes."""
    rows = book.income_rows(book.ytd_year())
    ties(rows["amount"].sum(), book.totals()["income"], "YTD income")


# =====================================================================================
# SORT ORDER
#
# Two rules. ENTITY LISTS use a canonical order; EVENT LOGS are newest first, each account's
# income among them since 14 Oct 2026 (the owner), when the one exception to the rule ended.
#
# Worth a test because it is exactly the kind of thing that drifts one block at a time
# and is only ever noticed by eye — which is how it was noticed.
# =====================================================================================

# ======================================================================================
# PERFORMANCE
# ======================================================================================

@needs("trades")
def test_a_quarters_name_is_derived_from_its_end_date(book):
    """THE POINT OF THE VOCABULARY. A reader once had to work out that "2026-06-30" and "Q2 2026"
    were the same quarter, because one table keyed on dates and another on names typed into a CSV.
    The name is DERIVED from the end date, year included, so a 2027 quarter cannot be stamped 2026,
    and every quarter the returns carry wears the name its own date gives it.
    """
    assert book.quarter_label("2026-03-31") == "Q1 2026"
    assert book.quarter_label("2026-06-30") == "Q2 2026"
    assert book.quarter_label("2025-12-31") == "Q4 2025"
    assert book.quarter_label("2031-01-02") == "Q1 2031"
    q = book.quarter_returns()
    assert len(q), "no closed quarter to name"
    for r in q.itertuples():
        assert r.quarter == book.quarter_label(str(r.quarter_end)[:10]), (
            f"{r.quarter_end} carries {r.quarter!r}, not the name its date gives it")


# ======================================================================================
# TRADES
# ======================================================================================

def test_the_quarter_to_close_moves_on_at_the_freeze(monkeypatch):
    """A typed quarter end goes on being printed after the quarter has closed. The quarter to
    close is the first after the last one FROZEN, so it moves on when the store says so — not
    when the calendar turns — and a quarter that has ended unfrozen stays the one named."""
    from portfusion.engine import Book
    from portfusion.record import rules as D
    for frozen, expected in ((set(), "2026-03-31"),
                             ({"2026-03-31", "2026-06-30"}, "2026-09-30"),
                             ({"2026-03-31", "2026-06-30", "2026-09-30", "2026-12-31"},
                              "2027-03-31")):
        monkeypatch.setattr(D, "QSNAP_FROZEN", frozen)
        assert str(Book.quarter_to_close().date()) == expected, (frozen, expected)


def test_trades_are_newest_first_with_a_stable_tie_break(book):
    """Several dates in this book carry more than one event. Sorting on date alone leaves their
    order to whatever pandas saw first, so the page could reorder between reads with nothing in
    the record having changed — indistinguishable from a real edit."""
    rows = book.activity()
    keys = list(zip(rows["date"], rows["trade_id"]))
    assert keys == sorted(keys, reverse=True), "not newest-first with trade id breaking ties"


def test_every_traded_price_is_local_or_absent(book):
    """THE COLUMN SAYS LOCAL, SO IT MUST BE LOCAL. Deriving value/quantity with no rate
    returns the GBP figure under a heading that says otherwise — a sterling price for a deal
    whose contract note gives it in euros. A deal priced in sterling on a foreign share reads at its
    day's close or not at all; a spread bet and a London deal take no rate."""
    rows = book.activity().set_index("trade_id")
    deals = {t.id: t for t in D.trades} | {e.eid: e for e in D.exits}
    for tid, r in rows.iterrows():
        d = deals[tid]
        if r["held_as"] == "spread bet" or r["currency"] == "GBP":
            assert pd.isna(r["fx_at_trade"]), f"{tid} took a rate it never needed"
            continue
        if d.price is None:
            assert pd.isna(r["traded_price"]), f"{tid} has a price no document states"
        elif d.cur == "GBP":
            if pd.notna(r["traded_price"]):
                ties(d.price * r["fx_at_trade"], r["traded_price"], f"{tid} at its day's close")
                assert r["fx_from"] == "TradingView close", tid


def test_the_contract_note_prices_come_from_the_record(book):
    """A deal's own price and its broker's rate, read off the row. The engine used to
    recompute these from value/quantity and get the GBP figure instead. Reading the record
    rather than recomputing it is the whole point of having one. The loop derives from the
    store, so it covers however many deals the loaded book states a price for."""
    rows = book.activity().set_index("trade_id")
    for d in [*D.trades, *D.exits]:
        i = getattr(d, "id", None) or d.eid
        if d.price is None or d.cur == "GBP" or i not in rows.index:
            continue
        ties(d.price, rows.loc[i, "traded_price"], f"{i} the document's price")
        if d.rate is not None:
            ties(d.rate, rows.loc[i, "fx_at_trade"], f"{i} the broker's rate", tol=1e-9)


# =====================================================================================
# THE PRICE DATE ON A MULTI-CONTRACT HOLDING  (the owner spotted this on Morane)
#
# Holdings shows ONE "Price as at" per ticker, and a spread-bet ticker can hold legs on
# several contracts. The lookup that fed it was `{t.ticker: LEG_CONTRACT[t.id] for t in
# trades}` — keyed by ticker, so the LAST leg in file order won. MORA SB collapsed onto
# MORA-DEC26, a closed leg with no price row by design, and the cell rendered BLANK for a
# holding that is priced daily.
#
# The blank was the lucky outcome. ZEPH SB collapses across four contracts and HALV SB
# across two; both landed on a priced contract and showed a plausible date from a leg that
# was not necessarily the right one. Had two contracts carried different dates, the tab
# would have printed one of them with nothing to say which.
# =====================================================================================

def test_every_open_holding_has_a_price_date(book):
    """A blank date reads as 'no price', and every open holding here has one."""
    h = book.holdings(by="ticker")
    missing = h.loc[h["priced_at"].isna(), "ticker"].tolist()
    assert not missing, (
        f"open holdings with no 'Price as at': {missing}. A spread bet priced daily must not "
        f"render a blank date — check whether its ticker collapsed onto a CLOSED leg's "
        f"contract, which is how MORA SB broke.")


def test_the_price_date_comes_from_the_open_legs_not_the_last_one(book):
    """The date must be the OLDEST mark across the ticker's OPEN legs — a position is only
    as fresh as its stalest leg — and it must ignore contracts nothing holds any more."""
    from portfusion.record import rules as _D
    px = {r[0]: r[3] for r in _D.CURRENT_PRICES}
    open_ids = set(book.ledger[book.ledger["open_leg"]]["id"])
    expected = {}
    for t in _D.trades:
        if t.mode != "sb" or t.id not in _D.LEG_CONTRACT or t.id not in open_ids:
            continue
        c = _D.LEG_CONTRACT[t.id]
        if c in px:
            expected.setdefault(t.ticker, []).append(px[c])
    h = book.holdings(by="ticker").set_index("ticker")
    for ticker, dates in expected.items():
        if ticker not in h.index:
            continue
        assert h.at[ticker, "priced_at"] == min(dates), (
            f"{ticker}: 'Price as at' is {h.at[ticker, 'priced_at']}, but its OPEN legs are "
            f"marked {sorted(set(dates))} — the oldest is the honest date for the position")


@needs("trades")
def test_a_closed_legs_contract_is_not_expected_to_be_priced(book):
    """The other half, so nobody 'fixes' this by adding price rows for dead contracts.

    MORA-DEC26 and STRM-SEP26 have no row in CURRENT_PRICES and should not: the legs on
    them are closed, and pricing a contract nothing holds would be inventing a mark to fill
    a column. The test that would have caught the original bug is the one above; this one
    stops the wrong cure.
    """
    from portfusion.record import rules as _D
    px = {r[0] for r in _D.CURRENT_PRICES}
    closed_only = set()
    by_contract = {}
    open_ids = set(book.ledger[book.ledger["open_leg"]]["id"])
    for t in _D.trades:
        if t.mode == "sb" and t.id in _D.LEG_CONTRACT:
            by_contract.setdefault(_D.LEG_CONTRACT[t.id], []).append(t.id in open_ids)
    for contract, held in by_contract.items():
        if not any(held):
            closed_only.add(contract)
    assert closed_only, "expected at least one contract whose legs are all closed"
    leaked = sorted(closed_only & px)
    assert not leaked, (
        f"contracts with no open leg carry a live price: {leaked}. Nothing holds them; a "
        f"price there is a mark nobody needs and a refresh would have to keep fresh.")


def test_every_live_price_is_on_a_line_still_held(book):
    """A share no account holds, or a contract no open leg is on, carries no live price: the
    sale that empties it retires it, and the audit names any that stays."""
    unheld = book.priced_unheld()
    assert not unheld, (
        f"live prices on lines nothing holds: {unheld}. Every refresh fetches them and their "
        f"age counts against the prices' freshness.")
    assert not [p for p in book.findings()["problems"] if "nothing holds" in p]


# =====================================================================================
# THE TRADING FLOW IS DERIVED  (after the owner found Q3 had stopped moving)
#
# capital-flows.csv was hand-kept, and its "Q3 to date" row had captured nothing for weeks.
# It was wrong in BOTH directions at once — understating one spread-bet account because two
# legs were never added, and overstating another because its opens were carried through and
# its closes were not. Two share-account sales were missing entirely.
#
# Nothing could see it. The table fed section 5, block 6b's net-invested returns and the
# quarter-return series, and there was nothing anywhere to compare it against.
#
# The figures now come from the ledger, and the hand-kept table is retired (8 Oct 2026).
# =====================================================================================

def test_every_closed_quarter_reads_as_it_was_held(book):
    """A CLOSED QUARTER DOES NOT MOVE UNLESS A ROW SAYS WHY (the owner, 1 Oct 2026).

    `quarter-results.csv` holds each closed quarter's six figures, for the book and each account,
    as the engine gave them; the newest row for a quarter end and an account is the one in force.
    A change that moves one fails here, and the fix is a decision: a restatement row with its
    reason, never a looser comparison. Every closed quarter must be held, so a freeze that left
    its results out fails too.
    """
    from portfusion.record import schema
    header = schema.TABLES["quarter-results"].header
    held = {}
    for r in D.QUARTER_RESULTS:
        row = dict(zip(header, r))
        held[(str(row["as_of"]), row["account"])] = row      # file order: a later row restates
    closed = sorted(str(q)[:10] for q in book.quarter_returns()["quarter_end"])
    assert sorted({q for q, _ in held}) == closed, (
        f"quarter-results.csv holds {sorted({q for q, _ in held})}; the closed quarters end "
        f"{closed}")
    moved = []
    for q in closed:
        for now in book.quarter_results(q):
            was = held.get((q, now["account"]))
            who = now["account"] or "the book"
            if was is None:
                moved.append(f"{q} {who}: no row held")
                continue
            moved += [f"{q} {who} {f}: held {was[f]}, the engine now says {now[f]}"
                      for f in book.RESULT_FIGURES if was[f] != now[f]]
    assert not moved, ("a closed quarter moved:\n  " + "\n  ".join(moved)
                       + "\nIf the change is meant, append a restatement row saying why.")


# =====================================================================================
# ONE REASONING STORE  (the owner)
#
# It was two — OPEN_THESIS for Holdings, TRADE_RATIONALE for Round Trips — both keyed by
# ticker and both holding why_entered. A position moves from Holdings to Round Trips when
# it closes; THE REASONING DID NOT MOVE WITH IT, because the two pages read different
# dictionaries. A thesis would have vanished the day its position closed, and nothing would
# have said so.
#
# It had not fired because every closed parcel was opened before the write-up cut-off, so
# every why_entered on Round Trips is legitimately blank. The defect was invisible for the
# same reason it was harmless — which is the worst combination.
# =====================================================================================

@needs("trades")
def test_an_open_position_keeps_its_thesis_when_it_closes():
    """THE DEFECT THE MERGE REMOVED, asserted at the source rather than on a page.

    Holdings and Round Trips must read the SAME store, so a ticker's reasoning is reachable
    whichever side of the close it is on: one store, and both pages keyed off it through
    Book.with_reasoning().
    """
    assert not hasattr(D, "OPEN_THESIS"), "the split store is back"
    assert not hasattr(D, "TRADE_RATIONALE"), "the split store is back"
    assert isinstance(D.REASONING, dict) and D.REASONING
    from portfusion.desk.panels import holdings, round_trips
    for mod in (holdings, round_trips):
        assert "with_reasoning" in pathlib.Path(mod.__file__).read_text(), \
            f"{mod.__name__} does not read the reasoning through the engine"


def test_the_research_note_is_derived_not_stored_twice():
    """It used to be a third element in the tuple, and Round Trips ignored it in favour of
    deriving it from RESEARCH_NOTES anyway — a copy one consumer already disagreed with.
    Both tabs derive it now, so there is nothing to drift."""
    fields = tuple(f.name for f in D.schema.TABLES["reasoning"].fields)
    for ticker, rows in D.REASONING.items():
        assert all(r._fields == fields for r in rows), (
            f"{ticker}'s whys carry {rows[0]._fields}; a why holds the table's own columns and "
            f"the research note is derived")


# =====================================================================================
# THE RETURN STOPS CHASING CASH  (the owner)
#
# A flow is money into POSITIONS, not cash across the book's boundary. These pin the defect
# that forced it and the coherence of what replaced it.
# =====================================================================================

def _figures(b):
    """The year's figures, rounded. A BLANK ONE IS None: until the year's opening is frozen its
    return is NaN, and NaN equals nothing, itself included, so every January a figure that had
    not moved read as moved."""
    t = b.totals()
    return {k: None if pd.isna(t[k]) else round(float(t[k]), 2) for k in
            ("opening_capital", "capital_deployed", "capital_employed", "nav",
             "capital_growth", "return_income", "ytd")}


@needs("trades")
@needs("trades")
def test_a_blank_years_figures_equal_themselves(monkeypatch):
    """JANUARY, BEFORE THE YEAR'S OPENING IS FROZEN: the return is blank, and the tests above that
    compare the figures before and after a change would fail with nothing changed."""
    b = Book()
    real = b.totals
    monkeypatch.setattr(b, "totals", lambda *a, **k: {**dict(real(*a, **k)), "ytd": float("nan")})
    assert _figures(b) == _figures(b)


def test_A_CASH_WITHDRAWAL_MOVES_NO_RETURN_FIGURE(monkeypatch):
    """THE DEFECT THAT STARTED THIS. Two cash withdrawals moved the published return by
    over a point — most of it from the numerator alone, because the
    flow term fell while NAV never moved. NAV for a share account is positions at market and
    cash is not in it, so subtracting a cash flow booked gain that never happened.

    Now a withdrawal is not a flow at all, and nothing may move.
    """
    from portfusion import engine
    import pandas as pd
    before = _figures(engine.Book())

    b = engine.Book()
    extra = pd.DataFrame([{"date": pd.Timestamp("2026-09-03"), "account": an_account("shares"),
                           "amount": -1000.0, "source": "test", "detail": "a withdrawal"}])
    b.store["movements"] = pd.concat([b.store["movements"], extra], ignore_index=True)
    b.__dict__.pop("by_account", None)          # drop any cached frame
    after = _figures(b)

    assert after == before, (
        "a £1,000 withdrawal moved a figure. Cash is outside NAV, so it must be outside the "
        f"return too.\n  before {before}\n  after  {after}")


@needs("trades")
def test_a_deposit_that_sits_as_cash_moves_nothing_either():
    """The same defect with the opposite sign, and the one that would have made the book look
    WORSE: money in, NAV unmoved, so the numerator falls by the whole deposit."""
    from portfusion import engine
    import pandas as pd
    b = engine.Book()
    before = _figures(b)
    extra = pd.DataFrame([{"date": pd.Timestamp("2026-09-03"), "account": an_account("shares"),
                           "amount": 5000.0, "source": "test", "detail": "a deposit"}])
    b.store["movements"] = pd.concat([b.store["movements"], extra], ignore_index=True)
    assert _figures(b) == before, "a deposit sitting as cash moved the return"


@needs("trades")
def test_a_spread_bets_flow_is_its_funds_on_any_book():
    """Q6'S TWIN (decided 9 Oct 2026): its sibling in `checks/` pins THIS book's settled
    figures and stays home with the book; this one derives the same three-way
    distinction from whichever book is loaded, so the beta ships with the enforcement.

    THE FLOW IS THE MONEY MOVED IN — the account's cash movements, recomputed here straight
    off the store — never the legs' entry cost and never their notional. On a funded
    spread-bet account with open legs the three are different numbers, and the premise that
    they differ is asserted, not assumed."""
    from portfusion import engine
    from portfusion.record import rules as D
    b = engine.Book()
    deployed = b.capital_deployed()
    mv = b.store["movements"]
    accounts = [a for a in D.ACCOUNT_ORDER if D.ACCOUNT_KIND[a] == "spread bet"]
    assert accounts, "no spread-bet account on this book — the distinction has nothing to bite on"
    distinguished = 0
    for account in accounts:
        funds = round(float(mv[mv["account"] == account]["amount"].sum()), 2)
        legs = b.ledger.query("acct == @account and direction == 'Buy' and qty > 0")
        entry_cost = round(float(legs["gbp_cost"].sum()), 2)
        notional = round(float(legs["gbp_value"].sum()), 2)
        assert deployed[account] == funds, (
            f"{account}: the flow term is {deployed[account]:,.2f}, not the account's own "
            f"funds {funds:,.2f}")
        for figure, said in ((entry_cost, "entry cost"), (notional, "notional")):
            if figure != funds:
                distinguished += 1
                assert deployed[account] != figure, (
                    f"{account}: the flow equals its {said} {figure:,.2f} — the basis "
                    f"mistake the FUNDS rule exists to prevent")
    assert distinguished, (
        "every spread-bet account's legs happen to equal its funds, so nothing here told "
        "the three figures apart — the premise is gone, not proven")


def test_only_the_capitals_own_income_reaches_the_return():
    """The owner's split: a dividend is return on the shares and funding interest is the price of
    holding a bet open, so both count. A platform fee and interest on idle CASH belong to the
    account — they are the noise this basis exists to remove.

    AND YTD INCOME IS UNCHANGED. Only the return filters; the Dashboard figure is true about
    the book and dropping it would answer a question nobody asked."""
    from portfusion import engine
    from portfusion.record import rules as D
    b = engine.Book()
    assert set(D.POSITION_INCOME) == {"Dividend", "Funding interest"}
    assert set(D.ACCOUNT_INCOME) == {"Cash interest", "Fee"}

    # DERIVED, NOT TYPED. Two live totals written in here failed on ordinary work — entering
    # one dividend turned the test red, and the fix was always to retype a figure.
    #
    # A FIGURE IS NOT THE RULE. The rule is that the return takes POSITION_INCOME and the
    # Dashboard's Income takes everything, and that holds whatever the numbers are. Stated
    # this way a cash-interest row provably cannot move the return, which is the claim the
    # hardcoded pair was standing in for. Why each figure moved is in the commits.
    rows = b.income_rows(2026)
    position = rows[rows["category"].isin(D.POSITION_INCOME)]["amount"].sum()
    assert round(float(b.position_income(2026).sum()), 2) == round(float(position), 2), \
        "the return's numerator is not the POSITION_INCOME rows"
    assert round(float(b.income_by_account(2026).sum()), 2) == round(float(rows["amount"].sum()), 2), \
        "the year's income is not the whole table — only the RETURN filters"

    # AND THE FILTER IS LOAD-BEARING: an account-income row must reach Income and not the
    # return. Asserted on the record's own rows rather than on a remembered total.
    account_side = rows[rows["category"].isin(D.ACCOUNT_INCOME)]["amount"].sum()
    assert round(float(position + account_side), 2) == round(float(rows["amount"].sum()), 2), \
        "the two halves do not add back to the whole table"


def test_income_reaches_a_return_once():
    """A SPREAD-BET ACCOUNT'S EQUITY ALREADY HOLDS ITS INCOME, and the book's return once added
    its funding on top: a quarter's funding was counted twice (found 30 Sep 2026).
    A share account's value holds none, so its dividends are added — and, until the same day,
    reached the book's return and never the account's own. The term is `return_income()`."""
    from portfusion import engine
    from portfusion.record import rules as D
    b = engine.Book()
    rows = b.income_rows(2026)
    got = b.return_income(2026)
    for account in D.ACCOUNT_ORDER:
        mine = rows[rows["account"] == account]
        if b.is_spread_bet(account):
            want = -mine[mine["category"].isin(D.ACCOUNT_INCOME)]["amount"].sum()
        else:
            want = mine[mine["category"].isin(D.POSITION_INCOME)]["amount"].sum()
        assert round(float(got.get(account, 0.0)), 2) == round(float(want), 2), account


@needs("trades")
def test_a_year_end_moves_no_balance():
    """THE YEAR'S FIGURES ROLL AT THE YEAR END AND THE BALANCES DO NOT — `by_account()` says what
    rolling the balances too would cost. The year opens at its frozen 31 December, every
    account's NAV is the same figure either side of it, and the year to date is the same
    day-weighted formula a quarter is."""
    now = Book()
    b = book_in_the_next_year(frozen=True)
    by = b.by_account().set_index("account")
    assert b.ytd_year() == now.ytd_year() + 1
    assert (by["nav"] - now.by_account().set_index("account")["nav"]).abs().max() < PENNY, \
        "a year end moved a balance"
    opens = b.ytd_opens()
    at_open = b.quarter_nav_rows(opens).set_index("account")["amount"]
    for account in D.ACCOUNT_ORDER:
        assert by.loc[account, "opening_capital"] == pytest.approx(
            at_open.get(account, 0.0), abs=PENNY), f"{account} does not open at {opens}"
    year = b._dietz(opens, b.valued_at(), b.quarter_nav_total()[opens], b.nav())
    assert b.totals()["ytd"] == pytest.approx(year["return"], abs=RATE)


@needs("trades")
def test_the_year_to_date_is_blank_until_its_opening_is_frozen():
    """NOTHING TO MEASURE FROM IS NOT ZERO (the owner, 2 Oct 2026: a blank, for the short time it
    lasts). From the first price of a new year until its 31 December is frozen, the year's
    opening, capital employed, growth and return are blank, on every account and in the total —
    where pandas would otherwise sum the blanks to £0.00 — and every balance stands."""
    now = Book()
    b = book_in_the_next_year(frozen=False)
    by = b.by_account().set_index("account")
    assert (by["nav"] - now.by_account().set_index("account")["nav"]).abs().max() < PENNY
    t = b.totals()
    for column in ("opening_capital", "capital_employed", "capital_growth", "ytd"):
        assert by[column].isna().all(), f"{column} has a figure with nothing to measure from"
        assert pd.isna(t[column]), f"the total {column} is {t[column]}, from nothing"
    assert not by["opened_in_period"].any(), "a blank opening read as an account opened in the year"
    assert t["nav"] == pytest.approx(now.nav(), abs=PENNY)


@needs("trades")
def test_a_row_of_the_new_year_rolls_the_year_before_its_first_price():
    """A ROW DATED 2 JANUARY ROLLS THE YEAR AS A FIRST PRICE WOULD (the owner, 2 Oct 2026;
    `ytd_year()` says why). Stopping the terms at 31 December instead would leave a January
    purchase in the value with no money in against it. With nothing frozen to open from, the
    rolled year's return is blank."""
    year = Book().ytd_year() + 1
    before = Book()
    before.valued_at = lambda: f"{year - 1}-12-31"
    assert before.ytd_year() == year - 1, "a book valued at 31 December rolled with no new row"

    b = Book()
    b.valued_at = lambda: f"{year - 1}-12-31"
    income = b.store["income"]
    row = income.iloc[[-1]].assign(date=pd.Timestamp(f"{year}-01-02"))
    b.store = {**b.store, "income": pd.concat([income, row], ignore_index=True)}
    assert b.ytd_year() == year, "a row of the new year was counted under the year before"
    assert pd.isna(b.totals()["ytd"]), "the year rolled onto an opening nobody has frozen"


@needs("trades")
def test_the_return_since_the_start_links_the_years():
    """LINKED, NOT ONE PERIOD (the owner, 2 Oct 2026; `since_start()` says why). In the first year it
    is the year to date; after a year end, each full year's frozen return linked with the year to
    date; and with nothing yet to open the year from, blank as that is."""
    first = Book()
    first.valued_at = lambda: f"{BASELINE.year}-09-30"
    assert first.since_start() == pytest.approx(first.totals()["ytd"], abs=RATE)

    b = book_in_the_next_year(frozen=True)
    years = range(BASELINE.year, b.ytd_year())
    assert len(years) >= 1
    want = (1 + b.totals()["ytd"]) * math.prod(
        1 + b.year_to_quarter(f"{y}-12-31")["return"] for y in years) - 1
    assert b.since_start() == pytest.approx(want, abs=RATE)
    assert pd.isna(book_in_the_next_year(frozen=False).since_start())


def test_the_firms_gain_is_its_accounts_gains():
    """ONE NUMERATOR, so the parts add to the whole: each closed quarter's firm gain is the sum
    of its accounts' — which it was not while the accounts counted no income and the book
    counted a spread bet's funding twice."""
    from portfusion import engine
    b = engine.Book()
    per = b.account_quarter_returns()
    # A BLANK GAIN ADDS NOTHING, so this also says a quarter whose account gain is blank moved
    # nothing the book counts. Failing on such a row would mean the book counts a gain its own
    # account calls unknown.
    for q in b.quarter_returns().to_dict("records"):
        parts = per[per["quarter_end"] == q["quarter_end"]]["gain"].sum()
        assert abs(parts - q["gain"]) < 0.01, (q["quarter"], parts, q["gain"])


def test_the_quarters_and_the_year_are_the_same_measure():
    """They were not, for a moment: the year moved to money-into-positions while the quarters
    still summed cash movements, and nothing would have said which was right."""
    from portfusion import engine
    b = engine.Book()
    q = b.quarter_returns()
    assert "capital_deployed" in q.columns and "return_income" in q.columns
    assert "external_capital" not in q.columns, "a quarter still measures cash flows"


def test_the_engines_own_column_names_say_notional(book):
    """THE THIRD PLACE THE RETIRED TERM COULD HIDE, and it was hiding there.

    `notional` won because it is the store's own word. tests/desk/test_panels.py holds the desk
    to it by reading app.js, which is RENDERED OUTPUT — so it could not see an engine method
    returning a column literally named `economic`, three lines under a docstring that already
    said "which part is money and which is notional".

    A LABEL IS NOT ONLY WHAT A READER SEES. A frame column is what every renderer reads it by,
    and it outlives any one of them. This checks the engine's own vocabulary, which is where the
    word is decided.
    """
    banned = ("economic", "contract_value", "contract value")
    offenders = []
    for name in ("holdings", "by_account", "round_trips", "activity", "quarter_returns"):
        frame = getattr(book, name)()
        for col in frame.columns:
            low = str(col).lower()
            if any(b in low for b in banned):
                offenders.append(f"{name}() -> {col!r}")
    assert not offenders, (
        "these ENGINE column names use a retired word for a spread-bet position:\n  "
        + "\n  ".join(offenders)
        + "\n'notional' is the store's own word — quarter-nav.csv carries basis 'notional'.")


def test_a_pair_is_judged_when_it_is_comparable_and_not_when_it_is_not(book):
    """The rule that replaced the day limit, at its boundaries.

    THE DAY LIMIT AND ITS SCALING BAND LASTED ONE DAY. Measured against the marks on file,
    a share account can move several percent in a single day, against a
    rule allowing 0.25% a day capped at 1.5%. So it fired whenever the book actually moved,
    and widening it far enough not to would take thousands on one account, which is wider
    than a wrong quantity on a single holding. There was no number that was neither too
    tight nor too loose, which is how you know a tolerance was the wrong instrument.

    What replaced it asks whether the two figures describe the SAME STATE OF THE MARKET.
    `Book.comparability()` measures it, this classifies it, and the verdict prints
    comparability's own words so a reader is told which of several reasons applied.

    NOTHING HERE IS HARDCODED against today's record. Both boundaries are asserted on the rule
    itself, and the frame check below adapts to whatever the record currently holds.
    """
    v = Book.reconciliation_verdict

    # NOT COMPARABLE IS NOT JUDGED, and it is not a pass either.
    apart = v(100_000.0, 50_000.0, "ig-accounts", False, "not read in one pass")
    assert apart["verdict"] == "struck-apart"
    assert apart["checkable"] is False and apart["ties"] is None
    assert apart["rule"] == "not read in one pass", "the verdict prints the measured reason"

    # COMPARABLE IS JUDGED, on the derivation band and nothing else.
    band = 100_000.0 * D.RECON_LIVE_TOLERANCE_PCT
    assert v(100_000.0, band - 0.01, "ig-accounts", True, "")["verdict"] == "within-band"
    assert v(100_000.0, band + 0.01, "ig-accounts", True, "")["verdict"] == "differs"

    # A SHARE ACCOUNT IS NOT ASKED THIS (the owner, 30 Sep 2026): its check is units, so neither a
    # comparability nor a difference moves its verdict.
    assert v(100_000.0, 50_000.0, "ii-valuation", False, "anything")["verdict"] == "units-agree"

    # AND THE ENGINE AGREES WITH ITSELF: a row the frame calls incomparable is never judged.
    rc = book.reconciliation()
    for _, row in rc.iterrows():
        if row["statement"] != row["statement"] or row["comparable"] is not False:
            continue
        out = v(row["statement"], row["difference"], row["evidence"],
                row["comparable"], row["comparability"])
        assert out["verdict"] == "struck-apart", row["account"]


# =====================================================================================
# THE DENOMINATOR IS DAY-WEIGHTED, and a period that opened on nothing
#
# Each flow weighs by the share of the period after its date, so an account funded inside the
# period divides by its deposit scaled by the days it was in. The engine flags those rows and
# words the footnote once (`Book.OPENED_IN_PERIOD`); every renderer prints that wording and
# none has its own.
# =====================================================================================

@needs("trades")
def test_every_return_is_the_gain_over_the_day_weighted_capital(book):
    """THE FORMULA, HELD TO THE ARITHMETIC on every row that has a return: gain ÷ (opening +
    the flows weighted by the days after each), the weights from `weighted_flows()` and nothing
    typed. A change of method fails here before the footnote goes on describing the old one."""
    q = book.account_quarter_returns(include_open=True)
    assert q["return"].notna().any(), "no quarter has a return — this asserts nothing"
    for _, r in q.loc[q["return"].notna()].iterrows():
        wcf = float(book.weighted_flows(r["opens"], r["quarter_end"])[r["account"]])
        assert abs(r["return"] - r["gain"] / (r["opening_nav"] + wcf)) < RATE, r.to_dict()
    opens, end = book.ytd_opens(), book.valued_at()
    a = book.by_account()
    for _, r in a.loc[a["ytd"].notna()].iterrows():
        wcf = float(book.weighted_flows(opens, end)[r["account"]])
        gain = r["nav"] - r["opening_capital"] - r["capital_deployed"] + r["return_income"]
        assert abs(r["ytd"] - gain / (r["opening_capital"] + wcf)) < RATE, r.to_dict()


@needs("trades")
def test_a_flow_weighs_by_the_days_after_it(book, monkeypatch):
    """The weights themselves, on an invented set of flows: one the day after the start weighs
    almost whole, one half way weighs half, one on the last day weighs nothing, and the capital
    deployed still counts every one in full.

    WHY BY DAYS: weighted at the period's midpoint, a flow's date never reached the figure, and
    an account funded on a quarter's last day read as invested for half of it."""
    import pandas as pd
    account = D.ACCOUNT_ORDER[0]
    flows = pd.DataFrame({"account": [account] * 3,
                          "date": pd.to_datetime(["2026-07-01", "2026-08-15", "2026-09-30"]),
                          "amount": [1000.0, 1000.0, 1000.0]})
    monkeypatch.setattr(book, "_dated_flows", lambda start=None, end=None: flows)
    weighted = book.weighted_flows("2026-06-30", "2026-09-30")
    assert weighted[account] == pytest.approx(1000 * (91 + 46 + 0) / 92, abs=1e-6)
    assert book.capital_deployed("2026-06-30", "2026-09-30")[account] == 3000.0
    assert book.weighted_flows("2026-09-30", "2026-09-30")[account] == 0.0, "no days, no weight"




@needs("trades")
def test_a_company_held_in_one_listing_reads_as_that_line(book):
    """A COMPANY ROW IS ONE POSITION, so a company held only as shares of one listing reads as
    that line: the same quantity, entry and current price, in the same currency."""
    lines = book.holdings(by="ticker")
    company = book.holdings(by="issuer").set_index("company")
    single = lines.groupby("company").filter(lambda g: len(g) == 1)
    single = single[single["held_as"] == "shares"]
    if single.empty:
        pytest.skip("no company in this book is held as one share line")
    for r in single.to_dict("records"):
        c = company.loc[r["company"]]
        assert c["currency"] == r["currency"], r["company"]
        assert c["qty"] == r["qty"], r["company"]
        for f in ("entry_price", "current_price"):
            ties(c[f], r[f], f"{r['company']} {f}")


@needs("trades")
def test_a_bet_counts_in_shares_on_its_companys_row(book):
    """A SPREAD BET IS SHARE-EQUIVALENTS on its company's row: stake per point × points per unit ×
    its currency's rate per pound on the deal date × shares per unit, added to the shares held,
    in the share listing's currency wherever shares are held."""
    L = book.ledger
    ident = book._identity().set_index("code")
    company = book.holdings(by="issuer").set_index("company")
    lines = book.holdings(by="ticker")
    checked = 0
    for name, g in L[L["open_leg"]].groupby(L["ticker"].map(ident["company"])):
        bets = g[g["held_as"] == "spread bet"]
        if bets.empty or company.at[name, "qty"] != company.at[name, "qty"]:
            continue
        n = 0.0
        for leg in bets.to_dict("records"):
            cur = ident.at[leg["ticker"], "currency"]
            rate = 1.0 if cur == "GBP" else book._close_on(cur, leg["date"])[1]
            spu = pd.to_numeric(ident.at[leg["ticker"], "shares_per_unit"], errors="coerce")
            n += (leg["qty"] * float(ident.at[leg["ticker"], "points_per_unit"]) * rate
                  * (1.0 if spu != spu else float(spu)))
        shares = lines[(lines["company"] == name) & (lines["held_as"] == "shares")]
        assert company.at[name, "qty"] == round(shares["qty"].sum() + n), name
        if not shares.empty:
            assert company.at[name, "currency"] == shares.sort_values("value")["currency"].iloc[-1]
            assert company.at[name, "current_price"] == shares.sort_values("value")[
                "current_price"].iloc[-1], name
        checked += 1
    if not checked:
        pytest.skip("no company in this book holds a bet with its points per unit on file")
    assert not [g for g in book.findings()["gaps"] if g.startswith("points per unit owed")]


def test_a_listing_is_translated_into_the_feeds_form():
    """The record names a listing as its market does; the feed is asked in its own form, and a
    market it is not mapped for is refused by name rather than asked for."""
    from portfusion.feeds import tv
    assert tv.tv_symbol("XLON:BRYC") == "LSE:BRYC"
    assert tv.tv_symbol("XCSE:HALD B") == "OMXCOP:HALD_B"
    with pytest.raises(ValueError, match="XHKG"):
        tv.tv_symbol("XHKG:0700")
