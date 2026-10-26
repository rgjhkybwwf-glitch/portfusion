"""
EVERY READ OF THE STORE GOES THROUGH A DECLARED DOOR.

An AST scan of the whole repository against an explicit allow-list. Matched on the call and the
names in what it opens, never on a file's text or a substring, and across every module.

The allow-list is the point: each door is named, so closing one is a visible deletion from
this file rather than a silent improvement nobody can audit.
"""
import ast
import pathlib

import pytest

from harness import (NO_CHECKOUT, ROOT, SRC, STORE_NAMES, TESTS, book_classes, engine_files,
                     file_calls, needs)

#: EVERY MODULE THAT OPENS A FILE OF THE STORE, to read it or to write it, and each one is a door
#: into store/: a call on a path a table, the store's folder or a `store` names
#: (`harness.file_calls`, `harness.STORE_NAMES`). A new door is not forbidden, it is forbidden to
#: be quiet; closing one is a deletion here that somebody can point at.
#:
#:   record/schema.py     THE INTENDED DOOR. load(ref) is what every table in schema.TABLES
#:                        comes through.
#:   engine/store.py      load_store() reads price-history, fx-history and
#:                        account-statements with pd.read_csv — the three files that are
#:                        not in schema.TABLES. It asks `D.store_dir()` where the store is,
#:                        so it reads the same store as every other table (the sentinel tests
#:                        below).
#:   history/_appendonly.py  THE THREE HISTORIES, through one reader. Nullable is an argument.
#:
#: The engine reads the same three files with pandas, and that is deliberate rather than
#: unfinished: it wants FRAMES for analysis where history/ wants ROWS for appending, and the
#: travel rules keep the build and the feeds apart on purpose.
#:   desk/doors/envelope.py a table REWRITTEN ROW BY ROW (`rewrite()`): every line it is not
#:                        replacing or taking out passes through as the bytes it read. Going
#:                        through a csv writer instead would requote unrelated rows — bytes
#:                        changing without meaning changing, which makes a diff nobody can read,
#:                        and this store is CSV so that a diff can be read. And an event placed
#:                        where its date puts it (`place()`, `placed()`), the journal, and the
#:                        bytes put back when a write fails (`atomic()`).
#:   desk/doors/marks.py, desk/doors/freeze.py
#:                        a mark replaced or retired, and a quarter end restated, through the
#:                        envelope's `rewrite()`.
#:   desk/doors/observations.py the same, for account-readings.csv, whose rows it also reads as
#:                        raw cells because a reading replaces the MONEY columns of a row and
#:                        must leave the rest exactly as it found them: `positions` there is
#:                        NOTIONAL, which no allowlisted IG endpoint returns, so re-rendering the
#:                        row would mean composing a value for a column the reading has no
#:                        opinion about. A supplied value is a claim.
#:   record/migrations.py a release's renames, read and written line by line, on a book the
#:                        loader cannot open yet (`portfusion migrate`).
#:   desk/doors/commit.py an event, placed through the envelope.
#:   desk/doors/research_notes.py
#:                        a published research note's rows, placed by `envelope.placed()`.
#:   init/__init__.py     a new book's tables and histories, each headed as the demo's are.
#:   about.py             every table's bytes, read for the record's fingerprint in a page's stamp.
#:   tools/make_demo.py   the demo's store, written whole (`test_demo.py` holds it to the demo).
#:
#: A document is not the store: `desk/intake/read_document.py` reads _inbox/ and is not here.
STORE_FILE_DOORS = {
    "record/schema.py", "engine/store.py", "record/migrations.py",
    "desk/doors/marks.py", "desk/doors/observations.py", "desk/doors/freeze.py",
    "history/_appendonly.py", "desk/doors/commit.py", "desk/doors/envelope.py",
    "desk/doors/research_notes.py",
    "init/__init__.py", "about.py", "tools/make_demo.py",
}


