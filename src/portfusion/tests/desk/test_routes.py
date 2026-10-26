"""THE ROUTES — the functions behind them, and the same routes requested over HTTP."""
from __future__ import annotations

import re
import pytest
from portfusion.desk import actions, app, panels, engine
from fastapi.testclient import TestClient
from harness import SRC, desk_script


# =====================================================================================
# The routes.
# =====================================================================================

def test_the_shell_lists_what_is_registered_and_nothing_else():
    s = app.state()
    assert [p["name"] for p in s["panels"]] == [m.NAME for m in panels.all_panels()]
    assert [a["name"] for a in s["actions"]] == [a.name for a in actions.all_actions()]


def test_static_refuses_a_path_that_leaves_the_directory():
    """`../app.py` IS THERE: the desk's own source, beside the folder. Every other probe named a
    file that does not exist, so a route serving whatever it reached would have passed on a
    not-found."""
    from fastapi import HTTPException
    assert (SRC / "desk" / "app.py").is_file(), "the premise: the probe's target exists"
    for bad in ("../app.py", "../credentials.json", "../../etc/passwd", "..%2fcredentials.json"):
        with pytest.raises(HTTPException):
            app.static(bad)


def test_every_typeface_the_tokens_declare_is_served():
    """A FACE THAT DOES NOT LOAD FALLS BACK SILENTLY to the next one in its stack, so the desk
    would render in the system font with nothing to say so. Each file /tokens.css names must
    come back from /fonts, and nothing else may: the route serves house/fonts/ and no further."""
    import re
    from fastapi import HTTPException
    named = set(re.findall(r"url\('/fonts/([^']+)'\)", app.tokens().body.decode()))
    assert named, "tokens.css declares no typeface"
    for name in sorted(named):
        assert app.fonts(name).status_code == 200, f"/fonts/{name} is declared and not served"
    for bad in ("../palette.py", "../../credentials.json", "../mark.py", "..%2fpalette.py"):
        with pytest.raises(HTTPException):
            app.fonts(bad)


def test_tokens_are_derived_from_the_palette_not_written_here():
    """A colour changed in house/palette.py must reach the desk: hardcoded in each consumer, one
    colour breaks in each, some silently."""
    css = app.tokens().body.decode()
    for key, value in engine.palette().items():
        assert value in css, f"{key} did not reach tokens.css"


def test_there_is_exactly_one_palette_derivation():
    """ONE ROUTE TO THE COLOURS: two routes to one answer drift.

    engine.py stays the one way the desk reads; theme.py holds the derivation; app.py serves what
    engine hands it (the `one-palette` import contract).
    """
    from portfusion.desk import theme
    assert engine.palette() == theme.palette()
    assert engine.tokens_css() == theme.tokens_css()


def test_every_token_the_desk_is_handed_is_worn(repo_root):
    """A TOKEN NOBODY CONSUMES is a palette entry pretending to be a treatment. The icon wears its
    own through `desk.icon.ROLES`, and the served shell wears the mark's two in the book's lockup,
    so both count as a use."""
    import re
    from portfusion.desk import icon
    used = ((SRC / "desk" / "static" / "app.css").read_text(encoding="utf-8")
            + app.index().body.decode())
    declared = set(re.findall(r"--([a-z-]+):", app.tokens().body.decode()))
    unworn = sorted(t for t in declared
                    if f"var(--{t})" not in used and t not in icon.ROLES.values())
    assert not unworn, f"tokens.css declares {unworn} and nothing on the desk wears them"


def test_every_token_the_desk_wears_is_handed_to_it(repo_root):
    """THE OTHER DIRECTION: a var() naming a token nobody declares draws in the property's default,
    with nothing on screen saying so. Every var(--x) in app.css is a token /tokens.css declares or
    one app.css sets itself."""
    import re
    css = (SRC / "desk" / "static" / "app.css").read_text(encoding="utf-8")
    declared = (set(re.findall(r"--([a-z0-9-]+):", app.tokens().body.decode()))
                | set(re.findall(r"--([a-z0-9-]+):", css)))
    unhanded = sorted(set(re.findall(r"var\(--([a-z0-9-]+)", css)) - declared)
    assert not unhanded, f"app.css wears {unhanded}, which nothing declares"


