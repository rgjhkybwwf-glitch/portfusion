"""THE FREEZE — a quarter end appended from the engine, once, at the marks nearest it."""
from __future__ import annotations

import datetime as _dt
import types

import pandas as pd
import pytest
from harness import needs, write_rows

_DAY = "2026-09-24"      # the IG legs are already marked this day on file; the shares are banked


def _as_if_due(monkeypatch, day=_DAY):
    from portfusion.engine import Book
    monkeypatch.setattr(Book, "quarter_to_close", staticmethod(lambda: pd.Timestamp(day)))


def _as_if_come(monkeypatch, day):
    """The freeze's clock reads `day`, so a day after today's marks has come. A refresh dates its
    marks today, and the day after them is tomorrow until it has passed."""
    from portfusion.desk.doors import freeze

    class _Today(_dt.date):
        @classmethod
        def today(cls):
            return _dt.date.fromisoformat(day)
    monkeypatch.setattr(freeze, "_dt", types.SimpleNamespace(
        date=_Today, datetime=_dt.datetime, timedelta=_dt.timedelta))


def _bank_the_day(day=_DAY):
    """Every share and rate closed on `day`, at the figures on file — what the Price Refresh's
    past-day mode banks."""
    from portfusion.record import rules as D
    from portfusion.desk.doors import marks
    src = f"TradingView 1D, session {day} close — test"
    contracts = set(D.LEG_CONTRACT.values())      # the IG legs bank by their own route
    prices = [{"mark_key": t, "price": p, "currency": c, "as_of": day, "source": src,
               "struck": "close", "at": ""}
              for t, p, c, *_ in D.CURRENT_PRICES if t not in contracts]
    rates = [{"currency": c, "as_of": day, "rate": r,
              "source": f"TradingView 1D FX_IDC:GBP{c}, session {day} close — test",
              "struck": "close"}
             for c, r, *_ in D.fx_rows if c not in D.RATE_CARRIED]
    marks.bank_closes(day, prices=prices, rates=rates)


@needs("quarter-nav", "current-prices")
def test_a_quarter_end_is_frozen_from_the_engine_and_journalled(store_copy, monkeypatch):
    """What a person once copied off HOLDINGS at a close, derived instead: one row per line,
    each account's contribution beside it, and the journal accounting for every row."""
    from portfusion.record import schema
    from portfusion.engine import Book
    from portfusion.desk.doors import freeze
    _bank_the_day()
    _as_if_due(monkeypatch)
    plan = freeze.plan(_DAY)
    assert plan["ready"], plan["why"] + plan["off_date"]

    out = freeze.write(_DAY)

    snaps = [r for r in schema.load("quarter-snapshots") if str(r[0]) == _DAY]
    navs = [r for r in schema.load("quarter-nav") if str(r[0]) == _DAY]
    assert (len(snaps), len(navs)) == (out["quarter_snapshots"], out["quarter_nav"])
    b = Book()
    for account in b.by_account(_DAY)["account"]:
        mine = [r for r in snaps if r[1] == account]
        pos = [r for r in navs if r[1] == account and r[3] in ("positions at market", "notional")]
        assert abs(sum(r[6] for r in mine) - pos[0][2]) < 0.02, account
    assert b.journal_unaccounted().empty, b.journal_unaccounted()
    journal = [r for r in schema.load("journal") if r[1] == "freeze"]
    assert {r[3] for r in journal} == {"quarter-snapshots", "quarter-nav", "quarter-results"}
    held = [r for r in schema.load("quarter-results") if str(r[0]) == _DAY]
    assert len(held) == out["quarter_results"] == 1 + len(b.by_account(_DAY)), held


