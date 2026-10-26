"""THE DESK'S TWO LOAD-BEARING CLAIMS, and the named set of modules that may write.

  1. THE BOOK DOES NOT DEPEND ON THE DESK. Delete desk/ and the report builds unchanged: the
     import contracts in `pyproject.toml`.
  2. NO ACTION CAN WRITE AN EVENT. The marks rule lets a feed write a MARK on the owner's tick and
     never an event, and `Action` refuses to be constructed otherwise.

The rest of tests/desk/ is detail on these two, split by subject.
"""
from __future__ import annotations

import datetime as _dt
import functools

import pytest
from portfusion.desk import actions
from harness import SRC, STORE_NAMES, file_calls, write_call


# =====================================================================================
# 2. No action can write an event. This is the security claim, so it is tested hardest.
# =====================================================================================

def test_no_registered_action_writes_an_event():
    """The marks rule: a feed may write a mark, never an event. A trade, exit, dividend or
    capital movement happened once and is history; it goes to the bench for evidence,
    reasoning and approval.

    WHY THE LINE FALLS THERE: a wrong mark is one write from right, with the old value kept in
    its history; a wrong event corrupts cost, realised gain and every return built on them."""
    assert [a.name for a in actions.all_actions() if a.writes == "events"] == []


def test_the_registry_refuses_an_event_writer_at_construction():
    """Not merely absent — IMPOSSIBLE. The wrong thing should be unbuildable rather than
    forbidden by a comment somebody has to read."""
    with pytest.raises(ValueError, match="never write an event"):
        actions.Action(name="x", label="x", panel="p", run=lambda: None,
                       writes="events", gate="approved")


def test_writes_is_three_valued_not_a_boolean():
    """'Does it write?' is answerable with a bool; 'what may it write?' is not, and the whole
    decision lives in the second question."""
    assert actions.WRITE_KINDS == (None, "marks", "events")
    with pytest.raises(ValueError, match="not one of"):
        actions.Action(name="y", label="y", panel="p", run=lambda: None,
                       writes=True, gate="approved")


def test_a_write_must_name_its_human_gate():
    """The marks rule does not settle a write with no stated human step."""
    with pytest.raises(ValueError, match="no gate"):
        actions.Action(name="z", label="z", panel="p", run=lambda: None, writes="marks")


def test_every_writing_action_is_pinned():
    """The list of actions that can change the record, pinned. A NEW WRITING BUTTON FAILS THIS
    TEST until someone declares it on purpose.

    THIS IS THE ONLY STANDING GUARD ON THE WRITES. There is no blanket date gate, so nothing
    else sits between a writing action and a live record — which is why each entry is a NAME
    here rather than a count, and why another has to be argued for.

    IT IS A MARK, AND THE MARKS RULE NAMES IT: *a feed may write a MARK — a price, an FX rate,
    LIVE EQUITY — on the owner's per-line tick; it may never write an EVENT.*

      refresh-write-marks  the Price Refresh's write: prices, FX rates, and the IG accounts'
                           equity read with the levels, landing together or not at all.

    A share account's reading is not an action: it is filed with its holdings export by the
    Bench's commit, through the same door. The outgoing value is banked first, and the whole
    operation is refused if any line lacks its date, its evidence or its reference.
    """
    assert {a.name for a in actions.writing_actions()} == {"refresh-write-marks"}
    for name in ("refresh-write-marks",):
        assert actions.get(name).writes == "marks", \
            f"{name} must declare marks — an action that wrote events could not exist"


def test_every_reaching_action_is_pinned():
    """The mirror of the writes pin: the set of actions that LEAVE THIS MACHINE, named here so
    another cannot appear without somebody deciding it should.

    The question is not "does it leave" but "what does it reach" — the same shape of question
    `writes` answers about the record. The registry is "the one place that says what this thing
    can do", and an action that talks to a third party without saying so is the gap this axis
    closes.

    THE KINDS OF REACHING ARE NOT THE SAME, which is why each carries its own gate rather than
    a shared one:

      ig-events          asks IG — a broker this book already holds an account with — for that
                         account's events, and sends nothing but the request.
      refresh-fetch-all  the price sweep, so TWO vendors: IG's levels and each account's equity
                         in one pass, then TradingView. Declared rather than inherited from the
                         feeds it calls: `reaches` describes what an ACTION does. The levels
                         and the equity together are the point: struck apart they differ,
                         struck together they agree to the penny.
      ig-setup-to-bench  asks IG for one new contract's level: the first mark its first bet is
                         valued at, read on the press that sets the bet up.

    `ig-event-to-bench` IS DELIBERATELY NOT HERE. It carries an event the sweep already
    fetched onto the bench and opens no connection of its own — the distinction this axis
    exists to draw, applied to the action that most looks like it should be in the list.
    """
    assert {a.name for a in actions.reaching_actions()} == {
        "refresh-fetch-all", "ig-events", "ig-setup-to-bench"}
    assert actions.get("ig-event-to-bench").reaches is None, \
        "carrying a swept event onto the bench opens no connection — it reaches nothing"