def test_the_desk_wears_the_books_lockup():
    """THE HEADER'S LOCKUP, THE TITLE AND THE FOOTER ARE FILLED IN AT SERVE TIME from
    `portfusion.brand`, so a placeholder that stopped matching would leave the header with no
    name at all, and quietly. Each must arrive whole, and nothing of a placeholder left."""
    from portfusion import brand
    shell = app.index().body.decode()
    assert brand.lockup() in shell, "the header has no lockup"
    for placeholder in ("<!-- lockup -->", "<!-- title -->", "<!-- footer -->"):
        assert placeholder not in shell, f"{placeholder} was served as it stands"


def test_every_state_colour_reaches_the_stylesheet():
    """The colours that carry MEANING — a warning, a row that differs, and the four states — must
    reach the stylesheet. A renderer missing one of them is a renderer that cannot say what state
    a figure is in. A tag's state is drawn as a coloured point in one of the four key colours."""
    css = app.tokens().body.decode()
    for token in ("warn", "band",
                  "key-problem", "key-gap", "key-note", "key-clear"):
        assert f"--{token}:" in css, f"{token} did not reach tokens.css"


def test_the_freshness_line_says_what_can_be_out_of_date():
    """THE DESK'S STATUS BAR: the store, the code, the marks and the hosted desk, each with the
    thing that moves it beside it.

    An exact set rather than a subset: a key that arrives without anyone deciding to add it is
    the drift this assertion exists to catch.

    The CODE signal — the `source_*` keys, `engine.source_stale()`, tested in test_process.py —
    is there because a long-running server can serve an old engine behind a current page while
    this line says everything is fine. `prices_as_at` is Book.valued_at(), the newest
    mark, the same answer the Dashboard heads its glance with; it sits on this line because the
    refresh is started from here.
    """
    f = engine.freshness()
    assert set(f) == {"store_changed", "source_stale", "source_changed", "source_files",
                      "source_count", "prices_as_at", "hosted"}
    assert isinstance(f["source_stale"], bool)
    from portfusion.house.precision import day
    assert f["prices_as_at"] == day(engine.book().valued_at()), \
        "the header's price date is not the engine's — every renderer shares this one"


# =====================================================================================
# OVER HTTP
# =====================================================================================

# THE DESK OVER HTTP — every route, requested the way the browser requests it.
#
# The rest of the desk's suite calls panels, the bench and the doors as functions. That proves
# what each one decides; it cannot prove the decision reaches the browser as the status code the
# page acts on.
#
# NOTHING HERE WRITES. Every request is a read, or a refusal its door makes before a file is
# touched. The writing paths are proved against a copied store elsewhere in tests/desk/.

#: Well formed, so it passes bench._path(), and dated in 2099, so no real item has it.
ABSENT = "B-20990101-abcdef"


#: Where the browser finds the desk. The desk answers to its loopback names only, and
#: TestClient's own default host is not one of them.
DESK = "http://127.0.0.1:8765"


@pytest.fixture(scope="module")
def client():
    return TestClient(app.app, base_url=DESK)


def test_a_write_from_another_page_is_refused(client):
    """ANY PAGE IN THE SAME BROWSER CAN SEND TO 127.0.0.1. A write naming another origin is
    refused before any route runs. The item is ABSENT, so a check that failed would reach a 404
    and still write nothing; a 403 is the check itself answering."""
    url = f"/api/bench/{ABSENT}/commit"
    for origin in ("https://example.com", "null", "http://127.0.0.1:9999"):
        r = client.post(url, headers={"Origin": origin})
        assert r.status_code == 403, f"a write from {origin} reached the route"
    assert client.post(url, headers={"Origin": DESK}).status_code == 404, \
        "the desk's own page was refused"
    assert client.post(url).status_code == 404, "a script on this Mac (no Origin) was refused"


