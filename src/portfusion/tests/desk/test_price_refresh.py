"""THE PRICE REFRESH — the marks door, the journal it writes, and the bay's rules."""
from __future__ import annotations

import datetime as _dt
import pytest
from portfusion.record import rules as _rules
from portfusion.desk import actions
from desk_support import SPREAD_BET_ACCOUNT, _ready, _static, all_crlf, to_crlf
from portfusion.desk.intake import bench as _bench
from harness import SRC, needs, require, desk_script

# THE LOADED BOOK'S OWN LINES, derived once. These doors only replace rows the book has, so
# every fixture row names whichever book is loaded rather than this one (docs/testing.md:
# one suite, any book). The figures on the rows stay invented — a write lands in a copy.
_CONTRACTS = set(_rules.LEG_CONTRACT.values())
_BY_TICKER = {r[0]: r for r in _rules.CURRENT_PRICES}
#: A replaceable share line: not a contract, not carried — the stand-in wherever one mark will do.
TICK = next((t for t in _BY_TICKER if t not in _CONTRACTS and t not in _rules.STATEMENT_PRICED),
            None)
TICK_CUR = _BY_TICKER[TICK][2] if TICK else None
#: Every door here replaces a row the book already has, so a book with no mark runs none of it.
#: A CURRENCY THE BOOK HOLDS A RATE FOR, never a typed one: a typed USD fails every rate test
#: here on a book priced in none.
RATE_CUR = next((r[0] for r in _rules.fx_rows if r[0] != "GBP"), None)

require(TICK, SPREAD_BET_ACCOUNT, RATE_CUR,
        what="a replaceable share mark, a spread-bet account and a foreign rate")


# =====================================================================================
# THE MARKS DOOR — a replace, beside commit.py's append
# =====================================================================================


def test_a_mark_is_replaced_and_the_row_count_does_not_move(store_copy):
    """A REPLACE, not an append — which is the whole difference from the other door."""
    from portfusion.record import schema
    from portfusion.desk.doors import marks

    was = schema.load("current-prices")
    row = {"mark_key": TICK, "price": 91.5, "currency": TICK_CUR, "as_of": "2026-09-04",
           "source": f"TradingView 1D {TICK}, session 2026-09-04 close — test", "struck": "close"}

    result = marks.write(prices=[row])

    now = schema.load("current-prices")
    assert len(now) == len(was), "a replace moved the row count"
    assert result["prices"] == 1
    landed = next(r for r in now if r[0] == TICK)
    assert landed[1] == 91.5 and landed[3] == "2026-09-04"


def test_a_crlf_table_is_written_back_in_crlf(store_copy):
    """THE FILE'S OWN LINE ENDING: a CRLF file comes back CRLF, or every line shows as
    changed."""
    from portfusion.record import schema
    from portfusion.desk.doors import marks
    to_crlf("current-prices")
    before = schema.TABLES["current-prices"].path.read_bytes().split(b"\r\n")
    marks.write(prices=[{"mark_key": TICK, "price": 91.5, "currency": TICK_CUR,
                         "as_of": "2026-09-04", "struck": "close",
                         "source": f"TradingView 1D {TICK}, session 2026-09-04 close — test"}])
    assert all_crlf("current-prices"), "the marks door wrote a CRLF table back as LF"
    after = schema.TABLES["current-prices"].path.read_bytes().split(b"\r\n")
    assert sum(a != b for a, b in zip(before, after)) == 1, "more than the one line moved"


def test_a_rate_replaces_its_own_line_and_every_other_line_is_byte_identical(store_copy):
    """A refresh replaces LINES: the currency it was given, and every other line passed through
    as the bytes it read, so a diff of fx.csv shows the rates that moved and nothing else."""
    from portfusion.record import schema
    from portfusion.desk.doors import marks

    path = schema.TABLES["fx"].path
    before = path.read_text(encoding="utf-8").splitlines()

    marks.write(rates=[{"currency": RATE_CUR, "as_of": "2026-09-04", "rate": 1.3611,
                        "source": f"TradingView quote FX_IDC:GBP{RATE_CUR}, live at 2026-09-04T14:00:00Z — test",
                        "struck": "live"}])

    after = path.read_text(encoding="utf-8").splitlines()
    assert len(before) == len(after)
    moved = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(moved) == 1, f"lines {moved} changed; only the {RATE_CUR} line should have"
    assert after[moved[0]].startswith(f"{RATE_CUR},")


def _the_desk_reads(monkeypatch):
    """The desk's Book rebuilt over the record as patched, and cached at the store's own time, so
    a panel reads the patch and no reload wipes it (`desk.engine.book()`)."""
    from portfusion import engine as E
    from portfusion.desk import engine as desk
    monkeypatch.setitem(desk._cache, "key", desk.store_mtime())
    monkeypatch.setitem(desk._cache, "book", E.Book())


@pytest.fixture
def one_carried_rate(monkeypatch):
    """A currency carried by decision, injected. A carry is a setting (settings.csv
    `rate_carried`, read as rules.RATE_CARRIED) rather than prose in a source cell, and none is
    carried by default, so the witness is planted on a
    currency fx.csv holds, with the record's own reason."""
    from portfusion.record import rules as R
    currency = R.fx_rows[0][0]
    monkeypatch.setattr(R, "RATE_CARRIED", {currency: R.RATE_CARRIED_WHY})
    _the_desk_reads(monkeypatch)
    return currency


def test_a_carried_line_is_refused_by_name_and_by_reason(store_copy, one_carried_rate):
    """A refresh must not quietly undo a decision about what the book has stopped watching."""
    from portfusion.desk.doors import marks

    assert one_carried_rate in marks.carried()
    with pytest.raises(marks.Refused) as e:
        marks.write(rates=[{"currency": one_carried_rate, "as_of": "2026-09-04", "rate": 12.9,
                            "source": "test", "struck": "live"}])
    assert "carried" in str(e.value) and "nothing the book values" in str(e.value), \
        "the refusal does not carry the reason the line is held"


def test_a_mark_without_a_source_and_a_date_together_is_refused(store_copy):
    """RULE 1 OF docs/prices.md, ENFORCED HERE.

    A stale price wearing today's date is worse than a stale price, because the freshness
    indicator then agrees everything is fine.
    """
    from portfusion.desk.doors import marks
    for missing in ("as_of", "source"):
        row = {"mark_key": TICK, "price": 91.5, "currency": TICK_CUR,
               "as_of": "2026-09-04", "source": "a source", "struck": "close"}
        row[missing] = ""
        with pytest.raises(marks.Refused) as e:
            marks.write(prices=[row])
        assert missing in str(e.value)


def test_a_price_that_does_not_say_which_instant_it_describes_is_refused(store_copy):
    """`struck` and `at` are the FEED'S. A price typed into the form says neither, and nothing
    is typed; a live read without its instant, or with one on another day, is the
    stale-level-wearing-a-fresh-date failure in a new column."""
    from portfusion.desk.doors import marks
    base = {"mark_key": TICK, "price": 91.5, "currency": TICK_CUR, "as_of": "2026-09-04",
            "source": "a source"}
    for over, says in (
        ({}, "struck"),
        ({"struck": "live"}, "UTC instant"),
        ({"struck": "live", "at": "2026-09-03T12:00:00Z"}, "dated"),
        ({"struck": "close", "at": "2026-09-04T21:00:00Z"}, "carries no instant"),
    ):
        with pytest.raises(marks.Refused) as e:
            marks.write(prices=[{**base, **over}])
        assert says in str(e.value), (over, str(e.value))


def test_a_live_read_is_dated_by_its_uk_day_and_lands_with_its_instant(store_copy):
    """23:30 UTC in summer is 00:30 the next UK day — the book's day. The instant itself is
    kept in UTC, exactly as the feed gave it."""
    from portfusion.record import schema
    from portfusion.desk.doors import marks
    marks.write(prices=[{"mark_key": TICK, "price": 91.5, "currency": TICK_CUR,
                         "as_of": "2026-09-04", "source": "a live read — test",
                         "struck": "live", "at": "2026-09-03T23:30:00Z"}])
    landed = dict(zip(schema.TABLES["current-prices"].header,
                      next(r for r in schema.load("current-prices") if r[0] == TICK)))
    assert (landed["struck"], landed["at"]) == ("live", "2026-09-03T23:30:00Z")


