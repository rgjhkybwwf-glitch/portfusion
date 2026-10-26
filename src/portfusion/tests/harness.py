"""
THE HARNESS: the suite's shared fixtures and hooks, loaded as a plugin (`-p harness`, pytest.ini)
so they reach a book's own checks as well as `tests/`. A conftest's fixtures reach only the
folder it sits in, and a book's checks sit in the book's folder. The app is imported as the
installed package, `portfusion`, which the venv's editable install points at this checkout's
`src/`.

record/rules.py loads the record on import and runs no build.

The report is importable: its page is `report.page.render()` and its command line sits behind a
__main__ guard, so collecting the tests runs no command.

The subprocess tests in test_report.py run the real command line — the gate's refusal, the exit
code — which is how the report is actually invoked, and an in-process call would not prove it.
"""
import functools
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

#: THE APP'S SOURCE: the package this suite ships inside, installed or checked out. A test names a
#: module from here (`record/schema.py`), as the code's own prose does.
SRC = Path(__file__).resolve().parent.parent
#: THE CHECKOUT, when the app runs from one: anything outside the package (`tools/glossary.py`, the
#: guides, the hooks) is named from here. NONE ON AN INSTALLED COPY, where a test that needs it
#: skips through `repo_root` or `project_files` and says so.
ROOT = SRC.parents[1] if (SRC.parents[1] / "pyproject.toml").is_file() else None
#: THE SUITE ITSELF, inside the package it tests: the code-reading guards skip it by this.
TESTS = SRC / "tests"

_BOOK_STATE = pytest.StashKey[dict]()
_BOOK_MOVED = pytest.StashKey[list]()
_SKIPS_OFF = pytest.StashKey[list]()
_SKIPS_RAN = pytest.StashKey[list]()

#: THE SKIPS A BOOK EXPECTS, one test per line, in that book's `checks/` folder. A test the book
#: cannot give rows to skips, which is right on a new book and wrong on one that has the rows: a
#: skip there hides a test. A book that lists its skips has every other one fail the run, and a
#: listed one that ran: its line would let the test skip unseen later.
SKIPS_FILE = "skips.txt"
#: Why a test that reads the checkout skips on an installed copy.
NO_CHECKOUT = "reads the checkout (its guides, tools or git), and this copy of the app is installed"
#: A test that reads the checkout and asks for neither fixture says so with this.
needs_checkout = pytest.mark.skipif(ROOT is None, reason=NO_CHECKOUT)
#: Why a test of the demo's own documents skips on another book.
DEMO_ONLY = "reads the demo's own documents, and another book is loaded"


def app_name(path) -> str:
    """A project file's name as the tests write it: from SRC for the app's own files, from ROOT
    for everything else."""
    path = Path(path)
    return (path.relative_to(SRC) if path.is_relative_to(SRC) or ROOT is None
            else path.relative_to(ROOT)).as_posix()


def engine_files() -> list[Path]:
    """The engine's source files: the package `engine/`, one file per topic."""
    return sorted((SRC / "engine").glob("*.py"))


def desk_script(name: str | None = None) -> str:
    """The desk's script: every file of `desk/bundle.py`'s SCRIPTS, in the order the page loads
    them, or the one file named."""
    from portfusion.desk import bundle
    return "".join((SRC / "desk" / "static" / n).read_text(encoding="utf-8")
                   for n in ([name] if name else bundle.SCRIPTS))


def book_classes() -> list:
    """`Book` and every class it is built from, as the engine's files define them: `ClassDef`s."""
    import ast
    defs = [n for p in engine_files() for n in ast.parse(p.read_text(encoding="utf-8")).body
            if isinstance(n, ast.ClassDef)]
    classes = {n.name: n for n in defs}
    assert len(classes) == len(defs), "two of the engine's files define a class of one name"
    found, todo = [], ["Book"]
    while todo:
        c = classes[todo.pop(0)]
        if c not in found:
            found.append(c)
            bases = [ast.unparse(b) for b in c.bases]
            assert set(bases) <= set(classes), \
                f"{c.name} is built from {bases}, not all of them the engine's"
            todo += bases
    return found


