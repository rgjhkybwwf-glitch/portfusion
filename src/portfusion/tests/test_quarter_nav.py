"""
NET ASSET VALUE AT EACH QUARTER END.

The rule these tests exist to protect: A SPREAD-BET ACCOUNT CONTRIBUTES ITS EQUITY,
NEVER ITS NOTIONAL. An IG statement prints both on one page, the notional several times the
equity, and the gap between them is the most expensive mistake available against a record.

An account's record may begin after the book's (accounts.csv `record_begins`): a quarter end before it
holds no row for the account, and its funds enter as a flow on the day.
"""
import re

import pytest

from portfusion.record import rules as D
from portfusion.engine import Book
from harness import an_account, holds, needs

#: The register's spread-bet accounts, BY KIND — B2 moved kind onto the register, and a
#: tuple of this book's names would judge another book's table against the wrong accounts.
SPREAD_BET = tuple(r[0] for r in D.register
                   if r[D.schema.TABLES["accounts"].header.index("held_as")] == "spread bet")


# The engine is the one implementation of these. These names keep the tests below reading as
# they always have while asking the live code.
NAV_TOTAL = Book().quarter_nav_total().to_dict()
EXPOSURE_TOTAL = Book().quarter_exposure_total().to_dict()


def test_spread_bet_accounts_contribute_equity_not_notional():
    """The table also carries spread-bet NOTIONAL rows, for the exposure series. Those are not
    a counter-example to this rule — they are the reason it has to be stated in terms of what
    reaches NAV rather than what appears in the table. A spread-bet account has exactly one row
    on a NAV basis, and that row is its equity."""
    for q in D.QUARTER_NAV:
        if q.contribution == "notional":
            assert q.account in SPREAD_BET, (
                f"{q.account} at {q.as_of} is on basis 'notional' — only a spread bet has "
                f"notional, and a securities account carrying one would leak into exposure")
            continue
        if q.account in SPREAD_BET:
            assert q.contribution == "account equity", (
                f"{q.account} at {q.as_of} contributes on {q.contribution!r} — a spread-bet account "
                f"contributes equity, never notional")
        else:
            assert q.contribution == "positions at market"


@needs("quarter-nav")
def test_a_notional_row_does_not_move_net_asset_value():
    """THE GUARD THAT FIRED. When the notional rows were added, both totals summed the table
    blind, and a quarter's NAV read the true figure plus the exposure. Exactly the
    July defect, arriving through the store instead of by hand. This asserts the totals stay
    apart by construction, not by the data happening to be all money; the 30 Jun figures
    themselves are held, figure for figure, by quarter-results.csv and its own test."""
    dates = sorted({q.as_of for q in D.QUARTER_NAV
                    if q.contribution == "notional" and q.amount})
    assert dates, "no quarter end carries a notional row — this asserts nothing"
    assert Book.NAV_BASES.isdisjoint({"notional"}), "notional never contributes to NAV"
    for d in dates:
        nav_rows = sum(q.amount for q in D.QUARTER_NAV
                       if str(q.as_of) == str(d) and q.contribution in Book.NAV_BASES)
        assert NAV_TOTAL[str(d)] == pytest.approx(round(nav_rows, 2)), (
            f"{d}: NAV must be the NAV-basis rows alone — a notional row has leaked into "
            f"the total, which is the July defect again")


@needs("quarter-nav")
def test_a_contribution_nobody_classified_stops_every_reader():
    """`_classified()` IS THE ONE PLACE quarter-nav.csv is checked: a contribution in neither
    NAV_BASES nor EXPOSURE_BASES must be neither summed nor dropped. A second reader of the rows
    skipped it until step 5, so the year's opening and every spread-bet account's baseline read
    past a row nobody had classified. Planted in memory, never on file."""
    import pandas as pd
    b = Book()
    q = b.store["quarter_nav"]
    stray = q[q["as_of"] == q["as_of"].min()].head(1).assign(contribution="unclassified")
    b.store["quarter_nav"] = pd.concat([q, stray], ignore_index=True)
    for read in (b.quarter_nav_total, b.by_account, b.ytd_window):
        with pytest.raises(ValueError, match="neither NAV_BASES nor EXPOSURE_BASES"):
            read()


