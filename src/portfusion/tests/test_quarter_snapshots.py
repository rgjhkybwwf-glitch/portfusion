"""
THE FROZEN QUARTER SNAPSHOTS, checked against the ledger.

Q2 2026 is the opening point for the Q3 return, so what the book says was held at a
quarter end has stopped being a display question and become an input to a published
figure. This file reconstructs each quarter from the ledger and compares.

WHY THE LEDGER IS THE AUTHORITY HERE. It is the sourced event log — contract notes and
statements, one row per event. A frozen snapshot is a rendering of it made at a moment
in time, and a rendering can go stale when a trade is later corrected. That is exactly
what happened twice; both were cured when the quarter ends were restated on 14 Oct 2026, and
KNOWN below is where a next one would be explained.

THE BASELINE. The record was deliberately begun at 1 January 2026, so a leg with no
parseable date can only be PRE-BASELINE — it was already held when the book opened.
Seven legs are in that position and they are not a defect; treating them as one is how
you end up inventing dates for a boundary that was chosen on purpose.
"""
import re
from collections import defaultdict

import pytest

from portfusion.engine import Book
from quarter_support import frozen_quarters
from portfusion.record import rules as D
from harness import needs

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BASELINE = "2026-01-01"


def held_at(date, account=None):
    """Quantity per ticker actually held on `date`, from the event log. An account not yet open
    holds nothing (`rules.accounts_open()`), whatever its legs' deal dates."""
    qty = defaultdict(int)
    open_then = set(D.accounts_open(date))
    for t in D.buys:
        if ISO.match(t.date) and t.date > date:
            continue                        # not yet opened
        if (account and t.acct != account) or t.acct not in open_then:
            continue
        qty[t.ticker] += t.size
    for e in D.sales:
        if e.date > date or (account and e.acct != account) or e.acct not in open_then:
            continue
        qty[e.ticker] -= e.size
    return {k: v for k, v in qty.items() if v}


# ---------------------------------------------------------------------------------
# KNOWN DISCREPANCIES — explained, and deliberately NOT silently corrected.
#
# NONE IS OPEN. The last three — an account's Q1 snapshot (holdings missing, quantities from
# before the ledger's corrections), its Q2 snapshot (a holding missing), and a holding filed
# under another account's code — were cured on 14 Oct 2026, when the owner had the frozen
# quarter ends restated and Marlow Group folded to one code.
#
# Anything NOT in this list fails. That is the point: the known set is fixed and
# visible, so new drift cannot hide behind it.
# ---------------------------------------------------------------------------------
KNOWN: dict[tuple[str, str], str] = {}

QUARTERS = frozen_quarters()


def _accounts(rows):
    return sorted({r[0] for r in rows if r[1] != "(no positions)"})


@pytest.mark.parametrize("date,rows", QUARTERS,
                         ids=[Book.quarter_label(d) for d, _ in QUARTERS])
def test_snapshot_matches_the_ledger(date, rows):
    """Every account's frozen snapshot agrees with the event log, or is a KNOWN case.

    AN ACCOUNT THE SNAPSHOT LEAVES OUT ALTOGETHER IS COMPARED TOO: only the accounts it named were,
    so one omitted while it held positions was never checked. An explicit "(no positions)" row is
    the snapshot's own statement, with its reason beside it, and stands as stated: an account
    whose record begins after the quarter end says so in one."""
    problems = []
    named = {r[0] for r in rows}
    for acct in sorted(set(_accounts(rows))
                       | {a for a in D.ACCOUNT_ORDER if a not in named and held_at(date, a)}):
        snap = {r[1]: r[2] for r in rows if r[0] == acct and r[1] != "(no positions)"}
        led = held_at(date, acct)
        delta = ([f"missing {t}" for t in sorted(set(led) - set(snap))]
                 + [f"unexpected {t}" for t in sorted(set(snap) - set(led))]
                 # TO A BILLIONTH: a bet's stakes are decimals, and 1 + 1 + 0.8 - 1 is not 1.8 to
                 # the last binary place, which is a float's fact and not a disagreement.
                 + [f"{t} qty {snap[t]} vs ledger {led[t]}"
                    for t in sorted(set(snap) & set(led)) if abs(snap[t] - led[t]) > 1e-9])
        if delta and (date, acct) not in KNOWN:
            problems.append(f"{date} {acct}: " + "; ".join(delta))
    assert not problems, (
        "frozen snapshot disagrees with the ledger, and it is not a documented case:\n  "
        + "\n  ".join(problems))


