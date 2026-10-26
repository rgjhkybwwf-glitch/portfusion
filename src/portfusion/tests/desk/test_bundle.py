"""THE SHELL'S FILES — one set, served by the Mac desk and published for the hosted one.

`desk/bundle.py` says what the set is. These hold that the Mac desk serves exactly those bytes,
that the set is reproducible, and that nothing in it is a fact from the record.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from portfusion.desk import app, bundle


@pytest.fixture(scope="module")
def files():
    return bundle.files()


def test_the_hosted_bundle_is_the_bytes_the_mac_desk_serves(files):
    """ONE SOURCE, TWO SERVERS. Every file the publish step writes out is requested from the Mac
    desk over HTTP and must come back byte for byte, with the headers the hosted desk sends it
    (`bundle.SHELL_HEADERS`). A route that served something of its own would be a second shell,
    and the two desks would drift apart unseen."""
    client = TestClient(app.app, base_url="http://127.0.0.1:8765")
    for path, body in files.items():
        r = client.get(path)
        assert r.status_code == 200, f"{path} is in the bundle and the desk does not serve it"
        assert r.content == body, f"{path}: the desk serves different bytes from the bundle"
        assert {k: r.headers.get(k) for k in bundle.SHELL_HEADERS} == bundle.SHELL_HEADERS, path


def test_the_bundle_is_built_the_same_twice(files):
    """Reproducible, or the version would move with nothing changed and the hosted page would
    call itself behind a Mac it matches."""
    assert bundle.files() == files
    assert bundle.version() == bundle.version()


def test_the_bundle_is_the_shell_and_nothing_else(files):
    """THE ALLOWLIST. The page, its stylesheet and scripts from desk/static/, the generated
    stylesheet and tab icon, the three app icons copied from the website, the manifest that names
    them, and the typefaces the stylesheet declares. A new kind of file joins by being named in
    `bundle.paths()` — and must then pass the scan below."""
    fonts = {p for p in files if p.startswith("/fonts/")}
    assert fonts and all(re.fullmatch(r"/fonts/[a-z0-9-]+\.woff2", p) for p in fonts)
    scripts = {f"/static/{n}" for n in ("core.js", "kit.js", "reading.js", "access.js", "bench.js",
                                        "sweep.js", "price-refresh.js", "app.js")}
    assert set(files) - fonts == {"/", "/static/app.css", *scripts, "/tokens.css", "/favicon.png",
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


def test_the_bundle_carries_nothing_from_the_record(files):
    """THE HOSTED COPY IS PUBLIC UP TO ITS SIGN-IN, so the shell may carry labels and layout
    and nothing of the book. `desk/publish.py` runs this scan before every publish and refuses
    on a hit; here it runs on every change, so a hit is found before anyone publishes."""
    from portfusion.record import schema
    from portfusion.desk import publish

    # THE SCAN MUST AT LEAST LOOK FOR THE WHOLE REGISTER — every account and every security
    # the loaded book names; a count floor says nothing on a smaller book.
    def column(table, name):
        at = schema.TABLES[table].header.index(name)
        return {str(r[at]).strip() for r in schema.load(table) if str(r[at]).strip()}

    values = publish.record_values()
    assert column("accounts", "account") <= values, "an account name is not being scanned for"
    assert column("securities", "ticker") <= values, "a security code is not being scanned for"
    assert publish.leaks(files) == []


def test_every_stamp_is_the_content_of_the_file_it_links(files):
    """A CHANGED FILE GETS A CHANGED URL. The stamp is the start of the file's own hash, so a
    browser holding an older app.js is handed a URL it has never fetched. The scripts are linked
    in SCRIPTS' order, which is the order they load in."""
    import hashlib
    page = files["/"].decode()
    scripts = [f"/static/{n}" for n in bundle.SCRIPTS]
    assert re.findall(r'<script src="([^"?]+)', page) == scripts
    for url in ("/static/app.css", *scripts, "/tokens.css"):
        stamp = hashlib.sha256(files[url]).hexdigest()[:12]
        assert f'"{url}?v={stamp}"' in page, f"{url} is not linked by its content"


def test_the_page_names_its_own_version(files):
    """The hosted page reads this before drawing anything and compares it with the Mac's."""
    page = files["/"].decode()
    assert f'<meta name="desk-version" content="{bundle.version()}">' in page
    assert 'content=""' not in page, "the version placeholder was served as it stands"


def test_a_short_ticker_is_not_a_leak_of_the_shells_own_words(files, monkeypatch):
    """A TICKER THAT IS AN ORDINARY WORD — `A`, `T`, `ON`, `ALL`, `NOW`, `KEY` — would match the
    shell's own comments and prose, so a book holding one could never publish. Three characters
    or fewer are looked for outside comments, one not at all."""
    from portfusion.desk import publish
    monkeypatch.setattr(publish, "record_values",
                        lambda: {"A", "T", "ON", "ALL", "NOW", "KEY", "IT", "AND", "OR"})
    assert publish.leaks(files) == []


def test_a_comment_is_still_published_and_still_scanned(monkeypatch):
    """THE SHELL IS SERVED WHOLE, COMMENTS AND ALL, before the sign-in: a holder or a longer
    ticker named in a comment is a leak, and a short one in the code is too."""
    from portfusion.desk import publish
    monkeypatch.setattr(publish, "record_values", lambda: {"Jane Holder", "ZZTOP", "QQ"})
    tree = {"/static/app.js": b"/* priced for Jane Holder */ const x = 'ZZTOP';\n// QQ\nlet q = 1;",
            "/static/app.css": b"/* QQ */ .QQ { }"}
    said = publish.leaks(tree)
    assert any("'Jane Holder'" in s for s in said) and any("'ZZTOP'" in s for s in said), said
    assert [s for s in said if "'QQ'" in s] == [], said
    tree["/static/app.js"] += b" const QQ = 2;"
    assert any("app.js names 'QQ'" in s for s in publish.leaks(tree))
