"""
THE JOURNAL — record time, and the guards on it.

`store/journal.csv` is the one table in the store that is ABOUT the record rather than part
of it. Every other table holds facts about the world; this holds facts about the book: one
row per WRITE, saying when, by what route, to which table, and how much moved.

WHY IT NEEDED ITS OWN FILE OF TESTS. `test_schema.py` proves the table loads and its types
hold, which is what it proves for every table. It cannot prove the things that make this one
worth having — that the seed is a faithful copy of the archive rather than a retyping, that
the arithmetic against the store actually closes, and that a door which writes the record
also writes the journal. Those are three different claims and they live here.
"""
import json

import pytest

from portfusion.record import schema

# THE LOADED BOOK'S bench archive — commit.py owns the constant, and deriving it here is
# what lets these audits run on whatever book PORTFUSION_BOOK names rather than this repo's.
from portfusion.desk.doors.commit import ARCHIVE as BENCH   # noqa: E402


def _rows() -> list[dict]:
    header = schema.TABLES["journal"].header
    return [dict(zip(header, r)) for r in schema.load("journal")]


# =====================================================================================
# THE SHAPE
# =====================================================================================

def test_every_record_table_has_exactly_one_opening_count():
    """ONE OPENING COUNT per table, and the journal's whole claim to be checkable.

    A table with no opening count cannot be reconciled at all — `appends − removes` would be
    compared against a total that includes every row entered before the journal existed. A
    table with two would be reconciled against whichever the reader happened to read.

    DERIVED FROM THE SCHEMA, so a new table joins this guard by existing and fails until
    somebody opens its count on purpose. That is the same shape as every other list in this
    project that is a NAMED SET rather than a number.
    """
    opened = [r for r in _rows() if r["route"] == "baseline"]
    assert all(r["op"] == "open" for r in opened), \
        "a baseline row must be op=open; it records rows already on file, it wrote none"

    want = {t for t in schema.TABLES if t != "journal"}
    got = [r["table"] for r in opened]
    assert sorted(got) == sorted(want), (
        f"opening counts cover {sorted(set(got))}; the schema holds {sorted(want)}. Every "
        f"record table needs one, and the journal itself needs none — it opens empty.")
    assert len(got) == len(set(got)), f"a table has two opening counts: {sorted(got)}"


def test_the_opening_counts_share_one_instant():
    """One opening, not nineteen. The check reads rows at or after a table's own opening, and
    staggered openings would make "since the journal opened" mean a different moment per
    table."""
    at = {r["at"] for r in _rows() if r["route"] == "baseline"}
    assert len(at) == 1, f"the journal opened at {sorted(at)}; it must open once"


def test_a_replace_is_never_counted_as_a_row_arriving():
    """THE ONE PIECE OF ARITHMETIC THAT MAKES THE CHECK USABLE, stated as a rule.

    A refresh replacing twelve marks leaves `current-prices.csv` exactly as long as it was.
    If `replace` were added to the opening count, every fortnightly refresh would read as
    twelve unaccounted rows — and a check that fires on normal work trains its reader to
    ignore it.
    """
    assert schema.TABLES["journal"].fields[2].name == "op"
    assert set(schema.TABLES["journal"].fields[2].enum) == {"open", "append", "replace", "remove"}


# =====================================================================================
# THE SEED — a copy of what the book already recorded, not a retyping of it
# =====================================================================================

def _archived() -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted(BENCH.glob("*.json"))]


@pytest.mark.audit
def test_every_archived_bench_item_is_in_the_journal():
    """THE SEED IS A COPY AND THIS IS WHAT KEEPS IT ONE.

    Every item in `_archive/bench/` already carries `written_at` and `written_to` — the fact
    this table exists to hold, recorded before the journal existed and never read back.
    Seeding from them moves a fact the book already had into the place it belongs.

    DERIVED FROM THE ARCHIVE ON EVERY RUN, never a fixture. An item committed tomorrow fails
    this until its journal row exists — the same claim the door guards make from the other
    end, and worth making twice because the archive and the journal are written by the same
    operation and could fail together.
    """
    if not BENCH.is_dir():
        pytest.skip("no bench archive")
    journal = _rows()
    for item in _archived():
        for table, n in (item.get("written_to") or {}).items():
            match = [r for r in journal if r["ref"] == item["id"] and r["table"] == table]
            assert match, (
                f"{item['id']} wrote {n} row(s) to {table} at {item['written_at']} and the "
                f"journal has no entry for it. The archive and the journal record the same "
                f"write; if one has it and the other does not, one of them is wrong.")
            assert len(match) == 1, f"{item['id']} has {len(match)} journal rows for {table}"
            assert match[0]["rows"] == n, (
                f"{item['id']} wrote {n} row(s) to {table}; the journal says "
                f"{match[0]['rows']}")
            assert match[0]["at"] == item["written_at"], (
                f"{item['id']}: archive says {item['written_at']}, journal says "
                f"{match[0]['at']}")


