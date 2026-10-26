"""A NEW BOOK, as `portfusion init` writes it: empty, or a copy of the demo, and never over
anything already there."""
import csv
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from portfusion.init import Refused, create, settings
from portfusion.record import schema
from harness import SRC


def test_an_empty_book_holds_every_table_with_its_header_and_no_rows(tmp_path):
    """Every table the schema registers and every history, headed as the demo heads it, with no
    row but the settings: a table missing would stop the record loading, a row would be a fact
    nobody entered."""
    book = create(tmp_path / "book", begins=2027)
    demo = sorted(p.name for p in (schema.DEMO / "store").glob("*.csv"))
    made = sorted(p.name for p in (book / "store").glob("*.csv"))
    assert made == demo
    assert {f"{t}.csv" for t in schema.TABLES} <= set(made)
    for name in made:
        with (book / "store" / name).open(encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
        with (schema.DEMO / "store" / name).open(encoding="utf-8", newline="") as fh:
            assert rows[0] == next(csv.reader(fh)), name
        # THE SETTINGS, and the journal's opening count of every table: the record's own
        # account of what was on file when the book began.
        assert name in ("settings.csv", "journal.csv") or len(rows) == 1, \
            f"{name} was written with rows"
    for folder in ("_archive/statements", "_archive/bench", "_inbox"):
        assert (book / folder).is_dir(), folder
    assert "credentials.*" in (book / ".gitignore").read_text()


def test_an_empty_books_settings_name_every_key_and_date_its_record(tmp_path):
    """Every key once, in the schema's order; the record begins on a year's 1 January or on the day
    given, its first report is due when that day's quarter ends, and nothing that names a place
    outside the book is filled in."""
    rows = dict(settings(2027))
    assert list(rows) == list(schema.SETTING_KEYS)
    assert rows["record_begins"] == "2027-01-01"
    assert rows["first_report"] == "2027-03-31"
    for begins, first in (("2027-05-15", "2027-06-30"), ("2027-10-01", "2027-12-31")):
        dated = dict(settings(begins))
        assert (dated["record_begins"], dated["reasoning_owed_from"], dated["first_report"]) == (
            begins, begins, first), dated
    assert not any(rows[k] for k in ("hosted_origin", "passkey_domain", "deploy_repo", "research_repo"))


def test_a_practice_book_is_the_demo_and_says_so(tmp_path):
    """Every file the demo ships, byte for byte, beside the folders a book works in — but for
    one row, which says it is a practice book so that every run on it says so too, and that
    row's journal entry."""
    from portfusion.init import PRACTICE, PRACTICE_JOURNAL
    book = create(tmp_path / "book", practice=True)
    shipped = sorted(p.relative_to(schema.DEMO) for p in schema.DEMO.rglob("*")
                     if p.is_file() and "_inbox" not in p.parts)
    settings, journal = pathlib.Path("store/settings.csv"), pathlib.Path("store/journal.csv")
    for rel in shipped:
        demo, made = (schema.DEMO / rel).read_bytes(), (book / rel).read_bytes()
        if rel == settings:
            demo += (",".join(PRACTICE) + "\n").encode()
        if rel == journal:
            made, entry = made[:len(demo)], made[len(demo):].decode()
            assert entry.split(",", 1)[1] == PRACTICE_JOURNAL + "\n", entry
        assert made == demo, rel
    assert (book / "_inbox").is_dir()
    run = subprocess.run([sys.executable, "-c", "from portfusion import about; "
                          "print(about.book_line())"], capture_output=True, text=True,
                         env={**os.environ, schema.ENV: str(book)})
    assert "a practice book" in run.stdout, run.stdout + run.stderr


def test_a_practice_books_journal_accounts_for_every_row(tmp_path):
    """A row no route accounts for is a hand edit the audit reports, and a new book has none."""
    book = create(tmp_path / "book", practice=True)
    run = subprocess.run([sys.executable, "-c", "from portfusion import engine; "
                          "print(engine.Book().journal_unaccounted().empty)"],
                         capture_output=True, text=True, env={**os.environ, schema.ENV: str(book)})
    assert run.stdout.strip().endswith("True"), run.stdout + run.stderr


def test_a_book_is_never_written_over(tmp_path):
    """A folder that holds anything is refused, and left as it was."""
    (tmp_path / "book").mkdir()
    (tmp_path / "book" / "notes.txt").write_text("mine")
    with pytest.raises(Refused):
        create(tmp_path / "book")
    assert [p.name for p in (tmp_path / "book").iterdir()] == ["notes.txt"]


#: What a new user opens first, asked of a book `create()` has just written: the engine's
#: figures and findings, every page the desk serves and the hosted desk's renaming of them, and
#: the report's gate on its first quarter.
_OPENS = """
from fastapi.testclient import TestClient
from portfusion.desk import app, panels
from portfusion.engine import Book
from portfusion.record import rules
from portfusion.report.gate import completeness
b = Book()
import sys
if "empty" in sys.argv:                     # a new book's every figure is nought, or blank (NaN)
    assert all(v == 0 or v != v for v in b.headline().values())
b.findings()
completeness(rules.SETTINGS["first_report"])
desk = TestClient(app.app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)
paths = ["/", "/api/state", "/api/holdings", "/api/round-trips", "/api/trades",
         *[f"/api/panel/{m.NAME}" for m in panels.all_panels()]]
failed = [(p, r.status_code) for p in paths if (r := desk.get(p)).status_code != 200]
assert not failed, failed
from portfusion.desk import naming, remote
for name in remote.REMOTE_PANELS:          # what the hosted door renames before it answers
    naming.of(b).apply(desk.get(f"/api/panel/{name}").json())
"""


def _opens(book, *said) -> subprocess.CompletedProcess:
    """`_OPENS` on `book`, in its own process, because the record loads the book named when it
    is first imported."""
    return subprocess.run([sys.executable, "-c", _OPENS, *said], capture_output=True, text=True,
                          env={**os.environ, schema.ENV: str(book)})


def test_the_loaded_book_opens():
    """WHAT `portfusion check` ASKS OF A USER'S OWN BOOK, beside the code on the demo
    (`check/__init__.py`): that its figures, findings, desk pages and gate all answer."""
    run = _opens(schema.BOOK)
    assert run.returncode == 0, run.stderr[-2000:]


def test_an_empty_book_opens(tmp_path):
    """A NEW BOOK IS THE FIRST THING A NEW USER RUNS, so it must open: every figure nought or
    blank, every desk page answering, and the gate saying what its first quarter needs. Its tables
    have no rows, and a frame built from rows alone has no columns."""
    run = _opens(create(tmp_path / "book"), "empty")
    assert run.returncode == 0, run.stderr[-2000:]


#: What a book that began on 18 May is asked, in its own process: its year and its first quarter
#: measure from its opening, the quarter says so on the desk's list and the report, and the gate
#: asks for that opening rather than a 31 March the record never had.
_MID_YEAR = """
import math
from portfusion.engine import Book
from portfusion.report.gate import completeness
from portfusion.report.page import render
b = Book()
assert b.ytd_opens() == b.baseline_asof == "2026-05-17", b.ytd_opens()
assert not math.isnan(b.headline()["YTD return (MWR)"]), "the year has nothing to open from"
first = b.quarter_returns().iloc[0]
assert (first["quarter"], first["opens"]) == ("Q2 2026, from 17 May", "2026-05-17"), first
year = b.year_to_quarter("2026-09-30")
assert (year["quarter"], year["opens"]) == ("2026 to 30 Sep, from 17 May", "2026-05-17"), year
assert completeness("2026-06-30") == [], completeness("2026-06-30")
page = render("2026-06-30")
assert "<h1>Q2 2026, from 17 May</h1>" in page and "2026 to 30 Jun, from 17 May" in page
from portfusion.desk import engine as desk
assert desk.reports()["quarters"][-1]["quarter"] == "Q2 2026, from 17 May", desk.reports()
# A RESTATEMENT OF THAT QUARTER JOURNALS IT BY THE SAME NAME. The engine's strike is moved £100,
# so there is something to restate.
from portfusion.desk.doors import freeze
from portfusion.record import schema
real = Book.freeze_rows
def moved(self, as_of, accounts=None, restated=None):
    rows = real(self, as_of, accounts=accounts, restated=restated)
    for r in rows["quarter_nav"]:
        r["amount"] = round(r["amount"] + 100.0, 2)
    return rows
Book.freeze_rows = moved
account = next(r[1] for r in schema.load("quarter-nav") if str(r[0]) == "2026-06-30")
freeze.restate({"2026-06-30": [account]}, "a test moved it")
said = [r[-1] for r in schema.load("journal") if r[3] == "quarter-results"][-2:]
assert said[0].startswith("Q2 2026, from 17 May: ") and said[1].startswith("Q3 2026: "), said
"""


def _begun_mid_quarter(tmp_path):
    """A practice book whose record begins on 18 May 2026: its opening is the demo's frozen
    31 March, dated the day before, and nothing is frozen, deposited or earned before it."""
    import csv
    book = create(tmp_path / "book", practice=True)
    store = book / "store"

    def edit(table, keep=lambda r: True, change=lambda r: r):
        path = store / f"{table}.csv"
        with path.open(newline="", encoding="utf-8") as fh:
            head, *rows = list(csv.reader(fh))
        with path.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh, lineterminator="\n").writerows([head, *(change(r) for r in rows if keep(r))])
    begins = {"record_begins": "2026-05-18", "reasoning_owed_from": "2026-05-18",
              "first_report": "2026-06-30"}
    edit("settings", change=lambda r: [r[0], begins.get(r[0], r[1])])
    for table in ("quarter-nav", "quarter-snapshots"):
        edit(table, keep=lambda r: r[0] >= "2026-03-31",
             change=lambda r: ["2026-05-17", *r[1:]] if r[0] == "2026-03-31" else r)
    edit("quarter-results", keep=lambda r: r[0] > "2026-03-31")
    for table in ("capital-movements", "income"):
        edit(table, keep=lambda r: r[0] >= "2026-05-18")
    return book


