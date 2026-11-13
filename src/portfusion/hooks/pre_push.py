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

AND IT WRITES UP WHAT IT CHANGES: a branch that changes the app since it left `origin/main`, its
tests apart, also changes `CHANGELOG.md`, or the push is refused (`unlogged`). The version beside
it is `test_brand.py`'s to hold.

AND IT NAMES THE GUIDES IT LEAVES BEHIND, and lets the push go: a guide that names a file the
branch changed, when the guide itself did not change (`behind`). Whether its words are still right
is a reader's call; the release's read starts from these.

Held by tests/test_hooks.py.
"""
import os
import pathlib
import re
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


#: What a push of this checkout writes up, and where: the app, its tests apart.
APP, TESTS, CHANGELOG = "src/portfusion/", "src/portfusion/tests/", "CHANGELOG.md"


def unlogged(sha: str, checkout) -> list[str]:
    """The app's files `sha` changes since it left `origin/main`, when it leaves `CHANGELOG.md`
    as it was; none when it changes the changelog too, or `origin/main` is not here to ask."""
    run = subprocess.run(["git", "diff", "--name-only", f"origin/main...{sha}"], cwd=checkout,
                         capture_output=True, text=True)
    names = run.stdout.split()
    if run.returncode or CHANGELOG in names:
        return []
    return [n for n in names if n.startswith(APP) and not n.startswith(TESTS)]


def written_up(lines: list[str], checkout) -> int:
    """0 when every branch pushed writes up the app changes it carries, 1 and the files if not."""
    for line in lines:
        fields = line.split()
        if len(fields) != 4 or fields[1] == ZERO:
            continue
        files = unlogged(fields[1], checkout)
        if files:
            log.error(f"pre-push: REFUSED. {fields[0]} changes the app and not {CHANGELOG}: add "
                      f"its line under Unreleased.\n  " + "\n  ".join(files[:10]))
            return 1
    return 0


#: The guides a push of this checkout reads for what it leaves behind: the way in, and `docs/`
#: but the audit's evidence log, which records what was seen and is not kept current.
GUIDES, NOT_GUIDES = ("README.md", "CONTRIBUTING.md", "CLAUDE.md", "docs/*.md"), ("docs/ux-audit.md",)


def guide_pointers(text: str) -> list[tuple[int, str]]:
    """(line, pointer) for every path a guide names in code or as a link target.

    A fenced block is blanked line for line so the numbers stay true. A span holding a space is a
    command and one holding `*` or `<` a pattern; a bare extension names a kind of file, not one."""
    text = re.sub(r"```.*?```", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for code, link in re.findall(r"`([^`\n]+)`|\]\(([^)\s]+)\)", line):
            t = (code or link).strip()
            if re.search(r"[\s*<]", t) or t.startswith(("~", "/", ":", "#", "http")):
                continue
            path = re.split(r":+", t, maxsplit=1)[0]
            if re.fullmatch(r"\.\w+", path):
                continue
            if (re.search(r"\.(py|md|csv|json|css|js|html|ini|toml|txt|xlsx)$", path)
                    or ("/" in path and re.fullmatch(r"[\w./-]+", path))):
                out.append((n, t))
    return out


def behind(sha: str, checkout, base: str = "origin/main") -> dict[str, list[str]]:
    """Each guide naming a file `sha` changes since it left `base`, when the guide is not among
    the changes, with the files it names; empty when `base` is not here to ask. A guide names a
    file by its path from the root or from the guide's folder, or by a tail only that file has, or
    only the one nearest the root. A changed guide is a guide, not a file left behind."""
    root = pathlib.Path(checkout)
    run = subprocess.run(["git", "diff", "--name-only", f"{base}...{sha}"], cwd=root,
                         capture_output=True, text=True)
    if run.returncode:
        return {}
    changed = set(run.stdout.split())
    # THE GUIDES AS `sha` HOLDS THEM, not as the working tree does: a draft is not pushed.
    listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha], cwd=root,
                            capture_output=True, text=True).stdout.split()
    guides = sorted({p for g in GUIDES for p in listed if pathlib.PurePosixPath(p).match(g)
                     and p.count("/") == g.count("/")} - set(NOT_GUIDES) - changed)

    def names(pointer: str, here: str) -> str | None:
        path = re.split(r":+", pointer, maxsplit=1)[0].rstrip("/")
        for c in (path, os.path.normpath(f"{here}/{path}")):
            if c in listed:
                return c
        tails = sorted((p for p in listed if p.endswith("/" + path)), key=lambda p: p.count("/"))
        if len(tails) == 1 or (tails and tails[0].count("/") < tails[1].count("/")):
            return tails[0]
        return None

    out = {}
    for guide in guides:
        here = str(pathlib.PurePosixPath(guide).parent)
        text = subprocess.run(["git", "show", f"{sha}:{guide}"], cwd=root, capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
        named = {names(p, here) for _, p in guide_pointers(text)}
        left = sorted(n for n in named & changed if not n.endswith(".md"))
        if left:
            out[guide] = left
    return out


def said_behind(lines: list[str], checkout) -> None:
    """Name the guides each branch pushed leaves behind. It never refuses."""
    for line in lines:
        fields = line.split()
        if len(fields) != 4 or fields[1] == ZERO:
            continue
        found = behind(fields[1], checkout)
        if found:
            log.info(f"pre-push: these guides name files {fields[0]} changed, and did not "
                     f"change:\n  " + "\n  ".join(f"{g}: {', '.join(fs)}" for g, fs in found.items()))


def main(argv: list[str], lines: list[str], checkout=None) -> int:
    """`checkout`, given only by a checkout's own hook pushing that checkout, adds `said_behind`,
    `written_up` and `what_leaves`."""
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
        if not checkout:
            return 0
        said_behind(lines, checkout)
        return written_up(lines, checkout) or what_leaves(checkout)
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
