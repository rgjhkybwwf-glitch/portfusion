"""
ACCOUNT STATEMENTS — the third append-only store.

The book held one snapshot per account, overwritten each time a statement arrived, so
"what was this account worth at 30 June" had no answer. That gap had a real cost: the
book concluded Q3 could publish no quarter return because no 30 Jun NAV existed. It
existed; it just had not been fetched.

The property these tests protect is the one that would be most expensive to lose:
A SPREAD-BET ACCOUNT CONTRIBUTES ITS EQUITY TO NAV, NEVER ITS NOTIONAL.
"""
import re
from collections import Counter

import pytest

from portfusion.history import accounts as A
from portfusion.record import rules as D
from harness import needs

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def rows():
    r = A.load()
    assert r, "account-statements.csv is empty or missing"
    return r


@needs("account-statements")
def test_spread_bet_accounts_contribute_equity_not_notional(rows):
    """Adding notional to money is the single most expensive mistake available against
    this record. A spread-bet row's NAV component must be its equity."""
    for r in rows:
        if D.ACCOUNT_KIND[r["account"]] == "spread bet":
            assert A.nav_component(r) == r["equity"], (
                f"{r['account']} at {r['as_of']} contributed something other than equity")
            if r["positions_value"]:
                assert A.nav_component(r) != r["positions_value"], (
                    f"{r['account']} at {r['as_of']} contributed NOTIONAL to NAV")


@needs("account-statements")
def test_cash_is_never_in_nav_for_a_share_account(rows):
    """CASH IS NOT IN NAV, at any date (the owner).

    The return is on capital deployed and does not chase cash, so nothing needs cash in NAV.
    Adding it from some date would make `nav_component` and `Book.by_account()` disagree about
    what NAV is from that day — a split that test_quarter_nav.py, which checks one against the
    other, would report as a defect.

    The assertion carries no date, which is its strength: cash is on the row, and the only
    thing stopping it reaching a total is that nothing adds it.
    """
    for r in rows:
        if D.ACCOUNT_KIND[r["account"]] != "spread bet":
            assert A.nav_component(r) == r["positions_value"], (
                f"{r['account']} at {r['as_of']} included cash in NAV")


@needs("account-statements")
def test_no_duplicate_statement_per_account_per_date(rows):
    """One reading per account per date: two would be two answers. A figure put right at the
    same date replaces the row it puts right."""
    dupes = [k for k, n in Counter((r["account"], r["as_of"]) for r in rows).items() if n > 1]
    assert not dupes, f"more than one statement for: {dupes}"


@needs("account-statements")
def test_every_row_names_a_source_and_a_known_quality(rows):
    bare = [(r["account"], r["as_of"]) for r in rows if not (r["source"] or "").strip()]
    assert not bare, f"rows with no source: {bare}"
    assert not {r["quality"] for r in rows} - set(A.QUALITIES)


@needs("account-statements")
def test_dates_are_iso(rows):
    assert not [r["account"] for r in rows if not ISO.match(r["as_of"])]


@needs("account-statements")
def test_every_account_is_covered_at_every_quarter_end(rows):
    """A quarter-end NAV is only meaningful if every account open then has a value at it. A
    missing account contributes silently nothing, which understates NAV and no check
    downstream would catch it. One not yet open (`rules.accounts_open()`) needs none: a 0.00
    statement standing in for it was the last of the stand-ins the quarter tables retired."""
    from portfusion.record import rules as D
    # THE DATES DERIVE from the quarter series, which also fixes a stale guard: the typed
    # list this replaces stopped at Q2 and never checked 30 Sep.
    dates = sorted({str(q.as_of) for q in D.QUARTER_NAV})
    assert dates, "no quarter series on file — this asserts nothing"
    for d in dates:
        covered = set(A.at(d, rows))
        missing = sorted(set(D.accounts_open(d)) - covered)
        assert not missing, f"no statement on or before {d} for: {missing}"


def test_the_usage_names_what_the_command_reads():
    """THE USAGE IS WHAT `main()` READS. It offered `--at DATE`, which no branch read, and
    `--nav [DATE]`, whose date was required; and `--nav` added the accounts' readings into a net
    asset value of its own, the one sum of accounts into net asset value outside the engine, until
    step 5. Summing accounts is the engine's; the desk's Accounts and Reconcile show the readings."""
    import ast
    import pathlib
    src = pathlib.Path(A.__file__).read_text(encoding="utf-8")
    main = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "main")
    read = {n.value for n in ast.walk(main)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("--")}
    offered = set(re.findall(r"--[a-z]+", A.__doc__ + ast.get_docstring(main)))
    assert offered == read, f"the usage offers {sorted(offered)}; main() reads {sorted(read)}"
    assert "--nav" not in read, "a sum of accounts into net asset value is the engine's"


