"""HOLDINGS — what is owned, and what is merely an interest.

It can be asked by issuer or by ticker, and for one account or all of them. **The grouping is
the engine's** —
`book.holdings(account, by)` and `book.allocation(by, account)` already take those arguments,
and re-implementing a group-by here would be a second answer to a question the engine answers.

EVERY ROW SAYS WHAT IT IS HELD AS, in the record's two words (schema.KINDS) and `mixed` for an
issuer row holding both: the engine's own `held_as` column, reported as it stands. A share
position's `value` is its market value and a spread bet's is its NOTIONAL (rules.SPREAD_BET),
and the two must never be added into a figure called capital — the two figures at the top are
the engine's, apart. This panel classifies nothing.
"""
from __future__ import annotations


from portfusion.desk import engine
from portfusion.desk.panels import _shape
from portfusion.house.headings import headings

NAME = "holdings"
TITLE = "Holdings"
ORDER = 40

#: How a holding may be grouped. The engine's own vocabulary, not this module's.
#:
#: `issuer` IS THE ONLY ONE THAT COLLAPSES TWO BASES INTO ONE ROW — a company held as XYZ and as
#: XYZ SB is one line at issuer level, carrying one basis label. Every other grouping keeps the
#: partition and its rows sum to the engine's own owned/exposure figures exactly. So `ticker` is
#: the default and the screen opens with nothing withheld; issuer-level exposure is one choice
#: away, its totals still the engine's and its collapsed rows marked.
#
# TWO, BECAUSE THE ENGINE GROUPS BY TWO. `book.holdings(by=)` decides one thing:
# `key = "company" if by == "issuer" else "ticker"`. Any other axis offered here would change the
# dropdown and nothing else.
#
# THE OTHERS ARE NOT BUILT, deliberately. Grouping value by sector would sum owned money and
# spread-bet notional into one cell, the sum the basis split exists to refuse.
# Every other axis is answered correctly elsewhere on this panel: currency, region and sector by
# the allocation breakdown below the table; account by the account filter beside this control; type by the
# two figures at the top, which are the basis split and are never added.
GROUPINGS = ("ticker", "issuer")
#: EACH GROUPING IN THE READER'S WORD: the engine's `issuer` is the glossary's Company, the word
#: every page heads the column with.
GROUPING_WORDS = {"ticker": "ticker", "issuer": "company"}

COLUMNS = ("ticker", "company", "held_as", "accounts", "currency", "entry_price",
           "price", "priced_at", "cost", "value", "unrealised", "unrealised_pct", "weight",
           "opened", "days_held")

#: WHAT ONLY A TICKER ROW HAS: an issuer row can be several instruments, so it has no single
#: ticker. Grouped by issuer the column is not sent, rather than sent empty.
BY_TICKER_ONLY = ("ticker",)

#: How much is held. A share line carries its count and a spread bet its stake per point, never
#: both; an issuer row is one position, its count in shares with bets as share-equivalents.
HELD_COLUMNS = ("qty", "stake")

#: The mark's own history, as the expansion shows it. `source` is the point of opening it: it
#: carries the corroboration and the symbol actually queried. `mark_key`, never `ticker` — a
#: contract is not an instrument.
#:
#: THE LAST FIVE REFRESHES, NOT EVERY MARK: enough to see the trend under the value, which What
#: Changed and the charts carry further. Every mark stays on file, because a past valuation, What
#: Changed and the IG checks are worked out from them. Whether a mark is a close, a bid or a
#: reconstruction its source already says, so `quality` and `struck` are not drawn; a mark a
#: later read of its day replaced is not on file at all. Its price prints as Holdings' own do: a
#: spread bet's `level` in points, a share's at its currency's places, house/precision.py's.
MARK_COLUMNS = ("date", "mark_key", "price", "currency", "source")
MARK_REFRESHES = 5


#: THE JUDGEMENT under each line, in its detail: `Book.with_reasoning()`'s, by ticker —
#: every why dated since the position opened, oldest first. An issuer row carries one entry per
#: instrument it collapses, because each has its own. Whether a thesis is OWED is the engine's
#: flag (`why_entered_owed`), never decided here.
REASON_COLUMNS = ("whys", "research_notes")

#: WHAT A ROW'S DETAIL OPENS, under kit.js's one desk-wide order: the whys, the research notes,
#: then the mark history (`marks`, MARK_COLUMNS' table).
DETAIL_COLUMNS = ("why_entered", "why_exited", "research_notes", "marks")

#: WHERE THE EXPOSURE SITS, under the table: the report's split, in its order and its words
#: (house/headings.py's Dashboard ones, as the report's `_allocation` heads them).
ALLOCATION_AXES = ("currency", "region", "sector")
ALLOCATION_HEADS_TAB = "Dashboard"


def data() -> dict:
    return query()


