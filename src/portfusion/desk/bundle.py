"""THE SHELL AS ONE SET OF FILES — everything a browser loads before its first /api call.

    from portfusion.desk import bundle
    bundle.files()      # {"/": b"<!doctype html>…", "/static/core.js": b"…", "/tokens.css": …}
    bundle.version()    # "3f9c2a1b7d04" — the name of this exact set

ONE SOURCE, TWO SERVERS. The Mac desk answers `/`, `/static/*`, `/tokens.css`, `/favicon.png`,
the app icons, `/manifest.webmanifest` and `/fonts/*` from here, and `portfusion desk --publish`
writes the same mapping out for Netlify. The
hosted desk and the Mac's are therefore the same bytes by construction, and
`tests/desk/test_bundle.py` requests every path over HTTP to hold it. A file the shell needs
joins by being named in `paths()`; a second list anywhere else would be the drift this prevents.

A CHANGED FILE GETS A CHANGED URL. Each stylesheet and script is linked with `?v=` and the start
of its own content hash, so a browser can never run an older copy inside a fresh shell. Content
rather than modification time, because the hosted copy is written by a checkout and a time
would differ where the bytes do not.

THE VERSION names the whole set: a hash over every file except the shell page, which carries it
in `<meta name="desk-version">`. Not "build", which in this repo is the report's. The hosted page compares it with the Mac's before it draws anything,
so old screen code never renders new data — the mixture `engine.source_stale()` guards against.

IT COMPUTES NOTHING OF THE BOOK'S. The colours come from `engine.tokens_css()`, the lockup from
`engine.lockup()`, the name and the footer's words from `portfusion.brand`, the icons from the
book's `brand/` folder or, where it has none, from `desk.icon`; this only gathers them, and
states the manifest that names them. It writes nothing.

THE ICONS, BY SURFACE. A browser tab draws `/favicon.png`, rounded. Every larger surface takes
the full mark, square and opaque, because each draws its own corner: Safari's "Add to Dock" and
an iPhone's home screen read `apple-touch-icon`, which the page points at `/apple-touch-icon.png`
(180, the name iOS asks for unprompted) and `/icon-512.png` (sharp at the Dock's magnification);
Chrome and Android read `/manifest.webmanifest`.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import html as _html
import json
import pathlib
import re

from portfusion import about, brand
from portfusion.desk import engine

STATIC = pathlib.Path(__file__).resolve().parent / "static"
FONTS = brand.FONT_DIR

#: The app icons' sizes, by the name each is served at.
APP_ICON_SIZES = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512}
assert set(APP_ICON_SIZES) == set(brand.APP_ICONS)

#: THE DESK'S SCRIPT, in the order it loads: ordered classic scripts sharing one global scope, so
#: a file's top-level code may use only what the files before it declare. app.js, the entry,
#: loads last. `index()` writes the page's script tags from this, and nowhere else states it.
SCRIPTS = ("core.js", "kit.js", "reading.js", "access.js", "bench.js", "sweep.js",
           "price-refresh.js", "app.js")

#: The files under desk/static/ the shell loads. index.html is not one: it is the page itself,
#: filled in by `index()`, and its raw template is served nowhere.
SHELL_STATIC = ("app.css", *SCRIPTS)

#: The URLs `index.html` links and stamps, each with the asset it stands for.
_STAMPED = ("/static/app.css", *(f"/static/{n}" for n in SCRIPTS), "/tokens.css")


def _fonts() -> list[str]:
    """The typefaces /tokens.css declares, as their URLs. Derived from the stylesheet, so a face
    declared by house/palette.py's FONT joins the shell by being declared."""
    return sorted(set(re.findall(r"url\('(/fonts/[^']+)'\)", engine.tokens_css())))


def paths() -> list[str]:
    """Every asset URL the shell loads, the page itself aside."""
    return [*(f"/static/{n}" for n in SHELL_STATIC), "/tokens.css", "/favicon.png",
            *_app_icons(), "/manifest.webmanifest", *_fonts()]


def _app_icons() -> list[str]:
    """The full-mark icons, as their URLs."""
    return [f"/{name}" for name in brand.APP_ICONS]


