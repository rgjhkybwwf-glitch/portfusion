"""
THE FX HISTORY — an append-only record of exchange rates, by currency and date.

The live table, store/fx.csv, holds one rate per currency, the one each refresh replaces. Here
the currency and a real date identify a rate, and rates accumulate: every dated rate the record
converts at is on this file. Nothing names a rate by a key: a deal or an income
row carries its broker's rate, or converts at its day's close.

    python3 -m portfusion.history.fx --archive         # bank the live rates
    python3 -m portfusion.history.fx --show USD        # one currency's series
    python3 -m portfusion.history.fx --check           # are the live rates banked?
    python3 -m portfusion.history.fx --rate USD 2026-06-30

TWO KINDS OF RATE, NEVER TO BE CONFUSED

  spot     a rate ON a date            — 30 Jun 2026, GBP/USD 1.28410
  average  a rate ACROSS a period      — the 2023 annual average, 1.244

An average has no single date, so it is filed at its period end and marked `average`.
rate_on() returns SPOT ONLY: an annual average given as the rate on 3 April 2023 would be a
wrong answer that looks right. An average on file is replaced once a leg's own price at its
day's close is on file.

A tool alongside the build, never part of it.
"""
from __future__ import annotations


import datetime as _dt
import sys
from collections import defaultdict

from portfusion.history import files
from portfusion.history._appendonly import AppendOnlyCSV
from portfusion.record import rules as D
from portfusion.log import log

# The file and its columns are `history/files.py`'s, where the demo's generator reads them.
CSV_NAME, FIELDS = files.FX, files.FX_FIELDS
KINDS = ("spot", "average")
# Provenance, as in `history/prices.py`; a rate put right replaces its row there too.
QUALITIES = ("sourced", "derived")

# GBP is not stored. A GBP/GBP rate of 1.0 is an identity, not an observation, and
# putting it in a table of observations invites someone to "refresh" it.
BASE = "GBP"

# --- the file itself ------------------------------------------------------------------------
_FILE = AppendOnlyCSV(CSV_NAME, FIELDS, numeric=("rate",), sort_key=lambda r: (r["currency"], r["date"], r["kind"]),
                      identity=("currency", "date", "kind"), nullable=False, figure="rate",
                      places=files.PLACES[CSV_NAME])

load = _FILE.load
save = _FILE.save
known = _FILE.known

def _iso(day: str) -> str | None:
    """`day` as an ISO date, or None when it is not one: a rate with no date cannot be banked."""
    try:
        return _dt.date.fromisoformat(str(day)).isoformat()
    except ValueError:
        return None


def live_marks() -> list[dict]:
    """The live rates, one per currency, in this file's shape: a spot rate on its `as_of`, a
    feed's, so sourced."""
    return [{"currency": ccy, "date": _iso(as_of), "rate": rate, "kind": "spot",
             "quality": "sourced", "struck": struck, "source": src}
            for ccy, rate, as_of, src, struck in D.fx_rows
            if ccy != BASE and _iso(as_of) is not None]


def archive(verbose: bool = True) -> list[dict]:
    """Append the live rates, as the price history appends its marks (`AppendOnlyCSV.bank()`):
    idempotent at the same figure, and a second read of a day replaces a live read of it
    — until 14 Oct 2026 the first read of a day stayed, and fx.csv and this file
    disagreed about that day after a second refresh."""
    new, replaced = _FILE.bank(live_marks())
    if verbose:
        for r in sorted(replaced, key=lambda r: r["currency"]):
            log.info(f"    replaced {r['currency']:4} {r['date']}  {r['rate']:>10.5f}")
        if new:
            log.info(f"  archived {len(new)} new rate(s):")
            for m in sorted(new, key=lambda m: (m["currency"], m["date"])):
                log.info(f"    {m['currency']:4} {m['date']}  {m['rate']:>10.5f}  {m['kind']}")
        else:
            log.info("  nothing to archive — every live rate is already on file")
    return new


