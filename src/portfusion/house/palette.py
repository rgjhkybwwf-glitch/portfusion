"""house/palette.py — PortFusion's own colours and typeface, which every book wears unless its brand
says otherwise.

The desk and the report turn SCREEN and DARK below into CSS custom properties (`desk/theme.py`,
`report/style.py`), through `portfusion.brand`, which lays a book's accent and spark over them. A
colour changed here moves every renderer that wears it, or none.

A STAND-IN. PortFusion's own design system is still to be drawn; until it is, these are a set
of cool greys, status inks and a graphite accent, with grounds and inks legible in both schemes.
Its arrival replaces this file's values and nothing else.

Bare six-digit hex; the screens add the `#`.

Imports nothing, so a renderer reads it without loading the record.
"""

# ---- the tokens: each colour under its own name ---------------------------------------------
#: Light first, then the dark theme where it differs.
TOKENS = {
    # grounds and lines
    "surface": "FFFFFF", "surface-panel": "F4F5FC", "tint": "E8EAFC",
    "line": "D9DBEA", "line-strong": "0D0E1A", "control-line": "0D0E1A", "control-bg": "FFFFFF",
    # text
    "ink": "0D0E1A", "ink-body": "22253A", "ink-muted": "4A4E63",
    # the accent, and the field it stands on: graphite, until PortFusion has a colour of its own
    "accent": "3A3F52", "field": "3A3F52", "on-field": "FFFFFF", "on-field-muted": "C4C7D4",
    "field-rule": "5A5F74",
    # the thread, the selected point on the rail: white, ringed in the heading's ink
    "spark": "FFFFFF",
    # the footer, the same in both themes
    "footer": "0D0E1A", "footer-edge": "0D0E1A", "footer-line": "2A2C40",
    "on-footer": "FFFFFF", "on-footer-muted": "A9ADC4",
    # status inks on their soft fills, and the bar colours for tallies and table keys
    "status-bear": "8F2A10", "status-bear-soft": "FFE1D6",
    "status-bull": "1D27A8", "status-bull-soft": "E8EAFC",
    "status-held": "3A3D4F", "status-held-soft": "EEEFF3",
    "status-mixed": "6B5300", "status-mixed-soft": "FFF3C2",
    "bar-bear": "C2451E", "bar-mixed": "E8B500", "bar-held": "A3A7BA",
}

#: MOVEMENT, WHICH IS NOT PROVENANCE, worn on these fields: the up and down below. A JUDGEMENT,
#: NOT A TYPE: each is a gain, whose sign says whether the book is better or worse off. Money that
#: is no result stays plain: a Reconcile difference (a gap is not a loss), a weight (never
#: negative), cost, value, capital deployed, and `transacted` (a purchase is not a gain). The
#: Dashboard's headline gains stay plain too: a summary is read, a column is scanned.
MOVEMENT_FIELDS = ("gain", "unrealised", "unrealised_pct", "realised_pct", "return", "change",
                   "price_effect", "fx_effect", "price_move_pct", "realised", "life_gain",
                   "life_pct")

#: The dark theme: only the tokens that change. The field and the footer do not.
TOKENS_DARK = {
    "surface": "0E0F16", "surface-panel": "171926", "tint": "1E2140",
    "line": "2A2D40", "line-strong": "C9CCE0", "control-line": "6A6E88", "control-bg": "171926",
    "ink": "F2F3FA", "ink-body": "D6D8E6", "ink-muted": "A3A7BF",
    "accent": "C3C7D6", "footer-edge": "2A2D40",
    "status-bear": "FFB59E", "status-bear-soft": "3A1A12",
    "status-bull": "B9C0FF", "status-bull-soft": "1E2140",
    "status-held": "C9CCE0", "status-held-soft": "23253A",
    "status-mixed": "F2D47A", "status-mixed-soft": "332A0A",
    "bar-bear": "E0714F", "bar-held": "6A6E88",
}

#: ONE FAMILY: Archivo, whose width and weight axes do three typefaces' work. Expanded 800 for
#: display and figures that lead, normal for text, condensed 600 in capitals for labels.
#: Figures are Archivo's own, set tabular wherever they line up — the screens set no monospace.
FACES = {"sans": '"Archivo", ui-sans-serif, system-ui, sans-serif'}

