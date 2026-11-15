"""house/words.py — what a house word is called on screen.

ONE PLACE FOR A WORD THE DESK SHOWS IN THE READER'S TERMS. The guides and the store keep the
house's own word (`docs/glossary.md`); a page says the plain one, and says it from here, so the
two cannot drift.

RETIRED_FOR_DISPLAY holds the words the desk never shows, each with what it says instead:
`tests/test_figures.py` refuses one in any desk string. WORDS holds the plain words for a house
term, each with its unit; the desk sends them to the page with every panel answer.

Imports nothing.
"""
from __future__ import annotations

#: A store and guide word the page never shows, and what it says instead (glossary §5).
RETIRED_FOR_DISPLAY = {
    "mark": "price",
    "marks": "prices",
    "marked": "priced",
    "marking": "pricing",
}

#: A house term, as the page says it.
WORDS = {
    "modified_dietz": "a day-weighted return on money",
    "share_equivalents": "shares, a bet counted as the shares it stands for",
    "pre_baseline": "entered before the record began",
}
