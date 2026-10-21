"""
THE PRICE HISTORY — an append-only record of what each instrument was worth, and when.

Current prices are replaced on every refresh, so without this file the book could say what was
held on any past date but not what it was worth. Prices ACCUMULATE here; nothing is overwritten,
and the one row ever deleted is a live read that a later read of its own day replaces
(`AppendOnlyCSV.restruck()`). CSV because this is the table whose diff is worth reading.

    python3 -m portfusion.history.prices --archive      # before a refresh: bank the current marks
    python3 -m portfusion.history.prices --show TSSL    # one instrument's series
    python3 -m portfusion.history.prices --check        # is the current set banked?

A tool alongside the build, never part of it: the build must not import it.
"""
from __future__ import annotations


import sys
from collections import defaultdict

from portfusion.history import files
from portfusion.history._appendonly import AppendOnlyCSV
from portfusion.record import rules as D
from portfusion.record import schema
from portfusion.log import log

# The file and its columns are `history/files.py`'s, where the demo's generator reads them.
CSV_NAME, FIELDS = files.PRICES, files.PRICE_FIELDS

# WHAT INSTANT A MARK WAS STRUCK AT — `schema.STRUCK_KINDS`, one vocabulary for this file and
# current-prices.csv. Blank here means the row never said, as with the pre-baseline
# reconstructions, and a blank is comparable with nothing.
#
# A reconciliation must ask this — two figures compare only when they describe the same state
# of the market — so it is a column rather than a phrase to search for in `source`. Named
# `struck`, not `kind`: fx-history.csv's `kind` already answers a different question.
STRUCK_KINDS = schema.STRUCK_KINDS

# TWO AXES. `quality` is the PROVENANCE: sourced (a statement, contract note or named feed) or
# derived (a reconstruction). `status` is the LIFECYCLE: live, or
# superseded — replaced by a better mark and kept on file. They cannot share a column: a sourced
# mark superseded by another sourced one is both. A superseded row keeps its REAL date; a date
# altered to keep (ticker, date) unique would show a correction as a price move.
#
# A LIVE READ IS NOT CORRECTED, IT IS REPLACED (12 Oct 2026): the rule both mark histories keep,
# `AppendOnlyCSV.restruck()`, and `desk/doors/marks.py:bank_closes()` with them.
QUALITIES = ("sourced", "derived")
STATUSES = D.MARK_STATUSES

LIVE = D.LIVE_MARK          # the status a lookup or a series should see









# --- the file itself ------------------------------------------------------------------------
_FILE = AppendOnlyCSV(CSV_NAME, FIELDS, numeric=("price",), sort_key=lambda r: (r["date"], r["ticker"]),
                      identity=("ticker", "date"), nullable=False, figure="price")

load = _FILE.load
save = _FILE.save
known = _FILE.known

def current_marks() -> list[dict]:
    """The live CURRENT_PRICES set, in this file's shape. `struck` is the column the feed wrote
    with the price — the one party that knows whether it fetched a close or a live read."""
    return [{"ticker": t, "date": d, "price": p, "currency": c,
             "quality": "sourced", "struck": struck, "status": D.LIVE_MARK, "source": src}
            for t, p, c, d, src, struck, _at in D.CURRENT_PRICES]


#: The same-day rule, the one both mark histories keep (`AppendOnlyCSV`).
_outranked = AppendOnlyCSV.outranked
_restruck = _FILE.restruck


def archive(verbose: bool = True) -> list[dict]:
    """Append today's marks. Idempotent on (ticker, date) at the SAME price — safe to run
    twice, and safe to run late, so long as CURRENT_PRICES has not been overwritten yet.

    A same-day mark at a DIFFERENT price replaces a live read on file and supersedes anything
    else (`_restruck()`). A live read of a day whose close is on file is not banked at all
    (`_outranked()`): the close is that day's mark.
    """
    new, dropped, superseded = _FILE.bank(current_marks())
    if verbose:
        for r in sorted(dropped, key=lambda r: r["ticker"]):
            log.info(f"    replaced   {r['ticker']:12} {r['date']}  {r['price']:>12,.4f} "
                  f"— a live read, read again the same day")
        for r in sorted(superseded, key=lambda r: r["ticker"]):
            log.info(f"    superseded {r['ticker']:12} {r['date']}  {r['price']:>12,.4f} "
                  f"— corrected the same day")
        if new:
            log.info(f"  archived {len(new)} new mark(s):")
            for m in sorted(new, key=lambda m: m["ticker"]):
                log.info(f"    {m['ticker']:12} {m['date']}  {m['price']:>12,.4f} {m['currency']}")
        else:
            log.info("  nothing to archive — every current mark is already on file")
    return new


def check() -> list[dict]:
    """The live marks that are NOT yet banked. Empty means everything is on file.

    Silent when all is well. A re-struck mark counts as unbanked — its (ticker, date) is on file
    but its price is not — because this is the precondition the Price Refresh's first step and
    `desk/doors/marks.py` read before allowing a write. A live read its day's close outranks
    needs no banking: the close is that day's mark.

    Side effects: none.
    """
    return _FILE.unstruck(current_marks())


def show(ticker: str | None = None) -> None:
    """Print the mark history, or one ticker's, with the move between readings.

    Side effects: prints. The percentage move is display arithmetic, not a stored figure.
    """
    rows = load()
    if not rows:
        log.info("  no history on file yet — run --archive")
        return
    # Superseded rows are found by `status`, the lifecycle — not by `quality`.
    by, dead = defaultdict(list), defaultdict(list)
    for r in rows:
        (by if r["status"] == LIVE else dead)[r["ticker"]].append(r)
    tickers = [ticker] if ticker else sorted(by)
    for t in tickers:
        series = sorted(by.get(t, []), key=lambda r: r["date"])
        if not series:
            log.info(f"  {t}: nothing on file")
            continue
        log.info(f"  {t}  ({len(series)} marks, {series[0]['currency']})")
        prev = None
        for r in series:
            # The move chain runs over LIVE marks only. A superseded mark is not a
            # price movement — it is a correction, and showing it as one would lie.
            move = "" if prev is None else f"{(r['price'] / prev - 1) * 100:+7.2f}%"
            flag = "" if r["quality"] == "sourced" else "  (derived)"
            log.info(f"     {r['date']}  {r['price']:>12,.4f} {move:>9}{flag}")
            prev = r["price"]
        for r in sorted(dead.get(t, []), key=lambda r: r["date"]):
            log.info(f"     {r['date']}  {r['price']:>12,.4f} {'':>9}  (superseded)")
        log.info("")


def main(argv: list[str]) -> int:
    """The command line: --show [ticker], --archive, --check.

    Side effects: --archive APPENDS to store/price-history.csv. Everything else reports.
    """
    if "--archive" in argv:
        archive()
    elif "--check" in argv:
        missing = check()
        if missing:
            log.info(f"  ✗ {len(missing)} current mark(s) not in the history:")
            for m in missing:
                log.info(f"      {m['ticker']} {m['date']}")
            log.info("    run: python3 -m portfusion.history.prices --archive")
            return 1
        log.info("  ✓ every current mark is on file")
    elif "--show" in argv:
        i = argv.index("--show")
        show(argv[i + 1] if len(argv) > i + 1 else None)
    else:
        log.info(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
