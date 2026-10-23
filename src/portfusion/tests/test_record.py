"""
THE RECORD — invariants of record/rules.py.

These import no build and touch no file. They exist because record/rules.py once carried NO
assertions of its own: every guard lived inside the build, which only fires once you rebuild,
and several of the things that can go wrong here produce a page that renders cleanly and
is quietly wrong.

Each test names the failure it is defending against. If one fails after a change you meant to
make, update the expectation and say why in the commit message. Do not delete a test to make
a build pass.
"""
import datetime as _dt
import re
from collections import Counter, defaultdict
from datetime import date as _date
import pytest
from harness import needs, free_id

# Trade tuple field positions. Named here once so a reorder breaks in one place rather than
# silently reading the wrong column.
T_ID, T_DATE, T_SOURCE, T_ACCOUNT, T_TICKER, T_CCY = 0, 1, 2, 3, 4, 5

# =====================================================================================
# Identity and referential integrity
# =====================================================================================

def test_trade_ids_are_unique(D):
    """A duplicated ID makes DIRECTION and REALISATION_ID collide silently."""
    dupes = [i for i, n in Counter(t[T_ID] for t in D.buys).items() if n > 1]
    assert not dupes, f"duplicate trade IDs: {dupes}"


def test_exit_ids_are_unique(D):
    """A duplicated exit ID makes REALISATION_BY_EXIT keep one sale's parcel and drop the other's."""
    dupes = [i for i, n in Counter(e.sale_id for e in D.sales).items() if n > 1]
    assert not dupes, f"duplicate exit IDs: {dupes}"


def test_every_trade_account_is_a_known_account(D):
    """
    Account names are matched as STRINGS by every join in the engine. A typo ("Voss IG
    Spread Bet" for "...bet") does not error — it silently joins to nothing and the position
    quietly disappears from its account breakdown.
    """
    known = set(D.ACCOUNT_ORDER)
    unknown = {t[T_ACCOUNT] for t in D.buys} - known
    assert not unknown, f"trades reference accounts not in ACCOUNT_ORDER: {sorted(unknown)}"


def test_an_account_is_named_by_its_code_without_its_holder():
    """THE NAME ANYONE BUT THE OWNER READS (decided 6 Oct 2026): one code per account, in the
    register's own order, and a label that carries no word of the holder's name. The two IG
    spread bets read alike once the holder comes off, so the code is what tells them apart."""
    from portfusion.engine import Book
    b = Book()
    codes, reg = b.account_codes(), b.account_register().set_index("account")
    assert list(codes["account"]) == b.account_order()
    assert list(codes["code"]) == [f"A{i}" for i in range(1, len(codes) + 1)], \
        "the codes are not A1 upwards in the register's order"
    for r in codes.itertuples(index=False):
        assert r.label.startswith(f"{r.code} · ")
        held = set(reg.loc[r.account, "holder_names"])
        assert held and not held & set(r.label.split()), f"{r.label!r} names its holder"
    assert codes["label"].is_unique


def test_every_account_has_a_dated_cash_reading(D):
    """The Accounts tab reads both; a mismatch drops an account off one side.

    store/cash-readings.csv is APPEND-ONLY — several readings per account over time — so
    the question is about the NEWEST reading per account, which is what the tab renders. A
    SPREAD-BET ACCOUNT'S CASH IS ITS FUNDS, on its own reading under IG's name (13 Oct 2026),
    and it has no row here.
    """
    latest = D.cash_latest()
    shares = {a for a in D.ACCOUNT_ORDER if D.ACCOUNT_KIND[a] != "spread bet"}
    assert set(latest) == shares, (
        f"cash-readings vs the share accounts: {set(latest) ^ shares}")
    for a in D.ACCOUNT_ORDER:
        if D.ACCOUNT_KIND[a] == "spread bet":
            r = next((x for x in D.ac_rows if x.acct == a), None)
            assert r is not None and r.funds is not None, f"{a}: no funds on its reading"


def test_a_cash_reading_names_an_evidence_class_that_exists(D):
    """A reading whose class is not in EVIDENCE_CLASSES has no stated authority and no
    reference shape — limbs 2 and 3 of statement-grade, which prose alone cannot enforce.

    New with the table. The literal carried its provenance as one free-text blob, so there
    was nothing to check: 'HL app, read 20 Aug' and 'ii statement of transactions' were the
    same kind of thing as far as any code could tell, though they sit on different rungs.
    """
    for o in D.cash_readings:
        assert o.evidence in D.EVIDENCE_BY_KEY, (
            f"{o.account} at {o.as_of} cites unknown evidence class {o.evidence!r}")
        assert o.reference.strip(), (
            f"{o.account} at {o.as_of} has no reference — nothing retrieves it a second time")


def test_an_account_reading_names_an_evidence_class_that_exists(D):
    """The same guard cash readings have, for account readings, which state their provenance
    too.

    IT MATTERS MORE HERE. A cash reading is a component; an ACCOUNT reading is the figure the
    whole reconciliation is judged against. Without the pair it could not say what it rested
    on at all — the flags had to colour the row from a different file, and nothing could bank
    an observation into the history, because a banked row needs a source and a quality.
    """
    for r in D.ac_rows:
        assert r.evidence in D.EVIDENCE_BY_KEY, (
            f"{r.acct} at {r.as_of} cites unknown evidence class {r.evidence!r}")
        assert r.reference.strip(), (
            f"{r.acct} at {r.as_of} has no reference — nothing retrieves it a second time")


def test_a_spread_bet_account_reconciles_against_an_official_class(D):
    """An IG account's reading rests on `ig-accounts`, and it has to be OFFICIAL for that to mean
    anything.

    IG issues no statement for an account that has not traded, so a spread-bet row can never
    reconcile against a document. Its authenticated /accounts read is the strongest thing
    obtainable and is what the account is actually worth — close the positions and that is
    the money. If somebody later demotes the class, this says what breaks.
    """
    for r in D.ac_rows:
        if D.ACCOUNT_KIND.get(r.acct) != "spread bet":
            continue
        ev = D.EVIDENCE_BY_KEY[r.evidence]
        assert ev.official, (
            f"{r.acct} reconciles against {ev.key}, which is not official — and no statement "
            f"is coming for an account that has not traded")
        assert ev.retrieval != "none", (
            f"{r.acct} rests on {ev.key}, which nothing retrieves")


def test_every_trade_date_is_a_date(D):
    """A trade's date is an ISO date, with no exceptions. Dates written in words were retired on
    12 Oct 2026 with the machinery that read them, so any other string is a mistyped date, which
    the engine would otherwise refuse to load."""
    bad = []
    for t in D.buys:
        try:
            _dt.date.fromisoformat(t[T_DATE])
        except (ValueError, TypeError):
            bad.append((t[T_ID], t[T_DATE]))
    assert not bad, f"trade dates that are not ISO dates: {bad}"