def test_a_book_begun_mid_quarter_is_measured_from_its_opening(tmp_path):
    """A BOOK MAY BEGIN ON ANY DAY. Its year and first quarter measure from its opening, never a
    31 December or quarter end the record never had."""
    run = subprocess.run([sys.executable, "-c", _MID_YEAR], capture_output=True, text=True,
                         env={**os.environ, schema.ENV: str(_begun_mid_quarter(tmp_path))})
    assert run.returncode == 0, run.stderr[-2000:]


def test_init_runs_where_there_is_no_book(tmp_path, capsys):
    """A new user's first command is typed where no book is yet, and every other command refuses
    there: `init` alone must not, by either route to it."""
    env = {k: v for k, v in os.environ.items() if k != schema.ENV}
    for n, route in enumerate((["-m", "portfusion", "init"], ["-m", "portfusion.init"])):
        run = subprocess.run([sys.executable, *route, f"book{n}", "--no-venv", "--no-git"],
                             cwd=tmp_path, env=env, capture_output=True, text=True)
        assert run.returncode == 0 and (tmp_path / f"book{n}" / "store").is_dir(), run.stderr
    # `--begins` TAKES A DAY as well as a year, and the book's record begins on it.
    from portfusion.init import __main__ as command
    assert command.main([str(tmp_path / "dated"), "--no-git", "--no-venv",
                         "--begins", "2026-05-18"]) == 0
    assert "record_begins,2026-05-18" in (tmp_path / "dated/store/settings.csv").read_text()
    with pytest.raises(SystemExit) as refused:
        command.main([str(tmp_path / "undated"), "--no-git", "--no-venv", "--begins", "15 May"])
    assert refused.value.code == 2 and "neither a year nor a day" in capsys.readouterr().err
    assert not (tmp_path / "undated").exists()