@needs("quarter-nav", "current-prices")
def test_a_freeze_writes_in_each_files_own_line_ending(store_copy, monkeypatch):
    """The Q3 freeze rewrote quarter-snapshots.csv's CRLF lines as LF, a whole-file diff for a
    few-row write. Every line on file before must be there after, byte for byte and in its order,
    and every line in the file's own ending, wherever the new rows' dates put them."""
    from portfusion.record import schema
    from portfusion.desk.doors import freeze
    _bank_the_day()
    _as_if_due(monkeypatch)
    before = {t: schema.TABLES[t].path.read_bytes() for t in freeze.TABLES}
    freeze.write(_DAY)
    for table, original in before.items():
        after = schema.TABLES[table].path.read_bytes()
        eol = b"\r\n" if original.count(b"\r\n") * 2 > original.count(b"\n") else b"\n"
        assert after.count(b"\n") == after.count(eol), f"{table}.csv written in another ending"
        lines = iter(after.split(eol))
        assert all(line in lines for line in original.split(eol)), (
            f"{table}.csv was rewritten: a line on file before is not there after, as it was")


@needs("quarter-nav", "current-prices")
def test_a_quarter_is_frozen_once_and_only_when_due(store_copy, monkeypatch):
    from portfusion.desk.doors import freeze
    _bank_the_day()
    _as_if_due(monkeypatch)
    freeze.write(_DAY)
    assert "frozen once" in " ".join(freeze.plan(_DAY)["why"])
    with pytest.raises(freeze.Refused):
        freeze.write(_DAY)
    _as_if_due(monkeypatch, "2026-09-30")
    assert "not the quarter due" in " ".join(freeze.plan(_DAY)["why"])


@needs("quarter-nav", "current-prices")
def test_a_line_the_window_does_not_reach_stops_the_freeze_and_is_named(store_copy, monkeypatch):
    """With no window, a mark struck the day before the freeze day is another day's price, so
    the freeze names that line and refuses. The window is what lets it in.

    THE LINE AND THE DAY ARE THE LOADED BOOK'S OWN: any share mark on file, frozen one day
    after its date — skipping a frozen quarter end, where "frozen once" would refuse first
    and prove nothing about the window."""
    from portfusion.record import rules as D
    from portfusion.desk.doors import freeze
    monkeypatch.setattr(D, "CLOSE_CHECK_WINDOW_DAYS", 0)
    contracts = set(D.LEG_CONTRACT.values())
    frozen = {str(q.as_of) for q in D.QUARTER_NAV}
    line, dated = next(
        (t, str(a)[:10]) for t, _p, _c, a, *_ in D.CURRENT_PRICES
        if t not in contracts
        and (_dt.date.fromisoformat(str(a)[:10]) + _dt.timedelta(days=1)).isoformat()
        not in frozen)
    day = (_dt.date.fromisoformat(dated) + _dt.timedelta(days=1)).isoformat()
    _as_if_due(monkeypatch, day)
    _as_if_come(monkeypatch, day)
    plan = freeze.plan(day)
    assert not plan["ready"]
    assert any(line in named and dated in named for named in plan["off_date"])
    assert any(line in why and "Price Refresh" in why for why in plan["why"]), plan["why"]
    with pytest.raises(freeze.Refused, match="the Price Refresh"):
        freeze.write(day)


def test_the_close_window_admits_the_days_either_side(monkeypatch):
    """The same freeze with the window on file: the 23 Sep marks are a day from the 24th."""
    from portfusion.desk.doors import freeze
    _as_if_due(monkeypatch)
    assert freeze.plan(_DAY)["off_date"] == []


def _nearest(dates, day, window=7):
    """`_marks_at(day, window)` over a history holding one line, X, marked on `dates` at a price
    equal to each date's position in the list."""
    from portfusion.engine import Book
    b = Book()
    b.store = {**b.store, "history.prices": pd.DataFrame({
        "mark_key": "X", "date": dates, "price": [float(i) for i in range(len(dates))]})}
    return b._marks_at(day, window)[0].get("X")


def test_a_quarter_end_takes_each_lines_nearest_mark_either_side():
    """The owner, 30 Sep 2026: a quarter end is "close enough". Nearest wins in either direction,
    the earlier on a tie; beyond the window the newest on or before stands, for
    `freeze_rows()` to name."""
    assert _nearest(["2026-09-23", "2026-09-29"], "2026-09-24") == ("2026-09-23", 0.0)
    assert _nearest(["2026-09-23", "2026-09-29"], "2026-09-27") == ("2026-09-29", 1.0)
    assert _nearest(["2026-09-23", "2026-09-29"], "2026-09-26") == ("2026-09-23", 0.0)
    assert _nearest(["2026-09-01", "2026-10-20"], "2026-09-30") == ("2026-09-01", 0.0)
    assert _nearest(["2026-09-23", "2026-09-29"], "2026-09-27", window=None) == \
        ("2026-09-23", 0.0), "without a window a mark after the date is never taken"