@pytest.mark.parametrize("prices, rates", [
    ([{"mark_key": TICK, "price": 91.5, "currency": TICK_CUR, "as_of": "2026-09-04",
       "source": "fine", "struck": "close"}],
     [{"currency": "XXX", "as_of": "2026-09-04", "rate": 1.0, "source": "names no row",
       "struck": "live"}]),
    ([{"mark_key": "NOT-A-ROW", "price": 1.0, "currency": RATE_CUR, "as_of": "2026-09-04",
       "source": "names no row", "struck": "close"}], None),
], ids=["a rate naming no row", "a price naming no row"])
def test_a_refused_write_leaves_every_file_as_it_was(store_copy, prices, rates):
    """THE ENVELOPE, ON THIS DOOR: the two tables, the two histories they are banked into and the
    journal are left byte for byte as they were. The outgoing mark is unbanked first, so the bank
    has something to take back."""
    from portfusion.history import prices as PH
    from portfusion.desk.doors import marks
    live = {(m["mark_key"], m["date"]) for m in PH.current_marks() if m["mark_key"] == TICK}
    PH.save([r for r in PH.load() if (r["mark_key"], r["date"]) not in live])
    before = {p: p.read_bytes() for p in marks.paths() if p.is_file()}

    with pytest.raises(marks.Refused):
        marks.write(prices=prices, rates=rates)

    moved = [p.name for p, was in before.items() if p.read_bytes() != was]
    assert not moved, f"a refused write left these files changed: {moved}"


@pytest.mark.parametrize("rates", [None, [{"currency": "XXX", "as_of": "2026-09-07", "rate": 1.0,
                                            "source": "names no row", "struck": "live"}]],
                         ids=["refused before a write", "refused after the price landed"])
def test_a_refused_write_does_not_even_move_the_mtime(store_copy, rates):
    """Restoring identical bytes changes the MTIME, and `engine.freshness()` reads the store's
    newest mtime — so a refused write would make the desk's header announce "store changed" when
    nothing had. Byte-comparing the files, which is what every other test here does, passes on that
    happily. Refused before anything is written, and refused after the price has landed, when the
    rollback rewrites the table.

    A guard that reports a change it caused is worse than no guard.
    """
    from portfusion.desk.doors import marks

    price = {"mark_key": TICK if rates else "NOT-A-ROW", "price": 1.0,
             "currency": TICK_CUR if rates else RATE_CUR, "as_of": "2026-09-07",
             "source": "a refused write", "struck": "close"}
    before = {p: p.stat().st_mtime_ns for p in marks.paths() if p.is_file()}

    with pytest.raises(marks.Refused):
        marks.write(prices=[price], rates=rates)

    moved = [p.name for p, ns in before.items() if p.stat().st_mtime_ns != ns]
    assert not moved, f"a refused write touched {moved}: the desk will report the store as changed"


@pytest.mark.parametrize("fault", [RuntimeError, SystemExit])
def test_a_fault_mid_write_puts_back_the_files_and_the_record_in_memory(store_copy, monkeypatch,
                                                                        fault):
    """A FAULT, NOT A REFUSAL. Anything a write raises puts back the files and the record in
    memory. Here the mark lands, the record reloads with it, and then the write fails. An exit
    too, which `except Exception` lets past: the record raises one when a store goes incomplete,
    and it goes on once the files and the record are back."""
    from portfusion.record import rules as D, schema
    from portfusion.desk.doors import marks
    path = schema.TABLES["current-prices"].path
    before = path.read_bytes()
    was = {r[0]: r[1] for r in D.CURRENT_PRICES}[TICK]
    real = marks.write

    def write_then_fail(**kw):
        real(**kw)
        raise fault("the disk went away")
    monkeypatch.setattr(marks, "write", write_then_fail)

    def write():
        return marks.refresh(prices=[{
            "mark_key": TICK, "price": was + 1, "currency": TICK_CUR, "as_of": "2026-09-04",
            "struck": "close", "source": f"TradingView 1D {TICK}, session 2026-09-04 close — test"}])

    if fault is SystemExit:
        with pytest.raises(SystemExit):
            write()
    else:
        out = write()
        assert out["ok"] is False and "the disk went away" in out["refused"], out
    assert path.read_bytes() == before, "the files were not put back"
    assert {r[0]: r[1] for r in D.CURRENT_PRICES}[TICK] == was, \
        "the record in memory kept a mark the files no longer hold"


def test_the_outgoing_mark_is_banked_before_the_new_one_lands(store_copy):
    """THE ORDERING feeds/refresh.py EXISTS TO MAKE INSEPARABLE, enforced by this door rather than
    by anyone remembering: a mark replaced before it is banked is lost for good."""
    from portfusion.history import prices as PH
    from portfusion.desk.doors import marks

    outgoing = {(m["mark_key"], m["date"]) for m in PH.current_marks()}
    marks.write(prices=[{"mark_key": TICK, "price": 91.5, "currency": TICK_CUR,
                         "as_of": "2026-09-04", "source": "test", "struck": "close"}])

    banked = {(r["mark_key"], r["date"]) for r in PH.load()}
    assert outgoing <= banked, "an outgoing mark was replaced without being banked first"
    # THE FIGURE, not just the day: the book may already hold a banked close for this line on
    # this date, and (ticker, date) alone would then pass with the write's own bank skipped.
    assert any(r["mark_key"] == TICK and r["date"] == "2026-09-04" and r["price"] == 91.5
               for r in PH.load()), "the incoming mark was not banked after the write"


def test_the_written_mark_is_visible_to_the_engine_without_a_restart(store_copy):
    """WRITING THE CSV IS ONLY HALF OF REPLACING A MARK.

    `rules.CURRENT_PRICES` and `rules.fx_rows` are module-level and read ONCE at import, and
    `engine.load_store()` takes prices and FX from those attributes rather than from the files.
    A long-lived desk would therefore go on serving the mark it had just replaced, however many
    times the engine was rebuilt, with nothing on the page saying so.
    """
    from portfusion.record import rules as _rules
    from portfusion.desk.doors import marks

    marks.write(prices=[{"mark_key": TICK, "price": 91.5, "currency": TICK_CUR,
                         "as_of": "2026-09-04", "source": "test", "struck": "close"}])

    live = {r[0]: r[1] for r in _rules.CURRENT_PRICES}
    assert live[TICK] == 91.5, \
        "the record in memory still holds the old mark — the write is invisible to the engine"


def test_a_carried_rate_is_flagged_by_the_engine_and_carries_its_reason(one_carried_rate):
    """A decision the code cannot read is a decision the code eventually breaks: the bay would
    ask for a rate nobody intends to supply unless the returned shape says otherwise."""
    from portfusion import engine
    rates = {r["currency"]: r for r in engine.Book().marks_replaceable()["fx"]}
    assert rates, "no live rates at all"
    carried = [r for r in rates.values() if r["carried"]]
    assert [r["currency"] for r in carried] == [one_carried_rate]
    for rate in carried:
        assert rate["why"], f"{rate['currency']} is carried with no reason on it"
    for rate in rates.values():
        assert rate["carried"] == (rate["why"] is not None), \
            f"{rate['currency']}: carried and its reason disagree"


