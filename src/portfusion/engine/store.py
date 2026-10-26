"""The engine's one seam into the store, and the day the record begins."""

from __future__ import annotations

import pandas as pd

from portfusion.record import rules as D


# =====================================================================================
# 1 · THE STORE  —  record in, DataFrames out
# =====================================================================================
#
# pd.DataFrame() on a list of NamedTuples takes the column names off the tuple itself, so there
# is no mapping layer to write or keep in step. AN EMPTY TABLE HAS NO TUPLE TO TAKE THEM OFF, so
# each frame also names its tuple's fields: a new book, whose tables are empty, still has columns.

def utc_of(at: str) -> str:
    """An instant a reader names, on the journal's clock (`schema.record_instant`): UTC, to the
    second, marked `Z`. One written so is returned as it is; one with no zone is UK wall-clock
    time, as the desk shows it, and is read as that."""
    at = str(at)
    if not at or at.endswith("Z"):
        return at
    t = pd.Timestamp(at).tz_localize("Europe/London").tz_convert("UTC")
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def uk_instant(at: str) -> str:
    """A journal instant as UK wall-clock time, for a reader: "2026-10-21T15:29:09"."""
    return pd.Timestamp(utc_of(at)).tz_convert("Europe/London").strftime("%Y-%m-%dT%H:%M:%S")


def load_store() -> dict[str, pd.DataFrame]:
    """The tables the engine reads as frames: the dated ones, the marks, the histories and the
    quarter rows. The rest of the record it reads as the record's own rows, through `self.D`, and a
    frame here that nothing reads is refused (`test_store_doors.py`).

    The histories' folder comes from `D.store_dir()`, as every other table's comes from
    `schema.STORE`, so a store that moves moves all of them together.

    Side effects: reads every file in the store directory.
    """
    # A HISTORY IS THE ONLY COPY OF EVERY MARK IT HOLDS, so an absent one is refused BY NAME
    # rather than read as empty, which would value every past date at nothing and say nothing.
    # `portfusion init` writes all three with a book.
    for name in ("price-history.csv", "fx-history.csv", "account-statements.csv"):
        if not (D.store_dir() / name).is_file():
            raise SystemExit(f"{name} is missing from {D.store_dir()}: a new book is given it by "
                             f"`portfusion init`, so restore this book's copy rather than start "
                             f"an empty one — a history is the only copy of every mark it holds")
    store = {
        "income":    pd.DataFrame(D.ci_rows, columns=D.CostIncomeRow._fields),
        "movements": pd.DataFrame(D.movements,
                                  columns=["date", "account", "amount", "source", "detail"]),
        # THE SCHEMA'S HEADER: a typed copy goes stale when the table gains a column.
        "prices":    pd.DataFrame(D.CURRENT_PRICES,
                                  columns=D.schema.TABLES["current-prices"].header),
        # THE HISTORIES, so the engine can value a past date. Here, because
        # load_store() is the ONE seam into the store.
        "history.prices": pd.read_csv(D.store_dir() / "price-history.csv", dtype={"date": str}),
        "history.fx":    pd.read_csv(D.store_dir() / "fx-history.csv", dtype={"date": str}),
        # The account statements: what a broker said an account was worth, and when.
        "statements":    pd.read_csv(D.store_dir() / "account-statements.csv",
                                     dtype={"as_of": str}),
        # Every account's CONTRIBUTION to net asset value at each quarter end.
        # `contribution` is a column here, not a footnote: a share account contributes its
        # POSITIONS AT MARKET and a spread-bet account its ACCOUNT EQUITY, never its
        # notional. That is the one rule this table exists to enforce.
        "quarter_nav": pd.DataFrame(D.QUARTER_NAV, columns=D.QuarterNAV._fields),
        # RECORD TIME — the one table ABOUT the record rather than part of it. Through the record,
        # like the row counts it reconciles against, so both come from the same store.
        # `rules.journal_rows()` is a function, never loaded at import: the build must never
        # depend on WHEN a row was entered. COLUMNS FROM THE SCHEMA, never typed here: a typed
        # list is a second copy of it.
        "journal":       pd.DataFrame(D.journal_rows(), columns=list(D.JOURNAL_FIELDS)),
    }
    # A SPREAD BET IS PRICED BY ITS CONTRACT, one underlying sitting on several at several levels,
    # so a mark under the bet's own code values none of them and is refused by name.
    bets = {code for code, kind in D.KIND_OF_CODE.items() if kind == "spread bet"}
    by_code = [f"{file}: {key} {day}" for file, frame, on in (
                   ("price-history.csv", "history.prices", "date"),
                   ("current-prices.csv", "prices", "as_of"))
               for key, day in store[frame][["mark_key", on]].itertuples(index=False)
               if key in bets]
    if by_code:
        raise ValueError("A SPREAD BET IS PRICED BY ITS CONTRACT, NOT ITS OWN CODE: key each of "
                         "these by the contract it prices (contracts.csv):\n  "
                         + "\n  ".join(by_code))
    # Dates as real dates, not strings. Doing this once, here, is what makes every
    # "give me Q2" question downstream a one-liner instead of string slicing.
    for name in ("income", "movements"):
        store[name]["date"] = pd.to_datetime(store[name]["date"], errors="coerce")
    return store


def _lookup(keys: pd.Series, by: pd.Series) -> pd.Series:
    """`keys.map(by)` for a `by` with a unique index. pandas cannot map through an EMPTY datetime
    series — it casts it to float and fails — and on a new book every such series is empty."""
    return pd.Series(by.reindex(keys).to_numpy(), index=keys.index)


# =====================================================================================
# THE BASELINE  —  the book's own starting line
# =====================================================================================
#
# The record begins on the book's `record_begins` date. Positions opened before then are in the
# book so their COST BASIS is known; they are not part of the performance record. A pre-baseline
# leg is an opening holding, HELD AT THE BASELINE, and carries a flag.

def record_begins() -> pd.Timestamp:
    """The day the record begins, read from the record as it stands now: what code that has no
    Book reads. A Book reads its own (`Book.baseline`)."""
    return pd.Timestamp(D.RECORD_BEGINS)
