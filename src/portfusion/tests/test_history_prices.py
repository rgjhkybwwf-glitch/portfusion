"""
THE PRICE HISTORY.

price-history.csv exists so the book can answer "what was this
worth on that date?" — which it could not do while CURRENT_PRICES was overwritten in
place on every refresh.

These tests guard the properties that make it trustworthy rather than merely present:
the live set is banked, and no date carries two marks: a mark put right replaces its row.
"""
import re
from collections import Counter

import pytest

from portfusion.engine import Book
from portfusion.history import prices as PH
from quarter_support import frozen_quarters
from portfusion.record import rules as D
from harness import needs

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def rows():
    r = PH.load()
    assert r, "price-history.csv is empty or missing"
    return r


@pytest.mark.audit
def test_every_current_mark_is_archived():
    """The whole point. If a refresh happens without archiving, the outgoing mark is
    gone for good — so this failing means data is about to be lost, not that a file is
    untidy. Fix: python3 -m portfusion.history.prices --archive"""
    missing = PH.check()
    assert not missing, ("current marks not in the history: "
                         + ", ".join(f"{m['mark_key']} {m['date']}" for m in missing))


@needs("price-history")
def test_no_duplicate_marks(rows):
    """One price per instrument per date. A second one means two sources disagreed and nobody
    chose between them."""
    dupes = [k for k, n in Counter((r["mark_key"], r["date"]) for r in rows).items() if n > 1]
    assert not dupes, f"more than one mark for: {dupes}"


@needs("price-history")
def test_struck_values_are_known(rows):
    """`STRUCK_KINDS` was once declared and read by nothing, and a vocabulary no code checks is
    only a comment. Every mark on file is one of its kinds or blank — and blank means the row
    never said what instant it describes, which is a fact about the row, not an error. The live
    marks cannot be blank: current-prices.csv's loader refuses it (`schema.CURRENT_PRICES`)."""
    allowed = set(PH.STRUCK_KINDS) | {""}
    bad = {r["struck"] for r in rows} - allowed
    assert not bad, f"unknown struck value(s) on file: {bad}"
    assert all(m["struck"] in PH.STRUCK_KINDS for m in PH.current_marks())


@needs("price-history")
def test_qualities_are_known(rows):
    bad = {r["quality"] for r in rows} - set(PH.QUALITIES)
    assert not bad, f"unknown quality value(s): {bad}"


@needs("price-history")
def test_dates_are_iso_and_prices_positive(rows):
    bad_date = [r["mark_key"] for r in rows if not ISO.match(r["date"])]
    assert not bad_date, f"non-ISO date on: {bad_date}"
    bad_price = [(r["mark_key"], r["date"]) for r in rows if not r["price"] > 0]
    assert not bad_price, f"non-positive price on: {bad_price}"


@needs("price-history")
def test_every_mark_names_a_source(rows):
    """No fabricated data: a price with no stated source cannot be checked by anyone."""
    bare = [(r["mark_key"], r["date"]) for r in rows if not (r["source"] or "").strip()]
    assert not bare, f"marks with no source: {bare}"


def test_the_build_does_not_import_this(build_imports):
    """A tool alongside the build, never part of it — the same contract feeds/ig.py
    works to. A report build must not be able to fail because a CSV moved.

    Checked as an IMPORT rather than a grep: the prose mentions these tools by name.
    """
    assert "history.prices" not in build_imports


# ---------------------------------------------------------------------------------
# QUARTER-END COVERAGE
#
# A holding once went missing. Its trade date was later CORRECTED back across a quarter end --
# moving it into the earlier quarter. The Performance reconstruction
# picked the correction up; the Q Snapshots tab did not, and the price history seeded from
# the snapshot inherited the hole.
#
# A quarter-end valuation is only as complete as its price coverage, so the coverage
# is asserted rather than assumed.
#
# The snapshot quarters are DERIVED from rules.QSNAP_FROZEN, so a new freeze is checked from
# its first row — a hand-typed list would let the next quarter land unchecked.
# ---------------------------------------------------------------------------------
QUARTER_TABLES = [
    *(pytest.param(as_of, "quarter-snapshots", rows, 1, id=Book.quarter_label(as_of))
      for as_of, rows in frozen_quarters()),
]


