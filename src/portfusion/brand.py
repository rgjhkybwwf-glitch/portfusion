"""brand.py — whose book this is and how it looks: the book's `brand/` folder, or PortFusion's own.

PORTFUSION OWNS THE SHELL — the layout, the type, the grounds and lines, the status inks — and a
book's `brand/` folder supplies its identity. A book without one wears PortFusion's look and name,
which is what a new book and the demo do.

    <book>/brand/brand.toml         the words and the colours, below
    <book>/brand/mark.svg           the mark beside the wordmark, drawn in currentColor
    <book>/brand/favicon.png        the tab's icon, 64px
    <book>/brand/apple-touch-icon.png, icon-192.png, icon-512.png
                                    the larger surfaces' icons, at 180, 192 and 512
    <book>/brand/<face>.woff2       a typeface, when [font] names one

brand.toml:

    name = "…"                      where a book is read: the tab, the Dock, the report, a passkey
    ownership = "© {year} …"        the footer's first half; {year} is the page's own
    wordmark = ["…", "…"]           the lockup's lines: the name, then a smaller line under it
    [light] / [dark]                any of BRAND_ROLES, as six-digit hex
    [font]                          family, file, weight, stretch, as house/palette.py's FONT

Every key is optional, and a key nobody named is refused rather than ignored. THE COLOURS A BOOK
MAY SET ARE ITS ACCENT AND ITS SPARK, with the field the accent stands on: the rest are
PortFusion's, so every book reads alike where reading is the work. A role the dark scheme
changes by default must be given for the dark scheme too, or a light accent would sit beside
PortFusion's dark one.

READ ONCE, when first imported, from `schema.BOOK`, as the record is. Imports nothing of the
book's record, so a renderer reads it without loading one.
"""
from __future__ import annotations

import pathlib
import re
import tomllib

from portfusion.house import mark, palette as P
from portfusion.record.schema import BOOK

#: The app's name, wherever software is operated and wherever a book names none of its own.
APP = "PortFusion"

#: The palette roles a book's brand may set. `link`, `mark`, `key-clear` and `chart` follow the
#: accent, as they do in PortFusion's own palette.
BRAND_ROLES = ("accent", "field", "on-field", "on-field-muted", "field-rule", "spark")
FOLLOW_ACCENT = ("link", "mark", "key-clear", "chart")
#: The app icons, by the name each is served at.
APP_ICONS = ("apple-touch-icon.png", "icon-192.png", "icon-512.png")

#: THE FOLDER, or None when the book has none.
DIR = BOOK / "brand" if (BOOK / "brand").is_dir() else None

_KEYS = {"name", "ownership", "wordmark", "light", "dark", "font"}


def _read() -> dict:
    path = DIR / "brand.toml" if DIR else None
    if path is None or not path.is_file():
        return {}
    with open(path, "rb") as fh:
        got = tomllib.load(fh)
    if unknown := set(got) - _KEYS:
        raise SystemExit(f"{path} names {sorted(unknown)}, which a brand does not hold: "
                         f"it holds {sorted(_KEYS)}")
    for scheme in ("light", "dark"):
        if unknown := set(got.get(scheme, {})) - set(BRAND_ROLES):
            raise SystemExit(f"{path} [{scheme}] sets {sorted(unknown)}: a brand sets only "
                             f"{', '.join(BRAND_ROLES)}, and PortFusion the rest")
        for role, value in got.get(scheme, {}).items():
            if not re.fullmatch(r"[0-9A-Fa-f]{6}", str(value)):
                raise SystemExit(f"{path} [{scheme}] {role} is {value!r}, not six-digit hex")
    if missing := sorted(r for r in got.get("light", {}) if r in P.DARK
                         and r not in got.get("dark", {})):
        raise SystemExit(f"{path} sets {missing} for the light scheme only: the dark scheme "
                         f"changes them too, so [dark] must give them")
    return got


_B = _read()

NAME: str = _B.get("name", APP)
OWNERSHIP: str | None = _B.get("ownership")
WORDMARK: tuple[str, ...] = tuple(_B.get("wordmark", (NAME,)))
MARK_SVG = ((DIR / "mark.svg").read_text(encoding="utf-8").strip()
            if DIR and (DIR / "mark.svg").is_file() else "")


def _scheme(base: dict, given: dict) -> dict:
    out = {**base, **{r: v.upper() for r, v in given.items()}}
    if "accent" in given:
        out |= {r: given["accent"].upper() for r in FOLLOW_ACCENT}
    return out


#: The two screens' colours, PortFusion's with the brand's laid over them.
SCREEN = _scheme(P.SCREEN, _B.get("light", {}))
DARK = _scheme(P.DARK, _B.get("dark", {}))

#: The typeface, and the folder its file is in.
FONT = {**P.FONT, **_B["font"]} if "font" in _B else P.FONT
FONT_DIR = DIR if "font" in _B else pathlib.Path(P.__file__).resolve().parent / "fonts"
FACES = ({"sans": f'"{FONT["family"]}", ui-sans-serif, system-ui, sans-serif'}
         if "font" in _B else P.FACES)

#: THE BOOK'S OWN ICONS, the folder they are in, or None: PortFusion then draws its own
#: (`desk/icon.py`). All four or none, so a tab and the Dock never wear two different marks.
_have = [n for n in ("favicon.png", *APP_ICONS) if DIR and (DIR / n).is_file()]
if _have and len(_have) != 1 + len(APP_ICONS):
    raise SystemExit(f"{DIR} holds {_have}: a brand's icons are favicon.png and "
                     f"{', '.join(APP_ICONS)}, all of them or none")
ICONS = DIR if _have else None


def lockup() -> str:
    """The mark and the wordmark, in the screens' own `mark` token."""
    return mark.lockup(NAME, WORDMARK, MARK_SVG)


def ownership(year: int) -> str | None:
    """The footer's first half, in the book's own words, or None when it gives none."""
    return OWNERSHIP.format(year=year) if OWNERSHIP else None
