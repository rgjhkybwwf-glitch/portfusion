"""check/ — THE GUARD: the suite that ships inside the app, run as pytest runs it in a checkout.

TWO QUESTIONS, TWO BOOKS. Whether the CODE is right is asked on the demo the app carries,
which holds a row of every kind the suite is built from, so every test proves something; a
user's book, new or half-filled, would leave most of them nothing to stand on. Whether THE
LOADED BOOK OPENS — its figures, findings, every desk page and the report's gate — is asked of
that book, with the book's own `checks/` beside it. `check()` asks both; the second is skipped
when the loaded book is the demo, which the first has just asked.

`run()` is the suite on the loaded book alone: a checkout's `python3 -m pytest`, and the audit's
test half (`portfusion record`), which is a question about the book and so never the demo's.
One runner, so none of them can be configured apart: the suite's `pytest.ini` names the harness,
and the harness sets everything else (`tests/harness.py:configure`).
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

#: THE SUITE, as the package carries it: files beside the code, installed or checked out.
TESTS = pathlib.Path(__file__).resolve().parent.parent / "tests"
#: What is asked of a user's own book: that it opens.
OPENS = TESTS / "test_init.py::test_the_loaded_book_opens"


def _pytest(paths: list[str], args, book: str) -> int:
    env = {**os.environ, "PORTFUSION_BOOK": book, "PYTHONPATH": os.pathsep.join(
        filter(None, [str(TESTS), os.environ.get("PYTHONPATH")]))}
    return subprocess.run([sys.executable, "-m", "pytest", "-c", str(TESTS / "pytest.ini"),
                           "-p", "no:cacheprovider", *paths, *args], env=env).returncode


def _checks(book: pathlib.Path) -> list[str]:
    return [str(book / "checks")] if (book / "checks").is_dir() else []


def run(args: list[str] = ()) -> int:
    """The suite and the loaded book's own checks, on the loaded book, with `args` passed through
    to pytest. Returns pytest's exit code. The book is the one `record/schema.py` resolved, which
    it has written back to the environment absolute, so the child reads the same book from any
    folder.

    Side effects: runs pytest in a child process, which prints its own report."""
    from portfusion.record import schema
    return _pytest([str(TESTS), *_checks(schema.BOOK)], args, str(schema.BOOK))


def check(args: list[str] = ()) -> int:
    """`portfusion check`: the code on the demo, then the loaded book opening, with its checks.
    Returns the first non-zero exit code, or 0.

    Side effects: runs pytest in one or two child processes, each printing its own report."""
    from portfusion.record import schema
    code = _pytest([str(TESTS)], args, "demo")
    if schema.BOOK == schema.DEMO:
        return code
    book = _pytest([str(OPENS), *_checks(schema.BOOK)], args, str(schema.BOOK))
    # A FILTER THAT SELECTS NOTHING OF THE BOOK'S RUN is the filter's doing: `-k` naming a test of
    # the suite deselects the book's one test, and pytest's 5 (no test selected) failed the check.
    if book == 5 and args:
        book = 0
    return code or book


def migrated(book: str) -> int:
    """After `portfusion migrate --write`: the book opens and the record's audit passes, its own
    `checks/` left out — the book's code, which a migration lists and does not move. As `check()`,
    an exit code and pytest's own reports."""
    quiet = ["-q", "--no-header", "--tb=line"]
    return _pytest([str(OPENS)], quiet, book) or _pytest([str(TESTS)], ["-m", "audit", *quiet], book)