def _sources(project_files):
    """Every .py file in the project except the tests and the archive."""
    for path in project_files(".py"):
        if path.is_relative_to(TESTS) or path.relative_to(ROOT).parts[0] == "_archive":
            continue
        yield (path.relative_to(SRC) if path.is_relative_to(SRC) else path.relative_to(ROOT)).as_posix(), path


def _store_calls(path):
    """(line, call) for each call in `path` that opens a file of the store, to read or to write."""
    return [(line, call) for line, call, target in file_calls(path, reads=True)
            if STORE_NAMES.search(target)]


def test_every_store_read_goes_through_a_declared_door(project_files):
    """The set of files that touch the store is a DECISION, written down here.

    A new door is not forbidden — it is forbidden to be quiet. Adding one means adding a
    line to STORE_FILE_DOORS above, which is a diff a reviewer sees.
    """
    found = {rel for rel, path in _sources(project_files) if _store_calls(path)}
    assert found == STORE_FILE_DOORS, (
        f"store doors changed.\n  opened: {sorted(found - STORE_FILE_DOORS)}\n"
        f"  closed: {sorted(STORE_FILE_DOORS - found)}\n"
        f"If a door was closed, delete it from the list. If one was opened, say why "
        f"beside it — a new reader of the record is a decision, not a detail.")


def test_the_engine_still_reads_the_record_through_one_function():
    """The engine's own rule, checked by AST rather than by splitting its text.

    Every store read inside the engine, in any of its files, is inside load_store(). This
    survives a rename and a reorder.
    """
    path = SRC / "engine" / "store.py"
    hits = [(p, line, call) for p in engine_files() for line, call in _store_calls(p)]
    seam = next(n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.FunctionDef)
                and n.name == "load_store")
    assert hits, "the engine reads no store file at all — has the seam moved?"
    outside = [(p.name, line, call) for p, line, call in hits
               if p != path or not seam.lineno <= line <= seam.end_lineno]
    assert not outside, (
        f"the engine opens a store file outside load_store(): {sorted(outside)}. "
        f"Every table must come through the seam.")


def test_the_store_loads_no_frame_nothing_reads(project_files):
    """A FRAME NOTHING READS IS A SECOND COPY OF A TABLE, built with every Book and waiting for a
    reader to choose it over the record's own rows. As the registry refuses a figure nothing
    renders, this refuses a frame nothing outside the tests reads."""
    from portfusion.engine import load_store
    read = set()
    for path in project_files(".py"):
        if path.is_relative_to(TESTS):
            continue
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                    and isinstance(n.slice.value, str)
                    and "store" in (getattr(n.value, "attr", None), getattr(n.value, "id", None))):
                read.add(n.slice.value)
    unread = set(load_store()) - read
    assert not unread, (
        f"load_store() builds {sorted(unread)}, which nothing reads. Read the table through the "
        f"record's rows or drop the frame: two copies of one table is two populations to choose from.")


def test_the_engine_imports_nothing_but_the_record_and_pandas(imports_of):
    """The engine's own rule: it imports the record, pandas and house's places, and nothing
    else. A file of the engine may import another (`engine`)."""
    for path in engine_files():
        assert imports_of(path) <= {"__future__", "pandas", "record", "engine", "house"}, path.name
        # `record` is a package, so the name above admits all of it. The rule is the RECORD'S
        # RULES alone, so what the engine takes from the package is checked by its DOTTED name,
        # every form alike: `from portfusion.record import schema`, and
        # `from portfusion.record.schema import TABLES`.
        taken = {m for m in imports_of(path, dotted=True) if m.startswith("record.")}
        assert taken <= {"record.rules"}, f"engine/{path.name} takes {sorted(taken)} from record/"