def an_account(kind: str) -> str | None:
    """The loaded book's first account of `kind` ("shares", "spread bet"), in the register's
    order. A test that ASKS THE BOOK about an account takes it from here: a name typed in would
    ask the demo's question of every other book, find nothing, and pass on nothing.

    None when the book has no such account — a new book has none — and a test that needs one
    skips through `holds()`."""
    from portfusion.record import rules as D
    return next((a for a in D.ACCOUNT_ORDER if D.ACCOUNT_KIND[a] == kind), None)


def append_rows(path, lines) -> None:
    """Append `lines` to a copied store's CSV at `path`, each on its own line, whether or not
    the file ends in a newline: one that does not would join the first row to its last."""
    text = path.read_text(encoding="utf-8")
    path.write_text(text.rstrip("\n") + "\n" + "".join(f"{ln}\n" for ln in lines),
                    encoding="utf-8")


def write_rows(table: str, *rows: dict) -> None:
    """`rows` written to the copied store as a door writes them (`envelope.place()`)."""
    from portfusion.desk.doors import envelope
    envelope.place({table: [envelope.rendered(table, r) for r in rows]})


def holds(*found, what: str = "the rows this test is built from"):
    """Skip unless every one of `found` is there: a test built from the loaded book's own rows
    cannot run on a book that has none of them yet, and says so rather than failing. As a
    module's `pytestmark`, or a decorator."""
    return pytest.mark.skipif(any(f is None for f in found),
                              reason=f"the book holds none of {what} yet")


#: THE CALLS THAT WRITE OR REMOVE A FILE, by name: the one list every guard asking "does this
#: module write?" reads (`write_call`).
WRITE_CALLS = {"write_text", "write_bytes", "move", "copy2", "copyfile", "copytree", "unlink",
               "rmtree", "rmdir", "touch", "append_lines", "rewrite", "to_csv", "dump"}

#: The envelope's writers that find the store's tables themselves (`desk/doors/envelope.py`).
ENVELOPE_WRITES = {"place", "journal"}

#: The flags with which `os.open` creates, writes or empties a file.
_OS_WRITE_FLAGS = ("O_WRONLY", "O_RDWR", "O_CREAT", "O_APPEND", "O_TRUNC")


def write_call(node) -> str | None:
    """The name of the write a call makes, or None. Beyond `WRITE_CALLS`: `ENVELOPE_WRITES` called
    on the envelope, `os.replace(a, b)`, a path's `.replace(target)` and `.rename(target)` — one
    argument; a string's replace takes two, a frame's rename takes keywords — `os.rename`,
    `os.remove`, `shutil.copy`, `os.open` with a flag that writes, and `open()` with a mode that
    writes, appends or creates. A csv writer's rows are not counted: they go to whatever it was
    handed, and a file is caught where it was opened."""
    import ast
    if not isinstance(node, ast.Call):
        return None
    name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
    if name in WRITE_CALLS:
        return name
    on = (node.func.value.id if isinstance(node.func, ast.Attribute)
          and isinstance(node.func.value, ast.Name) else None)
    if on == "envelope" and name in ENVELOPE_WRITES:
        return name
    one_target = len(node.args) == 1 and not node.keywords
    if name in ("replace", "rename") and isinstance(node.func, ast.Attribute) and (
            on == "os" or one_target):
        return name
    if (on, name) in (("os", "remove"), ("shutil", "copy")):
        return name
    if (on, name) == ("os", "open"):
        return name if any(f in ast.unparse(a) for a in node.args[1:2] for f in _OS_WRITE_FLAGS) \
            else None
    if name in ("open", "fdopen"):
        modes = [a for a in node.args[1:2]] + [k.value for k in node.keywords if k.arg == "mode"]
        if name == "open" and isinstance(node.func, ast.Attribute) and on != "os":  # path.open("w")
            modes = [a for a in node.args[:1]] + modes
        if any(isinstance(m, ast.Constant) and isinstance(m.value, str)
               and set(m.value) & set("wax+") for m in modes):
            return name
    return None


