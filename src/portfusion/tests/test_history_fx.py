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
    """If a refresh lands without archiving, the superseded rate is gone. Fix:
    python3 -m portfusion.history.fx --archive"""
    missing = FX.check()
    assert not missing, ("live rates not in the history: "
                         + ", ".join(f"{m['currency']} {m['date']} {m['kind']}" for m in missing))


@needs("fx-history")
def test_no_duplicate_live_rates(rows):
    """One live rate per currency per date PER KIND. The kind matters: EUR genuinely
    holds both a spot and an annual average at 2025-12-31, and they are different
    facts. A CURRENCY KEYS ITS LIVE RATE, as a ticker keys its price: a key with a date or a year
    inside it is how stale typed rates came to sit beside the live ones."""
    live = [(r["currency"], r["date"], r["kind"]) for r in rows if r["status"] == FX.LIVE]
    dupes = [k for k, n in Counter(live).items() if n > 1]
    assert not dupes, f"more than one live rate for: {dupes}"


@needs("fx-history")
def test_kinds_and_qualities_are_known(rows):
    assert not {r["kind"] for r in rows} - set(FX.KINDS)
    assert not {r["quality"] for r in rows} - set(FX.QUALITIES)
    assert not {r["status"] for r in rows} - set(FX.STATUSES)


@needs("fx-history")
def test_rate_on_never_returns_an_average(rows):
    """THE POINT OF THE SPLIT. Ask for a rate on a date inside a year that has an
    annual average on file, and you must not get the average back.

    ON A PLANTED AVERAGE FIRST, dated on the very day asked about and nearer it than any spot:
    the loop below over the book's own rows asks nothing on a book that holds no average,
    which the demo does not."""
    spot = {"currency": "XTS", "date": "2026-01-02", "rate": 1.5, "kind": "spot",
            "status": FX.LIVE}
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
        first = min(r["date"] for r in rows if r["currency"] == ccy and r["kind"] == "spot"
                    and r["status"] == FX.LIVE)
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


def test_the_build_does_not_import_this(build_imports):
    """A tool alongside the build, never part of it — the same contract feeds/ig.py
    works to. A report build must not be able to fail because a CSV moved.

    Checked as an IMPORT rather than a grep: the prose mentions these tools by name.
    """
    assert "history.fx" not in build_imports


def test_a_superseded_rate_would_not_be_listed_as_a_rate_movement(monkeypatch, capsys):
    """WRITTEN BEFORE ANY RATE WAS SUPERSEDED, when this listing was right by accident: it
    never split on the lifecycle at all, so the first replaced rate would have printed as a
    movement on its own date — the defect `history/prices.py` was actually carrying.

    Both histories answer "is this still the mark" the same way, whether or not this one has
    anything to say yet. Synthetic rows, for the reason the price test gives.
    """
    def row(date, rate, status):
        return {"currency": "USD", "date": date, "rate": rate, "kind": "spot",
                "quality": "sourced", "status": status, "source": "synthetic"}
    rows = [row("2026-01-02", 1.30, "live"),
            row("2026-01-02", 1.20, "superseded"),
            row("2026-01-03", 1.40, "live")]
    monkeypatch.setattr(FX, "load", lambda: rows)
    FX.show("USD")
    out = capsys.readouterr().out

    replaced = [ln for ln in out.splitlines() if "1.20000" in ln]
    assert len(replaced) == 1, f"the replaced rate is missing or printed twice: {replaced}"
    assert "(superseded)" in replaced[0], \
        f"a replaced rate was shown inside the move chain: {replaced[0]!r}"
    assert "%" not in replaced[0], "a correction was printed as a percentage move"
    assert "(2 rates" in out, "the replaced rate was counted as part of the series"


# =====================================================================================
# A RATE READ TWICE IN ONE DAY — the price history's rule, now this one's
# =====================================================================================

def _rate(date, rate, struck, source, status="live"):
    return {"currency": "USD", "date": date, "rate": rate, "kind": "spot",
            "quality": "sourced", "struck": struck, "status": status, "source": source}


def test_a_second_read_of_a_day_replaces_a_live_rate_and_supersedes_a_typed_one():
    """THE HOLE THIS CLOSES. The identity is (currency, date, kind), so the second refresh of a
    day found its rate already banked and appended nothing: fx.csv held the afternoon's rate
    while this file kept the morning's. A LIVE read on file now leaves for the later one; a
    rate typed or closed at another figure is a correction, superseded and kept, its
    provenance unchanged. In memory only."""
    read = _rate("2026-09-30", 1.33, "live", "a morning read — test")
    typed = {**_rate("2026-06-30", 1.32, "", "a typed rate — test"), "quality": "derived"}
    rows = [read, typed]
    live = [{**read, "rate": 1.34, "source": "an evening read — test"},
            {**typed, "rate": 1.3301, "struck": "close", "source": "that day's close — test"}]
    dropped, superseded = FX._FILE.restruck(rows, live)
    assert dropped == [read], "a same-day live rate was not replaced"
    assert superseded == [typed], "a typed rate a close replaces was not superseded"
    assert typed["status"] == "superseded" and typed["quality"] == "derived" \
        and typed["source"] == "a typed rate — test", "the correction changed more than the lifecycle"
    kept = [r for r in rows if r is not read]
    assert len(FX._FILE.unbanked(live, kept)) == 2, "the new rates would not be appended"


def test_a_live_rate_is_not_banked_over_its_days_close():
    """A close outranks a live read of its own day: once the past-day door has filed a day's
    close, the live rate still sitting in fx.csv must not strike back over it."""
    close = _rate("2026-09-30", 1.3304, "close", "that day's close — test")
    later = _rate("2026-09-30", 1.33, "live", "a read during the day — test")
    assert FX._FILE.restruck([close], [later]) == ([], [])
    assert FX._FILE.outranked_on_file([close], later)
    assert FX._FILE.unstruck([later], [close]) == [], "an outranked live rate reads as unbanked"


@needs("fx-history")
def test_a_restruck_rate_reads_as_unbanked(monkeypatch):
    """check() is the precondition the Price Refresh's write reads. It asked only whether the
    (currency, date) was on file, so a rate re-read at another figure reported as banked while
    the figure sat nowhere."""
    live = FX.live_marks()
    assert live, "no live rate to re-strike — this asserts nothing"
    moved = [{**m, "rate": round(m["rate"] + 0.01, 5)} if i == 0 else m
             for i, m in enumerate(live)]
    monkeypatch.setattr(FX, "live_marks", lambda: moved)
    assert [m["currency"] for m in FX.check() if not m.get("why")] == [moved[0]["currency"]]
