"""init/ — A NEW BOOK'S FOLDER, written once: empty, or a practice book — a copy of the demo,
marked as one, to try the desk's doors on without touching the demo the app ships.

AN EMPTY BOOK IS THE DEMO'S STORE WITH EVERY ROW TAKEN OUT. Each table's header comes from the
demo the app ships (`record/schema.py:DEMO`), so a table or a history joins a new book by joining
the demo, and there is no second list of headers to drift. The settings are the one table that
is not left empty: every key in `schema.SETTING_KEYS` gets a row, the three dates the record
cannot load without set from the year the record begins, and the rest blank, which each feature
that needs one reads as "not set up" and says so.

It writes into a folder that does not exist or is empty, and nowhere else: a book is never
written over. It reads no book, so it runs from any folder (`portfusion/__main__.py`).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import shutil
import subprocess
import sys

#: The folders a book keeps beside its store, each made empty.
FOLDERS = ("_archive/statements", "_archive/bench", "_inbox")

#: WHAT A BOOK'S OWN REPOSITORY MUST NEVER HOLD: the files that reach its brokers and readers, and
#: the documents still being worked on. Written as the book's .gitignore.
GITIGNORE = """\
# The files that reach the brokers and the readers: never in git.
credentials.*
.ig_session.json
.tv_session.json
.desk_passkeys.json
.desk_readers.json
.desk_signins.jsonl
.desk_proxy_secret.json
# A document resting in the inbox is unfinished work.
_inbox/*
# The book's own venv, which runs the portfusion `requirements.txt` names, and what Python and
# the Mac leave beside the files: none of it is the record.
.venv/
__pycache__/
.pytest_cache/
.DS_Store
"""

#: THE BOOK'S SECRET GATE, as `.githooks/pre-commit`. The gate is the app's
#: (`portfusion/hooks/pre_commit.py`); this finds the portfusion the book runs and asks it, and
#: where none can be found the commit is REFUSED: a gate that cannot run has checked nothing.
HOOK = """\
#!/bin/sh
# THIS BOOK'S SECRET GATE, written by `portfusion init`: a commit that would put a credential into
# git is refused. The gate is PortFusion's own; this asks the portfusion the book runs.
top=$(git rev-parse --show-toplevel)
main=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
for py in "$top/.venv/bin/python3" "$main/.venv/bin/python3" python3; do
    if "$py" -c "import portfusion.hooks.pre_commit" 2>/dev/null; then
        exec "$py" -m portfusion.hooks.pre_commit "$@"
    fi
done
echo "pre-commit: REFUSED. The secret gate could not run: no portfusion in the book's .venv or on PATH." >&2
echo "  Install it (pip install -r requirements.txt) or activate the venv that has it, and commit again." >&2
exit 1
"""


def pin() -> str:
    """The requirement line for the portfusion running now, as `pip install -r` takes it: the
    commit it was installed from, the folder or file, or else the release by its number."""
    from importlib import metadata
    dist = metadata.distribution("portfusion")
    found = json.loads(dist.read_text("direct_url.json") or "{}")
    if "vcs_info" in found:
        return f"portfusion @ git+{found['url']}@{found['vcs_info']['commit_id']}"
    if "url" in found:
        return f"portfusion @ {found['url']}"
    return f"portfusion=={dist.version}"


#: The book's `requirements.txt`: which portfusion it runs, moved on purpose and never by itself.
PIN = """\
# THE PORTFUSION THIS BOOK RUNS, written by `portfusion init`. Its venv installs it with
#   python3 -m venv .venv && .venv/bin/python3 -m pip install -r requirements.txt
# A new release is taken by changing this line, then installing it and running the guard.
{pin}
"""


def start_history(folder: pathlib.Path) -> str:
    """Make `folder` a git repository and commit the new book as its first commit, so the record
    has a history from its first row: a correction is a new row, and git is what shows what was
    believed and when. Returns what was done, in a line; never raises, because the book is
    written whether or not git is there.

    Side effects: runs `git init` and `git commit` in `folder`, and points its hooks at the
    book's `.githooks/`, so the secret gate (`HOOK`) is on from that first commit."""
    # THE GATE GUARDS THE FIRST COMMIT TOO, run by the Python running this: the book has no venv
    # yet, and this one has portfusion in it.
    env = {**os.environ, "PATH": os.pathsep.join([str(pathlib.Path(sys.executable).parent),
                                                  os.environ.get("PATH", "")])}

    def git(*args):
        return subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, env=env)
    try:
        if git("init", "-q", "-b", "main").returncode:
            return "git would not start a repository here: the book has no history yet"
    except FileNotFoundError:
        return "git is not installed: the book has no history yet (`git init` in it, later)"
    git("config", "core.hooksPath", ".githooks")
    git("add", "-A")
    if git("commit", "-q", "-m", "A new book, written by portfusion init").returncode:
        return ("a git repository, with the book staged but not committed: git has no name and "
                "email to commit under (`git config --global user.name` and `user.email`)")
    return "a git repository, the new book its first commit"


class Refused(Exception):
    """The folder already holds something, so no book is written there."""


def settings(begins: int) -> list[tuple[str, str]]:
    """Every settings key, in `SETTING_KEYS` order: the record begins on 1 January of `begins`,
    a reason is owed from then, and the first report is that year's first quarter end."""
    from portfusion.record import schema           # here, not at the top: see `create()`
    dated = {"record_begins": f"{begins}-01-01", "reasoning_owed_from": f"{begins}-01-01",
             "first_report": f"{begins}-03-31"}
    return [(key, dated.get(key, "")) for key in schema.SETTING_KEYS]


#: The setting a practice book carries, so every run on it says what it is (`about.book_line`).
PRACTICE = ("practice", "yes")


def create(folder, practice: bool = False, begins: int | None = None) -> pathlib.Path:
    """Write a new book at `folder`: with `practice`, a copy of the demo whose settings say it is
    one; else an empty book whose record begins in `begins` (this year when not given). Returns
    the folder, absolute; `start_history()` makes it a repository.

    Side effects: makes `folder` and writes the book's files inside it, nothing outside it.
    Raises Refused when `folder` exists and is not empty.

    The record is imported here and not with the module, because importing it loads a book, and
    `portfusion init` runs where there is none yet (`init/__main__.py`)."""
    from portfusion.record import schema
    folder = pathlib.Path(folder).expanduser().resolve()
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise Refused(f"{folder} already holds something: a book is written into an empty folder")
    if practice:
        shutil.copytree(schema.DEMO, folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("_inbox"))
        with (folder / "store" / "settings.csv").open("a", encoding="utf-8", newline="") as fh:
            fh.write(",".join(PRACTICE) + "\n")
    else:
        store = folder / "store"
        store.mkdir(parents=True)
        for table in sorted((schema.DEMO / "store").glob("*.csv")):
            with table.open(encoding="utf-8", newline="") as fh:
                header = fh.readline()
            (store / table.name).write_text(header, encoding="utf-8", newline="")
        rows = settings(begins or _dt.date.today().year)
        (store / "settings.csv").write_text(
            "key,value\n" + "".join(f"{k},{v}\n" for k, v in rows), encoding="utf-8", newline="")
        # THE JOURNAL OPENS WITH THE BOOK: one opening count per table, of what is written now,
        # all at one instant. Without them the journal has nothing to reconcile against and its
        # hand-edit check never runs (`Book.journal_opened()`), on every book this made.
        at = schema.record_instant()
        with (store / "journal.csv").open("a", encoding="utf-8", newline="") as fh:
            for table in sorted(t for t in schema.TABLES if t != "journal"):
                count = len((store / f"{table}.csv").read_text(encoding="utf-8").splitlines()) - 1
                fh.write(f"{at},baseline,open,{table},{count},,"
                         f"rows on file when the journal opened\n")
    for name in FOLDERS:
        (folder / name).mkdir(parents=True, exist_ok=True)
    (folder / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    hook = folder / ".githooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(HOOK, encoding="utf-8")
    hook.chmod(0o755)
    (folder / "requirements.txt").write_text(PIN.format(pin=pin()), encoding="utf-8")
    return folder
