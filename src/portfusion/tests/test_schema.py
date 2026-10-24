"""
THE STORE — the CSV files, and the schema that validates them on load.

record/rules.py loads the CSV, so `schema.load("companies") == D.COMPANIES` is TRIVIALLY TRUE
— they are the same object — and a test that kept asserting it would look like a check and
prove nothing, the most expensive kind of test there is.

What guards a table instead:

  * the SCHEMA MECHANISM, round-tripped through a temp file, on data with every awkward
    type in it — proving the reader and writer are inverses
  * the CONTENT INVARIANTS below — uniqueness, the join between the two tables, and the
    controlled vocabularies. These do not need updating when a company is added, which
    is what makes them worth having.
  * and, outside this file, the engine's figures tied to the record: tests/test_engine_ties.py.

`tests/test_record.py` already covers trades -> identity (`test_every_traded_ticker_has_
an_identity_row`), and is not repeated here.
"""
import datetime as _dt

import pytest

from portfusion.record import schema
from harness import SRC, needs


# EVERY TABLE THE SCHEMA REGISTERS, so a new one fails until it is guarded.
FLIPPED = {"companies", "securities", "accounts", "capital-movements",
           "buys", "sales", "income", "quarter-nav", "fx",
           "current-prices",
           "quarter-snapshots", "account-readings", "reasoning",
           # Cash readings are their own table.
           "cash-readings",
           # Research notes are a table so a NEW note can be recorded at all. The research repo
           # stays the source of truth for a REF; this is the record of what the book cites, and
           # test_record.py ties the two together.
           "research-notes",
           # A closed quarter's results, written by the freeze from the engine and held against
           # it by test_engine_ties.py, so a closed quarter cannot move without a row saying why.
           "quarter-results",
           # The book's own settings: the dates and names the code may not type.
           "settings",
           # The IG contracts a spread-bet leg can be on, with their epics.
           "contracts",
           # The journal is the one table here that is ABOUT the record rather than part of it:
           # record time, one row per WRITE. record/rules.py does not load it — nothing in the
           # BUILD may depend on when a row was entered, only on what it says. Its own guards
           # are in test_journal.py.
           "journal"}


def test_every_registered_table_is_accounted_for():
    """A table in the schema that no test knows about is an unguarded table."""
    assert set(schema.TABLES) == FLIPPED


@pytest.mark.parametrize("name", sorted(schema.TABLES))
def test_the_file_header_matches_the_schema(name):
    """A column added to the CSV but not to the schema — or renamed in one and not the
    other — must fail at the door rather than be read positionally."""
    table = schema.TABLES[name]
    with table.path.open(encoding="utf-8") as fh:
        assert fh.readline().rstrip("\n").split(",") == table.header


#: "loads" runs on every book; "not empty" wherever the engine requires rows — which is every
#: table but these. research-notes is the register of another repository's notes, and a book
#: that has written none legitimately has none; its emptiness here is this book's own check,
#: below.
MAY_START_EMPTY = ("research-notes",)


@pytest.mark.parametrize("name", [n if n in MAY_START_EMPTY else pytest.param(n, marks=needs(n))
                                  for n in sorted(schema.TABLES)])
def test_the_table_loads_and_is_not_empty(name):
    """Validation runs on LOAD, so this exercises every cell in the file. An empty
    store that loaded cleanly would satisfy every other test here.

    A NEW BOOK HOLDS NO ROW YET, and each table says so as a skip rather than a failure; a book
    that lists its skips (`harness.SKIPS_FILE`) still fails the run on an empty table."""
    rows = schema.load(name)
    assert all(len(r) == len(schema.TABLES[name].fields) for r in rows)
    if name not in MAY_START_EMPTY:
        assert rows, f"{name}.csv holds no rows"


# =====================================================================================
# CONTENT INVARIANTS — true of the data whatever is in it
# =====================================================================================

def test_issuer_names_are_unique():
    """`company` is the join key. A duplicate would make the join ambiguous and the
    sector a coin toss."""
    names = [r[0] for r in schema.load("companies")]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"companies.csv has duplicate companies: {dupes}"


def test_security_codes_are_unique():
    codes = [r[0] for r in schema.load("securities")]
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    assert not dupes, f"securities.csv has duplicate codes: {dupes}"


