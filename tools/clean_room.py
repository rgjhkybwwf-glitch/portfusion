"""
THE CLEAN-ROOM TEST: does the app stand on its own?

The tracked files are copied to an empty folder and asked three ways:

  THE COPY, installed in a venv of its own and its suite run on the demo: nothing the code needs
  lives outside what git tracks, every guard that reads a checkout's files included.
  A NEW BOOK, made by `portfusion init` and holding no row, with the copy's suite run on it: every
  test either runs or says which rows it needs, so the suite is one any book can run.
  THE WHEEL, built from the copy as a release is, installed in a second venv, and `portfusion
  check` run from an empty folder: the app a user installs carries everything it needs (the demo,
  the desk's screens, the typeface, the suite) and reaches back into no checkout. The guards that
  read a checkout skip there, as they do for a user, which is why the copy is asked as well.

Green means all three pass. The workflow, `.github/workflows/guard.yml`, runs this same file, so
the Mac and GitHub ask the question one way, and it is the workflow's one run of the suite.

    python3 tools/clean_room.py             run it; exit 0 only when all three pass
    python3 tools/clean_room.py --keep      the same, and leave the copy, the wheel and the venvs
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from portfusion.log import log

HERE = pathlib.Path(__file__).resolve().parent.parent     # the checkout; this file is in tools/


def copy_tracked(into: pathlib.Path) -> int:
    """Copy every tracked file into `into`, and make it a repository of its own: the guards read
    what git calls the project. Returns how many files went."""
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=HERE, capture_output=True, text=True,
                            check=True).stdout.split("\0")
    files = [p for p in listed if p]
    for path in files:
        (into / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / path, into / path)
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=clean-room", "-c", "user.email=clean-room@example.invalid",
                  "commit", "-qm", "clean room"]):
        subprocess.run(["git", *args], cwd=into, check=True)
    return len(files)


def build(into: pathlib.Path) -> pathlib.Path:
    """The copy built into a wheel, as a release is: returns the wheel."""
    subprocess.run([sys.executable, "-m", "pip", "wheel", "-q", "--no-deps", "-w",
                    str(into / "dist"), str(into)], check=True)
    wheels = list((into / "dist").glob("portfusion-*.whl"))
    assert len(wheels) == 1, f"the build made {wheels}"
    return wheels[0]


def install(what: str, constraints: pathlib.Path, where: pathlib.Path) -> pathlib.Path:
    """A venv of its own in `where`, with `what` installed in it — the copy, editable, or the
    wheel: returns its interpreter."""
    subprocess.run([sys.executable, "-m", "venv", str(where / ".venv")], check=True)
    python = where / ".venv" / "bin" / "python3"
    subprocess.run([str(python), "-m", "pip", "install", "-q", *what.split(),
                    "-c", str(constraints)], cwd=where, check=True)
    return python


def run_suite(where: pathlib.Path, python: pathlib.Path, *command: str,
              book: str = "demo") -> tuple[int, str]:
    """The suite on `book` (the demo unless named), from `where`. Returns pytest's exit code and
    what it said, which lists each failure and each skip with its reason: a skip on one machine
    and not another is where a test leans on the machine."""
    env = {**os.environ, "PORTFUSION_BOOK": book}
    env.pop("VIRTUAL_ENV", None)
    env.pop("PYTHONPATH", None)
    done = subprocess.run([str(python), "-m", *command, "-q", "-rfEs"],
                          cwd=where, env=env, capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def verdict(code: int, output: str) -> list[str]:
    """What is wrong with a run; empty when nothing is. pytest exits 0 when all passed and 1 when
    some failed; anything else means the run itself broke."""
    if code not in (0, 1):
        return [f"pytest exited {code}: the run did not complete"]
    failed = set(re.findall(r"^(?:FAILED|ERROR) (\S+)", output, re.M))
    # EXIT 1 NAMES A FAILURE, or the run failed in a way no test reported — a crash after the
    # tests, or the harness failing a run that moved the loaded book. Read as "no failure", it
    # passed (the review of 21 Oct 2026).
    if code == 1 and not failed:
        return ["pytest exited 1 and named no failed test: the run itself failed"]
    return [f"FAILED: {t}" for t in sorted(failed)]


def main(argv: list[str]) -> int:
    top = pathlib.Path(tempfile.mkdtemp(prefix="clean-room-"))
    into, user = top / "copy", top / "user"
    into.mkdir()
    user.mkdir()
    try:
        log.info(f"clean room: {copy_tracked(into)} tracked files copied to {into}")
        lock = into / "requirements.lock"
        copy = install("-e .[dev]", lock, into)
        code, output = run_suite(into, copy, "pytest", "-p", "no:cacheprovider")
        log.info(output.rstrip())
        problems = [f"the copy: {p}" for p in verdict(code, output)]
        # A NEW BOOK, the first a new user has: every table and no row. A test built from rows it
        # does not hold skips; one that fails leans on a book like the demo.
        empty = top / "a-new-book"
        subprocess.run([str(copy), "-m", "portfusion", "init", str(empty)], cwd=top,
                       check=True, capture_output=True)
        log.info(f"clean room: the suite on a new, empty book ({empty})")
        code, output = run_suite(into, copy, "pytest", "-p", "no:cacheprovider", book=str(empty))
        log.info(output.rstrip().splitlines()[-1] if output.strip() else "")
        problems += [f"a new book: {p}" for p in verdict(code, output)]
        wheel = build(into)
        log.info(f"clean room: built {wheel.name}; `portfusion check` from {user}")
        code, output = run_suite(user, install(f"{wheel}[dev]", lock, user), "portfusion", "check")
        log.info(output.rstrip())
        problems += [f"the wheel: {p}" for p in verdict(code, output)]
        for line in problems:
            log.error(line)
        if not problems:
            log.info("clean room: green — the app stands on its own")
        return 1 if problems else 0
    finally:
        if "--keep" in argv:
            log.info(f"the copy, the wheel and the venvs are kept at {top}")
        else:
            shutil.rmtree(top, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
