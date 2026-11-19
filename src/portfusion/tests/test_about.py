"""
WHAT A RUN SAYS IT IS MADE OF: two lines `portfusion record` prints come from about.py and are
held here: which Python ran, and whether GitHub holds the branch. And which release it is: the
number's one home, and what the README and the changelog say of it.
"""
import pathlib
import sys

import pytest


def test_the_interpreter_is_reported_not_typed(repo_root):
    """The venv path is DERIVED from the module's own location, never written down — the same
    rule every figure in this book sits under."""
    from portfusion.about import interpreter, project_venv
    assert project_venv() == repo_root / ".venv"
    d = interpreter()
    assert d["is_project_venv"] is (pathlib.Path(sys.prefix).resolve()
                                    == project_venv().resolve())
    # The line has to be readable at a glance in either state, and must SAY when it is wrong.
    assert ("NOT the project .venv" in d["line"]) is not d["is_project_venv"]


def test_the_guard_names_an_app_that_is_not_installed(monkeypatch):
    """The suite's environment guard, run where the app is not installed: its refusal says so,
    rather than the guard raising before it can refuse."""
    import importlib.metadata
    import harness

    def not_installed(name):
        raise importlib.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(importlib.metadata, "requires", not_installed)
    assert f"{harness.SRC.name} is not installed" in harness.environment_faults()


def test_a_skip_fails_the_run_unless_the_book_lists_it_and_a_listed_one_that_ran_fails():
    """A book lists the skips its rows explain. One about the installed copy, or about the demo's
    own documents, is the same on every book: no book lists it, and none fails its run for it.
    A listed test that ran fails the run too: its line would let it skip unseen later."""
    import types
    import harness

    def skipped(why):
        return types.SimpleNamespace(longrepr=("a_test.py", 1, f"Skipped: {why}"))
    assert harness._the_books(skipped("the book holds no income rows yet"))
    assert not harness._the_books(skipped(harness.NO_CHECKOUT))
    assert not harness._the_books(skipped(harness.DEMO_ONLY))
    assert harness.skips_off(seen={"a", "b"}, ran={"c", "d"}, listed={"b", "c"}) == (["a"], ["c"])
    # BY FILE NAME, never folder: a file moved between the suite's folders changes no book's list.
    assert {harness._test_id(n) for n in ("src/portfusion/tests/desk/test_x.py::test_y[a/b]",
                                          "desk/test_x.py::test_y[a/b]", "test_x.py::test_y[a/b]")
            } == {"test_x.py::test_y[a/b]"}


# =====================================================================================
# THE BACKUP REPORTS ITS OWN STATE
#
# A hook that prints only on failure makes a working backup look like an absent one. These
# check that the line tells the truth in both directions, because a freshness line that only
# ever says "current" is furniture.
# =====================================================================================

def _bare_repo(tmp_path, work):
    import subprocess
    bare = tmp_path / "backup.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=work, check=True)
    return bare


@pytest.fixture
def sandbox(tmp_path):
    """A throwaway repo whose `origin` is a local bare repo. NEVER the real one: this pushes."""
    import subprocess
    work = tmp_path / "work"
    work.mkdir()
    for args in (["init", "-q", "-b", "master"],
                 ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=work, check=True)
    (work / "a.txt").write_text("one")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=work, check=True)
    return work, _bare_repo(tmp_path, work)


def _state_in(work):
    """backup_state() of a book at `work`, typed from wherever the suite runs: the book is the
    input, never the folder the command was typed in."""
    from portfusion.about import backup_state
    from portfusion.record import schema
    with pytest.MonkeyPatch.context() as m:
        m.setattr(schema, "BOOK", work)
        return backup_state()


def test_backup_says_never_pushed_before_the_first_push(sandbox):
    """Before the first push, the line says the branch HAS NEVER BEEN PUSHED."""
    work, _ = sandbox
    assert "HAS NEVER BEEN PUSHED" in _state_in(work)


def test_backup_says_current_when_the_tip_is_there(sandbox):
    import subprocess
    work, _ = sandbox
    subprocess.run(["git", "push", "-q", "origin", "master"], cwd=work, check=True)
    assert _state_in(work).startswith("backup: current")


def test_backup_says_behind_and_counts_the_commits(sandbox):
    """A backup that is stale must say by how much, or 'not current' is unactionable."""
    import subprocess
    work, _ = sandbox
    subprocess.run(["git", "push", "-q", "origin", "master"], cwd=work, check=True)
    for n in ("two", "three"):
        (work / "a.txt").write_text(n)
        subprocess.run(["git", "commit", "-aqm", n], cwd=work, check=True)
    state = _state_in(work)
    assert "BEHIND by 2 commit(s)" in state, state
    assert "git push origin master" in state, "it must say how to fix it"


def test_backup_says_so_when_there_is_no_origin(sandbox):
    """The audit runs constantly. A clone with its remote removed must be told, never raise."""
    import subprocess
    work, _ = sandbox
    subprocess.run(["git", "remote", "remove", "origin"], cwd=work, check=True)
    assert "NO 'origin' REMOTE" in _state_in(work)


def test_backup_says_when_the_hooks_are_off(sandbox):
    """A clone does not carry `core.hooksPath`, so a restored copy neither pushes nor checks a
    commit for credentials. Nothing fails when that happens, so this line must say it."""
    import subprocess
    work, _ = sandbox
    assert "hooks: NOT ACTIVE" in _state_in(work)
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=work, check=True)
    assert "hooks" not in _state_in(work)