def test_every_security_joins_to_an_issuer():
    """THE JOIN IS BY FULL LEGAL NAME, not by ticker. A security whose company does not appear
    in companies.csv silently loses its sector and region.
    """
    issuers = {r[0] for r in schema.load("companies")}
    orphans = sorted({(r[0], r[1]) for r in schema.load("securities") if r[1] not in issuers})
    assert not orphans, f"securities with no issuer row: {orphans}"


def test_one_issuer_may_hold_several_codes():
    """The reason these are two tables and not one. If this ever stops being true the
    merge becomes tempting, and merging loses the company-level exposure view."""
    from collections import Counter
    counts = Counter(r[1] for r in schema.load("securities"))
    multi = {co: n for co, n in counts.items() if n > 1}
    if not multi:
        pytest.skip("no issuer holds more than one code in this book")


def test_a_spread_bet_code_carries_the_suffix():
    """The ' SB' suffix and the kind column must agree. The suffix is the code's NAME, what
    tells ORLA SB from ORLA; the kind is the fact, and nothing decides from the name — but the
    two are stated once each and can disagree, so they are held together."""
    sh = schema.TABLES["securities"].header
    for r in schema.load("securities"):
        code, kind = r[sh.index("ticker")], r[sh.index("held_as")]
        if code.endswith(" SB"):
            assert kind == "spread bet", f"{code} is a spread bet marked {kind!r}"
        elif kind == "spread bet":
            pytest.fail(f"{code} is a spread bet but does not carry the ' SB' suffix")


# =====================================================================================
# THE SCHEMA MECHANISM — reader and writer are inverses
# =====================================================================================

def test_the_schema_round_trips_every_awkward_type(tmp_path, monkeypatch):
    """DUMP THEN LOAD, on a table containing all six awkward cases at once: a blank
    nullable string, a real empty string, a nullable and a non-nullable number, a date,
    a bool, and a value carrying the delimiter.

    It proves the mechanism on a table of its own.
    """
    table = schema.Table(name="synthetic", fields=(
        schema.Field("code", "str"),
        schema.Field("note", "str"),                  # "" is a real value
        schema.Field("detail", "str", null=True),     # blank means absent
        schema.Field("qty", "int"),
        schema.Field("stake", "float", null=True),
        schema.Field("opened", "date"),
        schema.Field("live", "bool"),
    ))
    monkeypatch.setitem(schema.TABLES, "synthetic", table)
    monkeypatch.setattr(schema, "STORE", tmp_path)

    rows = [
        ("GRVL", "", None, 64, None, _dt.date(2023, 4, 3), True),
        ("HALV SB", 'a note, with a comma and "quotes"', "present", 500, 5.0,
         _dt.date(2026, 8, 14), False),
    ]
    schema.dump("synthetic", rows)
    assert schema.load("synthetic") == rows


def _cell(kind, raw, null=False):
    return schema._parse(schema.Field("x", kind, null), raw, "t", 2)


def test_blank_is_none_only_where_the_schema_allows_it():
    """`None` and `""` ARE DIFFERENT AND BOTH OCCUR. income.note is genuinely the
    empty string; a spread bet's stake is genuinely absent. One blank cell cannot mean
    both, so the schema decides — and the test proves it decides."""
    assert _cell("str", "", null=True) is None
    assert _cell("str", "") == ""
    assert _cell("float", "", null=True) is None


def test_a_blank_number_that_is_not_nullable_is_refused():
    """A missing balance is a GAP, never zero. An account silently contributing nothing
    would understate net asset value and no check would catch it."""
    with pytest.raises(ValueError, match="never zero"):
        _cell("float", "")


def test_an_integer_column_refuses_a_float():
    """Quantities are whole numbers and money is not. 4375.0 written where 4375 belongs
    reaches every page looking entirely plausible."""
    assert _cell("int", "4375") == 4375
    with pytest.raises(ValueError):
        _cell("int", "4375.0")


