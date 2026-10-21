"""
THE CODE ITSELF — what nobody reads goes, and what a comment says is so.

The other layers ask whether a figure is right. These ask whether the code that makes the figures
carries anything that is not doing work: a method only a test calls, an import nothing uses, a
comment naming a function that is gone. Each was found by the step 5 review (Beta 0.1, 15 Oct
2026), and each is a thing a reader trusts and should not have to check.

They read the source, never run the book, so they hold on any book.
"""
import ast
import pathlib
import re

from harness import ROOT, SRC, TESTS, needs_checkout


def _tree(path) -> ast.Module:
    return ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))


def _is_test(path) -> bool:
    return pathlib.Path(path).is_relative_to(TESTS)


def _book_class() -> ast.ClassDef:
    return next(n for n in _tree(SRC / "engine.py").body if isinstance(n, ast.ClassDef) and n.name == "Book")


# =====================================================================================
# THE ENGINE CARRIES NOTHING ONLY A TEST READS
# =====================================================================================

def _audited(fn: ast.FunctionDef) -> bool:
    return any(ast.unparse(d) == "pytest.mark.audit" for d in fn.decorator_list)


def test_every_public_engine_method_has_a_reader(project_files):
    """A METHOD ONLY A TEST CALLS IS A FIGURE NOBODY IS SHOWN, kept true at the cost of every
    change near it. `income()`, `by_issuer()` and `capital_flows()` were, the last the workbook's
    trading-flow block, until step 5 removed them. As the registry refuses a figure nothing renders
    (`test_figures.py`), this refuses an engine method nothing reads.

    A READER is any code outside the tests, the engine included, and the audit: a test marked
    `audit` is what `portfusion record` runs, so a method only it reads is still read.
    """
    public = {n.name for n in _book_class().body
              if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}
    read = set()
    for path in project_files(".py"):
        tree = _tree(path)
        scopes = ([f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and _audited(f)]
                  if _is_test(path) else [tree])
        read |= {n.attr for s in scopes for n in ast.walk(s) if isinstance(n, ast.Attribute)}
    unread = sorted(public - read)
    assert not unread, (
        f"Book.{', Book.'.join(unread)} — read by nothing but the tests. Remove it with the tests "
        f"that exist only for it, or give it the reader it was written for.")


# =====================================================================================
# A RULE THE ENGINE STATES ONCE
# =====================================================================================

def test_the_engine_states_its_window_once():
    """ONE STATEMENT OF THE ENGINE'S PERIOD, `_window()`. The filter was written out in six
    methods until step 5, and a seventh copy is how one drifts. `activity()` and `round_trips()`
    keep their own start, the desk's From date, and their docstrings say why."""
    tree = _tree(SRC / "engine.py")
    after_start = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)
                   and isinstance(n.ops[0], ast.Gt)
                   and ast.unparse(n.comparators[0]) == "pd.Timestamp(start)"]
    assert len(after_start) == 1, (
        f"engine.py writes the window's opening {len(after_start)} times, at lines "
        f"{[n.lineno for n in after_start]}. Bound the frame with `_window()`.")
    window = next(n for n in ast.walk(_book_class()) if isinstance(n, ast.FunctionDef)
                  and n.name == "_window")
    assert window.lineno <= after_start[0].lineno <= window.end_lineno


# =====================================================================================
# WHAT THE CODE SAYS OF ITSELF IS SO
# =====================================================================================

def test_a_command_says_it_returns_its_exit_code(project_files):
    """A `main()` ANNOTATED `None` THAT RETURNS A CODE tells its reader the exit status is
    nothing. The three `history/` commands were, until step 5, each handing `sys.exit()` 0, 1 or 2."""
    wrong = [f"{path.relative_to(ROOT)}:{fn.lineno}" for path in project_files(".py")
             for fn in ast.walk(_tree(path))
             if isinstance(fn, ast.FunctionDef) and fn.name == "main" and fn.returns is not None
             and ast.unparse(fn.returns) == "None"
             and any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(fn))]
    assert not wrong, f"annotated None, returning an exit code: {wrong}"