#: The one file, variable on both axes, declared once across its whole range so `font-stretch`
#: and `font-weight` drive the axes rather than selecting between files. Openly licensed (SIL
#: OFL), which is what lets a copy live in `house/fonts/`. A book's brand may name its own.
FONT = {"family": "Archivo", "file": "archivo.woff2", "weight": "100 900", "stretch": "62% 125%"}


# ---- the two screens: each colour named for its job -----------------------------------------
#: The desk's custom properties take these names, and the report maps its own onto them.
_O = TOKENS
SCREEN = {
    "paper": _O["surface"],             # the ground a table or a panel sits on
    "ground": _O["surface"],            # the report's page, behind its tables
    "band": _O["surface-panel"],        # one step off the paper: a panel, a filter box, a group row
    "hair": _O["line"],                 # a line between rows
    "rule": _O["line-strong"],          # the 2px rule that opens a section, a table, a figure strip
    "ink": _O["ink-body"],              # body text
    "heading": _O["ink"],               # a title, a column head, a field label
    "muted": _O["ink-muted"],           # explainer text and metadata
    "faint": _O["ink-muted"],           # the quietest text: the report's labels
    "control": _O["control-line"],      # an input's border
    "recessed": _O["control-bg"],       # an input's ground
    #: THE ACCENT: links, a selected page, focus, the mark on a light ground. A brand's own colour
    #: replaces it; in the dark scheme it lightens, so it stays legible on the dark page.
    "accent": _O["accent"],
    "link": _O["accent"],
    "mark": _O["accent"],
    #: THE DESK'S STATES ARE KEY DOTS: a round point in one of the bar colours beside the
    #: state's word in ink. The word is the
    #: reading and the dot is the scan, so colour is never the only signal.
    "key-problem": _O["bar-bear"],
    "key-gap": _O["bar-mixed"],
    "key-note": _O["bar-held"],
    "key-clear": _O["accent"],
    #: A ROW THAT DIFFERS, and a speculative figure's edge: the mixed status fill. The desk's
    #: warning ink — stale, an error, a required field — is the bear ink.
    "warn": _O["status-mixed-soft"],
    "warn-ink": _O["status-bear"],
    #: MOVEMENT, WHICH IS NOT PROVENANCE: the desk's channel and the report's. Blue up, orange
    #: down, a pair that differs in lightness and not hue alone.
    "up": _O["status-bull"],
    "down": _O["status-bear"],
    "chart": _O["accent"],              # the report's bars, making no claim about a source
    #: THE FIELD: the one strong moment — the app icon, the Dashboard's band, the sign-in. It is
    #: the same in both schemes.
    "field": _O["field"],
    "on-field": _O["on-field"],
    "on-field-muted": _O["on-field-muted"],
    "field-rule": _O["field-rule"],
    #: THE THREAD: spark, the selected point on the rail, once a view.
    "spark": _O["spark"],
    "footer": _O["footer"],
    "footer-edge": _O["footer-edge"],
    "on-footer-muted": _O["on-footer-muted"],
}

#: THE DARK SCHEME, keyed by the job each replaces, wherever the dark tokens differ. The contrast
#: is computed, not trusted: `test_every_screen_colour_is_legible_in_both_schemes`.
_I = {**TOKENS, **TOKENS_DARK}
DARK = {
    "paper": _I["surface"], "ground": _I["surface"], "band": _I["surface-panel"],
    "hair": _I["line"], "rule": _I["line-strong"],
    "ink": _I["ink-body"], "heading": _I["ink"], "muted": _I["ink-muted"], "faint": _I["ink-muted"],
    "control": _I["control-line"], "recessed": _I["control-bg"],
    "accent": _I["accent"], "link": _I["accent"], "mark": _I["accent"],
    "key-problem": _I["bar-bear"], "key-note": _I["bar-held"], "key-clear": _I["accent"],
    "warn": _I["status-mixed-soft"], "warn-ink": _I["status-bear"],
    "up": _I["status-bull"], "down": _I["status-bear"], "chart": _I["accent"],
    "footer-edge": _I["footer-edge"],
}