def test_money_is_written_to_the_penny_and_a_quote_to_at_most_six_places():
    """ONE FORMATTER FOR EVERY WRITER (`schema.cell()`): a sum of money always two places, never
    rounded from more; a price, rate or level rounded to six and its trailing noughts dropped."""
    money = schema.Field("m", "float", **schema.MONEY)
    quote = schema.Field("q", "float", **schema.QUOTE)
    assert [schema.cell(money, v) for v in (1234.5, "0", 7, None, "")] == [
        "1234.50", "0.00", "7.00", "", ""]
    with pytest.raises(ValueError, match="sum to 2 decimal places"):
        schema.cell(money, 12.345)
    assert [schema.cell(quote, v) for v in (0.1235, "2", 1.2917000001)] == ["0.1235", "2.0", "1.2917"]
    assert schema.cell(money, -0.0) == "0.00" and schema.cell(money, 12345678.91) == "12345678.91"
    from portfusion.desk.intake import bench
    [line] = bench.paste_block({"rows": [{"table": "capital-movements",
                                          "values": {"amount": "12.345", "account": "x"}}]})
    assert "12.345" in line["line"], "a figure the gate refuses vanished from its own line"
    from portfusion.desk.doors import commit
    assert commit._rendered("capital-movements", {"amount": "250"})[2] == "250.00"


@pytest.mark.parametrize("field, text", [
    (schema.Field("m", "float", **schema.MONEY), "1234.5"),
    (schema.Field("m", "float", **schema.MONEY), "1234.567"),
    (schema.Field("q", "float", **schema.QUOTE), "1.2345678"),
    (schema.Field("q", "float", **schema.QUOTE), "1e-3")])
def test_a_figure_written_to_other_places_is_refused_on_load(field, text):
    """Money written to one place, or a quote to seven, is refused where the cell is read, the
    refusal saying the places and nothing more."""
    with pytest.raises(ValueError, match="decimal places$"):
        schema._parse(field, text, "t", 2)


def test_every_figure_column_declares_its_places():
    """A float column with no places is a figure written however its writer liked."""
    loose = [f"{t.name}.{f.name}" for t in schema.TABLES.values() for f in t.fields
             if f.kind == "float" and f.places is None]
    assert not loose, loose


def test_the_number_kind_preserves_int_against_float():
    """A SPREAD-BET STAKE MIXES THEM, 1 or 0.25. Declaring it float would be a silent reshape no
    equality test could see, because 1 == 1.0. `number` mirrors what the text says."""
    assert _cell("number", "1") == 1 and isinstance(_cell("number", "1"), int)
    assert _cell("number", "1.0") == 1.0 and isinstance(_cell("number", "1.0"), float)
    assert _cell("number", "0.25") == 0.25
    assert schema._render(schema.Field("x", "number"), 1) == "1"
    assert schema._render(schema.Field("x", "number"), 1.0) == "1.0"


def test_a_date_comes_back_as_a_date():
    """Not as a string that happens to look like one — a date column holds real date objects
    and the ledger compares against them."""
    assert _cell("date", "2026-06-30") == _dt.date(2026, 6, 30)
    with pytest.raises(ValueError):
        _cell("date", "30/06/2026")


def test_a_bad_boolean_is_refused_rather_than_read_as_true():
    assert _cell("bool", "true") is True and _cell("bool", "false") is False
    with pytest.raises(ValueError):
        _cell("bool", "maybe")


def test_the_error_names_the_table_row_and_column():
    """A validation failure has to say WHERE. 'invalid literal for int()' on a
    400-row store is not a diagnosis."""
    with pytest.raises(ValueError) as exc:
        schema._parse(schema.Field("qty", "int", False), "twelve", "buys", 47)
    assert "buys.csv row 47" in str(exc.value) and "'qty'" in str(exc.value)


def test_writing_none_into_a_non_nullable_column_is_refused():
    """The inverse of the read rule, and it must fail on WRITE — otherwise the round
    trip loses the distinction silently and the CSV is already wrong."""
    with pytest.raises(ValueError):
        schema._render(schema.Field("x", "str", null=False), None)
    assert schema._render(schema.Field("x", "str", null=True), None) == ""


def test_a_short_row_is_refused(tmp_path, monkeypatch):
    """A hand-edited CSV with a missing comma must FAIL, not shift every column left.
    Written to a real file and loaded, because that is the path a real edit takes."""
    table = schema.TABLES["companies"]
    monkeypatch.setattr(schema, "STORE", tmp_path)
    n = len(table.header)
    table.path.write_text(",".join(table.header) + "\n" + ",".join(["x"] * (n - 1)) + "\n",
                          encoding="utf-8")
    with pytest.raises(ValueError, match=f"{n - 1} cells, expected {n}"):
        schema.load("companies")