#: What names the store in a call's target: a table's path, the store's folder, a `store`, or
#: the envelope, whose writes are the store's.
STORE_NAMES = re.compile(r"\b(TABLES|STORE|store_dir|store|envelope)\b")

#: The calls that read a file, for a census of what a module OPENS (`file_calls(reads=True)`).
READ_CALLS = {"open", "fdopen", "read_text", "read_bytes", "read_csv"}


def _names(text: str) -> set[str]:
    """The names an expression reads: `table.path` is `table`, `table.path` and any `.path`."""
    out = set()
    for token in re.findall(r"[A-Za-z_][\w.]*", text):
        parts = token.split(".")
        out |= {".".join(parts[:i]) for i in range(1, len(parts) + 1)}
        out |= {f".{p}" for p in parts[1:]}
    return out


def file_calls(path, reads: bool = False) -> list[tuple[int, str, str]]:
    """(line, call, target) for each call in a source file that writes a file (`write_call`), or,
    with `reads`, opens or reads one: THE ONE SCAN every guard of what a module writes asks.

    The target is the receiver and the arguments, then what each name in it is
    assigned, in the same function or at the module, and what a property it reads returns, so
    `path.write_text(…)` after `path = schema.TABLES[t].path` reads as a store write. Within the
    function, because a name as common as `path` means another thing in the next one."""
    import ast
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)

    def bindings(scope, outer):
        """`outer`'s names and what `scope` assigns, not reaching into a function inside it."""
        bound = {k: list(v) for k, v in outer.items()}
        stack = list(ast.iter_child_nodes(scope))
        while stack:
            node = stack.pop()
            if isinstance(node, functions):
                if any(getattr(d, "id", None) == "property" for d in node.decorator_list):
                    bound.setdefault(f".{node.name}", []).extend(
                        ast.unparse(r.value) for r in ast.walk(node)
                        if isinstance(r, ast.Return) and r.value)
                continue
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    for name in t.elts if isinstance(t, (ast.Tuple, ast.List)) else [t]:
                        bound.setdefault(ast.unparse(name), []).append(ast.unparse(node.value))
            elif isinstance(node, (ast.For, ast.comprehension)):
                bound.setdefault(ast.unparse(node.target), []).append(ast.unparse(node.iter))
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                bound.setdefault(ast.unparse(node.optional_vars), []).append(
                    ast.unparse(node.context_expr))
            stack.extend(ast.iter_child_nodes(node))
        return bound

    calls = []

    def visit(node, bound):
        for child in ast.iter_child_nodes(node):
            inner = bindings(child, bound) if isinstance(child, functions) else bound
            if isinstance(child, ast.Call):
                calls.append((child, inner))
            visit(child, inner)

    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    visit(tree, bindings(tree, {}))
    out = []
    for node, bound in calls:
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        call = write_call(node) or (name if reads and name in READ_CALLS else None)
        if call is None:
            continue
        receiver = [node.func.value] if isinstance(node.func, ast.Attribute) else []
        target = " ".join(ast.unparse(a) for a in [*receiver, *node.args])
        for _ in range(2):                          # a name assigned from another, once removed
            for word in _names(target) & bound.keys():
                target += " " + " ".join(bound[word])
        out.append((node.lineno, call, target))
    return sorted(out)


def free_id(table: str, step: int = 0) -> str:
    """The loaded book's next free id for `table` ("buys", "sales"), or the one `step` after it.
    A typed id — T-999, E-099 — is one a book reaching it already holds."""
    from portfusion.record import rules
    prefix, number = rules.next_free_ids()[table].split("-")
    return f"{prefix}-{int(number) + step:0{len(number)}d}"


@functools.lru_cache(maxsize=None)
def _rows_in(table: str) -> int:
    from portfusion.record import schema
    if table in schema.TABLES:
        return len(schema.load(table))
    path = schema.STORE / f"{table}.csv"                  # a history: read as a file
    return max(len(path.read_text(encoding="utf-8").splitlines()) - 1, 0) if path.is_file() else 0