def test_a_new_books_history_starts_with_it(tmp_path):
    """A correction is a new row, and git is what shows what was believed and when, so a book
    starts as a repository, the book its first commit — and the .gitignore holds from that
    commit, so no credentials file can enter it. Without git's name and email, it is staged and
    the line says why: the book is written either way."""
    from portfusion.init import start_history
    book = create(tmp_path / "book")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test"}
    with pytest.MonkeyPatch.context() as m:
        for k, v in env.items():
            m.setenv(k, v)
        said = start_history(book)
    assert "first commit" in said, said
    tracked = subprocess.run(["git", "ls-files"], cwd=book, capture_output=True,
                             text=True).stdout.split()
    assert ".gitignore" in tracked and "store/settings.csv" in tracked
    (book / "credentials.json").write_text("{}")
    ignored = subprocess.run(["git", "status", "--porcelain"], cwd=book, capture_output=True,
                             text=True).stdout
    assert "credentials.json" not in ignored


_GIT_NAMED = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
              "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test"}


def _git_env() -> dict:
    """Git under the throwaway name, with this run's portfusion on PATH for the book's hooks."""
    return {**os.environ, **_GIT_NAMED, "PATH": os.pathsep.join(
        [str(pathlib.Path(sys.executable).parent), "/usr/bin", "/bin"])}