def test_a_live_rate_says_how_old_it_is_as_a_price_does():
    """THE THREE GROUPS ON THE PRICE REFRESH READ ALIKE: a price, an IG account and a rate each show
    their outgoing date and its age. The engine ages a live rate's as_of against the same today as a
    price's; a value that is no date is left without an age rather than given a guessed one."""
    import pandas as pd
    from portfusion import engine
    from portfusion.record import rules as D
    can = engine.Book().marks_replaceable()
    today = pd.Timestamp(can["today"])
    dated = [r for r in can["fx"] if r["as_of"] is not None]
    assert dated, "no live rate carries a date — this asserts nothing"
    as_of = {cur: day for cur, _rate, day, *_ in D.fx_rows}
    for r in can["fx"]:
        day = pd.to_datetime(as_of[r["currency"]], errors="coerce")
        if pd.isna(day):
            assert r["as_of"] is None and r["age_days"] is None, r
        else:
            assert r["as_of"] == day.date().isoformat(), r
            assert r["age_days"] == (today - day).days, r


def test_a_typed_figure_sits_on_the_line_of_a_fetched_one():
    """A rate the sweep left unpriced opens for typing, its text on the column of fetched figures
    above it. The box reaches into the cell's padding by its own padding, on the side the column's
    text is set to."""
    import re
    css = (SRC / "desk" / "static" / "app.css").read_text()
    left = re.search(r'#rb-form td input:not\(\[readonly\]\)[^{]*\{([^}]*)\}', css).group(1)
    right = re.search(r"#rb-form td\.num input:not\(\[readonly\]\) \{([^}]*)\}", css).group(1)
    assert "padding-left: var(--space-2)" in left and "margin-left: calc(-1 * var(--space-2))" in left
    assert "margin-right: calc(-1 * var(--space-2))" in right


def test_the_engine_still_imports_nothing_new_for_the_refresh_set():
    """marks_replaceable() needs today's date and takes it from pandas rather than importing datetime —
    `engine/` imports only the record, `house` and pandas, and that is asserted elsewhere.
    Named here too because it is the constraint that shaped the function."""
    from portfusion import engine
    assert "datetime" not in {n.split(".")[0] for n in dir(engine) if not n.startswith("_")}
    assert engine.Book().marks_replaceable()["today"] == _dt.date.today().isoformat()


# =====================================================================================
# BOTH DOORS WRITE THE JOURNAL, IN THE SAME OPERATION
#
# `store/journal.csv` is record time — when the book LEARNED a thing. Its whole value rests on
# a claim these tests make from the door end: a write to the record cannot happen without a
# journal row, and a refused write cannot leave one behind. `tests/record/test_journal.py` holds the
# table's own shape and arithmetic; this is the half that exercises the doors.
# =====================================================================================

def _journal(store):
    from portfusion.record import schema
    header = schema.TABLES["journal"].header
    return [dict(zip(header, r)) for r in schema.load("journal")]


def test_a_committed_item_lands_in_the_journal_as_well_as_the_record(
        item, store_copy, tmp_path, monkeypatch):
    """RECORD TIME IS WRITTEN BY THE SAME OPERATION THAT WRITES THE RECORD.

    An item that reached `buys.csv` without reaching the journal would make the check report
    a hand edit that never happened — and worse, it would make the journal's silence
    meaningless, because a missing row could mean either "nobody wrote this" or "the door
    forgot". The whole table is only worth having if this cannot happen.

    THE INSTANT IS THE ARCHIVE'S. `written_at` is computed once, before the envelope opens, and
    goes to the journal, the archived item and the summary — so `test_journal.py`'s comparison
    of the two is comparing one fact rather than two clock readings a second apart.
    """
    from portfusion.desk.doors import commit as _commit
    was = len(_journal(store_copy))

    result = _commit.commit(_bench.save(_ready(item))["id"])

    rows = _journal(store_copy)
    new = rows[was:]
    assert new, "the commit wrote the record and not the journal"
    assert all(r["ref"] == item["id"] for r in new), \
        "the journal must name the item that retrieves the write"
    assert all(r["at"] == result["written_at"] for r in new), (
        "the journal and the summary disagree about when this landed; they are one write")

    # TWO ROWS, AND THE SECOND ONE IS THE POINT. This item opens a position, so it writes the
    # trade AND appends its thesis to reasoning.csv. Unjournalled, the check would find a row no
    # route accounts for.
    # A `replace` beside them is a renumbering, where the trade's date falls before others.
    assert {(r["op"], r["table"], r["rows"]) for r in new if r["op"] == "append"} == {
        ("append", "buys", 1), ("append", "reasoning", 1)}
    from portfusion.record import rules
    from portfusion import engine
    rules.reload_store()
    assert engine.Book().journal_unaccounted().empty, "the journal no longer accounts for the store"


def test_a_refused_commit_leaves_the_journal_exactly_as_it_was(
        item, store_copy, tmp_path, monkeypatch):
    """THE OTHER HALF, AND THE REASON THE APPEND IS INSIDE THE ENVELOPE.

    A journal row for a write that was rolled back is worse than no row: it asserts the record
    holds something it does not, and the check would then report a row MISSING from the store.
    `envelope.atomic()` holds journal.csv among its targets, so a failure takes both.
    """
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit, envelope
    before = schema.TABLES["journal"].path.read_bytes()

    real = envelope.rendered
    monkeypatch.setattr(envelope, "rendered", lambda tbl, v: real(tbl, v)[:-1])
    with pytest.raises(Exception):          # the truncated row fails at the LOADER, not a gate
        _commit.commit(_bench.save(_ready(item))["id"])

    assert schema.TABLES["journal"].path.read_bytes() == before, \
        "a refused commit left a journal row claiming a write that did not happen"


def test_a_replaced_mark_is_journalled_as_a_replace_and_not_as_an_arrival(store_copy):
    """`op` IS LOAD-BEARING HERE, and this is the test that says why.

    A refresh replaces marks and adds no rows. Journalled as `append`, one fortnightly refresh
    would make the check report twelve rows arriving in a table whose length never moved — and
    a check that fires on ordinary work is one that teaches its reader to skip the line.

    THE REF IS THE MARK DATE, because that is what retrieves the write: every replaced row
    carries that `as_of`, and `price-history.csv` holds the value each one displaced.
    """
    from portfusion.record import schema
    from portfusion.desk.doors import marks
    was = len(_journal(store_copy))
    marks.write(prices=[{"mark_key": TICK, "price": 91.5, "currency": TICK_CUR,
                         "as_of": "2026-09-04", "source": "AV close 4 Sep", "struck": "close"}])

    rows = _journal(store_copy)
    assert len(rows) == was + 1
    row = rows[-1]
    assert (row["route"], row["op"], row["table"]) == ("marks", "replace", "current-prices")
    assert row["rows"] == 1
    assert row["ref"] == "2026-09-04", "the journal must name the date that retrieves the marks"
    assert len(schema.load("current-prices")) == \
        sum(1 for _ in schema.TABLES["current-prices"].path.read_text().splitlines()[1:]), \
        "sanity: a replace did not change the row count"


# =====================================================================================
# THE BAY'S TWO CONVENIENCES, AND THE RULE NEITHER MAY BEND
# =====================================================================================

def test_take_all_can_only_ever_tick_a_line_the_form_already_allows():
    """SELECT-ALL IS A SHORTCUT THROUGH THE CLICKING, NEVER THROUGH THE RULE.

    Fetching the IG levels fills a row per contract at once, and one click takes them all rather
    than a click per row to accept one machine answer. What must not come with it is a way past rule
    1 of `docs/prices.md`: a line without its figure, its date AND its source cannot be ticked one
    at a time, so it must not become tickable in a batch.

    The handler filters on `!b.disabled`, and `retick()` is the only thing that sets `disabled`
    — from `complete(tr)`, which requires every field. So the shortcut reaches exactly the rows
    the form had already opened, and this reads that filter rather than trusting the comment
    beside it.
    """
    js = desk_script()
    import re
    m = re.search(r'const kind = e\.target\?\.dataset\?\.all;(.*?)\n    \}\);', js, re.S)
    assert m, "app.js no longer wires a take-all handler this test can read"
    body = m.group(1)
    assert "!b.disabled" in body, (
        "take-all no longer filters on the row being enabled — it could tick a line with no "
        "source, which is the one thing the bay exists to refuse")
    assert "data-all" in js and js.count('data-all="') >= 1

    # ONE PER GROUP, NOT ONE FOR THE PAGE. Prices, rates and the IG accounts arrive by different
    # routes and are finished at different moments — the contracts come from the broker while the
    # shares are still being typed — so one control over all of them would tick a half-typed
    # column. The three share one table, and each group row carries its own.
    for label, kind in (("Prices", "price"), ("Rates", "rate"), ("IG accounts", "reading")):
        assert f'group("{label}", "{kind}"' in js, f"{label} has no group, and so no take-all"
    assert "${takeAll(kind)}" in js, "a group row no longer carries its own take-all"


