"""house/mark.py — the lockup a page wears, and PortFusion's stand-in mark.

THE LOCKUP is the mark beside the wordmark: the mark first, if the book's brand has one, then
the wordmark's lines, the name and a smaller line under it. Each renderer sizes it in its own
stylesheet, by the classes `lockup`, `wordmark`, `name` and `sub`, and colours the mark through
`currentColor`. The words and the mark are `portfusion.brand`'s; this only sets them out.

THE STAND-IN MARK is a ring on a graphite tile, which `desk/icon.py` draws for a book whose brand
gives no icons of its own: rounded for a tab, square and opaque for the Dock and a home screen,
which draw their own corner. It stands until PortFusion has a mark, and its proportions are here
as data, each a fraction of the icon's side.

Imports nothing, like the rest of house/.
"""
import html

#: The ring's radius to the middle of its stroke, and the stroke's width.
RING_RADIUS, RING_STROKE = 0.27, 0.09
#: The tab icon's corner radius. The app icons are square.
TILE_RADIUS = 0.17


def lockup(label: str, lines: tuple[str, ...], svg: str = "") -> str:
    """The mark and the wordmark together, read by a screen reader as `label` once."""
    name, *sub = lines
    words = f'<span class="name">{html.escape(name)}</span>' + "".join(
        f'<span class="sub">{html.escape(s)}</span>' for s in sub)
    return (f'<span class="lockup" role="img" aria-label="{html.escape(label)}">'
            f'{svg}<span class="wordmark">{words}</span></span>')
