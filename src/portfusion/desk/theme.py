"""The screen palette as CSS custom properties — `house/palette.py`'s colours with the book's brand
laid over them (`portfusion.brand`), never retyped.

A second renderer is where "derive it, never type it twice" breaks first: a hand-copied hex
here would drift the day the palette moves. So the tokens are generated from the one palette:
change a colour in house/palette.py and every renderer that wears it changes together, or none
does. The dark scheme too.

THE TYPEFACE: one family as one stack, and one @font-face across the file's whole weight and
width range, served from house/fonts/ (or the brand's folder, when it names a face) by app.py's
/fonts route — on disk, so the desk renders the same with the network down.

THE DESK WEARS THESE AND NO OTHERS. A token emitted and never consumed is a palette entry
pretending to be a treatment, so `tests/desk/test_routes.py` holds every one here to a use in
app.css or the icon, and the report's own (its page ground, its labels) stay out, except its
bars, which Holdings' allocation draws as the report does.
"""
from __future__ import annotations

from portfusion import brand as P

#: The screen roles the desk wears, by house/palette.py's names for their jobs.
DESK = ("paper", "band", "hair", "rule", "ink", "muted", "heading", "control", "recessed",
        "accent", "link", "mark", "warn", "warn-ink",
        "key-problem", "key-gap", "key-note", "key-clear", "up", "down", "chart", "field", "on-field",
        "on-field-muted", "field-rule", "spark", "footer", "footer-edge", "on-footer-muted")


def palette(dark: bool = False) -> dict[str, str]:
    """The desk's colours in one scheme, keyed by the token names the stylesheet uses. The icon
    draws on the field, which is the same in both."""
    return {role: "#" + (P.DARK.get(role, P.SCREEN[role]) if dark else P.SCREEN[role])
            for role in DESK}


def faces_css() -> str:
    """The variable file's single declaration, its two axes as house/palette.py gives them."""
    f = P.FONT
    return (f"@font-face {{ font-family: '{f['family']}'; font-style: normal; "
            f"font-weight: {f['weight']}; font-stretch: {f['stretch']}; font-display: swap; "
            f"src: url('/fonts/{f['file']}') format('woff2'); }}\n")


def tokens_css() -> str:
    """The palette as CSS custom properties, both schemes.

    Everything in static/ styles itself from these names and never from a literal colour —
    use the style layer; never set a fill or a font at a call site.
    """
    body = "\n".join([*(f"  --font-{k}: {v};" for k, v in P.FACES.items()),
                      *(f"  --{k}: {v};" for k, v in palette().items())])
    # DARK IS DERIVED: a role given a dark value in the palette reaches the desk by existing.
    dark = "\n".join(f"    --{role}: #{P.DARK[role]};" for role in DESK if role in P.DARK)
    return (
        "/* GENERATED from house/palette.py by desk/theme.py. Do not edit — edit the palette. */\n"
        f"{faces_css()}"
        f":root {{\n{body}\n}}\n"
        "/* house/palette.py's DARK says what moves and why. */\n"
        f"@media (prefers-color-scheme: dark) {{\n  :root {{\n{dark}\n  }}\n}}\n"
    )
