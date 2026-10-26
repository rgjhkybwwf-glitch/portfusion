"""The hooks: nothing that is a credential reaches git, and nothing takes anything away from `main`.

`.githooks/pre-commit` is the gate, and why it is the gate is `portfusion/hooks/pre_commit.py`'s
docstring. These run it for real, through `git commit`, in a throwaway repo pointed at the project's own hooks and given a
FAKE credentials file. Nothing here reads the real one.

A host may protect no branch, so `.githooks/pre-push` refuses a deletion or
a rewrite of `main`. Its tests push for real, to a bare repository in a temporary folder.
Pushing a checkout, it also runs the leak test on the named book.

The fake values are assembled at run time. Written out whole, this file would be refused by the
hook it tests.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

API_KEY = "0f1e2d3c4b5a" * 3 + "abcd"
PASSWORD = "fake-" + "password-" + "1234"
TOKEN = "fake+" + "token/" + "with=symbols"
ENV_TOKEN = "fake-" + "env-" + "token-" + "5678"
ACCOUNT_ID = "ZZ9Q1"
IDENTIFIER = "someuser"
ANTHROPIC_SHAPE = "sk-" + "ant-" + "api03-" + "x" * 40


def _git(work, *args):
    return subprocess.run(["git", *args], cwd=work, capture_output=True, text=True)


@pytest.fixture(scope="module")
def _repo_made(tmp_path_factory, repo_root):
    """`repo`, made once for the module: its first commit runs the hooks, which is the cost."""
    from portfusion import init
    work = tmp_path_factory.mktemp("repo") / "work"
    work.mkdir()
    for args in (["init", "-q", "-b", "master"], ["config", "user.email", "t@t"],
                 ["config", "user.name", "t"], ["config", "core.hooksPath", str(repo_root / ".githooks")]):
        _git(work, *args)
    (work / ".gitignore").write_text(init.GITIGNORE)
    (work / "credentials.json").write_text(json.dumps({"VOSS_IG": {
        "identifier": IDENTIFIER, "password": PASSWORD, "api_key": API_KEY, "token": TOKEN,
        "account_id": ACCOUNT_ID, "env": "LIVE"}}))
    _git(work, "add", ".gitignore")
    assert _git(work, "commit", "-qm", "start").returncode == 0
    return work


@pytest.fixture
def repo(_repo_made, tmp_path):
    """A throwaway repo on the project's hooks and a new book's `.gitignore`, holding a fake
    credentials.json, with no remote: a copy of the module's, for each test."""
    work = tmp_path / "work"
    shutil.copytree(_repo_made, work, symlinks=True)
    return work


def _commit(work, name, content, *add_flags):
    path = work / name
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    _git(work, "add", *add_flags, name)
    return _git(work, "commit", "-qm", f"add {name}")


def _refused(result):
    return result.returncode != 0 and "REFUSED" in result.stderr


def test_an_ordinary_commit_passes(repo):
    assert _commit(repo, "notes.md", "a trade, and why").returncode == 0


def test_the_credentials_file_is_refused_even_when_forced(repo):
    """`git add -f` overrides `.gitignore`. It must not override the hook."""
    result = _commit(repo, "credentials.json", (repo / "credentials.json").read_text(), "-f")
    assert _refused(result)
    assert "credentials.json" in result.stderr and "ignore list" in result.stderr


def test_a_planted_value_is_refused_by_NAME_and_never_quoted(repo):
    """A refusal that printed the key would leave it in the terminal's scrollback. A value is
    found as it is and in each form it arrives changed, from a `.env` as from the JSON files, in
    a file that was a link until this commit, and in the commit's message, above the scissors line
    `commit -v` writes in the comment string the repository uses."""
    import base64
    import urllib.parse
    (repo / ".env").write_text(f"export BROKER_TOKEN='{ENV_TOKEN}'  # the broker's\n")
    for planted, label in (
            (API_KEY, "credentials.json VOSS_IG/api_key"),
            (PASSWORD.upper(), "VOSS_IG/password (upper case)"),
            (urllib.parse.quote(TOKEN, safe=""), "VOSS_IG/token (URL-encoded)"),
            (base64.b64encode(f"{API_KEY} and more".encode()).decode(), "VOSS_IG/api_key (base64)"),
            (ENV_TOKEN, ".env BROKER_TOKEN")):
        result = _commit(repo, "notes.md", f"key was {planted} for a moment")
        assert _refused(result) and label in result.stderr, (label, result.stderr)
        assert planted not in result.stdout + result.stderr
        _git(repo, "restore", "--staged", "notes.md")
    (repo / "link.md").symlink_to("elsewhere.md")
    _git(repo, "add", "link.md")
    assert _git(repo, "commit", "-qm", "a link").returncode == 0
    (repo / "link.md").unlink()
    result = _commit(repo, "link.md", f"key was {API_KEY}")
    assert _refused(result) and "link.md" in result.stderr, result.stderr
    _git(repo, "restore", "--staged", "link.md")
    result = _git(repo, "commit", "--allow-empty", "-qm", f"key was {API_KEY}")
    assert _refused(result) and "commit-msg" in result.stderr
    assert "the commit message" in result.stderr and "VOSS_IG/api_key" in result.stderr
    assert API_KEY not in result.stdout + result.stderr
    _git(repo, "config", "core.commentChar", ";")
    (repo / "old.md").write_text(f"key was {API_KEY}\n")
    _git(repo, "add", "old.md")
    assert _git(repo, "commit", "--no-verify", "-qm", "a key, let through").returncode == 0
    (repo / "old.md").write_text("no key\n")
    _git(repo, "add", "old.md")
    taken_out = subprocess.run(["git", "commit", "-qv"], cwd=repo, capture_output=True, text=True,
                               env={**os.environ, "GIT_EDITOR": f"{sys.executable} -c \"import sys; "
                                    "p = sys.argv[1]; s = open(p).read(); "
                                    "open(p, 'w').write('the key, taken out' + chr(10) + s)\""})
    assert taken_out.returncode == 0, f"`commit -v` below the scissors was read: {taken_out.stderr}"