def test_every_account_is_covered_at_every_quarter_end():
    """A missing account contributes silently nothing, which understates NAV and no
    downstream check would catch it. One that had not opened holds no row
    (`rules.accounts_open()`)."""
    for d in sorted(NAV_TOTAL):
        covered = {q.account for q in D.QUARTER_NAV if q.as_of == d}
        want = set(D.accounts_open(d))
        assert covered == want, f"{d}: missing {want - covered}, before opening {covered - want}"


@pytest.mark.parametrize("table, row", [
    ("quarter-nav", "{q},{a},0.00,account equity,derived,a stand-in"),
    ("quarter-snapshots", "{q},{a},(no positions),,,,0.00,0.00,derived,a stand-in"),
    ("quarter-results", "{q},{a},0.00,0.00,0.00,0.00,,,a stand-in")])
def test_a_row_before_its_account_opens_is_refused_on_load(store_copy, table, row):
    """AN ACCOUNT HOLDS NOTHING BEFORE IT OPENS, so a quarter end then has no row for it: a 0.00
    row standing in for that reads as a figure. The record will not load, naming the row."""
    from harness import append_rows
    if not D.ACCOUNT_BEGINS:
        pytest.skip("no account in this book opened after it")
    account, opens = next(iter(D.ACCOUNT_BEGINS.items()))
    before = [q for q in D.QSNAP_FROZEN if q < opens] or ["2025-12-31"]
    append_rows(store_copy / f"{table}.csv", [row.format(q=before[-1], a=account)])
    with pytest.raises(ValueError, match=rf"(?s)BEFORE ITS RECORD BEGINS.*{table}\.csv: {account} at"):
        D.reload_store()


@pytest.mark.parametrize("table", ["quarter-nav", "quarter-snapshots", "quarter-results"])
def test_a_quarter_end_written_twice_is_refused_on_load(store_copy, table):
    """A RESTATEMENT REPLACES ITS ROW, so a second row for one key is two answers to one question:
    a row copied beside itself by hand, and the record will not load, naming the table."""
    path = store_copy / f"{table}.csv"
    head, *lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        pytest.skip(f"the book holds no {table} row")
    path.write_text(head + lines[0] + "".join(lines), encoding="utf-8")
    with pytest.raises(ValueError, match=rf"(?s)FROZEN ONCE.*{table}\.csv"):
        D.reload_store()


def test_every_row_names_a_source_and_a_known_quality():
    """The vocabulary is `schema.QUALITIES`, read rather than restated — it says what each
    state means, and a copy here would permit whatever it had last been told."""
    from portfusion.record import schema
    assert not [q for q in D.QUARTER_NAV if not q.source.strip()]
    assert not {q.quality for q in D.QUARTER_NAV} - set(schema.QUALITIES)


def test_the_csv_store_agrees_with_the_record():
    """account-statements.csv and QUARTER_NAV hold the same facts. Two homes for one
    fact is how this project's worst defects have always started, so they are tied
    rather than trusted.

    ONLY A ROW COPIED FROM A STATEMENT, its quality `sourced`. A `derived` row is the engine's
    valuation at the quarter end (what the freeze writes), and its tie to the broker is the
    reconciliation inside `rules.CLOSE_CHECK_WINDOW_DAYS`, which `report/gate.py:completeness()`
    gates. The row says which it is, so no other file is asked: the journal once was, and a book
    whose journal began afresh had its engine's valuations tied to statements they never copied.
    A spread bet's notional is exposure, not NAV, and has no statement figure here."""
    from portfusion.history import accounts as A
    wrong = _untied(A.load())
    assert not wrong, wrong


def _untied(statements, rows=None) -> list[str]:
    """Each sourced quarter-NAV row its account's statement OF THAT DAY does not bear out. A
    statement of another day describes another day: the latest on or before the quarter end tied a
    row copied from a statement no longer on file to an older one's figure."""
    from portfusion.history import accounts as A
    of_day = {(s["account"], s["as_of"]): s for s in statements}
    wrong = []
    for q in D.QUARTER_NAV if rows is None else rows:
        if q.quality != "sourced" or q.contribution == "notional":
            continue
        on_file = of_day.get((q.account, str(q.as_of)))
        stated = None if on_file is None else round(A.nav_component(on_file), 2)
        if stated != round(q.amount, 2):
            wrong.append(f"{q.as_of} {q.account}: the record says {q.amount:,.2f}, its statement "
                         + ("of that day is not on file" if stated is None else f"{stated:,.2f}"))
    return wrong


