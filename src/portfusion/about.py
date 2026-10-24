"""
about.py — WHAT THIS RUN IS MADE OF: which release, which code, which book, which Python, and
whether the book's history is backed up. `portfusion record` prints these lines, the desk's footer
carries the release, the report's footer the stamp, and the suite names the book it ran on. Each
is REPORTED, never enforced.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path as _Path


def _commit(root: str) -> str | None:
    """The checkout's short commit, "+uncommitted" when its tree is edited; None where the code
    is not a checkout, as an installed release is not."""
    import subprocess
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                              capture_output=True, text=True, timeout=5).stdout.strip()
        if not head:
            return None
        changed = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                 capture_output=True, text=True, timeout=5).stdout.strip()
        return head + (" +uncommitted" if changed else "")
    except Exception:
        return None


def _installed_commit() -> str | None:
    """The short commit pip installed this release from, where it came from a repository; None
    for a release installed by its number or from a folder."""
    import json
    from importlib import metadata
    try:
        found = json.loads(metadata.distribution("portfusion").read_text("direct_url.json") or "{}")
    except Exception:
        return None
    commit = found.get("vcs_info", {}).get("commit_id")
    return commit[:7] if commit else None


def release(root: str | None = None) -> str:
    """WHICH RELEASE THIS IS, as a reader meets it: "PortFusion 0.2.0 beta" for a release, and
    between releases the dev number and the commit, "PortFusion 0.2.0.dev0 · 1a2b3c4", since a
    dev number alone names no one set of code."""
    from portfusion import LABEL, __version__
    if ".dev" not in __version__:
        return f"PortFusion {__version__} {LABEL}"
    if root is None:
        # THE CODE'S OWN COMMIT, never the folder's around it: installed in a book's `.venv`, git
        # asked from the package finds the book's repository.
        from portfusion.record import schema
        commit = _commit(str(schema.ROOT)) if schema.ROOT else _installed_commit()
    else:
        commit = _commit(root)
    return f"PortFusion {__version__}" + (f" · {commit}" if commit else "")


def stamp(root: str | None = None, store: str | None = None) -> str:
    """WHICH CODE AND WHICH DATA MADE THIS ARTEFACT, in one line.

    Two identifiers, because each moves on its own: the RELEASE pins the code — with its commit
    between releases, `release()` — and the STORE DIGEST pins the facts — a trade can change
    every figure with no commit behind it yet. "+uncommitted" is not a warning; it is the honest
    state of a book rebuilt against an edited tree.

    Never raises: a build must not fail because git is unavailable or the store moved.
    `store` is the folder the record was read from; a renderer passes `rules.store_dir()`, so
    a page built from another book never carries this repo's digest.
    """
    import hashlib
    import datetime

    code = release(root)            # asked before `root` defaults: installed, the package's
    root = root or os.path.dirname(os.path.abspath(__file__))   # folder holds no commit
    built = datetime.date.today().isoformat()

    try:
        store = str(store or os.path.join(root, "store"))
        digest = hashlib.sha256()
        for name in sorted(os.listdir(store)):
            if name.endswith(".csv"):
                with open(os.path.join(store, name), "rb") as fh:
                    digest.update(name.encode())
                    digest.update(fh.read())
        facts = digest.hexdigest()[:8]
    except Exception:
        facts = "unknown"

    return f"built {built} · {code} · store {facts}"


# =================================================================================================
# WHICH PYTHON IS RUNNING. Derived, never typed — the venv is the checkout's .venv where the app
# runs from one, and the loaded book's where it is installed: a book runs the release its
# requirements.txt names from a venv of its own.
def project_venv() -> _Path:
    from portfusion.record import schema
    return (schema.ROOT or schema.BOOK) / ".venv"


def interpreter() -> dict:
    """Which interpreter this is, and whether it is the project's own.

    REPORTED, NEVER ENFORCED. The tests refuse to run outside the venv (tests/harness.py); the
    AUDIT only reports, because a report built on the system interpreter the day before a close
    beats no report. You only have to KNOW that is what happened — docs/environment.md says why
    the two interpreters can differ.
    """
    prefix = _Path(sys.prefix).resolve()
    venv = project_venv()
    is_project = venv.exists() and prefix == venv.resolve()
    v = ".".join(str(n) for n in sys.version_info[:3])
    line = (f"{prefix} · {v}" if is_project
            else f"SYSTEM — {prefix} · {v}  (NOT the project .venv)")
    return {"prefix": str(prefix), "venv": str(venv),
            "is_project_venv": is_project, "version": v, "line": line}


def book_line() -> str:
    """WHICH BOOK THIS RUN LOADED, in one line, and how it was chosen: a run on the demo or a
    practice book passes as quietly as one on a real book, and the line is what tells them
    apart."""
    from portfusion.record import schema
    where = (str(schema.BOOK.relative_to(schema.ROOT)) or ".") if schema.ROOT and \
        schema.BOOK.is_relative_to(schema.ROOT) else str(schema.BOOK)
    settings = {k: v for k, v in schema.load("settings")}
    what = ("this repository's own book" if schema.BOOK == schema.ROOT
            else "the invented demo book" if schema.BOOK == schema.DEMO
            else "a practice book: a copy of the demo, its figures invented"
            if settings.get("practice") else "another book")
    return f"{where} — {what}" + (f" ({schema.ENV} set)" if schema.NAMED
                                  else " (the folder it ran in)")


def backup_state() -> str:
    """Whether GitHub holds this branch's tip, and whether the hooks that keep it so are on.

    A push from a hook prints only on FAILURE, so a working backup looks exactly like an absent
    one; a backup you cannot verify is one you stop trusting. This says so on every audit.

    READ-ONLY AND CANNOT FAIL THE AUDIT, and it never touches the network. It reads the
    remote-tracking ref that every successful push moves, so "current" means GitHub accepted
    this tip; it does not ask GitHub what it holds now.

    THE HOOKS ARE ON BY ONE LINE OF CONFIG THAT A CLONE DOES NOT CARRY. Without it a restored
    copy neither backs up nor checks a commit for credentials, and nothing else would say so. What
    is judged is the directory git will RUN, not the setting's spelling: the desktop app points a
    session worktree at the main checkout's `.githooks` by absolute path, and those hooks run.

    A DETACHED HEAD PUSHES NOTHING, because the hook pushes a branch and there is none.
    """
    import pathlib
    import subprocess

    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              timeout=5).stdout.strip()
    try:
        branch, head = git("symbolic-ref", "--short", "HEAD"), git("rev-parse", "HEAD")
        runs = pathlib.Path(git("rev-parse", "--path-format=absolute", "--git-path", "hooks"))
        ours = {(pathlib.Path(d) / ".githooks").resolve() for d in (
            git("rev-parse", "--show-toplevel"),
            pathlib.Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent)}
        hooks = ("" if runs.resolve() in ours else
                 " · hooks: NOT ACTIVE — `git config core.hooksPath .githooks`")
        if not git("remote", "get-url", "origin"):
            return "backup: NO 'origin' REMOTE — nothing off this machine" + hooks
        if not branch:
            held = "origin holds" if git("branch", "-r", "--contains", head) else \
                "origin does NOT hold"
            return (f"backup: DETACHED at {head[:7]}, which {held} — a commit here is on no "
                    f"branch and is never pushed. `git switch -c <name>` before committing" + hooks)
        there = git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}")
        if not there:
            return f"backup: '{branch}' HAS NEVER BEEN PUSHED to origin" + hooks
        if there == head:
            return f"backup: current — '{branch}' {head[:7]} is on origin" + hooks
        behind = git("rev-list", "--count", f"{there}..{head}")
        return (f"backup: BEHIND by {behind or '?'} commit(s) — origin has {there[:7]}, "
                f"HEAD is {head[:7]}. `git push origin {branch}`" + hooks)
    except Exception as e:                                    # never fail the check over a backup
        return f"backup: unknown ({type(e).__name__})"
