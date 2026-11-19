"""house/mark.py — PortFusion's name, the lockup a page wears, and its stand-in mark.

THE LOCKUP is the wordmark: PortFusion's name, which every book's pages wear. Each renderer sizes
it in its own stylesheet, by the classes `lockup`, `wordmark` and `name`, and gives it the palette's
`mark` colour, which nothing in it wears until PortFusion has a mark.

THE STAND-IN MARK is a ring on a graphite tile, which `desk/icon.py` draws as the desk's icons:
rounded for a tab, square and opaque for the Dock and a home screen, which draw their own corner.
It stands until PortFusion has a mark, and its proportions are here as data, each a fraction of
the icon's side.

Imports nothing.
"""

#: The app's name, wherever a page says what it is: the lockup, a tab, the Dock, a report's title.
NAME = "PortFusion"

#: The ring's radius to the middle of its stroke, and the stroke's width.
RING_RADIUS, RING_STROKE = 0.27, 0.09
#: The tab icon's corner radius. The app icons are square.
TILE_RADIUS = 0.17


def lockup() -> str:
    """The wordmark, read by a screen reader as the name once."""
    return (f'<span class="lockup" role="img" aria-label="{NAME}">'
            f'<span class="wordmark"><span class="name">{NAME}</span></span></span>')