@pytest.mark.parametrize("door", sorted(STORE_FILE_DOORS))
def test_each_declared_door_still_exists(door):
    """A door listed here that no longer opens anything is stale documentation. The set
    equality above catches it, but this names WHICH one so the failure reads plainly."""
    if door.startswith("tools/") and ROOT is None:
        pytest.skip(NO_CHECKOUT)                    # the maintainer's tools sit beside the app
    path = ROOT / door if door.startswith("tools/") else SRC / door
    assert path.exists(), f"{door} is on the list but the file is gone"
    assert _store_calls(path), f"{door} opens no file of the store now — remove it from the list"


# =====================================================================================
# THE STORE IS ONE MOVABLE SEAM
#
# The doors above say WHERE the record is read. These say the doors all read the SAME
# PLACE, which is a different claim.
#
# Proof is by SENTINEL, never by a copy and the record happening to agree.
# =====================================================================================

def _plant(path, col: int, value: str, eol: str = "\n") -> None:
    """`value` into the first row's column `col`, AS CSV, not split on commas: a quoted cell may
    hold one, a mark's source."""
    import csv
    import io
    lines = path.read_bytes().decode("utf-8").splitlines()
    cells = next(csv.reader([lines[1]]))
    cells[col] = value
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(cells)
    lines[1] = out.getvalue()
    path.write_bytes((eol.join(lines) + eol).encode("utf-8"))


def _sentinel_store(tmp_path):
    """The LOADED record, copied, with one unmistakable row planted in each history."""
    import shutil
    from portfusion.record import schema
    target = tmp_path / "store"
    target.mkdir()
    for csv_file in schema.STORE.glob("*.csv"):
        shutil.copy2(csv_file, target / csv_file.name)
    # THE COLUMN MATTERS. The first three are read with pandas and join to nothing, so the
    # key column takes the sentinel. `account-readings.csv` IS in schema.TABLES and its
    # `account` joins to the register, so a sentinel there is refused at the door — rightly.
    # It goes in `reference`, which is free text.
    # THE LIVE MARKS TOO, in their free-text `source`: the test that the record is put back looks
    # for the sentinel there, and with none planted it could not fail.
    planted = {}
    for name, col in (("price-history.csv", 0), ("fx-history.csv", 0),
                      ("account-statements.csv", 0), ("account-readings.csv", -1),
                      ("current-prices.csv", 4)):
        path = target / name
        if len(path.read_bytes().splitlines()) < 2:
            continue                # an empty history has nothing to carry a sentinel
        _plant(path, col, "ZZ-SENTINEL", eol="\r\n")
        planted[name] = "ZZ-SENTINEL"
    return target, planted


@needs("buys", "current-prices")
def test_moving_the_store_moves_every_table_the_engine_reads(tmp_path):
    """THE THREE READ WITH PANDAS rather than schema.load(), which is deliberate — the engine
    wants frames — but it must still be the same folder."""
    from portfusion.record import rules
    from portfusion.engine import Book

    target, _ = _sentinel_store(tmp_path)
    with rules.store_at(target):
        store = Book().store
        for key in ("history.prices", "history.fx", "statements"):
            frame = store[key]
            first = frame.columns[0]
            assert "ZZ-SENTINEL" in set(frame[first]), (
                f"Book.store[{key!r}] did not come from the store the record was pointed "
                f"at: that table reads a path of its own")


@needs("buys", "current-prices")
def test_moving_the_store_moves_the_three_append_only_histories(tmp_path):
    """`history/*` writes the record. A write that does not follow the store writes the
    REAL one while a test believes it is sandboxed — which is worse than a wrong read."""
    from portfusion.record import rules
    from portfusion.history import accounts as AH
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH

    target, _ = _sentinel_store(tmp_path)
    with rules.store_at(target):
        for module in (PH, FX, AH):
            assert pathlib.Path(module._FILE.path).parent == target, (
                f"{module.__name__} still writes to {module._FILE.path} — it bound a path "
                f"at import instead of asking where the record is.")