def query(account: str | None = None, by: str = GROUPINGS[0]) -> dict:
    """Interrogate the holdings. Both arguments go straight to the engine."""
    if by not in GROUPINGS:
        raise ValueError(f"group by {by!r}; the engine groups by {GROUPINGS}")
    b = engine.book()
    frame = b.holdings(account=account or None, by=by)
    owned, notional = _split(b, account)
    columns = _columns(by)

    return {
        "rows": _rows(frame, columns, b, by, account or None),
        "columns": columns,
        "mark_columns": list(MARK_COLUMNS),
        "detail": list(DETAIL_COLUMNS),
        "groupings": list(GROUPINGS),
        "grouping_words": GROUPING_WORDS,
        "by": by,
        "account": account or "",
        "accounts": _shape.accounts(b.holdings(), "accounts", b.account_order()),
        "total": int(len(frame)),
        "valued_at": b.valued_at(),
        "owned": owned,
        "notional": notional,
        # EVERY GROUPING SAYS WHAT ITS ROWS ARE, and that is a layout decision as much as an
        # editorial one. A note that grows and shrinks with the grouping moves the controls and
        # the table under it; a note that is always the same shape does not, and each grouping
        # has something true and worth saying anyway.
        "note": ("Securities owned and spread-bet notional are shown apart and never added. A "
                 "spread bet's value is its notional; the equity behind it is the account's. "
                 + ("Grouped by company, one held both ways is one row, held as mixed, so "
                    "the column is not a split by basis; the two figures above are the engine's."
                    if by == "issuer" else
                    "Grouped by ticker, each row is one instrument, so a company held both "
                    "ways appears twice and no single line is that company's total.")),
        "allocation": _allocation(b, account),
        "allocation_heads": headings(ALLOCATION_HEADS_TAB, (*ALLOCATION_AXES, "share")),
    }


def _marks(history) -> list[dict]:
    """The marks of the line's last MARK_REFRESHES refresh dates, newest first, in the engine's
    order. Selection: the engine's rows, fewer of them."""
    days = sorted(set(history["date"]), reverse=True)[:MARK_REFRESHES]
    return _shape.rows(history[history["date"].isin(days)], MARK_COLUMNS + ("level",),
                       dates=("date",))


def _split(b, account) -> tuple:
    """Securities owned and notional. THE ENGINE'S FIGURES, never a sum of the rows above.

    SUMMING THE ROWS IS WRONG BY ISSUER. Grouped by issuer, a company held both ways (XYZ and
    XYZ SB) collapses to ONE row carrying ONE basis label, so the label stops being
    a partition and summing on it misstates both sides. Every other grouping ties exactly;
    `issuer` is the one that does not, which is precisely why the figure must not be worked out
    here. Ask the engine.
    """
    if not account:
        return _shape.money(b.owned()), _shape.money(b.exposure())
    # PER ACCOUNT, the engine's own split is by_account()'s `held_as` — a shares account's
    # exposure IS its securities owned; a spread-bet account's is its notional. Reading a column
    # the engine already computed is selection, not calculation.
    for r in b.by_account().itertuples(index=False):
        if str(r.account) == account:
            value = _shape.money(r.exposure)
            return (value, 0.0) if str(r.held_as) == "shares" else (0.0, value)
    return 0.0, 0.0


def _allocation(b, account) -> dict:
    """The engine's allocation, one breakdown per axis in ALLOCATION_AXES, largest slice first.
    `share_of_largest` is the bar's length, the engine's, so the desk's script divides
    nothing."""
    out = {}
    for axis in ALLOCATION_AXES:
        frame = b.allocation(by=axis, account=account or None)
        out[axis] = [{"key": _shape.plain(getattr(r, axis, None)),
                      "value": _shape.plain(getattr(r, "value", None)),
                      "share": _shape.plain(getattr(r, "share", None)),
                      "share_of_largest": _shape.plain(getattr(r, "share_of_largest", None))}
                     for r in frame.itertuples(index=False)]
    return out


def _columns(by: str) -> list[str]:
    """COLUMNS for this grouping: all of them by ticker, less BY_TICKER_ONLY by issuer."""
    return [c for c in COLUMNS if by == "ticker" or c not in BY_TICKER_ONLY]


def _rows(frame, columns: list, b, by: str, account) -> list[dict]:
    out = _shape.rows(frame, columns, dates=("opened", "priced_at"))
    held = _shape.rows(frame, HELD_COLUMNS)
    key_col = "company" if by == "issuer" else "ticker"
    keys = list(frame[key_col])
    reasons: dict = {}
    for r in _shape.rows(b.with_reasoning(b.holdings(account=account, by="ticker")),
                         REASON_COLUMNS + ("ticker", "company", "why_entered_owed")):
        reasons.setdefault(r[key_col], []).append(r)

    for row, key, size in zip(out, keys, held):
        row.update(size)
        row["marks"] = _marks(b.mark_history(key, by=by, account=account))
        row["reasons"] = reasons.get(key, [])
    return out
