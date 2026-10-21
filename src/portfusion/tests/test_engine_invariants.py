"""
THE ENGINE'S OWN ARITHMETIC — checked against ITSELF, never against what a page shows.

WHY THIS FILE EXISTS: it closes the one gap the guard had.

Every figure is the engine's and every page its output, so `tests/desk/test_ties.py` is a
REGRESSION test — it catches a renderer that stops rendering what the engine computed, which is
worth having and is not a second opinion: no page computes a figure of its own to compare. It
cannot catch the engine being wrong; that is the cost of one implementation, and this file is
what pays it.

WHAT AN INVARIANT IS HERE. A relationship that must hold WHATEVER THE NUMBERS ARE. Nothing
below renders a page, and nothing below hardcodes a figure — an expected figure would make
this a fixture that goes stale the first time a real trade moves something.

So a test here fails for one reason: the engine's arithmetic contradicts itself. That is
the only kind of wrongness the rest of the suite cannot see.

WHAT IT STILL CANNOT DO. It cannot tell you a figure is the WRONG ANSWER — only that the
engine is inconsistent with itself. A book where every position's cost was doubled would
satisfy every identity here. The external check on that is the brokers' own statements,
which nothing in this repo can influence, and which `Book.reconciliation()` already runs.
"""
import pandas as pd
import pytest

from portfusion.record import rules as D
from portfusion.engine import BASELINE_ASOF, MEASURE_BASIS, BasisError, Book, roll_up
from harness import needs

PENNY = 0.01


def close(a, b, tol=PENNY):
    return abs(float(a) - float(b)) < tol


# =====================================================================================
# THE TWO BASES — the identities that stop money and notional being added together
# =====================================================================================

def test_the_two_bases_compose_into_total_exposure(book):
    """owned + notional = total market exposure. The whole book, split exactly once.

    If these stop composing, one basis is being counted twice or a holding belongs to
    neither — and the headline figure a reader meets first is the sum of the two.
    """
    assert close(book.owned() + book.exposure(), book.total_exposure())


def test_leverage_is_exactly_the_gap_between_exposure_and_the_money(book):
    """Leverage is DERIVED from two published figures and is itself published.

    That combination is why it once drifted unnoticed in a to-do list: it is the one headline
    nothing recomputes. Here it is recomputed.
    """
    f = book.headline()
    assert close(f["Exposure above net asset value"],
                 book.total_exposure() - book.nav())


def test_each_basis_closes_its_own_cost_gain_and_value(book):
    """cost + gain = value, WITHIN a basis. Three columns that must agree per partition.

    Per basis rather than per book, because that is the sharper statement: a book-wide
    version passes even if a gain has been booked against the wrong basis, since the two
    errors cancel in the total.
    """
    h = book.holdings(by="ticker")
    for basis in sorted(set(h["held_as"])):
        s = h[h["held_as"] == basis]
        assert close(s["cost"].sum() + s["gain"].sum(), s["value"].sum()), \
            f"{basis}: cost + gain does not reach value"


@needs("trades")
def test_owned_cost_plus_the_whole_books_unrealised_is_NOT_the_owned_value(book):
    """A NEGATIVE INVARIANT, and it is the issuer roll-up trap written as a test.

    `unrealised()` spans BOTH bases. Adding it to the owned cost alone produces a number
    that looks like the owned value, is out by the spread bets' share, and would sail
    through a reviewer because both inputs are real engine figures.

    Asserted as an inequality on purpose: if these ever coincide it means the spread-bet
    legs have stopped contributing unrealised gain, and the identity above is the one that
    should be passing instead.
    """
    h = book.holdings(by="ticker")
    owned = h[h["held_as"] == "shares"]
    assert not close(owned["cost"].sum() + book.unrealised(), owned["value"].sum()), (
        "owned cost + WHOLE-BOOK unrealised now equals owned value. Either the spread bets "
        "have no unrealised gain, or a basis has stopped being a partition.")


@needs("trades")
def test_roll_up_refuses_to_add_exposure_to_money(book):
    """THE BASIS SPLIT, enforced structurally rather than remembered.

    A sentence would rely on its reader to remember. Here the wrong sum raises.
    Good design makes the wrong thing impossible rather than forbidden.
    """
    by = book.by_account()
    assert MEASURE_BASIS["exposure"] != MEASURE_BASIS["nav"]
    with pytest.raises(BasisError):
        roll_up(by, "exposure", "nav")
    with pytest.raises(BasisError):
        roll_up(by, "nav", "capital_employed", "exposure")
    # Each on its own is fine, and that is the whole point: ask twice, never once.
    assert roll_up(by, "exposure")["exposure"] > roll_up(by, "nav")["nav"]


def test_every_measure_declares_a_basis(book):
    """A new column with no declared basis must fail loudly, not default to money."""
    # Two labels, a rate and a flag: none is an amount, and none may be totalled.
    not_measures = ("account", "held_as", "ytd", "opened_in_period")
    numeric = [c for c in book.by_account().columns if c not in not_measures]
    undeclared = [c for c in numeric if c not in MEASURE_BASIS]
    assert not undeclared, f"add these to MEASURE_BASIS: {undeclared}"
    for column in ("ytd", "opened_in_period"):
        with pytest.raises(KeyError):
            roll_up(book.by_account(), column)


# =====================================================================================
# PARTITIONS — a roll-up must cover the book exactly once
# =====================================================================================

@needs("trades")
def test_the_issuer_roll_up_is_not_a_partition_by_basis(book):
    """THE TRAP `Book.holdings()` NAMES, asserted rather than described.

    holdings(by="issuer") merges tickers, so its `basis` column is NOT a partition — summing
    cost by basis on it understates the owned figure. The totals still
    agree, which is exactly what makes it dangerous: the number you get is plausible.
    """
    by_ticker = book.holdings(by="ticker")
    by_issuer = book.holdings(by="issuer")
    assert close(by_ticker["value"].sum(), by_issuer["value"].sum()), \
        "the two roll-ups disagree about what the book is worth"

    owned_t = by_ticker.loc[by_ticker["held_as"] == "shares", "cost"].sum()
    owned_i = by_issuer.loc[by_issuer["held_as"] == "shares", "cost"].sum()
    assert not close(owned_t, owned_i), (
        "the issuer roll-up now partitions by basis. If that is a deliberate change, this "
        "test and `Book.holdings()`'s docstring both need updating — but check first, because the "
        "usual cause is a holding losing its second ticker.")