def test_a_renamed_column_is_refused(tmp_path, monkeypatch):
    """The header IS the contract. Renaming a column in the file without renaming it in
    the schema must stop everything, rather than being read by position."""
    table = schema.TABLES["securities"]
    monkeypatch.setattr(schema, "STORE", tmp_path)
    header = list(table.header)
    header[2] = "basis"                       # was "exposure"
    table.path.write_text(",".join(header) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema expects"):
        schema.load("securities")


# =====================================================================================
# THE BOUNDARY
# =====================================================================================

def test_the_schema_imports_nothing_third_party(repo_root, imports_of):
    """record/rules.py reads the store and the build reads record/rules.py, so anything
    imported here becomes a dependency of the REPORT BUILD. Same rule that keeps feeds/ig.py
    out: a rebuild must not be able to fail over something it does not need. pandas belongs to
    the engine, not to this path.
    """
    assert imports_of(SRC / "record/schema.py") <= {"__future__", "csv", "datetime",
                                                  "os", "pathlib", "threading", "typing"}


def test_the_build_never_imports_the_schema_directly(build_imports):
    """The build reads facts through record/rules.py and only through it. That is what
    keeps 'a trade goes in one file' true — and what makes the record the single place
    the store is assembled."""
    assert "record.schema" not in build_imports


# =====================================================================================
# THE REASONING TABLE — a fact, so it lives in the store and not in a renderer.
# =====================================================================================

def test_the_reasoning_is_never_a_literal_inside_a_renderer(repo_root):
    """THE REASONING IS A FACT, so it lives in `store/reasoning.csv`, where the bench writes it,
    never as a literal in a renderer. Checked on the syntax tree.
    """
    import ast
    for path in [*(SRC / "desk").rglob("*.py"), *(SRC / "report").rglob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Assign) and "REASONING" in [
                    t.id for t in node.targets if isinstance(t, ast.Name)]:
                assert not isinstance(node.value, (ast.Dict, ast.DictComp)), (
                    f"{path.relative_to(repo_root)} defines REASONING as a literal. The reasoning "
                    f"is a FACT and belongs in store/reasoning.csv, where the bench can write it.")


def test_there_is_one_reasoning_and_both_pages_read_it(repo_root):
    """Holdings and Round Trips show the same text. One object, reached one way: `D.REASONING`,
    joined by the engine (`Book.with_reasoning()`) and read by both pages through it. No page may
    hold the name, which would bind the dict at import and go stale at the next
    `rules.reload_store()`."""
    import ast
    from portfusion.record import rules as D
    assert set(D.REASONING) == {r.ticker for r in D.reasoning}
    holders = []
    for f in (SRC / "desk" / "panels").glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Name) and node.id == "REASONING":
                holders.append(f"{f.name}:{node.lineno}")
    assert not holders, f"these hold REASONING rather than asking the engine: {holders}"
    for page in ("holdings.py", "round_trips.py"):
        assert "with_reasoning" in (SRC / "desk" / "panels" / page).read_text(), page


@needs("buys", "reasoning")
def test_the_reasoning_round_trips_through_the_loader():
    """It is a store table like any other: the loader is the only door in, and a blank column
    reads back as None rather than as an empty string — a position still open has no
    why_exited, and that is a legitimate blank, not a gap."""
    from portfusion.record import rules as D
    rows = [D.Reasoning(*r) for r in schema.load("reasoning")]
    assert rows, "store/reasoning.csv is empty"
    blank = next((r for r in rows if r.why_exited is None and r.why_entered), None)
    assert blank is not None, \
        "no row holds a why_entered with a blank why_exited — the premise is gone"
    assert blank.why_exited is None, "a blank why_exited must read back as None"
    assert blank.why_entered.strip(), "the entered side of that row must survive the trip"
    assert all(isinstance(r.date, __import__("datetime").date) for r in rows), \
        "a why's date must load as a date, so the desk can place it within a position's life"


# =====================================================================================
# A SALE'S BROKER REFERENCE — forward-only.
# =====================================================================================

