"""THE BRAND — PortFusion's look and name unless a book's `brand/` folder says otherwise.
`portfusion.brand` reads the folder once, at import, so each case here is a fresh interpreter on
a book made for it."""
import json
import os
import subprocess
import sys

import pytest

#: What a case prints: the brand as the renderers read it.
_SHOW = """
import json
from portfusion import brand
print(json.dumps({"name": brand.NAME, "wordmark": brand.WORDMARK, "mark": brand.MARK_SVG,
                  "ownership": brand.ownership(2026), "icons": str(brand.ICONS),
                  "accent": brand.SCREEN["accent"], "link": brand.SCREEN["link"],
                  "dark_accent": brand.DARK["accent"], "paper": brand.SCREEN["paper"],
                  "lockup": brand.lockup()}))
"""


def _brand(tmp_path, files: dict[str, str | bytes] | None):
    """The brand a book with these files in `brand/` reads, or the refusal it gets."""
    if files is not None:
        (tmp_path / "brand").mkdir()
        for name, body in files.items():
            (tmp_path / "brand" / name).write_bytes(body if isinstance(body, bytes)
                                                    else body.encode())
    env = {**os.environ, "PORTFUSION_BOOK": str(tmp_path)}
    r = subprocess.run([sys.executable, "-c", _SHOW], env=env, capture_output=True, text=True,
                       timeout=60)
    return json.loads(r.stdout) if r.returncode == 0 else r.stderr


def test_a_book_without_a_brand_wears_portfusions(tmp_path):
    """A NEW BOOK IS THE VANILLA APP: PortFusion's name, a wordmark with no mark beside it, its
    own colours and its drawn icons. The demo is such a book."""
    from portfusion.house import palette as P
    got = _brand(tmp_path, None)
    assert got["name"] == "PortFusion" and got["wordmark"] == ["PortFusion"], got
    assert got["mark"] == "" and got["ownership"] is None and got["icons"] == "None", got
    assert got["accent"] == P.SCREEN["accent"] and got["paper"] == P.SCREEN["paper"], got
    assert "<svg" not in got["lockup"] and ">PortFusion<" in got["lockup"], got["lockup"]


def test_a_brand_lays_its_accent_over_portfusions_shell(tmp_path):
    """The accent reaches the roles that follow it; the grounds stay PortFusion's."""
    from portfusion.house import palette as P
    got = _brand(tmp_path, {
        "brand.toml": 'name = "Example & Co"\nownership = "© {year} Example & Co"\n'
                      'wordmark = ["EXAMPLE", "AND CO"]\n'
                      '[light]\naccent = "aa0000"\n[dark]\naccent = "ff8888"\n',
        "mark.svg": '<svg viewBox="0 0 1 1"></svg>\n'})
    assert got["name"] == "Example & Co" and got["ownership"] == "© 2026 Example & Co", got
    assert got["accent"] == got["link"] == "AA0000" and got["dark_accent"] == "FF8888", got
    assert got["paper"] == P.SCREEN["paper"], "a brand moved PortFusion's ground"
    assert got["lockup"] == ('<span class="lockup" role="img" aria-label="Example &amp; Co">'
                             '<svg viewBox="0 0 1 1"></svg><span class="wordmark">'
                             '<span class="name">EXAMPLE</span><span class="sub">AND CO</span>'
                             '</span></span>'), got["lockup"]


@pytest.mark.parametrize("files, says", [
    ({"brand.toml": 'title = "x"\n'}, "which a brand does not hold"),
    ({"brand.toml": '[light]\npaper = "ffffff"\n'}, "a brand sets only"),
    ({"brand.toml": '[light]\nspark = "lime"\n'}, "not six-digit hex"),
    ({"brand.toml": '[light]\naccent = "aa0000"\n'}, "[dark] must give them"),
    ({"favicon.png": b"\x89PNG"}, "all of them or none"),
])
def test_a_brand_that_says_too_much_or_too_little_is_refused(tmp_path, files, says):
    """A KEY NOBODY READS IS REFUSED, not ignored: a brand that set the paper would believe it had,
    and a light accent beside PortFusion's dark one would be two looks at once."""
    got = _brand(tmp_path, files)
    assert isinstance(got, str) and says in got, got


@pytest.mark.parametrize("size, square", [(64, False), (180, True), (512, True)])
def test_portfusions_icons_are_drawn_at_their_size(size, square):
    """THE STAND-IN'S ICONS: the tab's with transparent corners, the larger surfaces' opaque, as
    each surface wants. `tests/desk/test_routes.py` reads the pixels of the one served."""
    import struct
    from portfusion.desk import icon
    body = icon.png(size, square=square)
    assert body[:8] == b"\x89PNG\r\n\x1a\n"
    width, height, _, colour = struct.unpack(">IIBB", body[16:26])
    assert (width, height, colour) == (size, size, 2 if square else 6)


def test_the_release_has_one_home_and_every_reader_meets_it(monkeypatch):
    """The number is PEP 440 and lives in portfusion/__init__.py alone; `beta` is a label beside
    it; between releases the dev number travels with its commit, and a release with neither.
    `portfusion --version`, the desk's footer and the report's stamp all say `about.release()`."""
    import importlib.metadata
    import re
    import portfusion
    from portfusion import about
    from portfusion.__main__ import main
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+)?", portfusion.__version__), portfusion.__version__
    assert importlib.metadata.version("portfusion") == portfusion.__version__, \
        "the installed metadata is another number: reinstall, `pip install -e .`"
    monkeypatch.setattr(portfusion, "__version__", "9.9.0")
    assert about.release() == f"PortFusion 9.9.0 {portfusion.LABEL}"
    monkeypatch.setattr(portfusion, "__version__", "9.9.0.dev0")
    assert about.release().startswith("PortFusion 9.9.0.dev0")
    monkeypatch.setattr(about, "_commit", lambda root: "abc1234")           # a checkout
    monkeypatch.setattr(about, "_installed_commit", lambda: "abc1234")       # an install
    assert about.release() == "PortFusion 9.9.0.dev0 · abc1234"
    assert main(["--version"]) == 0