@pytest.mark.audit
def test_the_journal_claims_no_bench_write_the_record_does_not_have():
    """The other direction, and the one that catches a hand-typed row. A journal entry
    routed `bench` names what wrote it, and that has to retrieve something — a reference
    that retrieves nothing is the defect `statement-grade` exists to prevent, arriving in a
    new table.

    TWO THINGS ARE PRESSED ON THE BENCH. An event names its bench item, which the archive
    holds. A published research note names its own ref, and the rows it wrote are on file
    under that ref, as many as the journal says — the research repo, not the archive, holds
    the note itself."""
    ids = {i["id"] for i in _archived()} if BENCH.is_dir() else set()
    header = schema.TABLES["research-notes"].header
    notes: dict[str, int] = {}
    for r in schema.load("research-notes"):
        ref = dict(zip(header, r))["ref"]
        notes[ref] = notes.get(ref, 0) + 1
    journalled: dict[str, int] = {}
    for row in _rows():
        if row["route"] != "bench":
            continue
        if row["table"] == "research-notes":
            assert row["ref"] in notes, (
                f"journal row at {row['at']} names research note {row['ref']!r}, which has no "
                f"row in research-notes.csv. Its ref must retrieve the rows it wrote.")
            journalled[row["ref"]] = journalled.get(row["ref"], 0) + row["rows"]
            continue
        assert row["ref"] in ids, (
            f"journal row at {row['at']} names bench item {row['ref']!r}, which is not in "
            f"_archive/bench/. Its ref must retrieve the item that wrote it.")
    # AT LEAST, NOT EXACTLY: a note's earlier rows may have arrived before the journal opened,
    # and the table-by-table arithmetic below is what counts every row.
    for ref, n in journalled.items():
        assert notes[ref] >= n, (
            f"{ref}: the journal says the Bench wrote {n} row(s) and research-notes.csv holds "
            f"{notes[ref]} under that ref")


def test_writes_in_the_same_second_read_newest_first():
    """ONE SECOND CAN HOLD SEVERAL WRITES — a refresh replaces marks, rates and readings at one
    instant — and the later row in the file is the newer. Sorted unstably by time alone, What
    Changed showed one second's rows in file order and another's reversed (13 Oct 2026)."""
    from portfusion.engine import Book
    from portfusion.engine import utc_of
    keys = ("at", "route", "op", "table", "ref")
    # ON THE JOURNAL'S ONE CLOCK, as the engine reads it (`engine.utc_of`).
    written = [(utc_of(r["at"]), *(r[k] for k in keys[1:])) for r in _rows()
               if r["route"] != "baseline"]
    expected = sorted(reversed(written), key=lambda r: r[0], reverse=True)
    shown = [tuple(r[k] for k in keys) for r in Book().journal().to_dict("records")]
    assert shown == expected, "the journal does not read newest first within one second"


# =====================================================================================
# THE ARITHMETIC — opening + appends − removes = rows on file
# =====================================================================================


def _book():
    """A Book built against whatever `schema.STORE` currently points at.

    `record/rules.py` reads the store at IMPORT and the engine reads rules, so a fixture that
    repoints schema.STORE does not reach the tables rules already holds. The reconciliation
    only reads two things — the journal frame and `rules.store_rows()` — and both go through
    schema at call time, which is what makes this testable at all.
    """
    from portfusion import engine
    return engine.Book()


@pytest.mark.audit
def test_the_journal_closes_against_the_record_as_it_stands():
    """THE CLAIM, ON THE REAL RECORD. If this fails, either a row reached the store by a route
    nobody journalled, or the arithmetic is wrong — and the message says which table."""
    off = _book().journal_unaccounted()
    assert off.empty, (
        "these tables hold rows no journal route accounts for:\n"
        + off.to_string(index=False)
        + "\n\nThat is a hand edit. It is allowed — docs/store.md says so — but it should "
          "carry a `hand` journal row saying what it was, or this line stops being readable.")


def test_a_row_added_by_hand_is_reported_as_unaccounted(store_copy):
    """THE CHECK EARNING ITS PLACE. Until the journal existed, a hand-edited row and a
    committed one were indistinguishable the moment the file was saved. This is the difference:
    a row that arrived by no journalled route now has somewhere to show up.
    """
    # MEASURED AS A DELTA. Asserting the WHOLE frame rested on the live record carrying no other
    # unaccounted row, and went red when one did — reporting a mechanism failure where there was
    # a record finding. The mechanism is "a hand-added row shows up", and that is a difference.
    def _unaccounted():
        return {r["table"]: r["unaccounted"]
                for r in _book().journal_unaccounted().to_dict("records")}

    before = _unaccounted()
    path = store_copy / "reasoning.csv"
    path.write_text(path.read_text() + "ZZZ,2026-01-02,typed straight into the file,\n",
                    encoding="utf-8")
    after = _unaccounted()

    assert after.get("reasoning", 0) - before.get("reasoning", 0) == 1, (
        f"a row typed straight into reasoning.csv did not show up as unaccounted: "
        f"{before.get('reasoning', 0)} -> {after.get('reasoning', 0)}")