@holds(an_account("shares"), what="a share account")
def test_a_statement_of_another_day_does_not_tie_a_quarter_end():
    """THE TIE ABOVE, shown to fire: a row copied from a share account's statement ties to that
    day's, and not to the same figure stated the day before."""
    row = D.QuarterNAV("2026-06-30", an_account("shares"), 1234.56, "positions at market",
                       "sourced", "a statement of 30 Jun")
    stated = {"account": row.account, "positions_value": 1234.56}
    assert _untied([{**stated, "as_of": "2026-06-30"}], [row]) == []
    assert _untied([{**stated, "as_of": "2026-06-29"}], [row]) == [
        f"2026-06-30 {row.account}: the record says 1,234.56, its statement of that day is not "
        f"on file"]


@needs("quarter-nav")
def test_the_desks_quarter_navs_are_the_records():
    """Performance's quarter series, every quarter end the record has, against the record: each
    is a quarter's closing net asset value, and the first is the first quarter's opening."""
    from portfusion.desk.panels import performance
    firm = {r["quarter"]: r for r in performance.data()["firm"]}
    # THE PAGE NAMES A QUARTER AND SENDS NO DATES, so each row is found by its
    # name and dated by the engine's frame, which keeps both bounds.
    series = Book().quarter_returns(include_open=True).to_dict("records")
    shown = {str(e["quarter_end"])[:10]: firm[e["quarter"]]["closing_nav"] for e in series}
    shown.setdefault(str(series[0]["opens"])[:10], firm[series[0]["quarter"]]["opening_nav"])
    assert set(NAV_TOTAL) <= set(shown), f"the series shows {sorted(shown)}"
    for d, nav in NAV_TOTAL.items():
        assert round(shown[d], 2) == nav, f"Performance's net asset value at {d}"


@needs("quarter-nav")
def test_a_quarter_return_only_exists_where_both_endpoints_have_a_nav():
    """Q1 and Q2 are COMPUTED (the owner). They are internal figures — Q3 2026 is the first
    period the book reports on.

    What replaced the old "nothing above Q3" rule is narrower and permanent: a return
    may only sit on a row where BOTH endpoints carry a net asset value, because a
    return measured from a blank is not a return. Every row of the series carries both
    ends, for the book and for each account, so the check is on the row itself.
    """
    b = Book()
    for frame in (b.quarter_returns(include_open=True),
                  b.account_quarter_returns(include_open=True)):
        assert len(frame), "the quarter series has no rows"
        for r in frame.to_dict("records"):
            if r["return"] == r["return"] and r["return"] is not None:
                for end in ("opening_nav", "closing_nav"):
                    assert r[end] == r[end] and r[end] is not None, \
                        f"{r.get('account', 'the book')} {r['quarter']} has a return and no {end}"


@needs("quarter-nav")
def test_q1_and_q2_are_computed():
    """Guards the instruction itself: these two were once blank by decision and are now
    expected to carry a figure."""
    q = Book().quarter_returns(include_open=True)
    seen = {str(r["quarter_end"])[:10]: r["return"] for r in q.to_dict("records")}
    for d in ("2026-03-31", "2026-06-30"):
        assert d in seen, f"{d} is not in the quarter series"
        assert isinstance(seen[d], float) and seen[d] == seen[d], f"no quarter return on {d}"


def test_the_published_methodology_says_what_the_formula_does():
    """The method ran Simple Dietz, every flow at the period midpoint, until 13 Oct 2026, and
    the Method page said so; since then each flow is weighted by the days after it — modified
    Dietz, day-weighted — and the page must say that, not the old formula, and not the
    time-weighting an early report claimed."""
    # The desk's Method page is the single home for methodology, so the claim is checked there.
    from portfusion.desk.panels import method
    joined = " ".join(r["text"] for s in method.data()["sections"] for r in s["rows"])
    assert "MODIFIED DIETZ" in joined.upper() and re.search(r"weighted by the days", joined)
    assert not re.search(r"time-weights external cash flows", joined), \
        "the method claims time-weighting, which this formula does not do"
    assert "Simple Dietz" not in joined and "midpoint" not in joined, \
        "the method describes the formula the book no longer runs"


# =====================================================================================
# THE REPORT QUOTES ONE BASIS
# =====================================================================================