def test_the_header_box_reports_its_column_rather_than_claiming_it():
    """A select-all showing "on" over a half-ticked column is a control lying about the thing it
    controls. It follows: checked only when every takeable row is taken, indeterminate when some
    are, disabled while none can be."""
    js = desk_script()
    for state in ("all.indeterminate", "all.checked", "all.disabled"):
        assert state in js, f"the take-all no longer sets {state}"


def test_a_written_refresh_moves_to_what_changed_and_a_refused_one_does_not():
    """THE LOOP ENDS WHERE IT IS REPORTED: bay writes, What Changed says what it did.

    A REFUSAL MUST NOT MOVE. The refusal names the line and the rule that stopped it — which is
    the only thing worth reading at that moment — and navigating away would throw it away. The
    early return is what guarantees it, so this reads for the return rather than for the
    navigation alone.
    """
    js = desk_script()
    import re
    m = re.search(r'if \(error\) \{\s*out\.textContent = refused \? `refused(.*?)\n        \}',
                  js, re.S)
    assert m, "the refusal branch no longer returns before anything else happens"
    assert "return;" in m.group(1), "a refused write no longer stops before navigating"
    assert 'openPanel("what-changed")' in js, "a written refresh no longer moves to What Changed"
    assert "LAST_REFRESH" in js, "the receipt is no longer carried to the destination"


def test_a_write_button_is_never_offered_without_something_to_write():
    """AN ACTION STRIP OFFERS ONLY WHAT CAN BE PRESSED NOW.

    A write means something only against lines that have been fetched and ticked, so its button
    is rendered by the form that holds them — #rb-write in the bay — and never by an action
    strip, where pressed alone it posts an empty body and is refused.

    ASSERTED ON THE SOURCE, because this is a rendering rule and no Python object holds it.
    """
    js = desk_script()
    assert 'wireActions("bench")' in js, "the Bench offers every standing button it has"
    assert 'wireActions("accounts"' not in js, "Reconcile has no standing button to offer"
    # THE RESTART IS THE SHELL'S, not a Bench button: the rail draws it on every page, so the
    # Bench's strip has no list to keep it off with.
    from portfusion.desk import actions
    assert actions.get("restart-desk").panel == "desk"
    assert "restart-desk" not in [a.name for a in actions.all_actions() if a.panel == "bench"]

    # The write action is reachable, and not offered as a standing panel button.
    assert 'runAction("refresh-write-marks"' in js, "the bay must post its ticked marks"


# =====================================================================================
# THE PRICE REFRESH'S LABELS
# =====================================================================================

@needs("accounts", "account-readings", "buys")
def test_the_bay_says_what_it_can_replace_rather_than_what_is_due():
    """THE BAY LISTS WHAT IT CAN REPLACE, and nothing calls those lines "due".

    The LIST is the whole set, never filtered by age: docs/prices.md's rule is that the book is
    refreshed whole or not at all. The step says the marks' age against the limit, as the
    Dashboard does, and a line past the limit says so in its own row.
    """
    from portfusion import engine
    js = desk_script()
    assert "price(s) due" not in js, "step 3 calls the replaceable lines due again"
    assert "limit ${d.age_limit} days" in js, "step 3 does not say what the threshold is"

    can = engine.Book().marks_replaceable()
    assert can["age_limit"] == _rules.PRICE_AGE_LIMIT
    assert can["replaceable"], "nothing is replaceable — this asserts nothing"
    for row in can["replaceable"]:
        assert row["stale"] == (row["age_days"] > can["age_limit"]), \
            f"{row['ticker']}: stale and its age disagree"


def test_the_age_limit_lives_where_the_classification_does(build_sources, repo_root):
    """A limit kept in a renderer is one `book.marks_replaceable()` — which decides whether a
    mark is old — cannot read, because `engine/` imports the record, `house` and pandas and
    nothing else; the engine would have no threshold and call everything due. The limits are the
    record's, and neither renderer — the report nor the desk — holds a name of its own for
    either."""
    import ast
    renderers = [*build_sources, *sorted((SRC / "desk").rglob("*.py"))]
    copies = [f"{f.relative_to(repo_root)}:{n.lineno}" for f in renderers
              for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
              if isinstance(n, (ast.Assign, ast.AnnAssign))
              and any(getattr(t, "id", None) in ("PRICE_AGE_LIMIT", "PRICE_SPREAD_LIMIT")
                      for t in getattr(n, "targets", [getattr(n, "target", None)]))]
    assert not copies, f"a renderer holds its own copy of a price limit: {copies}"


# =====================================================================================
# A CARRIED PRICE, which the record cannot supply
# =====================================================================================

@pytest.fixture
def one_carried_price(monkeypatch):
    """A holding carried by decision, injected — because the record cannot supply one.

    `rules.STATEMENT_PRICED` is empty by default, and record/rules.py is explicit
    that it must stay narrow: the test for an entry is BOTH no feed AND immaterial, and
    *"do not add a holding to make a flag go away"*. So the second witness has to be a fixture.
    Everything the carried path does for a PRICE goes unexercised without one, as for a RATE
    (`one_carried_rate`): the two go down different branches.

    THE TICKER MUST ALREADY BE IN CURRENT_PRICES: `marks_replaceable()` builds `held` by
    filtering that table, so an invented code would produce an empty `held` and prove nothing.
    """
    from portfusion.record import rules as R
    ticker = R.CURRENT_PRICES[0][0]
    monkeypatch.setattr(R, "STATEMENT_PRICED",
                        {ticker: "no market feed and immaterial — test fixture"})
    _the_desk_reads(monkeypatch)
    return ticker


def test_a_carried_price_leaves_the_replaceable_set_and_says_why(one_carried_price):
    """The engine's half. A carried line is a DECISION with its reason, not a gap somebody is
    chasing, and the two populations are kept apart so a refresh cannot assert an observation
    nobody made."""
    from portfusion import engine
    can = engine.Book().marks_replaceable()
    assert one_carried_price not in [r["mark_key"] for r in can["replaceable"]], \
        "a carried line is still being offered for replacement"
    held = {r["mark_key"]: r for r in can["held"]}
    assert one_carried_price in held, "a carried line reached neither population"
    assert held[one_carried_price]["why"], "a carried line arrived with no reason on it"


def test_the_bay_cannot_tick_a_carried_line(one_carried_price, one_carried_rate):
    """The panel's half. A carried line is left off the screen, so the one thing to hold is that
    it never reaches a tickable list — a price or a rate."""
    from portfusion.desk.panels import price_refresh
    q = price_refresh.data()
    assert one_carried_price not in [r["mark_key"] for r in q["prices"]], \
        "the bay offers a carried line in the tickable list"
    assert one_carried_rate not in [r["currency"] for r in q["rates"]], \
        "the bay offers a carried rate in the tickable list"


def test_a_carried_price_write_is_refused_by_name_and_by_reason(store_copy, one_carried_price):
    """THE PRICE BRANCH OF THE REFUSAL. `marks.write()` has two loops with two `raise`
    statements, one for a price and one for a rate."""
    from portfusion.desk.doors import marks
    assert one_carried_price in marks.carried()
    with pytest.raises(marks.Refused) as e:
        marks.write(prices=[{"mark_key": one_carried_price, "price": 1.0, "currency": "GBP",
                             "as_of": "2026-09-08", "source": "test", "struck": "close"}])
    assert one_carried_price in str(e.value) and "carried" in str(e.value), \
        "the refusal does not name the line or say why it is held"