def test_every_account_row_rolls_up_to_the_portfolio_total_on_both_bases(book):
    """Per-account and total are the same numbers, at every frozen quarter end.

    On BOTH bases, because they answer different questions with different answers and a
    roll-up that ties on one can be wrong on the other.
    """
    for as_of in book.quarter_nav_total().index:
        rows = book.quarter_nav_rows(as_of, "nav")
        assert close(rows["amount"].sum(), book.quarter_nav_total()[as_of]), \
            f"nav rows at {as_of} do not sum to the nav total"
    for as_of in book.quarter_exposure_total().index:
        rows = book.quarter_nav_rows(as_of, "exposure")
        assert close(rows["amount"].sum(), book.quarter_exposure_total()[as_of]), \
            f"exposure rows at {as_of} do not sum to the exposure total"


def test_a_basis_nobody_has_classified_is_refused_rather_than_guessed(book, monkeypatch):
    """`_classified()` raises on an unknown basis instead of dropping or summing it.

    Refusing is the only answer that cannot be quietly wrong: dropping understates the
    total and summing puts notional inside net asset value, and neither says anything.
    """
    q = book.quarter_nav()
    assert set(q["contribution"]) <= (book.NAV_BASES | book.EXPOSURE_BASES), \
        "quarter-nav.csv carries a basis in neither set — _classified() should refuse it"
    assert book.MEASURE_SETS["nav"] is book.NAV_BASES
    assert book.MEASURE_SETS["exposure"] is book.EXPOSURE_BASES
    # AND IT IS FED ONE: the asserts above say only that today's record has none to refuse.
    if q.empty:
        pytest.skip("quarter-nav.csv holds no row to give an unknown basis")
    odd = pd.concat([q, q.head(1).assign(contribution="a basis nobody classified")])
    monkeypatch.setattr(book, "quarter_nav", lambda: odd)
    with pytest.raises(ValueError, match="neither"):
        book._classified()


# =====================================================================================
# TWO ROUTES TO ONE FIGURE — the strongest shape of self-check available here
# =====================================================================================

def test_realised_gain_is_reachable_two_ways_and_agrees(book):
    """Once from the exits, once by totalling the round trips. Two paths, one number."""
    assert close(book.realised(), float(book.round_trip_totals()["gain"]))


def test_total_gain_is_its_two_halves(book):
    assert close(book.headline()["Total gain"], book.unrealised() + book.realised())


def test_portfolio_cost_is_the_two_bases_costs(book):
    """A MIXED-BASIS figure, the engine's own term for unrealised and registered as a headline
    until 13 Oct 2026: the two costs it sums are shown apart instead. This checks
    it is still the sum it claims to be."""
    h = book.holdings(by="ticker")
    assert close(book.portfolio_cost(),
                 h.loc[h["held_as"] == "shares", "cost"].sum()
                 + h.loc[h["held_as"] == "spread bet", "cost"].sum())
    assert "Cost and entry notional" not in Book.HEADLINE


def test_the_unrealised_total_is_the_sum_of_the_holdings_own_gains(book):
    assert close(book.unrealised(), book.holdings(by="ticker")["gain"].sum())


# =====================================================================================
# THE RETURN — its inputs partition, or the numerator is quietly wrong
# =====================================================================================

def test_every_income_category_is_classified_as_position_or_account(book):
    """The return takes POSITION_INCOME only. A category in neither list would be silently
    excluded from the numerator, and a category in both would be counted twice. The loader
    refuses an undeclared category; this holds the declared ones to the split."""
    declared = list(D.schema.INCOME_CATEGORIES)
    assert sorted(D.POSITION_INCOME + D.ACCOUNT_INCOME) == sorted(declared), (
        f"income categories in neither list, or in both: {declared}")


def test_the_two_income_halves_partition_the_whole(book):
    """POSITION income + ACCOUNT income = all income. Exactly, with nothing left over.

    The return takes the first half only — dividends and funding interest, what the capital
    earns and costs — while fees and interest on idle cash belong to the account. A category
    landing in neither would vanish from the total; one landing in both would be counted
    twice. Either way the published return moves and nothing says so.

    NOTE THE SIGN. Position income can be LARGER than total income,
    because the account half is negative — it is mostly fees. A test asserting the
    numerator was a subset "and therefore smaller" would fail on a correct book, which is
    what the first draft of this did.
    """
    rows = book.income_rows(book.ytd_year())
    position = rows[rows["category"].isin(D.POSITION_INCOME)]["amount"].sum()
    account = rows[rows["category"].isin(D.ACCOUNT_INCOME)]["amount"].sum()
    assert close(position + account, book.totals()["income"]), \
        "the two income halves do not add up to the book's income"
    assert close(position, book.position_income(book.ytd_year()).sum()), \
        "position_income() disagrees with the rows it is drawn from"
    # And every category present really is in one list or the other.
    known = set(D.POSITION_INCOME) | set(D.ACCOUNT_INCOME)
    assert set(rows["category"]) <= known, \
        f"income categories in neither list: {sorted(set(rows['category']) - known)}"


# =====================================================================================
# WHAT MOVED — the three effects account for the change, and for nothing else
# =====================================================================================

