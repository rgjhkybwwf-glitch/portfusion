"""
THE STORE — the CSV files, and the schema that validates them on load.

EVERY TABLE HAS FLIPPED: record/rules.py loads the CSV, and the literals it once held are gone.
So `schema.load("companies") == D.COMPANIES` is TRIVIALLY TRUE — they are the same object —
and a test that kept asserting it would look like a check and prove nothing, the most
expensive kind of test there is.

What guards a table instead:

  * the SCHEMA MECHANISM, round-tripped through a temp file, on data with every awkward
    type in it — proving the reader and writer are inverses without needing the literals
  * the CONTENT INVARIANTS below — uniqueness, the join between the two tables, and the
    controlled vocabularies. These do not need updating when a company is added, which
    is what makes them worth having.
  * and, outside this file, the two witnesses that actually matter: every page renders
    as it did, and tests/test_engine_ties.py still ties.

`tests/test_record.py` already covers trades -> identity (`test_every_traded_ticker_has_
an_identity_row`), and is not repeated here.
"""
import datetime as _dt

import pytest

from portfusion.record import schema
from harness import SRC, needs


# WHERE EACH TABLE HAS GOT TO. This is the migration's state, written down where the
# tests can act on it, and it is the difference between a check and a tautology.
FLIPPED = {"companies", "securities", "accounts", "capital-movements", "realisations",
           "buys", "sales", "income", "quarter-nav", "fx",
           "current-prices", "baseline-reconstruction",
           "quarter-snapshots", "account-readings", "reasoning",
           # Cash has its own table rather than account-statements.csv's `cash` column: that
           # column means cash AT THAT STATEMENT'S DATE, and accounts.at() reads those rows as
           # the latest STATEMENT, so a cash-only row there would have fed None into the
           # quarter-NAV cross-check the first time it was the newest thing on file — at a close.
           "cash-readings",
           # Research notes are a table so a NEW note can be recorded at all. The research repo
           # stays the source of truth for a REF; this is the record of what the book cites, and
           # test_record.py ties the two together.
           "research-notes",
           # A closed quarter's results, written by the freeze from the engine and held against
           # it by test_engine_ties.py, so a closed quarter cannot move without a row saying why.
           "quarter-results",
           # The book's own settings: the dates and names the code may not type (8 Oct 2026).
           "settings",
           # The IG contracts a spread-bet leg can be on, with their epics (8 Oct 2026).
           "contracts",
           # The journal is the one table here that is ABOUT the record rather than part of it:
           # record time, one row per WRITE. record/rules.py does not load it — nothing in the
           # BUILD may depend on when a row was entered, only on what it says. Its own guards
           # are in test_journal.py.
           "journal"}
EMITTED = {}          # written and verified, record still holds the literals — none right now

def test_every_registered_table_is_accounted_for():
    """A table in the schema that no test knows about is an unguarded table."""
    assert set(schema.TABLES) == FLIPPED | set(EMITTED)


def test_the_store_reproduces_the_record():
    """STEP 1: THE TRANSCRIPTION IS FAITHFUL, cell for cell and type for type.

    Runs over EMITTED — tables whose CSV is written but whose literals are still the
    source. Tuple equality is deliberately strict: it fails on 4375 becoming 4375.0, on
    a date becoming a string, and on None becoming "" — the three ways a CSV round trip
    goes quietly wrong.

    When a table flips it moves to FLIPPED and drops out of here, because afterwards
    both sides are the same object and the comparison proves nothing.

    A LOOP AND NOT A PARAMETRIZE, on purpose: an empty parametrize SKIPS, and a test
    that reports "skipped" every run between emits is furniture. This one passes
    vacuously and starts working the moment a table is emitted.
    """
    for name in sorted(EMITTED):
        loaded = schema.load(name)
        expected = [tuple(r) for r in EMITTED[name]()]
        assert len(loaded) == len(expected), \
            f"{name}: store has {len(loaded)} rows, the record has {len(expected)}"
        for i, (got, want) in enumerate(zip(loaded, expected)):
            assert got == want, f"{name} row {i + 2} (file line): {got!r} != {want!r}"
            # TYPE, NOT JUST VALUE. `1 == 1.0` is True and `True == 1` is True, so
            # equality alone would pass while an int quietly became a float. Two columns
            # in trades genuinely mix int and float, which is what makes this necessary
            # rather than paranoid.
            for col, (a, b) in enumerate(zip(got, want)):
                assert type(a) is type(b), (
                    f"{name} row {i + 2}, column {schema.TABLES[name].fields[col].name!r}: "
                    f"store gives {type(a).__name__}, the record has {type(b).__name__}")


