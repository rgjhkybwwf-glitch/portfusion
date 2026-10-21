"""
EVERY READ OF THE STORE GOES THROUGH A DECLARED DOOR.

An AST scan of the whole repository against an explicit allow-list. It replaced a check that
had three holes, and each is a reason for the shape of this one:

  1. It read engine.py as TEXT — `source.split("def load_store()")` — so it enforced the
     rule by position in a file. Renaming the function or moving it broke the check
     without changing a single behaviour.
  2. Its door list was `("read_csv(", "open()", "DictReader(")`, and **"open()" matches
     nothing anybody writes**. `open(path)` does not contain the substring `open()`.
     The most common way to open a file was never checked at all.
  3. It could only ever see engine.py. The identical violation in the report and in all
     three history modules was invisible to it, while the docs said load_store() was the
     one door. It was one of five.

The allow-list is the point: each door is named, so closing one is a visible deletion from
this file rather than a silent improvement nobody can audit.
"""
import ast
import pathlib

import pytest

from harness import ROOT, SRC, TESTS, needs

#: The CSV doors. These four constructors plus pandas are how tabular data enters or
#: leaves a file in this project — every store access goes through one of them, and
#: nothing else in the repo uses them. Scoping to CSV rather than to `open` is what keeps
#: this precise: dropoff opens documents, and that is not a record door.
CSV_CALLS = {"reader", "DictReader", "writer", "DictWriter", "read_csv", "to_csv"}

#: A csv.writer over an in-memory buffer FORMATS a line; it does not open anything. feeds/ig.py
#: and desk/doors/commit.py both do this to build one CSV row for printing, and neither is a
#: door on that account.
BUFFER_HINTS = ("buf", "stringio", "io.")

#: EVERY MODULE THAT READS OR WRITES A CSV FILE, and each one is a door into store/. A new
#: door is not forbidden, it is forbidden to be quiet; closing one is a deletion here that
#: somebody can point at.
#:
#:   record/schema.py     THE INTENDED DOOR. load(ref) is what every table in schema.TABLES
#:                        comes through.
#:   engine.py              load_store() reads price-history, fx-history and
#:                        account-statements with pd.read_csv — the three files that are
#:                        not in schema.TABLES. It asks `D.store_dir()` where the store is,
#:                        so it reads the same store as every other table (the sentinel tests
#:                        below).
#:   history/_appendonly.py  THE THREE HISTORIES, through one reader. Three modules each with
#:                        their own load/save/known were three parse rules: one coerced a blank
#:                        to None and two raised on it, for no reason anybody chose. One
#:                        implementation now, with nullable an argument.
#:
#: The engine reads the same three files with pandas, and that is deliberate rather than
#: unfinished: it wants FRAMES for analysis where history/ wants ROWS for appending, and the
#: travel rules keep the build and the feeds apart on purpose. Two readers for two jobs is not
#: the defect this list was drawn up to shrink; five readers of one file with five parse rules
#: was.
#:   desk/doors/marks.py        a READ in service of a REPLACE. Replacing one mark means reading the
#:                        file LINE BY LINE and passing every line it is not replacing through
#:                        as the bytes it read. Going through a csv writer instead would requote
#:                        unrelated rows — bytes changing without meaning changing, which makes
#:                        a diff nobody can read, and this store is CSV so that a diff can be
#:                        read.
#:   desk/doors/observations.py the same read in service of the same replace, for a different
#:                        table. It reads account-observations.csv line by line because a
#:                        reading replaces the MONEY columns of a row and must leave the rest
#:                        exactly as it found them: `positions` there is NOTIONAL, which no
#:                        allowlisted IG endpoint returns, so re-rendering the row would mean
#:                        composing a value for a column the reading has no opinion about. A
#:                        supplied value is a claim.
#:   desk/doors/freeze.py the same read in service of a SUPERSEDE. A restatement
#:                        moves the `status` of the rows it replaces and nothing else, so every
#:                        line it is not marking passes through as the bytes it read.
#:
#: `desk/intake/read_document.py` READS DOCUMENTS AND IS NOT HERE. A UK broker's export is CP1252 and
#: a strict utf-8 open raised on four of five real HL downloads, so it decodes the bytes itself
#: and parses from memory; the scan resolves a csv call's target back to an assignment and
#: cannot see one there. That is the scan being honest about what it can prove, and the module
#: reads _inbox/, which is not the record.
CSV_FILE_READERS = {
    "record/schema.py", "engine.py",
    "desk/doors/marks.py", "desk/doors/observations.py", "desk/doors/freeze.py",
    "history/_appendonly.py",
}


def _sources(project_files):
    """Every .py file in the project except the tests and the archive."""
    for path in project_files(".py"):
        if path.is_relative_to(TESTS) or path.relative_to(ROOT).parts[0] == "_archive":
            continue
        yield (path.relative_to(SRC) if path.is_relative_to(SRC) else path.relative_to(ROOT)).as_posix(), path