def needs(*tables: str):
    """Skip unless the loaded book holds rows in every one of `tables` — the tables, or the
    histories by file name, a test is built from. A new book holds none and every such test says
    which it is waiting for; a book that holds them runs it, and one that lists its skips
    (`SKIPS_FILE`) fails the run if it does not."""
    empty = [t for t in tables if not _rows_in(t)]
    return pytest.mark.skipif(bool(empty), reason=f"the book holds no {', '.join(empty)} rows yet")


def require(*found, what: str = "the rows this module is built from") -> None:
    """`holds()` for a whole module whose own top level is built from the rows, called before it
    reaches them."""
    if any(f is None for f in found):
        pytest.skip(f"the book holds none of {what} yet", allow_module_level=True)

# ---------------------------------------------------------------------------------------
# THE ENVIRONMENT GUARD — the tests REFUSE to run unless the app they import is THIS checkout's,
# with every package pyproject.toml names installed beside it.
#
# THIS ENFORCES WHERE THE BUILD ONLY REPORTS (`about.interpreter()`), and the asymmetry
# is the whole design. A guard that has not verified its own environment is worth nothing, so
# strictness belongs here. The build must never refuse: if the venv breaks the day before a
# quarter close, a report built on identical system packages beats no report at all.
#
# WHAT IT ASKS: not whether a folder named .venv is running, but the two things that folder
# stands for.
#
#   * `portfusion` comes from THIS checkout's src/. An installed checkout is found through the
#     venv, so a worktree run on another checkout's venv imports THAT checkout's code and passes
#     on it. Each checkout has a venv of its own (docs/environment.md).
#   * Every package the project names is installed. A dead venv falls back to the system
#     interpreter, where the book's tests pass on its packages, installed system-wide too, while
#     the desk's cannot be collected.
#
# IT FIRES IN `pytest_configure`, BEFORE COLLECTION, because that is the only moment early
# enough: a collection error in a desk test interrupts the run before any test executes, so a
# test could not have caught this one however it was written.
def environment_faults() -> list[str]:
    """What is wrong with the environment the suite would run in; empty when nothing is."""
    import importlib.metadata
    import importlib.util
    import re
    faults = []
    spec = importlib.util.find_spec(SRC.name)
    found = Path(spec.origin).resolve().parent if spec and spec.origin else None
    if found != SRC:
        faults.append(f"`{SRC.name}` is imported from {found or 'nowhere'}, not {SRC}")
    # The app's own requirements always; the development extra only where there is a checkout
    # to develop in. An app not installed has none to read, and that is the fault.
    try:
        requires = importlib.metadata.requires(SRC.name) or []
    except importlib.metadata.PackageNotFoundError:
        return [*faults, f"{SRC.name} is not installed"]
    for wanted in requires:
        if "extra ==" in wanted and ROOT is None:
            continue
        name = re.match(r"[A-Za-z0-9._-]+", wanted).group(0)
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            faults.append(f"{name} is not installed")
    return faults


def book_line() -> str:
    from portfusion import about
    return about.book_line()


#: THE LOADED BOOK'S OWN FOLDERS, which no test may move: its record, its filed documents and
#: its workbench. A test writes to a copy (`store_copy`, `item`, `workbench`, `inbox`).
BOOK_FOLDERS = ("store", "_archive", "_inbox")


def book_state() -> dict:
    """Every file and folder under the loaded book's own folders: its size and when it changed.
    A folder's own time is in it, so a file made and removed again still shows."""
    from portfusion.record import schema
    state = {}
    for name in BOOK_FOLDERS:
        top = schema.BOOK / name
        for p in [top, *sorted(top.rglob("*"))] if top.exists() else []:
            if "__pycache__" not in p.parts:
                st = p.stat()
                state[str(p.relative_to(schema.BOOK))] = (st.st_size if p.is_file() else None,
                                                         st.st_mtime_ns)
    return state


