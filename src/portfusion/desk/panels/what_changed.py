"""WHAT CHANGED — on both clocks, each block saying which.

The question this panel answers is TWO questions on two clocks, and the difference is the
whole design: what moved since the last price refresh, and what the book learned when a document
was worked — a cash position, a contract note — where, why and when.

MARKET TIME is what the MARKS did: each line against its own previous banked mark. RECORD TIME
is what the BOOK LEARNED: every write to the store, from `journal.csv`.

ONE SCREEN, TWO BLOCKS, EACH NAMING ITS CLOCK — never one merged list. A mark banked this week
and a dividend entered weeks after it was paid sit side by side on the page and answer different
questions; unlabelled, a reader has no way to tell which sense of *when* is being used. The
glossary states it as a rule (§4); this is the rule in the layout.

EVERY FIGURE IS `Book.changes_since()`'s. This module filters and labels; it does not add up.
The two block totals are `Book.change_totals()` and the heading dates are
`Book.change_windows()`, both for the same reason — a panel that computed either would be a
second answer to something the engine already decides.

TWO BLOCKS, NEVER ONE TOTAL. The LEVEL of total market exposure is registered in
`Book.HEADLINE` and carries its basis there; its DECOMPOSITION is not, and cannot be: a combined
`transacted` row would add spread-bet notional to money. `change_totals()` raises `BasisError`
rather than return it, so the panel shows the two bases apart and never sums them — the book's
oldest rule, arriving in a new place.
"""
from __future__ import annotations

from portfusion.desk import engine
from portfusion.desk.panels import _shape
from portfusion.engine import uk_instant

NAME = "what-changed"
TITLE = "What Changed"
#: STRAIGHT AFTER THE PRICE REFRESH, because it is where the refresh loop ENDS: the Price Refresh
#: writes the marks and this says what they did. The write itself lands you here.
ORDER = 27

#: What each row shows. `mark_key` is the MARK KEY — the contract for a spread bet, the ticker for a
#: share — because that is where a price lives; `company` is beside it so a reader meets Halvard
#: rather than only HALV-MAR27.
#:
#: THE ROW ADDS UP LEFT TO RIGHT: the mark's move in per cent beside the
#: pounds it made, then the other two parts, then `change`, their sum, then where the line
#: landed. The two dates come last: they are the row's provenance, not its subject, and they
#: differ per line because the marks can.
COLUMNS = ("mark_key", "company", "price_move_pct", "price_effect", "fx_effect", "transacted",
           "change", "value_to", "priced_from", "priced_at")

#: A SPREAD BET HAS NO FX PART. It is sterling at parity, so its From FX is nought on every line
#: and in the total by construction; the notional block leaves the column and the figure out.
#: Drawn, the two blocks share COLUMNS as one grid (`grid`), so a figure sits under its fellow;
#: the column a block does not carry is drawn as a dash.
NOTIONAL_COLUMNS = tuple(c for c in COLUMNS if c != "fx_effect")

#: The two kinds of line, in the record's own words (`schema.KINDS`, glossary §2).
#:
#: THE LABEL CARRIES THE BASIS. The heading says it, in the words Holdings' figures use.
BLOCKS = (("shares", "Shares", COLUMNS),
          ("spread bet", "Spread bets", NOTIONAL_COLUMNS))

CAVEAT = ("Market time runs from each line's own previous banked mark to its live one, or to its "
          "close if it closed in between.")

#: What a journal row shows. `at` is RECORD TIME and leads, because that is the axis this block
#: is ordered on and the one thing distinguishing it from everything above it.
JOURNAL_COLUMNS = ("at", "route", "op", "table", "rows", "ref", "detail")

RECORD_CAVEAT = (
    "Record time is when the book learned a thing, not when it happened: a July dividend "
    "entered in September appears here in September. Forward-only — the journal reaches back to "
    "the day it opened, and the writes it was seeded from.")


def data() -> dict:
    b = engine.book()
    frame = b.changes_since()
    return {
        "windows": b.change_windows(),
        "blocks": [_block(b, frame, *block) for block in BLOCKS],
        "grid": list(COLUMNS),
        "caveat": CAVEAT,
        "record": _record(b),
    }


def _record(b) -> dict:
    """The record-time half: every write the book has journalled, newest first.

    OVER THE SAME SPAN AS THE MARKS: the writes since the earliest window above opened, and
    the rest apart, as `earlier`. The journal grows with every write, and what the book learned
    since the last refresh is the half that answers this page's question.

    EVERYTHING HERE IS `Book.journal()`'s AND `Book.journal_reconciliation()`'s. This selects
    and labels; it counts nothing. The reconciliation in particular is arithmetic over the
    whole store and belongs to the engine — a panel adding up `rows` by table would be a
    second answer to the question `portfusion record` already prints.

    THE OPENING COUNTS ARE NOT LISTED and the engine excludes them: they record what was
    already on file, so showing them beside real writes would fill the journal's first day with
    entries the book learned nothing from. The DATE is shown instead, once, because a reader has
    to know how far back this reaches.
    """
    off = b.journal_unaccounted()
    since = b.change_opened()
    opened = b.journal_opened()
    return {
        "opened": _uk_at(opened) if opened else None,
        "since": since,
        "rows": _uk(_shape.rows(b.journal(since=since), JOURNAL_COLUMNS)),
        "earlier": _uk(_shape.rows(b.journal(before=since), JOURNAL_COLUMNS)) if since else [],
        "columns": list(JOURNAL_COLUMNS),
        # WHAT NO ROUTE ACCOUNTS FOR — the hand edits. A finding and never a failure: the
        # record allows a hand edit with a commit message, and this makes one visible rather
        # than objecting to it.
        "unaccounted": _shape.rows(off, ("table", "expected", "on_file", "unaccounted")),
        "caveat": RECORD_CAVEAT,
    }


def _block(b, frame, held_as: str, label: str, columns: tuple) -> dict:
    """One basis: its totals from the engine, and its lines already ordered by the engine.

    The rows arrive biggest-mover-first within a basis, which is `changes_since()`'s own
    ordering — the frame answers "what moved", so the order is part of the answer.
    """
    totals = b.change_totals(held_as=held_as)
    lines = frame[frame["held_as"] == held_as]
    return {
        "held_as": held_as,
        "label": label,
        "totals": totals,
        "columns": list(columns),
        "rows": _shape.rows(lines, columns, dates=("priced_from", "priced_at")),
    }


def _uk_at(at: str) -> str:
    """One instant as UK wall-clock time (`engine.uk_instant`): the journal keeps UTC, and a
    reader reads the clock they keep."""
    return uk_instant(at)


def _uk(rows: list[dict]) -> list[dict]:
    return [{**r, "at": _uk_at(r["at"])} for r in rows]