def _csv_calls(path):
    """Every call in `path` that points a CSV reader or writer at a FILE.

    Returns (tree, parents, hits). Matched on the call itself, so `open(path)`,
    `pd.read_csv(STORE / x)` and `(ROOT / p).open()` all register through the csv or
    pandas call wrapped around them — the retired check's `"open()"` literal matched none
    of those, because `open(path)` does not contain the substring `open()`.
    """
    src = path.read_text()
    tree = ast.parse(src)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else \
            node.func.id if isinstance(node.func, ast.Name) else None
        if name not in CSV_CALLS:
            continue
        first = ast.get_source_segment(src, node.args[0]) if node.args else ""
        target = (first or "").lower()
        if isinstance(node.func, ast.Attribute) and not node.args:
            target = (ast.get_source_segment(src, node.func.value) or "").lower()
        if any(h in target for h in BUFFER_HINTS):
            continue                                    # formats a line, opens nothing
        hits.append((node, name))
    return tree, parents, hits


def test_every_store_read_goes_through_a_declared_door(project_files):
    """The set of files that touch the store is a DECISION, written down here.

    A new door is not forbidden — it is forbidden to be quiet. Adding one means adding a
    line to CSV_FILE_READERS above, which is a diff a reviewer sees.
    """
    found = {rel for rel, path in _sources(project_files) if _csv_calls(path)[2]}
    assert found == CSV_FILE_READERS, (
        f"CSV file doors changed.\n  opened: {sorted(found - CSV_FILE_READERS)}\n"
        f"  closed: {sorted(CSV_FILE_READERS - found)}\n"
        f"If a door was closed, delete it from the list. If one was opened, say why "
        f"beside it — a new reader of the record is a decision, not a detail.")


def test_the_engine_still_reads_the_record_through_one_function():
    """engine.py's own rule, checked by AST rather than by splitting its text.

    Every store read inside the engine is inside load_store(). This survives a rename, a
    reorder, and a split of engine.py into a package — none of which the retired version did.
    """
    path = SRC / "engine.py"
    tree, parents, hits = _csv_calls(path)

    def enclosing_function(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return None

    assert hits, "engine.py reads no store file at all — has the seam moved?"
    outside = {(enclosing_function(n), n.lineno) for n, _ in hits
               if enclosing_function(n) != "load_store"}
    assert not outside, (
        f"engine.py opens a store file outside load_store(): {sorted(outside)}. "
        f"Every table must come through the seam.")


def test_the_store_loads_no_frame_nothing_reads(project_files):
    """A FRAME NOTHING READS IS A SECOND COPY OF A TABLE, built with every Book and waiting for a
    reader to choose it over the record's own rows. Six of fourteen were, until step 5 (15 Oct
    2026): the engine reads trades, exits, the closed positions and the register through `self.D`,
    and nothing read the frames beside them. As the registry refuses a figure nothing renders, this
    refuses a frame nothing outside the tests reads."""
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
    """The engine's own rule: it imports the record and pandas, and nothing else."""
    assert imports_of(SRC / "engine.py") <= {"__future__", "pandas", "record"}
    # `record` is a package, so the name above admits all of it. The rule was always the
    # RECORD'S RULES and nothing else of it — so what engine.py takes from the package is checked
    # by its DOTTED name, every form alike: `from portfusion.record import schema`, and
    # `from portfusion.record.schema import TABLES`, which a check of the first form alone passed.
    taken = {m for m in imports_of(SRC / "engine.py", dotted=True) if m.startswith("record.")}
    assert taken <= {"record.rules"}, f"engine.py takes {sorted(taken)} from record/"


@pytest.mark.parametrize("door", sorted(CSV_FILE_READERS))
def test_each_declared_door_still_exists(door):
    """A door listed here that no longer opens anything is stale documentation. The set
    equality above catches it, but this names WHICH one so the failure reads plainly."""
    path = SRC / door
    assert path.exists(), f"{door} is on the list but the file is gone"
    assert _csv_calls(path)[2], f"{door} no longer reads a CSV file — remove it from the list"


# =====================================================================================
# THE STORE IS ONE MOVABLE SEAM
#
# The doors above say WHERE the record is read. These say the doors all read the SAME
# PLACE, which is a different claim.
#
# While `schema.STORE` was the seam in name only — `engine.load_store()` reading three
# histories from the repo's own path, `history/_appendonly.py` binding a path at import —
# `store_copy`, the fixture whose whole job is to keep a test off the real record, moved
# twenty tables and left three behind, and fixtures patched around the ones it missed, per
# module, by hand.
#
# NOTHING FAILED, because the copy and the record agreed. That is the condition these tests
# exist to end: proof by SENTINEL rather than by two files happening to match.
# =====================================================================================

def _sentinel_store(tmp_path):
    """The LOADED record, copied, with one unmistakable row planted in each history."""
    import csv
    import shutil
    from portfusion.record import schema
    target = tmp_path / "store"
    target.mkdir()
    for csv_file in schema.STORE.glob("*.csv"):
        shutil.copy2(csv_file, target / csv_file.name)
    # THE COLUMN MATTERS. The first three are read with pandas and join to nothing, so the
    # key column takes the sentinel. `account-observations.csv` IS in schema.TABLES and its
    # `account` joins to the register, so a sentinel there is refused at the door — rightly.
    # It goes in `reference`, which is free text.
    # THE LIVE MARKS TOO, in their free-text `source`: the test that the record is put back looks
    # for the sentinel there, and with none planted it could not fail.
    planted = {}
    for name, col in (("price-history.csv", 0), ("fx-history.csv", 0),
                      ("account-statements.csv", 0), ("account-observations.csv", -1),
                      ("current-prices.csv", 4)):
        path = target / name
        lines = path.read_bytes().decode("utf-8").splitlines()
        # A LIVE ROW: a superseded one stays on file and is no answer, so a reader that filters
        # on the lifecycle rightly passes it by.
        header = next(csv.reader([lines[0]]))
        at = header.index("status") if "status" in header else None
        i = next(i for i in range(1, len(lines))
                 if at is None or next(csv.reader([lines[i]]))[at] == "live")
        # AS CSV, not split on commas: a quoted cell holding one — a mark's source — moved
        # every column after it.
        import io
        cells = next(csv.reader([lines[i]]))
        cells[col] = "ZZ-SENTINEL"
        out = io.StringIO()
        csv.writer(out, lineterminator="").writerow(cells)
        lines[i] = out.getvalue()
        path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
        planted[name] = "ZZ-SENTINEL"
    return target, planted


@needs("trades", "current-prices")
def test_moving_the_store_moves_every_table_the_engine_reads(tmp_path):
    """THE THREE THE SEAM USED TO MISS. Each is read with pandas rather than schema.load(),
    which is deliberate — the engine wants frames — but it must still be the same folder."""
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
                f"at. That table is reading a path of its own again.")