def test_a_value_inside_a_binary_file_is_refused(repo):
    """The archive files PDFs. A password inside one is as leaked as one in a CSV."""
    pdf = b"%PDF-1.4\n\x00\xff\xfe" + PASSWORD.encode() + b"\x00\n%%EOF"
    result = _commit(repo, "statement.pdf", pdf)
    assert _refused(result) and "VOSS_IG/password" in result.stderr


def test_the_exempt_fields_pass(repo):
    """The account number is already in the record, and a login name may also appear inside
    a /Users/ path. Refusing either would refuse ordinary commits."""
    content = f"{ACCOUNT_ID} at /Users/{IDENTIFIER}/Projects"
    assert _commit(repo, "accounts.csv", content).returncode == 0


def test_a_key_shape_is_refused_without_any_credential_file(repo):
    """A fresh clone has no credentials.json. The shapes still guard it, and it says what ran."""
    (repo / "credentials.json").unlink()
    result = _commit(repo, "config.py", f'KEY = "{ANTHROPIC_SHAPE}"')
    assert _refused(result) and "an Anthropic API key" in result.stderr
    assert "no credential files here" in result.stderr


def test_a_commit_from_a_worktree_is_checked_against_the_main_checkout(repo, tmp_path):
    """A worktree has no credentials beside it."""
    tree = tmp_path / "tree"
    assert _git(repo, "worktree", "add", "-q", str(tree), "-b", "side").returncode == 0
    result = _commit(tree, "notes.md", f"pw {PASSWORD}")
    assert _refused(result) and "VOSS_IG/password" in result.stderr


def test_history_finds_what_no_verify_let_through(repo, repo_root):
    """`--no-verify` is the one bypass, so `--history` is how to know it was never used on a
    secret. It reads every file and message, on every branch."""
    (repo / "notes.md").write_text(f"key {API_KEY}")
    _git(repo, "add", "notes.md")
    assert _git(repo, "commit", "--no-verify", "-qm", "planted").returncode == 0
    _git(repo, "commit", "--no-verify", "--allow-empty", "-qm", f"pw {PASSWORD}")
    result = subprocess.run([str(repo_root / ".githooks" / "pre-commit"), "--history"], cwd=repo,
                            capture_output=True, text=True)
    assert result.returncode == 1 and "NOT CLEAN" in result.stderr
    assert "notes.md" in result.stderr and "message" in result.stderr
    assert API_KEY not in result.stdout + result.stderr


# =====================================================================================
# PRE-PUSH: main only ever gains
# =====================================================================================

@pytest.fixture(scope="module")
def _pushed_made(tmp_path_factory, repo_root):
    """`pushed`, made once for the module: its commits and push run the hooks, which is the cost."""
    made = tmp_path_factory.mktemp("pushed")
    origin, work = made / "origin.git", made / "pushed"
    _git(made, "init", "-q", "--bare", "-b", "main", str(origin))
    work.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
                 ["config", "user.name", "t"], ["config", "core.hooksPath", str(repo_root / ".githooks")],
                 ["remote", "add", "origin", str(origin)]):
        _git(work, *args)
    for name in ("a.md", "b.md"):
        assert _commit(work, name, name).returncode == 0
    assert _push(work, "main").returncode == 0
    assert _tip(work, "origin/main") == _tip(work, "main"), "main did not reach origin"
    return made


@pytest.fixture
def pushed(_pushed_made, tmp_path):
    """A repo on the project's hooks whose `main` is on a bare `origin`, two commits deep: a copy
    of the module's, its origin with it, for each test."""
    for name in ("origin.git", "pushed"):
        shutil.copytree(_pushed_made / name, tmp_path / name, symlinks=True)
    work = tmp_path / "pushed"
    _git(work, "remote", "set-url", "origin", str(tmp_path / "origin.git"))
    return work


def _tip(work, ref):
    if ref.startswith("origin/"):
        out = _git(work, "ls-remote", "origin", f"refs/heads/{ref[7:]}").stdout.split()
        return out[0] if out else None
    return _git(work, "rev-parse", ref).stdout.strip()


