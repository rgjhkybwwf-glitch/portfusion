"""THE SHELL AS ONE SET OF FILES — everything a browser loads before its first /api call.

    from portfusion.desk import bundle
    bundle.index()               # b"<!doctype html>…", every asset linked by its content
    bundle.asset("/tokens.css")  # one asset's bytes; KeyError for anything not in `paths()`

ONE SOURCE. The desk answers `/`, `/static/*`, `/tokens.css`, `/favicon.png`, the app icons,
`/manifest.webmanifest` and `/fonts/*` from here, and `tests/desk/test_bundle.py` requests every
path over HTTP to hold it. A file the shell needs joins by being named in `paths()`; a second
list anywhere else would be the drift this prevents.

A CHANGED FILE GETS A CHANGED URL. Each stylesheet and script is linked with `?v=` and the start
of its own content hash, so a browser can never run an older copy inside a fresh shell.

IT COMPUTES NOTHING OF THE BOOK'S. The colours come from `theme.tokens_css()`, the lockup and
the name from `house/mark.py`, the footer's words from `about.release()` and the icons from
`desk.icon`; this only gathers them, and states the manifest that names them. It writes nothing.

THE ICONS, BY SURFACE. A browser tab draws `/favicon.png`, rounded. Every larger surface takes
the full mark, square and opaque, because each draws its own corner: Safari's "Add to Dock" and
an iPhone's home screen read `apple-touch-icon`, which the page points at `/apple-touch-icon.png`
(180, the name iOS asks for unprompted) and `/icon-512.png` (sharp at the Dock's magnification);
Chrome and Android read `/manifest.webmanifest`.
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import pathlib
import re

from portfusion import about
from portfusion.desk import theme
from portfusion.house import mark, palette

STATIC = pathlib.Path(__file__).resolve().parent / "static"
FONTS = palette.FONT_DIR

#: The app icons' sizes, by the name each is served at.
APP_ICON_SIZES = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512}

#: THE DESK'S SCRIPT, in the order it loads: ordered classic scripts sharing one global scope, so
#: a file's top-level code may use only what the files before it declare. app.js, the entry,
#: loads last. `index()` writes the page's script tags from this, and nowhere else states it.
SCRIPTS = ("core.js", "kit.js", "what-changed.js", "dashboard.js", "holdings.js", "round-trips.js",
           "method.js", "accounts.js", "reports.js", "performance.js", "trades.js", "reconcile.js",
           "bench.js", "sweep.js", "price-refresh.js", "app.js")

#: THE DESK'S STYLESHEET, in the order it is linked: a later file's rule wins a tie with an
#: earlier one's, so the kit comes first and the phone's rules last. `index()` writes the page's
#: link tags from this.
STYLES = ("kit.css", "tables.css", "pages.css", "bench.css", "phone.css")

#: WHAT EVERY FILE OF THE SHELL IS SENT WITH: the page loads and connects to its own origin only,
#: and nothing may frame it; no type is sniffed and no referrer sent.
SHELL_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
                               "base-uri 'none'; form-action 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

#: The files under desk/static/ the shell loads. index.html is not one: it is the page itself,
#: filled in by `index()`, and its raw template is served nowhere.
SHELL_STATIC = (*STYLES, *SCRIPTS)

#: The URLs `index.html` links and stamps, each with the asset it stands for.
_STAMPED = (*(f"/static/{n}" for n in SHELL_STATIC), "/tokens.css")


def _fonts() -> list[str]:
    """The typefaces /tokens.css declares, as their URLs. Derived from the stylesheet, so a face
    declared by house/palette.py's FONT joins the shell by being declared."""
    return sorted(set(re.findall(r"url\('(/fonts/[^']+)'\)", theme.tokens_css())))


def paths() -> list[str]:
    """Every asset URL the shell loads, the page itself aside."""
    return [*(f"/static/{n}" for n in SHELL_STATIC), "/tokens.css", "/favicon.png",
            *_app_icons(), "/manifest.webmanifest", *_fonts()]


def _app_icons() -> list[str]:
    """The full-mark icons, as their URLs."""
    return [f"/{name}" for name in APP_ICON_SIZES]


def title() -> str:
    """The page's name, which the tab, the window and the Dock carry alike."""
    return f"The Desk | {mark.NAME}"


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
    colours = theme.palette()
    sized = [(n, m[1]) for n in APP_ICON_SIZES if (m := re.fullmatch(r"icon-(\d+)\.png", n))]
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
        return theme.tokens_css().encode()
    if path == "/favicon.png" or path in _app_icons():
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


def index() -> bytes:
    """The page: the template, its assets stamped by content, and the lockup."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace("<!-- styles -->", "\n".join(
        f'<link rel="stylesheet" href="/static/{n}">' for n in STYLES))
    html = html.replace("<!-- scripts -->", "\n".join(
        f'<script src="/static/{n}"></script>' for n in SCRIPTS))
    for url in _STAMPED:
        html = html.replace(f'"{url}"', f'"{url}?v={_digest(asset(url))}"')
    html = html.replace("<!-- lockup -->", mark.lockup())
    html = html.replace("<!-- title -->", _html.escape(title()))
    # WHICH RELEASE, in the footer.
    html = html.replace("<!-- footer -->", _html.escape(about.release()))
    return html.encode()
