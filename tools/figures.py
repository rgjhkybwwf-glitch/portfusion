"""THE DEMO'S HEADLINE FIGURES, WORKED ON TWO CHECKOUTS AND COMPARED: whether a change moves a
figure, made a fact rather than the builder's call (CONTRIBUTING.md, Merging). `tiers.yml` runs it
on a tier-2 pull request, once with the base's code and once with the branch's.

    PORTFUSION_BOOK=demo python3 tools/figures.py > figures.json     every figure of `Book.HEADLINE`,
                                                                     live and at each quarter end
    python3 tools/figures.py base.json branch.json                   the figures that moved, a line
                                                                     each; exits 1 when any did

A figure moves when it differs by more than its unit's rounding: half a penny, half a millionth of
a return, any count; one that appears or goes moves too.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from portfusion.log import log

TOLERANCE = {"gbp": 0.005, "pct": 5e-7, "count": 0}


def work() -> dict[str, dict]:
    """Every headline figure the engine gives on the loaded book, live and at each quarter end the
    store has frozen, keyed `<when> · <key>` by its key in `house/headings.py`, so a heading
    reworded moves no figure; each with its unit from the registry."""
    from portfusion.engine.book import Book
    from portfusion.house import headings as H

    book = Book()
    keys = {label: key for key, label in H.FIGURES.items()} | {book.SINCE_START: "since_start"}
    units = {label: entry["unit"] for label, entry in Book.HEADLINE.items()}
    found = {}
    for when, figures in [("live", book.headline())] + [(q, book.headline(q))
                                                        for q in book.D.QSNAP_FROZEN]:
        for label, value in figures.items():
            found[f"{when} · {keys.get(label, label)}"] = {"value": float(value),
                                                           "unit": units.get(label, "gbp")}
    return found


def moved(base: dict[str, dict], branch: dict[str, dict]) -> list[str]:
    """Each figure whose value differs beyond its unit's rounding, or that only one side has."""
    out = []
    for key in dict.fromkeys([*base, *branch]):
        a, b = base.get(key), branch.get(key)
        if a is None or b is None:
            out.append(f"{key}: {'new' if a is None else 'gone'}")
            continue
        x, y = a["value"], b["value"]
        if (math.isnan(x) != math.isnan(y)) or abs(x - y) > TOLERANCE.get(b["unit"], 0):
            out.append(f"{key}: {x:,.6g} → {y:,.6g}")
    return out


def main(args: list[str]) -> int:
    if not args:
        log.info(json.dumps(work(), indent=1))
        return 0
    base, branch = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args)
    lines = moved(base, branch)
    for line in lines:
        log.info(line)
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