@needs_checkout
def test_the_linter_finds_nothing():
    """THE LINTER, run by the guard as well as by the workflow, so a session meets a finding before
    it commits rather than after it pushes. `pyproject.toml` says which checks, and why the
    formatter is not among them. Its unused-import check replaced this file's own, which counted a
    name as used wherever any line of the file spelt it and so missed twenty."""
    import subprocess
    import sys
    done = subprocess.run([sys.executable, "-m", "ruff", "check", "--no-cache", "--quiet"],
                          cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, f"`python3 -m ruff check` found:\n{done.stdout}{done.stderr}"


def test_every_function_a_comment_names_exists(project_files):
    """A COMMENT NAMING A FUNCTION THAT IS GONE sends its reader looking for it. Four did until
    step 5: the desk's engine called the store's seam `rules.load_store`, which is book's; two
    comments named `Book.market`, an inner function of `value_legs`; and one named
    `Book.movements`, which is `capital_movements`. Every call of `Book.`, `book.`, `rules.` or
    `schema.` a comment or a docstring names is one the code has; `book.` may be the module or an
    engine, as the code's own comments use it."""
    import io
    import tokenize
    from portfusion import engine
    from portfusion.record import rules, schema
    owners = {"Book": (engine.Book,), "book": (engine, engine.Book), "rules": (rules,), "schema": (schema,)}
    named = re.compile(r"(?<![\w.])(Book|book|rules|schema)\.([A-Za-z_]\w*)\(")
    gone = []
    for path in project_files(".py"):
        src = path.read_text(encoding="utf-8")
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if not (tok.type == tokenize.COMMENT or (tok.type == tokenize.STRING
                                                     and tok.string.lstrip("rbuf")[:3] in ('"""', "'''"))):
                continue
            for m in named.finditer(tok.string):
                if not any(hasattr(o, m.group(2)) for o in owners[m.group(1)]):
                    line = tok.start[0] + tok.string[:m.start()].count("\n")
                    gone.append(f"{path.relative_to(ROOT)}:{line} {m.group(1)}.{m.group(2)}()")
    assert not gone, "named in a comment, and not in the code:\n  " + "\n  ".join(gone)


def test_the_record_is_read_without_a_fallback(project_files):
    """A DEFENCE AGAINST A NAME THE RECORD ALWAYS DEFINES hides the day it stops: three
    `getattr(D, name, {})` in the engine, until step 5, would have read `STATEMENT_PRICED` and
    `RATE_CARRIED` as empty had either gone, offering the carried marks to a refresh and ageing
    them with the rest, and nothing would have failed. A name the record defines is read as one."""
    record = {"D", "self.D", "rules", "_rules", "R", "_D"}
    found = [f"{path.relative_to(ROOT)}:{n.lineno} {ast.unparse(n)}"
             for path in project_files(".py") if not _is_test(path)
             for n in ast.walk(_tree(path))
             if isinstance(n, ast.Call) and ast.unparse(n.func) == "getattr" and len(n.args) == 3
             and ast.unparse(n.args[0]) in record]
    assert not found, "the record read with a fallback:\n  " + "\n  ".join(found)


def test_a_module_is_imported_one_way(project_files):
    """`record/rules.py` imported each of its companions twice, by star to re-export them and by
    name beside it, a partial second list of what the star already brings, until step 5. A module
    imported whole is not also imported by name in the same file."""
    twice = []
    for path in project_files(".py"):
        froms = [n for n in ast.walk(_tree(path)) if isinstance(n, ast.ImportFrom) and n.module]
        starred = {n.module for n in froms if any(a.name == "*" for a in n.names)}
        twice += [f"{path.relative_to(ROOT)}:{n.lineno} {n.module}" for n in froms
                  if n.module in starred and not any(a.name == "*" for a in n.names)]
    assert not twice, "imported by star and again by name:\n  " + "\n  ".join(twice)


#: Lines of `engine.py`'s comments and docstrings that carry a date. A RATCHET, set at step 5's
#: count: each names the day the record begins or when a rule in force was decided. Cutting can
#: never fail it; telling a change's story in a comment can.
BOOK_DATED_COMMENT_LINES = 6


def test_the_engines_comments_state_the_rule_not_its_history():
    """THE COMMIT LOG HOLDS THE HISTORY. `engine.py`'s
    comments told the story of thirteen changes until step 5, three of them with a figure of the
    book typed in, a second copy that ages where nothing checks it. A comment states the rule in
    force, and types no figure."""
    import io
    import tokenize
    typed = re.compile(r"£[1-9][\d,]*(\.\d+)?|\b\d{1,3}(,\d{3})+\.\d{2}\b")
    dated = re.compile(r"\b\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* 20\d\d\b")
    src = (SRC / "engine.py").read_text(encoding="utf-8")
    lines = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT or (tok.type == tokenize.STRING
                                            and tok.string.lstrip("rbuf")[:3] in ('"""', "'''")):
            lines += [(tok.start[0] + i, text) for i, text in enumerate(tok.string.splitlines())]
    assert not [n for n, text in lines if typed.search(text)], (
        f"engine.py types a figure into a comment at lines "
        f"{[n for n, text in lines if typed.search(text)]}: name the figure, never its value")
    when = [n for n, text in lines if dated.search(text)]
    assert len(when) <= BOOK_DATED_COMMENT_LINES, (
        f"engine.py's comments carry {len(when)} dated lines, above the {BOOK_DATED_COMMENT_LINES} "
        f"on file, at {when}. Put the story in the commit message and keep the rule.")


#: The topics the step 5 review found split across `Book`'s sub-sections: income across three, the
#: quarters, the past date and the headline across two each. Each heads one sub-section, or none.
BOOK_TOPICS = ("headline", "mark", "holding", "allocation", "round trip", "activity", "account",
               "income", "reconcil", "quarter", "return", "past date")


def _book_layout(src: str):
    """engine.py's numbered sections, every boxed heading at the top level, and Book's sub-sections."""
    lines = src.splitlines()
    numbered = [int(m.group(1)) for line in lines for m in [re.match(r"^# (\d) · ", line)] if m]
    bar = re.compile(r"^# ={20,}$")
    boxed = [i for i in range(2, len(lines)) if bar.match(lines[i - 2]) and bar.match(lines[i])
             and lines[i - 1].startswith("# ")]
    subsections = [m.group(1) for line in lines for m in [re.match(r"^    # ---- (.+?) -*$", line)] if m]
    return numbered, boxed, subsections


def test_book_py_keeps_each_topic_in_one_place():
    """EVERY TOPIC IN ONE PLACE, so a reader finds a figure's code where its topic is. Until step 5
    section 2's heading had nothing under it, the ledger's functions following two sections later,
    and inside `Book` income sat in three sub-sections and the quarters, the past date and the
    headline in two each. The numbered sections run in order and each holds code; every one of
    `Book`'s sub-sections has a heading, and no topic heads two."""
    src = (SRC / "engine.py").read_text(encoding="utf-8")
    numbered, boxed, subsections = _book_layout(src)
    assert numbered == list(range(1, len(numbered) + 1)), numbered
    code = [n.lineno for n in _tree(SRC / "engine.py").body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Assign))]
    ends = boxed[1:] + [len(src.splitlines()) + 1]
    empty = [src.splitlines()[i - 1] for i, end in zip(boxed, ends) if not any(i < c < end for c in code)]
    assert not empty, f"a heading in engine.py has no code under it: {empty}"
    twice = {t: [s for s in subsections if t in s.lower()] for t in BOOK_TOPICS}
    twice = {t: s for t, s in twice.items() if len(s) > 1}
    assert not twice, f"a topic heads more than one of Book's sub-sections: {twice}"
    assert not re.search(r"^    # -{60,}$", src, re.M), "a sub-section is headed in the boxed style"


# =====================================================================================
# THE APP SPEAKS THROUGH ITS LOGGER
# =====================================================================================

def test_nothing_outside_the_tests_prints(project_files):
    """EVERY LINE A COMMAND SAYS GOES THROUGH `portfusion.log` (since the app was packaged, 18 Oct 2026), so
    `portfusion -q` quiets all of it and a line's level says which stream it reaches. A print
    would answer to neither. A print written inside a string, as code a subprocess or another
    repository runs, is not a call here, and is not counted."""
    found = [f"{p.relative_to(ROOT)}:{n.lineno}" for p in project_files(".py") if not _is_test(p)
             for n in ast.walk(_tree(p))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]
    assert not found, f"these print; use `from portfusion.log import log`: {found}"