def test_no_trade_is_dated_in_the_future(D):
    """A fat-fingered year (2062 for 2026) would sail through an ISO parse."""
    today = _dt.date.today()
    future = [
        (t[T_ID], t[T_DATE])
        for t in D.buys
        if _dt.date.fromisoformat(t[T_DATE]) > today
    ]
    assert not future, f"trades dated in the future: {future}"


# =====================================================================================
# Prices and spread-bet contracts
# =====================================================================================

@pytest.mark.audit
@needs("current-prices")
def test_each_feed_shares_one_date(D):
    """
    ONE DATE PER MARKET, and every market within PRICE_SPREAD_LIMIT of the others.

    "Refresh the whole book or none of it." A price refreshed without its neighbours makes the
    book claim a freshness it does not have, and the Dashboard's freshness cell reads these
    dates, so it agrees. If this fails, ask "was a single price updated in isolation?" — the
    answer is usually yes. (A brand-new instrument's first mark, seeded from a confirming
    statement, is dated to the pinned date, so it does not appear here as a second date.)

    WHY NOT ONE DATE FOR THE WHOLE BOOK. It began as one and was widened three times, each
    the owner's call and each a real loosening, so the reasons are written down:

      · MARKETS KEEP THEIR OWN HOURS. A sweep strikes each line at its own instant: a market
        still trading gives a live read dated today, one not yet open gives its last session.
        Swept before New York opens, the US lines are yesterday's close while London's are
        today's, and back-dating either onto an instant it was not struck at would be
        fabrication: a true instant outranks a tidy single date. The contracts, read in one IG call,
        share an instant and are one group.
      · A WEEKLY CADENCE. Shares taken at Friday's close and contracts read on Monday are
        three days apart before anyone has done anything wrong, so the span is
        PRICE_SPREAD_LIMIT — one number, living beside PRICE_AGE_LIMIT, which the Legend
        quotes. It was once typed here as well, and this test caught the two disagreeing.
      · MARKET HOLIDAYS. On a US holiday the US lines come back at the session before — their
        last COMPLETE one — while the LSE and XETRA lines, whose markets traded, come back at
        the day itself. Both are right. So the shares group by CURRENCY, which is the market
        calendar for every line on file; ASKE-B.CO is DKK, priced in Copenhagen, and is a
        group of one.

    WHAT IS STILL GUARDED is most of the original force: every share within one market moves
    together, every contract moves together, and the whole book stays inside
    PRICE_SPREAD_LIMIT, so no group can drift off while another carries the book. The groups
    are DERIVED — contracts from LEG_CONTRACT, shares from the row's currency — so a market
    this book has never held joins the right group by existing.
    """
    contracts = set(D.LEG_CONTRACT.values())
    groups = defaultdict(set)
    for row in D.CURRENT_PRICES:
        # The contracts are one group whatever they are denominated in: IG serves a LIVE level
        # and every one of them is read in the same call, so they share an instant by
        # construction. The shares are grouped by currency, which is their market calendar.
        groups["contract" if row[0] in contracts else f"share ({row[2]})"].add(row[3])

    for name, dates in sorted(groups.items()):
        assert len(dates) == 1, (
            f"the {name} feed carries more than one date: {sorted(dates)} — was a single "
            f"price updated in isolation? A market holiday splits one CALENDAR from another, "
            f"never one line from its own market.")

    seen = sorted({d for ds in groups.values() for d in ds})
    span = (_date.fromisoformat(seen[-1]) - _date.fromisoformat(seen[0])).days
    assert span <= D.PRICE_SPREAD_LIMIT, (
        f"price feeds are {span} days apart ({seen}), past the "
        f"{D.PRICE_SPREAD_LIMIT}-day spread limit — one feed has been left behind; "
        f"refresh the whole book")


def test_price_dates_are_iso(D):
    bad = [(p[0], p[3]) for p in D.CURRENT_PRICES
           if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p[3]))]
    assert not bad, f"non-ISO price dates: {bad}"


def test_no_duplicate_price_instruments(D):
    """Two rows for one instrument: whichever the lookup hits first wins, silently."""
    dupes = [k for k, n in Counter(p[0] for p in D.CURRENT_PRICES).items() if n > 1]
    assert not dupes, f"duplicated instrument in CURRENT_PRICES: {dupes}"


def test_a_contract_is_named_only_on_a_spread_bet_leg(D):
    """Spread bets are priced by contract; shares are priced by ticker."""
    wrong = sorted(t[T_ID] for t in D.buys if t.contract and t.mode != "sb")
    assert not wrong, f"buys.csv names a contract on legs that are not spread bets: {wrong}"


@needs("buys")
def test_a_spread_bet_with_no_contract_is_refused_on_load(store_copy):
    """THE GAP FOUND ON 8 OCT 2026. A spread-bet leg with no contract was
    valued at nothing: on a scratch copy one new open HALV leg lowered net asset value by its whole
    entry notional, and nothing said so. The record now refuses it on load, which is also what
    stops the bench committing one."""
    import csv
    from portfusion.record import rules
    path = store_copy / "buys.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    leg = next(dict(r) for r in rows if r["contract"])
    leg.update(trade_id=free_id("buys"), contract="")
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n").writerow(leg)
    with pytest.raises(AssertionError, match="name no contract"):
        rules.reload_store()


@needs("buys")
@pytest.mark.parametrize("bet", [False, True])
def test_a_buy_whose_figure_is_in_the_other_kinds_column_is_refused_on_load(store_copy, bet):
    """`val` was one column a share and a bet both filled; split by kind (#43), a share's cost in
    the level column, or a bet's level in the cost one, would roll up as nothing."""
    import csv
    from portfusion.record import rules
    path = store_copy / "buys.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    leg = next(dict(r) for r in rows if bool(r["contract"]) == bet and r["cost"] != "0.0")
    leg.update(trade_id=free_id("buys"), cost=leg["level_points"], level_points=leg["cost"])
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n").writerow(leg)
    with pytest.raises(ValueError, match="a level and no cost" if bet else "a cost and no level"):
        rules.reload_store()


# =====================================================================================
# Funding interest is the contract's
# =====================================================================================

@needs("buys")
def test_a_funding_row_with_no_daily_funded_leg_on_its_nights_is_refused(store_copy):
    """IG charges funding on a daily funded bet, nightly, and on a dated bet never. A row charging
    nights on which the account held no daily leg is a row about nothing the book holds, and the
    load refuses it by name rather than letting it into the return."""
    import csv
    from portfusion.record import rules
    acct = next(a for a, k in rules.ACCOUNT_KIND.items() if k == "spread bet")
    path = store_copy / "income.csv"
    header = next(csv.reader(path.open(newline="", encoding="utf-8")))
    row = {h: "" for h in header}
    row.update(date="2026-01-06", account=acct, category="Funding interest",
               detail="Long Interest for US/Can shares 02/01/26 to 04/01/26", amount="-1.00",
               source="a test row", note="")
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=header, lineterminator="\n").writerow(row)
    with pytest.raises(ValueError, match="NO DAILY FUNDED LEG"):
        rules.reload_store()


