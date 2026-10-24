"""
THE CODE ITSELF — what nobody reads goes, and what a comment says is so.

The other layers ask whether a figure is right. These ask whether the code that makes the figures
carries anything that is not doing work: a method only a test calls, an import nothing uses, a
comment naming a function that is gone. Each is a thing a reader trusts and should not have to
check.

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
    change near it. As the registry refuses a figure nothing renders (`test_figures.py`), this
    refuses an engine method nothing reads.

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
    """ONE STATEMENT OF THE ENGINE'S PERIOD, `_window()`. A second copy of the filter is how one
    drifts. `activity()` and `round_trips()` keep their own start, the desk's From date, and their
    docstrings say why."""
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
    nothing."""
    wrong = [f"{path.relative_to(ROOT)}:{fn.lineno}" for path in project_files(".py")
             for fn in ast.walk(_tree(path))
             if isinstance(fn, ast.FunctionDef) and fn.name == "main" and fn.returns is not None
             and ast.unparse(fn.returns) == "None"
             and any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(fn))]
    assert not wrong, f"annotated None, returning an exit code: {wrong}"


@needs_checkout
def test_the_linter_finds_nothing():
    """THE LINTER, run by the guard as well as by the workflow, so a finding is met before the
    commit rather than after the push. `pyproject.toml` says which checks, and why the formatter
    is not among them."""
    import subprocess
    import sys
    done = subprocess.run([sys.executable, "-m", "ruff", "check", "--no-cache", "--quiet"],
                          cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, f"`python3 -m ruff check` found:\n{done.stdout}{done.stderr}"


def test_every_function_a_comment_names_exists(project_files):
    """A COMMENT NAMING A FUNCTION THAT IS GONE sends its reader looking for it. Every call of
    `Book.`, `book.`, `rules.` or `schema.` a comment or a docstring names is one the code has;
    `book.` may be the module or an engine, as the code's own comments use it."""
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
    """A DEFENCE AGAINST A NAME THE RECORD ALWAYS DEFINES hides the day it stops:
    `getattr(D, name, {})` reads a vanished name as empty, and nothing fails. A name the record
    defines is read as one."""
    record = {"D", "self.D", "rules", "_rules", "R", "_D"}
    found = [f"{path.relative_to(ROOT)}:{n.lineno} {ast.unparse(n)}"
             for path in project_files(".py") if not _is_test(path)
             for n in ast.walk(_tree(path))
             if isinstance(n, ast.Call) and ast.unparse(n.func) == "getattr" and len(n.args) == 3
             and ast.unparse(n.args[0]) in record]
    assert not found, "the record read with a fallback:\n  " + "\n  ".join(found)


def test_a_module_is_imported_one_way(project_files):
    """A module imported whole is not also imported by name in the same file."""
    twice = []
    for path in project_files(".py"):
        froms = [n for n in ast.walk(_tree(path)) if isinstance(n, ast.ImportFrom) and n.module]
        starred = {n.module for n in froms if any(a.name == "*" for a in n.names)}
        twice += [f"{path.relative_to(ROOT)}:{n.lineno} {n.module}" for n in froms
                  if n.module in starred and not any(a.name == "*" for a in n.names)]
    assert not twice, "imported by star and again by name:\n  " + "\n  ".join(twice)


#: Lines of comment and docstring prose, in the project's Python, JS and CSS, that carry a dated
#: year: a format example, a day a rule names, or an event the demo invents, never the day a change
#: was made. A RATCHET: cutting can never fail it; telling a change's story in a comment can.
DATED_PROSE_LINES = 30

#: What prose never names, in Python or JS: a code review, an issue number or a pull request. The
#: commit log holds them. CSS is not asked, since a colour there is a hash and three digits.
_HISTORY = re.compile(r"\bthe review of\b|(?<![\w/&])#\d{1,3}(?!\w)|\bPR \d+\b", re.I)
_DATED = re.compile(r"\b\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* 20\d\d\b")
#: The migration moves describe the shapes they move from, and leave with them.
_MOVES = ("record/migrations.py", "migrate/", "tests/test_migrations.py")


def _prose(path):
    """(line, text) for each line of a file's comments and docstrings: a string that is data, a
    fixture or a template, is not prose. JS and CSS comments are read by pattern, not parsed."""
    import io
    import tokenize
    src = path.read_text(encoding="utf-8")
    if path.suffix != ".py":
        return [(src.count("\n", 0, m.start()) + 1 + i, text)
                for m in re.finditer(r"/\*.*?\*/|(?<![:\"'\\/])//[^\n]*", src, re.S)
                for i, text in enumerate(m.group(0).splitlines())]
    out = [(tok.start[0], tok.string) for tok in tokenize.generate_tokens(io.StringIO(src).readline)
           if tok.type == tokenize.COMMENT]
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node, clean=False)
        if doc:
            out += [(node.body[0].lineno + i, text) for i, text in enumerate(doc.splitlines())]
    return out


def test_the_engines_comments_type_no_figure():
    """A comment in `engine.py` types no figure of the book: a second copy that ages where nothing
    checks it. Name the figure, never its value."""
    typed = re.compile(r"£[1-9][\d,]*(\.\d+)?|\b\d{1,3}(,\d{3})+\.\d{2}\b")
    found = [n for n, text in _prose(SRC / "engine.py") if typed.search(text)]
    assert not found, f"engine.py types a figure into a comment at lines {found}"


def test_comments_state_the_rule_not_its_history(project_files):
    """THE COMMIT LOG HOLDS THE HISTORY. A comment or docstring states the rule in force: it names
    no review, issue or pull request, and carries no more dated lines than the ratchet allows."""
    dated, told = [], []
    for path in project_files(".py", ".js", ".css"):
        rel = path.relative_to(ROOT).as_posix()
        for n, text in _prose(path):
            dated += [f"{rel}:{n}"] if _DATED.search(text) else []
            told += [f"{rel}:{n} {text.strip()[:80]}"] if (
                path.suffix != ".css" and _HISTORY.search(text)
                and not any(m in rel for m in _MOVES)) else []
    assert not told, "prose names a review, an issue or a pull request:\n  " + "\n  ".join(told)
    assert len(dated) <= DATED_PROSE_LINES, (
        f"{len(dated)} lines of prose carry a dated year, above the {DATED_PROSE_LINES} on file: "
        f"{dated}. Put the story in the commit message and keep the rule.")


#: The topics of `Book`'s sub-sections. Each heads one sub-section, or none.
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
    """EVERY TOPIC IN ONE PLACE, so a reader finds a figure's code where its topic is. The
    numbered sections run in order and each holds code; every one of `Book`'s sub-sections has a
    heading, and no topic heads two."""
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
    """EVERY LINE A COMMAND SAYS GOES THROUGH `portfusion.log`, so `portfusion -q` quiets all of
    it and a line's level says which stream it reaches. A print would answer to neither. A print
    written inside a string, as code a subprocess or another repository runs, is not a call here,
    and is not counted."""
    found = [f"{p.relative_to(ROOT)}:{n.lineno}" for p in project_files(".py") if not _is_test(p)
             for n in ast.walk(_tree(p))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]
    assert not found, f"these print; use `from portfusion.log import log`: {found}"
