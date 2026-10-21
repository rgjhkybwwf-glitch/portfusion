"""What more than one file in tests/ reads about the frozen quarters.

A MODULE, NOT A FIXTURE: `parametrize` needs the list at collection, before any fixture
exists. Imported by name, the way tests/desk/desk_support.py is.
"""
from portfusion.record import rules as D


def frozen_quarters():
    """(as_of, rows) for every quarter frozen in store/quarter-snapshots.csv — DERIVED from
    `rules.QSNAP_FROZEN`, never listed, so a new freeze is checked from its first row.

    Rows take the record's shape — (account, ticker, qty, ...).

    Reads the store at call time, so it follows `rules.set_store()`.
    """
    rows = D.live_rows("quarter-snapshots")
    return [(as_of, [tuple(r[1:]) for r in rows if r[0] == as_of]) for as_of in D.QSNAP_FROZEN]


def perf_recon_q2_rows():
    """The reconstructed holdings at 30 June 2026, from baseline-reconstruction.csv: the
    rows the published Q2 figure is built from, (ticker, qty, price, source, fx, quality)."""
    return [tuple(r[1:]) for r in D.dec_rows if r[0] == "2026-06-30"]


def book_in_the_next_year(frozen: bool):
    """A Book valued in the January after its own newest mark: the year end the record has not
    reached yet. `frozen` gives that 31 December the newest quarter end's rows, as a freeze
    would; without it there is nothing yet to open the year from.

    IN MEMORY ONLY. The Book gets its own copy of the table, and nothing reaches the store.
    """
    import pandas as pd
    from portfusion.engine import Book
    b = Book()
    year = b.ytd_year() + 1
    opens = f"{year - 1}-12-31"
    q = b.store["quarter_nav"]
    q = q[q["as_of"] != opens]
    if frozen:
        q = pd.concat([q, q[q["as_of"] == q["as_of"].max()].assign(as_of=opens)],
                      ignore_index=True)
    b.store = {**b.store, "quarter_nav": q}
    b.valued_at = lambda: f"{year}-01-15"
    return b