def test_something_that_reaches_out_must_declare_a_gate():
    """A write can be undone by restoring a file. A document that has left cannot be."""
    with pytest.raises(ValueError) as e:
        actions.Action(name="x", label="x", panel="p", run=lambda: None, reaches="network")
    assert "no gate" in str(e.value)


def test_reaches_is_not_a_fourth_value_on_writes():
    """The two axes stay separate. Folding "network" into WRITE_KINDS would make "what may
    this write?" unanswerable again, which is the exact collapse the marks rule's three-valued
    field was built to prevent."""
    assert "network" not in actions.WRITE_KINDS
    assert set(actions.REACH_KINDS) == {None, "network"}
    with pytest.raises(ValueError):
        actions.Action(name="x", label="x", panel="p", run=lambda: None,
                       writes="network", gate="g")


def test_there_is_no_blanket_date_gate():
    """NO BLANKET GATE (`WRITES_ENABLED_FROM` is None): the desk closes a quarter itself, so a gate
    that opens the day AFTER the close protects nothing. The per-action date is the next test."""
    assert actions.WRITES_ENABLED_FROM is None
    a = actions.Action(name="w", label="w", panel="p", run=lambda: None,
                       writes="marks", gate="tick-each-line")
    assert a.available is True
    assert a.as_json()["enabled_from"] is None


def test_an_action_may_still_name_its_own_date():
    """The per-action date is kept because it costs nothing — a single risky button can defer
    itself without a project-wide rule."""
    tomorrow = _dt.date.today() + _dt.timedelta(days=1)
    later = actions.Action(name="w", label="w", panel="p", run=lambda: None, writes="marks",
                           gate="tick-each-line", enabled_from=tomorrow)
    now = actions.Action(name="x", label="x", panel="p", run=lambda: None, writes="marks",
                         gate="tick-each-line", enabled_from=_dt.date.today())
    assert later.available is False
    assert now.available is True
    assert later.as_json()["enabled_from"] == tomorrow.isoformat()


# =====================================================================================
# THE NAMED WRITERS — what in the package may write, and which under desk/ reach the record
# =====================================================================================

#: What a write is: `harness.write_call()`, the one list, a removal, a copy and a rename among
#: them. A module that writes through `desk/doors/envelope.py` writes.


