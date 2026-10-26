"""What every Book is built on: the record it pins, its frames and its baseline."""

from __future__ import annotations

import pandas as pd

from portfusion.record import rules as D
from portfusion.engine.store import load_store
from portfusion.engine.ledger import build_ledger, cost_released
from portfusion.engine.valuation import value_legs


class _Pinned:
    """The record's names as they stood when a Book was built.

    `rules.reload_store()` REBINDS the module's names to a new build rather than changing the
    old one, and a function or row class among them answers from the build it was made in, so
    references taken here keep the record the Book's frames came from. A reference, not a copy:
    nothing is duplicated. `store_rows()` reads the files, not the record, and the Book takes it
    once, when it is built.
    """

    def __init__(self, module):
        self.__dict__.update(vars(module))


class Core:
    """The Book's construction, and the state every topic class reads through `self`."""

    @property
    def baseline(self) -> pd.Timestamp:
        """The day this Book's record begins: its own setting, pinned with the rest of the record
        it was built from, so a Book of another store, or one built after the setting changed,
        is measured from its own start, not from the date the loaded book held at import."""
        return pd.Timestamp(self.D.RECORD_BEGINS)

    @property
    def baseline_asof(self) -> str:
        """The baseline's quarter-end key: the day before the record begins, as an ISO date."""
        return (self.baseline - pd.Timedelta(days=1)).date().isoformat()

    def __init__(self, store_dir=None):
        """`store_dir` builds the Book from another store. The process's record is pointed there
        for the construction and put back after (`rules.store_at()`), so another thread reading
        the record meanwhile would see the other store; nothing in the build or the desk does.
        """
        if store_dir is None:
            self._build()
            return
        with D.store_at(store_dir):
            self._build()

    def _build(self):
        self.D = _Pinned(D)
        self.store = load_store()
        self.ledger = value_legs(build_ledger())
        self.cost_released = cost_released(self.ledger)
        self._cash_latest = D.cash_latest()
        # THE CASH AT EACH READING'S DATE, for a share reading whose document states none.
        self._cash_at_reading = {r.acct: D.cash_latest(on=r.as_of).get(r.acct)
                                 for r in D.ac_rows if r.as_of}
        self._rows_on_file = D.store_rows()

        # Held quantity walks the whole ledger, and holdings_at() asks once per ticker. Keyed by
        # DATE AND ACCOUNT: the date alone would hand one account's caller the whole book's legs —
        # an answer correct in itself, which is the worst kind of wrong to cache.
        self._held_cache: dict[tuple[str, str | None], dict[str, dict]] = {}

        # changes_since() walks the ledger twice per line, and What Changed asks for the frame
        # and both basis totals. Keyed by what the answer depends on, as above.
        self._changes_cache: dict[tuple[str | None, str | None], pd.DataFrame] = {}

        # The company lives walk the whole ledger and their income, and the Round Trips life view,
        # its totals and rate_gaps() all ask: walked once per Book, which is built once per store.
        self._lives_cache: dict[str, object] = {}