@needs("trades")
def test_the_three_effects_sum_to_the_change_on_every_line(book):
    """price + fx + transacted = change, exactly, per line and in total.

    This is the whole contract of changes_since(). A decomposition whose parts do not add
    back to the thing decomposed is not an explanation of it — it is three numbers beside a
    fourth, and a reader has no way to tell which one is lying.
    """
    frame = book.changes_since()
    assert not frame.empty, "changes_since() returned nothing — the identity is vacuous"
    for row in frame.to_dict("records"):
        parts = row["price_effect"] + row["fx_effect"] + row["transacted"]
        assert close(row["change"], parts), (
            f"{row['key']}: change {row['change']:,.2f} but the effects come to "
            f"{parts:,.2f} — price {row['price_effect']:,.2f}, fx {row['fx_effect']:,.2f}, "
            f"transacted {row['transacted']:,.2f}")
        assert close(row["value_from"] + row["change"], row["value_to"]), (
            f"{row['key']}: {row['value_from']:,.2f} + {row['change']:,.2f} is not "
            f"{row['value_to']:,.2f}")


@pytest.mark.audit
def test_the_lines_end_where_the_book_is(book):
    """Each kind of line ends at the figure the book publishes for it.

    THIS IS WHAT MAKES THE PANEL TRUSTWORTHY rather than decorative: a decomposition that
    lands somewhere other than the book is describing a different book. It caught a real
    defect on the first run — keying the frame off price-history rather than off the live
    ledger put four positions closed months ago into it, each reported across its own stale
    window, and direct value_to read well above the book's figure.

    AN AUDIT, NOT A GUARD. A line holds each position as it stood at that line's newest mark;
    the book holds it as it stands now. A close entered after the mark keeps the two apart
    until the next price refresh, with no code defect and no code change that could close the
    gap. Whether the marks are fresh enough is the record's question, so the audit asks it.
    """
    for held_as, published in (("shares", book.owned()), ("spread bet", book.exposure())):
        totals = book.change_totals(held_as=held_as)
        assert totals["lines"], f"no {held_as} lines at all — nothing is being asserted"
        assert close(totals["value_to"], published), (
            f"{held_as} lines end at {totals['value_to']:,.2f} but the book publishes "
            f"{published:,.2f}")
        parts = totals["price_effect"] + totals["fx_effect"] + totals["transacted"]
        assert close(totals["change"], parts), (
            f"{held_as} totals do not decompose: {totals['change']:,.2f} vs {parts:,.2f}")


@needs("trades")
def test_a_line_carries_its_own_two_dates(book):
    """EACH LINE IS MEASURED FROM ITS OWN PREVIOUS MARK, never from one book-wide date.

    Held line by line against the line's own history, so it holds on a day when every line
    happens to share one window as firmly as on a day when none do. It used to ask for more
    than one window, which was true only while two feeds banked on different days.
    """
    history = book.store["history.prices"]
    own_dates = {k: sorted({str(d)[:10] for d in g["date"]})
                 for k, g in history.groupby("ticker")}
    frame = book.changes_since()
    dated = frame[frame["priced_from"].notna()]
    assert not dated.empty, "no line has two marks — this asserts nothing"
    for row in dated.to_dict("records"):
        assert row["priced_from"] < row["priced_at"], (
            f"{row['key']} runs {row['priced_from']} -> {row['priced_at']}, which is not "
            f"forwards")
        before = [d for d in own_dates.get(row["key"], []) if d < str(row["priced_at"])[:10]]
        assert before and str(row["priced_from"])[:10] == before[-1], (
            f"{row['key']} is measured from {row['priced_from']}, not from its own previous "
            f"mark {before[-1] if before else None} — a book-wide date has crept back in")


def _held_the_day_before(book, day: str) -> tuple[str, dict, dict, dict]:
    """The book as it stood the day before `day`: that date, each mark key's valued legs, and
    the prices and rates it was valued at."""
    before = (pd.Timestamp(day) - pd.Timedelta(days=1)).date().isoformat()
    held: dict[str, list] = {}
    for leg in book._valued_legs_at(before).values():
        held.setdefault(leg["key"], []).append(leg)
    prices, rates = book._marks_at(before)
    return before, held, prices, rates


@needs("trades")
def test_the_window_starts_where_the_book_stood(book):
    """EACH LINE STARTS AS THE BOOK HELD IT THE DAY BEFORE ITS NEW MARK: every line the book
    held then has a row, valued at the mark and the RATE the book valued it at — the start's
    half of `test_the_lines_end_where_the_book_is`.

    IT FAILED TWO WAYS ON ITS FIRST RUN (13 Oct 2026). The US lines started at the rate
    banked on or before their close's own date, where the book had valued those closes at a
    later rate beside them: securities owned started above where the book stood. And a contract
    closed inside the window had no row, so its value at the outgoing mark was nowhere and the spread-bet notional started without it.

    A LINE DEALT IN BETWEEN ITS PREVIOUS MARK AND THAT DAY is left out: dealing is valued at
    what it cost, from the previous mark (changes_since()'s docstring), so its start is not the
    book's on the day before, by design.
    """
    rows = {r["key"]: r for r in book.changes_since().to_dict("records")}
    ident = book._identity().set_index("code")
    checked = 0
    for end in sorted({r["priced_at"] for r in rows.values()}):
        before, held, prices, rates = _held_the_day_before(book, end)
        for key, legs in held.items():
            if key not in prices:
                continue                          # never priced: no line to start
            row = rows.get(key)
            assert row is not None, (
                f"{key} was held on {before} and has no line — a window that drops a line the "
                f"book held starts somewhere the book never was")
            if row["priced_at"] != end or row["priced_from"] is None:
                continue                          # its window ends elsewhere, or it has one mark
            at_previous = sorted(leg["qty"] for leg in book._valued_legs_at(row["priced_from"]).values()
                                 if leg["key"] == key)
            if at_previous != sorted(leg["qty"] for leg in legs):
                continue                          # dealt in since its previous mark
            ticker = legs[0]["ticker"]
            cur = ident.at[ticker, "currency"]
            parity = ident.at[ticker, "kind"] == "spread bet" or cur == "GBP"
            rate = 1.0 if parity else rates[cur][1]
            stood = sum(leg["qty"] for leg in legs) * prices[key][1] / rate
            assert close(row["value_from"], stood), (
                f"{key} starts at {row['value_from']:,.2f}; the book held it at {stood:,.2f} on "
                f"{before}, its mark of {prices[key][0]} at the rate of {rates.get(cur, ('—',))[0]}")
            checked += 1
    assert checked, "no line's start was compared — this asserts nothing"