# =====================================================================================
# A LATE ROW AND A FROZEN QUARTER END. `Book.frozen_drift()` says what one does and how it is
# put right; these hold the audit to it.
# =====================================================================================

@pytest.mark.audit
def test_every_quarter_end_frozen_from_the_engine_still_describes_the_record():
    """Empty, or the record has moved under a quarter end already frozen."""
    drift = Book().frozen_drift()
    assert drift.empty, (
        "a quarter end frozen from the engine no longer matches the record; restate it through "
        "the freeze door (desk/doors/freeze.py) once the owner agrees:\n"
        + drift.to_string(index=False))


@needs("quarter-snapshots")
def test_a_late_row_before_a_frozen_quarter_end_is_named(store_copy):
    """The audit above, shown to fire on the FIGURE: a fee three days before the newest
    spread-bet equity frozen from the engine, appended to a copied store as a late entry is.
    That equity takes every income row since the baseline."""
    import csv
    import datetime as _dt
    from portfusion.record import schema
    b = Book()
    qn = b.quarter_nav()
    ours = qn[qn["source"].str.contains(b.FROM_THE_ENGINE, regex=False)
              & (qn["contribution"] == "account equity") & (qn["amount"] != 0)]
    assert len(ours), "no spread-bet equity frozen from the engine: this asserts nothing"
    row = ours.sort_values("as_of").iloc[-1]
    q, account = str(row["as_of"])[:10], row["account"]
    assert b.frozen_drift().empty, "the record drifts before the late row is planted"

    path = schema.TABLES["income"].path
    header = schema.TABLES["income"].header
    lines = path.read_text(encoding="utf-8").splitlines()
    model = next(r for r in reversed(list(csv.reader(lines[1:])))
                 if r[header.index("account")] == account)
    late = dict(zip(header, model))
    late.update(date=(_dt.date.fromisoformat(q) - _dt.timedelta(days=3)).isoformat(),
                category="Fee", detail="a fee entered after the quarter end was frozen",
                amount="-12.34", local_amount="", rate="")
    with path.open("a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow([late[h] for h in header])
    D.reload_store()

    drift = Book().frozen_drift()
    named = drift[(drift["as_of"] == q) & (drift["account"] == account)]
    assert len(named) == 1 and named.iloc[0]["contribution"] == "account equity", drift
    assert abs(named.iloc[0]["now"] - (row["amount"] - 12.34)) < 0.01, \
        "the drift is not the late row's own amount"


def _missing_at_quarter_ends(qn) -> list[tuple[str, str]]:
    """(quarter end, account) for each account open at a frozen quarter end, with an event on or
    before it, and no quarter-nav row there."""
    from portfusion.record import schema
    first: dict[str, str] = {}
    for table in ("buys", "sales", "income", "capital-movements"):
        h = schema.TABLES[table].header
        for r in schema.load(table):
            d, a = str(r[h.index("date")])[:10], r[h.index("account")]
            first[a] = min(first.get(a, d), d)
    ends = qn["as_of"].astype(str).str[:10]
    return [(q, a) for q in sorted(set(ends)) for a, d in sorted(first.items())
            if d <= q and a in D.accounts_open(q) and a not in set(qn.loc[ends == q, "account"])]


@pytest.mark.audit
def test_no_account_with_history_is_missing_from_a_frozen_quarter_end():
    """`by_account()` opens an account with no row at the frozen 31 December at zero: true of one
    opened during the year, false of one that already held something (2 Oct 2026)."""
    missing = _missing_at_quarter_ends(Book().quarter_nav())
    assert not missing, f"held before a frozen quarter end and missing from it: {missing}"


@needs("quarter-snapshots")
def test_an_account_left_out_of_a_frozen_quarter_end_is_named():
    """The audit above, shown to fire: one account's row taken out of the newest quarter end."""
    qn = Book().quarter_nav()
    ends = qn["as_of"].astype(str).str[:10]
    q = max(ends)
    account = qn.loc[ends == q, "account"].iloc[0]
    assert not _missing_at_quarter_ends(qn)
    assert (q, account) in _missing_at_quarter_ends(qn[~((ends == q) & (qn["account"] == account))])
