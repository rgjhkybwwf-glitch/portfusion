"""
THE FX HISTORY.

fx-history.csv is append-only and exists for the same reason price-history.csv does:
the live table, one rate per currency, overwrites. Every dated rate the record converts at is
here, by currency and a real date.

The property these tests exist to protect is the spot/average split. An annual average
is not a rate on a date, and returning one as though it were would be a wrong answer
that looks entirely right.
"""
import re
from collections import Counter

import pandas as pd
import pytest

from portfusion.history import fx as FX
from portfusion.record import rules as D
from harness import needs

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def rows():
    r = FX.load()
    assert r, "fx-history.csv is empty or missing"
    return r


@pytest.mark.audit
def test_every_live_rate_is_archived():
    """If a refresh lands without archiving, the outgoing rate is gone. Fix:
    python3 -m portfusion.history.fx --archive"""
    missing = FX.check()
    assert not missing, ("live rates not in the history: "
                         + ", ".join(f"{m['currency']} {m['date']} {m['kind']}" for m in missing))


@needs("fx-history")
def test_no_duplicate_rates(rows):
    """One rate per currency per date PER KIND. The kind matters: EUR genuinely
    holds both a spot and an annual average at 2025-12-31, and they are different
    facts. A CURRENCY KEYS ITS LIVE RATE, as a ticker keys its price: a key with a date or a year
    inside it lets a stale typed rate sit beside the live one."""
    dupes = [k for k, n in Counter((r["currency"], r["date"], r["kind"]) for r in rows).items()
             if n > 1]
    assert not dupes, f"more than one rate for: {dupes}"


@needs("fx-history")
def test_kinds_and_qualities_are_known(rows):
    assert not {r["kind"] for r in rows} - set(FX.KINDS)
    assert not {r["quality"] for r in rows} - set(FX.QUALITIES)


@needs("fx-history")
def test_rate_on_never_returns_an_average(rows):
    """THE POINT OF THE SPLIT. Ask for a rate on a date inside a year that has an
    annual average on file, and you must not get the average back.

    ON A PLANTED AVERAGE FIRST, dated on the very day asked about and nearer it than any spot:
    the loop below over the book's own rows asks nothing on a book that holds no average,
    which the demo does not."""
    spot = {"currency": "XTS", "date": "2026-01-02", "rate": 1.5, "kind": "spot"}
    average = dict(spot, date="2026-06-30", rate=9.999, kind="average")
    assert FX.rate_on("XTS", "2026-06-30", rows + [spot, average]) == 1.5
    for ccy in {r["currency"] for r in rows}:
        for probe in ("2023-06-15", "2025-06-15", "2026-06-30"):
            got = FX.rate_on(ccy, probe, rows)
            if got is None:
                continue
            avgs = {r["rate"] for r in rows if r["currency"] == ccy and r["kind"] == "average"}
            spots = {r["rate"] for r in rows if r["currency"] == ccy and r["kind"] == "spot"}
            assert got in spots, f"rate_on({ccy}, {probe}) returned {got}, which is not a spot"
            if got in avgs and got not in spots:
                pytest.fail(f"rate_on({ccy}, {probe}) returned an annual average")


@needs("fx-history")
def test_rate_on_returns_none_rather_than_guessing(rows):
    """A missing rate must be visible. The day before a currency's earliest spot rate has no
    answer — and None is the honest one."""
    import datetime as dt
    for ccy in {r["currency"] for r in rows}:
        first = min(r["date"] for r in rows if r["currency"] == ccy and r["kind"] == "spot")
        day_before = (dt.date.fromisoformat(first) - dt.timedelta(days=1)).isoformat()
        assert FX.rate_on(ccy, day_before, rows) is None, f"{ccy} answered before {first}"
    assert FX.rate_on("GBP", "2020-01-01") == 1.0


@needs("fx-history")
def test_gbp_is_not_stored(rows):
    """A GBP/GBP rate of 1.0 is an identity, not an observation. Storing it in a table
    of observations invites someone to refresh it."""
    assert not [r for r in rows if r["currency"] == "GBP"]


@needs("fx-history")
def test_dates_are_iso_and_rates_positive(rows):
    assert not [r["currency"] for r in rows if not ISO.match(r["date"])]
    assert not [(r["currency"], r["date"]) for r in rows if not r["rate"] > 0]


@needs("fx-history")
def test_every_rate_names_a_source(rows):
    bare = [(r["currency"], r["date"]) for r in rows if not (r["source"] or "").strip()]
    assert not bare, f"rates with no source: {bare}"


def test_every_live_rate_is_dated(monkeypatch):
    """A live rate with no date is skipped by live_marks() — there is no day to file it under —
    and would be lost at the next refresh. unbankable() names it, and check() with it, so the
    write refuses rather than replacing a rate banked nowhere."""
    assert not FX.unbankable(), f"live rates with no date: {FX.unbankable()}"
    planted = [("USD", 1.33, "30 Sep 2026", "planted for the test", "live")]
    monkeypatch.setattr(D, "fx_rows", planted)
    assert FX.live_marks() == [] and [m["currency"] for m in FX.check()] == ["USD"]


