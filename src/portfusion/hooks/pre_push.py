"""Refuse a push that would delete `main` or rewrite it.

A host may not enforce branch protection, so the moment before a push leaves the machine is
the one moment it can be stopped. Every change
reaches `main` either as a merge made on GitHub or as a commit made on top of it, and each of
those only ever adds to `main`. A push that takes anything away from it is refused:

1. Deleting `main`, by any remote, refspec or flag.
2. Moving `main` to a commit that does not contain the one it is on now: a force push, a reset,
   an amend or a rebase pushed over it. When this checkout has not fetched the commit `main` is
   on (a merge made on GitHub and not yet pulled), it is not known to be safe either, and is
   refused with the pull that resolves it.

Every other branch is free: a merged branch is deleted from GitHub, and a session's own branch
is its own.

THE OVERRIDE NAMES WHAT IT OVERWRITES. The owner approves a rewrite by naming the commit that
`main` is on now, at least seven characters of it:

    MAIN_REWRITE=<sha> git push --force-with-lease origin main

so an approval covers that one rewrite and cannot be carried to the next. `git push --no-verify`
skips this hook, as it is git's own; `.claude/settings.json` denies both, and every force push,
to a Claude session, which leaves them to the owner's own terminal.

THE GUARD IS THE APP'S, as the secret gate is: this checkout's `.githooks/pre-push` runs it from
`src/`, and a book's, which `portfusion init` writes (`init.PUSH_HOOK`), runs it from the
portfusion the book has installed.

A PUSH OF THIS CHECKOUT ALSO NAMES NOTHING OF A BOOK: its hook runs `LEAKS` on the book
`PORTFUSION_BOOK` names and refuses a push that names it, or that names no book, so a push that
checks nothing is a choice made by naming the demo. A book's own push does not.

Held by tests/test_hooks.py.
"""
import os
import pathlib
import subprocess
import sys

from portfusion.log import log

PROTECTED = "refs/heads/main"
ZERO = "0" * 40


def is_ancestor(old: str, new: str) -> bool | None:
    """Does `new` contain `old`? None when this checkout does not have `old` at all."""
    if subprocess.run(["git", "cat-file", "-e", f"{old}^{{commit}}"],
                      capture_output=True).returncode:
        return None
    return subprocess.run(["git", "merge-base", "--is-ancestor", old, new],
                          capture_output=True).returncode == 0


def refusal(local_sha: str, remote_sha: str) -> tuple[str, bool] | None:
    """Why a push of `main` from local_sha over remote_sha is refused, and whether the override
    may approve it; None when the push only adds. An unfetched tip is never approved: what it
    would overwrite has not been seen."""
    if remote_sha == ZERO:
        return None                                          # main is new on that remote
    if local_sha == ZERO:
        return "deletes main", True
    contained = is_ancestor(remote_sha, local_sha)
    if contained:
        return None
    if contained is None:
        return (f"main is at {remote_sha[:7]} there, a commit this checkout has not fetched: "
                f"`git pull --ff-only origin main`, then push", False)
    return f"rewrites main: {remote_sha[:7]} there is not contained in {local_sha[:7]}", True


def approved(remote_sha: str) -> bool:
    named = os.environ.get("MAIN_REWRITE", "").strip().lower()
    return len(named) >= 7 and remote_sha.startswith(named)


#: The test a push from a checkout runs on the book `PORTFUSION_BOOK` names (CONTRIBUTING.md).
LEAKS = "src/portfusion/tests/test_what_leaves.py"


def what_leaves(checkout) -> int:
    """Run `LEAKS` from `checkout` on the named book: 0 when it passes, 1 when what is pushed
    names the book or no book is named."""
    book = os.environ.get("PORTFUSION_BOOK", "").strip()
    if not book:
        log.error("pre-push: REFUSED. PORTFUSION_BOOK names no book, so nothing would check this "
                  "push for a book's names. Name yours, or `PORTFUSION_BOOK=demo` to push "
                  "without the check.")
        return 1
    # The checkout's own venv: the hook's python may have no pytest, and another checkout's
    # install is refused by the suite (docs/environment.md).
    venv = pathlib.Path(checkout) / ".venv" / "bin" / "python3"
    python = str(venv) if venv.exists() else sys.executable
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    run = subprocess.run([python, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", LEAKS],
                         cwd=checkout, env=env, capture_output=True, text=True)
    if run.returncode == 0:
        for line in run.stdout.splitlines():
            if line.startswith("SKIPPED"):
                log.info(f"pre-push: {line.rsplit(': ', 1)[-1]}, so nothing was checked for it.")
        return 0
    said = [ln for ln in run.stdout.splitlines() if ln.startswith("E ")]
    if said:
        log.error(f"pre-push: REFUSED. What this push carries names the book at {book}.\n")
    else:
        log.error("pre-push: REFUSED. The leak test could not run:\n")
    log.error("\n".join(said or (run.stdout + run.stderr).strip().splitlines()[-15:]))
    return 1


def main(argv: list[str], lines: list[str], checkout=None) -> int:
    """`checkout`, given only by a checkout's own hook pushing that checkout, adds `what_leaves`."""
    remote = argv[0] if argv else "the remote"
    problems = []
    for line in lines:
        fields = line.split()
        if len(fields) != 4 or fields[2] != PROTECTED:
            continue
        _, local_sha, _, remote_sha = fields
        refused = refusal(local_sha, remote_sha)
        if refused and not (refused[1] and approved(remote_sha)):
            problems.append((*refused, remote_sha))
    if not problems:
        return what_leaves(checkout) if checkout else 0
    log.error(f"pre-push: REFUSED. This push to {remote} would take something away from main.\n")
    for why, _, _ in problems:
        log.error(f"  {why}")
    log.error("\nChanges reach main as a pull request merged on GitHub (CONTRIBUTING.md). If "
              "GitHub has a merge this checkout lacks, take it first:\n"
              "  git pull --no-rebase --no-edit origin main")
    for _, overridable, remote_sha in problems:
        if overridable:
            log.error("Only the owner rewrites it, naming the commit it replaces:\n"
                      f"  MAIN_REWRITE={remote_sha[:12]} git push --force-with-lease {remote} main")
    return 1


if __name__ == "__main__":                      # python3 -m portfusion.hooks.pre_push
    sys.exit(main(sys.argv[1:], sys.stdin.read().splitlines()))