@needs("buys")
def test_the_audit_names_a_night_a_daily_funded_leg_was_held_uncharged(store_copy):
    """The other direction: every night a daily leg was held has its row, or the audit says
    which night has none. Built on a copy by making one dated contract daily — by preference one
    whose account has no funding rows at all, since a night is charged per account — so its legs'
    nights have no rows; the gaps name that leg and nothing else."""
    import csv
    from portfusion.record import rules
    from portfusion import engine
    path = store_copy / "contracts.csv"
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    charged = {r.account for r in rules.ci_rows if r.category == "Funding interest"}
    account_of = {t.contract: t.acct for t in rules.buys if t.contract}
    candidates = [r for r in rows if r["funding"] == "dated" and r["contract"] in account_of]
    victim = next((r for r in candidates if account_of[r["contract"]] not in charged),
                  candidates[0])
    victim["funding"] = "daily"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    rules.reload_store()
    its_legs = {t.trade_id for t in rules.buys if t.contract == victim["contract"]}
    gaps = engine.Book().funding_gaps()
    named = {leg for _a, leg, _n in gaps}
    assert named and named <= its_legs, (named, its_legs)
    assert any("funding interest missing" in g for g in engine.Book().findings()["gaps"])


# =====================================================================================
# Research note links
# =====================================================================================

def test_research_note_tickers_resolve_to_something_held(D):
    """
    RESEARCH_NOTES is keyed by the security's code ("HALV SB", not "HALV"). A key in
    another form, or a typo, links the note to nothing, with no error anywhere.
    """
    display = {t[T_TICKER] for t in D.buys}
    unresolved = sorted(set(D.RESEARCH_NOTES) - display)
    assert not unresolved, (
        f"RESEARCH_NOTES keys match no ticker in the book: {unresolved} "
        f"(keys must be the DISPLAY form, e.g. 'HALV SB' not 'HALV')"
    )


# =====================================================================================
# Ledger classification
#
# A share sale is one sales.csv row, and the pool derives what it released. A trade row with a
# negative quantity would be summed as a BUY by every quantity and cost figure.
# =====================================================================================

T_QTY = 7


def test_a_record_that_does_not_begin_on_a_1_january_is_refused(store_copy):
    """The year's return is measured from the 31 December before it, so a record beginning on any
    other day is refused on load, rather than as a KeyError on the first page asking for a return."""
    from portfusion.record import rules
    path = store_copy / "settings.csv"
    begins = rules.SETTINGS["record_begins"]
    text = path.read_text()
    assert text.count(f"record_begins,{begins}") == 1
    path.write_text(text.replace(f"record_begins,{begins}", f"record_begins,{begins[:4]}-04-01"))
    with pytest.raises(ValueError, match="must begin on a 1 January"):
        rules.reload_store()


def test_a_negative_quantity_carries_no_value(D):
    """A share consolidation changes the count and not the cost, so it is the one kind of trade row
    with a negative quantity, and it carries no value. A negative row WITH a value is a sale written
    the old way: it would rebuild cleanly and be counted as a buy."""
    bad = [(t[T_ID], t[T_QTY], t.cost) for t in D.buys
           if t[T_QTY] is not None and t[T_QTY] < 0 and t.cost != 0]
    assert not bad, (f"negative-quantity trades carrying a value — a sale is one sales.csv row, "
                     f"not a negative trade: {bad}")


# =====================================================================================
# Per-leg sourced figures
# =====================================================================================

T_MODE = 11


def test_a_brokers_rate_stands_beside_a_foreign_price(D):
    """A rate means nothing without the price it converted, and a price stated in sterling
    needed none. The load refuses both (`rules._misstated`); this names the rows if it ever
    stops."""
    bad = sorted(i for i, cur, price, rate in
                 [(t.trade_id, t.cur, t.traded_price, t.rate) for t in D.buys]
                 + [(e.sale_id, e.cur, e.traded_price, e.rate) for e in D.sales]
                 if rate is not None and (price is None or cur == "GBP"))
    assert not bad, f"a rate beside no foreign price: {bad}"


def test_every_stated_price_and_rate_is_a_positive_number(D):
    """A deal's price and its broker's rate are figures off a document: positive, or blank."""
    bad = [(i, f, v) for i, price, rate in
           [(t.trade_id, t.traded_price, t.rate) for t in D.buys]
           + [(e.sale_id, e.traded_price, e.rate) for e in D.sales]
           for f, v in (("price", price), ("rate", rate))
           if v is not None and not (isinstance(v, (int, float)) and v > 0)]
    assert not bad, f"a stated price or rate that is not a positive number: {bad}"


def test_exit_leg_match_joins_real_rows(D):
    """
    A leg-exact match names an exit and the buy leg it closed. Either side
    pointing at nothing means the cost released falls back to pool apportionment
    silently, on a parcel where a statement actually names the leg.
    """
    exit_ids = {e[0] for e in D.sales}
    buy_ids = {t[T_ID] for t in D.buys}
    bad = []
    for eid, tid in D.EXIT_LEG_MATCH.items():
        if eid not in exit_ids:
            bad.append((eid, tid, "exit id not in exits"))
        if tid not in buy_ids:
            bad.append((eid, tid, "buy id not in trades"))
    assert not bad, f"EXIT_LEG_MATCH does not join: {bad}"


# =====================================================================================
# The record's shape is declared, not described
#
# A field-name comment once listed SEVENTEEN names for an EIGHTEEN-field tuple and claimed 118
# rows against a real 102. A declaration cannot drift like that, but these pin the properties
# a declaration alone does not.
# =====================================================================================

@needs("buys")
def test_the_record_exports_named_rows_not_bare_tuples(D):
    """
    Bare tuples are what the wrong field comment was documenting. If a container
    reverts to plain tuples, every `.ticker` in the build becomes an AttributeError
    at best — and a silent positional misread if someone "fixes" it back to indexes.
    """
    expected = {
        "buys": "Buy", "sales": "Sale", "reasoning": "Reasoning",
        "realisations": "RealisationRow", "ci_rows": "CostIncomeRow", "ac_rows": "AccountRow",
    }
    wrong = []
    for attr, cls in expected.items():
        rows = getattr(D, attr)
        assert rows, f"{attr} is empty"
        for r in rows:
            if type(r).__name__ != cls:
                wrong.append((attr, type(r).__name__))
                break
    assert not wrong, f"containers no longer carrying their declared row type: {wrong}"