#: Every module in the package that writes any file at all, and what each one writes. A NAMED
#: SET: a new writer is a structural change, and wants a considered yes rather than a convenience
#: slipped in beside a layout tweak. The record is written only by the doors under desk/, and its
#: histories by those doors and the price refresh, through history/; outside desk/, `init` and
#: `migrate --write` write a book, and a feed writes only its own sign-in file.
#:
#: UNDER desk/:
#:
#:   auth.py          the hosted desk's three files at the root, all out of git and none the
#:                    record: the passkeys (.desk_passkeys.json), each reader's level
#:                    (.desk_readers.json), and the sign-in log it appends to
#:                    (.desk_signins.jsonl, opened for appending).
#:   bench.py         its own item note, in _inbox/.bench/ — staging, never the record
#:   commit.py        APPENDS AN EVENT to store/
#:   envelope.py      WRITES BACK WHAT A DOOR HELD when its write fails (`envelope.atomic()`), and
#:                    the journal, the placing and the rewriting the store doors share
#:   dropoff.py       a dropped document into _inbox/
#:   publish.py       the deploy repository's clone, the book's `deploy_repo` — the hosted
#:                    desk's generated files. Outside this repository and never the record.
#:   freeze.py        APPENDS A QUARTER END to store/, from the engine, once a quarter, and
#:                    RESTATES one by superseding its rows. Not commit.py,
#:                    because a frozen quarter is not an event anybody entered; not marks.py,
#:                    because it replaces no mark. It is run from the terminal or from Python,
#:                    not from an action: the marks rule's `writes` names marks and events, and a
#:                    freeze is neither.
#:   marks.py         REPLACES A MARK in store/. A separate door from commit.py because a
#:                    replace is a different operation from an append: an event happened once,
#:                    a price is replaced by design, and the two must not share a code path
#:                    that could confuse them.
#:   observations.py  REPLACES AN ACCOUNT READING in store/ — a mark too, on the same terms.
#:   research_notes.py
#:                    APPENDS A PUBLISHED NOTE'S ROWS to store/.
#:   withdraw.py      MOVES A DOCUMENT OUT of _inbox/. Separate from dropoff.py for the same
#:                    reason marks.py is separate from commit.py, and for a sharper one:
#:                    test_intake.py proves on dropoff.py's syntax tree that the way IN can
#:                    never become the way out, so putting the exit there would have meant
#:                    deleting `move` from that test's forbidden set. Gutting a guard to do the
#:                    thing it forbids is not a refactor.
#:   agent.py         WRITES THE DESK'S LAUNCHAGENT, one plist in ~/Library/LaunchAgents, and
#:                    deletes only that plist. Nothing of the book: it is the desk's own start,
#:                    run from the terminal (`portfusion desk --install-agent`), never an action.
#:
#: OUTSIDE desk/:
#:
#:   feeds/ig.py, feeds/tv.py
#:                    each its own sign-in file, out of git and never the record
#:                    (`test_tv.py::test_a_feed_writes_nothing_but_its_own_sign_in`).
#:   history/_appendonly.py
#:                    BANKS a history, swapped in whole: the three histories' one writer.
#:   init/__init__.py WRITES A NEW BOOK: its tables, histories, hooks and ignore list.
#:   record/migrations.py
#:                    MOVES A BOOK to this release's shape, on `portfusion migrate --write`, and
#:                    puts every file back if the book will not open.
#:   record/schema.py `dump()`, which nothing calls.
#:
#: desk/icon.py RETURNS BYTES and writes nothing — if it ever starts writing, this set is what
#: says so.
WRITERS = {"desk/agent.py", "desk/auth.py", "desk/intake/bench.py", "desk/doors/commit.py",
           "desk/doors/envelope.py", "desk/intake/dropoff.py", "desk/doors/freeze.py",
           "desk/doors/marks.py", "desk/doors/observations.py", "desk/doors/research_notes.py",
           "desk/intake/withdraw.py", "desk/publish.py", "feeds/ig.py", "feeds/tv.py",
           "history/_appendonly.py", "init/__init__.py", "record/migrations.py", "record/schema.py"}


@functools.cache
def _writes():
    """Every write call in the package (`harness.file_calls`), with the module, from the package,
    and the expression written TO. The target matters and the filename does not: a module writing
    a plist into ~/Library and one writing a row into store/buys.csv both "write"; only one of them
    touches the record."""
    files = [f for f in sorted(SRC.rglob("*.py"))
             if f.relative_to(SRC).parts[0] not in ("tests", "demo")]
    return [(file.relative_to(SRC).as_posix(), target, line)
            for file in files for line, _, target in file_calls(file)]


#: The doors that may write to store/, and what each may write.
#:
#: Append against replace is the marks rule's distinction, and it is the reason these are separate
#: modules rather than one with a flag: an EVENT happened once and its table is append-only, a
#: MARK is replaced by design and is safe only because its outgoing value is banked first. A
#: single code path that could do either is a code path that can confuse them.
STORE_DOORS_UNDER_DESK = {
    # AN EVENT GOES WHERE ITS DATE PUTS IT (`envelope.place()`), whichever door adds it.
    "doors/commit.py": "adds an event where its date puts it",
    # Its restore takes the paths a door held, which the scan cannot resolve: declared here.
    "doors/envelope.py": "writes back what a door held",
    "doors/marks.py": "replaces a mark, or retires a contract nothing holds",
    # An account reading is a MARK — the marks rule names "live equity" in as many words — so it is
    # replaced, banked first, like a price.
    "doors/observations.py": "replaces an account reading",
    # A quarter end, derived by the engine and written to quarter-snapshots, -nav and -results.
    "doors/freeze.py": "adds a frozen quarter end, or restates one, superseding its rows",
    # A published research note's rows, one per code it covers, from the research repo's own
    # frontmatter on the Bench's press, placed by `envelope.placed()`.
    "doors/research_notes.py": "adds a published research note",
}