@needs("trades", "current-prices")
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


@needs("trades", "current-prices")
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


@needs("trades", "current-prices")
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
    # A share account's, since 13 Oct 2026: a spread-bet account's funds are on its own
    # reading and it has no row in the cash readings.
    observed = {o.account for o in rules.cash_observations}
    account = next(a for a in rules.ACCOUNT_ORDER if a in observed)
    # AFTER EVERY READING OF EITHER KIND, so the planted cash is the account's newest.
    newest = max([o.as_of for o in rules.cash_observations if o.account == account]
                 + [r.as_of for r in rules.ac_rows if r.acct == account and r.as_of])
    after = (newest + _dt.timedelta(days=1)).isoformat()
    with (target / "cash-observations.csv").open("a", encoding="utf-8", newline="") as fh:
        fh.write(f"{account},{after},12345.67,ii-transactions,TESTPINREF1\n")

    built = Book(store_dir=target)
    assert not [o for o in rules.cash_observations if o.reference == "TESTPINREF1"], (
        "Book(store_dir=...) left the process's record pointing at the other store")

    def cash_now(book):
        return book.newest_cash().set_index("account").at[account, "cash"]

    assert cash_now(built) == 12345.67, (
        "a method answered from the process's record, not the store the Book was built from")
    assert cash_now(Book()) != 12345.67, "a Book built from the real store saw the planted row"


#: Book methods that read `rules` itself, each asked of the CLASS, where there is no Book.
ASKED_WITHOUT_A_BOOK = {
    "account_order":          "a typed constant, the same in every store",
    "reconciliation_verdict": "typed constants; the Reconcile panel asks the class",
    "quarter_to_close":       "which quarter the LIVE record has due; desk/doors/freeze.py asks the class",
}