def pytest_sessionstart(session):
    session.config.stash[_BOOK_STATE] = book_state()
    _SKIPS_SEEN.clear()
    _RAN.clear()


def _test_id(nodeid: str) -> str:
    """A test's id from the suite's own folder, the same in a checkout and an installed copy."""
    return nodeid.split("portfusion/tests/", 1)[-1]


def _the_books(report) -> bool:
    """Is this skip about the BOOK? One about the copy — the guards that read a checkout skip on an
    installed copy, by design (`NO_CHECKOUT`) — is the machine's, and one about the demo's own
    documents (`DEMO_ONLY`) is the demo's: no book lists either."""
    reason = report.longrepr[-1] if isinstance(report.longrepr, tuple) else str(report.longrepr)
    return not any(why in str(reason) for why in (NO_CHECKOUT, DEMO_ONLY))


def pytest_runtest_logreport(report):
    if report.skipped and report.when in ("setup", "call") and _the_books(report):
        _SKIPS_SEEN.add(_test_id(report.nodeid))
    elif report.when == "call" and not report.skipped:
        _RAN.add(_test_id(report.nodeid))


def pytest_collectreport(report):
    if report.skipped and _the_books(report):
        _SKIPS_SEEN.add(_test_id(report.nodeid))


#: Filled by the two hooks above; a plugin's report hooks are handed no session to keep it on.
_SKIPS_SEEN: set[str] = set()
_RAN: set[str] = set()


def skips_off(seen, ran, listed) -> tuple[list[str], list[str]]:
    """(the skips `listed` lacks, the listed tests that ran): each fails the run."""
    return sorted(seen - listed), sorted(ran & listed)


def expected_skips() -> set[str] | None:
    """The skips the loaded book lists (`SKIPS_FILE`), or None for a book that lists none."""
    from portfusion.record import schema
    path = schema.BOOK / "checks" / SKIPS_FILE
    if not path.is_file():
        return None
    return {ln.split("#")[0].strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.split("#")[0].strip()}


def pytest_sessionfinish(session, exitstatus):
    """THE RUN FAILS IF IT MOVED THE LOADED BOOK. A test that reached the real `_inbox/.bench/`
    or `_archive/` would otherwise pass. Checked once, across the whole run, so a test that
    cleans up after itself is still seen to have touched it. A write the owner made through the
    desk during the run shows here too; run the suite again."""
    # A SKIP THE BOOK DOES NOT LIST fails the run: a test it has the rows for was not run. So
    # does a listed test that ran.
    listed = expected_skips()
    if listed is not None:
        off, ran = skips_off(_SKIPS_SEEN, _RAN, listed)
        if off or ran:
            session.config.stash[_SKIPS_OFF], session.config.stash[_SKIPS_RAN] = off, ran
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
    was = session.config.stash.get(_BOOK_STATE, None)
    if was is None:
        return
    now = book_state()
    moved = sorted(k for k in was.keys() | now.keys() if was.get(k) != now.get(k))
    if moved:
        session.config.stash[_BOOK_MOVED] = moved
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter):
    """Which book the run loaded, beside the count it is read for: a run on the demo passes as
    quietly as one on this book. A summary line rather than a header, because `-q` drops those."""
    off = terminalreporter.config.stash.get(_SKIPS_OFF, None)
    if off:
        terminalreporter.write_line(
            f"FAILED: {len(off)} test(s) skipped that this book's checks/{SKIPS_FILE} does not "
            f"list — it has their rows, so they must run: " + ", ".join(off[:10])
            + (" …" if len(off) > 10 else ""), red=True)
    ran = terminalreporter.config.stash.get(_SKIPS_RAN, None)
    if ran:
        terminalreporter.write_line(
            f"FAILED: {len(ran)} test(s) ran that this book's checks/{SKIPS_FILE} lists as "
            f"skipping — delete their lines: " + ", ".join(ran[:10])
            + (" …" if len(ran) > 10 else ""), red=True)
    moved = terminalreporter.config.stash.get(_BOOK_MOVED, None)
    if moved:
        terminalreporter.write_line(
            f"FAILED: the run moved the loaded book's own files ({len(moved)}): "
            + ", ".join(moved[:10]) + (" …" if len(moved) > 10 else ""), red=True)
    terminalreporter.write_line(f"book: {book_line()}")