def test_a_carried_price_is_out_of_the_freshness_measure(one_carried_price):
    """THE FIRST CONSEQUENCE record/rules.py declares: price_ageing() counts only market-fed
    holdings."""
    from portfusion import engine
    b = engine.Book()
    assert b.price_ageing()["marks"] == len(b.store["prices"]) - 1, \
        "the carried line is still inside the price-freshness measure"


# =====================================================================================
# A PAST DAY'S CLOSES — banked into the histories, the live marks left alone
# =====================================================================================

_DAY = "2026-09-25"


def _close(ticker=TICK, price=250.0, currency=TICK_CUR, **over):
    row = {"mark_key": ticker, "price": price, "currency": currency, "as_of": _DAY,
           "source": f"TradingView 1D {ticker}, session {_DAY} close — test",
           "struck": "close", "at": ""}
    row.update(over)
    return row


def _rated_line():
    """A foreign-priced, marked line a share account holds at _DAY, with its units — a banked
    close has to reach that day's value through the day's own rate, and only a held foreign
    line can stand that conversion up."""
    from portfusion.record import rules as D
    from portfusion.engine import Book
    b = Book()
    for account in D.ACCOUNT_ORDER:
        if D.ACCOUNT_KIND[account] == "spread bet":
            continue
        held = b.holdings_at(_DAY, account)
        for t, q, c in zip(held["ticker"], held["qty"], held["currency"]):
            if c == RATE_CUR and t in _BY_TICKER:
                return account, t, float(q)
    raise AssertionError(
        f"no share account holds a foreign-priced, marked line at {_DAY} — these conversion "
        f"tests have nothing to stand on in this book")


def _rate(rate=1.34, **over):
    row = {"currency": RATE_CUR, "as_of": _DAY, "rate": rate,
           "source": f"TradingView 1D FX_IDC:GBP{RATE_CUR}, session {_DAY} close — test",
           "struck": "close"}
    row.update(over)
    return row


def test_a_past_days_closes_are_banked_and_the_live_marks_do_not_move(store_copy):
    """The quarter end fetched after it. The engine values that day from the histories, so
    that is where the closes go; current-prices.csv and fx.csv stay byte-identical."""
    from portfusion.record import schema
    from portfusion.desk.doors import marks
    from portfusion.history import prices as PH
    from portfusion.engine import Book
    account, line, qty = _rated_line()
    live = {t: schema.TABLES[t].path.read_bytes() for t in ("current-prices", "fx")}
    before = Book().holdings_at(_DAY, account).set_index("ticker")["value"][line]

    out = marks.bank_closes(_DAY, prices=[_close(ticker=line, currency=RATE_CUR)], rates=[_rate()])

    assert out["banked"] == {"prices": 1, "rates": 1}, out
    assert all(schema.TABLES[t].path.read_bytes() == b for t, b in live.items())
    row = next(r for r in PH.load() if r["mark_key"] == line and r["date"] == _DAY)
    assert (row["struck"], row["price"]) == ("close", 250.0)
    after = Book().holdings_at(_DAY, account).set_index("ticker")["value"][line]
    assert after != before and abs(after - qty * 250.0 / 1.34) < 0.01, (before, after)


def test_the_same_close_twice_is_skipped_and_a_different_one_is_refused(store_copy):
    """A settled close has one value. The same figure again is nothing to do; a different one
    means one of the two is wrong, and the door does not choose."""
    from portfusion.desk.doors import marks
    marks.bank_closes(_DAY, prices=[_close()])
    assert marks.bank_closes(_DAY, prices=[_close()])["already"] == 1
    with pytest.raises(marks.Refused, match="does not choose"):
        marks.bank_closes(_DAY, prices=[_close(price=251.0)])


def test_a_close_on_file_from_the_retired_feed_still_reads_as_that_days_close(store_copy):
    """A RETIRED FEED'S ROWS STAY, each with `struck` saying it is a close, so a close on file in a
    shape no current feed writes must still settle a new fetch of the same day: the one fixture
    here in such a shape, on purpose."""
    from portfusion.desk.doors import marks
    retired = f"Old Feed FX_DAILY GBP/{RATE_CUR}, {_DAY} daily close — test"
    marks.bank_closes(_DAY, rates=[_rate(source=retired)])
    assert marks.bank_closes(_DAY, rates=[_rate()])["already"] == 1


@pytest.mark.parametrize("row, says", [
    (_close(as_of="2026-09-26"), "after 2026-09-25"),
    (_close(source="IG REST live SH.D.X, bid 1, IG updateTime 21:00:00, market OPEN",
            struck="live", at=f"{_DAY}T21:00:00Z"),
     "not a session close"),
    (_close(source=""), "no source"),
])
def test_what_is_not_that_days_close_is_refused_and_nothing_is_written(store_copy, row, says):
    from portfusion.desk.doors import marks
    from portfusion.history import prices as PH
    was = PH.load()
    with pytest.raises(marks.Refused, match=says):
        marks.bank_closes(_DAY, prices=[row])
    assert PH.load() == was


def _live_read(ticker, price=249.0):
    return {"mark_key": ticker, "price": price, "currency": RATE_CUR, "as_of": _DAY,
            "source": f"TradingView {ticker} quote, live — test", "struck": "live",
            "at": f"{_DAY}T13:45:00Z"}


def test_a_close_outranks_its_days_live_read_and_the_next_bank_leaves_it(store_copy, capsys):
    """THE TRAP. The 15:00 sweep writes and banks a live read; that day's close is banked over it
    later; the next refresh's bank step still finds the live read in current-prices.csv. The close
    stays the day's mark, the read leaves the file — the day seen earlier, never a wrong figure —
    and the next write is not refused for a read the close has settled, nor does the read come
    back."""
    from portfusion.engine import Book
    from portfusion.desk.doors import marks
    from portfusion.feeds import refresh
    from portfusion.history import prices as PH
    _, line, _ = _rated_line()
    marks.write(prices=[_live_read(line)])
    out = marks.bank_closes(_DAY, prices=[_close(ticker=line, currency=RATE_CUR)])
    assert out["banked"]["prices"] == 1
    assert out["replaced"] == [f"{line} {_DAY}: the live read 249.0 is replaced by that "
                               f"day's close 250.0"]
    refresh.bank()
    day = [r for r in PH.load() if (r["mark_key"], r["date"]) == (line, _DAY)]
    assert [(r["struck"], r["price"]) for r in day] == [("close", 250.0)]
    assert PH.check() == [] and marks.banked()["ok"]
    assert Book()._marks_at(_DAY)[0][line] == (_DAY, 250.0)


def test_a_days_closing_rate_outranks_its_live_rate(store_copy):
    """The same rule for FX: the day's close replaces the live read and becomes the day's rate."""
    from portfusion.desk.doors import marks
    from portfusion.history import fx as FX
    FX.save(FX.load() + [{"currency": RATE_CUR, "date": _DAY, "rate": 1.33,
                          "kind": "spot", "quality": "sourced", "struck": "live",
                          "source": f"TradingView FX_IDC:GBP{RATE_CUR} quote, live — test"}])
    out = marks.bank_closes(_DAY, rates=[_rate()])
    assert out["banked"]["rates"] == 1 and len(out["replaced"]) == 1
    day = [r for r in FX.load() if (r["currency"], r["date"]) == (RATE_CUR, _DAY)]
    assert [r["rate"] for r in day] == [1.34]
    assert FX.rate_on(RATE_CUR, _DAY) == 1.34


def test_a_live_read_its_close_outranks_needs_no_banking(store_copy, monkeypatch):
    """The one path where the read reached no history first. The close is that day's mark, so the
    read is not owed to the history and the archive step neither files it nor strikes it over the
    close."""
    from portfusion.history import prices as PH
    read = {"mark_key": TICK, "date": _DAY, "price": 249.0, "currency": TICK_CUR,
            "quality": "sourced", "struck": "live", "source": "a read — test"}
    PH.save(PH.load() + [{**read, "price": 250.0, "struck": "close", "source": "a close — test"}])
    monkeypatch.setattr(PH, "current_marks", lambda: [read])
    assert PH.check() == []
    PH.archive(verbose=False)
    day = [r for r in PH.load() if (r["mark_key"], r["date"]) == (TICK, _DAY)]
    assert [r["struck"] for r in day] == ["close"]
    assert PH.check() == []