@pytest.mark.parametrize("date,table,rows,tick_idx", QUARTER_TABLES)
def test_every_quarter_end_holding_has_a_price(date, table, rows, tick_idx):
    """A holding is priced at the quarter end by its own mark within the close window
    (`rules.CLOSE_CHECK_WINDOW_DAYS` either side, the window a freeze takes its marks from), or
    — a spread bet — by such a mark for every contract it was held under that day, which is how
    IG marks are keyed. The engine says which contracts those were, so this asks the question a
    valuation asks."""
    import datetime as _dt
    day, window = _dt.date.fromisoformat(date), _dt.timedelta(days=D.CLOSE_CHECK_WINDOW_DAYS)
    marked = {}
    for r in PH.load():
        marked.setdefault(r["mark_key"], []).append(_dt.date.fromisoformat(r["date"][:10]))

    def near(key):
        return any(abs(d - day) <= window for d in marked.get(key, []))

    contracts = {}
    for (ticker, key), _qty in Book()._held_by_mark_key(date).items():
        contracts.setdefault(ticker, set()).add(key)
    wanted = {row[tick_idx] for row in rows
              if row[tick_idx] not in ("(no positions)",)}
    missing = sorted(t for t in wanted
                     if not near(t)
                     and not (contracts.get(t) and all(near(k) for k in contracts[t])))
    assert not missing, (
        f"{table} holds {missing} at {date} with no price mark within the close window — "
        f"a quarter-end valuation cannot be reconstructed without one")


# =====================================================================================
# A MARK READ TWICE IN ONE DAY
# =====================================================================================

def _restrike(rows, price_delta=0.5):
    """One live mark, re-read the same day at a different price. Returns (live_set, ticker)."""
    live = PH.current_marks()
    target = live[0]["mark_key"]
    for m in live:
        if m["mark_key"] == target:
            m["price"] = round(m["price"] + price_delta, 4)
    return live, target


def _row(ticker, price, struck, source):
    return {"mark_key": ticker, "date": "2026-09-30", "price": price, "currency": "USD",
            "quality": "sourced", "struck": struck, "source": source}


def test_a_same_day_restrike_replaces_the_row_on_file():
    """THE HOLE THIS CLOSES. The identity is (ticker, date), so the second reading of a day
    found itself already banked and appended nothing — leaving price-history holding the
    morning's level while current-prices held the afternoon's. Two files disagreeing about one
    date is what makes changes_since() stop tying to the book, which is a failure two invariants
    are there to catch and a reader is not.

    ONE OUTCOME (23 Oct 2026). A live read on file is the same day seen earlier; a close or a
    statement's price a different figure replaces was wrong. Either way the row leaves the file
    and the new figure takes its place: git keeps what it said, and no reader filters.

    In memory only: nothing here touches the store.
    """
    read = _row("AAA", 10.0, "live", "a morning read — test")
    close = _row("BBB", 20.0, "close", "a close — test")
    rows = [read, close]
    live = [{**read, "price": 10.5, "source": "an afternoon read — test"},
            {**close, "price": 20.5, "source": "another close — test"}]
    replaced = PH._FILE.restruck(rows, live)
    assert [r["mark_key"] for r in replaced] == ["AAA", "BBB"], "a same-day re-strike was kept"
    assert close == _row("BBB", 20.0, "close", "a close — test"), "a replaced row was edited"
    landing = sorted(m["mark_key"] for m in PH._FILE.unbanked(live, []))
    assert landing == ["AAA", "BBB"], f"the new figures would not be appended: {landing}"


def test_a_same_day_reading_at_the_same_price_is_a_no_op():
    """Re-reading a closed market returns the same level. If that replaced anything, every
    reading would bank a replacement of itself and the history would churn every day."""
    rows = PH.load()
    assert PH._FILE.restruck(rows, PH.current_marks()) == [], \
        "an unchanged same-day mark was treated as a re-strike"


@needs("price-history")
def test_a_restruck_mark_reads_as_unbanked(monkeypatch):
    """check() is the PRECONDITION the Price Refresh's step 1 and desk/doors/marks.py both read
    before allowing a write. It asked only whether the (ticker, date) was on file, so a
    re-struck mark reported as banked while its price sat nowhere — the write gate opening on
    a guarantee that had not been met."""
    rows = PH.load()
    live, ticker = _restrike(rows)
    monkeypatch.setattr(PH, "current_marks", lambda: live)
    assert [m["mark_key"] for m in PH.check()] == [ticker], \
        "a re-struck mark still reads as banked"