def test_the_freeze_may_run_on_the_day_but_not_for_one_to_come(monkeypatch):
    import datetime as _dt
    from portfusion.desk.doors import freeze
    today = _dt.date.today()
    for day, refused in ((today, False), (today + _dt.timedelta(days=1), True)):
        _as_if_due(monkeypatch, day.isoformat())
        why = " ".join(freeze.plan(day.isoformat())["why"])
        assert ("has not come yet" in why) is refused, (day, why)


def test_an_account_holding_nothing_at_a_quarter_end_freezes_as_no_positions():
    """An account not yet funded at a quarter end values at nothing and is frozen as
    "(no positions)". `holdings_at()` once built that empty frame with no columns and raised
    KeyError 'value', so such a quarter end could not be frozen at all."""
    from portfusion.engine import Book
    from portfusion.record import rules as D
    b = Book()
    empty = [(q, a) for q in D.QSNAP_FROZEN for a in D.ACCOUNT_ORDER if b.as_of(q, a).empty]
    if not empty:
        pytest.skip("no account is empty at a frozen quarter end in this book")
    for q, a in empty:
        assert b.holdings_at(q, a).empty, (q, a)
    q = max(q for q, _ in empty)
    lines = b.freeze_rows(q)["quarter_snapshots"]
    assert {(s["account"], s["ticker"]) for s in lines} >= {(a, "(no positions)")
                                                            for d, a in empty if d == q}


# =====================================================================================
# A RESTATEMENT — a frozen quarter end struck again, superseding its rows
# =====================================================================================

def _a_frozen_share_line():
    """The loaded book's newest frozen quarter end and a share account holding something there."""
    from portfusion.engine import Book
    from portfusion.record import rules as D
    b = Book()
    q = max(D.QSNAP_FROZEN)
    account = next(a for a in D.ACCOUNT_ORDER
                   if not b.is_spread_bet(a) and not b.as_of(q, a).empty)
    return q, account


@needs("quarter-nav", "current-prices")
def test_a_restatement_replaces_the_rows_and_holds_the_quarter_again(store_copy, monkeypatch):
    """A correction replaces, at a quarter end too: the account's rows there give way to the ones
    struck again; the engine reads them; the quarter's results row is replaced, saying why; and the
    journal accounts for every row, with the reason. The engine's strike is moved by a fixed £100
    here, so the test holds the door's arithmetic on any book."""
    from portfusion.engine import Book
    from portfusion.record import schema
    from portfusion.desk.doors import freeze
    q, account = _a_frozen_share_line()
    real = Book.freeze_rows

    def moved(self, as_of, accounts=None, restated=None):
        rows = real(self, as_of, accounts=accounts, restated=restated)
        for r in rows["quarter_nav"]:
            r["amount"] = round(r["amount"] + 100.0, 2)
        rows["quarter_snapshots"][0]["value"] = round(
            rows["quarter_snapshots"][0]["value"] + 100.0, 2)
        return rows
    monkeypatch.setattr(Book, "freeze_rows", moved)
    hdr = schema.TABLES["quarter-nav"].header

    def mine():
        return [dict(zip(hdr, r)) for r in schema.load("quarter-nav")
                if str(r[0]) == q and r[1] == account]

    def results():
        return [dict(zip(schema.TABLES["quarter-results"].header, r))
                for r in schema.load("quarter-results") if str(r[0]) == q and r[1] == account]

    before, held = mine(), results()
    total = Book().quarter_nav_total()[q]
    # WHAT THE RECORD NOW STRIKES, which a frozen quarter end need not equal: the £100 is on top.
    delta = sum(r["amount"] for r in real(Book(), q, accounts=[account])["quarter_nav"]
                if r["contribution"] != "notional") + 100.0 - sum(
                    r["amount"] for r in before if r["contribution"] != "notional")

    out = freeze.restate({q: [account]}, "a test moved it")

    now = mine()
    assert len(now) == len(before), "a restated row was kept beside the one replacing it"
    assert all("restated on" in r["source"] for r in now)
    assert Book().quarter_nav_total()[q] == pytest.approx(total + delta, abs=0.01)
    [result] = results()
    assert result["note"] == "Restated: a test moved it"
    assert result["closing_nav"] == pytest.approx(held[0]["closing_nav"] + delta, abs=0.01)
    assert out["quarter_results"] >= 2, "the account's row and the book's"
    assert Book().journal_unaccounted().empty, Book().journal_unaccounted()
    said = [r for r in schema.load("journal") if r[1] == "freeze" and r[5] == f"restated {q}"]
    assert {r[3] for r in said} == set(freeze.TABLES)
    assert all(r[6].endswith("a test moved it") for r in said), "the journal does not say why"


