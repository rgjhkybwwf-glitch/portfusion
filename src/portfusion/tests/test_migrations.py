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


def test_a_book_out_of_date_order_is_put_in_it_and_numbered_by_it(tmp_path):
    """The record reads as it happened (`record/order.py`). A demo copy with its first buy moved to
    the bottom, the sales out of order, and the retired `trade_id_floor` back in its settings is
    carried to the demo exactly: every table in date order, every id its place, and a sale's
    `closes` following the leg it named. Rows that tie on date, account and ticker keep their file
    order, which is why the buy moved is one that ties with none."""
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    store = book / "store"
    buys = (store / "buys.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    sales = (store / "sales.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    # THE OLD NUMBERS: the first buy last and numbered after the rest, every other one down by one.
    last = f"T-{len(buys) - 1:03d}"
    old = {f"T-{n:03d}": f"T-{n - 1:03d}" for n in range(2, len(buys))} | {"T-001": last}
    moved = [buys[0]] + [line.replace(line.split(",")[0], old[line.split(",")[0]], 1)
                         for line in buys[2:] + buys[1:2]]
    (store / "buys.csv").write_text("".join(moved), encoding="utf-8")
    (store / "sales.csv").write_text(re.sub(r",(T-\d{3}),", lambda m: f",{old[m.group(1)]},",
                                            "".join([sales[0], *reversed(sales[1:])])),
                                     encoding="utf-8")
    with (store / "settings.csv").open("a", encoding="utf-8") as fh:
        fh.write("trade_id_floor,T-050\n")

    m, changes = M.plan(book)
    assert m is M.MIGRATIONS[1] and changes, "a book out of date order planned no move"
    M.write(changes)
    for p in sorted((schema.DEMO / "store").glob("*.csv")):
        if p.name != "journal.csv":
            assert (store / p.name).read_bytes() == p.read_bytes(), f"{p.name} moved wrong"
    # THE JOURNAL SAYS WHAT MOVED, after the demo's own rows, or the audit would find rows no
    # route accounts for.
    said = (store / "journal.csv").read_text(encoding="utf-8")
    assert said.startswith((schema.DEMO / "store" / "journal.csv").read_text(encoding="utf-8"))
    added = [r for r in csv.reader(io.StringIO(said)) if r[1] == "migrate"]
    assert {(r[2], r[3]) for r in added} == {
        ("replace", "buys"), ("replace", "sales"), ("remove", "settings")}, added
    assert M.plan(book) == (None, []), "a book in date order still planned a move"


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


def test_a_retired_table_leaves_with_the_journal_rows_that_name_it(tmp_path):
    """A demo copy holding the two retired tables, as a book made before they went does, and
    journal rows naming them: the files go and so do those rows, and the book is the demo again."""
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    store = book / "store"
    (store / "realisations.csv").write_text("ticker,realisation_id,opened,note\n", encoding="utf-8")
    (store / "baseline-reconstruction.csv").write_text(
        "as_of,ticker,qty,price,source,rate,quality\n", encoding="utf-8")
    journal = store / "journal.csv"
    lines = journal.read_text(encoding="utf-8").splitlines(keepends=True)
    opening = next(ln for ln in lines if ",baseline,open," in ln)
    journal.write_text("".join(lines[:2] + [
        opening.replace(f",{opening.split(',')[3]},", f",{t},", 1)
        for t in M.RETIRED] + lines[2:]), encoding="utf-8")

    m, changes = M.plan(book)
    assert m is M.MIGRATIONS[2] and changes, "the retired tables planned no move"
    M.write(changes)
    for name in M.RETIRED:
        assert not (store / f"{name}.csv").exists(), f"{name}.csv is still in the store"
    assert journal.read_bytes() == (schema.DEMO / "store" / "journal.csv").read_bytes()
    assert M.plan(book) == (None, []), "a book with no retired table still planned a move"


def test_a_book_with_the_lifecycle_loses_the_column_and_every_row_it_kept_beside_another(tmp_path):
    """A demo copy in the shape before a correction replaced its row: `status` in its five tables, a
    superseded row beside a live one in a history and in quarter-nav, and a restated quarter's
    first row before its restatement. The column goes, those rows with it, the journal says so of
    the tables it counts, and the book is the demo again."""
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    store = book / "store"
    after = {"price-history": "struck", "fx-history": "struck", "account-statements": "quality",
             "quarter-nav": "quality", "quarter-snapshots": "quality"}
    for name, col in after.items():
        rows = list(csv.reader(io.StringIO((store / f"{name}.csv").read_text(encoding="utf-8"))))
        at = rows[0].index(col) + 1
        rows = [rows[0][:at] + ["status"] + rows[0][at:]] + [r[:at] + ["live"] + r[at:] for r in rows[1:]]
        if name in ("price-history", "quarter-nav"):
            rows.insert(2, rows[1][:at] + ["superseded"] + rows[1][at + 1:])
        out = io.StringIO()
        csv.writer(out, lineterminator="\n").writerows(rows)
        (store / f"{name}.csv").write_text(out.getvalue(), encoding="utf-8")
    results = (store / "quarter-results.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    restated = next(i for i, ln in enumerate(results) if "Restated:" in ln)
    results.insert(restated, results[restated].split('"Restated:')[0] + "\n")
    (store / "quarter-results.csv").write_text("".join(results), encoding="utf-8")

    m, changes = M.plan(book)
    assert m is M.MIGRATIONS[3] and changes, "a book with the lifecycle planned no move"
    M.write(changes)
    for p in sorted((schema.DEMO / "store").glob("*.csv")):
        if p.name != "journal.csv":
            assert (store / p.name).read_bytes() == p.read_bytes(), f"{p.name} moved wrong"
    said = (store / "journal.csv").read_text(encoding="utf-8")
    assert said.startswith((schema.DEMO / "store" / "journal.csv").read_text(encoding="utf-8"))
    added = [r for r in csv.reader(io.StringIO(said)) if r[1] == "migrate"]
    assert {(r[2], r[3], r[4]) for r in added} == {
        ("remove", "quarter-nav", "1"), ("remove", "quarter-results", "1")}, added
    assert M.plan(book) == (None, []), "a book without the lifecycle still planned a move"


def _with_cash_in_three_places(tmp_path):
    """A demo copy in the shape before cash had one place: a statement's cash in its own column,
    the demo's cash readings bar the last quarter's gone from `cash-readings`, an unfunded
    account's statement carrying a cash of zero, a spread bet's statement carrying its funds as
    cash, and a share reading with its cash and total."""
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    store = book / "store"
    cash = list(csv.reader((store / "cash-readings.csv").open(encoding="utf-8")))
    held = {(r[0], r[1]): r[2] for r in cash[1:]}
    rows = list(csv.reader((store / "account-statements.csv").open(encoding="utf-8")))
    at = rows[0].index("positions_value") + 1
    rows = [rows[0][:at] + ["cash"] + rows[0][at:]] + [
        r[:at] + [held.get((r[0], r[1]), "0.0" if "not yet funded" in r[-2] and r[2] else
                           "6500.0" if r[0].endswith("Spread bet") and r[1] == "2026-09-30" else "")]
        + r[at:] for r in rows[1:]]
    _write(store / "account-statements.csv", rows)
    _write(store / "cash-readings.csv", cash[:1] + [r for r in cash[1:] if r[1] == "2026-09-30"])
    readings = list(csv.reader((store / "account-readings.csv").open(encoding="utf-8")))
    at = readings[0].index("positions") + 1
    share = next(r for r in cash[1:] if r[1] == "2026-09-30")
    readings = [readings[0][:at] + ["stmt_value", "recon_cash"] + readings[0][at:]] + [
        r[:at] + ["", ""] + r[at:] for r in readings[1:]] + [
        [share[0], share[1], "", "100.00", f"{100.0 + float(share[2]):.2f}", share[2],
         *[""] * (len(readings[0]) - 4 - 2), share[3], share[4]]]
    _write(store / "account-readings.csv", readings)
    return book, store, share


def _write(path, rows):
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")


def test_a_share_accounts_cash_is_carried_into_its_cash_readings(tmp_path):
    """Each statement's cash becomes a cash reading of its day, its class and reference read back
    out of its source; a reading's cash on file at the same figure is not doubled; a zero no
    document names goes; the columns leave; and the journal counts what came in."""
    book, store, share = _with_cash_in_three_places(tmp_path)

    m, changes = M.plan(book)
    assert m is M.MIGRATIONS[4] and changes, "cash in three places planned no move"
    M.write(changes)
    for name in ("cash-readings.csv", "account-statements.csv"):
        assert (store / name).read_bytes() == (schema.DEMO / "store" / name).read_bytes(), name
    readings = list(csv.reader((store / "account-readings.csv").open(encoding="utf-8")))
    assert readings[0] == schema.TABLES["account-readings"].header
    assert readings[-1][:4] == [share[0], share[1], "", "100.00"], readings[-1]
    added = [r for r in csv.reader((store / "journal.csv").open(encoding="utf-8"))
             if r[1] == "migrate"]
    want = len(list(csv.reader((schema.DEMO / "store" / "cash-readings.csv").open()))) - 3
    assert [(r[2], r[3], r[4]) for r in added] == [("append", "cash-readings", str(want))], added
    assert M.plan(book) == (None, []), "a book with cash in one place still planned a move"


def test_a_readings_total_its_stock_and_cash_do_not_make_is_moved_by_hand(tmp_path):
    """The total leaves with the column, so a reading whose three figures never agreed is refused
    rather than losing the one sign that a figure was mistyped."""
    book, store, share = _with_cash_in_three_places(tmp_path)
    path = store / "account-readings.csv"
    total = f"{100.0 + float(share[2]):.2f}"
    path.write_text(path.read_text(encoding="utf-8").replace(f",{total},", ",1.0,", 1),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="is not its total"):
        M.plan(book)


def test_cash_a_document_never_stated_is_not_made_a_cash_reading(tmp_path):
    """A statement banked off ii's holdings export, which states no cash, carrying a cash figure
    another document gave: the column leaves and no cash reading is credited to the export."""
    book, store, _share = _with_cash_in_three_places(tmp_path)
    path = store / "account-statements.csv"
    rows = list(csv.reader(path.open(encoding="utf-8")))
    at = rows[0].index("source")
    isa = next(r for r in rows[1:] if r[1] == "2026-06-30" and r[rows[0].index("cash")])
    isa[at] = f"ii valuation 30 Jun 2026 14:05 ({isa[0]})"
    _write(path, rows)
    cash = store / "cash-readings.csv"
    before = cash.read_text(encoding="utf-8")

    _m, changes = M.plan(book)
    moved = next(c for c in changes if c.to == cash)
    assert f"{isa[0]},2026-06-30," not in moved.text, "the export was credited with a cash figure"
    assert any("does not state" in line for c in changes for line in c.said), changes
    assert moved.text.count("\n") == before.count("\n") + 4, "the other figures did not come"


def test_two_cash_figures_for_one_day_are_moved_by_hand(tmp_path):
    """A reading's cash at another figure than the cash reading of its day: one of them is wrong,
    so the migration refuses and names the row, writing nothing."""
    book, store, share = _with_cash_in_three_places(tmp_path)
    path = store / "account-readings.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(
        f",{share[2]},", f",{float(share[2]) + 1},", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="move it by hand"):
        M.plan(book)


def test_every_sum_of_money_is_written_to_the_penny(tmp_path):
    """A demo copy with its money written as it came — 1234.5, 0.0 — in the record's tables and the
    account history is carried to the demo exactly, the journal saying which tables were rewritten,
    and a sum with more places than pennies is refused, to be moved by hand."""
    from portfusion.history import files
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    store = book / "store"
    money = {t.name: [f.name for f in t.fields if f.exact] for t in schema.TABLES.values()}
    money["account-statements"] = list(files.ACCOUNT_MONEY)
    touched = set()
    for name, cols in money.items():
        path = store / f"{name}.csv"
        rows = list(csv.reader(path.open(encoding="utf-8")))
        at = [rows[0].index(c) for c in cols]
        for r in rows[1:]:
            for j in at:
                if r[j].endswith("0") and "." in r[j]:
                    r[j] = r[j][:-1]
                    touched.add(name)
        _write(path, rows)
    assert {"buys", "account-statements"} <= touched, touched

    m, changes = M.plan(book)
    assert m is M.MIGRATIONS[5] and changes, "money as it came planned no move"
    M.write(changes)
    for p in sorted((schema.DEMO / "store").glob("*.csv")):
        if p.name != "journal.csv":
            assert (store / p.name).read_bytes() == p.read_bytes(), f"{p.name} moved wrong"
    added = {r[3] for r in csv.reader((store / "journal.csv").open(encoding="utf-8"))
             if r[1] == "migrate"}
    assert added == touched - {"account-statements"}, added
    assert M.plan(book) == (None, [])

    path = store / "capital-movements.csv"
    rows = list(csv.reader(path.open(encoding="utf-8")))
    rows[1][rows[0].index("amount")] = "12.345"
    _write(path, rows)
    with pytest.raises(ValueError, match="move it by hand"):
        M.plan(book)


def test_a_books_check_naming_a_retired_table_is_listed_to_move_by_hand(tmp_path):
    """The book's own checks/ are its code: a line reading a retired table is listed, so the
    owner hears of it before the moved book's guard does."""
    (tmp_path / "checks").mkdir()
    (tmp_path / "checks" / "test_mine.py").write_text(
        'rows = schema.load("realisations")\nfirst = D.dec_rows[0]\nfine = D.sales\n',
        encoding="utf-8")
    assert M.named_in_checks(tmp_path) == [
        'test_mine.py:1: rows = schema.load("realisations")', "test_mine.py:2: first = D.dec_rows[0]"]