@needs("price-history")
def test_a_save_that_fails_leaves_the_history_as_it_was(store_copy):
    """A SAVE THAT RAISES MUST NOT TRUNCATE. It once opened the file for writing and then
    rendered the rows, so a row the writer refused — a cell under a column the history does not
    have — left price-history.csv empty: every mark ever banked, gone in one refresh."""
    path = store_copy / PH.CSV_NAME
    before = path.read_bytes()
    rows = PH.load()
    bad = dict(rows[0], date="1900-01-01", stray="a cell no column holds")
    with pytest.raises(ValueError):
        PH.save(rows + [bad])
    assert path.read_bytes() == before, "a refused save changed the history on disk"
    assert not [p for p in store_copy.iterdir() if p.name.startswith(".")], \
        "a refused save left its working file in the store"


@needs("price-history")
def test_a_price_written_to_more_than_six_places_is_refused_on_reading(store_copy):
    """A history holds its figures to their places (`files.PLACES`), as the record's loader does,
    so a hand edit cannot leave a price the bank would never have written."""
    path = store_copy / PH.CSV_NAME
    lines = path.read_text(encoding="utf-8").splitlines()
    cells = lines[1].split(",")
    cells[2] = "1.2345678"
    path.write_text("\n".join([lines[0], ",".join(cells)] + lines[2:]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="price: .*decimal places"):
        PH.load()


def test_a_row_that_does_not_fit_the_header_is_refused_on_reading(store_copy):
    """A HAND-EDITED ROW WITH AN EXTRA CELL is refused where the file is READ, so the bank never
    gets as far as writing over a history it could not have written back whole."""
    path = store_copy / PH.CSV_NAME
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines + [lines[-1] + ",extra"]) + "\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="cells expected"):
        PH.load()
    with pytest.raises(ValueError):
        PH.archive(verbose=False)
    assert path.read_bytes() == before


def test_a_close_at_the_figure_of_its_days_live_read_still_replaces_it(store_copy):
    """A CLOSE IS THE DAY'S MARK, whatever figure it lands on. One that equalled the live read
    already banked for its day was skipped as "the same figure", so the history kept a live read
    for that day and the day read as owed its close (the review of 21 Oct 2026)."""
    close = next((m for m in PH.current_marks() if m["struck"] == "close"), None)
    if close is None:
        pytest.skip("the book holds no close among its live marks")
    key = (close["mark_key"], close["date"])
    rows = [r for r in PH.load() if (r["mark_key"], r["date"]) != key]
    PH.save(rows + [dict(close, struck="live")])
    assert PH.check() == [close], "a close over its day's live read reads as banked"

    PH.archive(verbose=False)

    on_file = [r for r in PH.load() if (r["mark_key"], r["date"]) == key]
    assert [r["struck"] for r in on_file] == ["close"], on_file
    assert PH.check() == []


def test_a_history_keeps_only_the_marks_a_figure_can_take(store_copy, monkeypatch):
    """THE NEXT BANK DROPS WHAT NO FIGURE CAN TAKE (`AppendOnlyCSV.kept()`). Kept: a close; the
    mark on or before and the nearest to a quarter end (the year's before too), an opening and a
    current reading; the live mark and the one before it, though a later close sits above them.
    An invented line in an invented year, so no figure of the loaded book is near it."""
    from types import SimpleNamespace
    from portfusion.history import accounts as AH, fx as FX
    monkeypatch.setattr(D, "ACCOUNT_BEGINS", {"An account": "2031-04-22"})
    monkeypatch.setattr(D, "ac_rows", [SimpleNamespace(as_of="2031-08-05")])

    def mark(day, struck="live"):
        return {**_row("ZZZ", 1.0, struck, "test"), "date": f"2031-{day}"}

    PH.save(PH.load() + [mark("01-03"), mark("01-06"), mark("03-31"), mark("04-14"),
                         mark("04-15", "close"), mark("04-21"), mark("06-27"), mark("07-02"),
                         mark("08-05"), mark("08-10"), mark("08-20"), mark("08-25", "close")])
    PH._FILE.bank([mark("08-21")])
    days = [r["date"][5:] for r in PH.load() if r["mark_key"] == "ZZZ"]
    assert days == ["01-03", "03-31", "04-15", "04-21", "06-27", "07-02", "08-05", "08-20",
                    "08-21", "08-25"], days
    rate = {"currency": "ZZZ", "kind": "spot", "rate": 1.0, "quality": "sourced",
            "struck": "live", "source": "test"}
    rates = [{**rate, "date": f"2031-{d}"} for d in ("01-03", "01-06", "03-31", "08-20", "08-21")]
    assert FX._FILE.kept(rates) == [rates[0], *rates[2:]], "the FX history keeps what prices keep"
    assert AH._FILE.series is None, "an account's history is its value series, every row kept"