@pytest.fixture(scope="module")
def _books_started(tmp_path_factory):
    """Each kind of started book, made once for the module: its first commit runs the gate,
    which is the cost."""
    from portfusion.init import start_history
    made = {}

    def make(**kind):
        key = tuple(sorted(kind.items()))
        if key not in made:
            book = create(tmp_path_factory.mktemp("started") / "book", **kind)
            with pytest.MonkeyPatch.context() as m:
                for k, v in _GIT_NAMED.items():
                    m.setenv(k, v)
                assert "first commit" in start_history(book)
            made[key] = book
        return made[key]
    return make


@pytest.fixture
def started(_books_started, tmp_path):
    """A new book, made as `create()` is told, with its history begun under a throwaway name: a
    copy of the module's, for each test."""
    def copy(**kind):
        book = tmp_path / "book"
        shutil.copytree(_books_started(**kind), book, symlinks=True)
        return book
    return copy


def _commit(book, path_dirs):
    """Commit a note holding a planted key, with only `path_dirs` on PATH."""
    key = "0f1e2d3c4b5a" * 3 + "abcd"                    # assembled, as test_hooks.py does
    (book / "credentials.json").write_text(f'{{"A_BROKER": {{"api_key": "{key}"}}}}')
    (book / "notes.md").write_text(f"the key was {key} for a moment")
    env = {**os.environ, **_GIT_NAMED, "PATH": os.pathsep.join(path_dirs)}
    subprocess.run(["git", "add", "notes.md"], cwd=book, env=env, check=True)
    return subprocess.run(["git", "commit", "-qm", "a note"], cwd=book, env=env,
                          capture_output=True, text=True)


def test_a_new_book_never_tracks_its_venv_or_what_python_leaves(started, tmp_path):
    """The book's venv lives in the book's folder, where a `git add -A` would commit it: the
    .gitignore `init` writes names it, and what Python leaves."""
    book = started()
    for leftover in (".venv/bin/python3", "store/__pycache__/x.pyc", ".pytest_cache/v",
                     ".DS_Store"):
        (book / leftover).parent.mkdir(parents=True, exist_ok=True)
        (book / leftover).write_text("")
    untracked = subprocess.run(["git", "status", "--porcelain"], cwd=book, capture_output=True,
                               text=True).stdout
    assert untracked == "", untracked


@pytest.mark.parametrize("where", ["a new book", "this checkout"])
def test_no_secret_file_is_tracked_by_a_new_book_or_this_checkout(where, tmp_path, request):
    """A KEY KEPT BESIDE THE BOOK stays out of git: every file `secret_scan.SECRET_FILES` names is
    on the .gitignore `init` writes, and on this checkout's, and the gate refuses whatever it
    ignores."""
    from portfusion import secret_scan
    folder = (request.getfixturevalue("started")() if where == "a new book"
              else request.getfixturevalue("repo_root"))
    names = [pattern.replace("*", "x") for pattern in secret_scan.SECRET_FILES]
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=folder,
                             input="\n".join(names), capture_output=True, text=True).stdout
    assert sorted(ignored.split()) == sorted(names), f"{where} tracks a secret file"


def test_a_new_books_secret_gate_refuses_a_credential(started, tmp_path):
    """A NEW BOOK HOLDS ITS OWNER'S CREDENTIALS TOO, so it has a gate, on its files and its
    messages: the app's, on from the first commit, run by the portfusion the book has installed."""
    book = started()
    assert "pre-commit" in subprocess.run(["git", "ls-files", ".githooks"], cwd=book,
                                          capture_output=True, text=True).stdout
    result = _commit(book, [str(pathlib.Path(sys.executable).parent), "/usr/bin", "/bin"])
    assert result.returncode != 0 and "REFUSED" in result.stderr, result.stderr
    assert "A_BROKER/api_key" in result.stderr
    subprocess.run(["git", "restore", "--staged", "notes.md"], cwd=book, check=True)
    said = subprocess.run(["git", "commit", "--allow-empty", "-qm", (book / "notes.md").read_text()],
                          cwd=book, env=_git_env(), capture_output=True, text=True)
    assert said.returncode != 0 and "commit-msg: REFUSED" in said.stderr, said.stderr