@needs("buys")
def test_whether_a_leg_is_still_held_comes_from_the_sales(D, book):
    """A leg's `status` was once a column the engine read, and then a column nothing read; it is
    retired. Which legs are still held comes from the sales alone: a leg an IG close names is not
    held, and neither is any leg of a ticker no account holds any more."""
    buys = book.ledger[book.ledger["direction"] == "Buy"].set_index("event_id")
    named = sorted({e.closes for e in D.sales if e.closes})
    assert named and not buys.loc[named, "open_leg"].any(), "a leg a sale closed still reads as held"
    held = set(book.holdings(by="ticker")["ticker"])
    gone = buys[~buys["ticker"].isin(held)]
    assert len(gone) and not gone["open_leg"].any(), "a leg of a ticker nobody holds reads as held"


def test_dead_cash_slot_on_account_rows_stays_dead(D):
    """
    ac_rows' third field is a retired cash slot; cash lives in store/cash-readings.csv so
    that a balance carries its own date and source. The build asserts it is None. A value
    reappearing here is cash with no date — the exact defect that move fixed.
    """
    live = [(r.acct, r.cash_retired) for r in D.ac_rows if r.cash_retired is not None]
    assert not live, f"the retired cash slot has been written to: {live}"


# =====================================================================================
# No silent gaps — a missing row must stop the build, not degrade quietly
# =====================================================================================

def test_every_traded_ticker_has_an_identity_row(D):
    """
    REGRESSION-BY-DISCOVERY, found while mis-aiming a mutation at CURRENT_PRICES and hitting
    SECURITIES instead — which turned out to be the more interesting result.

    Sector, region and exposure are all built from SECURITIES. Deleting one identity row once
    failed nothing: sector and region silently took a default wherever they were shown, and the
    report's issuer table lost the company name and shifted every row below it. Today
    `Book.holdings()` refuses a held code with no identity row; this names every traded one, held
    or closed, without a build.

    That is the "plausible, rebuilds cleanly, passes every check, and is wrong" pattern this
    suite exists for — the same shape as the Halvard sub-row miss. A ticker in the
    ledger with no identity row is a gap, not a default.
    """
    sec_codes = {r[0] for r in D.SECURITIES}
    traded = {t.ticker for t in D.buys} | {e.ticker for e in D.sales}
    missing = sorted(traded - sec_codes)
    assert not missing, (
        f"tickers in the ledger with no SECURITIES row: {missing} — every traded code needs "
        "one for its company, sector and region"
    )


def test_every_open_share_has_a_price_route(D):
    """
    The build stops too — `engine.value_legs()` raises on the first missing mark — but this needs no
    build and names every offender at once.

    Spread bets are excluded on purpose: they are priced by CONTRACT via LEG_CONTRACT,
    not by ticker, which is a different route with its own guards.
    """
    priced = {r[0] for r in D.CURRENT_PRICES} | set(D.STATEMENT_PRICED)
    sold = {e.ticker for e in D.sales}
    open_shares = {t.ticker for t in D.buys if t.mode != "sb"}
    missing = sorted(open_shares - priced - sold)
    assert not missing, (
        f"open share holdings with no sourced price and no STATEMENT_PRICED entry: {missing}"
    )


# =====================================================================================
# THE IMPLIED DEALING COST ON A SALE  (the owner)
#
# `price` is the EXECUTION price and `proceeds` is NET, so the gap between them is the
# dealing cost. NOTHING STORES THAT COST, and after an audit that is deliberate: a buy
# commission is part of the cost basis and a sell commission reduces proceeds, so both
# are already counted, in the right place, exactly once. Recording either again in
# income.csv double-counts it — which was once done, and caught.
#
# WHAT THIS TEST IS FOR is the other half. The gap is not stored, so nothing checks that
# it is SANE — and a mis-keyed price or proceeds shows up nowhere else in the book. A
# 10x price slip would sail through every page, which shows what the engine computed, and
# through the engine, which recomputes exit price as proceeds/quantity
# and would simply report the wrong number consistently.
#
# THE BOUNDS, and why they are not symmetric:
#
#   lower   -(qty x 5e-6 + 0.005). `price` is stored to five decimals, so a rounded
#           price times a large quantity can land the gap slightly NEGATIVE without
#           anything being wrong: -£0.01 on 2,000 shares is inside its own £0.015
#           allowance. A cost cannot really be negative; this is the arithmetic
#           of the stored precision, and the tolerance says so in the only honest way —
#           scaled by the quantity that caused it.
#
#   upper   2% of proceeds. Typical dealing costs are a few pounds flat, which is
#           a fraction of a percent on most rows. Two percent is far above
#           anything genuine and far below a transposed digit.
#
# A SPREAD-BET EXIT MUST LAND ON EXACTLY ZERO. A closing level is at parity and carries
# no commission, so any gap there is an error by definition — the tolerance still
# applies, but nothing has ever needed it.
# =====================================================================================

def _implausible_dealing_cost(qty, price, proceeds, rate=None):
    """The complaint, or None. A function and not an inline loop so the guard can be
    fired at a row the record does not contain — see the fat-finger test below. A price in
    another currency comes to sterling at `rate`, whose own five places it may be off by."""
    price = price if rate is None else price / rate
    implied = round(qty * price - proceeds, 2)
    lower = -(qty * 5e-6 + 0.005)                # the stored price's own rounding
    if rate is not None:
        lower -= abs(qty * price) * 5e-6 / rate  # and the stated rate's
    # TWO PER CENT, AND ONE FIXED DEALING CHARGE: a small sale's commission is a flat fee, which
    # can be more than 2% of the sale on its own; £12.50 covers a broker's flat charge.
    upper = 0.02 * abs(proceeds) + 12.50
    if lower <= implied <= upper:
        return None
    return (f"{qty} x {price} = {qty * price:,.2f} against proceeds {proceeds:,.2f} "
            f"implies a dealing cost of {implied:,.2f}, outside "
            f"[{lower:,.3f}, {upper:,.2f}]")


def test_the_implied_dealing_cost_on_every_sale_is_plausible(D):
    """price x qty - proceeds is the dealing cost. It is never stored, so this is the
    only thing standing between a mis-keyed sell row and a wrong realised gain. A price in the
    share's own currency comes to sterling at the broker's rate beside it."""
    bad = [f"{e.sale_id} {e.ticker}: {msg}" for e in D.sales
           if (e.cur == "GBP" or e.rate)
           and (msg := _implausible_dealing_cost(
               e.size, e.traded_price, e.proceeds, None if e.cur == "GBP" else e.rate))]
    assert not bad, (
        "implausible dealing cost implied by a sell row — check the price and the "
        "proceeds against the contract note:\n  " + "\n  ".join(bad))


def test_the_implied_dealing_cost_on_every_priced_buy_is_plausible(D):
    """THE SAME GUARD, FACING THE OTHER WAY: a buy settles price x qty PLUS its costs, so the
    sterling paid less the price's worth is the commission, stamp duty and any FX charge. Every
    price on a buy is a document's, so a mis-keyed one shows here."""
    bad = [f"{t.trade_id} {t.ticker}: {msg}" for t in D.buys
           if t.traded_price is not None and t.qty and (t.cur == "GBP" or t.rate)
           and (msg := _implausible_dealing_cost(
               t.qty, -t.traded_price, -t.cost, None if t.cur == "GBP" else t.rate))]
    assert not bad, (
        "implausible dealing cost implied by a priced buy — check the price and the sterling "
        "paid against the document:\n  " + "\n  ".join(bad))


