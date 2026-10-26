"""THE PANEL REGISTRY — a panel joins by existing.

One module per screen, and they do not depend on each other.
Adding a panel is adding a file; reordering is changing one number. Nothing here has a list of
panels in it, because a list is a second place to update.

Each panel module declares:

    NAME    stable id, used in the URL
    TITLE   what the tab says
    ORDER   position, low first
    data()  -> dict, the panel's whole payload
    APART   optional: True for a page off the thread of the work, drawn below a rule

THE TABS RUN IN THE ORDER OF THE WORK: DASHBOARD, where the book stands, is tab one and the
landing screen — `app.js` opens whatever comes first; then the work — BENCH · PRICE REFRESH ·
WHAT CHANGED · RECONCILE; then the book — PERFORMANCE · HOLDINGS · ROUND TRIPS · TRADES ·
ACCOUNTS; then REPORTS, read after the work it reports on, which ends the thread. PRICE REFRESH
PRECEDES WHAT CHANGED because you run a refresh and then read what it did; RECONCILE closes the
work because it reads both. METHOD and ACCESS sit APART, below a rule with no heading: how the
numbers are made and who reads them are not work on the book.

A PANEL HAS ONE NAME: its file, its URL and its title agree (`test_a_panel_has_one_name`).

`data()` MUST NOT COMPUTE A FIGURE. It reaches the engine through `desk.engine` and shapes what
comes back. A panel that does arithmetic is a second calculation of something `engine.py` already
answers.
"""
from __future__ import annotations

import importlib
import pkgutil


def _modules():
    # THROUGH THE DESK'S GUARD: a panel that reads the record on import fails to import when the
    # record will not load, and that is "record unavailable", not a fault in the panel.
    from portfusion.desk.engine import _guarded
    for info in pkgutil.iter_modules(__path__):
        if not info.name.startswith("_"):
            yield _guarded(lambda: importlib.import_module(f"{__name__}.{info.name}"))


def all_panels() -> list:
    """Every registered panel, in ORDER. Discovered, never listed."""
    found = []
    for mod in _modules():
        missing = [a for a in ("NAME", "TITLE", "ORDER", "data") if not hasattr(mod, a)]
        if missing:
            raise AttributeError(
                f"{mod.__name__} is in desk/panels/ but does not declare {missing}. "
                f"A panel joins the desk by existing, so an incomplete one must fail loudly "
                f"rather than be skipped silently.")
        found.append(mod)
    names = [m.NAME for m in found]
    if len(set(names)) != len(names):
        raise ValueError(f"two panels share a NAME: {sorted(names)}")
    return sorted(found, key=lambda m: (m.ORDER, m.NAME))


def heads(mod) -> dict[str, str]:
    """What each column the panel shows is called: every field in its `*COLUMNS` constants, in
    `house/headings.py`'s words for its tab. kit.js draws a table head from this and from nothing
    else, so the desk cannot name a column differently from the report."""
    from portfusion.house.headings import headings
    fields = [f for n in sorted(dir(mod)) if n.endswith("COLUMNS") for f in getattr(mod, n)]
    return headings(mod.TITLE, fields)


def get(name: str):
    for mod in all_panels():
        if mod.NAME == name:
            return mod
    raise KeyError(name)