@needs("buys", "current-prices")
def test_the_record_is_put_back_when_the_block_ends(tmp_path):
    """`store_at()` is what makes the seam safe to use in a test at all."""
    from portfusion.record import rules
    from portfusion.record import schema

    was = schema.STORE
    target, _ = _sentinel_store(tmp_path)

    def loaded():
        return any(row[4] == "ZZ-SENTINEL" for row in rules.CURRENT_PRICES)
    with rules.store_at(target):
        assert schema.STORE == target
        assert loaded(), "the premise: inside the block, the sentinel store is the record"
    assert schema.STORE == was, "store_at() left the record pointed somewhere else"
    assert not loaded(), \
        "the sentinel store is still loaded — reload_store() did not run on the way out"


@needs("buys", "current-prices")
def test_a_book_answers_from_the_store_it_was_built_from(tmp_path):
    """A BOOK HOLDS ONE RECORD: the one it was built from, however the process's record moves.

    Its frames are taken at construction, and so is everything its methods read later — `self.D`,
    the record pinned in `_build()`. The probe is `newest_cash()`, which reads `cash_latest()`: a
    reading planted in a copy of the store must still be the Book's answer after the process's
    record has gone back to the real one.
    """
    import datetime as _dt
    import shutil
    from portfusion.record import rules, schema
    from portfusion.engine import Book

    target = tmp_path / "store"
    target.mkdir()
    for csv_file in schema.STORE.glob("*.csv"):
        shutil.copy2(csv_file, target / csv_file.name)
    # Any account with a cash reading — the probe is the planting, not the account's name.
    # A share account's: a spread-bet account's funds are on its own reading and it has no row
    # in the cash readings.
    observed = {o.account for o in rules.cash_readings}
    account = next(a for a in rules.ACCOUNT_ORDER if a in observed)
    # AFTER EVERY READING OF EITHER KIND, so the planted cash is the account's newest, and after
    # every account's cash, so it is in date order at the file's end.
    newest = max([o.as_of for o in rules.cash_readings]
                 + [r.as_of for r in rules.ac_rows if r.acct == account and r.as_of])
    after = (newest + _dt.timedelta(days=1)).isoformat()
    with (target / "cash-readings.csv").open("a", encoding="utf-8", newline="") as fh:
        fh.write(f"{account},{after},12345.67,ii-transactions,TESTPINREF1\n")

    built = Book(store_dir=target)
    assert not [o for o in rules.cash_readings if o.reference == "TESTPINREF1"], (
        "Book(store_dir=...) left the process's record pointing at the other store")

    def cash_now(book):
        return book.newest_cash().set_index("account").at[account, "cash"]

    assert cash_now(built) == 12345.67, (
        "a method answered from the process's record, not the store the Book was built from")
    assert cash_now(Book()) != 12345.67, "a Book built from the real store saw the planted row"


#: Book methods that read `rules` itself, each asked of the CLASS, where there is no Book.
ASKED_WITHOUT_A_BOOK = {
    "reconciliation_verdict": "typed constants; the Reconcile panel asks the class",
    "quarter_to_close":       "which quarter the LIVE record has due; desk/doors/freeze.py asks the class",
}

#: The `rules` functions a method may call through `self.D`. A function the record builds
#: answers from its own build, and one that reads the FILES — `store_rows()` — is called once,
#: in `_build()`; what a method calls late is held to this list, so a new late call is a visible
#: diff. The four from `record/rules_evidence.py` are its, and that module holds no table at
#: all. `schema`'s are held to this list as well: `filed_statements()` lists
#: `_archive/statements/`, which is no table and which no Book pins, so a document filed after a
#: Book was built is on file to it. `funding_nights()` reads a row's own detail with a regex and
#: no table.
CALLABLE_THROUGH_THE_PIN = {"evidence_from_source", "reference_resolves", "document_not_on_file",
                            "states_cash", "filed_statements", "funding_nights"}