def pytest_configure(config):
    """Fires before collection, which is the only moment early enough — a collection error in
    a desk test module interrupts the run before any test executes, so a TEST could never have
    caught this."""
    configure(config)
    unsigned_git()
    faults = environment_faults()
    if faults:
        pytest.exit(
            "\n\nTHE TESTS ARE NOT RUNNING ON THIS CHECKOUT'S OWN INSTALL\n\n"
            + "".join(f"  {f}\n" for f in faults)
            + f"\n  running   {sys.prefix}\n\n"
            f"Activate this checkout's venv, or build one (docs/environment.md):\n\n"
            f"  python3 -m venv .venv && .venv/bin/python3 -m pip install -e '.[dev]' -c requirements.lock\n"
            f"  source .venv/bin/activate && python3 -m pytest -q\n",
            returncode=1)
    try:
        checks = book_checks(config)
    except SystemExit as no_book:               # the record refuses a folder holding no book
        pytest.exit(f"{no_book} In a checkout: export PORTFUSION_BOOK=demo (CONTRIBUTING.md)",
                    returncode=1)
    if checks is not None:
        config.args.append(str(checks))


#: What every git command the suite starts is told, whatever the machine's own config says. A
#: machine that signs commits by default would fail every test that commits in a scratch
#: repository, with no key to sign with.
UNSIGNED = (("commit.gpgsign", "false"), ("tag.gpgsign", "false"))


def unsigned_git() -> None:
    """Add `UNSIGNED` to the git config the environment passes every child (GIT_CONFIG_COUNT), so
    the machine's own files are read and left alone. Side effects: sets environment variables."""
    n = int(os.environ.get("GIT_CONFIG_COUNT", "0") or 0)
    for key, value in UNSIGNED:
        os.environ[f"GIT_CONFIG_KEY_{n}"], os.environ[f"GIT_CONFIG_VALUE_{n}"] = key, value
        n += 1
    os.environ["GIT_CONFIG_COUNT"] = str(n)


def configure(config) -> None:
    """HOW EVERY RUN IS SET UP, in a checkout or an installed copy alike, so the two cannot differ.

    THE DEFAULT RUN IS THE GUARD: green unless the code broke. The audit tests are deselected, not
    skipped, and run on their own command (`docs/testing.md`).

        portfusion check            the guard, on the loaded book (`python3 -m pytest` in a checkout)
        portfusion record           the audit: what the record needs today
        python3 -m pytest -m audit  the same set, without the framing

    Strict markers make a misspelt mark an error, so an audit test cannot quietly join the guard.
    A run that names its own `-m` or `--tb` keeps it.
    """
    config.addinivalue_line("markers", "audit: asks whether the RECORD is in good order, not whether the CODE is")
    config.option.strict_markers = True
    if not config.option.markexpr:
        config.option.markexpr = "not audit"
    if config.option.tbstyle == "auto":
        config.option.tbstyle = "short"


def book_checks(config) -> Path | None:
    """THE LOADED BOOK'S OWN CHECKS, when a default run should take them in.

    THE SUITE RUNS ON ANY BOOK. `PORTFUSION_BOOK` points the record at a book's folder
    (`record/schema.py`), and the one suite in `tests/` is the guard for whichever is loaded:
    there is no second suite to drift. A check of ONE book's own facts — a typed census, a
    migrated text, a reading whose incident lives in one row — is a fact another book can neither
    satisfy nor refute, so it lives in that book's `checks/` folder and leaves nothing behind in
    the code. A run that names no paths collects it when, and only when, its book is the one
    loaded; a run that names paths takes exactly those.

      PORTFUSION_BOOK=. python3 -m pytest        the guard, and this book's checks
      PORTFUSION_BOOK=demo python3 -m pytest     the same guard on the demo, and the demo's, if any
    """
    from portfusion.record import schema
    checks = schema.BOOK / "checks"
    if config.args_source == pytest.Config.ArgsSource.TESTPATHS and checks.is_dir():
        return checks
    return None


