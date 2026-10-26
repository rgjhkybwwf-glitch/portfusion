"""THE MIGRATION FRAMEWORK, held by running a move backwards and then forwards.

A move is data (`record/migrations.py`), so a copy of the demo can be put back into the shape
before one; `plan()` and `write()` must then carry it to the demo exactly, byte for byte, and
`put_back()` must return it to the old shape exactly. The moves here are made up for the test, and
installed in place of the release's own: a move that renamed a name the demo does not use, or lost
a row's bytes on the way, fails here.
"""
import csv
import io
import json
import pathlib
import shutil

from portfusion.record import migrations as M, schema

#: A MADE-UP MOVE: a table renamed, a column renamed, and the buys' one money column split by
#: each line's `held_as`, with a pattern a book's checks might read the old table by.
RENAME = M.Migration(
    issue="a made-up rename",
    tables={"purchases": "buys"},
    columns={"buys": {"ref": "trade_id"}},
    splits={"buys": ("amount", {"shares": "cost", "spread bet": "level_points"}, "ticker")},
    marks={}, code=(r"\bD\.purchases\b",))

#: A MADE-UP MOVE OF ROWS: a file the release no longer reads, removed.
LEFTOVER = "leftover.txt"
SWEEP = M.Migration(
    issue="a made-up sweep", tables={}, columns={}, splits={}, marks={}, code=(),
    rows=lambda store: [M.Change(store / LEFTOVER, store / LEFTOVER, None, [f"remove {LEFTOVER}"])]
    if (store / LEFTOVER).exists() else [])


def _demo_copy(tmp_path):
    book = tmp_path / "book"
    for part in ("store", "_archive"):
        shutil.copytree(schema.DEMO / part, book / part)
    return book


def _files(book):
    return {p.relative_to(book): p.read_bytes() for p in book.rglob("*") if p.is_file()}


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