@pytest.mark.parametrize("name", sorted(schema.TABLES))
def test_the_file_header_matches_the_schema(name):
    """A column added to the CSV but not to the schema — or renamed in one and not the
    other — must fail at the door rather than be read positionally."""
    table = schema.TABLES[name]
    with table.path.open(encoding="utf-8") as fh:
        assert fh.readline().rstrip("\n").split(",") == table.header


#: Q2 (decided 9 Oct 2026): "loads" runs on every book; "not empty" wherever the engine
#: requires rows — which is every table but these. research-notes is the register of another
#: repository's notes, and a book that has written none legitimately has none; its emptiness
#: here is this book's own check, below.
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
    """THE JOIN IS BY FULL LEGAL NAME, not by ticker — which is the one thing the
    removed header comment said that no column carries. A security whose company does
    not appear in companies.csv silently loses its sector and region.
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

    This is what replaces comparing against the literals. It proves the mechanism
    without needing a table that has not flipped yet.
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


def test_the_number_kind_preserves_int_against_float():
    """TWO COLUMNS IN THIS RECORD GENUINELY MIX THEM — a spread-bet stake is 1 or 0.25,
    a limit level is 11300 or 8922.1. Declaring them float would be a silent reshape no
    equality test could see, because 1 == 1.0. `number` mirrors what the text says."""
    assert _cell("number", "1") == 1 and isinstance(_cell("number", "1"), int)
    assert _cell("number", "1.0") == 1.0 and isinstance(_cell("number", "1.0"), float)
    assert _cell("number", "0.25") == 0.25
    assert schema._render(schema.Field("x", "number"), 1) == "1"
    assert schema._render(schema.Field("x", "number"), 1.0) == "1.0"


def test_a_date_comes_back_as_a_date():
    """Not as a string that happens to look like one — `realisations.opened` holds real
    date objects and the ledger compares against them."""
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
    imported here becomes a dependency of the REPORT BUILD. Same rule that keeps
    feeds/ig.py and engine.py out: a rebuild must not be able to fail over something it
    does not need. pandas belongs to the engine, not to this path.
    """
    assert imports_of(SRC / "record/schema.py") <= {"__future__", "csv", "datetime",
                                                  "os", "pathlib", "threading", "typing"}


def test_the_build_still_does_not_import_the_schema_directly(build_imports):
    """The build reads facts through record/rules.py and only through it. That is what
    keeps 'a trade goes in one file' true — and what makes the record the single place
    the store is assembled."""
    assert "record.schema" not in build_imports


# =====================================================================================
# THE REASONING TABLE — a fact, so it lives in the store and not in a renderer.
# =====================================================================================