def test_today_is_not_a_past_day(store_copy):
    from portfusion.desk.doors import marks
    with pytest.raises(marks.Refused, match="not a past day"):
        marks.bank_closes(_dt.date.today().isoformat(), prices=[_close()])


def test_the_bay_asks_for_a_past_day_and_the_write_banks_it(monkeypatch):
    """The fetch passes the day to the sweep; the write routes to the banking door; the screen
    carries the day from one to the other."""
    from portfusion.feeds import refresh
    from portfusion.desk.intake import sweep
    monkeypatch.setattr(refresh, "sweep", lambda on=None, filed=None: {"on": on})
    assert sweep.prices(on=_DAY)["on"] == _DAY

    from portfusion.desk.doors import marks
    monkeypatch.setattr(marks, "bank_closes", lambda day, prices=None, rates=None: {"day": day})
    assert marks.refresh(prices=[_close()], close_of=_DAY) == {"ok": True, "day": _DAY}

    js = desk_script()
    assert 'id="rb-on"' in js and "payload.close_of = closeOf" in js


def test_the_bay_sends_every_column_a_mark_is_written_with():
    """WHAT THE SWEEP SUPPLIES REACHES THE WRITE, for a rate as for a price.

    A rate sent without `struck` is written blank, and `bank_closes()` refuses a rate that does not
    say it is a close. The columns come from the schema, so a column added later fails here until
    the bay fills it from the sweep and sends it. `quality` is the door's own word, never the bay's.
    """
    import re
    from portfusion.record import schema
    js = desk_script()
    for table, kind in (("current-prices", "prices"), ("fx", "rates")):
        m = re.search(rf"payload\.{kind}\.push\(\{{(.*?)\}}\);", js, re.S)
        assert m, f"app.js no longer builds a row of {kind} this test can read"
        sent = set(re.findall(r"(\w+):", m.group(1)))
        wanted = {f.name for f in schema.TABLES[table].fields} - {"quality"}
        assert wanted <= sent, f"the bay writes {kind} without {sorted(wanted - sent)}"
    fills = re.findall(r'fill\(row\.\w+, "(price|rate)",\s*\{(.*?)\}', js, re.S)
    assert {kind for kind, _ in fills} == {"price", "rate"}, "a fill this test reads has gone"
    for kind, body in fills:
        assert "struck: row.struck" in body, f"a {kind} row is filled without the sweep's struck"


# =====================================================================================
# THE IG READING — the equity lands with the levels read in the same pass
# =====================================================================================

def _account_number(account):
    from portfusion.record import schema
    hdr = schema.TABLES["accounts"].header
    return next(r[hdr.index("number")] for r in schema.load("accounts")
                if r[hdr.index("account")] == account)


def _mapped_contract(among=None):
    """A still-quoted contract the book maps a leg to AND marks, with its epic — the only kind
    of level a reading may ride in on (`marks.refresh` gates on `D.LEG_CONTRACT.values()`).
    With `among`, one of those mark keys: a book with two IG accounts holds each contract in one."""
    from portfusion.record import schema
    epic_of = {r[0]: str(r[1] or "").strip() for r in schema.load("contracts")}
    return next((c, epic_of[c]) for c in sorted(_CONTRACTS)
                if c in _BY_TICKER and epic_of.get(c) and (among is None or c in among))


def _reading(account=SPREAD_BET_ACCOUNT, **over):
    row = {"account": account, "as_of": "2026-09-08", "at": "2026-09-08T13:00:00Z",
           "funds": 20000.0, "running_pl": 3000.0, "equity": 23000.0, "deposit": 5000.0,
           "available": 18000.0,
           "evidence": "ig-accounts",
           "reference": f"{_account_number(account)}, read 2026-09-08 at 14:00",
           "note": "IG REST /accounts — test"}
    row.update(over)
    return row


def _level(contract=None, **over):
    contract, epic = (contract, contract) if contract else _mapped_contract()
    row = {"mark_key": contract, "price": 7690.0, "currency": _BY_TICKER[contract][2],
           "as_of": "2026-09-08",
           "source": f"IG REST live {epic}, bid 7690.0 — test",
           "struck": "live", "at": "2026-09-08T14:02:11Z"}
    row.update(over)
    return row


def test_a_reading_writes_its_levels_beside_its_equity(store_copy):
    """The book's figure for a spread-bet account comes from its contract MARKS and the broker's
    from the instant it is asked, so a reading written without the levels it was struck against
    is compared to marks from some other time.

    AN IG READING KEEPS EACH OF ITS FIVE FIGURES ONCE, IN ITS OWN COLUMN."""
    from portfusion.record import schema
    from portfusion.desk.doors import marks
    contract, _ = _mapped_contract()

    out = marks.refresh(prices=[_level()], readings=[_reading()])

    assert out["ok"] is True, out.get("refused")
    assert (out["prices"], out["readings"]) == (1, 1)
    landed = next(r for r in schema.load("current-prices") if r[0] == contract)
    assert landed[1] == 7690.0, "the contract mark was not replaced"
    read = next(r for r in schema.load("account-readings") if r[0] == SPREAD_BET_ACCOUNT)
    head = schema.TABLES["account-readings"].header
    five = ("funds", "running_pl", "equity", "deposit", "available")
    assert [read[head.index(c)] for c in five] == [_reading()[c] for c in five], \
        "the reading was not replaced, figure by figure"


