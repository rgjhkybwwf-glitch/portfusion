"""
WHAT A RUN SAYS IT IS MADE OF: two lines `portfusion record` prints come from about.py and are
held here: which Python ran, and whether GitHub holds the branch.
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


def test_a_skip_about_the_copy_or_the_demo_is_no_books():
    """A book lists the skips its rows explain. One about the installed copy, or about the demo's
    own documents, is the same on every book: no book lists it, and none fails its run for it."""
    import types
    import harness

    def skipped(why):
        return types.SimpleNamespace(longrepr=("a_test.py", 1, f"Skipped: {why}"))
    assert harness._the_books(skipped("the book holds no income rows yet"))
    assert not harness._the_books(skipped(harness.NO_CHECKOUT))
    assert not harness._the_books(skipped(harness.DEMO_ONLY))


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
    """backup_state() as seen from `work`. It shells out to git, so cwd is the input."""
    import os
    from portfusion.about import backup_state
    old = os.getcwd()
    try:
        os.chdir(work)
        return backup_state()
    finally:
        os.chdir(old)


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
