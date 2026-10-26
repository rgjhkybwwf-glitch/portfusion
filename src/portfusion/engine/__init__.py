"""
engine — THE ENGINE.

Events in, book out: one implementation of every derived figure, so every caller asking the same
question gets the same answer. The renderers — the desk and the report — read from here and
compute nothing of their own (tests/test_figures.py), and `Book.HEADLINE` registers
every headline figure with its basis and unit.

It reads the record through ONE seam, `load_store()`, and imports only pandas and the record's
rules (tests/record/test_store_doors.py).

THE BASIS IS A COLUMN, NOT A WARNING: a figure is money or notional, and roll_up() refuses to add
across the two.

PANDAS TRAPS, 1–3 commented where they bite:
  1. `r.mode` in `df.apply(axis=1)` is `Series.mode`, the METHOD — silently truthy. Use `r["mode"]`.
  2. A share sale from a holding still held is VALUED at minus its quantity: two flags, not one.
  3. A pooled S.104 disposal releases cost from a position that stays OPEN — `share_pools()`.
  4. pandas 3.0's `str` dtype refuses a `datetime.date`; convert with isoformat().

New to pandas? A DataFrame is a table in memory. `df["cost"].sum()` totals a column;
`df[df.direction == "Buy"]` filters rows; `df.groupby("account")["amount"].sum()` totals by
account; `a.merge(b, on="realisation_id")` joins two tables. Most of the engine is those four.

| File | Holds |
|---|---|
| `store.py` | 1 · the store, and the baseline |
| `bases.py` | the two bases |
| `ledger.py` | 2 · the derived ledger |
| `valuation.py` | 3 · valuation |
| `core.py` | a Book's construction, which every topic class below builds on |
| `book.py` | 4 · `Book`: its headline figures and `HEADLINE`; the rest of its methods, by topic: |
| `positions.py` | the marks, identity, holdings, the judgement, allocation |
| `trades.py` | round trips, the company life, investment activity |
| `accounts.py` | the register, account level, money in and out |
| `reconciliation.py` | reconciliation |
| `quarters.py` | the quarter ends, the returns |
| `past.py` | valuing at a past date, what moved |
| `findings.py` | record time, what the record needs today |
"""

from __future__ import annotations

from portfusion.engine.store import load_store, record_begins, uk_instant, utc_of
from portfusion.engine.bases import MEASURE_BASIS, MONEY_KINDS, BasisError, MissingMark, roll_up
from portfusion.engine.ledger import build_ledger, cost_released, realised_legs, share_pools
from portfusion.engine.valuation import rate_now, value_legs
from portfusion.engine.book import Book

__all__ = ["BasisError", "Book", "MEASURE_BASIS", "MONEY_KINDS", "MissingMark", "build_ledger",
           "cost_released", "load_store", "rate_now", "realised_legs", "record_begins", "roll_up",
           "share_pools", "uk_instant", "utc_of", "value_legs"]