def test_the_evidence_rules_cannot_reach_a_table(repo_root):
    """What CALLABLE_THROUGH_THE_PIN takes from `record/rules_evidence.py` is safe to call late
    only while that module imports nothing that could hold the store."""
    import ast
    tree = ast.parse((SRC / "record" / "rules_evidence.py").read_text(encoding="utf-8"))
    imported = ({a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                 for a in n.names}
                | {(n.module or ".").split(".")[0] for n in ast.walk(tree)
                   if isinstance(n, ast.ImportFrom)})
    assert imported <= {"__future__", "datetime", "re", "typing"}, (
        f"record/rules_evidence.py imports {sorted(imported)}; if one of them holds a table, take "
        f"its functions out of CALLABLE_THROUGH_THE_PIN")


def test_no_book_method_reads_the_process_record(repo_root):
    """THE SOURCE HALF of the test above, which can only probe the methods it calls.

    Inside `Book` and the classes it is built from, nothing but construction reads `rules`
    directly; a module-level helper that reads it is handed `self.D`; and a `rules` function
    called through `self.D` is one that reads no table. Each exception is named above with its
    reason.
    """
    import ast
    reads_rules = {f.name for path in engine_files()
                   for f in ast.parse(path.read_text(encoding="utf-8")).body
                   if isinstance(f, ast.FunctionDef)
                   and any(isinstance(n, ast.Name) and n.id == "D" for n in ast.walk(f))}
    offenders = []
    for c, method in ((c, m) for c in book_classes() for m in c.body):
        if not isinstance(method, ast.FunctionDef):
            continue
        if method.name in ("__init__", "_build") or method.name in ASKED_WITHOUT_A_BOOK:
            continue
        for n in ast.walk(method):
            if isinstance(n, ast.Name) and n.id == "D":
                offenders.append(f"{c.name}.{method.name}:{n.lineno} reads rules, not self.D")
            if not isinstance(n, ast.Call):
                continue
            if isinstance(n.func, ast.Name) and n.func.id in reads_rules and not any(
                    ast.unparse(a) == "self.D" for a in [*n.args, *(k.value for k in n.keywords)]):
                offenders.append(f"{c.name}.{method.name}:{n.lineno} calls {n.func.id}() "
                                 f"without self.D")
            if (isinstance(n.func, ast.Attribute)
                    and ast.unparse(n.func.value) in ("self.D", "self.D.schema")
                    and n.func.attr not in CALLABLE_THROUGH_THE_PIN):
                offenders.append(f"{c.name}.{method.name}:{n.lineno} calls "
                                 f"self.D.{n.func.attr}() late")
    assert not offenders, (
        "a Book method reaches past the record it was built from:\n  " + "\n  ".join(offenders))


def test_the_archive_is_listed_in_one_place(project_files, repo_root):
    """`schema.statements()` is where a document is filed and `schema.filed_statements()` is what
    is there. A module composes the path here or not at all."""
    import re
    composed = re.compile(r"[\"']_archive[\"']\s*/\s*[\"']statements[\"']")
    from harness import app_name
    found = [app_name(p) for p in project_files(".py")
             if not p.is_relative_to(TESTS) and composed.search(p.read_text())]
    assert found == ["record/schema.py"], (
        f"the archive's path is composed in {found}; use schema.statements() and "
        f"schema.filed_statements()")


def test_a_hidden_file_or_a_folder_is_not_a_filed_document(monkeypatch, tmp_path):
    """What `filed_statements()` counts: the documents, sorted, and not the `.DS_Store` Finder
    leaves behind or a folder somebody made. No archive at all is an empty list, not an error."""
    from portfusion.record import schema
    monkeypatch.setattr(schema, "BOOK", tmp_path)
    assert schema.filed_statements() == []
    (folder := schema.statements()).mkdir(parents=True)
    for name in ("30 Sep 2026 IG statement (Voss IG Spread bet).pdf", ".DS_Store",
                 "02 Sep 2026 ii broker direct (Voss ii ISA).csv"):
        (folder / name).write_bytes(b"x")
    (folder / "loose").mkdir()
    assert schema.filed_statements() == ["02 Sep 2026 ii broker direct (Voss ii ISA).csv",
                                         "30 Sep 2026 IG statement (Voss IG Spread bet).pdf"]


