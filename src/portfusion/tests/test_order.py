"""THE RECORD'S ONE ORDER — `record/order.py`, and the loader that holds a book to it.

The order's rules are held here on rows written in the test; that the loaded book keeps them is
the loader's, which refuses a table out of order or an id not its place, and is shown to.
"""
import pytest

from portfusion.record import order

_ACCOUNTS = ["Isa", "Bet"]
_BUYS = ["trade_id", "date", "account", "ticker", "note"]
_SALES = ["sale_id", "date", "account", "ticker", "closes", "note"]


def test_a_row_goes_where_its_date_puts_it_and_after_any_it_ties_with():
    rows = [["T-001", "2026-01-05", "Isa", "AAA", ""], ["T-002", "2026-03-01", "Bet", "BBB", ""]]
    tie = ["T-003", "2026-01-05", "Isa", "AAA", "the later entry"]
    early = ["T-004", "2026-01-05", "Isa", "AA", ""]
    other = ["T-005", "2026-01-05", "Bet", "AAA", ""]
    got = order.placed("buys", _BUYS, rows, [tie, early, other], _ACCOUNTS)
    assert got == [early, rows[0], tie, other, rows[1]], "date, then account, then ticker"


def test_a_backdated_buy_renumbers_what_follows_and_every_reference_follows():
    buys = [["T-001", "2026-01-05", "Isa", "AAA", ""],
            ["T-003", "2026-02-01", "Isa", "CCC", "rolled from T-001; T-999 is not on file"],
            ["T-002", "2026-03-01", "Bet", "BBB", ""]]
    sales = [["E-001", "2026-04-01", "Bet", "BBB", "T-002", "closes T-002"]]
    b, s, moves = order.renumbered((_BUYS, buys), (_SALES, sales))
    assert [r[0] for r in b] == ["T-001", "T-002", "T-003"]
    assert b[1][4] == "rolled from T-001; T-999 is not on file", "an id no row holds stays"
    assert s[0][4:] == ["T-003", "closes T-003"], "the sale follows the leg it closes"
    assert b[0] is buys[0] and moves == {"buys": [("T-003", "T-002"), ("T-002", "T-003")],
                                         "sales": []}
    assert order.said(moves) == ["T-002 becomes T-003", "T-003 becomes T-002"], "by the id it was"


def test_two_rows_holding_one_id_are_refused_rather_than_followed():
    buys = [["T-001", "2026-01-05", "Isa", "AAA", ""], ["T-001", "2026-02-01", "Isa", "CCC", ""]]
    with pytest.raises(ValueError, match="T-001"):
        order.renumbered((_BUYS, buys), (_SALES, []))


def test_a_door_refuses_a_file_with_a_cell_spanning_lines(store_copy):
    """Placed line by line, such a cell would split into two broken rows; it is moved by hand."""
    import csv
    from portfusion.desk.doors import commit
    from portfusion.record import schema
    header = schema.TABLES["income"].header
    with (store_copy / "income.csv").open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh, lineterminator="\n").writerow(
            ["2099-01-01" if c == "date" else "a note\nin two lines" if c == "note" else ""
             for c in header])
    with pytest.raises(ValueError, match="spans lines"):
        commit.placed({"income": []})


def test_a_run_of_moved_ids_is_said_as_one():
    moves = {"buys": [(f"T-{n:03d}", f"T-{n + 1:03d}") for n in range(90, 103)]}
    assert order.said(moves) == ["T-090 to T-102 become T-091 to T-103"]


def test_the_loader_finds_a_row_out_of_order_and_an_id_not_its_place():
    rows = [["T-001", "2026-01-05", "Isa", "AAA", ""], ["T-002", "2026-01-04", "Isa", "AAA", ""]]
    assert order.out_of_order("buys", _BUYS, rows, _ACCOUNTS) == 2, "the second row, after the header"
    assert order.misnumbered("buys", _BUYS, [rows[1], rows[0]]) == 1
    assert order.misnumbered("buys", _BUYS, [["T-001", *rows[1][1:]], ["T-002", *rows[0][1:]]]) is None


@pytest.mark.parametrize("table", ["buys", "income"])
def test_a_hand_edit_out_of_date_order_is_refused_on_load(store_copy, table):
    """A row moved to the end of its file by hand: the record will not load, and says which
    table."""
    from portfusion.record import rules
    path = store_copy / f"{table}.csv"
    head, *lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(lines) < 2 or len({ln.split(",")[1 if table == "buys" else 0] for ln in lines}) < 2:
        pytest.skip(f"the book holds no two {table} rows on different days")
    path.write_text(head + "".join(lines[1:] + lines[:1]), encoding="utf-8")
    with pytest.raises(ValueError, match=rf"NOT IN DATE ORDER:\n  {table}\.csv"):
        rules.reload_store()


def test_a_buy_numbered_out_of_its_place_is_refused_on_load(store_copy):
    from portfusion.record import rules
    path = store_copy / "buys.csv"
    text = path.read_text(encoding="utf-8")
    if "T-002," not in text or ",T-002," in (store_copy / "sales.csv").read_text(encoding="utf-8"):
        pytest.skip("the book holds fewer than two buys, or a sale names its second")
    path.write_text(text.replace("T-002,", "T-999,", 1), encoding="utf-8")
    with pytest.raises(ValueError, match=r"buys\.csv row 2's id is not its place"):
        rules.reload_store()
