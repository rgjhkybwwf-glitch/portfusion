"""PUBLISHING THE HOSTED DESK — into a deploy repository of the test's own.

Every test here publishes into a bare repository and clone made in a temporary folder, with a
made-up tunnel and a made-up source commit. Nothing reaches GitHub, Netlify or the real clone.
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from portfusion.desk import auth, bundle, publish
from harness import needs

TUNNEL = "https://mac.example.ts.net"
SOURCE = "a" * 40


def _git(where, *args):
    return subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


@pytest.fixture(autouse=True)
def git_identity(monkeypatch):
    """Who the test repositories' commits are by. A publish commits, and without this the commit
    takes the machine's own identity: a GitHub runner has none, and every publish failed there."""
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.invalid")


@pytest.fixture(autouse=True)
def proxy_secret(tmp_path, monkeypatch):
    """A proxy secret of the test's own, which a publish requires; never the Mac's."""
    path = tmp_path / "proxy_secret.json"
    path.write_text(json.dumps({"secret": "a-test-secret"}))
    monkeypatch.setattr(auth, "PROXY_SECRET", path)
    return path


@pytest.fixture()
def deploy(tmp_path):
    """An empty deploy repository, as `gh repo create` leaves one, and its clone."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(tmp_path / "clone")], check=True,
                   capture_output=True)
    return tmp_path / "clone", origin


def test_publish_only_ever_pushes_main_of_the_deploy_repo(deploy):
    clone, origin = deploy
    got = publish.publish(deploy=clone, tunnel=TUNNEL, commit=SOURCE)
    assert got["published"] and got["version"] == bundle.version() and got["this_month"] == 1
    assert _git(origin, "for-each-ref", "--format=%(refname)") == "refs/heads/main"
    assert subprocess.run(["git", "-C", str(origin), "show", "main:bundle/index.html"],
                          capture_output=True, check=True).stdout == bundle.files()["/"]
    m = json.loads(_git(origin, "show", "main:version.json"))
    assert m["version"] == bundle.version() and m["source"] == SOURCE
    assert f"PortFusion@{SOURCE[:7]}" in _git(origin, "log", "-1", "--format=%s", "main")


def test_every_file_in_the_deploy_repository_is_generated(deploy):
    """The manifest covers everything but itself, and verify.py — Netlify's build — passes
    what the publish wrote and refuses a hand edit."""
    clone, _ = deploy
    publish.publish(deploy=clone, tunnel=TUNNEL, commit=SOURCE)
    listed = set(_git(clone, "ls-files").split("\n")) - {"version.json"}
    assert listed == set(json.loads((clone / "version.json").read_text())["files"])
    verify = [sys.executable, str(clone / "verify.py")]
    assert subprocess.run(verify, capture_output=True).returncode == 0
    (clone / "bundle" / "static" / "app.css").write_text("/* edited here */")
    r = subprocess.run(verify, capture_output=True, text=True)
    assert r.returncode == 1 and "bundle/static/app.css" in r.stdout


def test_nothing_is_published_when_nothing_moved(deploy):
    clone, origin = deploy
    publish.publish(deploy=clone, tunnel=TUNNEL, commit=SOURCE)
    again = publish.publish(deploy=clone, tunnel=TUNNEL, commit="b" * 40)
    assert again["published"] is False
    assert _git(origin, "rev-list", "--count", "main") == "1"


def test_the_redirects_send_the_api_and_the_sign_in_to_the_tunnel_signed():
    """Netlify signs only a redirect written in netlify.toml, so the two proxies live there, each
    naming the environment variable the door's secret is held in, and there is no _redirects
    for an unsigned rule to hide in."""
    tree = publish.files(TUNNEL)
    assert "bundle/_redirects" not in tree
    rules = tree["netlify.toml"].decode().split("[[redirects]]")[1:]
    assert len(rules) == 2
    for path, rule in zip(("api", "auth"), rules):
        lines = [line.strip() for line in rule.strip().splitlines()]
        assert lines == [f'from = "/{path}/*"', f'to = "{TUNNEL}/{path}/:splat"', "status = 200",
                         f'signed = "{auth.PROXY_SECRET_ENV}"']
    headers = publish.files(TUNNEL)["bundle/_headers"].decode()
    assert "frame-ancestors 'none'" in headers and "X-Robots-Tag: noindex" in headers


def test_a_crawler_may_read_the_noindex_and_never_reach_the_tunnel():
    """robots.txt blocked everything until 7 Oct 2026, which hid the noindex on every response
    from every crawler that obeys it: a crawler reads a rule only on a page it may fetch. It now
    keeps crawlers off /api and /auth, the tunnel to the Mac, and nothing else; the noindex
    header keeps the shell out of search."""
    robots = publish.files(TUNNEL)["bundle/robots.txt"].decode().splitlines()
    assert robots == ["User-agent: *", "Disallow: /api/", "Disallow: /auth/"]
    headers = publish.files(TUNNEL)["bundle/_headers"].decode()
    assert "X-Robots-Tag: noindex" in headers.split("\n/\n")[0], \
        "the noindex must cover every path, /*, or allowing the crawl lets the shell be indexed"


def test_netlify_serves_the_manifest_as_a_manifest():
    """`_HEADERS` says why the hosted copy names the manifest's type; the Mac's comes from
    `app.MEDIA`. This holds the hosted one to it."""
    headers = publish.files(TUNNEL)["bundle/_headers"].decode()
    assert "/manifest.webmanifest\n  Content-Type: application/manifest+json\n" in headers


def test_netlifys_build_is_the_tamper_check():
    """T step 4's one finding (9 Oct 2026): `verify.py` refuses a hand edit in the deploy
    repository ONLY because Netlify runs it, and that wiring is one generated line in
    netlify.toml that nothing held — every other test here exercises verify.py directly,
    which proves the gate works, not that it is on the gate."""
    toml = publish.files(TUNNEL)["netlify.toml"].decode()
    assert 'command = "python3 verify.py"' in toml, \
        "the deploy's build no longer runs the tamper check"


def test_publish_refuses_rather_than_guessing(deploy, monkeypatch):
    clone, origin = deploy
    monkeypatch.setattr(publish, "tunnel_url", lambda port: None)
    with pytest.raises(publish.Refused, match="tunnel is off"):
        publish.publish(deploy=clone, commit=SOURCE)
    with pytest.raises(publish.Refused, match="no clone"):
        publish.publish(deploy=clone.parent / "nowhere", tunnel=TUNNEL, commit=SOURCE)
    monkeypatch.setattr(publish, "DEPLOY", None)          # a book that names no deploy_repo
    with pytest.raises(publish.Refused, match="no deploy_repo"):
        publish.publish(tunnel=TUNNEL, commit=SOURCE)
    assert publish.published() is None
    _git(clone, "switch", "-q", "-c", "other")
    with pytest.raises(publish.Refused, match="not main"):
        publish.publish(deploy=clone, tunnel=TUNNEL, commit=SOURCE)
    assert _git(origin, "for-each-ref") == "", "a refused publish pushed something"


@needs("accounts")
def test_a_value_from_the_record_stops_the_publish(deploy, monkeypatch):
    clone, origin = deploy
    holder = sorted(publish.record_values())[0]
    real = bundle.files()
    monkeypatch.setattr(bundle, "files", lambda: {**real, "/static/app.js":
                                                  real["/static/app.js"] + f"/* {holder} */".encode()})
    with pytest.raises(publish.Refused, match="must not"):
        publish.publish(deploy=clone, tunnel=TUNNEL, commit=SOURCE)
    assert _git(origin, "for-each-ref") == ""


def test_only_a_clean_pushed_main_is_published(tmp_path):
    origin, work = tmp_path / "o.git", tmp_path / "w"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True,
                   capture_output=True)
    (work / "f").write_text("1")
    _git(work, "add", "f")
    _git(work, "commit", "-q", "-m", "one")
    with pytest.raises(publish.Refused, match="not pushed"):
        publish.source(work)
    _git(work, "push", "-q", "origin", "main")
    assert publish.source(work) == _git(work, "rev-parse", "HEAD")
    (work / "f").write_text("2")
    with pytest.raises(publish.Refused, match="uncommitted"):
        publish.source(work)
    _git(work, "checkout", "-q", "--", "f")
    _git(work, "switch", "-q", "-c", "branch")
    with pytest.raises(publish.Refused, match="not main"):
        publish.source(work)


#: `tailscale funnel status --json` for a Mac whose port 8768 is published on 443.
FUNNEL = {"TCP": {"443": {"HTTPS": True}},
          "Web": {"mac.example.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8768"}}}},
          "AllowFunnel": {"mac.example.ts.net:443": True}}


def test_the_tunnel_is_read_from_tailscales_own_configuration():
    assert publish.tunnel_url(8768, FUNNEL) == "https://mac.example.ts.net"
    assert publish.tunnel_url(8769, FUNNEL) is None, "another port's tunnel was taken for this one"
    shut = dict(FUNNEL, AllowFunnel={})
    assert publish.tunnel_url(8768, shut) is None, "a tailnet-only serve was taken for a funnel"
    other = {"Web": {"mac.example.ts.net:8443": FUNNEL["Web"]["mac.example.ts.net:443"]},
             "AllowFunnel": {"mac.example.ts.net:8443": True}}
    assert publish.tunnel_url(8768, other) == "https://mac.example.ts.net:8443"
    assert publish.tunnel_url(8768, {}) is None


def test_the_header_reads_the_hosted_desk_locally(deploy, monkeypatch):
    """No remote door, no signal. With one, `publish.status()` reads the clone and the local
    daemon, never the network."""
    from portfusion.desk import remote
    clone, _ = deploy
    monkeypatch.setattr(remote, "PORT", None)
    assert publish.status() is None
    monkeypatch.setattr(remote, "PORT", 8768)
    monkeypatch.setattr(publish, "DEPLOY", clone)
    monkeypatch.setattr(publish, "tunnel_url", lambda port: TUNNEL)
    monkeypatch.setitem(publish._tunnel_seen, "at", 0.0)
    assert publish.status() == {"tunnel": True, "published": None, "current": bundle.version()}
    publish.publish(deploy=clone, tunnel=TUNNEL, commit=SOURCE)
    assert publish.status()["published"] == bundle.version()


def test_a_publish_is_refused_while_the_mac_holds_no_proxy_secret(deploy, proxy_secret):
    """The redirects ask Netlify to sign, and a door with no secret refuses every request it
    signs, so publishing then would shut the hosted desk. Nothing is written or pushed."""
    clone, origin = deploy
    proxy_secret.unlink()
    with pytest.raises(publish.Refused, match="no proxy secret"):
        publish.publish(deploy=clone, tunnel=TUNNEL, commit=SOURCE)
    assert not (clone / "version.json").exists()


def test_a_publish_needs_no_web_framework(tmp_path):
    """`portfusion desk --publish` ran from a terminal without the project's venv until 16 Oct
    2026, when asking for the proxy secret loaded the remote door and with it FastAPI. The
    secret lives in `desk/auth.py` so it does not: here the publish module is imported, and the
    tree built and checked for the secret, with FastAPI and uvicorn made unimportable."""
    script = tmp_path / "no_web.py"
    script.write_text(
        "import sys\n"
        "for name in ('fastapi', 'starlette', 'uvicorn'):\n"
        "    sys.modules[name] = None\n"
        "from portfusion.desk import auth, publish\n"
        f"publish.files({TUNNEL!r})\n"
        "auth.proxy_secret()\n"
        "print('ok')\n")
    from portfusion.record import schema
    r = subprocess.run([sys.executable, str(script)], cwd=schema.ROOT, capture_output=True,
                       text=True)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr


def test_a_tunnel_daemon_that_does_not_answer_is_no_tunnel(monkeypatch):
    """`tailscale funnel status` timing out raised through the publish as a traceback; a daemon
    that does not answer is a tunnel that is not there (the review of 21 Oct 2026)."""
    import subprocess
    from portfusion.desk import publish
    monkeypatch.setattr(publish.shutil, "which", lambda name: "/usr/bin/true")

    def hangs(*a, **k):
        raise subprocess.TimeoutExpired(a[0], 5)
    monkeypatch.setattr(publish.subprocess, "run", hangs)
    assert publish.tunnel_url(8768) is None