def test_the_reasoning_is_no_longer_a_literal_inside_a_renderer(repo_root):
    """THE WHOLE POINT OF THE MOVE, checked on the syntax tree rather than on prose.

    `REASONING` was once a dict literal inside a renderer — a FACT living in code, where a fact
    belongs in its CSV, and which the bench could not write to. It is
    `store/reasoning.csv`. If this fails, someone has put the facts back in a renderer.
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
    """Holdings and Round Trips show the same text, and a second copy is how HALV SB's thesis
    nearly vanished — OPEN_THESIS and TRADE_RATIONALE were two dicts holding one answer. One
    object, reached one way: `D.REASONING`, joined by the engine (`Book.with_reasoning()`) and
    read by both pages through it. No page may hold the name, which would bind the dict at
    import and go stale at the next `rules.reload_store()`."""
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
    """THE ASYMMETRY THAT WAS THERE FROM THE BEGINNING. A buy has carried `broker_ref` since
    the first row; a sale had nowhere to put one, so every sale's reference lived in prose and
    the Trades "Broker ref" cell was blank for all 32 of them.

    Both sides now have the same column. What has NOT changed is the note, which keeps the
    sell-to-buy linkage an IG close needs — the closing deal is this row's reference, the
    opening deal it closes is a relationship between two rows.
    """
    fields = {f.name: f for f in schema.TABLES["sales"].fields}
    assert "broker_ref" in fields, "a sale has nowhere to record its reference again"
    assert fields["broker_ref"].null, (
        "exits.broker_ref must be nullable — a sale read off a statement has no deal "
        "reference of its own, and a required column would make every one fail to load")


def test_a_sales_deal_reference_is_in_its_column_never_its_note():
    """The closing deal is `broker_ref`'s, and the feed matches a close by it. A deal id in a
    note is the same fact in two places, and the feed no longer reads notes."""
    from portfusion.record import rules as D
    in_notes = [e.sale_id for e in D.sales if "DIAAAA" in str(e.note or "")]
    assert not in_notes, f"these sales name a deal in their note: {in_notes}"


def test_a_sale_s_reference_reaches_the_trades_cell():
    """engine.py hard-coded `"broker_ref": None` for every exit, so the column could not have
    been rendered even once it existed. It reads the row now."""
    from portfusion import engine
    from portfusion.record import rules as D
    ledger = engine.Book().ledger
    sells = ledger[ledger["direction"] == "Sell"]
    assert len(sells) == len(D.sales)
    assert "broker_ref" in sells.columns
    # WIRED, not absent: each sell carries its own exit's reference, and is blank where that is.
    # That the historic ones ARE blank is test_no_historic_sale_was_backdated's to hold.
    got = {i: r if isinstance(r, str) else None
           for i, r in zip(sells["event_id"], sells["broker_ref"])}
    assert got == {e.sale_id: e.broker_ref for e in D.sales}, \
        "a sell row's broker_ref is not its exit's"


def _wrong_leg_cases():
    """The four wrong-leg shapes, built from the LOADED book's own rows so each book is
    poisoned with its own names: another ticker's leg, a leg already closed, a spread bet
    naming none, and a share sale naming one. The incident rows were a spread-bet close and a
    share sale."""
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
# THE STORE JOINS UP  (the owner)
#
# The schema once enforced TYPES and nothing else, so "Voss ii lSA" — a lowercase L for the
# I — loaded cleanly, joined to nothing, and dropped its rows out of every per-account
# figure while every TOTAL still added up. Wrong in a way that still builds cleanly, which
# is the shape of defect this suite exists for.
#
# The bench's closed vocabularies caught it on that route. A hand-edited CSV was not
# covered, and hand-editing is still how most of this record is corrected.
# =====================================================================================

def test_every_account_reference_is_in_the_register():
    """The live store, as it stands. If this fails, a row has an account the register
    does not have — fix the row, or add the account to store/accounts.csv."""
    schema.check_references()


@needs("buys", "reasoning")
def test_the_reference_check_actually_catches_a_bad_name(tmp_path, monkeypatch):
    """A guard that cannot fire is worth nothing, and this one runs at import where a
    silent pass would be invisible. The mistyped name is the real one from the defect."""
    import shutil
    store = tmp_path / "store"
    shutil.copytree(schema.STORE, store)
    bad = store / "income.csv"
    text = bad.read_text()
    # Any register account the income table names, mistyped by one character — the defect
    # itself was "Voss ii ISA" entered as "Voss ii lSA".
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
    empty on most rows and that is a real value. So a string that MUST be filled had no way to
    say so, and two tables relied on `test_record.py` to catch a blank instead. A test runs when
    someone runs it; the loader runs on every import, whatever route the row arrived by.
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
    the Dashboard alike (14 Oct 2026). The loader refuses the blank instead."""
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