def test_a_new_book_refuses_a_push_that_takes_anything_from_main(started, tmp_path):
    """A HOST MAY PROTECT NO BRANCH, so `init` writes the hook that refuses a deletion or a
    rewrite of `main`. The guard is the app's, run by the portfusion the book runs."""
    book = started()
    env = _git_env()
    env.pop("MAIN_REWRITE", None)

    def git(*args):
        return subprocess.run(["git", *args], cwd=book, env=env, capture_output=True, text=True)

    subprocess.run(["git", "init", "-q", "--bare", str(tmp_path / "origin.git")], check=True)
    git("remote", "add", "origin", str(tmp_path / "origin.git"))
    assert git("push", "-q", "origin", "HEAD:refs/heads/main").returncode == 0
    there = git("rev-parse", "HEAD").stdout.strip()
    git("commit", "-q", "--amend", "-m", "the first commit, rewritten")
    for args in (["--force", "origin", "HEAD:refs/heads/main"], ["origin", "--delete", "main"]):
        result = git("push", "-q", *args)
        assert result.returncode != 0 and "REFUSED" in result.stderr, (args, result.stderr)
    shown = subprocess.run(["git", "rev-parse", "refs/heads/main"], cwd=tmp_path / "origin.git",
                           capture_output=True, text=True).stdout.strip()
    assert shown == there, "main moved on the remote"


def test_a_new_books_gate_refuses_when_it_cannot_run(started, tmp_path):
    """A gate that cannot find the app has checked nothing, so the commit is refused and the
    line says how to give it the app: never waved through."""
    book = started()
    result = _commit(book, ["/usr/bin", "/bin"])
    assert result.returncode != 0 and "could not run" in result.stderr, result.stderr


