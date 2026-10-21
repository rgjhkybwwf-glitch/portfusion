"""The page's stylesheet: one string, inlined into the page so the file stands on its own.

ITS COLOURS AND TYPEFACE ARE house/palette.py's with the book's brand over them
(`portfusion.brand`), in both schemes, as the desk's are —
`tests/test_figures.py::test_no_renderer_types_a_colour` says what that replaced. The look is
PortFusion's: a white page in the light and a dark one in the dark, square corners, a 2px
rule opening every section and table, labels in condensed capitals and every figure in tabular
numerals.

THE FACE TRAVELS INSIDE THE PAGE, as base64, because a page that stands on its own cannot fetch
it, and one that falls back would do so silently. The one file is variable on weight and width,
so one declaration across its range serves every style the page sets.
"""
import base64

from portfusion import brand as P

#: Each colour the stylesheet draws with, and the screen role in house/palette.py it comes from.
#: A role with no dark value keeps its colour in both schemes.
TOKENS = {"ground": "ground", "surface": "paper", "sunken": "band", "ink": "ink",
          "heading": "heading", "muted": "muted", "faint": "faint", "control": "control",
          "line": "hair", "strong": "rule", "data": "chart", "pos": "up", "neg": "down",
          "accent": "accent", "mark": "mark", "field": "field"}

_FONTS = P.FONT_DIR


def _scheme(dark: bool) -> str:
    return ";".join(f"--{t}:#{P.DARK.get(r, P.SCREEN[r]) if dark else P.SCREEN[r]}"
                    for t, r in TOKENS.items())


def _face() -> str:
    f = P.FONT
    data = base64.b64encode((_FONTS / f["file"]).read_bytes()).decode()
    return (f"@font-face{{font-family:'{f['family']}';font-style:normal;font-weight:{f['weight']};"
            f"font-stretch:{f['stretch']};src:url(data:font/woff2;base64,{data}) format('woff2')}}\n")


CSS = (_face() + f''':root{{--font-sans:{P.FACES["sans"]};--radius-none:0px;--rule-section:2px;--rule-verdict:4px;{_scheme(False)}}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{_scheme(True)}}}}}
:root[data-theme="dark"]{{{_scheme(True)}}}
''' + """*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--font-sans);
font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1040px;margin:0 auto;padding:0 24px 80px}
h1{font-size:4.5rem;font-weight:800;font-stretch:125%;line-height:.98;letter-spacing:-.025em;
color:var(--heading);margin:10px 0 0}
h2{font-size:1.875rem;font-weight:800;font-stretch:125%;line-height:1.1;letter-spacing:-.015em;
color:var(--heading);margin:0}
h3{color:var(--heading)}
.lede{font-size:1.3rem;line-height:1.5;color:var(--ink);margin:14px 0 0}
.lockup{display:inline-flex;align-items:center;gap:12px;margin-bottom:32px;color:var(--mark)}
.lockup svg{height:36px;width:auto;flex:none}
.wordmark{display:flex;flex-direction:column;gap:4px;line-height:.95;white-space:nowrap}
.wordmark .name{font-size:19px;font-weight:800;font-stretch:125%;color:var(--heading)}
.wordmark .sub{font-size:10px;font-weight:600;font-stretch:75%;letter-spacing:.5em;
color:var(--muted)}
.eyebrow,.snum,.stats .k,th{font-size:11.5px;font-weight:600;font-stretch:75%;letter-spacing:.1em;
text-transform:uppercase;color:var(--faint)}
header{padding:48px 0 0}
.notice{margin-top:24px;padding:16px 20px;background:var(--sunken);
border-top:var(--rule-verdict) solid var(--field);border-radius:var(--radius-none);
font-weight:600;color:var(--heading);max-width:760px}
.rule{height:var(--rule-section);background:var(--strong);margin:56px 0 16px}
.snum{display:inline-block;color:var(--accent);font-weight:800;font-stretch:125%;
font-size:15px;letter-spacing:0;margin:0 16px 0 0}
section h2{display:inline}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));column-gap:24px;
margin-top:18px}
.stats>div{padding:14px 0 16px;border-bottom:1px solid var(--line)}
.stats .v{font-size:2.25rem;font-weight:800;font-stretch:125%;line-height:.9;
font-variant-numeric:tabular-nums;color:var(--heading);margin-bottom:10px}
.stats .k{color:var(--heading)}
.stats .sub{font-size:.8rem;color:var(--muted);margin-top:6px}
table{width:100%;border-collapse:collapse;font-size:.875rem;margin-top:16px;
border-top:var(--rule-section) solid var(--strong);font-variant-numeric:tabular-nums}
th{text-align:left;padding:10px 12px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:9px 12px;border-bottom:1px solid var(--line)}
td.n,th.n{text-align:right;white-space:nowrap}
td.dim{color:var(--muted)} td.pos{color:var(--pos)} td.neg{color:var(--neg)}
tr.total td{font-weight:700;color:var(--heading);border-bottom:var(--rule-section) solid var(--strong)}
table.alloc{table-layout:fixed} table.alloc th:nth-child(1){width:30%}
table.alloc th:nth-child(3){width:12%}
.bar{height:10px;background:var(--sunken);position:relative;min-width:70px}
.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--data)}
.note{color:var(--muted);font-size:.85rem;margin-top:8px}
.scroll{overflow-x:auto}
.scroll::-webkit-scrollbar{height:10px}
.scroll::-webkit-scrollbar-thumb{background:var(--control);border:2px solid transparent;
background-clip:padding-box}
.scroll::-webkit-scrollbar-thumb:hover{background-color:var(--muted)}
footer{margin-top:56px;padding-top:16px;border-top:var(--rule-section) solid var(--strong);
font-size:.75rem;color:var(--faint)}
@media print{.rule{margin-top:32px}}
""")
