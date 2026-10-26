"""Money and notional: a figure's basis, and the total that refuses to mix them."""

from __future__ import annotations

import pandas as pd

from portfusion.record import rules as D


# =====================================================================================
# THE TWO BASES  —  as code rather than as a warning. rules.SPREAD_BET is the definition.
# =====================================================================================
#
# Every published metric is on ONE of two bases — money (what the book has: NAV, capital, income,
# growth) or notional (the size of an economic interest) — and roll_up() refuses to add across
# them, so the wrong sum is impossible rather than forbidden. A spread-bet account contributes its
# EQUITY to NAV and its NOTIONAL to exposure; both are on the frame, and the basis decides which
# total each may touch.
#
# A LINE'S KIND — `shares` / `spread bet`, the register's own words (schema.KINDS) — asks a
# different question: DO WE OWN IT, OR HAVE EXPOSURE TO IT. Not `basis` (what kind of number,
# Book.HEADLINE), `measure`, `evidence` or `contribution`: four names for four questions
# (docs/glossary.md §2). Every frame carries it as `held_as`, the heading a reader meets.
MONEY_KINDS = frozenset({"shares"})
assert MONEY_KINDS < set(D.schema.KINDS), "engine.MONEY_KINDS and the schema disagree"

MEASURE_BASIS = {
    "exposure":       "notional",
    "nav":            "capital",
    "capital_employed": "capital",
    "opening_nav": "capital",
    "capital_deployed": "capital",
    "return_income":  "capital",
    "capital_growth": "capital",
    "income":         "capital",
}


class BasisError(TypeError):
    """Raised when a caller tries to add a notional figure to a money figure."""


class MissingMark(KeyError):
    """No mark on or before a date for a line: `keys` names the mark keys that have none. A
    KeyError, so every caller that catches one still does; `Book.valuation_gaps()` reads the keys
    rather than the sentence."""

    def __init__(self, keys: list[str], message: str):
        super().__init__(message)
        self.keys = keys


def roll_up(frame: pd.DataFrame, *measures: str) -> dict[str, float]:
    """Total the named measures over an account-level frame.

    REFUSES TO ADD ACROSS BASES. Asking for exposure and nav in one call is the
    mistake this function exists to make impossible; ask twice instead.
    """
    unknown = [m for m in measures if m not in MEASURE_BASIS]
    if unknown:
        raise KeyError(f"no basis declared for {unknown}; add it to MEASURE_BASIS")
    bases = {MEASURE_BASIS[m] for m in measures}
    if len(bases) > 1:
        raise BasisError(
            f"refusing to total {list(measures)} together: that mixes "
            f"{sorted(bases)}. Total one basis or the other, "
            f"never a figure from each.")
    # A TOTAL WITH A BLANK IN IT IS BLANK. pandas reads a blank as nothing and returns a figure,
    # and a year whose opening is not yet frozen would open at £0.00.
    return {m: float(frame[m].sum(min_count=len(frame))) for m in measures}