def test_a_sale_can_carry_its_own_broker_reference():
    """A SALE CARRIES `broker_ref` AS A BUY DOES.

    `closes` keeps the sell-to-buy linkage an IG close needs — the closing deal is this row's
    reference, the opening deal it closes is a relationship between two rows.
    """
    fields = {f.name: f for f in schema.TABLES["sales"].fields}
    assert "broker_ref" in fields, "a sale has nowhere to record its reference"
    assert fields["broker_ref"].null, (
        "sales.broker_ref is required, so a sale read off a statement, which has no deal "
        "reference of its own, fails to load")


def test_a_sales_deal_reference_is_in_its_column_never_its_note():
    """The closing deal is `broker_ref`'s, and the feed matches a close by it. A deal id in a
    note is the same fact in two places."""
    from portfusion.record import rules as D
    in_notes = [e.sale_id for e in D.sales if "DIAAAA" in str(e.note or "")]
    assert not in_notes, f"these sales name a deal in their note: {in_notes}"


def test_a_sale_s_reference_reaches_the_trades_cell():
    """Each sell row carries its own sale's `broker_ref`."""
    from portfusion import engine
    from portfusion.record import rules as D
    ledger = engine.Book().ledger
    sells = ledger[ledger["direction"] == "Sell"]
    assert len(sells) == len(D.sales)
    assert "broker_ref" in sells.columns
    # WIRED, not absent: each sell carries its own exit's reference, and is blank where that is.
    got = {i: r if isinstance(r, str) else None
           for i, r in zip(sells["event_id"], sells["broker_ref"])}
    assert got == {e.sale_id: e.broker_ref for e in D.sales}, \
        "a sell row's broker_ref is not its exit's"


def _wrong_leg_cases():
    """The four wrong-leg shapes, built from the LOADED book's own rows so each book is
    poisoned with its own names: another ticker's leg, a leg already closed, a spread bet
    naming none, and a share sale naming one."""
    from portfusion.record import schema
    th = schema.TABLES["buys"].header
    eh = schema.TABLES["sales"].header
    sh = schema.TABLES["securities"].header
    synthetic = {r[sh.index("ticker")] for r in schema.load("securities")
                 if r[sh.index("held_as")] == "spread bet"}
    trades = [dict(zip(th, r)) for r in schema.load("buys")]
    exits = [dict(zip(eh, r)) for r in schema.load("sales")]
    try:
        sb_sale = next(e for e in exits if e["ticker"] in synthetic and e["closes"])
        share_sale = next(e for e in exits if e["ticker"] not in synthetic)
        other_leg = next(t for t in sorted(trades,
                                           key=lambda t: t["account"] != sb_sale["account"])
                         if t["ticker"] in synthetic and t["ticker"] != sb_sale["ticker"])
        closed_other = next(e["closes"] for e in exits
                            if e["closes"] and e["sale_id"] != sb_sale["sale_id"])
        leg_any = next(t["trade_id"] for t in trades if t["ticker"] in synthetic)
    except StopIteration:         # a book without the sales to poison: the test skips, empty
        return []
    return [
        (sb_sale["sale_id"], other_leg["trade_id"],
         f"a {other_leg['account']} {other_leg['ticker']} leg, but sells "
         f"{sb_sale['account']} {sb_sale['ticker']}"),
        (sb_sale["sale_id"], closed_other, f"{closed_other} is closed by more than one sale"),
        (sb_sale["sale_id"], "",
         f"{sb_sale['sale_id']} sells the spread bet {sb_sale['ticker']} and names no leg"),
        (share_sale["sale_id"], leg_any,
         f"{share_sale['sale_id']} sells the share {share_sale['ticker']} and names the leg "
         f"{leg_any}"),
    ]


@pytest.mark.parametrize("eid, closes, says", _wrong_leg_cases())
def test_a_sale_naming_the_wrong_leg_is_refused_on_load(store_copy, eid, closes, says):
    """`closes` releases THAT leg's cost, so a wrong one moves a realised gain and still loads:
    another position's leg, a leg already closed, a spread bet naming none, or a share sale
    naming one — a pool has no legs, and a share releases its average (`engine.share_pools()`).
    Each is refused when the record loads, on every route in, the bench's included."""
    import csv
    from portfusion.record import rules
    path = store_copy / "sales.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    next(r for r in rows if r["sale_id"] == eid)["closes"] = closes
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(ValueError) as e:
        rules.reload_store()
    assert says in str(e.value), str(e.value)