def title() -> str:
    """The page's name, which the tab, the window and the Dock carry alike: the book's."""
    return f"The Desk | {brand.NAME}"


def footer() -> str:
    """WHOSE IT IS AND WHICH RELEASE: the book's own words, when it gives them, then the app's.
    The year is the page's own, so the line never needs retyping."""
    whose = brand.ownership(_dt.date.today().year)
    return " · ".join([*([whose] if whose else []), about.release()])


def manifest() -> str:
    """THE WEB APP MANIFEST: what Chrome, Android and Safari's Dock read to make the desk an app.

    The name is the page's own `<title>`, `title()`, because the Dock, the tab and the window
    carry one name. `standalone`, because
    the desk is an app, where the website, a publication, keeps the browser's chrome. The colours
    are the palette's: the field behind the icon while the app opens, the paper the page is
    grounded in for the window. The manifest takes the icons named by their size; the touch icon
    is iOS's, which reads it from the page. Each is offered twice, as "any" and as "maskable":
    the mark sits well inside the 40% circle a launcher keeps, so one file serves both.
    """
    name = title()
    colours = engine.palette()
    sized = [(n, m[1]) for n in brand.APP_ICONS if (m := re.fullmatch(r"icon-(\d+)\.png", n))]
    icons = [{"src": f"/{n}", "sizes": f"{px}x{px}", "type": "image/png", "purpose": purpose}
             for purpose in ("any", "maskable") for n, px in sized]
    return json.dumps({
        "id": "/", "name": name, "short_name": "The Desk", "lang": "en-GB",
        "start_url": "/", "scope": "/", "display": "standalone",
        "theme_color": colours["paper"], "background_color": colours["field"],
        "icons": icons,
    }, indent=2, ensure_ascii=False) + "\n"


def asset(path: str) -> bytes:
    """One asset's bytes. KeyError for anything that is not part of the shell, which is the
    containment rule: a name is looked up, never resolved against a directory."""
    if path == "/tokens.css":
        return engine.tokens_css().encode()
    if path == "/favicon.png" or path in _app_icons():
        if brand.ICONS:
            return (brand.ICONS / path[1:]).read_bytes()
        from portfusion.desk.icon import png
        return (png(64) if path == "/favicon.png"
                else png(APP_ICON_SIZES[path[1:]], square=True))
    if path == "/manifest.webmanifest":
        return manifest().encode()
    if path in {f"/static/{n}" for n in SHELL_STATIC}:
        return (STATIC / path.rsplit("/", 1)[1]).read_bytes()
    if path in _fonts():
        return (FONTS / path.rsplit("/", 1)[1]).read_bytes()
    raise KeyError(path)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def version(assets: dict[str, bytes] | None = None) -> str:
    """The name of this set of files: one hash over every asset, path and bytes together."""
    assets = assets if assets is not None else {p: asset(p) for p in paths()}
    h = hashlib.sha256()
    for path in sorted(assets):
        h.update(path.encode() + b"\0" + assets[path] + b"\0")
    return h.hexdigest()[:12]


def index(assets: dict[str, bytes] | None = None) -> bytes:
    """The page: the template, its assets stamped by content, the lockup, and the version."""
    assets = assets if assets is not None else {p: asset(p) for p in paths()}
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace("<!-- scripts -->", "\n".join(
        f'<script src="/static/{n}"></script>' for n in SCRIPTS))
    for url in _STAMPED:
        html = html.replace(f'"{url}"', f'"{url}?v={_digest(assets[url])}"')
    html = html.replace("<!-- lockup -->", engine.lockup())
    html = html.replace("<!-- title -->", _html.escape(title()))
    # WHOSE IT IS AND WHICH RELEASE, in the footer, on the Mac and the hosted desk alike.
    html = html.replace("<!-- footer -->", _html.escape(footer()))
    html = html.replace('<meta name="desk-version" content="">',
                        f'<meta name="desk-version" content="{version(assets)}">')
    return html.encode()


def files() -> dict[str, bytes]:
    """The whole shell, keyed by the URL each file answers at."""
    assets = {p: asset(p) for p in paths()}
    return {"/": index(assets), **assets}