def test_only_one_quarter_return_series_is_exposed():
    """THE RULE A REPORT DEFECT TAUGHT, kept after its subject was deleted.

    A report tab once quoted Performance's NET-INVESTED column for its quarterly series while
    the year-to-date beside it was on the NAV basis — two bases in one table, which the
    methodology forbids. What survives is structural: THE QUARTER SERIES EXPOSES EXACTLY ONE
    COLUMN THAT IS A QUARTER RETURN, and it is the NAV one, so a consumer asking for "the
    quarter return" cannot be handed the wrong series.

    The other half of that defect — an unreported quarter prints BLANK, never 0.00% — is a
    requirement on the report generator.
    """
    from portfusion.desk.panels import performance
    from portfusion.house.headings import heading
    heads = [heading("Performance", c) for c in performance.COLUMNS]
    returns = [h for h in heads if "return" in h.lower()]
    assert returns == ["Return"], (
        f"expected exactly one quarter-return column in the series, found {returns}. "
        f"Two would let a consumer pick the wrong basis, which is how the Q3 Report went wrong.")
    assert "net-invested" not in " ".join(heads).lower(), \
        "the net-invested series is back beside the net asset value series"


def test_no_renderer_names_simple_dietz(repo_root):
    """The book runs modified Dietz, day-weighted, whose formula `Book._dietz_row()` states. It
    ran Simple Dietz, every flow at the period midpoint, until 13 Oct 2026, and that name must
    not go on appearing where a reader meets the method: a renderer still saying it describes
    a figure the engine no longer makes.
    """
    from harness import SRC
    # THE PACKAGE'S RENDERERS, where they live. Read from the checkout's root this scanned two
    # folders that were not there, and passed on nothing.
    offenders = [str(f.relative_to(SRC))
                 for d in ("desk", "report") for f in (SRC / d).rglob("*")
                 if f.suffix in (".py", ".js", ".html") and "Simple Dietz" in f.read_text()]
    assert any((SRC / d).is_dir() for d in ("desk", "report")), "no renderer folder to scan"
    assert not offenders, f"these name a method the book no longer runs: {offenders}"


# =====================================================================================
# THE FLEXIBLE CLOSE — the broker's check may follow the quarter end by a few days
# =====================================================================================

def _statements(*rows):
    import pandas as pd
    return pd.DataFrame([{"account": a, "as_of": d, "positions_value": 1.0, "cash": 0.0,
                          "equity": None, "deposit": None, "source": "test", "quality": q}
                         for a, d, q in rows])


def test_a_reading_checks_the_quarter_it_follows_within_the_window(monkeypatch):
    """The first reading from the quarter end to CLOSE_CHECK_WINDOW_DAYS after it — never one
    before the quarter end, which describes a different book, and never one past the window."""
    from portfusion.engine import Book
    from portfusion.record import rules as D
    assert D.CLOSE_CHECK_WINDOW_DAYS == 7
    b = Book()
    monkeypatch.setattr(b, "statements", lambda: _statements(
        ("Rowe HL ISA", "2026-09-29", "sourced"),      # before: another book
        ("Rowe HL ISA", "2026-10-03", "sourced"),      # inside: this one
        ("Rowe HL ISA", "2026-10-05", "sourced"),      # inside, but not the first
        ("Voss ii ISA", "2026-10-08", "sourced"),    # one day past the window
        ("Voss ii Trading", "2026-09-30", "sourced")))  # on the day
    got = dict(zip(*[b.quarter_readings("2026-09-30")[c] for c in ("account", "as_of")]))
    assert got == {"Rowe HL ISA": "2026-10-03", "Voss ii Trading": "2026-09-30"}


def test_only_a_sourced_reading_confirms_a_frozen_quarter_end(monkeypatch):
    """A derived quarter end checked by a SOURCED reading in the window counts as observed, so
    the spread-bet return beside it is not blanked. A carried-back or reconstructed row
    confirms nothing — it would un-blank a closed quarter."""
    from portfusion.engine import Book
    b = Book()
    monkeypatch.setattr(b, "_quarter_quality", lambda account, as_of: "derived")
    monkeypatch.setattr(b, "statements", lambda: _statements(
        ("Rowe IG Spread bet", "2026-10-02", "sourced"),
        ("Voss IG Spread bet", "2026-10-02", "derived")))
    assert b._quarter_observed("Rowe IG Spread bet", "2026-09-30")
    assert not b._quarter_observed("Voss IG Spread bet", "2026-09-30")
    assert not b._quarter_observed("Rowe IG Spread bet", "2026-06-30")