def test_the_dealing_cost_guard_actually_catches_a_fat_finger(D):
    """A GUARD THAT HAS NEVER FIRED CANNOT SHOW YOU IT STILL WORKS. A cap in this record was
    once wired to nothing for a whole session and printed the same reassuring "0 in scope"
    throughout; firing the guard at rows built to fail is what proves it is connected.

    Three slips the record could really make, on a sale of 1,200 @ 0.8043, proceeds 960.16:
    """
    # a decimal point in the wrong place on the price
    assert _implausible_dealing_cost(1200, 8.043, 960.16)
    # proceeds keyed from the GROSS line of the note instead of the TOTAL
    assert _implausible_dealing_cost(1200, 0.8043, 700.00)
    # a sign or a swap that makes the sale look like it cost money to make
    assert _implausible_dealing_cost(1200, 0.8043, 1100.00)
    # and a correct row must still pass, or the bounds are merely strict
    assert _implausible_dealing_cost(1200, 0.8043, 960.16) is None


def test_a_spread_bet_sale_implies_no_dealing_cost(D):
    """A closing LEVEL is at parity and carries no commission, so proceeds must be
    exactly stake x level. Any gap is an error, not a fee."""
    off = [(e.sale_id, round(e.stake * e.traded_price - e.proceeds, 2))
           for e in D.sales if " SB" in e.ticker
           and abs(e.stake * e.traded_price - e.proceeds) > 0.005]
    assert not off, f"spread-bet exits implying a dealing cost: {off}"


# =====================================================================================
# THE RULES ARE STATED ONCE  (the owner)
#
# The source hierarchy was once written out in FOUR places — CLAUDE.md, this module's header,
# the Legend tab, and an architecture document — and they had already drifted: two said
# "broker platform" and two said "broker platform or app", in a rule whose entire job is
# deciding which source wins when two disagree.
#
# That is the leverage defect applied to prose. Leverage stood wrong in two documents for
# three weeks because it was DERIVED and restated; a rule restated four times is the same
# failure with no arithmetic to catch it.
#
# One copy, in rules. The Method page renders it.
# =====================================================================================

def _flat(text):
    """The WORDS, not the formatting.

    Whitespace-insensitive so markdown line wrapping is not a false failure, and emphasis
    is stripped so a guide may bold a phrase without breaking the comparison. It
    did: a guide rendered "**Statement-grade means three things...**" and the first version
    of this test read that as a drift.
    """
    import re
    return " ".join(re.sub(r"[*`]", "", str(text)).split())


def test_no_file_writes_out_a_rule_the_record_states_once(repo_root, project_files):
    """THE SOURCE HIERARCHY, THE ARCHIVE CONVENTION AND STATEMENT GRADE are each stated once, in
    `record/rules.py`, and the Method page renders them. A file may NAME one and point at it;
    writing it out is a second copy, and the second copy is the one that goes stale: four
    tellings of the hierarchy had drifted apart, and five of the archive convention were stale
    in all five.

    Each rule is found by the part nobody can restate it without: the hierarchy's first rungs,
    the convention's date token, and any eight words in a row of statement grade, taken from the
    constant so a rewording needs no list edited. Every directory is read: a guard globbing the
    root alone is how the store's guide carried a whole second hierarchy for weeks.
    """
    import re
    from harness import app_name
    from portfusion.record import rules as D

    def words(text):
        return re.sub(r"[^a-z0-9 ]", " ", _flat(text).lower()).split()

    grade = words(D.STATEMENT_GRADE)
    grade_runs = {" ".join(grade[i:i + 8]) for i in range(len(grade) - 7)}
    offenders = []
    for path in project_files(".md", ".py", ".js", ".css"):
        rel = app_name(path)
        if rel in ("record/rules.py", "tests/test_record.py"):
            continue
        text = path.read_text()
        if re.search(r"contract note\s*/\s*statement\s*[>/]", _flat(text)):
            offenders.append(f"{rel}: the source hierarchy, not rules.SOURCE_HIERARCHY")
        offenders += [f"{rel}:{n}: the archive convention, not rules.ARCHIVE_CONVENTION"
                      for n, line in enumerate(text.splitlines(), 1) if re.search(r"DD\s+Mon\s+YYYY", line)]
        hit = next((r for r in grade_runs if r in " ".join(words(text))), None)
        if hit:
            offenders.append(f"{rel}: statement grade ({hit!r}), not rules.STATEMENT_GRADE")
    assert not offenders, "these write a rule out instead of pointing at it:\n  " + "\n  ".join(offenders)


#: THE CODE'S OWN PROSE, HELD TO ONE TELLING: the comments and docstrings in `.py`, where a
#: sentence written twice turns up — a test's docstring restating its module's, a comment
#: repeating the docstring below it. This counts every copy, beyond the first, of an eight-word run of comment or docstring prose. It
#: measures repetition, not length: a long docstring that says a thing once adds nothing.
#:
#: A HIGH-WATER MARK, in the shape `test_evidence.py:_UNCLASSIFIED_HIGH_WATER` uses, taken after
#: the prose passes so it holds their cuts. Cutting can never fail it; writing a sentence a
#: second time can.
REPEATED_PROSE_HIGH_WATER = 2026


def _prose_blocks(src):
    """(line, text) for every docstring, and for every run of comments on consecutive lines."""
    import ast
    import io
    import tokenize
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=True)
            if doc:
                out.append((node.body[0].lineno, doc))
    start, lines, last = None, [], None
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            continue
        if last is None or tok.start[0] != last + 1:
            if lines:
                out.append((start, " ".join(lines)))
            start, lines = tok.start[0], []
        lines.append(tok.string)
        last = tok.start[0]
    if lines:
        out.append((start, " ".join(lines)))
    return out


def _prose_runs(src):
    """{eight-word run: lines of the prose blocks holding it}, for one file's source."""
    runs = defaultdict(set)
    for line, text in _prose_blocks(src):
        words = re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
        for i in range(len(words) - 7):
            runs[" ".join(words[i:i + 8])].add(line)
    return runs