def test_a_restatement_journals_a_changed_line_count_as_what_went_and_what_came():
    """A REPLACE ADDS NO ROWS, so only an equal count is one: a quarter end restated with a line
    more or fewer is journalled as the rows taken out and the rows put in, or the journal's count
    would not close."""
    from portfusion.desk.doors import freeze
    assert freeze._journalled("quarter-nav", "r", 2, 2, "why") == [
        ("freeze", "replace", "quarter-nav", 2, "r", "why")]
    assert freeze._journalled("quarter-snapshots", "r", 3, 2, "why") == [
        ("freeze", "remove", "quarter-snapshots", 3, "r", "why"),
        ("freeze", "append", "quarter-snapshots", 2, "r", "why")]


@needs("quarter-nav", "current-prices")
def test_a_restatement_that_moves_nothing_writes_nothing(store_copy, monkeypatch):
    """Struck again at the figures on file, an account is left as it is, and a restatement that
    leaves every account so is refused before a byte is written."""
    from portfusion.engine import Book
    from portfusion.record import schema
    from portfusion.desk.doors import freeze
    q, account = _a_frozen_share_line()
    nav = [dict(zip(schema.TABLES["quarter-nav"].header, r)) for r in schema.load("quarter-nav")]
    snap = [dict(zip(schema.TABLES["quarter-snapshots"].header, r))
            for r in schema.load("quarter-snapshots")]
    as_filed = {"off_date": [],
                "quarter_nav": [r for r in nav if str(r["as_of"]) == q and r["account"] == account],
                "quarter_snapshots": [r for r in snap if str(r["as_of"]) == q
                                      and r["account"] == account]}
    monkeypatch.setattr(Book, "freeze_rows", lambda self, *a, **k: as_filed)
    before = {t: schema.TABLES[t].path.read_bytes() for t in (*freeze.TABLES, "journal")}
    with pytest.raises(freeze.Refused, match="nothing would move"):
        freeze.restate({q: [account]}, "no reason to")
    assert before == {t: schema.TABLES[t].path.read_bytes() for t in before}


@needs("quarter-nav", "current-prices")
def test_a_composition_is_appended_where_there_was_none(store_copy):
    """THE OPENING'S COMPOSITION: the record's 31 Dec 2025 has net asset
    values and no lines, so its first quarter has no contributors. `lines_only` strikes the lines
    where none are frozen and appends them, and touches nothing else: no net asset value, no
    result, nothing replaced; asked again, it refuses. Held here on the newest frozen quarter
    end with its lines taken out of the copy."""
    import csv
    import datetime as _dt
    from portfusion.engine import Book
    from portfusion.record import rules as D, schema
    from portfusion.desk.doors import freeze
    q = max(D.QSNAP_FROZEN)
    path = schema.TABLES["quarter-snapshots"].path
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    with path.open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(r for r in rows if r[0] != q)
    D.reload_store()
    assert q not in D.QSNAP_FROZEN
    untouched = {t: schema.TABLES[t].path.read_bytes() for t in ("quarter-nav", "quarter-results")}
    # THE COPY'S OWN HAND REMOVAL IS UNJOURNALLED; the door must account for every row it adds.
    gap = Book().journal_unaccounted().set_index("table")["unaccounted"]
    want = Book().freeze_rows(q, accounts=list(D.ACCOUNT_ORDER),
                              restated=_dt.date.today().isoformat())["quarter_snapshots"]

    out = freeze.restate({q: list(D.ACCOUNT_ORDER)}, "the lines were never frozen", lines_only=True)

    assert out["quarter_snapshots"] == len(want) and out["quarter_nav"] == out["quarter_results"] == 0
    assert untouched == {t: schema.TABLES[t].path.read_bytes() for t in untouched}
    got = [r for r in D.QSNAP_ROWS if r[0] == q]
    assert len(got) == len(want) and q in D.QSNAP_FROZEN
    assert Book().journal_unaccounted().set_index("table")["unaccounted"].equals(gap), \
        Book().journal_unaccounted()
    with pytest.raises(freeze.Refused, match="composition on file"):
        freeze.restate({q: list(D.ACCOUNT_ORDER)}, "again", lines_only=True)