@pytest.fixture
def store_copy(tmp_path, monkeypatch):
    """The LOADED BOOK, copied — store and archive together — with the record reading from
    the copy for this test.

    EVERY test that writes to the store uses this and never the record — a test that
    appended a row to `store/buys.csv` would be a fabricated trade in the book.

    IT MOVES THE WHOLE BOOK, not the store alone. The DOORS read and write the archive beside
    the store — `commit.py` files a committed item in `_archive/bench/` and a document in
    `_archive/statements/` — so a copy without it would file into the real book's folders.
    Copying from `schema.STORE`, never `ROOT / "store"`, is also what lets the suite check
    whatever book is loaded.

    A TEST'S BOOK IS ITS `tmp_path`, here and in the bench fixtures below: each rebinds
    `schema.BOOK` there, so they agree whichever a test takes. Restored however the test ends.
    """
    import shutil
    from portfusion.record import rules, schema
    target = tmp_path / "store"
    target.mkdir()
    for csv_file in schema.STORE.glob("*.csv"):
        shutil.copy2(csv_file, target / csv_file.name)
    for name in ("bench", "statements"):
        src = schema.BOOK / "_archive" / name
        dst = tmp_path / "_archive" / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.mkdir(parents=True)
    monkeypatch.setattr(schema, "BOOK", tmp_path)
    with rules.store_at(target):
        yield target


# THE DESK TESTS' BENCH AND WORKBENCH, with the other fixtures. Each reads its constants from
# desk_support.py, which is importable whenever a test in tests/desk/ is running, and no other
# test asks for these.

@pytest.fixture
def item(inbox):
    """A bench item in a temp directory, so the suite never touches the real workbench — of the
    document kind `GOOD_EVIDENCE` describes, with that document on a workbench of its own. The
    bench owes a kind before it approves, and a contract note is retrieved by its FILE; the
    commit door files it from this workbench, never the real `_inbox/`."""
    from desk_support import GOOD_CLASS, GOOD_DOCUMENT
    from portfusion.desk.intake import bench as _bench
    (inbox / GOOD_DOCUMENT).write_bytes(b"%PDF-1.4")
    made = _bench.new_item(title="test item")
    made["evidence_class"] = GOOD_CLASS
    made["document"] = {"name": GOOD_DOCUMENT}
    return made


@pytest.fixture
def workbench(inbox, tmp_path_factory, monkeypatch):
    """A workbench and a destination of our own, for the exit route.

    Never the real `_inbox/` and never the real `~/Downloads` — this module is the one under
    desk/ that can REMOVE a file, so a test of it that reached either would be the accident it
    exists to prevent. NOR THE REAL BENCH OR ARCHIVE: a withdrawal closes the bench item working
    its document and copies it to `_archive/bench/`, so a name the loaded book's bench also held
    would have closed that book's item. The destination is outside the book, where a withdrawal
    may go.
    """
    from portfusion.desk.intake import withdraw
    out = tmp_path_factory.mktemp("out")
    monkeypatch.setattr(withdraw, "DEFAULT_DESTINATION", out)
    return inbox, out


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    """A workbench of our own, in a book of our own. NEVER the real _inbox/ — a test that landed
    a document in the real one would fail test_inbox.py's "the workbench is clear" on the next
    run, and the failure would look like an unfinished intake rather than a stray test."""
    from portfusion.record import schema
    monkeypatch.setattr(schema, "BOOK", tmp_path)
    target = schema.inbox()
    target.mkdir(exist_ok=True)
    return target


@pytest.fixture(scope="session")
def D():
    from portfusion.record import rules
    return rules


@pytest.fixture(scope="session")
def repo_root():
    if ROOT is None:
        pytest.skip(NO_CHECKOUT)
    return ROOT