def _push(work, *args, rewrite=None):
    env = {k: v for k, v in os.environ.items() if k != "MAIN_REWRITE"}
    if rewrite:
        env["MAIN_REWRITE"] = rewrite
    return subprocess.run(["git", "push", "-q", "origin", *args], cwd=work, capture_output=True,
                          text=True, env=env)


def _rewrite(work):
    """`main` moved here to a commit that does not contain the one on origin. Returns that one."""
    there = _tip(work, "main")
    _git(work, "reset", "-q", "--hard", "HEAD~1")
    _commit(work, "c.md", "c")
    assert _tip(work, "origin/main") == there
    return there


def test_a_push_that_only_adds_to_main_passes(pushed):
    _commit(pushed, "c.md", "c")
    assert _push(pushed, "main").returncode == 0
    assert _tip(pushed, "origin/main") == _tip(pushed, "main")


def test_a_force_push_that_rewrites_main_is_refused(pushed):
    there = _rewrite(pushed)
    result = _push(pushed, "--force", "main")
    assert _refused(result) and "rewrites main" in result.stderr
    assert f"MAIN_REWRITE={there[:12]}" in result.stderr, "the refusal names the override"
    assert _tip(pushed, "origin/main") == there


@pytest.mark.parametrize("args", [("--delete", "main"), (":main",), ("-d", "main")])
def test_deleting_main_is_refused_however_it_is_spelt(pushed, args):
    there = _tip(pushed, "origin/main")
    result = _push(pushed, *args)
    assert _refused(result) and "deletes main" in result.stderr
    assert _tip(pushed, "origin/main") == there


def test_the_override_approves_only_the_rewrite_it_names(pushed):
    """An approval names the commit it overwrites, so it cannot be carried to the next one."""
    there = _rewrite(pushed)
    assert _refused(_push(pushed, "--force", "main", rewrite="0123456789ab"))
    assert _refused(_push(pushed, "--force", "main", rewrite=there[:6])), "too short to name one"
    assert _push(pushed, "--force", "main", rewrite=there[:7]).returncode == 0
    assert _tip(pushed, "origin/main") == _tip(pushed, "main")


def test_every_other_branch_is_free(pushed):
    """A session's branch is its own, and a merged branch is deleted from GitHub."""
    _git(pushed, "switch", "-q", "-c", "side")
    _commit(pushed, "c.md", "c")
    _git(pushed, "reset", "-q", "--hard", "HEAD~1")
    assert _push(pushed, "--force", "side").returncode == 0
    assert _push(pushed, "--delete", "side").returncode == 0


def test_a_main_moved_on_github_and_not_fetched_is_never_overwritten(pushed, tmp_path):
    """A merge made on GitHub that this checkout has not pulled: what a push would overwrite has
    not been seen here, so not even the override lets it through."""
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(other))
    for args in (["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        _git(other, *args)
    _commit(other, "merged.md", "made on GitHub")
    _git(other, "push", "-q", "origin", "main")
    there = _tip(pushed, "origin/main")
    _commit(pushed, "c.md", "c")
    result = _push(pushed, "--force", "main", rewrite=there[:12])
    assert _refused(result) and "has not fetched" in result.stderr and "git pull" in result.stderr
    assert "MAIN_REWRITE=" not in result.stderr
    assert _tip(pushed, "origin/main") == there


# =====================================================================================
# PRE-PUSH, from a checkout: what is pushed names nothing of the named book
# =====================================================================================

def _checkout(tmp_path, passes):
    """A stand-in checkout whose leak test passes or fails."""
    from portfusion.hooks.pre_push import LEAKS
    test = tmp_path / "checkout" / LEAKS
    test.parent.mkdir(parents=True)
    test.write_text(f"def test_it():\n    assert {passes}\n")
    return tmp_path / "checkout"


@pytest.mark.parametrize("passes, status", [(True, 0), (False, 1)])
def test_a_checkouts_push_is_refused_when_it_names_the_book(tmp_path, monkeypatch, passes, status):
    from portfusion.hooks.pre_push import what_leaves
    monkeypatch.setenv("PORTFUSION_BOOK", str(tmp_path / "book"))
    assert what_leaves(_checkout(tmp_path, passes)) == status


def test_with_no_book_named_the_push_is_refused_and_says_how_to_name_one(tmp_path, monkeypatch,
                                                                         capfd):
    """A push that checks nothing for a book's names is a choice, made by naming the demo."""
    from portfusion.hooks.pre_push import what_leaves
    monkeypatch.delenv("PORTFUSION_BOOK", raising=False)
    assert what_leaves(_checkout(tmp_path, True)) == 1
    said = "".join(capfd.readouterr())
    assert "names no book" in said and "PORTFUSION_BOOK=demo" in said


def test_the_suites_commits_are_never_signed(tmp_path):
    """NO COMMIT THE SUITE MAKES IS SIGNED: a fresh repository, asked, says so, whatever this
    machine's own git config would have it do (`harness.UNSIGNED`)."""
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    said = subprocess.run(["git", "-C", str(tmp_path), "config", "--get", "commit.gpgsign"],
                          capture_output=True, text=True).stdout.strip()
    assert said == "false", f"git in the suite would sign: commit.gpgsign is {said!r}"