def test_an_ig_check_describes_its_own_instant(store_copy):
    """AN IG CHECK DESCRIBES ITS OWN INSTANT: a sweep on a later day leaves the reconciliation of the
    reading before it as it was, its tie included; one later on the reading's own day takes the
    place of the levels it was read with, so the reading is no longer one pass with its marks.
    On the loaded book's own reading."""
    import datetime as dt
    from portfusion.desk.doors import marks
    from portfusion.engine import Book

    def row():
        return {k: str(v) for k, v in next(r for r in Book().reconciliation().to_dict("records")
                                         if r["account"] == SPREAD_BET_ACCOUNT).items()}
    was = row()
    if was["comparable"] != "True":
        pytest.skip(f"{SPREAD_BET_ACCOUNT}'s reading is not one pass with its marks")
    day = next(r.as_of for r in _rules.ac_rows if r.acct == SPREAD_BET_ACCOUNT)
    later = (dt.date.fromisoformat(str(day)[:10]) + dt.timedelta(days=1)).isoformat()
    # A level moves only the reading of the account holding its contract on the reading's day.
    held = {k for _, k in Book()._held_by_mark_key(str(day)[:10], SPREAD_BET_ACCOUNT)}
    if not (held & _CONTRACTS):
        pytest.skip(f"{SPREAD_BET_ACCOUNT} holds no contract on {str(day)[:10]}")
    contract, _ = _mapped_contract(held)
    marks.write(prices=[_level(contract, price=round(_BY_TICKER[contract][1] * 0.9, 1),
                               as_of=later, at=f"{later}T14:02:11Z")])
    assert row() == was, "a later day's level moved the reconciliation of the reading before it"
    read_at = next(r.at for r in _rules.ac_rows if r.acct == SPREAD_BET_ACCOUNT)
    after = (dt.datetime.fromisoformat(read_at) + dt.timedelta(minutes=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    marks.write(prices=[_level(contract, price=round(_BY_TICKER[contract][1] * 0.9, 1),
                               as_of=str(day)[:10], at=after)])
    now = row()
    assert now["comparable"] == "False" and "struck after the equity was read" in \
        now["comparability"], now["comparability"]


def test_a_refused_reading_rolls_back_the_levels_too(store_copy):
    """THE ENVELOPE SPANS TWO DOORS. The levels are good and the reading is not, so the marks
    door SUCCEEDS and the observations door refuses; anything short of a rollback across both
    leaves the book re-struck against a stale baseline."""
    from portfusion.desk.doors import marks, observations

    files = {p: p.read_bytes()
             for p in (*marks.paths(), *observations.paths()) if p.is_file()}

    out = marks.refresh(prices=[_level()], readings=[_reading(evidence="")])

    assert out["ok"] is False, "a reading with no evidence class was accepted"
    after = {p: p.read_bytes() for p in files}
    moved = sorted(p.name for p in files if files[p] != after[p])
    assert not moved, f"a refused write left these files changed: {moved}"


@pytest.mark.parametrize("prices, reading, close_of, says", [
    ([], _reading(), None, "contract levels"),
    ([_level()], _reading(positions=76510.0), None, "NOTIONAL"),
    ([_close()], _reading(), _DAY, "past day"),
    ([], None, None, "nothing to write"),
])
def test_what_the_write_refuses_leaves_every_file_as_it_was(store_copy, prices, reading,
                                                            close_of, says):
    """A reading with no level from its pass, a notional figure no endpoint returns, a reading on
    a past day's closes, and an empty press."""
    from portfusion.desk.doors import marks, observations
    files = {p: p.read_bytes() for p in (*marks.paths(), *observations.paths()) if p.is_file()}
    out = marks.refresh(prices=prices, readings=[reading] if reading else None, close_of=close_of)
    assert out["ok"] is False and says in out["refused"], out
    assert all(p.read_bytes() == b for p, b in files.items()), "a refused write moved a file"


def test_the_write_is_declared_as_writing_marks_and_reaching_nothing():
    """The marks rule: a contract level and an account's live equity are both MARKS, and neither is
    an event. The write reaches nothing; the sweep that fetched them writes nothing."""
    a = actions.get("refresh-write-marks")
    assert a.writes == "marks" and a.reaches is None
    assert "one operation" in a.summary.lower(), \
        "the summary does not say the marks and readings land together"


def test_the_bay_previews_each_ig_account_before_the_fetch():
    """Each spread-bet account comes with the page, before the fetch, its outgoing equity and date
    shown the way a price's are."""
    from portfusion.desk.panels import price_refresh
    q = price_refresh.data()
    readings = {r["account"]: r for r in q["readings"]}
    from portfusion.record import rules as D
    assert set(readings) == {a for a in D.ACCOUNT_ORDER if D.ACCOUNT_KIND[a] == "spread bet"}
    for r in readings.values():
        assert r["equity"] is not None and r["as_of"], r


def test_an_ig_accounts_source_is_the_line_its_reading_is_filed_under(monkeypatch):
    """THE REVIEW SHOWS WHAT THE WRITE RECORDS. Each account's row carries the record's own
    provenance line for its reading, and the bay fills the row with it."""
    from portfusion.feeds import refresh
    from portfusion.desk.intake import sweep
    from portfusion.record import rules as D
    account = SPREAD_BET_ACCOUNT
    reading = _reading(account)
    monkeypatch.setattr(refresh, "sweep", lambda on=None, filed=None: {
        "ig_equity": {"ok": True, "readings": [reading],
                      "rows": [{"account": account, "equity": reading["equity"]}]}})
    row = sweep.prices()["ig_equity"]["rows"][0]
    assert row["source"] == D.evidence_source(reading["evidence"],
                                              reference=reading["reference"], account=account)
    assert reading["reference"] in row["source"]
    js = desk_script()
    import re
    m = re.search(r'fill\(r\.account, "reading", \{(.*?)\}', js, re.S)
    assert m, "app.js no longer fills an IG account's row in a way this test can read"
    assert "source: read.source" in m.group(1), "the bay composes an account's source again"


def test_the_bay_sends_what_it_draws_and_a_mark_past_the_limit_says_so():
    """The key is `mark_key`, as the grid heads it; the outgoing source is not sent and stays at
    its home, Holdings' Mark history; and the age of a mark past the limit is drawn in the warning
    ink, which is the desk's on every page."""
    from portfusion.desk.panels import holdings, price_refresh
    q = price_refresh.data()
    assert q["prices"] and all(set(r) == set(price_refresh.PRICE_COLUMNS) for r in q["prices"])
    assert not any("source" in r for r in q["prices"] + q["rates"]), \
        "the outgoing mark's source is sent to a page that does not draw it"
    assert "source" in holdings.MARK_COLUMNS, "the outgoing source has lost its home"
    js = desk_script()
    assert '${r.stale ? "stale" : "muted"}' in js, "a mark past the limit no longer says so"
    css = _static("app.css")
    import re
    assert re.search(r"^\.stale \{ color: var\(--warn-ink\); \}", css, re.M), \
        "the warning ink is no longer the desk's on every page"


def test_the_bay_reads_a_store_moved_under_the_desk_on_its_first_load(store_copy):
    """THE OUTGOING MARK IS THE DESK'S BOOK'S, on the first load after the store moved under the
    desk (a hand edit, a pull, a checkout): the bay asks `engine.book()`, which reloads, so the
    "Was" column and the figures beside it read one record. On a copy."""
    from portfusion.desk import engine as desk
    from portfusion.desk.panels import price_refresh
    can = {r["mark_key"] for r in desk.book().marks_replaceable()["replaceable"]}
    if not can:
        pytest.skip("the book holds no replaceable mark")
    path = store_copy / "current-prices.csv"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    i = next(i for i, line in enumerate(lines) if line.split(",")[0] in can)
    cells = lines[i].split(",")
    cells[1] = f"{float(cells[1]) * 2:g}"
    lines[i] = ",".join(cells)
    path.write_text("".join(lines), encoding="utf-8")
    was = {r["mark_key"]: r["price"] for r in price_refresh.data()["prices"]}
    assert was[cells[0]] == float(cells[1]), "the bay shows a mark the store no longer holds"


def test_each_group_of_the_grid_runs_a_to_z_by_its_line():
    """In the store's own order a contract sits among the shares. A-Z by line puts each contract
    beside its company."""
    from portfusion.desk.panels import price_refresh
    q = price_refresh.data()
    for rows, key in ((q["prices"], "mark_key"), (q["rates"], "currency"), (q["readings"], "account")):
        said = [str(r[key]) for r in rows]
        assert said == sorted(said, key=str.upper), f"{key}s are not A-Z: {said}"


def test_the_step_bar_says_the_marks_age_and_draws_the_bank_only_when_it_cannot_bank():
    """The age leads, as the Dashboard's does and from the same figure, the Bank step is drawn only
    when the histories cannot be read, and the line says what came back."""
    from portfusion.engine import Book
    from portfusion.desk.panels import price_refresh
    assert price_refresh.data()["age_days"] == Book().price_ageing()["age_days"]
    js = desk_script()
    assert "${d.age_days} days old · limit ${d.age_limit} days" in js
    assert "const bank = !b.unavailable ? [] :" in js, "the Bank step is drawn when all is well"
    assert "filled in below" not in js and "can be replaced" not in js


def test_the_tick_column_is_headed_and_its_boxes_carry_no_word():
    """The tick column is headed once, in house/headings.py's words, and each box keeps its word
    only for a screen reader. The form's heads are GRID_COLUMNS, in its order: the rows are drawn
    by hand, so nothing else holds them to the panel's list."""
    import re
    from portfusion.desk.panels import price_refresh
    assert "take" in price_refresh.GRID_COLUMNS
    js = desk_script()
    form = js[js.index('<div class="scroll" id="rb-form">'):js.index('${group("Prices"')]
    assert re.findall(r'head\("(\w+)"\)', form) == list(price_refresh.GRID_COLUMNS), \
        "the Price Refresh's heads are not GRID_COLUMNS in order"
    assert '<th>${head("take")}</th>' in js, "the tick column has no heading"
    assert not re.search(r"data-tick disabled> take", js), "a box still prints the word"
    # ONE BOX PER ROW TEMPLATE: a price, a rate, a rate the record lacks, an IG account.
    assert js.count('data-tick disabled\n          aria-label="${head("take")}"') == 4


def test_a_fetched_line_says_beside_its_date_whether_it_is_a_close_or_a_time():
    """The sweep says whether a read is a close (`struck`) and when (`at`), so a price or rate row
    shows "close" or the read's wall-clock time beside the date it sends. The date the write sends
    is the date alone: the time sits outside the form's fields."""
    import re
    js = desk_script()
    cells = re.findall(r'<tr data-kind="(price|rate)".*?<input data-f="as_of" readonly '
                       r'size="10"> <span class="muted small" data-when></span>', js, re.S)
    assert sorted(cells) == ["price", "rate"], "a price or rate row lost its time"
    assert 'values.struck === "close" ? "close"' in js and "clock(values.at)" in js


# =====================================================================================
# THE DATED RATES THE RECORD LACKS
# =====================================================================================

def test_every_rate_the_record_lacks_is_a_past_foreign_date_it_converts_at():
    """What `Book.rate_gaps()` names is work the record owes: a currency the book converts, a
    date already past, one of the six kinds of date, and the rate it converts at today."""
    import pandas as pd
    from portfusion.engine import Book
    today = pd.Timestamp.today().normalize()
    for g in Book().rate_gaps():
        assert g["currency"] != "GBP" and pd.Timestamp(g["date"]) < today, g
        assert g["why"] in ("quarter end", "income", "typed", "deal", "bet", "life"), g


def _a_lacking_date(store_copy):
    """A rate the record owes, planted where the book does not owe one: a typed rate on a
    past weekday (a Wednesday), with no close on or after it in the week."""
    from portfusion.history import fx as FX
    day = "2025-12-10"
    FX.save(FX.load() + [{"currency": RATE_CUR, "date": day, "rate": 1.29,
                          "kind": "spot", "quality": "derived", "struck": "",
                          "source": "typed for the test"}])
    return day


def test_a_rate_the_record_lacks_leaves_the_list_when_its_close_is_banked(store_copy):
    """THE LOOP: a typed rate is owed its day's close; the close banked through the past-day door
    replaces it, and the date is owed nothing more."""
    from portfusion.engine import Book
    from portfusion.desk.doors import marks
    from portfusion.history import fx as FX
    day = _a_lacking_date(store_copy)
    assert {"currency": RATE_CUR, "date": day, "why": "typed", "rate": 1.29} in Book().rate_gaps()
    out = marks.bank_closes(day, rates=[{"currency": RATE_CUR, "as_of": day, "rate": 1.2917,
                                         "source": f"TradingView 1D FX_IDC:GBP{RATE_CUR}, session {day} "
                                                   f"close 1.2917 {RATE_CUR} — test",
                                         "struck": "close"}])
    assert out["banked"]["rates"] == 1 and out["days"] == [day]
    assert not [g for g in Book().rate_gaps() if (g["currency"], g["date"]) == (RATE_CUR, day)]
    on_day = [r["rate"] for r in FX.load() if (r["currency"], r["date"]) == (RATE_CUR, day)]
    assert on_day == [1.2917]
    assert out["replaced"] == [f"{RATE_CUR} rate {day}: 1.29 is replaced by that day's close 1.2917"]


def test_a_weekend_date_is_served_by_the_friday_close():
    """A Saturday has no session: the close of the Friday before it is that date's rate, so a
    Saturday's income row owes nothing once Friday's close is on file."""
    import pandas as pd
    from portfusion.engine import Book
    b = Book()
    fh = b.store["history.fx"]
    closes = fh[(fh["struck"] == "close") & (fh["kind"] == "spot")]
    friday = next((d for d in closes["date"] if pd.Timestamp(d).weekday() == 4), None)
    if friday is None:
        pytest.skip("no Friday close on file to stand a Saturday on")
    cur = closes[closes["date"] == friday]["currency"].iloc[0]
    saturday = (pd.Timestamp(friday) + pd.Timedelta(days=1)).date().isoformat()
    later = fh[(fh["currency"] == cur) & (fh["date"] == saturday)]
    assert later.empty, "a rate dated the Saturday would answer before the Friday's close"
    b.store["income"] = pd.concat([b.store["income"], pd.DataFrame([{
        "date": pd.Timestamp(saturday), "account": "x", "category": "Cash interest",
        "detail": "test", "amount": 0.0, "source": "test", "note": "", "currency": cur,
        "local_amount": 1.0, "rate": None}])], ignore_index=True)
    assert not [g for g in b.rate_gaps() if (g["currency"], g["date"]) == (cur, saturday)]


def test_one_write_banks_a_rate_wanted_twice_once_and_refuses_two_figures(store_copy):
    """Two dates one session serves are filled from one row, and both can be ticked: the same
    close twice in one write is one close, and two figures for one day are refused."""
    from portfusion.desk.doors import marks
    day = _a_lacking_date(store_copy)
    row = {"currency": RATE_CUR, "as_of": day, "rate": 1.2917, "struck": "close",
           "source": f"TradingView 1D FX_IDC:GBP{RATE_CUR}, session {day} close — test"}
    out = marks.bank_closes(day, rates=[row, dict(row)])
    assert out["banked"]["rates"] == 1 and out["already"] == 1
    with pytest.raises(marks.Refused, match="does not choose"):
        marks.bank_closes("2025-12-11", rates=[{**row, "as_of": "2025-12-11", "rate": 1.30},
                                               {**row, "as_of": "2025-12-11", "rate": 1.31}])


def test_the_audit_names_every_rate_the_record_lacks():
    """`portfusion record` and the Dashboard read one list: the engine's."""
    from portfusion.engine import Book
    b = Book()
    f = b.findings()
    owed = [g for g in f["gaps"] if g.startswith("rate owed")]
    assert len(owed) == len(b.rate_gaps())
    assert f"dated rates: {len(owed)} owed a TradingView close" in f["notes"]


def test_the_bay_offers_the_rates_the_record_lacks_and_banks_them(monkeypatch):
    """The panel sends the engine's list; the fetch reads it in one press, the action reaching
    TradingView once per currency; the rows fill by currency and date, and the write sends them
    as rates for the past-day door to bank, never as live rates."""
    import re
    from portfusion.engine import Book
    from portfusion.desk.intake import sweep
    from portfusion.desk.panels import price_refresh
    q = price_refresh.data()
    assert q["lacking"] == Book().rate_gaps()
    asked = {}

    def fake(wanted, conn=None, today=None):
        asked.update(wanted)
        return {"rates": [{"currency": c, "as_of": d, "rate": 1.0, "struck": "close", "at": "",
                           "wanted": [d], "source": "test", "symbol": "x", "raw": 1.0}
                          for c, ds in wanted.items() for d in ds], "failed": []}
    from portfusion.feeds import tv
    monkeypatch.setattr(tv, "rate_closes", fake)
    got = sweep.prices(lacking=True)
    assert got["lacking"] and got["tv"]["ok"]
    assert sorted((c, d) for c, ds in asked.items() for d in ds) == \
        sorted((g["currency"], g["date"]) for g in q["lacking"])
    if q["lacking"]:
        assert got["on"] == max(g["date"] for g in q["lacking"])
    js = desk_script()
    assert 'group("Rates the record lacks", "lacking", d.lacking.map(lackingRow))' in js
    assert re.search(r'fill\(`\$\{row\.currency\}@\$\{w\}`, "lacking"', js)
    assert 'fetchSweep(e.currentTarget, { lacking: true }, "TradingView")' in js
    assert re.search(r"if \(lacking\) \{[^}]*\} else if \(ig\.ok === false\)", js), \
        "a rates-only fetch reports IG, which it never asked"
    m = re.search(r'dataset\.kind === "lacking"\) \{\s*payload\.rates\.push\(\{(.*?)\}\);', js, re.S)
    assert m and {"currency", "as_of", "rate", "source", "struck"} <= set(re.findall(r"(\w+):", m.group(1)))