def test_the_code_repeats_itself_no_more_than_it_did(repo_root, project_files):
    """A SENTENCE WRITTEN TWICE is two sentences to keep true, and the prose passes found the
    second copy was usually the stale one. The unit is eight words, and every copy beyond the
    first counts, so a third telling costs what the second did.

    If this fires, the failure names the runs each uncommitted file has gained since the last
    commit, which is where the new copy is. Keep the telling where the thing is done and point
    at it from the other place. Rewording to get under the mark leaves two copies still.
    """
    import subprocess
    where = defaultdict(set)
    for path in project_files(".py"):
        rel = path.relative_to(repo_root).as_posix()
        for run, lines in _prose_runs(path.read_text(encoding="utf-8")).items():
            where[run] |= {(rel, n) for n in lines}
    shared = {run: places for run, places in where.items() if len(places) > 1}
    copies = sum(len(places) - 1 for places in shared.values())

    gained = []
    if copies > REPEATED_PROSE_HIGH_WATER:
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root,
                                capture_output=True, text=True).stdout.splitlines()
        for rel in sorted({entry[3:].split(" -> ")[-1] for entry in status}):
            if not rel.endswith(".py") or not (repo_root / rel).is_file():
                continue
            head = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=repo_root,
                                  capture_output=True, text=True)
            had = _prose_runs(head.stdout) if head.returncode == 0 else {}
            now = _prose_runs((repo_root / rel).read_text(encoding="utf-8"))
            gained += [f"{run!r} at " + ", ".join(f"{f}:{n}" for f, n in sorted(shared[run]))
                       for run, lines in sorted(now.items())
                       if run in shared and len(lines) > len(had.get(run, ()))]
    assert copies <= REPEATED_PROSE_HIGH_WATER, (
        f"comment and docstring prose repeats {copies} eight-word runs beyond their first "
        f"telling, above the {REPEATED_PROSE_HIGH_WATER} on file. Gained since the last commit:\n  "
        + ("\n  ".join(gained[:20]) or "(nothing uncommitted — the rise is in committed work)"))


#: Things a guide names that are not in the tree, each on purpose. Anything else a guide points
#: at must be there, or be a path git ignores, which names a local thing deliberately.
NAMED_ON_PURPOSE = {
    ".git/": "git's own folder, which it never lists",
    "bin/activate": "inside the venv, which git never lists",
}


def _guide_pointers(text):
    """(line, pointer) for every path a guide names in code or as a link target.

    A fenced block is blanked line for line so the numbers stay true. A span holding a space is a
    command and one holding `*` or `<` a pattern; a bare extension names a kind of file, not one."""
    text = re.sub(r"```.*?```", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for code, link in re.findall(r"`([^`\n]+)`|\]\(([^)\s]+)\)", line):
            t = (code or link).strip()
            if re.search(r"[\s*<]", t) or t.startswith(("~", "/", ":", "#", "http")):
                continue
            path = re.split(r":+", t, maxsplit=1)[0]
            if re.fullmatch(r"\.\w+", path):
                continue
            if (re.search(r"\.(py|md|csv|json|css|js|html|ini|txt|xlsx)$", path)
                    or ("/" in path and re.fullmatch(r"[\w./-]+", path))):
                out.append((n, t))
    return out


def test_every_pointer_in_a_guide_leads_somewhere(repo_root, project_files):
    """A POINTER THAT LEADS NOWHERE sends its reader nowhere and tells nobody.

    The guides point rather than restate, so a pointer is most of what one holds, and it goes stale
    when the thing it names moves. A guide once sent its reader to a folder that had been
    renamed, and nothing saw it: the guide tests read words, not
    where they lead. A path must name a listed file or folder (from the root, from the guide's
    own folder, or by a tail only one path has, or only the path nearest the root has) or one
    git ignores; after `:` or `::`, the name must be in that file. Code points at guides too, so
    a `.py` file naming a CLAUDE.md is held to the same.
    """
    import subprocess
    # Every listed file whatever its suffix, by project_files' own git call, which filters by one.
    listed = [p for p in subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root, capture_output=True, text=True, check=True).stdout.split("\0")
        if p and (repo_root / p).is_file()]
    known = set(listed) | {"/".join(p.split("/")[:i]) for p in listed for i in range(1, p.count("/") + 1)}

    def find(path, here):
        for c in (path, f"{here}/{path}" if here != "." else path):
            if c in known:
                return c
        # A tail only one path has; or, where a book repeats a name (the demo's demo/store/ beside
        # store/), the one path nearer the root than every other. A tie still leads nowhere.
        tails = sorted((k for k in known if k.endswith("/" + path)), key=lambda k: k.count("/"))
        if len(tails) == 1 or (tails and tails[0].count("/") < tails[1].count("/")):
            return tails[0]
        return None

    def ignored(path, here):
        return any(subprocess.run(["git", "check-ignore", "-q", c], cwd=repo_root).returncode == 0
                   for c in (path, f"{here}/{path}"))

    broken = []
    for guide in project_files(".md"):
        rel = guide.relative_to(repo_root).as_posix()
        here = guide.parent.relative_to(repo_root).as_posix()
        for n, pointer in _guide_pointers(guide.read_text(encoding="utf-8")):
            if pointer in NAMED_ON_PURPOSE:
                continue
            given, _, name = re.match(r"([^:]+)(:+)?(.*)", pointer).groups()
            path = given.rstrip("/")
            found = find(path, here)
            if not found and "." in path.rsplit("/", 1)[-1]:      # module.ATTRIBUTE
                module, name = path.rsplit(".", 1)
                found = find(module + ".py", here)
            if not found:
                # As written: a pattern ending in `/` ignores only a folder, and says so by the slash.
                if not ignored(given, here):
                    broken.append(f"{rel}:{n}: {pointer} — no such file or folder")
                continue
            name = name.split("(")[0]
            if name and not name.isdigit() and (repo_root / found).is_file() and not re.search(
                    rf"\b{re.escape(name)}\b", (repo_root / found).read_text(encoding="utf-8")):
                broken.append(f"{rel}:{n}: {pointer} — {found} has no {name}")
    for source in project_files(".py"):
        for n, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            for guide in re.findall(r"[\w./-]*CLAUDE\.md", line):
                if guide.lstrip("./") not in known:
                    broken.append(f"{source.relative_to(repo_root).as_posix()}:{n}: {guide}")
    assert not broken, "these pointers lead nowhere:\n  " + "\n  ".join(broken)