#: The `rules` functions a method may call through `self.D`. A function held there still reads
#: the MODULE when it runs, so only one that reads no table may be called late; one that reads
#: the store — `cash_latest()`, `store_rows()` — is called once, in `_build()`. The four from
#: `record/rules_evidence.py` are its, and that module holds no table at all. `schema`'s are held
#: to this list as well: `filed_statements()` lists `_archive/statements/`, which is no table and
#: which no Book pins, so a document filed after a Book was built is on file to it.
#: `funding_nights()` reads a row's own detail with a regex and no table (13 Oct 2026).
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

    Inside `Book`, nothing but construction reads `rules` directly; a module-level helper that
    reads it is handed `self.D`; and a `rules` function called through `self.D` is one that
    reads no table. Each exception is named above with its reason.
    """
    import ast
    tree = ast.parse((SRC / "engine.py").read_text(encoding="utf-8"))
    reads_rules = {f.name for f in tree.body if isinstance(f, ast.FunctionDef)
                   and any(isinstance(n, ast.Name) and n.id == "D" for n in ast.walk(f))}
    book = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Book")
    offenders = []
    for method in book.body:
        if not isinstance(method, ast.FunctionDef):
            continue
        if method.name in ("__init__", "_build") or method.name in ASKED_WITHOUT_A_BOOK:
            continue
        for n in ast.walk(method):
            if isinstance(n, ast.Name) and n.id == "D":
                offenders.append(f"{method.name}:{n.lineno} reads rules, not self.D")
            if not isinstance(n, ast.Call):
                continue
            if isinstance(n.func, ast.Name) and n.func.id in reads_rules and not any(
                    ast.unparse(a) == "self.D" for a in [*n.args, *(k.value for k in n.keywords)]):
                offenders.append(f"{method.name}:{n.lineno} calls {n.func.id}() without self.D")
            if (isinstance(n.func, ast.Attribute)
                    and ast.unparse(n.func.value) in ("self.D", "self.D.schema")
                    and n.func.attr not in CALLABLE_THROUGH_THE_PIN):
                offenders.append(f"{method.name}:{n.lineno} calls self.D.{n.func.attr}() late")
    assert not offenders, (
        "a Book method reaches past the record it was built from:\n  " + "\n  ".join(offenders))


def test_the_archive_is_listed_in_one_place(project_files, repo_root):
    """`schema.STATEMENTS` is where a document is filed and `schema.filed_statements()` is what is
    there. Four modules composed the path and five listed the folder until 2 Oct 2026. A new
    one composes it here or not at all."""
    import re
    composed = re.compile(r"[\"']_archive[\"']\s*/\s*[\"']statements[\"']")
    from harness import app_name
    found = [app_name(p) for p in project_files(".py")
             if not p.is_relative_to(TESTS) and composed.search(p.read_text())]
    assert found == ["record/schema.py"], (
        f"the archive's path is composed in {found}; use schema.STATEMENTS and "
        f"schema.filed_statements()")


def test_a_hidden_file_or_a_folder_is_not_a_filed_document(monkeypatch, tmp_path):
    """What `filed_statements()` counts: the documents, sorted, and not the `.DS_Store` Finder
    leaves behind or a folder somebody made. No archive at all is an empty list, not an error."""
    from portfusion.record import schema
    for name in ("30 Sep 2026 IG statement (Voss IG Spread bet).pdf", ".DS_Store",
                 "02 Sep 2026 ii broker direct (Voss ii ISA).csv"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "loose").mkdir()
    monkeypatch.setattr(schema, "STATEMENTS", tmp_path)
    assert schema.filed_statements() == ["02 Sep 2026 ii broker direct (Voss ii ISA).csv",
                                         "30 Sep 2026 IG statement (Voss IG Spread bet).pdf"]
    monkeypatch.setattr(schema, "STATEMENTS", tmp_path / "absent")
    assert schema.filed_statements() == []


def test_the_import_reader_sees_a_module_imported_from_the_package(imports_of, tmp_path):
    """`from portfusion import engine` IMPORTS THE ENGINE. The reader took the package for the
    import and never the name after it, so every boundary guard asking whether a file imports
    `engine` or `desk` passed this form, which the report already uses (the review of 21 Oct
    2026). Each name is read, dotted or not."""
    src = tmp_path / "m.py"
    src.write_text("from portfusion import engine, desk as d\nimport portfusion.record.rules\n")
    assert {"engine", "desk", "record"} <= imports_of(src)
    assert "record.rules" in imports_of(src, dotted=True)


def test_a_store_that_will_not_load_leaves_the_record_where_it_was(tmp_path):
    """`store_at()` PUTS THE RECORD BACK EVEN WHEN THE STORE IT WAS GIVEN WILL NOT LOAD. The move
    happened before the block was entered, so a refusal from it left `schema.STORE` pointing at
    the store that failed (the review of 21 Oct 2026)."""
    import shutil
    from portfusion.record import rules, schema
    was = schema.STORE
    bad = tmp_path / "store"
    shutil.copytree(schema.STORE, bad)
    trades = bad / "trades.csv"
    lines = trades.read_text(encoding="utf-8").splitlines()
    trades.write_text("\n".join([lines[0], "not,a,trade"]) + "\n", encoding="utf-8")
    with pytest.raises(Exception):
        with rules.store_at(bad):
            pass
    assert schema.STORE == was, "the record was left pointing at the store that would not load"


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
    """EACH BOOK READS ITS OWN START. The engine read the day the record begins once, when it was
    imported, so a Book built from another store — or after the setting changed — was measured
    from the loaded book's start (the review of 21 Oct 2026)."""
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