def test_a_book_made_to_push_on_commit_says_when_a_commit_is_not_backed_up(started, tmp_path):
    """`--push-on-commit` pushes a BRANCH, and a detached HEAD has none, so the hook says a commit
    there is not backed up. It never fails a commit, and a book made without the option has no
    such hook."""
    assert not (create(tmp_path / "plain") / ".githooks" / "post-commit").exists()
    book = started(push_on_commit=True)
    env = _git_env()

    def commit(name):
        """What the commit says (git hands a hook's output to stderr); it must never fail."""
        (book / name).write_text("a trade, and why")
        subprocess.run(["git", "add", name], cwd=book, env=env, check=True)
        done = subprocess.run(["git", "commit", "-qm", name], cwd=book, env=env,
                              capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return done.stdout + done.stderr

    on_branch = commit("notes.md")
    assert "could not push" in on_branch and "DETACHED" not in on_branch, on_branch
    subprocess.run(["git", "checkout", "-q", "--detach"], cwd=book, env=env, check=True)
    detached = commit("more.md")
    assert "NOT backed up" in detached and "git switch -c" in detached, detached


@pytest.mark.audit
def test_the_loaded_book_holds_what_init_writes_and_its_hooks_are_the_releases(tmp_path):
    """A BOOK MADE BY AN EARLIER RELEASE, or filled from another folder's files, can lack a file
    every new book now gets, or keep a hook or ignore list the release has since changed. A new
    book is made beside it and the two compared: every file it holds must be there, and its
    `.gitignore` and hooks byte for byte, so a pin that moves takes them by copying a new book's.
    A post-commit hook is held only when `--push-on-commit` wrote it: one of the book's own making
    is the book's. The demo ships inside the app and is no book's folder, so it has nothing to hold."""
    if schema.BOOK == schema.DEMO:
        return
    hook = schema.BOOK / ".githooks" / "post-commit"
    new = create(tmp_path / "new", push_on_commit=hook.is_file()
                 and "portfusion init --push-on-commit" in hook.read_text(encoding="utf-8"))
    written = [p.relative_to(new) for p in new.rglob("*")
               if p.is_file() and ".git" not in p.relative_to(new).parts]
    missing = [str(p) for p in written if not (schema.BOOK / p).is_file()]
    assert written and not missing, f"a new book holds these and this one does not: {missing}"
    differ = [str(p) for p in written if p.parts[0] in (".gitignore", ".githooks")
              and (schema.BOOK / p).read_bytes() != (new / p).read_bytes()]
    assert not differ, f"not what this release writes; take its copy from a new book: {differ}"


def test_a_new_book_names_the_portfusion_it_runs(tmp_path, monkeypatch):
    """The book is a folder, not a fork: it names the release it runs, against the lock its suite
    was proved on, and `portfusion init` makes the venv that installs that and nothing else
    (`README.md`, the book's folder). The install is stubbed: a test reaches no package index."""
    from portfusion import init
    from portfusion.init import __main__ as command
    book = create(tmp_path / "book")
    lines = [ln for ln in (book / "requirements.txt").read_text().splitlines()
             if not ln.startswith("#")]
    assert lines == [init.pin(), init.constraint()][:2 if init.constraint() else 1]
    assert lines[0].startswith("portfusion")
    # FROM A CHECKOUT, its own lock: the one the editable install was proved on.
    lock = SRC.parent.parent / "requirements.lock"
    assert not lock.is_file() or init.constraint() == f"-c {lock}"
    # FROM A RELEASE ON GITHUB, the lock at the commit it was installed from.
    monkeypatch.setattr(init, "_installed", lambda: {
        "url": "https://github.com/an-owner/a-repo.git", "vcs_info": {"commit_id": "0123abc"}})
    assert init.constraint() == ("-c https://raw.githubusercontent.com/an-owner/a-repo/0123abc/"
                                 "requirements.lock")
    monkeypatch.undo()

    ran = []
    monkeypatch.setattr(init.subprocess, "run", lambda step, **k: ran.append((step, k["cwd"]))
                        or subprocess.CompletedProcess(step, 0))
    assert command.main([str(tmp_path / "venv-book"), "--no-git"]) == 0
    folder = tmp_path / "venv-book"
    assert ran == [([sys.executable, "-m", "venv", str(folder / ".venv")], folder),
                   ([str(folder / ".venv/bin/python3"), "-m", "pip", "install", "-q",
                     "-r", "requirements.txt"], folder)]
    # A VENV THAT CANNOT BE MADE leaves the book written, and says so in the exit.
    monkeypatch.setattr(init.subprocess, "run",
                        lambda step, **k: subprocess.CompletedProcess(step, 1))
    assert command.main([str(tmp_path / "offline"), "--no-git"]) == 1
    assert (tmp_path / "offline" / "store").is_dir()


def test_a_new_books_journal_opens_with_it(tmp_path):
    """THE JOURNAL'S OPENING COUNTS ARE WRITTEN WITH THE BOOK: without them the check that catches
    a hand edit has nothing to reconcile against. One count per table, each of what was written,
    at one instant."""
    from portfusion.engine import Book
    from portfusion.record import rules
    book = create(tmp_path / "book", begins=2027)
    with rules.store_at(book / "store"):
        b = Book()
        assert b.journal_opened() is not None, "the new book's journal never opened"
        assert b.journal_unaccounted().empty, b.journal_unaccounted()
        opened = b.store["journal"]
        opened = opened[opened["route"] == "baseline"]
        assert sorted(opened["table"]) == sorted(t for t in schema.TABLES if t != "journal")
        assert opened["at"].nunique() == 1


def test_a_filter_for_the_suite_does_not_fail_the_books_run(monkeypatch):
    """`portfusion check -k <a suite test>` passes the filter to the book's run too, which then
    selects nothing, and pytest's exit 5 there is no failure. Without a filter, a book run that
    selects nothing is still a failure."""
    from portfusion import check
    from portfusion.record import schema
    monkeypatch.setattr(schema, "BOOK", schema.DEMO.parent / "not-the-demo")
    monkeypatch.setattr(check, "_checks", lambda book: [])
    monkeypatch.setattr(check, "_pytest", lambda paths, args, book: 0 if book == "demo" else 5)
    assert check.check(["-k", "a_suite_test"]) == 0
    assert check.check([]) == 5
