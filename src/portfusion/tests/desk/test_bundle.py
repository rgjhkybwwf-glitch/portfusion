"""THE SHELL'S FILES — one set, served by the desk.

`desk/bundle.py` says what the set is. These hold that the desk serves exactly those bytes, and
that the set is reproducible.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from portfusion.desk import app, bundle


@pytest.fixture(scope="module")
def files():
    return bundle.files()


def test_the_desk_serves_the_bundle_byte_for_byte(files):
    """ONE SOURCE. Every file of the bundle is requested from the desk over HTTP and must come back
    byte for byte, with `bundle.SHELL_HEADERS`. A route that served something of its own would be
    a second shell, drifting from this one unseen."""
    client = TestClient(app.app, base_url="http://127.0.0.1:8765")
    for path, body in files.items():
        r = client.get(path)
        assert r.status_code == 200, f"{path} is in the bundle and the desk does not serve it"
        assert r.content == body, f"{path}: the desk serves different bytes from the bundle"
        assert {k: r.headers.get(k) for k in bundle.SHELL_HEADERS} == bundle.SHELL_HEADERS, path


def test_the_bundle_is_built_the_same_twice(files):
    """Reproducible, or a stamp would move with nothing changed and a browser would fetch again
    what it already holds."""
    assert bundle.files() == files


def test_the_bundle_is_the_shell_and_nothing_else(files):
    """THE ALLOWLIST. The page, its stylesheet and scripts from desk/static/, the generated
    stylesheet and tab icon, the three app icons copied from the website, the manifest that names
    them, and the typefaces the stylesheet declares. A new kind of file joins by being named in
    `bundle.paths()`."""
    fonts = {p for p in files if p.startswith("/fonts/")}
    assert fonts and all(re.fullmatch(r"/fonts/[a-z0-9-]+\.woff2", p) for p in fonts)
    scripts = {f"/static/{n}" for n in ("core.js", "kit.js", "what-changed.js", "dashboard.js",
                                        "holdings.js", "round-trips.js", "method.js", "accounts.js",
                                        "reports.js", "performance.js", "trades.js", "reconcile.js",
                                        "bench.js", "sweep.js", "price-refresh.js", "app.js")}
    styles = {f"/static/{n}" for n in ("kit.css", "tables.css", "pages.css", "bench.css", "phone.css")}
    assert set(files) - fonts == {"/", *styles, *scripts, "/tokens.css", "/favicon.png",
                                  "/apple-touch-icon.png", "/icon-192.png", "/icon-512.png",
                                  "/manifest.webmanifest"}


def test_a_path_outside_the_shell_is_not_served():
    """`bundle.asset()` is the containment rule. The raw template is not part of the shell
    either: it is served only as the page it becomes."""
    from fastapi import HTTPException
    for bad in ("/static/index.html", "/static/../app.py", "/fonts/../palette.py",
                "/credentials.json"):
        with pytest.raises(KeyError):
            bundle.asset(bad)
    with pytest.raises(HTTPException):
        app.static("index.html")


def test_every_stamp_is_the_content_of_the_file_it_links(files):
    """A CHANGED FILE GETS A CHANGED URL. The stamp is the start of the file's own hash, so a
    browser holding an older app.js is handed a URL it has never fetched. The scripts are linked
    in SCRIPTS' order, which is the order they load in."""
    import hashlib
    page = files["/"].decode()
    scripts = [f"/static/{n}" for n in bundle.SCRIPTS]
    styles = [f"/static/{n}" for n in bundle.STYLES]
    assert re.findall(r'<script src="([^"?]+)', page) == scripts
    assert re.findall(r'<link rel="stylesheet" href="(/static/[^"?]+)', page) == styles
    for url in (*styles, *scripts, "/tokens.css"):
        stamp = hashlib.sha256(files[url]).hexdigest()[:12]
        assert f'"{url}?v={stamp}"' in page, f"{url} is not linked by its content"