def test_backup_says_a_detached_head_pushes_nothing(sandbox):
    """The hook pushes a branch; on a detached HEAD there is none."""
    import subprocess
    work, _ = sandbox
    subprocess.run(["git", "push", "-q", "origin", "master"], cwd=work, check=True)
    subprocess.run(["git", "checkout", "-q", "--detach"], cwd=work, check=True)
    state = _state_in(work)
    assert "DETACHED" in state and "which origin holds" in state and "git switch -c" in state, state
    (work / "a.txt").write_text("two")
    subprocess.run(["git", "commit", "-aqm", "two"], cwd=work, check=True)
    assert "which origin does NOT hold" in _state_in(work)


def test_backup_counts_the_hooks_on_in_a_worktree_pointed_at_the_main_checkout(sandbox, tmp_path):
    """The desktop app gives a session worktree an ABSOLUTE core.hooksPath, to the main checkout's
    `.githooks`. Those hooks run, whatever the setting's spelling."""
    import subprocess
    work, _ = sandbox
    tree = tmp_path / "tree"
    for cwd, args in ((work, ["config", "core.hooksPath", ".githooks"]),
                      (work, ["worktree", "add", "-q", str(tree), "-b", "side"]),
                      (work, ["config", "extensions.worktreeConfig", "true"]),
                      (tree, ["config", "--worktree", "core.hooksPath", str(work / ".githooks")])):
        subprocess.run(["git", *args], cwd=cwd, check=True)
    assert "hooks" not in _state_in(tree)
    subprocess.run(["git", "config", "--worktree", "core.hooksPath", str(tmp_path / "elsewhere")],
                   cwd=tree, check=True)
    assert "hooks: NOT ACTIVE" in _state_in(tree)


def test_an_installed_book_runs_on_its_own_venv(tmp_path, monkeypatch):
    """A BOOK RUNS ON ITS OWN VENV: where the app is installed, the project is the loaded book."""
    from portfusion import about
    from portfusion.record import schema
    venv = tmp_path / ".venv"
    venv.mkdir()
    monkeypatch.setattr(schema, "ROOT", None)
    monkeypatch.setattr(schema, "BOOK", tmp_path)
    monkeypatch.setattr(sys, "prefix", str(venv))
    d = about.interpreter()
    assert d["is_project_venv"] and "NOT the project .venv" not in d["line"], d["line"]


def test_an_installed_release_names_its_own_commit(monkeypatch):
    """INSTALLED, THE CODE'S COMMIT is the one it was installed from, never that of the book's
    repository around it."""
    import portfusion
    from portfusion import about
    from portfusion.record import schema
    monkeypatch.setattr(portfusion, "__version__", "9.9.0.dev0")    # a release names no commit
    monkeypatch.setattr(schema, "ROOT", None)
    monkeypatch.setattr(about, "_installed_commit", lambda: "abc1234")
    assert about.release() == "PortFusion 9.9.0.dev0 · abc1234", about.release()
    assert "· PortFusion 9.9.0.dev0 · abc1234 ·" in about.stamp(), "the footer's stamp drops it"


def test_the_release_has_one_home_and_every_reader_meets_it(monkeypatch):
    """The number is PEP 440 and lives in portfusion/__init__.py alone; `beta` is a label beside
    it; between releases the dev number travels with its commit, and a release with neither.
    `portfusion --version`, the desk's footer and the report's stamp all say `about.release()`."""
    import importlib.metadata
    import re
    import portfusion
    from portfusion import about
    from portfusion.__main__ import main
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+)?", portfusion.__version__), portfusion.__version__
    assert importlib.metadata.version("portfusion") == portfusion.__version__, \
        "the installed metadata is another number: reinstall, `pip install -e .`"
    monkeypatch.setattr(portfusion, "__version__", "9.9.0")
    assert about.release() == f"PortFusion 9.9.0 {portfusion.LABEL}"
    monkeypatch.setattr(portfusion, "__version__", "9.9.0.dev0")
    assert about.release().startswith("PortFusion 9.9.0.dev0")
    monkeypatch.setattr(about, "_commit", lambda root: "abc1234")           # a checkout
    monkeypatch.setattr(about, "_installed_commit", lambda: "abc1234")       # an install
    assert about.release() == "PortFusion 9.9.0.dev0 · abc1234"
    assert main(["--version"]) == 0


def test_a_release_is_installed_and_described_by_its_own_number(repo_root):
    """The README installs the newest release, and the changelog opens on what the number says: a
    release's own entry, dated, or between releases `Unreleased` above the release installed."""
    import datetime
    import re
    import portfusion
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    pins = set(re.findall(r"portfusion@v(\d+\.\d+\.\d+)\b", readme))
    entries = re.findall(r"^## (.+)$", changelog, re.M)
    dated = [e for e in entries if e != "Unreleased"]
    assert len(pins) == 1 and dated, f"the README installs {sorted(pins)}; the changelog's entries {entries[:2]}"
    number, _, day = dated[0].partition(f" — {portfusion.LABEL}, ")
    assert re.fullmatch(r"\d+\.\d+\.\d+", number) and day, f"a heading not `N.N.N — label, day`: {dated[0]}"
    datetime.datetime.strptime(day, "%d %b %Y")
    version, _, dev = portfusion.__version__.partition(".dev")
    assert entries[0] == ("Unreleased" if dev else dated[0]), entries[0]
    if dev:
        assert tuple(map(int, version.split("."))) > tuple(map(int, number.split("."))), \
            f"version {portfusion.__version__} is not ahead of the newest release, {number}"
    else:
        assert number == version, f"version {version}, but the changelog's newest entry is {number}"
    assert pins == {number}, f"the README installs v{pins.pop()}, the changelog's newest release is {number}"
