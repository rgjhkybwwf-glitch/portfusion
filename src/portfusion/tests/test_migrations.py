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
    assert m is M.MIGRATIONS[-1] and changes, "the retired tables planned no move"
    M.write(changes)
    for name in M.RETIRED:
        assert not (store / f"{name}.csv").exists(), f"{name}.csv is still in the store"
    assert journal.read_bytes() == (schema.DEMO / "store" / "journal.csv").read_bytes()
    assert M.plan(book) == (None, []), "a book with no retired table still planned a move"


def test_a_books_check_naming_a_retired_table_is_listed_to_move_by_hand(tmp_path):
    """The book's own checks/ are its code: a line reading a retired table is listed, so the
    owner hears of it before the moved book's guard does."""
    (tmp_path / "checks").mkdir()
    (tmp_path / "checks" / "test_mine.py").write_text(
        'rows = schema.load("realisations")\nfirst = D.dec_rows[0]\nfine = D.sales\n',
        encoding="utf-8")
    assert M.named_in_checks(tmp_path) == [
        'test_mine.py:1: rows = schema.load("realisations")', "test_mine.py:2: first = D.dec_rows[0]"]

