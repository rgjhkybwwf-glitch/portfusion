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
    from portfusion.about import PROJECT_VENV, interpreter
    assert PROJECT_VENV == repo_root / ".venv"
    d = interpreter()
    assert d["is_project_venv"] is (pathlib.Path(sys.prefix).resolve()
                                    == PROJECT_VENV.resolve())
    # The line has to be readable at a glance in either state, and must SAY when it is wrong.
    assert ("NOT the project .venv" in d["line"]) is not d["is_project_venv"]


# =====================================================================================
# THE BACKUP REPORTS ITS OWN STATE
#
# The owner reported that the repo backup "had never fired". It had: every commit was in the
# bare repo within seconds. NOTHING WAS BROKEN — but nothing ever said so either, because the
# hook that pushed printed only on failure. A working backup and an absent one looked
# identical from the outside, and after a while the owner stopped believing in it.
#
# That is a real defect in a backup. These check that the line tells the truth in both
# directions, because a freshness line that only ever says "current" is furniture.
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
    """The state that matters most, and the one the owner believed the repository was in."""
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
    """The hook pushes a branch; on a detached HEAD there is none. This line used to read
    `'' HAS NEVER BEEN PUSHED`, which is true and sounds like a glitch."""
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
    `.githooks`. Those hooks run; comparing the setting as text called them NOT ACTIVE."""
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
