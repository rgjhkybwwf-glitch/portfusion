"""Refuse a commit that would put a credential into git.

THE GATE BEFORE A COMMIT EXISTS. Secret scanning on the host may be off, and a commit pushed is
published, so the moment before a commit exists is the one moment a leak can be stopped. A key that did get out is not recalled
by deleting it from git: it is changed at the broker.

Three checks, over what is STAGED rather than the working tree:

1. A path the ignore list excludes. `git add -f` overrides `.gitignore`; this does not. The
   list is asked of `git check-ignore --no-index`, so it is `.gitignore`'s and nothing here
   restates it.
2. A value from the credential files, searched for in every staged file's bytes, PDFs
   included.
3. A key-shaped string: the formats a secret could arrive in that are not in those files.

What counts as a credential, and which fields are exempt, is `portfusion/secret_scan.py`, which the
hosted desk's publish asks too. THE GATE IS THE APP'S, so every repository it guards asks the one
copy: this checkout's `.githooks/pre-commit` runs it from `src/`, and a book's, which
`portfusion init` writes (`init.HOOK`), runs it from the portfusion the book has installed.
`git commit --no-verify` bypasses it; that is git's own escape hatch and deliberately the only one.

`--history` runs the same checks over every file and commit message ever committed, on any
branch or tag. That is the scan to run before the history goes anywhere new.

Held by tests/test_hooks.py.
"""
import pathlib
import subprocess
import sys

from portfusion import secret_scan
from portfusion.log import log
from portfusion.secret_scan import KEY_SHAPES, matches


def git(*args, stdin=b""):
    return subprocess.run(["git", *args], input=stdin, capture_output=True, check=True).stdout


def checkouts():
    """This checkout, and the main one. A worktree holds no credential files of its own, and a
    commit made from one must still be checked against the real ones."""
    here = pathlib.Path(git("rev-parse", "--show-toplevel").decode().strip())
    common = pathlib.Path(git("rev-parse", "--path-format=absolute",
                              "--git-common-dir").decode().strip())
    return list(dict.fromkeys([here, common.parent]))


def credential_values():
    """{value: 'file key/path'} for every secret in this checkout and the main one, and whether
    any file was found."""
    values, found, unreadable = secret_scan.credential_values(checkouts())
    for name in unreadable:
        log.warning(f"pre-commit: {name} is not valid JSON, so its values were not checked")
    return values, found


def staged():
    """[(path, blob)] for every file this commit adds or changes. Each raw entry is
    `:<old mode> <new mode> <old blob> <new blob> <status>` then the path; a submodule (mode
    160000) is a commit, not a file, and is skipped."""
    out = git("diff", "--cached", "--raw", "-z", "--no-abbrev", "--no-renames",
              "--diff-filter=AM")
    fields = out.split(b"\0")
    return [(fields[i + 1].decode(), fields[i].split()[3].decode())
            for i in range(0, len(fields) - 1, 2)
            if fields[i].split()[1] != b"160000"]


def ever_committed():
    """[(path, blob)] for every file in every commit reachable from any branch or tag."""
    out = git("rev-list", "--all", "--objects", "--filter=object:type=blob").decode()
    return [(line[41:], line[:40]) for line in out.splitlines() if len(line) > 41]


def contents(blobs):
    """Each blob's bytes, in order, from one `git cat-file --batch` call."""
    out = git("cat-file", "--batch", stdin="".join(b + "\n" for b in blobs).encode())
    at = 0
    for _ in blobs:
        end = out.index(b"\n", at)
        header = out[at:end].split()
        if len(header) < 3:                                  # "<name> missing"
            at = end + 1
            yield b""
            continue
        size = int(header[2])
        yield out[end + 1:end + 1 + size]
        at = end + 1 + size + 1


def findings(files, values):
    """(where, why) for everything in `files` that must not be committed."""
    if files:
        ignored = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin", "-z"], capture_output=True,
            input=b"".join(p.encode() + b"\0" for p, _ in files)).stdout
        for path in filter(None, ignored.split(b"\0")):
            yield path.decode(), "is on the ignore list (added with -f?)"
    for (path, _), data in zip(files, contents([b for _, b in files])):
        yield from matches(path, data, values)


def messages(values):
    """(commit, why) for every commit message that holds a credential."""
    out = git("log", "--all", "--format=%H%n%B%x00")
    for entry in filter(None, (e.strip() for e in out.split(b"\0"))):
        sha, _, body = entry.partition(b"\n")
        yield from matches(f"commit {sha[:7].decode()} message", body, values)


def main(argv):
    history = "--history" in argv
    values, found = credential_values()
    files = ever_committed() if history else staged()
    problems = sorted(set(findings(files, values)))
    if history:
        problems += sorted(set(messages(values)))
    if not found:
        log.warning("pre-commit: no credential files here, so only the ignore list and the key "
                    "shapes were checked")
    if not problems:
        if history:
            log.info(f"history: clean. {len(files)} files ever committed and every commit "
                     f"message, against {len(values)} credential values and {len(KEY_SHAPES)} "
                     f"key shapes.")
        return 0
    log.error("pre-commit: REFUSED. This would put a credential into git.\n" if not history
              else "history: NOT CLEAN.\n")
    width = max(len(w) for w, _ in problems)
    for where, why in problems:
        log.error(f"  {where:{width}}  {why}")
    if not history:
        log.error("\nUnstage it with `git restore --staged <file>` and commit again. A key that "
                  "was ever pushed is not recalled by deleting it: change it at the broker.")
    return 1


if __name__ == "__main__":                      # python3 -m portfusion.hooks.pre_commit
    sys.exit(main(sys.argv[1:]))