def unbankable() -> list[dict]:
    """Live rates whose `as_of` is not a date, so they CANNOT be banked.

    Its own function because the silence was the bug: live_marks() has to skip a row it cannot
    date, and check() asked only about the rows live_marks() returned, so an undated rate was
    never reported and was lost on the next refresh. This makes the next one loud.
    """
    return [{"currency": ccy, "date": None, "kind": None, "rate": rate,
             "why": f"as_of {as_of!r} is not a date, so there is no date to file it under."}
            for ccy, rate, as_of, *_ in D.fx_rows if ccy != BASE and _iso(as_of) is None]


def check() -> list[dict]:
    """The live rates NOT on file at their own figure — the ones not yet banked or re-struck —
    AND the unbankable.

    Both, because the caller asks one question — is it safe to replace the live rates? — and it
    is not in either case. This is `marks.banked()`'s precondition, so an undated rate refuses
    a refresh at the door. Silent when all is well. Side effects: none.
    """
    return _FILE.unstruck(live_marks()) + unbankable()


def rate_on(currency: str, date: str, rows: list[dict] | None = None) -> float | None:
    """GBP-per-unit rate for `currency` on `date`. SPOT ONLY — see the module note.

    Returns the most recent spot on or before the date, and None if the history does
    not reach back that far. None is deliberate: a missing rate must be visible, not
    quietly filled with the nearest thing to hand.
    """
    if currency == BASE:
        return 1.0
    rows = load() if rows is None else rows
    cand = [r for r in rows
            if r["currency"] == currency and r["kind"] == "spot"
            and r["date"] <= date]
    return max(cand, key=lambda r: r["date"])["rate"] if cand else None


def show(currency: str | None = None) -> None:
    """Print the rate history, or one currency's, with the move between readings.

    Side effects: prints. The percentage move is display arithmetic, not a stored figure.
    """
    rows = load()
    if not rows:
        log.info("  no history on file yet — run --archive")
        return
    by = defaultdict(list)
    for r in rows:
        by[r["currency"]].append(r)
    for c in ([currency] if currency else sorted(by)):
        series = sorted(by.get(c, []), key=lambda r: (r["kind"], r["date"]))
        if not series:
            log.info(f"  {c}: nothing on file")
            continue
        log.info(f"  GBP/{c}  ({len(series)} rates)")
        prev = None
        for r in series:
            if r["kind"] == "spot":
                move = "" if prev is None else f"{(r['rate'] / prev - 1) * 100:+7.2f}%"
                flag = "" if r["quality"] == "sourced" else "  (derived)"
                log.info(f"     {r['date']}  {r['rate']:>10.5f} {move:>9}{flag}")
                prev = r["rate"]
        for r in series:
            if r["kind"] == "average":
                log.info(f"     {r['date']}  {r['rate']:>10.5f}    period average"
                      f"{'' if r['quality'] == 'sourced' else '  (derived)'}")
        log.info("")


def main(argv: list[str]) -> int:
    """The command line: --show [ccy], --archive, --check, --rate CCY DATE.

    Side effects: --archive APPENDS to store/fx-history.csv. Everything else reports.
    """
    if "--archive" in argv:
        archive()
    elif "--check" in argv:
        missing = check()
        if missing:
            log.info(f"  ✗ {len(missing)} live rate(s) not in the history:")
            for m in missing:
                if m.get("why"):
                    log.info(f"      {m['currency']} — {m['why']}")
                else:
                    log.info(f"      {m['currency']} {m['date']} {m['kind']}")
            if any(not m.get("why") for m in missing):
                log.info("    run: python3 -m portfusion.history.fx --archive")
            return 1
        log.info("  ✓ every live rate is on file")
    elif "--rate" in argv:
        i = argv.index("--rate")
        ccy, date = argv[i + 1], argv[i + 2]
        r = rate_on(ccy, date)
        log.info(f"  GBP/{ccy} on {date}: {r if r is not None else 'no spot rate on or before that date'}")
    elif "--show" in argv:
        i = argv.index("--show")
        show(argv[i + 1] if len(argv) > i + 1 else None)
    else:
        log.info(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