def test_the_evidence_list_is_in_the_order_the_owner_gave(D):
    """THE ORDER IS THE FEATURE, not an accident of when each class was added (the owner).

    The two brokers that send documents first, each with its kinds running strongest to
    weakest, then IG which has an API and needs neither. Reading down the list is reading down
    the source hierarchy, so the strongest thing you have is the first thing you meet in the
    dropdown — which is the whole reason the owner specified an order rather than a set.

    Pinned because a list has no opinion about its own sequence: the next class added would
    land at the end, quietly putting an IG API read above it.

    WITHIN A BROKER, THE ORDER IS THE RETRIEVAL HIERARCHY, and `not-on-file`, which nothing
    retrieves, comes last of all.
    """
    # "IG account read" is the /accounts BALANCE read, not the /history/activity read beside it;
    # a balance read has no dealId to be its reference.
    # HL exports THREE reports all titled "Portfolio Summary" — a valuation, a transaction list
    # and a totals line — so one class could not name them. `hl-valuation` is OFFICIAL on the
    # ig-accounts argument: it carries the total, the cash, every holding with cost and the FX
    # rates, and no HL statement will ever be dated at a quarter end.
    # "ii valuation (holdings export)" holds the seat hl-valuation holds for HL: below the
    # statement, above the transaction list. ii issues nothing else that states the marks on
    # demand. It carries no cash, which `covers` says — see `reconciles_an_account()`.
    assert [e.label for e in D.EVIDENCE_CLASSES] == [
        "ii contract note", "ii statement", "ii valuation (holdings export)",
        "ii transaction history",
        "HL statement", "HL valuation (Account Summary download)",
        "HL income transactions",
        "HL transaction list (Portfolio Summary download)",
        "HL account totals (Portfolio Summary download)", "HL security movements",
        "IG statement", "IG API read", "IG account read",
        "Not on file",
    ]

    # The order is not just a list somebody agreed once: within each broker it must run
    # strongest to weakest, which is the hierarchy `retrieval` states. IG's three classes
    # carry all three strong retrieval kinds: statement (document), activity (api — a stored
    # dealId returns the same answer for ever), balance (reading — the endpoint answers again,
    # with a different number). That is a real hierarchy, and it is asserted.
    rank = {"document": 0, "none": 2, "api": 0, "reading": 1}
    for broker in ("ii-", "hl-", "ig-"):
        ranks = [rank[e.retrieval] for e in D.EVIDENCE_CLASSES if e.key.startswith(broker)]
        assert ranks == sorted(ranks), (
            f"{broker} classes are out of retrieval order: "
            f"{[(e.key, e.retrieval) for e in D.EVIDENCE_CLASSES if e.key.startswith(broker)]}")


def test_a_class_nothing_retrieves_is_never_marked_official(D):
    """Limb 3 of statement-grade asks for something that retrieves the figure a second time. A
    class with retrieval `none` can never be dressed as the official document a period is
    reconciled against."""
    for e in D.EVIDENCE_CLASSES:
        if e.retrieval == "none":
            assert e.official is False, f"{e.key} is marked official"


# =====================================================================================
# THE DERIVED GLOSSARY
# =====================================================================================