def test_a_book_in_the_old_shape_is_carried_to_this_release_and_can_be_put_back(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(M, "MIGRATIONS", (RENAME,))
    book = _demo_copy(tmp_path)
    _backwards(RENAME, book)
    assert (book / "store" / "purchases.csv").exists() and not (book / "store" / "buys.csv").exists()
    # AN OPEN ITEM ON THE BENCH, a bet's buy in the old shape: its level lands in level_points.
    bet = next(r["ticker"] for r in csv.DictReader((schema.DEMO / "store" / "securities.csv").open())
               if r["held_as"] == "spread bet")
    (book / "_inbox" / ".bench").mkdir(parents=True)
    (book / "_inbox" / ".bench" / "B-T.json").write_text(json.dumps({"id": "B-T", "rows": [
        {"table": "purchases", "values": {"ref": "T-999", "ticker": bet, "amount": "9850.0"},
         "derived": ["ref"]}]}, indent=2))
    old = _files(book)

    m, changes = M.plan(book)
    assert m is RENAME and changes, "the old shape planned no move"
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
    assert _files(book) == old, "put_back() did not return the book to its old shape"

    # THE COMMAND: a moved book that will not open or audit is put back, byte for byte; one that
    # does stays moved; the demo is the generator's to move.
    from portfusion import check
    from portfusion.migrate.__main__ import main
    monkeypatch.setattr(schema, "BOOK", book)
    monkeypatch.setattr(check, "migrated", lambda b: 1)
    assert main(["--write"]) == 1
    assert _files(book) == old, "the command did not put the book back"
    monkeypatch.setattr(check, "migrated", lambda b: 0)
    capsys.readouterr()
    assert main(["--write"]) == 0 and "Moved:" in capsys.readouterr().out
    assert not (book / "store" / "purchases.csv").exists(), "the command did not move the book"
    _backwards(RENAME, book)
    monkeypatch.setattr(schema, "DEMO", book)
    assert main(["--write"]) == 2
    assert (book / "store" / "purchases.csv").exists(), "the demo was moved"


def test_a_book_two_moves_behind_is_carried_through_both_before_it_is_opened(tmp_path, monkeypatch):
    """A book in the old names AND holding a file a later move removes would not load between the
    two, so `carry()` writes every one before the book is opened, each planned from the shape the
    last left, and `put_back()` returns it whole, the removed file with it."""
    monkeypatch.setattr(M, "MIGRATIONS", (RENAME, SWEEP))
    book = _demo_copy(tmp_path)
    _backwards(RENAME, book)
    (book / "store" / LEFTOVER).write_text("read by nothing\n", encoding="utf-8")
    old = _files(book)

    done, before = M.carry(book)
    assert done == [RENAME, SWEEP], [m.issue for m in done]
    assert not (book / "store" / LEFTOVER).exists()
    assert (book / "store" / "buys.csv").read_bytes() == (schema.DEMO / "store" / "buys.csv").read_bytes()
    assert M.plan(book) == (None, [])
    M.put_back(before)
    assert _files(book) == old


def test_a_book_holding_the_flag_lists_is_refused_carried_and_opens(tmp_path):
    """THIS RELEASE'S MOVE, on the demo put back before it. Its settings hold the TradingView flag
    lists' three rows, counted when its journal opened, and the loader refuses the book naming
    one. `carry()` removes them and journals the removal, so the book opens and its journal still
    closes; `put_back()` returns the old shape byte for byte. A book in this release's shape has
    nothing to carry, and a check reading a flag list is listed to move by hand."""
    import pytest
    import portfusion
    from portfusion.engine import Book
    from portfusion.record import rules
    book = _demo_copy(tmp_path)
    assert M.plan(book) == (None, []) and M.carry(book) == ([], {})

    store = book / "store"
    def rewrite(name, fn):
        rows = list(csv.reader(io.StringIO((store / name).read_text(encoding="utf-8"))))
        out = io.StringIO()
        csv.writer(out, lineterminator="\n").writerows(fn(rows))
        (store / name).write_text(out.getvalue(), encoding="utf-8")
    rewrite("settings.csv", lambda rows: rows + [[k, f"10000000{i}"]
                                                 for i, k in enumerate(M.FLAG_LISTS, 1)])
    rewrite("journal.csv", lambda rows: [
        r[:4] + [str(int(r[4]) + 3)] + r[5:] if r[1:4] == ["baseline", "open", "settings"] else r
        for r in rows])
    (book / "checks").mkdir()
    (book / "checks" / "test_mine.py").write_text('lists = D.SETTINGS["tv_list_live"]\n')
    old = _files(book)
    with pytest.raises(ValueError, match="'tv_list_live' is not one of"):
        with rules.store_at(store):
            pass
    assert M.named_in_checks(book) == ['test_mine.py:1: lists = D.SETTINGS["tv_list_live"]']

    done, before = M.carry(book)
    assert done == list(M.MIGRATIONS)
    assert (store / "settings.csv").read_bytes() == (schema.DEMO / "store" / "settings.csv").read_bytes()
    added = (store / "journal.csv").read_bytes()[len(old[pathlib.Path("store/journal.csv")]):]
    assert added.decode().split(",")[1:6] == [
        "migrate", "remove", "settings", "3", f"portfusion {portfusion.__version__}"], added
    assert M.plan(book) == (None, []), "a moved book still planned a move"
    with rules.store_at(store):
        assert "tv_list_live" not in rules.SETTINGS
        assert Book().journal_unaccounted().empty, "the journal no longer closes"

    M.put_back(before)
    assert _files(book) == old, "put_back() did not return the book to its old shape"


def test_a_books_check_naming_an_old_table_is_listed_to_move_by_hand(tmp_path, monkeypatch):
    """The book's own checks/ are its code: a line reading an old table, quoted or by a declared
    pattern, is listed, so the owner hears of it before the moved book's guard does."""
    monkeypatch.setattr(M, "MIGRATIONS", (RENAME,))
    (tmp_path / "checks").mkdir()
    (tmp_path / "checks" / "test_mine.py").write_text(
        'rows = schema.load("purchases")\nfirst = D.purchases[0]\nfine = D.buys\nnone = ""\n',
        encoding="utf-8")
    assert M.named_in_checks(tmp_path) == [
        'test_mine.py:1: rows = schema.load("purchases")', "test_mine.py:2: first = D.purchases[0]"]


def test_with_nothing_declared_no_check_is_listed(tmp_path, monkeypatch):
    """No old name and no pattern match nothing, not every empty string a check quotes."""
    monkeypatch.setattr(M, "MIGRATIONS", ())
    (tmp_path / "checks").mkdir()
    (tmp_path / "checks" / "test_mine.py").write_text("blank = \"\"\nalso = ''\n", encoding="utf-8")
    assert M.named_in_checks(tmp_path) == []
