"""The ledger's legs at their marks and rates."""

from __future__ import annotations

import pandas as pd

from portfusion.record import rules as D
from portfusion.engine.bases import MissingMark
from portfusion.engine.ledger import _buy_cost


# =====================================================================================
# 3 · VALUATION
# =====================================================================================

def _price_lookup():
    return {r[0]: r[1] for r in D.CURRENT_PRICES}


def _rate_now_lookup(record=None):
    """Currency -> the rate the book converts it at RIGHT NOW: fx.csv, one row per currency.

    FROM THE TABLE, not a list: a list would let a missing currency fall to PARITY, silently. A
    new currency joins by having a row.
    """
    return {cur: rate for cur, rate, *_ in (record or D).fx_rows}


def rate_now(cur: str, record=None) -> float:
    """THE ONE ANSWER to "what rate does this book convert `cur` at now". GBP per unit.

    Every present-tense figure comes through here — `value_legs()` and `changes_since()`'s
    `value_to` — so two readings of one figure cannot use two rates. A DATED figure does NOT:
    `_marks_at()` answers that, because a past valuation has to reproduce next year.

    Raises for an unknown currency rather than assuming parity: 1.0 is a real rate and a
    plausible wrong answer.
    """
    if cur == "GBP":
        return 1.0
    rates = _rate_now_lookup(record)
    if cur not in rates:
        raise KeyError(
            f"no live rate for {cur}. fx.csv carries a `-NOW` row per convertible currency; "
            f"it has {sorted(rates)}. A figure cannot be converted at a rate nobody banked.")
    return rates[cur]


def value_legs(ledger: pd.DataFrame) -> pd.DataFrame:
    """Attach cost and current market value to every leg.

    Two valuation routes, never merged:
      * Share      -- qty x price / fx      (price is local, fx is GBP-per-unit)
      * Spread bet -- stake x level         (sterling at parity; the ledger's qty is the stake)

    BRACKET ACCESS — r["mode"], never r.mode: `.mode` is the pandas METHOD, every comparison
    against it is silently False, and every spread bet becomes worth nothing.
    """
    px = _price_lookup()
    # A MARK CONVERTS AT ITS SHARE'S CURRENCY, never the deal's: a deal's `cur` is the
    # currency its price was stated in — sterling on an HL deal in a US share — so every leg is
    # priced in the currency its identity row quotes the holding in.
    _h = D.schema.TABLES["securities"].header
    quote = {r[_h.index("ticker")]: r[_h.index("currency")] for r in D.SECURITIES}

    def cost(r):
        """Cost attaches to OPEN BUY LEGS, and comes off by what each share sale from a holding
        still held released."""
        if r["direction"] == "Sell":
            return -r["released"] if r["valued"] else 0.0
        if not r["open_leg"]:
            return 0.0
        return _buy_cost(r["qty"], r["cost"], r["level_points"], r["mode"])

    def market(r):
        """Market value attaches to VALUED legs -- open buys, less each share sale from a holding
        still held."""
        if not r["valued"]:
            return 0.0
        if r["mode"] == "sb":
            contract = D.LEG_CONTRACT[r["event_id"]]
            if contract not in px:
                raise MissingMark([contract],
                                  f"{r['event_id']} is open on {contract}, which has no "
                                  f"mark: take one on the Price Refresh first.")
            return r["qty"] * px[contract]
        if r["held_as"] == "shares":
            sign = -1 if r["direction"] == "Sell" else 1
            return sign * r["qty"] * px[r["ticker"]] / rate_now(quote[r["ticker"]])
        return 0.0

    out = ledger.copy()
    out["gbp_cost"] = out.apply(cost, axis=1)
    out["gbp_value"] = out.apply(market, axis=1)
    return out