def test_a_journalled_hand_edit_closes_the_check(store_copy):
    """ROUTE `hand` IS WHY THE CHECK STAYS READABLE. A hand edit is a legitimate correction —
    docs/store.md calls it one — so a person who makes one and says so should not leave the
    line reporting a discrepancy forever. A check that fires on sanctioned work is a check
    people learn to skip.
    """
    from portfusion.desk.doors import commit

    def _reasoning_off():
        return {r["table"]: r["unaccounted"]
                for r in _book().journal_unaccounted().to_dict("records")}.get("reasoning", 0)

    before = _reasoning_off()
    path = store_copy / "reasoning.csv"
    path.write_text(path.read_text() + "ZZZ,2026-01-02,typed straight into the file,\n",
                    encoding="utf-8")
    commit.journal([("hand", "append", "reasoning", 1, "commit abc1234",
                     "corrected by hand, see the commit")])

    # THE TABLE THIS TEST TOUCHED, not the whole frame — same reason as the sibling above.
    assert _reasoning_off() == before, (
        "a hand edit that journalled itself is still being reported as unaccounted")


def test_a_replace_leaves_the_reconciliation_where_it_was(store_copy):
    """THE ARITHMETIC'S ONE SUBTLETY, TESTED RATHER THAN COMMENTED. A refresh replaces marks
    and adds no rows, so a `replace` entry must move `expected` by nothing. Counted as an
    arrival, one fortnightly refresh would report twelve unaccounted rows in a table whose
    length never moved."""
    from portfusion.desk.doors import commit

    def state():
        rows = _book().journal_reconciliation().to_dict("records")
        return ({r["table"]: r["unaccounted"] for r in rows},
                next(r["replaced"] for r in rows if r["table"] == "current-prices"))

    # THE DELTA, NOT THE ABSOLUTE. Read against the whole store, this passed only while no real
    # refresh had ever been journalled; the first one through the Price Refresh put 18 replaced
    # marks on file and the test failed on a store that was entirely correct. What is asserted is
    # what THIS journal entry does, so it is measured either side of it.
    before, before_replaced = state()
    commit.journal([("marks", "replace", "current-prices", 12, "2026-09-04",
                     "12 marks replaced")])
    after, after_replaced = state()
    assert after == before, "a replace moved the reconciliation; it adds no rows"
    assert after_replaced - before_replaced == 12, (
        f"the replace is not being counted at all — it should be reported, just not added: "
        f"{before_replaced} -> {after_replaced}")


def test_a_row_written_before_the_opening_is_inside_it(store_copy):
    """A ROW DATED BEFORE THE OPENING COUNT IS ALREADY INSIDE IT. A journal opened over a store
    some door had already written carries those writes in its opening figures; read into the
    arithmetic as well, they would be counted twice, and every table they touched would report a
    surplus that is not there. The reconciliation reads only rows at or after the opening
    instant.

    WRITTEN HERE, ON EITHER SIDE OF THE INSTANT, rather than looked for in the loaded book: a
    book holds such rows only if its journal was seeded from writes made before it, and a test
    that needed them stopped testing on every other book, a new one included. The row before
    must not count; the row after must, which is what shows the check can fail.
    """
    import datetime as dt
    opening = _book().journal_opened()
    assert opening, "the journal has no opening count, so nothing can be measured from it"
    opened = dt.datetime.fromisoformat(opening.replace("Z", "+00:00"))
    path = schema.TABLES["journal"].path
    clean = path.read_text(encoding="utf-8").rstrip("\n") + "\n"

    def written(seconds: int) -> None:
        at = (opened + dt.timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
        path.write_text(clean + f"{at},bench,append,companies,1,B-TEST,a write\n",
                        encoding="utf-8")

    written(-1)
    assert _book().journal_unaccounted().empty, (
        "a row written before the journal opened is being counted against the opening "
        "figures, which already hold it")
    written(+1)
    assert not _book().journal_unaccounted().empty, (
        "a row written after the journal opened went uncounted: the reconciliation is not "
        "reading the journal at all")


def test_the_journal_reads_one_clock_whichever_wrote_a_row(store_copy):
    """ONE CLOCK FOR THE JOURNAL: 13:30 in London summer time, an older row's way of writing it, is
    12:30 UTC, so it reads as before a UTC 12:45 written fifteen minutes later. Compared as
    written, it read as after it."""
    from portfusion.engine import Book
    from portfusion.record import rules, schema
    path = schema.TABLES["journal"].path
    path.write_text(path.read_text(encoding="utf-8")
                    + "2026-07-01T13:30:00,hand,append,reasoning,0,old,a UK time with no zone\n"
                    + "2026-07-01T12:45:00Z,hand,append,reasoning,0,new,a UTC time\n",
                    encoding="utf-8")
    rules.reload_store()
    refs = [r for r in Book().journal()["ref"] if r in ("old", "new")]
    assert refs == ["new", "old"], f"newest first, on one clock: {refs}"
    assert schema.record_instant().endswith("Z")