@pytest.fixture(scope="session")
def project_files():
    """The project's own files with the given suffixes — what GIT calls the project, not
    whatever happens to sit under the root. Every guard that reads the whole tree reads this.

    NOT `repo_root.rglob()`, which walks into the desktop app's worktrees under
    `.claude/worktrees/`, each a full checkout of the repo.

    Tracked files AND untracked ones git does not ignore, so a module written but not yet
    added is guarded before the commit rather than after it. Git does not descend into a
    nested checkout: it lists the directory, never its files, ignored or not.
    """
    if ROOT is None:
        pytest.skip(NO_CHECKOUT)
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\0")
    files = sorted({ROOT / p for p in listed if p and (ROOT / p).is_file()})

    def _with(*suffixes):
        return [p for p in files if p.suffix in suffixes]

    return _with


#: THE PACKAGE every module of the app is imported under, for the guards that read an import past it.
PACKAGE = SRC.name


@pytest.fixture(scope="session")
def imports_of():
    """Modules a source file actually IMPORTS, by parsing it rather than grepping it.

    A grep matches a module's name in prose, even in a docstring saying the file does not use
    it. A dependency claim has to be checked against the syntax tree, not the prose.

    AN IMPORT IS READ PAST THE PACKAGE: `from portfusion.desk import app` is `desk`. Under one
    package every import's first name is the package's, so a guard asking whether the book
    imports `desk` would hold for ever without this.

    `dotted=True` adds each module by its dotted name as well (`history.accounts`,
    `record.schema`), for a guard that names a module rather than a folder. Without it, such a
    guard asks a set of first names for a dotted one, and passes whatever is imported.
    """
    import ast

    def _name(module):
        head, _, rest = module.partition(".")
        return rest if head == PACKAGE and rest else module

    def _imports(path, dotted=False):
        tree = ast.parse(Path(path).read_text())
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [_name(a.name) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module == PACKAGE:
                # `from portfusion import engine` IMPORTS `engine`. Read as the package alone, it
                # names nothing a guard could refuse.
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = _name(node.module)
                names = [module] + ([f"{module}.{a.name}" for a in node.names] if dotted else [])
            else:
                continue
            for name in names:
                found.add(name.split(".")[0])
                if dotted:
                    found.add(name)
        return found

    return _imports


@pytest.fixture(scope="session")
def build_sources():
    """Every source file the build is made of: the quarterly report, the one generated document.

    DERIVED by globbing, never listed. The build is a package; a guard naming its entry point alone
    would go on passing while the code it guards sat beside it — passing for the WRONG REASON,
    which is the exact failure this suite exists to prevent. A new module joins these guards by
    existing, the same way a new table joins the staleness guard by existing.
    """
    return sorted((SRC / "report").rglob("*.py"))


@pytest.fixture(scope="session")
def book():
    """The engine, built once. Shared by the ties and the invariant layer."""
    from portfusion.engine import Book
    return Book()


@pytest.fixture
def book_names(D):
    """WHO AND WHAT THIS BOOK NAMES, read from its record and never typed, for the guards that
    hold a file or a page to naming none of it. `words`: each holder's names, matched as words
    in any case. `joined`: a holder's names run together, as a login or a home folder spells
    them. `exact`: the accounts' numbers and feed labels, and every sale's realisation id.
    `numbers`: the accounts' numbers alone, for a scan that finds one inside a longer number.
    A book with other holders is held to its own."""
    reg = [dict(zip(D.schema.TABLES["accounts"].header, r)) for r in D.register]
    titles = {"Mr", "Mrs", "Ms", "Miss", "Mx", "Dr"}
    return {
        "words": {w for r in reg for w in str(r["holder"]).split() if w not in titles},
        "joined": {"".join(w for w in str(r["holder"]).split() if w not in titles) for r in reg},
        "exact": ({str(r["number"]) for r in reg} | {str(r["feed_key"]) for r in reg if r["feed_key"]}
                  | {e.realisation_id for e in D.sales}),
        "numbers": {str(r["number"]) for r in reg if str(r["number"]).strip()},
    }