@needs("trades")
def test_a_line_sold_outright_inside_the_window_lands_at_nothing(store_copy):
    """A LINE CLOSED INSIDE THE WINDOW KEEPS ITS ROW, ending at its close: nothing left, the
    proceeds under dealing, the move from its last mark to the sale price under price, and
    the sale's date where the new mark's would be. Absent, the window's start lost the line
    and the dealing column showed a part-close but never a whole one.

    Built on a copy: the one-account share line with the newest mark sold outright on that
    mark's day, at 90% of its previous mark."""
    import csv
    from portfusion.record import rules
    book = Book()
    frame = book.changes_since()
    shares = frame[(frame["held_as"] == "shares") & frame["priced_from"].notna()]
    one_account = [r for r in shares.sort_values("priced_at", ascending=False).to_dict("records")
                   if len({leg["acct"] for leg in book._valued_legs_at(r["priced_at"]).values()
                           if leg["key"] == r["key"]}) == 1]
    assert one_account, "no share line held by one account — nothing to sell outright"
    line = one_account[0]
    legs = [leg for leg in book._valued_legs_at(line["priced_at"]).values() if leg["key"] == line["key"]]
    # A SHARE'S SIZE IS WHOLE; the ledger's qty column is a float since a bet's is its stake.
    account, qty = legs[0]["acct"], int(sum(leg["qty"] for leg in legs))
    previous = book._marks_at(line["priced_from"])[0][line["key"]][1]
    now = book._marks_at(line["priced_at"])[0][line["key"]][1]
    price = round(previous * 0.9, 6)
    proceeds = round(line["value_to"] * price / now, 2)      # at the rate the line ends at
    cur = book._identity().set_index("code")["currency"][line["ticker"]]   # the mark's currency
    with (store_copy / "exits.csv").open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh, lineterminator="\n").writerow(
            ["E-999", line["priced_at"], account, line["ticker"], qty, "", price, cur, "",
             proceeds, "a test sale", "", book.parcel(account, line["ticker"]), "", ""])
    rules.reload_store()
    after = Book()
    rows = {r["key"]: r for r in after.changes_since().to_dict("records")}
    sold = rows.get(line["key"])
    assert sold is not None, f"{line['key']} was sold outright inside the window and has no line"
    assert sold["value_to"] == 0 and sold["qty_to"] == 0, f"{line['key']} still holds something"
    assert close(sold["transacted"], line["transacted"] - proceeds), (
        f"{line['key']}: dealing {sold['transacted']:,.2f}, where it was "
        f"{line['transacted']:,.2f} before a sale of {proceeds:,.2f}")
    assert close(sold["value_from"], line["value_from"]), (
        f"{line['key']} starts at {sold['value_from']:,.2f}; before the sale it started at "
        f"{line['value_from']:,.2f} — a sale inside the window moved its start")
    assert sold["priced_from"] == line["priced_from"] and sold["priced_at"] == line["priced_at"]
    assert abs(sold["price_move_pct"] - (-0.10)) < 1e-6, (
        f"{line['key']}: mark move {sold['price_move_pct']:.4%}, the sale was 10% below its mark")
    assert close(sold["value_from"] + sold["price_effect"] + sold["fx_effect"]
                 + sold["transacted"], 0.0), "the effects do not take the line to nothing"