@needs("quarter-nav", "current-prices")
def test_the_records_opening_is_never_a_frozen_quarter(store_copy):
    """Lines frozen at the record's opening, the day before it begins, are what its first quarter
    is measured from: they open a quarter and close none. Labels, the close due and the report's
    gate count frozen quarters, so the opening is read through `quarter_lines()` and never joins
    `rules.QSNAP_FROZEN`."""
    import csv
    from portfusion.engine import BASELINE_ASOF, Book
    from portfusion.record import rules as D, schema
    path = schema.TABLES["quarter-snapshots"].path
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    # PLANTED WHERE NONE ARE ON FILE: a book with an opening composition already holds the case.
    if not any(r[0] == BASELINE_ASOF for r in rows[1:]):
        newest = max(D.QSNAP_FROZEN)
        write_rows("quarter-snapshots", *[dict(zip(rows[0], [BASELINE_ASOF, *r[1:]]))
                                          for r in rows[1:] if r[0] == newest])
        D.reload_store()
    assert BASELINE_ASOF not in D.QSNAP_FROZEN
    assert not Book().quarter_lines(BASELINE_ASOF).empty


@needs("quarter-nav", "current-prices")
def test_a_missing_mark_is_sent_where_it_can_be_had(store_copy, monkeypatch):
    """THE WAY IN FOR A LINE NO LONGER HELD. The Price Refresh's closes of a past
    day reach only the lines priced now, so a line closed since cannot be had there: its close is
    read in a session and banked through the marks door.
    A restatement the book cannot value names every gap at once, and each its way in."""
    from portfusion.engine import Book, MissingMark
    from portfusion.record import rules as D
    from portfusion.desk.doors import freeze
    now = next(t for t, *_ in D.CURRENT_PRICES)

    def unvalued(self, as_of, accounts=None, restated=None):
        raise MissingMark([now], f"no price for {now} on or before {as_of}")
    monkeypatch.setattr(Book, "freeze_rows", unvalued)
    monkeypatch.setattr(Book, "valuation_gaps",
                        lambda self, d: {"prices": [now, "GONE.L"], "rates": [], "other": []})
    q, account = _a_frozen_share_line()
    with pytest.raises(freeze.Refused) as refused:
        freeze.restate({q: [account]}, "a test")
    said = str(refused.value)
    assert f"{now}: the Price Refresh" in said, said
    assert "GONE.L: not priced now" in said and "bank_closes" in said, said


@needs("quarter-nav", "current-prices")
def test_a_restatement_refuses_what_it_cannot_say(store_copy):
    """No reason, no frozen row, or a day to come: refused, and nothing is struck."""
    import datetime as _dt
    from portfusion.desk.doors import freeze
    q, account = _a_frozen_share_line()
    with pytest.raises(freeze.Refused, match="says why"):
        freeze.restate({q: [account]}, "  ")
    with pytest.raises(freeze.Refused, match="no frozen row"):
        freeze.restate({"2026-02-14": [account]}, "a day that was never frozen")
    later = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
    with pytest.raises(freeze.Refused, match="has not come yet"):
        freeze.restate({later: [account]}, "tomorrow")

