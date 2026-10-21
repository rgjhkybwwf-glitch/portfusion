"""THE DESK'S OWN ICONS — PortFusion's stand-in mark, for a book whose brand gives none.

    from desk.icon import png
    png(64)                  # the tab's: rounded corners, RGBA
    png(512, square=True)    # the Dock's and a home screen's: square and opaque, RGB

WHY IT IS A MODULE OF ITS OWN. The page names `/favicon.png` as its icon, and drawing it in
`app.py` would make the routing module compute something, which is the one thing it does not do.
A book whose `brand/` holds icons serves those instead, and nothing here runs:
`desk/bundle.py` says which surface takes which.

THE MARK is `house/mark.py`'s ring on a tile, in proportions held there. The two colours are the
desk's `field` and `on-field`, read through `desk.theme` each time an icon is drawn — so a change
to the screens' colours moves the desk's CSS and the icons together, or neither.
`tests/desk/test_routes.py` changes the palette and checks the icon follows.

PURE STDLIB, AND IT WRITES NOTHING. A PNG is a zlib stream with a header, so this returns bytes
and adding a drawing library for one icon would be a poor trade. A ring and a rounded corner are
distances from a centre, so each pixel's coverage is computed rather than sampled, which keeps
the 512px icon quick. The corners outside a tab's tile are transparent. The palette and the mark
are read when an icon is drawn, never at import, so importing this module needs nothing but the
standard library. `tests/desk/test_boundaries.py` pins the set of modules under `desk/` that
write anything; this one is not among them and must not join.
"""
from __future__ import annotations

import functools
import math
import struct
import zlib

#: Which palette token each part of the mark wears. The tokens are `desk.theme`'s; the colours
#: behind them are house/palette.py's and the brand's, and are never written down here.
ROLES = {
    "tile": "field",        # the ground
    "ring": "on-field",     # the ring, on the field
}


def colours() -> dict[str, tuple[int, int, int]]:
    """The mark's two colours as RGB, read from the desk's palette now."""
    from portfusion.desk import theme
    palette = theme.palette()
    return {part: tuple(int(palette[token][i:i + 2], 16) for i in (1, 3, 5))
            for part, token in ROLES.items()}


def png(size: int, square: bool = False) -> bytes:
    """The stand-in mark, `size` pixels square: on a rounded tile with transparent corners, or
    `square`, opaque to every edge.

    Side effects: none. Returns the file's bytes.
    """
    c = colours()
    return _draw(size, square, c["tile"], c["ring"])


def _clamp(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else v


@functools.lru_cache(maxsize=16)
def _draw(size: int, square: bool, tile: tuple, ring: tuple) -> bytes:
    from portfusion.house import mark

    centre = size / 2
    radius, half = mark.RING_RADIUS * size, mark.RING_STROKE * size / 2
    corner = mark.TILE_RADIUS * size
    rows = []
    for py in range(size):
        row = bytearray(b"\x00")                      # filter byte: None
        y = py + 0.5
        for px in range(size):
            x = px + 0.5
            on_ring = _clamp(half + 0.5 - abs(math.hypot(x - centre, y - centre) - radius))
            rgb = bytes(round(t + (r - t) * on_ring) for t, r in zip(tile, ring))
            if square:
                row += rgb
                continue
            # Inside the rounded square: the distance past the corner's own circle, where a
            # pixel sits in a corner at all.
            dx = max(corner - x, 0, x - (size - corner))
            dy = max(corner - y, 0, y - (size - corner))
            on_tile = _clamp(corner + 0.5 - math.hypot(dx, dy)) if dx and dy else 1.0
            row += rgb + bytes([round(255 * on_tile)])
        rows.append(bytes(row))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2 if square else 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
            + chunk(b"IEND", b""))
