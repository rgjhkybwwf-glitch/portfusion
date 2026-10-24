"""THE MIGRATIONS, held by running each one backwards and then forwards (#12).

The steps are data (`record/migrations.py`), so a copy of the demo can be put back into the shape
before them; `plan()` and `write()` must then carry it to the demo exactly, byte for byte, and
`put_back()` must return it to the old shape exactly. A step that moved a name the demo does not
use, or lost a row's bytes on the way, fails here.
"""
import csv
import io
import json
import re
import shutil

import pytest

from portfusion.record import migrations as M, schema


def _backwards(m, book):
    """`book` as it was before `m`: every table, column, split, journal name and Bench key back."""
    store = book / "store"
    old_of = {n: o for o, n in m.tables.items()}
    for path in sorted(store.glob("*.csv")):
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"))))
        undo = {n: o for o, n in m.columns.get(path.stem, {}).items()}
        head = [undo.get(c, c) for c in rows[0]]
        old, into, _ = m.splits.get(path.stem) or (None, {}, None)
        if old:
            at = head.index(next(iter(into.values())))
            head[at:at + len(into)] = [old]
            for r in rows[1:]:
                r[at:at + len(into)] = [next((v for v in r[at:at + len(into)] if v), "")]
        if path.stem == "journal":
            for r in rows[1:]:
                r[rows[0].index("table")] = old_of.get(r[rows[0].index("table")], r[rows[0].index("table")])
        out = io.StringIO()
        csv.writer(out, lineterminator="\n").writerows([head, *rows[1:]])
        path.unlink()
        (store / f"{old_of.get(path.stem, path.stem)}.csv").write_text(out.getvalue(), encoding="utf-8")
    for path in (book / "_archive" / "bench").glob("*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        for r in item["rows"]:
            undo = {n: o for o, n in m.columns.get(r["table"], {}).items()}
            old, into, _ = m.splits.get(r["table"]) or (None, {}, None)
            undo.update({n: old for n in into.values()})
            r["values"] = {undo.get(c, c): v for c, v in r["values"].items()
                           if not (c in into.values() and not v)}
            r["sources"] = {undo.get(c, c): v for c, v in r.get("sources", {}).items()}
            r["derived"] = [undo.get(c, c) for c in r.get("derived", [])]
            r["table"] = old_of.get(r["table"], r["table"])
        item["written_to"] = {old_of.get(t, t): n for t, n in item.get("written_to", {}).items()}
        path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_a_book_in_the_old_shape_is_carried_to_this_release_and_can_be_put_back(tmp_path):
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    for m in M.MIGRATIONS:
        _backwards(m, book)
    # AN OPEN ITEM ON THE BENCH, a bet's buy in the old shape: its level lands in level_points.
    bet = next(r["ticker"] for r in csv.DictReader((schema.DEMO / "store" / "securities.csv").open())
               if r["held_as"] == "spread bet")
    (book / "_inbox" / ".bench").mkdir(parents=True)
    (book / "_inbox" / ".bench" / "B-T.json").write_text(json.dumps({"id": "B-T", "rows": [
        {"table": "trades", "values": {"id": "T-999", "ticker": bet, "val": "9850.0"},
         "derived": ["id"]}]}, indent=2))
    old = {p.relative_to(book): p.read_bytes() for p in book.rglob("*") if p.is_file()}

    m, changes = M.plan(book)
    assert m is M.MIGRATIONS[0] and changes, "the old shape planned no move"
    before = M.write(changes)
    for p in schema.DEMO.rglob("*"):
        if p.is_file() and p.relative_to(schema.DEMO).parts[0] in ("store", "_archive"):
            got = book / p.relative_to(schema.DEMO)
            assert got.read_bytes() == p.read_bytes(), f"{p.relative_to(schema.DEMO)} moved wrong"
    assert M.plan(book) == (None, []), "a moved book still planned a move"
    [row] = json.loads((book / "_inbox" / ".bench" / "B-T.json").read_text())["rows"]
    assert (row["table"], row["values"], row["derived"]) == (
        "buys", {"trade_id": "T-999", "ticker": bet, "cost": "", "level_points": "9850.0"},
        ["trade_id"]), row

    M.put_back(before)
    now = {p.relative_to(book): p.read_bytes() for p in book.rglob("*") if p.is_file()}
    assert now == old, "put_back() did not return the book to its old shape"


# =====================================================================================
# ONE MOVE BEHIND: a demo copy put back in the shape before one move, and carried to the demo.
#
# Each old shape below returns the journal rows its move must write, {(op, table): rows or None
# for any count}, and the files allowed to differ from the demo's (their headers must not).
# =====================================================================================

def _demo_copy(tmp_path):
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    return book, book / "store"


def _write(path, rows):
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")


def _rows_of(path):
    return list(csv.reader(path.open(encoding="utf-8")))


def _out_of_date_order(store):
    """The first buy moved to the bottom and numbered after the rest, the sales reversed, and the
    retired `trade_id_floor` back in settings. Rows that tie on date, account and ticker keep their
    file order, which is why the buy moved is one that ties with none."""
    buys = (store / "buys.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    sales = (store / "sales.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    old = {f"T-{n:03d}": f"T-{n - 1:03d}" for n in range(2, len(buys))} | {
        "T-001": f"T-{len(buys) - 1:03d}"}
    (store / "buys.csv").write_text("".join(
        [buys[0]] + [line.replace(line.split(",")[0], old[line.split(",")[0]], 1)
                     for line in buys[2:] + buys[1:2]]), encoding="utf-8")
    (store / "sales.csv").write_text(re.sub(r",(T-\d{3}),", lambda m: f",{old[m.group(1)]},",
                                            "".join([sales[0], *reversed(sales[1:])])),
                                     encoding="utf-8")
    with (store / "settings.csv").open("a", encoding="utf-8") as fh:
        fh.write("trade_id_floor,T-050\n")
    return {("replace", "buys"): None, ("replace", "sales"): None, ("remove", "settings"): "1"}, set()


def _with_retired_tables(store):
    """The two retired tables on file, and a journal row naming each."""
    (store / "realisations.csv").write_text("ticker,realisation_id,opened,note\n", encoding="utf-8")
    (store / "baseline-reconstruction.csv").write_text(
        "as_of,ticker,qty,price,source,rate,quality\n", encoding="utf-8")
    journal = store / "journal.csv"
    lines = journal.read_text(encoding="utf-8").splitlines(keepends=True)
    opening = next(ln for ln in lines if ",baseline,open," in ln)
    journal.write_text("".join(lines[:2] + [
        opening.replace(f",{opening.split(',')[3]},", f",{t},", 1)
        for t in M.RETIRED] + lines[2:]), encoding="utf-8")
    return {}, set()


def _with_the_lifecycle(store):
    """`status` in its five tables, a superseded row beside a live one in a history and in
    quarter-nav, and a restated quarter's first row before its restatement."""
    after = {"price-history": "struck", "fx-history": "struck", "account-statements": "quality",
             "quarter-nav": "quality", "quarter-snapshots": "quality"}
    for name, col in after.items():
        rows = _rows_of(store / f"{name}.csv")
        at = rows[0].index(col) + 1
        rows = [rows[0][:at] + ["status"] + rows[0][at:]] + [
            r[:at] + ["live"] + r[at:] for r in rows[1:]]
        if name in ("price-history", "quarter-nav"):
            rows.insert(2, rows[1][:at] + ["superseded"] + rows[1][at + 1:])
        _write(store / f"{name}.csv", rows)
    results = (store / "quarter-results.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    restated = next(i for i, ln in enumerate(results) if "Restated:" in ln)
    results.insert(restated, results[restated].split('"Restated:')[0] + "\n")
    (store / "quarter-results.csv").write_text("".join(results), encoding="utf-8")
    return {("remove", "quarter-nav"): "1", ("remove", "quarter-results"): "1"}, set()


def _a_share_reading():
    """The demo's last-quarter cash reading the cash cases give a share reading for."""
    return next(r for r in _rows_of(schema.DEMO / "store" / "cash-readings.csv")[1:]
                if r[1] == "2026-09-30")


def _with_cash_in_three_places(store):
    """A statement's cash in its own column, the demo's cash readings bar the last quarter's gone
    from `cash-readings`, an unfunded account's statement carrying a cash of zero, a spread bet's
    carrying its funds as cash, and a share reading with its cash and total, at the figure of the
    cash reading on file for its day, so it is matched and not doubled."""
    cash = _rows_of(store / "cash-readings.csv")
    held = {(r[0], r[1]): r[2] for r in cash[1:]}
    rows = _rows_of(store / "account-statements.csv")
    at = rows[0].index("positions_value") + 1
    rows = [rows[0][:at] + ["cash"] + rows[0][at:]] + [
        r[:at] + [held.get((r[0], r[1]), "0.0" if "not yet funded" in r[-2] and r[2] else
                           "6500.0" if r[0].endswith("Spread bet") and r[1] == "2026-09-30" else "")]
        + r[at:] for r in rows[1:]]
    _write(store / "account-statements.csv", rows)
    kept = [r for r in cash[1:] if r[1] == "2026-09-30"]
    _write(store / "cash-readings.csv", cash[:1] + kept)
    readings = _rows_of(store / "account-readings.csv")
    at = readings[0].index("positions") + 1
    share = _a_share_reading()
    readings = [readings[0][:at] + ["stmt_value", "recon_cash"] + readings[0][at:]] + [
        r[:at] + ["", ""] + r[at:] for r in readings[1:]] + [
        [share[0], share[1], "", "100.00", f"{100.0 + float(share[2]):.2f}", share[2],
         *[""] * (len(readings[0]) - 4 - 2), share[3], share[4]]]
    _write(store / "account-readings.csv", readings)
    return {("append", "cash-readings"): str(len(cash) - 1 - len(kept))}, {"account-readings.csv"}


def _money_as_it_came(store):
    """Money written as it came — 1234.5, 0.0 — in the record's tables and the account history."""
    from portfusion.history import files
    money = {t.name: [f.name for f in t.fields if f.exact] for t in schema.TABLES.values()}
    money["account-statements"] = list(files.ACCOUNT_MONEY)
    touched = set()
    for name, cols in money.items():
        rows = _rows_of(store / f"{name}.csv")
        at = [rows[0].index(c) for c in cols]
        for r in rows[1:]:
            for j in at:
                if r[j].endswith("0") and "." in r[j]:
                    r[j] = r[j][:-1]
                    touched.add(name)
        _write(store / f"{name}.csv", rows)
    assert {"buys", "account-statements"} <= touched, touched
    return {("replace", t): None for t in touched if t in schema.TABLES}, set()


@pytest.mark.parametrize("step, old_shape", [
    pytest.param(1, _out_of_date_order, id="date order and ids"),
    pytest.param(2, _with_retired_tables, id="two tables retired"),
    pytest.param(3, _with_the_lifecycle, id="the lifecycle column"),
    pytest.param(4, _with_cash_in_three_places, id="cash in three places"),
    pytest.param(5, _money_as_it_came, id="money as it came")])
def test_a_book_one_move_behind_is_carried_to_the_demo(tmp_path, step, old_shape):
    """The move planned is that one, and it lands the demo exactly: every file the demo's bytes,
    no file the demo lacks, the journal the demo's plus the rows the move must write, and nothing
    left to move after it."""
    book, store = _demo_copy(tmp_path)
    journal, may_differ = old_shape(store)

    m, changes = M.plan(book)
    assert m is M.MIGRATIONS[step] and changes, f"planned {m and m.issue!r}"
    M.write(changes)

    demo = schema.DEMO / "store"
    assert sorted(p.name for p in store.glob("*.csv")) == sorted(p.name for p in demo.glob("*.csv"))
    for p in sorted(demo.glob("*.csv")):
        got, want = (store / p.name).read_bytes(), p.read_bytes()
        if p.name in may_differ:
            assert got.splitlines()[0] == want.splitlines()[0], f"{p.name}'s header moved wrong"
        elif p.name != "journal.csv":
            assert got == want, f"{p.name} moved wrong"
    said = (store / "journal.csv").read_text(encoding="utf-8")
    assert said.startswith((demo / "journal.csv").read_text(encoding="utf-8"))
    added = {(r[2], r[3]): r[4] for r in csv.reader(io.StringIO(said)) if r[1] == "migrate"}
    assert set(added) == set(journal) and all(
        added[k] == n for k, n in journal.items() if n is not None), added
    assert M.plan(book) == (None, []), "a book in this release's shape still planned a move"


# =====================================================================================
# WHAT A MOVE WILL NOT PLACE: refused by name, to be moved by hand, writing nothing.
# =====================================================================================

def _two_cash_figures_for_one_day(store):
    """A reading's cash, adding up with its stock to its total, at another figure than the cash
    reading of its day."""
    _with_cash_in_three_places(store)
    share, path = _a_share_reading(), store / "account-readings.csv"
    cash = float(share[2])
    path.write_text(path.read_text(encoding="utf-8").replace(
        f",{100.0 + cash:.2f},{share[2]},", f",{101.0 + cash:.2f},{cash + 1:.2f},", 1),
        encoding="utf-8")


def _a_total_its_stock_and_cash_do_not_make(store):
    """The total leaves with its column, so one that never agreed would take the only sign that a
    figure was mistyped with it."""
    _with_cash_in_three_places(store)
    share, path = _a_share_reading(), store / "account-readings.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(
        f",{100.0 + float(share[2]):.2f},", ",1.00,", 1), encoding="utf-8")


def _statement_cash_no_document_names(store):
    """A statement's cash whose source names no class, so it cannot say what retrieves it."""
    _with_cash_in_three_places(store)
    rows = _rows_of(store / "account-statements.csv")
    row = next(r for r in rows[1:] if r[rows[0].index("cash")] not in ("", "0.0")
               and not r[0].endswith("Spread bet"))
    row[rows[0].index("source")], row[rows[0].index("cash")] = "a figure typed in", "12.34"
    _write(store / "account-statements.csv", rows)


def _a_sum_beyond_pennies(store):
    """A sum of money with more places than pennies: writing it to the penny would move it."""
    rows = _rows_of(store / "capital-movements.csv")
    rows[1][rows[0].index("amount")] = "12.345"
    _write(store / "capital-movements.csv", rows)


@pytest.mark.parametrize("break_it, says", [
    pytest.param(_two_cash_figures_for_one_day, "cash-readings.csv says", id="two cash figures"),
    pytest.param(_a_total_its_stock_and_cash_do_not_make, "is not its total", id="a total"),
    pytest.param(_statement_cash_no_document_names, "names no evidence class", id="no document"),
    pytest.param(_a_sum_beyond_pennies, "not a sum to the penny", id="beyond pennies")])
def test_a_figure_a_move_cannot_place_is_refused_by_name(tmp_path, break_it, says):
    book, store = _demo_copy(tmp_path)
    break_it(store)
    before = {p: p.read_bytes() for p in store.iterdir()}
    with pytest.raises(ValueError, match=f"{says}.*move it by hand"):
        M.plan(book)
    assert {p: p.read_bytes() for p in store.iterdir()} == before, "a refused plan wrote"


def test_cash_a_document_never_stated_is_not_made_a_cash_reading(tmp_path):
    """A statement banked off ii's holdings export, which states no cash, carrying a cash figure
    another document gave: the column leaves and no cash reading is credited to the export."""
    book, store = _demo_copy(tmp_path)
    _with_cash_in_three_places(store)
    rows = _rows_of(store / "account-statements.csv")
    isa = next(r for r in rows[1:] if r[1] == "2026-06-30" and r[rows[0].index("cash")])
    isa[rows[0].index("source")] = f"ii valuation 30 Jun 2026 14:05 ({isa[0]})"
    _write(store / "account-statements.csv", rows)
    cash = store / "cash-readings.csv"
    before = cash.read_text(encoding="utf-8")

    _m, changes = M.plan(book)
    moved = next(c for c in changes if c.to == cash)
    assert f"{isa[0]},2026-06-30," not in moved.text, "the export was credited with a cash figure"
    assert any("does not state" in line for c in changes for line in c.said), changes
    assert moved.text.count("\n") == before.count("\n") + 4, "the other figures did not come"


def test_a_book_two_moves_behind_is_carried_through_both_before_it_is_opened(tmp_path):
    """A book in the old names AND out of date order would not load between the two moves, so
    `carry()` writes every one before the book is opened, each planned from the shape the last
    left, and `put_back()` returns it whole."""
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    store = book / "store"
    sales = (store / "sales.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    (store / "sales.csv").write_text("".join([sales[0], *reversed(sales[1:])]), encoding="utf-8")
    for m in M.MIGRATIONS:
        _backwards(m, book)
    old = {p: p.read_bytes() for p in book.rglob("*") if p.is_file()}

    done, before = M.carry(book)
    assert done == list(M.MIGRATIONS[:2]), [m.issue for m in done]
    assert (store / "sales.csv").read_bytes() == (schema.DEMO / "store" / "sales.csv").read_bytes()
    assert M.plan(book) == (None, [])
    M.put_back(before)
    assert {p: p.read_bytes() for p in book.rglob("*") if p.is_file()} == old


def test_a_books_check_naming_a_retired_table_is_listed_to_move_by_hand(tmp_path):
    """The book's own checks/ are its code: a line reading a retired table is listed, so the
    owner hears of it before the moved book's guard does."""
    (tmp_path / "checks").mkdir()
    (tmp_path / "checks" / "test_mine.py").write_text(
        'rows = schema.load("realisations")\nfirst = D.dec_rows[0]\nfine = D.sales\n',
        encoding="utf-8")
    assert M.named_in_checks(tmp_path) == [
        'test_mine.py:1: rows = schema.load("realisations")', "test_mine.py:2: first = D.dec_rows[0]"]