def _glossary():
    """tools/glossary.py, loaded from its file: a tool beside the app, not a module of it."""
    import importlib.util
    from harness import ROOT
    spec = importlib.util.spec_from_file_location("glossary", ROOT / "tools" / "glossary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_generated_half_of_the_glossary_matches_the_constants(repo_root):
    """docs/glossary.md's §9 is GENERATED, and this is what makes that worth anything.

    THE GLOSSARY EXISTS BECAUSE OF DRIFT, and a document recording what the words are,
    maintained by hand, drifts exactly the way the words did — one file along. So the half with
    a code home is emitted from `record/rules.py`, `record/schema.py` and `Book.HEADLINE`, and
    the checked-in file is compared against what those constants produce right now.

    IF THIS FAILS, THE DOCUMENT IS STALE AND THE CODE IS RIGHT — which is the rule stated at
    the foot of the glossary itself. Run `python3 tools/glossary.py --write` and commit the result;
    read the diff, because it is telling you a vocabulary moved.

    THE MARKERS ARE PART OF THE CONTRACT. A glossary that has lost them is one where the
    generated block has been pasted in by hand, and that is the drift arriving by another route.
    """
    glossary = _glossary()
    text = (repo_root / "docs" / "glossary.md").read_text(encoding="utf-8")
    assert glossary.BEGIN in text and glossary.END in text, (
        "docs/glossary.md has lost its generated-block markers. §9 is emitted by glossary.py; "
        "without them nothing can tell the derived half from the hand-written one.")

    on_file = glossary.BEGIN + text.split(glossary.BEGIN, 1)[1].split(glossary.END, 1)[0] \
        + glossary.END
    fresh = glossary.generate().rstrip("\n")
    assert on_file == fresh, (
        "docs/glossary.md's generated section no longer matches the constants it is derived "
        "from. The CODE is right and the document is a defect — run `python3 tools/glossary.py "
        "--write`, then read the diff: a vocabulary has moved.")


def test_the_generated_glossary_indexes_rather_than_redefines(repo_root):
    """IT MAY LIST WORDS; IT MAY NOT DEFINE THEM, and that is a hard constraint rather than a
    style note.

    `test_record.py` already refuses a second telling of SOURCE_HIERARCHY and STATEMENT_GRADE
    in any file — because a rule stated twice drifts, which this whole document exists to stop
    (the spread-bet guard was retired on 13 Oct 2026 so its vocabulary could change, and the
    glossary still may not define it). That guard is right, and it is
    precisely the guard a generated glossary would trip the moment somebody emitted a
    definition into it. This says so out loud rather than leaving the next author to discover
    it by a failing test three files away.
    """
    glossary = _glossary()
    from portfusion.record import rules as D
    block = glossary.generate()
    for name, value in (("SPREAD_BET", D.SPREAD_BET),
                        ("STATEMENT_GRADE", D.STATEMENT_GRADE),
                        ("SOURCE_HIERARCHY", D.SOURCE_HIERARCHY)):
        opening = " ".join(str(value).split())[:40]
        assert opening not in " ".join(block.split()), (
            f"the generated glossary is emitting {name}'s text. It is an INDEX — names, values "
            f"and where they live. What a word MEANS stays where it is defined, and this book "
            f"asserts that place is exactly one.")


def test_every_history_permits_only_qualities_the_schema_declares():
    """ONE PROVENANCE VOCABULARY, and three files that each permit a subset.

    `reconstructed` was a fourth word for `derived` and lived only in `history/accounts.py`'s own
    tuple — so the same fact wore two labels in two files: a spread bet's carried-back 31 Dec figure
    read `derived` in quarter-nav.csv, where a test demanded it, and `sourced` in
    account-statements.csv, where nothing did.

    A SUBSET IS LEGITIMATE and a NEW WORD IS NOT. A reading is never `superseded` — it is
    replaced by a later reading at a later date — so accounts declares three of the four. What
    this refuses is a fifth word arriving in one file and nowhere else, which is how the last one
    got in.
    """
    from portfusion.record import schema
    from portfusion.history import accounts as AH
    from portfusion.history import fx as FH
    from portfusion.history import prices as PH
    for name, permitted in (("history/accounts.py", AH.QUALITIES),
                            ("history/fx.py", FH.QUALITIES),
                            ("history/prices.py", PH.QUALITIES)):
        stray = set(permitted) - set(schema.QUALITIES)
        assert not stray, (
            f"{name} permits {sorted(stray)}, which schema.QUALITIES does not declare. "
            f"A vocabulary that grows in one file is not a vocabulary.")


# =====================================================================================
# WHAT A LINE OF A BROKER'S TRANSACTION LIST IS
# =====================================================================================

def test_every_hl_code_seen_on_a_real_export_classifies(D):
    """The codes HL's exports use — the income list and both Portfolio Summary transaction
    lists. Unrecognised is a real answer from `hl_code()` and
    must stay one, so this pins the codes we have actually met rather than a pattern.
    """
    expected = {
        "OVR CR":     ("income", "Dividend"),
        "MANAGE FEE": ("income", "Fee"),
        "INTEREST":   ("income", "Cash interest"),
        "B000000011": ("buys", ""),
        "B000000012": ("buys", ""),
        "S000000013": ("sales", ""),
        "S000000014": ("sales", ""),
        "DRI0000001": (None, ""),
        "DRI0000002": (None, ""),
    }
    for code, (table, category) in expected.items():
        got = D.hl_code(code)
        assert got is not None, f"{code} is no longer recognised"
        assert (got.table, got.category) == (table, category), f"{code} -> {got}"


def test_an_unknown_code_is_not_guessed_at(D):
    """A code this map has not seen is a line nobody has decided about yet, and deciding by
    pattern is how a fee becomes a dividend."""
    assert D.hl_code("MYSTERY") is None
    assert D.hl_code("") is None


def test_a_transfer_between_sub_accounts_belongs_to_no_table(D):
    """IT CHANGES NO FIGURE THIS BOOK HOLDS. An HL ISA has a Capital and an Income sub-account,
    and a dividend moved between them appears on BOTH transaction lists under one reference,
    once negative and once positive — so entering it from both sides books it twice.

    Verified on a dividend re-investment: the amount out of Income and into Capital, then a
    purchase the book already holds with HL's own reference. Both ends are recorded; the
    movement between them is plumbing.
    """
    code = D.hl_code("DRI0000001")
    assert code.table is None, f"a sub-account transfer would become a {code.table} row"
    assert "not an event" in code.why, "the reason is not stated on the code"


def test_every_income_code_names_a_category_the_record_knows(D):
    """`income.category` is what decides whether a figure reaches the return — POSITION_INCOME
    does, ACCOUNT_INCOME does not. A category outside both would load and then be counted by
    neither half."""
    known = set(D.POSITION_INCOME) | set(D.ACCOUNT_INCOME)
    for code, entry in D.HL_CODES.items():
        if entry.table == "income":
            assert entry.category in known, \
                f"{code} maps to category {entry.category!r}, which is in neither income list"


def test_an_account_has_exactly_one_observation_row(D):
    """`account-readings.csv` holds the CURRENT observation per account, and a second row
    for one account is silently ignored rather than preferred.

    `Book.reconciliation()` reads it with `next(x for x in D.ac_rows if x.acct == a)` — the
    FIRST match, not the newest — so an appended row sits in the file changing nothing while
    the reconciliation goes on quoting the older one. That is how an account could go on reading
    out against an old anchor after a newer baseline had been written.

    THE TABLE'S ROUTE IS `replace`, not `append`, and the journal has always said so. This is
    the check that makes the convention hold on its own: `cash-readings.csv` is the
    append-only one and it has `cash_latest()` to pick by date, which this table does not need
    because it never has two rows to choose between.
    """
    seen = [r.acct for r in D.ac_rows]
    twice = sorted({a for a in seen if seen.count(a) > 1})
    assert not twice, (
        f"these accounts have more than one observation row: {twice}. The table is replaced, "
        f"not appended — the superseded figure is already banked in account-statements.csv, "
        f"which is the append-only history and the place a past observation lives.")


# =====================================================================================
# A CONVERSION IS DATA, NOT PROSE
#
# income.csv's `amount` is always GBP. Where the money arrived in another currency the
# conversion was once recorded inside `detail`, in words:
#
#     "Gross interest to 24/01/25: EUR 0.50 (GBP at 14 Jan rate 1.20000)"
#
# Every part of that is a fact the record knows how to hold, and in prose no guard could
# reach any of it — the rate sat in a free-text column nothing reads, and every check agreed.
# =====================================================================================

def test_a_converted_row_carries_its_currency_and_amount_or_neither(D):
    """`currency` and `local_amount` travel together, and a `rate` only with them. Half a
    conversion is a row that cannot be checked and cannot be redone."""
    bad = [(r.date, r.account, r.detail)
           for r in D.ci_rows
           if bool(r.currency) != (r.local_amount is not None)
           or (r.rate is not None and not r.currency)]
    assert not bad, (
        f"these income rows carry part of a conversion: {bad}\n"
        f"  A conversion is currency + local_amount, with the broker's rate where it states one.")


def test_every_converted_row_has_a_rate(D):
    """A foreign row converts at its broker's rate or at a close on fx-history.csv
    (`Book.conversions()`). One with neither is a figure nobody can redo."""
    from portfusion.engine import Book
    conv = Book().conversions()
    bad = conv[conv["rate"].isna()] if not conv.empty else conv
    assert bad.empty, (f"these income rows have neither the broker's rate nor a close on "
                       f"file: {list(zip(bad['date'].astype(str), bad['account']))}")


def test_the_converted_figure_is_what_the_rate_produces(D):
    """THE ARITHMETIC, which prose could never be held to.

    `amount` is GBP and `local_amount` is what the broker paid. One divided by the rate must
    be the other, to the penny the record rounds to. This is the check the 38p row never had:
    both halves of it were sourced and nothing anywhere multiplied them together. The rate is
    the engine's own answer (`Book.conversions()`), so the test and the book read one.
    """
    from portfusion.engine import Book
    bad = []
    for r in Book().conversions().dropna(subset=["rate"]).itertuples():
        want = round(r.local_amount / r.rate, 2)
        if abs(want - r.amount) > 0.005:
            bad.append(f"{str(r.date)[:10]} {r.account}: {r.currency} {r.local_amount} at "
                       f"{r.rate} is {want}, the row says {r.amount}")
    assert not bad, "a converted amount is not what its own rate produces:\n  " + "\n  ".join(bad)


@pytest.mark.audit
def test_no_conversion_reaches_too_far_back_for_its_rate(D):
    """AN AUDIT, NOT A GUARD, and the distinction is the point of the whole exercise.

    A conversion takes the newest sourced rate ON OR BEFORE the event — the rule
    `Book._marks_at()` already applies to prices — because the record holds a close for the
    days it fetched one, not for every day. How far back that reaches is a fact about the
    RECORD, not about the code: it says a rate has not been fetched recently enough, and the
    fix is to fetch one. So it belongs in the audit, where the answer is actionable, rather
    than in a suite whose job is to stay green unless something broke.
    """
    from portfusion.engine import Book
    conv = Book().conversions()
    stale = conv[conv["stale"]] if not conv.empty else conv
    assert stale.empty, (
        "these conversions used a rate older than "
        f"{D.FX_RATE_AGE_LIMIT_DAYS} days:\n  "
        + "\n  ".join(f"{r.account} {str(r.date)[:10]}: the close of {r.rate_date}, "
                      f"{r.days_apart} days before the event" for r in stale.itertuples()))