# =====================================================================================
# THE STORE JOINS UP
#
# A name that joins to nothing drops its rows out of every per-account figure while every
# TOTAL still adds up. Wrong in a way that still builds cleanly, which is the shape of defect
# this suite exists for. The bench's closed vocabularies cover the bench alone; a hand-edited
# CSV is caught only here.
# =====================================================================================

def test_every_account_reference_is_in_the_register():
    """The live store, as it stands. If this fails, a row has an account the register
    does not have — fix the row, or add the account to store/accounts.csv."""
    schema.check_references()


@needs("buys", "reasoning")
def test_the_reference_check_actually_catches_a_bad_name(tmp_path, monkeypatch):
    """A guard that cannot fire is worth nothing, and this one runs at import where a
    silent pass would be invisible."""
    import shutil
    store = tmp_path / "store"
    shutil.copytree(schema.STORE, store)
    bad = store / "income.csv"
    text = bad.read_text()
    # Any register account the income table names, mistyped by one character.
    accounts = [r[0] for r in schema.load("accounts")]
    good = next(a for a in accounts if a in text)
    bad_name = good[:-1] + good[-1].swapcase()
    bad.write_text(text.replace(good, bad_name, 1))

    monkeypatch.setattr(schema, "STORE", store)
    for t in schema.TABLES.values():
        monkeypatch.setattr(type(t), "path", property(
            lambda self, _s=store: _s / f"{self.name}.csv"), raising=False)

    with pytest.raises(ValueError) as e:
        schema.check_references()
    assert bad_name in str(e.value)
    assert "is not in accounts.csv" in str(e.value)
    assert good in str(e.value), "it must list what the register does hold"


def test_a_closed_vocabulary_refuses_a_value_outside_it():
    """Field.enum, the other half. Rows are proposed by column name and edited by hand, so a
    mistyped value would reach every total that filters on it with only review in its way. Each
    closed list is declared to the loader, which refuses anything outside it."""
    f = schema.Field("quality", "str", enum=("sourced", "derived", "reconstructed"))
    assert schema._parse(f, "sourced", "t", 2) == "sourced"
    with pytest.raises(ValueError) as e:
        schema._parse(f, "Sourced", "t", 2)
    assert "CLOSED" in str(e.value) and "sourced" in str(e.value)


def test_a_required_string_refuses_a_blank_at_the_loader():
    """`null` CANNOT SAY THIS, which is why the flag exists.

    A blank `str` column returns "" whatever `null` holds, and deliberately — `income.note` is
    empty on most rows and that is a real value. So a string that MUST be filled says so with
    `required`. A test runs when someone runs it; the loader runs on every import, whatever route
    the row arrived by.
    """
    import pytest
    from portfusion.record import schema
    plain = schema.Field("note", "str")
    assert schema._parse(plain, "", "buys", 1) == "", \
        "an ordinary string column stopped accepting a blank"
    needed = schema.Field("reference", "str", required=True)
    with pytest.raises(ValueError) as e:
        schema._parse(needed, "", "cash-readings", 1)
    assert "may not be" in str(e.value)


def test_every_line_has_a_place_in_each_split():
    """A SPLIT BY CURRENCY, REGION OR SECTOR GROUPS THE LINES BY THAT VALUE, and a blank one drops
    out of it: the line stays in the holdings and leaves the bars, on the report's Section 3 and
    the Dashboard alike. The loader refuses the blank instead."""
    from portfusion.record import schema
    for table, names in (("companies", ("sector", "region")), ("securities", ("currency",))):
        fields = {f.name: f for f in schema.TABLES[table].fields}
        for name in names:
            assert fields[name].required, f"{table}.{name} would let a line leave the splits"


def test_the_two_provenance_pairs_are_required_in_the_schema():
    """The pair that says what a reading rests on, on both tables that carry one.

    `test_record.py` asserts the same thing on the loaded rows and keeps doing so — it also
    checks the class EXISTS, which the schema cannot: EVIDENCE_CLASSES lives in record/rules.py and
    record/schema.py imports nothing. This half is the one a hand edit meets first.
    """
    from portfusion.record import schema
    for table in ("account-readings", "cash-readings"):
        fields = {f.name: f for f in schema.TABLES[table].fields}
        for name in ("evidence", "reference"):
            assert fields[name].required, \
                f"{table}.{name} no longer says a blank is not a value"