# =====================================================================================
# A RATE READ TWICE IN ONE DAY — the price history's rule too
# =====================================================================================

def _rate(date, rate, struck, source):
    return {"currency": "USD", "date": date, "rate": rate, "kind": "spot",
            "quality": "sourced", "struck": struck, "source": source}


def test_a_second_read_of_a_day_replaces_the_rate_on_file():
    """The identity is (currency, date, kind), so a later read appends nothing while the row on
    file stays: a live read, or a rate typed or closed at another figure, leaves for the later
    one, unedited. In memory only."""
    read = _rate("2026-09-30", 1.33, "live", "a morning read — test")
    typed = {**_rate("2026-06-30", 1.32, "", "a typed rate — test"), "quality": "derived"}
    rows = [read, typed]
    live = [{**read, "rate": 1.34, "source": "an evening read — test"},
            {**typed, "rate": 1.3301, "struck": "close", "source": "that day's close — test"}]
    assert FX._FILE.restruck(rows, live) == [read, typed], "a same-day re-read was kept"
    assert typed["quality"] == "derived" and typed["source"] == "a typed rate — test", \
        "a replaced rate was edited"
    assert len(FX._FILE.unbanked(live, [])) == 2, "the new rates would not be appended"


def test_a_live_rate_is_not_banked_over_its_days_close():
    """A close outranks a live read of its own day: once the past-day door has filed a day's
    close, the live rate still sitting in fx.csv must not strike back over it."""
    close = _rate("2026-09-30", 1.3304, "close", "that day's close — test")
    later = _rate("2026-09-30", 1.33, "live", "a read during the day — test")
    assert FX._FILE.restruck([close], [later]) == []
    assert FX._FILE.unstruck([later], [close]) == [], "an outranked live rate reads as unbanked"


def test_the_history_is_kept_in_date_order():
    """The record's one order is by date, and a saved history keeps it: a rate goes where its day
    puts it, then by currency, as a price goes by its day, then its line. In memory only."""
    rows = [{**_rate(d, 1.0, "close", "a close — test"), "currency": c}
            for c, d in (("USD", "2026-09-29"), ("DKK", "2026-09-30"), ("EUR", "2026-09-29"))]
    assert [(r["date"], r["currency"]) for r in sorted(rows, key=FX._FILE.sort_key)] == \
        [("2026-09-29", "EUR"), ("2026-09-29", "USD"), ("2026-09-30", "DKK")]


@needs("fx-history")
def test_a_restruck_rate_reads_as_unbanked(monkeypatch):
    """check() is the precondition the Price Refresh's write reads: a rate re-read at another
    figure reads as unbanked."""
    live = FX.live_marks()
    assert live, "no live rate to re-strike — this asserts nothing"
    moved = [{**m, "rate": round(m["rate"] + 0.01, 5)} if i == 0 else m
             for i, m in enumerate(live)]
    monkeypatch.setattr(FX, "live_marks", lambda: moved)
    assert [m["currency"] for m in FX.check() if not m.get("why")] == [moved[0]["currency"]]


def test_a_bank_moves_no_figure(store_copy):
    """WHAT A BANK DROPS NO FIGURE TAKES: What Changed and the headline read the same after the FX
    history drops what a bank drops (`AppendOnlyCSV.kept()`). What Changed sets a share line
    against the rate of the day before its mark, so with the live rate a fortnight past the
    marks and a rate read every day between, a prune of those reads would move it. On a copy."""
    import csv
    import datetime as dt
    from portfusion.engine import Book
    fx = store_copy / "fx.csv"
    with fx.open(newline="") as f:
        live = list(csv.DictReader(f))
    foreign = [r for r in live if r["currency"] != FX.BASE]
    if not foreign:
        pytest.skip("the book holds no foreign rate")
    newest = max(dt.date.fromisoformat(r["as_of"]) for r in live)

    def day(n):
        return (newest + dt.timedelta(days=n)).isoformat()

    with fx.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(live[0]), lineterminator="\n")
        w.writeheader()
        w.writerows({**r, "as_of": day(14), "struck": "live"} for r in live)
    D.reload_store()
    on_file = {FX._FILE.key(r) for r in FX.load()}
    reads = [{**_rate(day(n), round(float(r["rate"]) * (1 + n / 1000), 5), "live", "test"),
              "currency": r["currency"]} for r in foreign for n in range(-14, 14)]
    FX.save(FX.load() + [m for m in reads if FX._FILE.key(m) not in on_file])

    def figures():
        b = Book()
        return b.changes_since(), b.headline()
    changes, headline = figures()
    FX.save(FX._FILE.kept(FX.load(), FX.live_marks()))
    after, headline_after = figures()
    pd.testing.assert_frame_equal(after, changes)
    pd.testing.assert_series_equal(pd.Series(headline_after), pd.Series(headline))