def test_only_the_declared_doors_under_desk_write_the_record():
    """THE WRITE TARGET, NOT THE FILENAME.

    A set of FILENAMES conflates "writes a file" with "writes the record": bench.py writes its
    bench note and dropoff.py writes into _inbox/, and neither goes near store/. The claim worth
    making is the one the module docstring makes, and a filename cannot say what a call wrote
    to. A filename set would also fail on any split of a module, which is a check standing in
    the way of tidying rather than protecting anything.

    A NAMED map rather than a count, so another door fails here until somebody writes down what
    it may write and why.

    A write whose path arrives as a PARAMETER cannot be resolved by the scan below, so the
    envelope's restore is not seen to write the store: the envelope is declared a door, and a
    call to its `place()` or `journal()` is a store write wherever it is made.
    """
    assert STORE_NAMES.search("schema.TABLES[t].path") and not STORE_NAMES.search("restore(x)")
    store_writers = {module.removeprefix("desk/") for module, target, _ in _writes()
                     if module.startswith("desk/") and STORE_NAMES.search(target)}
    # AND THE FOLDER SAYS SO. desk/doors/ holds the store writers and nothing else, so the code
    # that can change the record is the code in one place — a store write outside it, or a
    # module inside it that writes no store file, fails here.
    in_doors = {f"doors/{p.name}" for p in (SRC / "desk" / "doors").glob("*.py")
                if p.name != "__init__.py"}
    assert in_doors == set(STORE_DOORS_UNDER_DESK), (
        f"desk/doors/ holds {sorted(in_doors)}; the declared doors are "
        f"{sorted(STORE_DOORS_UNDER_DESK)}")
    assert store_writers == set(STORE_DOORS_UNDER_DESK), (
        f"these modules under desk/ write to store/: {sorted(store_writers)}. The declared "
        f"doors are "
        + "; ".join(f"{m} {w}" for m, w in sorted(STORE_DOORS_UNDER_DESK.items()))
        + ". A new one is not forbidden, it is forbidden to be quiet.")


def test_a_new_writer_is_a_decision():
    """A module anywhere in the package that starts writing ANYTHING must be written down before
    it can pass. The set is not a count — it is a named list, and a new entry fails here until
    somebody says what it writes and why."""
    writers = {module for module, _, _ in _writes()}
    assert writers == WRITERS, (
        f"the set of writing modules changed: {sorted(writers)}. "
        f"Added: {sorted(writers - WRITERS)}. Removed: {sorted(WRITERS - writers)}.")


@pytest.mark.parametrize("code, writes", [
    ("os.replace(tmp, path)", "replace"), ("path.replace(target)", "replace"),
    ("os.rename(a, b)", "rename"), ("open(path, 'w')", "open"), ("open(path, mode='a')", "open"),
    ("path.open('x')", "open"), ("shutil.rmtree(folder)", "rmtree"),
    ("os.remove(path)", "remove"), ("shutil.copy(a, b)", "copy"), ("path.rename(target)", "rename"),
    ("path.touch()", "touch"), ("path.rmdir()", "rmdir"),
    ("os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)", "open"),
    ("envelope.place(rows)", "place"), ("envelope.journal(rows)", "journal"),
    ("'2026-10-21'.replace('-', '')", None), ("frame.rename(columns={'a': 'b'})", None),
    ("book.journal(since=day)", None), ("rows.append(row)", None),
    ("open(path)", None), ("open(path, 'rb')", None), ("rows.remove(row)", None),
    ("frame.copy()", None), ("os.open(path, os.O_RDONLY)", None),
])
def test_the_write_scan_sees_every_way_a_file_is_written(code, writes):
    """WHAT THE SCAN CALLS A WRITE (`harness.write_call`): an atomic swap (`os.replace`), a rename,
    a removal, a copy, a removed folder and an `open()` for writing; and not a string's replace,
    a frame's rename or copy, or a list's remove."""
    import ast
    assert write_call(ast.parse(code).body[0].value) == writes