def test_the_import_reader_sees_a_module_imported_from_the_package(imports_of, tmp_path):
    """THE GUARDS ON `imports_of` CAN FIRE. Each asks whether a name is absent, and absence is
    also what a scan that cannot see the name reports. Under one package every import begins with
    the package's name, so it is read past it: `from portfusion import engine` IMPORTS THE ENGINE,
    and each name is read, dotted or not."""
    src = tmp_path / "m.py"
    src.write_text("from portfusion import engine, desk as d\nimport portfusion.record.rules\n"
                   "from portfusion.history import fx\nfrom portfusion.record.schema import STORE\n")
    assert {"engine", "desk", "record", "history"} <= imports_of(src)
    assert {"record.rules", "history.fx", "record.schema"} <= imports_of(src, dotted=True)


@needs("buys")
def test_a_store_that_will_not_load_leaves_the_record_where_it_was(store_copy, tmp_path):
    """A REFUSED RELOAD LEAVES THE RECORD EXACTLY AS IT WAS: `store_at()` puts it back when the
    store it was given will not load, and a reload the record refuses rebinds no name — the
    tables are built apart and taken only when the whole build has passed.

    The planted fault is one the record finds LATE, after the ledger is read: a loader that bound
    each table as it went would already hold the refused rows beside the old ones."""
    import shutil
    from portfusion.record import rules, schema
    was = schema.STORE
    bad = tmp_path / "refused" / "store"
    shutil.copytree(schema.STORE, bad)
    trades = bad / "buys.csv"
    lines = trades.read_text(encoding="utf-8").splitlines()
    trades.write_text("\n".join([lines[0], "not,a,trade"]) + "\n", encoding="utf-8")
    with pytest.raises(Exception):
        with rules.store_at(bad):
            pass
    assert schema.STORE == was, "the record was left pointing at the store that would not load"

    before = dict(vars(rules))
    _plant(store_copy / "buys.csv", rules.Buy._fields.index("cur"), "JPY")   # a third currency
    with pytest.raises(ValueError, match="neither sterling"):
        rules.reload_store()
    moved = sorted(name for name, value in before.items() if vars(rules)[name] is not value)
    assert not moved, f"a refused reload left a mixture in memory; rebound: {moved}"


def test_a_missing_history_is_refused_by_name(tmp_path):
    """A BOOK WITHOUT ITS PRICE HISTORY is refused in words that name the file — not a bare
    FileNotFoundError, and not a history taken to hold no mark."""
    import shutil
    from portfusion.engine import Book
    from portfusion.record import schema
    copy = tmp_path / "store"
    shutil.copytree(schema.STORE, copy)
    (copy / "price-history.csv").unlink()
    with pytest.raises(SystemExit, match="price-history.csv is missing"):
        Book(store_dir=copy)


def test_a_book_from_another_store_is_measured_from_its_own_start(tmp_path):
    """EACH BOOK READS ITS OWN START. A Book built from another store is measured from that
    store's start."""
    import shutil
    from portfusion.engine import Book, record_begins
    from portfusion.record import schema
    copy = tmp_path / "store"
    shutil.copytree(schema.STORE, copy)
    settings = copy / "settings.csv"
    lines = settings.read_text(encoding="utf-8").splitlines()
    begins = next(ln for ln in lines if ln.startswith("record_begins,")).split(",")[1]
    later = f"{int(begins[:4]) + 1}{begins[4:]}"
    settings.write_text("\n".join(f"record_begins,{later}" if ln.startswith("record_begins,")
                                  else ln for ln in lines) + "\n", encoding="utf-8")
    other = Book(store_dir=copy)
    assert str(other.baseline.date()) == later
    assert str(Book().baseline.date()) == begins == str(record_begins().date()), \
        "the loaded book's start moved with another store's"
