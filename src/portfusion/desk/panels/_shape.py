"""
SHAPING A FRAME FOR THE BROWSER — the one implementation.

A panel's job is to hand the desk's script a list of plain dicts. Written once per panel, that
drifts the two ways copies always do: one copy gets a bug fix the others do not, and two copies of
one helper under one name come to return different types.

BY COLUMN NAME, NEVER `itertuples()`. `return` is a Python keyword, so pandas renames that
column on a namedtuple and `getattr(row, "return")` is quietly None for every row. Any frame
that grows a column named for a keyword would hit it.

The registry in __init__.py skips modules whose name starts with an underscore, so this file
joins nothing and is only what the panels import.

NOTHING HERE COMPUTES. It converts types and truncates dates; every figure has already been
decided by the engine before it arrives.
"""
from __future__ import annotations

import datetime as _dt
import math
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd


def plain(v):
    """One value as something JSON can carry: NaN becomes None, numpy scalars become Python.

    Side effects: none.
    """
    if isinstance(v, float) and math.isnan(v):
        return None
    return v.item() if hasattr(v, "item") else v


def money(v) -> float | None:
    """A figure to the penny, ONE WAY FOR EVERY PANEL: half-up on the figure as written, as a
    person rounds. None for a missing or NaN figure.

    Python's round() and numpy's disagree on a half-penny, so two pages could show a half-penny
    figure a penny apart.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return float(Decimal(repr(f)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def iso(v) -> str | None:
    """A date-ish value as a bare YYYY-MM-DD string, or None if it is not one.

    Tolerant on purpose: a column that is sometimes NaT and sometimes a Timestamp is normal
    in this book, and a panel should render the rows it has rather than raise.
    """
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
            return None
        return str(v)[:10]
    except (TypeError, ValueError):
        return None


def rows(frame: pd.DataFrame, columns, dates=()) -> list[dict]:
    """`frame` as a list of JSON-safe dicts, one per row, holding exactly `columns`.

    `dates` names the columns to truncate to YYYY-MM-DD. A column in `columns` that the
    frame does not carry comes back as None rather than raising — a panel showing a subset
    of a wider frame is ordinary.

    BY COLUMN NAME, never itertuples. See the module docstring: itertuples renames any
    column that is a Python keyword, and `return` is one of them.

    Side effects: none. The frame is not mutated.
    """
    out = []
    for record in frame.to_dict("records"):
        row = {c: plain(record.get(c)) for c in columns}
        for d in dates:
            if d in row:
                row[d] = iso(row[d])
        out.append(row)
    return out


def uniques(frame: pd.DataFrame, col: str) -> list[str]:
    """The sorted distinct non-blank values of one column, as strings — a filter dropdown.

    Coerced with str() so the list is one type whatever the column holds. Side effects: none.
    """
    return sorted({str(v) for v in frame[col].dropna().tolist() if str(v).strip()})


def company_codes(frame: pd.DataFrame) -> dict[str, list[str]]:
    """Each company in a frame with a `company` and a `ticker` column, and its codes there,
    sorted: a Ticker dropdown narrowed to the company chosen beside it."""
    codes: dict[str, set] = {}
    for company, code in zip(frame["company"], frame["ticker"]):
        if isinstance(company, str) and isinstance(code, str) and code.strip():
            codes.setdefault(company, set()).add(code)
    return {c: sorted(v) for c, v in sorted(codes.items())}


def accounts(frame: pd.DataFrame, col: str, order) -> list[str]:
    """The accounts appearing in a column, in the book's canonical order.

    A HOLDINGS ROW NAMES EVERY ACCOUNT ITS TICKER SITS IN, joined with " · " so no sub-rows
    double-count. Split on that separator: split on anything else and each COMBINATION becomes a
    dropdown entry of its own — three accounts' names joined by the separator, offered as though
    it were an account, returning zero rows because no account is called that.

    AND THE ORDER IS THE RECORD'S, NOT THE ALPHABET'S. `sorted()` can put a spread-bet account
    between two share accounts, so a spread-bet account sits among the share ones and
    the break between the two valuation bases disappears. `order` is the record's own
    sequence; anything outside it is appended rather than dropped, because a value the record
    does not know is a finding and not a thing to hide.
    """
    seen = set()
    for v in frame[col].dropna().tolist():
        for part in str(v).split("\u00b7"):
            if part.strip():
                seen.add(part.strip())
    known = [a for a in order if a in seen]
    return known + sorted(seen - set(order))


def reading(document, day) -> str:
    """What a figure was read from, as the desk and the report name it: the document, then its
    day — "IG account read, 12 Oct 2026". Reconcile's last broker check and Accounts' cash."""
    return (f"{document or 'not a classified document'}, "
            f"{_dt.date.fromisoformat(str(day)[:10]):%-d %b %Y}")