@needs("account-statements")
def test_show_prints_a_reading_with_no_net_asset_value_part(monkeypatch, capsys):
    """`show()` dropped such a reading's whole line: its conditional bound the line, not the NAV
    suffix, until step 5. No reading on file lacks the part today, so this one is planted."""
    share = next(a for a in D.ACCOUNT_ORDER if D.ACCOUNT_KIND.get(a) != "spread bet")
    row = {"account": share, "as_of": "2026-06-30", "positions_value": None,
           "funds": None, "running_pl": None, "equity": None, "deposit": None,
           "source": "a planted reading", "quality": "sourced"}
    monkeypatch.setattr(A, "load", lambda: [row])
    A.show()
    out = capsys.readouterr().out
    assert "2026-06-30" in out and "positions —" in out, out
    assert "-> NAV" not in out


def test_the_build_does_not_import_this(build_imports):
    assert "history.accounts" not in build_imports


# =====================================================================================
# THE BANKING FLOOR — archive() and check(), as the other two histories have
#
# Without them an outgoing account observation could not be banked, and `marks.banked()` had
# nothing to ask about accounts. The bank-before-replace rule that marks.py keeps for a price
# and an FX rate had no equivalent here, which is how the reconciliation baseline once went
# eight days stale by hand edit with no guard noticing.
# =====================================================================================

@pytest.mark.audit
def test_every_live_observation_is_archived():
    """If an observation is replaced without archiving, the outgoing reading is gone.
    Fix: python3 -m portfusion.history.accounts --archive"""
    from portfusion.history import accounts as AH
    missing = AH.check()
    assert not missing, ("observations not in the history: "
                         + ", ".join(f"{m['account']} {m['as_of']}" for m in missing))


@needs("account-statements")
def test_an_observation_that_cannot_be_filed_is_reported_not_skipped():
    """THE FX BUG, WHICH THIS MODULE WAS WRITTEN KNOWING ABOUT.

    history/fx.py's live_marks() skipped a row whose period it could not parse, and check()
    asked only about the rows live_marks() RETURNED — so three refreshed rates were replaced in
    the record and banked nowhere while every check read clean. The skip is unavoidable: a row
    that cannot be described cannot be filed. What is avoidable is the silence.

    Asserted against a TAMPERED COPY of the live rows rather than the record, so the record
    is untouched and the test says nothing about today's data.
    """
    from portfusion.record import rules as D
    from portfusion.history import accounts as AH

    saved = D.ac_rows
    try:
        D.ac_rows = list(saved) + [saved[0]._replace(
            acct="Tampered", evidence="not-a-real-class", reference="")]
        reported = AH.unbankable()
        assert any(r["account"] == "Tampered" for r in reported), (
            "an observation with an unknown evidence class was skipped silently — "
            "the exact shape of the FX defect this function exists to prevent")
        assert all("Tampered" != r["account"] for r in AH.live_observations()), (
            "an unclassifiable observation reached live_observations(), where it would be "
            "banked with an invented quality")
        assert AH.check(), "check() did not surface the unbankable row"
    finally:
        D.ac_rows = saved

    assert not AH.check(), "the tampered row outlived the test"


@needs("account-statements")
def test_a_same_day_re_reading_at_other_figures_replaces_the_first(store_copy):
    """A SECOND READING OF ONE DAY WAS NEVER BANKED. The history keyed on (as_of, account) alone,
    so a re-read of the same day at other figures found its day on file and appended nothing:
    account-statements.csv went on holding the earlier figures, and the reading the book then
    showed was in no history (the review of 21 Oct 2026). Now the new one takes the earlier row's
    place, as a corrected mark does."""
    from portfusion.history import accounts as AH
    live = AH.live_observations()
    assert live, "the book has no bankable account reading"
    AH.archive(verbose=False)
    first = live[0]
    figure = "equity" if first["equity"] is not None else "positions_value"
    was = first[figure]
    moved = dict(first, **{figure: was + 1.0})

    new, replaced = AH._FILE.bank([moved])

    rows = [r for r in AH.load() if (r["as_of"], r["account"]) == (first["as_of"], first["account"])]
    assert [r[figure] for r in rows] == [was + 1.0], rows
    assert [r[figure] for r in replaced] == [was], replaced
    assert AH._FILE.unstruck([moved]) == [], "the re-reading still reads as unbanked"
    assert AH._FILE.unstruck([first]) == [first], "the reading it replaced reads as banked"