def test_a_request_for_another_host_is_refused(client):
    """DNS REBINDING, which `app.own_page_only()` explains. Any name but the loopback ones is
    refused, reads included."""
    assert client.get("/api/health", headers={"Host": "evil.example:8765"}).status_code == 403
    assert client.get("/api/health", headers={"Host": "localhost:8765"}).status_code == 200


def test_the_page_and_the_health_line_answer(client):
    assert client.get("/").status_code == 200
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["desk"] is True


def test_the_state_lists_exactly_the_registered_panels(client):
    listed = [p["name"] for p in client.get("/api/state").json()["panels"]]
    assert listed == [m.NAME for m in panels.all_panels()]


@pytest.mark.parametrize("name", [m.NAME for m in panels.all_panels()])
def test_every_panel_is_served(client, name):
    r = client.get(f"/api/panel/{name}")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == name


@pytest.mark.parametrize("url", ["/api/holdings?by=ticker", "/api/round-trips", "/api/trades"])
def test_the_query_routes_answer(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    assert "rows" in r.json()


def test_a_grouping_the_engine_refuses_is_a_400_carrying_its_reason(client):
    for url in ("/api/holdings?by=nonsense", "/api/round-trips?view=nonsense"):
        r = client.get(url)
        assert r.status_code == 400, url
        assert "nonsense" in r.json()["detail"], url


def test_round_trips_reads_by_company_life(client):
    """The life view: the engine's lives and their totals, narrowed by company and close only."""
    r = client.get("/api/round-trips?view=life").json()
    assert r["view"] == "life" and r["columns"] and "account" not in r["columns"]
    assert r["totals"]["lives"] == len(r["rows"])


@pytest.mark.parametrize("method, url", [
    ("GET", "/api/panel/nope"),
    ("GET", f"/api/bench/{ABSENT}"),
    ("PUT", f"/api/bench/{ABSENT}"),
    ("POST", f"/api/bench/{ABSENT}/commit"),
    ("DELETE", f"/api/bench/{ABSENT}"),
    ("GET", "/api/document/not-here.pdf"),
    ("GET", "/api/document/not-here.pdf/raw"),
    ("POST", "/api/action/nope"),
])
def test_what_is_not_there_is_a_404(client, method, url):
    r = client.request(method, url, json={} if method in ("PUT", "POST") else None)
    assert r.status_code == 404, f"{method} {url} -> {r.status_code} {r.text[:120]}"


@pytest.mark.parametrize("url", ["/api/document/..%2Fengine.py/raw", "/static/..%2Fapp.py"])
def test_a_path_that_leaves_its_folder_is_not_served(client, url):
    assert client.get(url).status_code == 404


def test_a_withdrawal_the_door_refuses_reaches_the_browser_as_a_409(client):
    """The Withdraw button alerts `detail` on any status that is not ok. This is the server
    half of that: the door's own sentence arrives intact."""
    r = client.delete("/api/inbox/not-on-the-workbench.pdf")
    assert r.status_code == 409
    assert "not on the workbench" in r.json()["detail"]


@pytest.mark.parametrize("name, body, says", [
    (".hidden.pdf", b"x", "starts with a dot"),
    ("tool.exe", b"x", "the workbench takes"),
    ("empty.pdf", b"", "arrived empty"),
])
def test_a_drop_the_door_refuses_is_a_400_and_lands_nothing(client, name, body, says):
    # THE WORKBENCH THE DOOR WRITES TO, the loaded book's, which need not exist yet.
    from portfusion.record import schema
    inbox = schema.inbox()

    def held():
        return sorted(p.name for p in inbox.iterdir()) if inbox.is_dir() else None
    before = held()
    r = client.post(f"/api/inbox?name={name}", content=body)
    assert r.status_code == 400 and says in r.json()["detail"]
    assert held() == before


# =====================================================================================
# THE ICON — the page declares it, and the route returns a real PNG
# =====================================================================================

def test_the_favicon_route_returns_a_real_png():
    """A LOAD-BEARING ROUTE. The page names it as the tab's icon, so a break in it degrades to a
    generic icon SILENTLY, which is exactly the failure this project guards against everywhere
    else.

    Checked as bytes rather than by calling desk.icon.png() directly: the route is the thing
    that has to work, and asserting on the drawing function would pass with the route broken.

    IT READS THE PIXELS, and that is the point. A size threshold looks like a check — a blank
    square should be smaller — and is not: flat shapes compress hard. A SIZE THRESHOLD CANNOT SEE
    WHETHER ANYTHING WAS DRAWN. A mark at 64px is a few pixels of stroke on a tile, the likeliest
    thing to be lost.
    """
    import struct
    import zlib

    from portfusion.desk import icon

    body = app.favicon().body
    assert body[:8] == b"\x89PNG\r\n\x1a\n", "the favicon route is not returning a PNG"

    width, height = struct.unpack(">II", body[16:24])
    assert width == height == 64, f"the favicon is {width}x{height}, not 64x64"

    # Walk the chunks for the image data rather than assuming an offset.
    pos, idat = 8, b""
    while pos < len(body):
        length, tag = struct.unpack(">I", body[pos:pos + 4])[0], body[pos + 4:pos + 8]
        if tag == b"IDAT":
            idat += body[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)

    # Filter byte per scanline, then RGBA. This writer uses filter 0 (None) throughout.
    stride = width * 4 + 1
    seen = set()
    for y in range(height):
        row = raw[y * stride + 1:(y + 1) * stride]
        for x in range(width):
            seen.add(tuple(row[x * 4:x * 4 + 3]))

    # EVERY COLOUR OF THE MARK MUST ACTUALLY APPEAR, each in at least one pixel it fills
    # outright: the tile and the mark on it. Losing one is a part that did not render. A book's
    # own icon is drawn in its brand's field colours as PortFusion's is in its own.
    c = icon.colours()
    for name, rgb in (("the tile", c["tile"]), ("the mark", c["ring"])):
        assert rgb in seen, (
            f"{name} {rgb} is not in the rendered icon — something did not draw. "
            f"Colours present: {sorted(seen)}")


def test_a_palette_change_reaches_the_icon(monkeypatch):
    """THE ICON IS DRAWN IN THE PALETTE, not in copies of it, so a colour changed in
    house/palette.py or a brand must change PortFusion's drawn mark too — the same promise
    desk/theme.py makes for the CSS."""
    from portfusion.desk import icon, theme

    real = theme.palette
    before = icon.png(64)
    monkeypatch.setattr(theme, "palette", lambda dark=False: {**real(dark), "on-field": "#FF00AA"})

    assert icon.colours()["ring"] == (0xFF, 0x00, 0xAA), \
        "the icon's ring did not come from the palette's `on-field`"
    assert icon.png(64) != before, "the palette changed and the icon drew the same bytes"


def test_the_page_declares_the_icon_the_dock_will_use(repo_root):
    """THE OTHER END OF THE FAVICON ROUTE.

    Safari's "Add to Dock" takes the icon from `apple-touch-icon` on the page. Without it the
    Dock shows a generic page mark — and it does so QUIETLY, with the desk working perfectly in
    every other respect, which is exactly the class of failure this project refuses to leave
    unguarded. The route is tested above; this holds the page to naming it.

    The theme colours are checked against THE PALETTE THEY COME FROM, not against literals, so
    a palette change cannot leave the window chrome behind. `--paper` is the page's ground in
    each scheme and the browser paints the chrome around the page to match.

    Both halves are GENERATED, in `desk/theme.py`'s tokens_css(), from the `paper` role in
    house/palette.py's SCREEN and its DARK.
    """
    from portfusion.desk import theme
    from portfusion.house import palette as P

    html = (SRC / "desk" / "static" / "index.html").read_text()

    for size, href in (("180x180", "/apple-touch-icon.png"), ("512x512", "/icon-512.png")):
        assert f'rel="apple-touch-icon" sizes="{size}" href="{href}"' in html, (
            f"the page does not declare the {size} apple-touch-icon, so a Dock web app would "
            "wear a smaller or a generic icon — silently")
    assert 'rel="manifest" href="/manifest.webmanifest"' in html, \
        "the page does not name its manifest, so Chrome and Android cannot make it an app"
    assert 'name="apple-mobile-web-app-title"' in html, \
        "without this the Dock web app is named with the whole <title>"

    # THE DOCK AND THE TAB CARRY ONE NAME: "The Desk | <the book's name>", ending with the name,
    # so Safari does not trim the opening words two tabs share. The page states it twice, so this
    # holds the two alike.
    html = app.index().body.decode()
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    dock = re.search(r'name="apple-mobile-web-app-title" content="([^"]*)"', html).group(1)
    assert dock == title, \
        f"the Dock web app would be named {dock!r} while the browser tab reads {title!r}"

    light, dark = "#" + P.SCREEN["paper"], "#" + P.DARK["paper"]
    tokens = theme.tokens_css()
    assert f"--paper: {light};" in tokens.split("@media")[0], \
        "tokens.css no longer grounds the page in PAPER — the light theme-color below is stale"
    assert f"--paper: {dark};" in tokens.split("@media")[1], \
        "tokens.css no longer sets the dark ground — the dark theme-color below is stale"

    for scheme, colour in (("light", light), ("dark", dark)):
        assert f'content="{colour}" media="(prefers-color-scheme: {scheme})"' in html, \
            f"the {scheme} theme-color is not {colour}, which is what the page is grounded in"


def _png_shape(body: bytes) -> tuple[int, int, int]:
    """A PNG's width, height and colour type, from its header chunk."""
    import struct
    assert body[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    width, height, _, colour = struct.unpack(">IIBB", body[16:26])
    return width, height, colour


def test_the_dock_icons_are_the_full_mark_square_and_opaque():
    """THE DOCK, THE HOME SCREEN AND ANDROID WEAR THE FULL MARK: the book's own, from its brand,
    or PortFusion's, drawn.

    Each route is requested over HTTP and must return that icon, at the size its name says, with
    no alpha channel, since every one of those surfaces draws its own corner."""
    from portfusion import brand
    from portfusion.desk import icon
    client = TestClient(app.app, base_url="http://127.0.0.1:8765")
    sizes = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512}
    assert set(sizes) == set(brand.APP_ICONS), "an app icon was added or dropped without its size"
    for name, px in sizes.items():
        r = client.get(f"/{name}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png", f"/{name}"
        assert r.content == ((brand.ICONS / name).read_bytes() if brand.ICONS
                             else icon.png(px, square=True))
        width, height, colour = _png_shape(r.content)
        assert (width, height) == (px, px), f"/{name} is {width}x{height}, not {px}x{px}"
        assert colour == 2, f"/{name} is not opaque RGB (colour type {colour}): it has alpha"
    assert client.get("/icon-64.png").status_code == 404, "a size nobody named was served"


def test_the_manifest_makes_the_desk_an_app_under_the_tabs_name(repo_root):
    """WHAT CHROME, ANDROID AND SAFARI READ. `bundle.manifest()` says what each field is and
    why; this holds them: the name to the `<title>`, every icon to a file the shell serves at the
    size it names, the colours to the palette, and the response to a manifest's type."""
    import json
    from portfusion.desk import bundle, theme
    client = TestClient(app.app, base_url="http://127.0.0.1:8765")
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = json.loads(r.content)

    html = app.index().body.decode()
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    assert m["name"] == title, f"the app would be named {m['name']!r}, the tab {title!r}"
    assert m["display"] == "standalone" and m["start_url"] == m["scope"] == m["id"] == "/"

    palette = theme.palette()
    assert m["background_color"] == palette["field"] and m["theme_color"] == palette["paper"]

    assert {i["purpose"] for i in m["icons"]} == {"any", "maskable"}
    for icon in m["icons"]:
        assert icon["src"] in bundle.paths(), f"the manifest names {icon['src']}, not served"
        width, height, _ = _png_shape(client.get(icon["src"]).content)
        assert icon["sizes"] == f"{width}x{height}", f"{icon['src']} is not {icon['sizes']}"


def test_a_name_off_the_workbench_reads_nothing_from_the_books_folder(client, tmp_path,
                                                                      monkeypatch):
    """A BARE NAME IS NEVER TRIED AGAINST THE FOLDER THE DESK RUNS IN, the book's, which holds its
    credentials. A name means a document on the workbench, or nothing; and the bench will not
    open an item on a path at all."""
    from portfusion.record import schema
    book, inbox = tmp_path / "book", tmp_path / "book" / "_inbox"
    inbox.mkdir(parents=True)
    (book / "credentials.json").write_text('{"secret": "do-not-serve"}', encoding="utf-8")
    monkeypatch.setattr(schema, "BOOK", book)
    monkeypatch.chdir(book)
    for name in ("credentials.json", "..", "../credentials.json"):
        got = client.get(f"/api/document/{name}")
        assert "do-not-serve" not in got.text, f"{name!r} served the book's own file"
    assert client.post("/api/bench", json={"document": {"name": str(book / "credentials.json")}}
                       ).status_code == 404


def test_a_record_that_will_not_load_is_unavailable_on_every_panel(tmp_path):
    """ONE CELL NO LOADER ACCEPTS: the shell and every panel say "record unavailable" (503), the
    shell with the record's own words naming the file, and the remote door still opens with the
    book's settings. Served from a child process, on a copy of the demo with one cell no loader
    accepts, so this process's record is untouched."""
    import json
    import shutil
    import subprocess
    import sys
    from portfusion.record import schema
    book = tmp_path / "book"
    shutil.copytree(schema.DEMO, book)
    trades = book / "store" / "buys.csv"
    lines = trades.read_text(encoding="utf-8").splitlines()
    head = lines[0].split(",")
    cells = lines[1].split(",")
    cells[head.index("qty")] = "not-a-number"
    trades.write_text("\n".join([lines[0], ",".join(cells), *lines[2:]]) + "\n", encoding="utf-8")
    probe = (
        "import json\n"
        "from fastapi.testclient import TestClient\n"
        "from portfusion.desk import app, panels, remote\n"
        f"c = TestClient(app.app, base_url={DESK!r})\n"
        "names = [p.stem.replace('_', '-') for p in __import__('pathlib').Path(panels.__file__)"
        ".parent.glob('[a-z]*.py')]\n"
        "state = c.get('/api/state')\n"
        "out = {n: c.get(f'/api/panel/{n}').status_code for n in names}\n"
        "out['/api/state'] = [state.status_code, state.json().get('detail', '')]\n"
        "out['remote'] = remote.unconfigured()\n"
        "print(json.dumps(out))\n")
    run = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                         env={**__import__("os").environ, "PORTFUSION_BOOK": str(book)})
    assert run.returncode == 0, run.stderr[-1500:]
    codes = json.loads(run.stdout.strip().splitlines()[-1])
    status, said = codes.pop("/api/state")
    assert codes.pop("remote") == [], "the remote door did not read the book's settings"
    assert status == 503 and "buys.csv" in said, (status, said)
    assert len(codes) == 13 and set(codes.values()) == {503}, codes


def test_a_drop_with_no_download_time_is_not_refused_for_it(client, inbox):
    """A FILE WITH NO MODIFIED TIME is not refused for it: the page sends the parameter only when
    there is a time, and the route takes a drop without one."""
    import re
    js = re.sub(r"/\*.*?\*/", "", desk_script(), flags=re.S)
    assert "`&modified=${f.lastModified || \"\"}`" not in js, "the page still sends an empty time"
    assert client.post("/api/inbox?name=note.pdf", content=b"%PDF-1.4 x").status_code == 200