@pytest.mark.audit
def test_a_close_banked_after_the_live_mark_does_not_move_where_the_lines_end(store_copy):
    """A past day's closes are banked into the history and leave the live table alone, so a
    close can sit AFTER a line's live mark — a missed quarter end banked before the next
    refresh. The lines must still end where the book is, whole and by account.

    An audit, for the reason `test_the_lines_end_where_the_book_is` gives: it starts from the
    live record's marks."""
    import csv
    before = Book()
    live = {r["ticker"]: (r["price"], str(r["as_of"])[:10], r["currency"])
            for r in before.store["prices"].to_dict("records")}
    ahead = []
    for key, (price, as_of, currency) in live.items():
        later = (pd.Timestamp(as_of) + pd.Timedelta(days=3)).date().isoformat()
        ahead.append([key, later, round(float(price) * 1.05, 4), currency, "sourced", "close",
                      "live", f"a close banked after the live mark, {later}"])
    with (store_copy / "price-history.csv").open("a", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(ahead)
    book = Book()
    assert book.owned() == before.owned() and book.exposure() == before.exposure(), (
        "banking a close moved a published figure — it must wait for a refresh")
    for held_as, published in (("shares", book.owned()), ("spread bet", book.exposure())):
        totals = book.change_totals(held_as=held_as)
        assert close(totals["value_to"], published), (
            f"{held_as} lines end at {totals['value_to']:,.2f} but the book publishes "
            f"{published:,.2f} — the window ran on past the live mark")
    for account, held_as, published in _account_kind(book):
        totals = book.change_totals(held_as=held_as, account=account)
        assert close(totals["value_to"], published), (
            f"{account}: its lines end at {totals['value_to']:,.2f}, the book at {published:,.2f}")


def test_the_two_kinds_of_line_are_never_totalled_together(book):
    """One is money and the other is notional. The refusal is the guard, not a convention."""
    with pytest.raises(BasisError):
        book.change_totals(held_as="both")
    with pytest.raises(BasisError):
        book.change_totals(held_as="direct")      # the retired word, not the record's


def _account_kind(book):
    """Each account, and the one kind of line it holds. by_account()'s own `held_as`."""
    return [(r["account"], r["held_as"], r["exposure"])
            for r in book.by_account().to_dict("records")]


@pytest.mark.audit
def test_an_accounts_lines_end_where_that_account_is(book):
    """The same tie-back as the whole book, asserted one account at a time.

    Holdings can be asked by account and the chips read this frame, so a narrowed row showing
    the whole book's change would be a figure describing more than the row above it — a line
    can sit in several accounts.

    THE TIE IS TO `by_account().exposure`, which is the engine's own per-account figure: a
    share account's exposure IS its owned value and a spread-bet account's is its notional.

    An audit, for the reason `test_the_lines_end_where_the_book_is` gives.
    """
    for account, held_as, published in _account_kind(book):
        totals = book.change_totals(held_as=held_as, account=account)
        assert totals["lines"], f"{account}: no {held_as} lines at all"
        assert close(totals["value_to"], published), (
            f"{account}: its lines end at {totals['value_to']:,.2f} but by_account() puts it "
            f"at {published:,.2f}")
        parts = totals["price_effect"] + totals["fx_effect"] + totals["transacted"]
        assert close(totals["change"], parts), (
            f"{account}: totals do not decompose, {totals['change']:,.2f} vs {parts:,.2f}")


def test_an_account_holds_one_kind_of_line_and_only_one(book):
    """A shares account has no spread-bet lines and a spread-bet account has no share ones.

    This is what makes the accounts a PARTITION rather than an overlapping set, which the
    test below rests on. It is also `ACCOUNT_ORDER`'s stated reason for existing — the order
    separates the two valuation bases — asserted here on the changes frame.

    ONE WORD FOR A LINE'S KIND, STORED ONCE. A kind held in more than one place, or read from a
    name such as a code's ` SB` suffix, is a second answer that can disagree: `securities.kind`
    holds it per code, and nothing decides from the name.
    """
    for account, held_as, _ in _account_kind(book):
        other = "spread bet" if held_as == "shares" else "shares"
        totals = book.change_totals(held_as=other, account=account)
        assert totals["lines"] == 0, (
            f"{account} holds {held_as} but has {totals['lines']} {other} line(s) — the two "
            f"bases are meant to be separated by account")


def test_the_accounts_partition_the_whole_books_change(book):
    """Every account's change, added up within a basis, is the book's own change.

    A NARROWED VIEW THAT DOES NOT ADD BACK IS A DIFFERENT BOOK. Each half is asserted on its
    own basis and the two are never added — shares are money, spread bets notional.
    """
    for held_as in ("shares", "spread bet"):
        whole = book.change_totals(held_as=held_as)
        per_account = sum(book.change_totals(held_as=held_as, account=a)["change"]
                          for a, own, _ in _account_kind(book) if own == held_as)
        assert close(whole["change"], per_account), (
            f"{held_as}: the accounts come to {per_account:,.2f} against the book's "
            f"{whole['change']:,.2f}")


@needs("trades")
def test_narrowing_to_an_account_narrows_a_line_that_several_accounts_hold(book):
    """The point of the argument, on the line that proves it.

    A line held in ONE account must read the same narrowed as it does whole; a line held in
    SEVERAL must read smaller in each. Discovered from the frame rather than named here, so
    this keeps asserting something after the book changes shape.
    """
    whole = {r["key"]: r for r in book.changes_since().to_dict("records")}
    per_account: dict[str, list] = {}
    for account, _, _ in _account_kind(book):
        for r in book.changes_since(account=account).to_dict("records"):
            per_account.setdefault(r["key"], []).append((account, r["value_to"]))

    shared = {k: v for k, v in per_account.items() if len(v) > 1}
    assert shared, "no line is held by more than one account — this asserts nothing"
    for key, slices in shared.items():
        for account, value_to in slices:
            assert value_to < whole[key]["value_to"], (
                f"{key} in {account} reads {value_to:,.2f} against a whole-book "
                f"{whole[key]['value_to']:,.2f} — the narrowing did not narrow")
        assert close(sum(v for _, v in slices), whole[key]["value_to"]), (
            f"{key}: its account slices do not add back to the whole line")


# =====================================================================================
# A LINE'S MARK HISTORY — every key it was ever priced under
# =====================================================================================

@needs("trades")
def test_a_lines_mark_history_spans_every_key_it_was_ever_priced_under(book):
    """price-history still holds TICKER-KEYED rows from before the contract convention.

    A line's honest history spans every spelling it was ever marked under — ORLA SB here
    reads as `ORLA-DEC26` twice and the older `ORLA SB` once, from when that ticker had one
    contract open and the two keys meant the same thing. Showing only the contract would
    make a position opened in May look as though it began in August.

    THE LINE IS FOUND, NOT NAMED: any ticker the history prices under its own key AND under
    one of its mapped contracts. A book with no such line fails the premise loudly.

    A RETIRED CONTRACT CONTRIBUTES WHAT IT HAS, which may be nothing: closed, and never
    priced. That is an absence rather than a gap.
    """
    from portfusion.record import rules as D
    leg_ticker = {t.id: t.ticker for t in D.trades}
    contracts_of = {}
    for leg, contract in D.LEG_CONTRACT.items():
        if leg in leg_ticker:
            contracts_of.setdefault(leg_ticker[leg], set()).add(contract)
    keys_on_file = set(book.store["history.prices"]["ticker"])
    spanned = sorted(t for t, cs in contracts_of.items()
                     if t in keys_on_file and cs & keys_on_file)
    assert spanned, ("no line is priced under both its own key and a contract's — the "
                     "legacy-spelling claim has nothing to bite on in this book")
    line = spanned[0]

    history = book.mark_history(line)
    assert not history.empty, f"{line} has no marks at all"
    assert len(set(history["mark_key"])) > 1, (
        f"{line}'s history is under one key only: {set(history['mark_key'])} — the legacy "
        f"ticker-keyed rows are being dropped")
    assert "source" in history.columns and history["source"].notna().all(), \
        "a mark arrives without its source string, which is the point of opening this"
    dates = list(history["date"])
    assert dates == sorted(dates, reverse=True), "the history is not newest-first"


@needs("trades")
def test_a_multi_contract_line_opens_every_contracts_marks(book):
    """HALV SB's history has to answer for both contracts, at their own levels."""
    keys = book.changes_since().groupby("ticker")["key"].apply(set)
    several = keys[keys.map(len) > 1]
    assert not several.empty, "no multi-contract line — this asserts nothing"
    for ticker, priced_by in several.items():
        history = book.mark_history(ticker)
        assert priced_by <= set(history["mark_key"]), (
            f"{ticker} is priced by {priced_by} but its history covers "
            f"{set(history['mark_key'])}")


# =====================================================================================
# VALUING AT A DATE — one level cannot value a position held at two
# =====================================================================================

@needs("trades")
def test_one_accounts_spread_bet_can_be_valued_at_a_date(book):
    """A spread-bet account values at a past date, and its legs sum to the book's.

    The SIBLING of the test below. That one caught a per-contract split keyed by ticker; this
    one catches the split being made against the wrong POPULATION.

    `holdings_at(as_of, account)` narrowed its holdings to one account and then asked
    `_held_by_mark_key()` for the WHOLE BOOK's lots. So a multi-contract spread bet was split
    book-wide and compared against one account's quantity, which never matched: a ticker held on
    two contracts across two accounts, neither holding the combined quantity. The split was
    refused, the ticker fall-back found no ticker-keyed mark at any recent date, and EITHER
    ACCOUNT RAISED FOR EVERY DATE from the contract-keying convention onward.

    It failed loudly, which is why it survived: nothing in the build calls it that way. The
    share reconciliation does, and the spread-bet one was about to.

    NOTHING IS HARDCODED. The per-account values are summed and checked against the book-wide
    figure for the same date, so the assertion holds whatever the levels are.
    """
    accounts = [a for a in D.ACCOUNT_ORDER if book.is_spread_bet(a)]
    assert accounts, "no spread-bet account to check"
    dates = sorted({d for d in book.store["history.prices"]["date"]})[-6:]
    checked = 0
    for as_of in dates:
        try:
            whole = book.holdings_at(as_of)
        except (KeyError, ValueError):
            continue                      # a date the record cannot value at all
        parts = 0.0
        for a in D.ACCOUNT_ORDER:
            try:
                parts += float(book.holdings_at(as_of, a)["value"].sum())
            except (KeyError, ValueError):
                parts = None
                break
        if parts is None:
            continue
        assert close(parts, float(whole["value"].sum())), (
            f"on {as_of} the accounts sum to {parts:,.2f} against a book of "
            f"{whole['value'].sum():,.2f}")
        checked += 1
    assert checked, "no date valued for every account — the regression would not be caught"


@needs("trades")
def test_a_multi_contract_spread_bet_is_valued_at_each_contracts_own_level(book):
    """Every contract a position holds is valued at ITS OWN mark, and the lots sum.

    `_mark_for()` built `{t.ticker: LEG_CONTRACT[t.id] for t in trades if t.mode == "sb"}` — a
    dict keyed by TICKER, so a ticker with legs on several contracts kept whichever appeared
    LAST IN FILE ORDER. `holdings()` records that exact defect at the head of its own price
    lookup and was fixed first; the dated path still had it.

    MORA SB collapsed onto MORA-DEC26 — closed, and unpriced by design — so holdings_at()
    RAISED for every date from 13 Jul 2026, which is the whole of Q3 and the report's
    completeness gate with it. That was the lucky half, because it failed loudly. HALV SB
    collapsed onto HALV-MAR27 and ZEPH SB onto ZEPH-DEC26, both priced, and each valued a
    two-contract position entirely at one contract's level while failing nothing.

    NOTHING HERE IS HARDCODED. The expected value is rebuilt from the same dated marks, one
    contract at a time, and the collapse is asserted against directly: whatever the levels
    are, the position must not be worth its whole quantity at any single one of them. A
    ticker joins this test by holding legs on two contracts.
    """
    prices = book.store["history.prices"]
    checked = 0
    for as_of in sorted(set(prices["date"])):
        try:
            held = book.as_of(as_of).set_index("ticker")
            frame = book.holdings_at(as_of).set_index("ticker")
        except (KeyError, ValueError):
            continue                      # a date the record cannot value; covered elsewhere
        px, _ = book._marks_at(as_of)
        by_ticker: dict[str, dict[str, float]] = {}
        for (ticker, key), qty in book._held_by_mark_key(as_of).items():
            by_ticker.setdefault(ticker, {})[key] = qty

        for ticker, lots in by_ticker.items():
            if ticker not in frame.index or frame.at[ticker, "held_as"] != "spread bet":
                continue
            if len(lots) < 2 or not all(k in px for k in lots):
                continue
            qty = held.at[ticker, "qty"]
            if not close(sum(lots.values()), qty):
                continue                  # a leg with no contract; the ticker fall-back owns it

            expected = sum(q * px[k][1] for k, q in lots.items())
            assert close(frame.at[ticker, "value"], expected), (
                f"{ticker} at {as_of} is valued {frame.at[ticker, 'value']:,.2f}, but its "
                f"contracts at their own levels come to {expected:,.2f}: "
                f"{ {k: (q, px[k][1]) for k, q in lots.items()} }")

            for key, level in ((k, px[k][1]) for k in lots):
                if len({px[k][1] for k in lots}) == 1:
                    continue              # same level on both; the collapse is undetectable
                assert not close(frame.at[ticker, "value"], qty * level), (
                    f"{ticker} at {as_of} is worth its WHOLE quantity at {key}'s level — "
                    f"that is the ticker collapse, valuing {qty:,.0f} at {level}")
            checked += 1

    assert checked, ("no spread bet held legs on two contracts at any dated mark, so this "
                     "test asserted nothing — check the fixture before trusting it")


# =====================================================================================
# THE FIGURE REGISTRY — every published figure is declared, and means what it declares
# =====================================================================================

def test_every_figure_the_engine_publishes_is_in_the_registry(book):
    """headline() and HEADLINE must not drift apart. A figure the registry does not know
    has no basis, no unit and no rule about whether a dated page may quote it."""
    assert set(book.headline()) == set(Book.HEADLINE), \
        "headline() and the HEADLINE registry disagree about what the book publishes"


def _valuable_quarters(book):
    """The quarter ends the engine can actually value, and why the others are not here.

    `2025-12-31` is the baseline itself, the year's opening and no quarter's end. A quarter end
    the book cannot value is left out rather than valued from a price that does not exist:
    `2026-03-31` was, until its closes were banked on 14 Oct 2026.

    Discovered, never listed: a quarter joins by becoming valuable.
    """
    out = []
    for as_of in book.quarter_nav_total().index:
        if as_of == BASELINE_ASOF:
            continue
        try:
            book.headline(as_of)
        except (KeyError, ValueError):
            continue
        out.append(as_of)
    assert out, "no quarter can be valued at all — every dated assertion below is vacuous"
    return out


@needs("trades")
def test_a_dated_view_publishes_exactly_the_point_in_time_figures(book):
    """A year-to-date figure has no value AT a date, so a quarter page must not carry one."""
    registered = {k for k, v in Book.HEADLINE.items() if v["point_in_time"]}
    for as_of in _valuable_quarters(book):
        assert set(book.headline(as_of)) == registered, \
            f"the dated view at {as_of} does not match the point-in-time set"


@needs("trades")
def test_the_dated_parts_still_add_up_to_the_dated_whole(book):
    """"— of which" has to mean it at a quarter end too, not only live."""
    for as_of in _valuable_quarters(book):
        f = book.headline(as_of)
        assert close(f["— of which securities owned"] + f["— of which spread-bet notional"],
                     f["Total market exposure"])
        assert close(f["Exposure above net asset value"],
                     f["Total market exposure"] - f["Net asset value"])


def test_every_registered_figure_declares_a_basis_and_a_unit():
    """A FIGURE'S NAME AND ITS BASIS AGREE. A money figure once sat under a ratio's name and a
    mixed one under a cost's; each registered figure states its basis and unit, so a renderer
    marks what is notional and never guesses."""
    for label, spec in Book.HEADLINE.items():
        assert spec["basis"], f"{label} has no basis"
        assert spec["unit"] in {"gbp", "pct", "count"}, f"{label} has unit {spec['unit']!r}"
        assert isinstance(spec["point_in_time"], bool)


def test_the_live_headline_builds_the_year_once(monkeypatch):
    """ONE YEAR, ASKED ONCE. The live headline asked `by_account()` three times and `totals()`
    twice until step 5: net asset value rebuilt the year `totals()` already held, and the return
    since the start asked `totals()` again for the year's return. Every live figure comes from the
    one year, so it is built once."""
    b = Book()
    asked = {"by_account": 0, "totals": 0}
    for name in asked:
        def counted(*a, _real=getattr(b, name), _name=name, **k):
            asked[_name] += 1
            return _real(*a, **k)
        monkeypatch.setattr(b, name, counted)
    b.headline()
    assert asked == {"by_account": 1, "totals": 1}, f"one live headline asked {asked}"


# =====================================================================================
# TIME — the quarter vocabulary, independent of any tab
# =====================================================================================

def test_a_quarter_label_and_its_start_are_derived_from_the_date(book):
    """Both were hand-rolled somewhere once. quarter_start() was first-of-month minus 62
    days in the report, which lands on 1 MARCH for a Q2 page."""
    assert Book.quarter_label("2026-06-30") == "Q2 2026"
    assert Book.quarter_label("2025-12-31") == "Q4 2025"
    assert Book.quarter_start("2026-06-30") == "2026-04-01"
    assert Book.quarter_start("2027-01-15") == "2027-01-01"


def test_a_frozen_quarter_is_never_labelled_to_date(book):
    """The freeze is what closes a label. Nothing else may: only the quarter still running, which
    ends at the newest mark, says "to date"."""
    q = book.quarter_returns(include_open=True)
    frozen = set(book.quarter_nav_total().index)
    for r in q.itertuples():
        closed = str(r.quarter_end)[:10] in frozen
        assert closed != r.quarter.endswith(" to date"), (r.quarter_end, r.quarter)


# =====================================================================================
# THE POOL — a share sale releases its holding's average, and nothing is typed
# =====================================================================================

def _walk(monkeypatch, events):
    """`share_pools()` over one made-up holding: (id, day, direction, qty, cost, parcel)."""
    from portfusion import engine
    rows = [{"id": i, "date": pd.Timestamp(day) if day else pd.NaT, "direction": way,
             "held_as": "shares", "acct": "Voss ii ISA", "ticker": "TEST.L", "qty": qty,
             "val": money, "mode": "cost"} for i, day, way, qty, money, _ in events]
    monkeypatch.setattr(engine.D, "REALISATION_BY_EXIT",
                        {i: rid for i, _, way, _, _, rid in events if way == "Sell"})
    return engine.share_pools(pd.DataFrame(rows))


def test_a_share_sale_releases_the_average_and_the_last_takes_what_remains(monkeypatch):
    """Two buys at different prices make one pool. A partial sale takes quantity x the average;
    the sale that empties it takes all that is left, so rounding strands nothing."""
    p = _walk(monkeypatch, [("B1", "2026-01-05", "Buy", 3, 10.00, None),
                            ("B2", "2026-02-05", "Buy", 3, 20.00, None),
                            ("S1", "2026-03-05", "Sell", 1, 0, "R-TEST"),
                            ("S2", "2026-04-05", "Sell", 5, 0, "R-TEST")])
    assert p.at["S1", "released"] == 5.00
    assert p.at["S2", "released"] == 25.00, "the last sale did not take what remained"
    assert (p["parcel"] == "R-TEST").all() and (p["emptied"] == pd.Timestamp("2026-04-05")).all()
    assert (p["opened"] == pd.Timestamp("2026-01-05")).all()


def test_a_pool_sold_out_and_bought_again_is_a_new_holding(monkeypatch):
    """Its own opening date and its own realisation — and a sale filed under the old parcel is
    refused, because it would join two round trips into one."""
    fresh = [("B1", "2026-01-05", "Buy", 10, 100.00, None),
             ("S1", "2026-02-05", "Sell", 10, 0, "R-TEST"),
             ("B2", "2026-03-05", "Buy", 4, 80.00, None),
             ("S2", "2026-04-05", "Sell", 1, 0, "R-TEST-2")]
    p = _walk(monkeypatch, fresh)
    assert p.at["S2", "released"] == 20.00
    assert p.at["S2", "opened"] == pd.Timestamp("2026-03-05")
    assert pd.isna(p.at["B2", "emptied"]) and pd.isna(p.at["B2", "parcel"]), "still held"
    fresh[-1] = ("S2", "2026-04-05", "Sell", 1, 0, "R-TEST")
    with pytest.raises(ValueError, match="R-TEST spans two holdings"):
        _walk(monkeypatch, fresh)


def test_a_consolidation_moves_the_quantity_and_not_the_cost(monkeypatch):
    """A 20:1 consolidation: 40,000 became 2,000 at no cost, and the sale of the 2,000 released
    it all."""
    p = _walk(monkeypatch, [("B1", "2019-03-04", "Buy", 40000, 2500.00, None),
                            ("C1", "2021-06-01", "Buy", -38000, 0.0, None),
                            ("S1", "2025-05-12", "Sell", 2000, 0, "R-TEST")])
    assert p.at["S1", "released"] == 2500.00


def test_a_sale_larger_than_its_holding_is_refused(monkeypatch):
    """Named by account and ticker, in the words the bench shows: nothing is sold short here."""
    with pytest.raises(ValueError, match="sells 11 TEST.L from Voss ii ISA, which held 10"):
        _walk(monkeypatch, [("B1", "2026-01-05", "Buy", 10, 100.00, None),
                            ("S1", "2026-02-05", "Sell", 11, 0, "R-TEST")])


def test_a_holdings_share_cost_is_its_buys_less_what_its_sales_released(book):
    """THE POOL AND THE LEDGER ARE ONE ANSWER: each share holding's cost on `holdings()` is its
    own buys less the cost its sales released, per account — no parcel typed anywhere."""
    L = book.ledger
    shares = L[L["held_as"] == "shares"]
    for acct in book.account_order():
        if book.is_spread_bet(acct):
            continue
        held = book.holdings(account=acct, by="ticker").set_index("ticker")
        mine = shares[(shares["acct"] == acct) & shares["pool_emptied"].isna()]
        for ticker, g in mine.groupby("ticker"):
            bought = g.loc[g["direction"] == "Buy", "val"].sum()
            released = g.loc[g["direction"] == "Sell", "id"].map(book.cost_released).sum()
            assert close(held.at[ticker, "cost"], bought - released), f"{acct} {ticker}"


# =====================================================================================
# EVERY LEDGER ROW KEEPS ITS PROVENANCE
# =====================================================================================

def test_every_ledger_row_carries_the_evidence_it_came_in_with():
    """EVERY FIGURE TRACES TO A REAL, NAMED SOURCE, held here as an invariant.

    THIS TEST EXISTS BECAUSE THE SUITE MISSED THE DEFECT TWICE. First the engine served a
    column labelled `source` containing the word "exposure" — the provenance of every trade
    dropped between the store and the engine, because one name did two jobs and the valuation
    basis overwrote the evidence. It was fixed by ORDERING two lines, which is a fix that holds
    only while nobody reorders them.

    Then renaming the store column `basis` to `evidence` orphaned exactly that dance:
    `ledger["source"] = ledger["contribution"]` read a column only the SELL rows had, and 104
    of 136 rows went to NaN. The whole suite passed, and the build ran clean.

    So the claim is made directly rather than left to depend on the order of two assignments:
    a ledger row's source is present, and it is the EVIDENCE — a named document — never one of
    the valuation words that has twice been found sitting in it.
    """
    L = Book().ledger
    missing = L[L["source"].isna() | (L["source"].astype(str).str.strip() == "")]
    assert missing.empty, (
        f"{len(missing)} ledger row(s) carry no source: {sorted(missing['id'])[:8]}. Every "
        f"figure traces to a real, named source.")

    valuation_words = {"owned", "exposure", "notional", "capital", "mixed", "direct", "synthetic"}
    stray = sorted({s for s in L["source"].astype(str) if s.strip().lower() in valuation_words})
    assert not stray, (
        f"a ledger `source` holds {stray}, which is a VALUATION word and not a document. "
        f"Something is writing the basis into the provenance column again.")


def test_a_spread_bet_nav_does_not_depend_on_where_the_baseline_sits(book, monkeypatch):
    """A SPREAD-BET ACCOUNT'S NET ASSET VALUE IS BUILT FROM ITS BASELINE EQUITY, and that equity
    already holds every sale and every open gain up to the baseline. It added them again — every
    exit's realised gain, every open leg's gain from entry — so a book whose spread bets predate
    its baseline counted them twice (the review of 21 Oct 2026). The check, assuming nothing:
    move the baseline to a later quarter end, give it the account's worth that day, and today's
    figure must not move."""
    ends = [str(q)[:10] for q in book.quarter_nav_total().index if str(q)[:10] > BASELINE_ASOF]
    pick = next(((a, q) for q in reversed(ends) for a in D.ACCOUNT_ORDER
                 if book.is_spread_bet(a)
                 and any(e.acct == a and str(e.date)[:10] <= q for e in D.exits)
                 and not book.as_of(q, a).empty), None)
    if pick is None:
        pytest.skip("no spread-bet account both sold and held at a frozen quarter end")
    account, later = pick

    def nav(by_account):
        return float(by_account.set_index("account").at[account, "nav"])
    then, now = nav(book.by_account(as_of=later)), nav(book.by_account())

    real = Book.quarter_nav_rows
    def frozen(self, as_of, measure="nav"):
        if str(as_of)[:10] != later:
            return real(self, as_of, measure)
        rows = real(self, as_of, measure).copy()
        rows.loc[rows["account"] == account, "amount"] = then
        return rows
    # THE BOOK'S OWN BASELINE, which every figure of it reads (`Book.baseline`): the day after
    # `later`, so `later` is its quarter-end key.
    moved = pd.Timestamp(later) + pd.Timedelta(days=1)
    monkeypatch.setattr(Book, "baseline", property(lambda self: moved))
    monkeypatch.setattr(Book, "quarter_nav_rows", frozen)

    assert nav(book.by_account()) == pytest.approx(now, abs=0.01), (
        f"{account}: today's net asset value moved when the baseline moved to {later}")
