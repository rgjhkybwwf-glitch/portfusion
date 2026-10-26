"""THE BENCH — an event, from evidence to an approved row, and the rules at its door."""
from __future__ import annotations

import json
import pytest
from portfusion.record import rules as _rules
from portfusion.desk import app
from desk_support import (GOOD_CLASS, GOOD_DOCUMENT, GOOD_TRADE, GOOD_EVIDENCE, SHARES_ACCOUNT,
                          SPREAD_BET_ACCOUNT, SYNTHETIC_TICKER, _ready)


# =====================================================================================
# THE BENCH. An event, from evidence to an approved row.
#
# The gates are the whole point, so they are tested one at a time and from BOTH sides:
# that each refuses what it should, and that it lets the legitimate case through. A gate
# only tested on the refusing side is how you end up blocking real work.
# =====================================================================================
from portfusion.desk.intake import bench as _bench                                    # noqa: E402
from portfusion.desk.panels import bench as bench_panel
from harness import SRC, needs, free_id, desk_script

#: The ids a test's own sale takes: the book's next free ones, never typed (a book that has reached
#: E-099 holds one).
_EID, _EID_NEXT = free_id("sales"), free_id("sales", 1)


GOOD_INCOME = {
    "date": "2026-09-01", "account": SHARES_ACCOUNT, "category": "Cash interest",
    "detail": "Gross interest to 01/09/26", "amount": "1.23", "source": "ii statement",
    "note": "",
}


@needs("accounts", "buys")
def test_a_committed_item_lands_in_the_store_and_is_archived(item, store_copy, tmp_path,
                                                             monkeypatch):
    """END TO END. The row is in the CSV, it reads back through the loader, and the item has
    left the bench for _archive/bench/ in one operation."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    was = len(schema.load("buys"))

    result = _commit.commit(_bench.save(_ready(item))["id"])

    assert result["written"] == {"buys": 1}
    rows = schema.load("buys")
    assert len(rows) == was + 1
    assert rows[-1][0] == GOOD_TRADE["trade_id"], "the committed row is not the last row of the table"

    assert not list((_bench.BENCH_DIR).glob("*.json")), "the item is still on the bench"
    archived = json.loads((tmp_path / "archive" / f"{item['id']}.json").read_text())
    assert archived["state"] == "archived"
    assert archived["written_at"]


@needs("accounts", "buys")
def test_the_why_lands_in_the_reasoning_table(item, store_copy, tmp_path, monkeypatch):
    """The owner types the thesis once, at the document, and it reaches the table Holdings and
    Round Trips read — instead of being archived into a bench JSON nobody renders.

    KEYED BY TICKER, which is how both tabs read it."""
    import csv
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    _ready(item)
    _bench.save(item)
    out = _commit.commit(item["id"])

    assert out["reasoning"] == [GOOD_TRADE["ticker"]]
    # THIS COMMIT'S ROW, found by its text — the loaded book may already hold reasoning
    # for the derived ticker, and those rows are not this test's business.
    rows = [r for r in csv.DictReader(schema.TABLES["reasoning"].path.open(encoding="utf-8"))
            if "services margin story" in r["why_entered"]]
    assert len(rows) == 1 and rows[0]["ticker"] == GOOD_TRADE["ticker"]
    assert rows[0]["why_exited"] == "", "an open position has no exit reason yet"
    assert rows[0]["date"] == item["rows"][0]["values"]["date"], \
        "the why is filed under the date of the trade it explains"
    schema.load("reasoning")            # and it still loads through the ordinary door


@needs("accounts", "buys")
def test_a_second_why_is_added_beside_the_first(item, store_copy, tmp_path, monkeypatch):
    """A WHY IS APPENDED, NEVER REPLACED. The thesis a position was opened on must still be there
    when the position is trimmed: replaced, it would survive only in git, and the desk would show
    the latest reason as though it were the only one. Each why is its own row, dated by the event
    it explains, so the ticker appears twice and neither row is touched by the other.
    """
    import csv
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")

    _ready(item)
    _bench.save(item)
    _commit.commit(item["id"])

    second = _bench.new_item(title="the exit")
    # ITS OWN REFERENCE. A second event is a second document, and reusing the first one's
    # reference is precisely what the "already in the record" gate exists to stop.
    second["evidence"] = dict(GOOD_EVIDENCE, reference="TESTREF2")
    second["evidence_class"] = item["evidence_class"]
    (tmp_path / "_inbox" / "Contract_Note_TESTREF2.pdf").write_bytes(b"%PDF-1.4")
    second["document"] = {"name": "Contract_Note_TESTREF2.pdf"}
    second["why"] = {"why_entered": "", "why_exited": "Booked to release cash."}
    second["rows"] = [{"table": "sales", "values": dict(
        sale_id=_EID, date="2026-09-01", account=GOOD_TRADE["account"],
        ticker=GOOD_TRADE["ticker"], qty="10", traded_price="1.00", cur="GBP", proceeds="10.00",
        source="ii contract note 01 Sep 2026", broker_ref="", realisation_id="R-TESTWHY", closes="",
        note="n")}]
    _bench.save(second)
    _commit.commit(second["id"])

    # THE TEST'S OWN TWO ROWS, found by their texts — the loaded book may already hold
    # reasoning for this ticker, and those rows are not this test's business.
    rows = list(csv.DictReader(schema.TABLES["reasoning"].path.open(encoding="utf-8")))
    ours = [r for r in rows if r["ticker"] == GOOD_TRADE["ticker"]]
    entered = [r for r in ours if "services margin story" in r["why_entered"]]
    exited = [r for r in ours if r["why_exited"] == "Booked to release cash."]
    assert len(entered) == 1 and len(exited) == 1, \
        f"the second why did not get a row of its own: {ours}"
    assert not entered[0]["why_exited"], "the entry reason was changed by the exit"
    assert not exited[0]["why_entered"]
    assert exited[0]["date"] == "2026-09-01", "the exit's why is filed under the sale's date"


@needs("accounts", "buys")
def test_a_sale_the_book_cannot_load_is_refused_and_nothing_moves(item, store_copy, tmp_path,
                                                                  monkeypatch):
    """A sale can pass the schema and stop `Book()`: the schema judges a cell and cannot see that;
    the engine can. A sale in a parcel with nothing to release is refused in the engine's words,
    and every file, the record in memory and the bench item stay as they were."""
    from portfusion.record import rules, schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    item["evidence"] = dict(GOOD_EVIDENCE, reference="TESTREF3")
    item["why"] = {"why_entered": "", "why_exited": "Booked to release cash."}
    # A TICKER THE ACCOUNT DOES NOT HOLD, so the parcel has nothing to release.
    from portfusion import engine as _engine
    held_here = set(_engine.Book().holdings(account=GOOD_TRADE["account"],
                                          by="ticker")["ticker"])
    sh = schema.TABLES["securities"].header
    unheld = next(r[sh.index("ticker")] for r in schema.load("securities")
                  if r[sh.index("held_as")] == "shares"
                  and r[sh.index("ticker")] not in held_here)
    item["rows"] = [{"table": "sales", "values": dict(
        sale_id=_EID, date="2026-09-01", account=GOOD_TRADE["account"],
        ticker=unheld, qty="10", traded_price="1.00", cur="GBP", proceeds="10.00",
        source="ii contract note 01 Sep 2026", broker_ref="", realisation_id="R-NOTHING", closes="",
        note="n")}]
    _bench.save(item)
    before = {t: schema.TABLES[t].path.read_bytes() for t in ("sales", "journal", "reasoning")}

    with pytest.raises(_commit.Refused) as e:
        _commit.commit(item["id"])
    assert "would not load" in str(e.value) and "R-NOTHING" in str(e.value), str(e.value)
    for t, was in before.items():
        assert schema.TABLES[t].path.read_bytes() == was, f"{t}.csv moved on a refused commit"
    assert _EID not in rules.REALISATION_BY_EXIT, "the record in memory kept the refused sale"
    assert _bench.get(item["id"])["state"] != "archived", "a refused item left the bench"


def test_an_ig_close_naming_its_leg_is_written_and_the_leg_stops_being_held(
        item, store_copy, tmp_path, monkeypatch):
    """THE OTHER SIDE, and that sale's shape made whole: the parcel and the leg are on the row,
    where the bench writes them, so the close lands and the book still loads."""
    from portfusion import engine
    from portfusion.record import rules
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    item["evidence"] = dict(GOOD_EVIDENCE, reference="TESTREF4")
    item["evidence_class"] = "ig-api"
    item["why"] = {"why_entered": "", "why_exited": "Trimmed to manage margin."}
    leg = _open_sb_leg_with_parcel()
    item["rows"] = [{"table": "sales", "values": dict(
        sale_id=_EID, date="2026-09-21", account=leg["account"], ticker=leg["ticker"],
        qty="", stake=str(leg["stake"]), traded_price="80.0", cur="GBP", proceeds="2000.00",
        source="IG REST /history/activity 21 Sep 2026", broker_ref="DIAAAATESTCLOSE",
        realisation_id=leg["realisation_id"], closes=leg["trade_id"], note="n")}]
    _bench.save(item)

    written = _commit.commit(item["id"])["ids"][_EID]     # its place in date order
    assert rules.EXIT_LEG_MATCH[written] == leg["trade_id"]
    ledger = engine.Book().ledger
    assert not ledger.loc[ledger["event_id"] == leg["trade_id"], "open_leg"].iloc[0], \
        "the leg the sale closed is still held"


def test_a_close_filed_under_another_holdings_realisation_is_refused(
        item, store_copy, tmp_path, monkeypatch):
    """A close filed under another holding's realisation would sit inside that round trip, under its
    account: Round Trips groups by realisation. The bench names the clash before anything is
    written; the record refuses it on load, so a write that skipped the bench still could not
    stand."""
    from portfusion.record import rules, schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    leg = _open_sb_leg_with_parcel()
    other = next(e.realisation_id for e in rules.sales
                 if (e.acct, e.ticker) != (leg["account"], leg["ticker"]))
    item["evidence"] = dict(GOOD_EVIDENCE, reference="TESTREF5")
    item["evidence_class"] = "ig-api"
    item["why"] = {"why_entered": "", "why_exited": "Trimmed to manage margin."}
    item["rows"] = [{"table": "sales", "values": dict(
        sale_id=_EID, date="2026-09-21", account=leg["account"], ticker=leg["ticker"],
        qty="", stake=str(leg["stake"]), traded_price="80.0", cur="GBP", proceeds="2000.00",
        source="IG REST /history/activity 21 Sep 2026", broker_ref="DIAAAATESTCLOSE",
        realisation_id=other, closes=leg["trade_id"], note="n")}]
    _bench.save(item)
    rows = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not rows["ok"] and f"realisation: {other} is" in rows["detail"], rows["detail"]

    path = schema.TABLES["sales"].path
    was = path.read_bytes()
    with pytest.raises(_commit.Refused):
        _commit.commit(item["id"])
    assert path.read_bytes() == was, "sales.csv moved on a refused commit"

    eol = b"\r\n" if b"\r\n" in was else b"\n"
    path.write_bytes(was + _bench.paste_block(item)[0]["line"].encode() + eol)
    with pytest.raises(ValueError, match=f"{other} spans two holdings"):
        rules.reload_store()


def test_a_realisation_in_another_form_is_refused(item, store_copy, tmp_path, monkeypatch):
    """A REALISATION ID OUTSIDE `rules.REALISATION_FORM` (one ending "=2") is refused by the bench
    before writing, and by the record on load."""
    from portfusion.record import rules, schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    leg = _open_sb_leg_with_parcel()
    typo = leg["realisation_id"] + "=2"
    assert not rules.REALISATION_FORM.fullmatch(typo)
    item["evidence"] = dict(GOOD_EVIDENCE, reference="TESTREF6")
    item["evidence_class"] = "ig-api"
    item["why"] = {"why_entered": "", "why_exited": "Trimmed to manage margin."}
    item["rows"] = [{"table": "sales", "values": dict(
        sale_id=_EID, date="2026-09-21", account=leg["account"], ticker=leg["ticker"],
        qty="", stake=str(leg["stake"]), traded_price="80.0", cur="GBP", proceeds="2000.00",
        source="IG REST /history/activity 21 Sep 2026", broker_ref="DIAAAATESTCLOSE",
        realisation_id=typo, closes=leg["trade_id"], note="n")}]
    _bench.save(item)
    rows = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not rows["ok"] and "not in the record's form" in rows["detail"], rows["detail"]

    path = schema.TABLES["sales"].path
    was = path.read_bytes()
    eol = b"\r\n" if b"\r\n" in was else b"\n"
    path.write_bytes(was + _bench.paste_block(item)[0]["line"].encode() + eol)
    with pytest.raises(ValueError, match="NOT NAMED IN THE RECORD'S FORM"):
        rules.reload_store()


def test_no_document_kind_no_approval_and_the_authority_is_the_kinds(item):
    """The kind is owed first; the authority is its own words, set on every save."""
    from portfusion.desk.intake import propose as P
    _ready(item)
    item["evidence_class"] = ""
    grade = next(g for g in _bench.gates(item) if g["name"] == "statement-grade")
    assert not grade["ok"] and "what kind of document" in grade["detail"], grade["detail"]

    item["evidence_class"] = "ii-contract-note"
    item["evidence"] = dict(GOOD_EVIDENCE, authority="typed by hand")
    P.refresh_derived(item)
    from portfusion.record import rules
    assert item["evidence"]["authority"] == rules.EVIDENCE_BY_KEY["ii-contract-note"].authority


def test_a_trade_whose_source_is_not_its_kinds_format_is_refused(item):
    """The one format, checked at entry: a typed line in another shape is named with the line
    its document's kind composes, so the fix is a copy rather than a guess."""
    _ready(item, source="Contract note TESTREF1")
    rows = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not rows["ok"], rows["detail"]
    assert "'ii contract note 01 Sep 2026'" in rows["detail"], rows["detail"]
    _ready(item)
    assert next(g for g in _bench.gates(item) if g["name"] == "rows")["ok"]


def test_the_authority_box_is_shown_and_not_typed(repo_root):
    """The record keeps no typed authority, so the box is read-only and carries the kind's."""
    js = desk_script()
    assert 'fixed ? " readonly" : ""' in js and 'const fixed = l.key === "authority"' in js


def test_the_bench_speaks_the_desks_words_not_the_stores(item, repo_root):
    """Every field is headed for the Bench tab in house/headings.py (the panel's FORM_COLUMNS, so
    test_every_desk_column_has_a_heading_for_its_tab holds each one), every table has its word, and
    a gate a why blocks reads the why's heading."""
    from portfusion.house.headings import COMMON
    js = _renderer_free(repo_root)
    field_fn = js[js.index("function field(spec"):js.index("function drawItem(d)")]
    assert "head(spec.name)" in field_fn and "sentence(spec.name)" not in field_fn
    assert "BENCH.table_labels" in js[js.index("function drawItem(d)"):]
    assert set(_bench.TABLE_LABELS) == set(_bench.TABLES + _bench.REGISTER)
    assert set(bench_panel.FORM_COLUMNS) == {
        f.name for t in _bench.TABLES + _bench.REGISTER for f in _rules.schema.TABLES[t].fields}
    labels = {g["name"]: g["label"] for g in _bench.gates(item)}
    assert labels["why_exited"] == COMMON["why_exited"] == "Why we exited"


def _renderer_free(repo_root):
    return desk_script()


def test_one_item_at_a_time_then_a_review_then_one_write_each(item, repo_root):
    """An item takes the page; a finished one offers the next still owed, or the review; the review
    writes ONE ITEM PER PRESS, so each event keeps its own approval; "work it" redraws the list,
    and an item gone from under it says so."""
    _bench.save(item)
    d = bench_panel.detail(item["id"])
    assert d["bench"] and {"id", "title", "ready"} <= set(d["bench"][0])
    js = desk_script()
    opener = js[js.index("async function openItem("):js.index("function benchFocus(")]
    assert "catch" in opener and "BENCH_GONE" in opener, "a gone item must say so"
    assert 'id="bench-list"' in js and "list.hidden = on" in js, "an item must take the page"
    nxt = js[js.index("function nextStep("):js.index("async function reviewItems(")]
    assert 'id="nextitem"' in nxt and 'id="reviewall"' in nxt and "d.approved" in nxt
    review = js[js.index("async function reviewItems("):js.index("Object.assign(RENDER_LATE",
                                                                  js.index("async function reviewItems("))]
    assert 'data-write="${esc(it.id)}"' in review and "/commit" in review
    assert "write all" not in js.lower(), "one press per item: nothing writes them all"
    assert 'id="commit"' not in js, "an item is written from the review, not from its own screen"
    sweep = desk_script("sweep.js")
    sweep = sweep[sweep.index("function wireIgEvents("):]
    assert 'await show("bench")' in sweep, "work it must redraw the list it adds to"


def _open_legs_by_contract():
    """{contract: [open leg rows]} for every IG contract still mapped to an epic, from the
    loaded book's own files."""
    from portfusion.record import schema
    th, eh = schema.TABLES["buys"].header, schema.TABLES["sales"].header
    closed = {r[eh.index("closes")] for r in schema.load("sales") if r[eh.index("closes")]}
    epics = {r[0]: r[1] for r in schema.load("contracts")}
    out = {}
    for r in schema.load("buys"):
        row = dict(zip(th, r))
        if row["contract"] and epics.get(row["contract"]) and row["trade_id"] not in closed:
            out.setdefault(row["contract"], []).append(row)
    return out


def _closing(item, legs, ref):
    """The item, carrying one IG close per leg, each filed under its own holding's parcel."""
    from portfusion import engine
    b = engine.Book()
    item["evidence_class"] = "ig-api"
    item["evidence"] = dict(GOOD_EVIDENCE, reference=ref)
    item["why"] = {"why_entered": "", "why_exited": "Closed to manage margin."}
    item["rows"] = [{"table": "sales", "values": dict(
        sale_id=f"E-9{n:02d}", date="2026-09-21", account=leg["account"], ticker=leg["ticker"],
        qty="", stake=str(leg["stake"]), traded_price="80.0", cur="GBP", proceeds="2000.00",
        source="IG REST /history/activity 21 Sep 2026", broker_ref=f"DIAAAATEST{n:02d}",
        realisation_id=b.parcel(leg["account"], leg["ticker"]), closes=leg["trade_id"], note="n")}
        for n, leg in enumerate(legs)]
    _bench.save(item)
    return item


@needs("accounts", "buys")
def test_a_retirement_the_marks_door_refuses_is_the_commits_refusal(
        item, store_copy, tmp_path, monkeypatch):
    """A RETIREMENT THE MARKS DOOR REFUSES REFUSES THE COMMIT, by the commit's own refusal, so the
    page is told why with a 409; the files are as they were."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit, marks
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    _, legs = next(iter(sorted(_open_legs_by_contract().items())))
    _closing(item, legs, "TESTREF8")
    before = schema.TABLES["sales"].path.read_bytes()

    def refuses(*a, **k):
        raise marks.Refused("the outgoing price could not be banked")
    monkeypatch.setattr(marks, "retire", refuses)
    with pytest.raises(_commit.Refused, match="could not be retired"):
        _commit.commit(item["id"])
    assert schema.TABLES["sales"].path.read_bytes() == before


@needs("accounts", "buys")
def test_a_sale_closing_a_contracts_last_leg_retires_it_in_the_same_write(
        item, store_copy, tmp_path, monkeypatch):
    """A contract with no open leg is a mark nothing holds, so the write that closes its last leg
    takes its price out and blanks its epic, through the marks door and inside the commit's
    envelope, banked first and journalled; the review says so before the press."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    from portfusion.history import prices as PH
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    contract, legs = next(iter(sorted(_open_legs_by_contract().items())))
    _closing(item, legs, "TESTREF7")
    assert bench_panel.detail(item["id"])["retires"] == [contract]
    line = {r[0]: r[3] for r in schema.load("contracts")}[contract]

    done = _commit.commit(item["id"])
    assert done["retired"] == [contract]
    assert contract not in {r[0] for r in schema.load("current-prices")}, "still priced"
    assert not {r[0]: r[1] for r in schema.load("contracts")}[contract], "still has its epic"
    assert {r[0]: r[3] for r in schema.load("contracts")}[contract] == line, \
        "the closed contract lost its line"
    assert any(r["mark_key"] == contract for r in PH.load()), "its last price was not banked"
    jh = schema.TABLES["journal"].header
    said = [dict(zip(jh, r)) for r in schema.load("journal") if r[jh.index("ref")] == item["id"]]
    assert {(j["op"], j["table"]) for j in said} >= {("remove", "current-prices"),
                                                       ("replace", "contracts")}, said


@needs("accounts", "buys")
def test_a_retirement_writes_crlf_tables_back_in_crlf(item, store_copy, tmp_path, monkeypatch):
    """The retirement writes current-prices.csv and contracts.csv back in the ending it found."""
    from portfusion.desk.doors import commit as _commit
    from desk_support import all_crlf, to_crlf
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    contract, legs = next(iter(sorted(_open_legs_by_contract().items())))
    _closing(item, legs, "TESTREF7")
    to_crlf("current-prices", "contracts")
    assert _commit.commit(item["id"])["retired"] == [contract]
    for table in ("current-prices", "contracts"):
        assert all_crlf(table), f"the retirement wrote {table}.csv back as LF"


def test_a_sale_leaving_another_leg_open_retires_nothing(item, store_copy, tmp_path,
                                                         monkeypatch):
    """The other half: a contract still holding a leg keeps its price and its epic."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    shared = [(c, legs) for c, legs in sorted(_open_legs_by_contract().items()) if len(legs) > 1]
    if not shared:
        pytest.skip("no IG contract in this book holds two open legs")
    contract, legs = shared[0]
    _closing(item, legs[:1], "TESTREF8")
    assert bench_panel.detail(item["id"])["retires"] == []
    assert _commit.commit(item["id"])["retired"] == []
    assert contract in {r[0] for r in schema.load("current-prices")}
    assert {r[0]: r[1] for r in schema.load("contracts")}[contract]


def _sterling_shares_held():
    """{ticker: {account: quantity}} for every sterling share line with a live price, from the
    loaded book, each account's quantity as it stands."""
    from portfusion import engine
    from portfusion.record import schema
    priced = {r[0] for r in schema.load("current-prices") if r[2] == "GBP"}
    b = engine.Book()
    out = {}
    for acct in b.account_order():
        h = b.holdings(account=acct, by="ticker")
        for r in h[h["held_as"].eq("shares")].itertuples():
            if r.ticker in priced and r.qty > 0:
                out.setdefault(r.ticker, {})[acct] = int(r.qty)
    return out


def _selling(item, ticker, held, ref):
    """The item, carrying one sale per account of all that account holds of `ticker`, each
    filed under its own holding's parcel: two new ones in one item are numbered apart, as the
    record would number the second once the first is on file."""
    from portfusion import engine
    b = engine.Book()
    parcels = []
    for acct in sorted(held):
        parcel, n = b.parcel(acct, ticker), 2
        while parcel in parcels:
            parcel, n = f"{b.parcel(acct, ticker)}-{n}", n + 1
        parcels.append(parcel)
    item["evidence"] = dict(GOOD_EVIDENCE, reference=ref)
    item["why"] = {"why_entered": "", "why_exited": "Sold to release cash."}
    item["rows"] = [{"table": "sales", "values": dict(
        sale_id=free_id("sales", n), date="2026-09-21", account=acct, ticker=ticker, qty=str(qty),
        stake="", traded_price="1.00", cur="GBP", rate="", proceeds=f"{qty:.2f}",
        source="ii contract note 21 Sep 2026", broker_ref="", realisation_id=parcel,
        closes="", note="n")}
        for n, ((acct, qty), parcel) in enumerate(zip(sorted(held.items()), parcels))]
    _bench.save(item)
    return item


@needs("accounts", "buys")
def test_a_sale_emptying_a_share_in_every_account_retires_its_price_in_the_same_write(
        item, store_copy, tmp_path, monkeypatch):
    """A share no account holds is a quote nothing reads, and a failed fetch of it counts against
    the prices' freshness: the write that leaves no account holding it banks the price and takes it
    out, as a contract's last close does; the review says so before the press."""
    from portfusion import engine
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    from portfusion.history import prices as PH
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    ticker, held = next(iter(sorted(_sterling_shares_held().items())))
    _selling(item, ticker, held, "TESTREF9")
    assert bench_panel.detail(item["id"])["retires"] == [ticker]

    done = _commit.commit(item["id"])
    assert done["retired"] == [ticker]
    assert ticker not in {r[0] for r in schema.load("current-prices")}, "still priced"
    assert any(r["mark_key"] == ticker for r in PH.load()), "its last price was not banked"
    jh = schema.TABLES["journal"].header
    said = [dict(zip(jh, r)) for r in schema.load("journal") if r[jh.index("ref")] == item["id"]]
    assert ("remove", "current-prices") in {(j["op"], j["table"]) for j in said}, said
    assert ("replace", "contracts") not in {(j["op"], j["table"]) for j in said}, \
        "a share has no epic to blank"
    assert engine.Book().priced_unheld() == []


@needs("accounts", "buys")
def test_a_share_still_held_in_another_account_keeps_its_price(
        item, store_copy, tmp_path, monkeypatch):
    """The other half: a price is per ticker, so one account selling out retires nothing while
    another still holds the line."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    shared = [(t, h) for t, h in sorted(_sterling_shares_held().items()) if len(h) > 1]
    if not shared:
        pytest.skip("no sterling share in this book is held in two accounts")
    ticker, held = shared[0]
    one = dict([sorted(held.items())[0]])
    _selling(item, ticker, one, "TESTREF10")
    assert bench_panel.detail(item["id"])["retires"] == []
    assert _commit.commit(item["id"])["retired"] == []
    assert ticker in {r[0] for r in schema.load("current-prices")}


def test_a_share_bought_back_in_the_same_item_is_not_retired():
    """THE ITEM'S OWN BUY HOLDS THE LINE: a sale of all of it beside a buy retires nothing."""
    from portfusion.desk.doors import commit
    held = next(iter(sorted(_sterling_shares_held().items())), None)
    if held is None:
        pytest.skip("no sterling share line with a live price")
    ticker, by_account = held
    sales = [{"table": "sales", "values": {"ticker": ticker, "qty": str(q)}}
             for q in by_account.values()]
    assert commit.retired_by(sales) == [ticker], "the premise: the sales empty it"
    buy = {"table": "buys", "values": {"ticker": ticker, "qty": "10"}}
    assert commit.retired_by(sales + [buy]) == []


def test_an_event_is_dated_on_the_bench_and_on_load():
    """The date is required in the schema, so the loader refuses a blank on every route and the
    Bench's form follows it."""
    from portfusion.record import schema
    for table in ("buys", "sales", "income", "capital-movements"):
        date = next(f for f in schema.TABLES[table].fields if f.name == "date")
        with pytest.raises(ValueError):
            schema._parse(date, "", table, 0)
        assert next(f for f in _bench.form_for(table) if f["name"] == "date")["required"]
        assert "date: required, and empty" in _bench.validate_row(table, {"date": ""})


def _held(account, ticker):
    from portfusion import engine
    return engine.Book().holdings(account=account, by="ticker").set_index("ticker").loc[ticker]


def _trimmed_pool():
    """(account, ticker, its exits' ids, its realisation): a pool already trimmed and still
    held — the loaded book's own PENR shape."""
    from portfusion import engine
    from portfusion.record import schema
    eh = schema.TABLES["sales"].header
    realisation = {r[eh.index("ticker")]: r[eh.index("realisation_id")]
                   for r in schema.load("sales")}
    b = engine.Book()
    for r in schema.load("sales"):
        t, a = r[eh.index("ticker")], r[eh.index("account")]
        if str(t).endswith(" SB") or t not in realisation:
            continue
        if t in set(b.holdings(account=a, by="ticker")["ticker"]):
            ids = [x[eh.index("sale_id")] for x in schema.load("sales")
                   if x[eh.index("ticker")] == t]
            return a, t, ids, realisation[t]
    pytest.skip("no trimmed pool is still held in this book")


def _untrimmed_holding(account):
    """A held share line with no realisation on file yet, held in `account` ALONE — a line
    another account also holds stays open at the ticker when one pool empties."""
    from portfusion import engine
    from portfusion.record import schema
    eh = schema.TABLES["sales"].header
    tripped = {r[eh.index("ticker")] for r in schema.load("sales")}
    b = engine.Book()
    elsewhere = set()
    hh = schema.TABLES["accounts"].header
    for a in (r[hh.index("account")] for r in schema.load("accounts")
              if r[hh.index("held_as")] == "shares" and r[hh.index("account")] != account):
        elsewhere |= set(b.holdings(account=a, by="ticker")["ticker"])
    h = b.holdings(account=account, by="ticker")
    return next(t for t in h["ticker"]
                if not str(t).endswith(" SB") and t not in tripped and t not in elsewhere)


def _open_sb_leg_with_parcel():
    """An OPEN spread-bet leg whose own ACCOUNT has sold the ticker since the leg was opened,
    with its quantity and that holding's parcel — the latest such sale's. The parcel is the
    holding's, not the ticker's: two accounts may bet on the same ticker."""
    from portfusion.record import schema
    th = schema.TABLES["buys"].header
    eh = schema.TABLES["sales"].header
    exits = schema.load("sales")
    closed = {r[eh.index("closes")] for r in exits if r[eh.index("closes")]}
    for r in schema.load("buys"):
        tid, t, acct = r[th.index("trade_id")], r[th.index("ticker")], r[th.index("account")]
        sales = sorted((str(e[eh.index("date")]), e[eh.index("realisation_id")]) for e in exits
                       if e[eh.index("account")] == acct and e[eh.index("ticker")] == t
                       and str(e[eh.index("date")]) >= str(r[th.index("date")]))
        if str(t).endswith(" SB") and tid not in closed and sales:
            return {"trade_id": tid, "ticker": t, "account": acct,
                    "stake": r[th.index("stake")], "realisation_id": sales[-1][1]}
    pytest.skip("no open spread-bet leg with a parcel on file in this book")


def _recorded_share_sale():
    """(row, reference) for a share sale really in the loaded book's sales.csv — the subject
    of the duplicate guards. The reference is the row's own broker_ref, or the document
    token its source line carries (a note's reference may sit in the source)."""
    from portfusion.record import rules as D, schema
    eh = schema.TABLES["sales"].header
    rows = [dict(zip(eh, r)) for r in schema.load("sales")
            if not str(r[eh.index("ticker")]).endswith(" SB")]
    assert rows, "no share sale on file — the premise is gone"
    def ref_of(r):
        return str(r["broker_ref"] or "") or str(D.archive_reference(r["source"]) or "")
    sale = next((r for r in rows if ref_of(r)), rows[0])
    return sale, ref_of(sale)


def _sell_shares(item, tmp_path, monkeypatch, ref, acct, ticker, qty, proceeds):
    """Commit one share sale through the bench, as a contract note gives it: one exits row, its
    parcel from `Book.parcel()`, no leg. Returns the store's other tables as they were, and every
    sale id as it now is (`{was: now}`): the new sale's under `_EID`, and those its date moved."""
    from portfusion import engine
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    item["evidence"] = dict(GOOD_EVIDENCE, reference=ref)
    item["why"] = {"why_entered": "", "why_exited": "Sold to fund a new position."}
    item["rows"] = [{"table": "sales", "values": dict(
        sale_id=_EID, date="2026-09-30", account=acct, ticker=ticker, qty=str(qty), traded_price="1.00",
        cur="GBP", proceeds=f"{proceeds:.2f}", source="ii contract note 30 Sep 2026", broker_ref=ref,
        realisation_id=engine.Book().parcel(acct, ticker), closes="", note="n")}]
    _bench.save(item)
    others = {t: schema.TABLES[t].path.read_bytes() for t in ("buys",)}
    out = _commit.commit(item["id"])
    return others, {**out["renumbered"], **out["ids"]}


def test_a_further_trim_of_a_pool_is_one_row_and_moves_no_earlier_sale(
        item, store_copy, tmp_path, monkeypatch):
    """A FURTHER TRIM IS ONE ROW: it releases the pool's average and nothing before it moves."""
    from portfusion import engine
    from portfusion.record import schema
    account, ticker, earlier_ids, parcel = _trimmed_pool()
    was = engine.Book()
    held = was.holdings(account=account, by="ticker").set_index("ticker").loc[ticker]
    earlier = {e: was.cost_released[e] for e in earlier_ids}
    qty = int(held["qty"] // 2)

    others, now_id = _sell_shares(item, tmp_path, monkeypatch, "TESTREF5", account, ticker,
                                  qty, 4990.00)

    now = engine.Book()
    sale = now_id[_EID]
    assert now.D.REALISATION_BY_EXIT[sale] == parcel, "the trim did not join its holding"
    assert now.cost_released[sale] == round(held["cost"] * qty / held["qty"], 2)
    assert {e: now.cost_released[now_id.get(e, e)] for e in earlier} == earlier, \
        "an earlier sale moved"
    after = now.holdings(account=account, by="ticker").set_index("ticker").loc[ticker]
    assert after["qty"] == held["qty"] - qty
    for t, b in others.items():
        assert schema.TABLES[t].path.read_bytes() == b, f"{t}.csv was written for a share sale"


@needs("accounts", "buys")
def test_a_full_exit_is_one_row_and_the_holding_is_gone(item, store_copy, tmp_path, monkeypatch):
    """No leg switched to Closed, no ticker listed, no realisations row: the pool empties and
    the round trip reads its cost, company and entry date from the events."""
    from portfusion import engine
    account = GOOD_TRADE["account"]
    ticker = _untrimmed_holding(account)
    was = engine.Book()
    held = was.holdings(account=account, by="ticker").set_index("ticker").loc[ticker]

    _others, now_id = _sell_shares(item, tmp_path, monkeypatch, "TESTREF6", account, ticker,
                                   int(held["qty"]), 6000.00)

    now = engine.Book()
    assert ticker not in set(now.holdings(account=account, by="ticker")["ticker"])
    rt = now.round_trips().set_index("realisation_id") \
            .loc[now.D.REALISATION_BY_EXIT[now_id[_EID]]]
    assert round(rt["cost"], 2) == round(held["cost"], 2)
    assert rt["company"] == held["company"] and rt["opened"] == held["opened"]
    assert rt["fully_closed"]


def test_a_sale_from_one_account_leaves_the_others_holdings_alone(
        item, store_copy, tmp_path, monkeypatch):
    """A line several accounts hold is one pool per account — a line can sit in three — so a sale from one releases that account's average and moves nobody else's
    shares or cost."""
    from portfusion import engine
    from portfusion.record import schema as _schema
    b0 = engine.Book()
    hh = _schema.TABLES["accounts"].header
    shares_accounts = [r[hh.index("account")] for r in _schema.load("accounts")
                       if r[hh.index("held_as")] == "shares"]
    holders = {}
    for a in shares_accounts:
        for t in b0.holdings(account=a, by="ticker")["ticker"]:
            holders.setdefault(t, []).append(a)
    shared = next(((t, accts) for t, accts in holders.items() if len(accts) > 1), None)
    if shared is None:
        pytest.skip("no line sits in two share accounts in this book")
    ticker, accounts = shared
    seller = accounts[-1]

    def pools(b):
        return {a: tuple(b.holdings(account=a, by="ticker").set_index("ticker")
                         .loc[ticker, ["qty", "cost"]].round(2))
                for a in accounts}
    was = pools(b0)
    qty = int(b0.holdings(account=seller, by="ticker").set_index("ticker")
              .loc[ticker, "qty"] // 2)

    _sell_shares(item, tmp_path, monkeypatch, "TESTREF7", seller, ticker, qty, 12500.00)

    now = pools(engine.Book())
    for a in accounts[:-1]:
        assert now[a] == was[a], f"{a}'s pool moved on {seller}'s sale"
    assert now[seller][0] == was[seller][0] - qty


def test_the_bench_fills_a_share_sales_parcel_from_the_book(item, monkeypatch):
    """`realisation` is the record's, never the document's: the parcel the holding already has,
    or a new one named for its ticker. A spread bet's too — its account's holding's, the answer
    the IG sweep gives."""
    from portfusion.desk import engine
    from portfusion.desk.intake import propose
    monkeypatch.setattr(engine, "_cache", {"key": None, "book": None})
    trimmed_acct, trimmed, _ids, trimmed_parcel = _trimmed_pool()
    fresh = _untrimmed_holding(GOOD_TRADE["account"])
    sb = _open_sb_leg_with_parcel()
    cases = ((trimmed_acct, trimmed), (GOOD_TRADE["account"], fresh),
             (sb["account"], sb["ticker"]))
    parcel = {t: propose._derived(item, "sales", a, ticker=t).get("realisation_id")
              for a, t in cases}
    # A fresh holding's parcel is NAMED FOR ITS TICKER — the convention restated here on
    # purpose, so a renamed proposer cannot vouch for itself.
    named = "R-" + fresh.split(".")[0].replace(" ", "")
    assert parcel == {trimmed: trimmed_parcel, fresh: named, sb["ticker"]: sb["realisation_id"]}


def test_a_refused_commit_leaves_no_thesis_behind(item, store_copy, tmp_path, monkeypatch):
    """THE WHY IS INSIDE THE SAME ENVELOPE as the rows. A commit that fails on the read-back
    must not leave a thesis for a trade that never landed — the book would then show a WHY WE
    ENTERED against a position it has no record of."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit, envelope
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    _ready(item, ticker="CRNT")
    _bench.save(item)

    before = schema.TABLES["reasoning"].path.read_bytes()
    real = envelope.rendered
    monkeypatch.setattr(envelope, "rendered", lambda t, v: real(t, v)[:-1])
    with pytest.raises(Exception):
        _commit.commit(item["id"])
    assert schema.TABLES["reasoning"].path.read_bytes() == before, \
        "a thesis survived a refused commit"


def test_commit_is_refused_until_every_gate_is_green(item, store_copy):
    """The stored state is never trusted — gates are re-run from scratch. An item marked
    approved by hand is still refused, and the store is not touched."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    item["rows"] = [{"table": "buys", "values": dict(GOOD_TRADE)}]
    item["state"] = "approved"                      # a lie, told deliberately
    _bench.save(item)
    before = (schema.TABLES["buys"].path).read_bytes()

    with pytest.raises(_commit.Refused) as e:
        _commit.commit(item["id"])
    assert "not approved" in str(e.value)
    assert (schema.TABLES["buys"].path).read_bytes() == before



def test_two_rows_of_one_item_under_one_id_are_refused(item):
    """AN ID ONCE: two rows of one item under one id fail the rows gate."""
    _ready(item)
    item["rows"].append({"table": "buys", "values": dict(GOOD_TRADE, broker_ref="TESTREF2")})
    rows = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not rows["ok"] and f"id {GOOD_TRADE['trade_id']} is row 1's too" in rows["detail"], rows


@needs("accounts", "buys")
def test_the_record_refuses_two_rows_under_one_id(store_copy):
    """THE SAME RULE, ON THE STORE: a hand edit that repeats an id stops the record loading, as
    any other malformed row does, rather than becoming two legs nothing can tell apart."""
    from portfusion.record import rules, schema
    path = schema.TABLES["sales"].path
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines + [lines[-1]]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ids must be distinct"):
        rules.reload_store()


@needs("accounts", "buys")
def test_committing_twice_is_refused(item, store_copy, tmp_path, monkeypatch):
    """An event happened once. The second write would be a duplicate the schema cannot see,
    because nothing in it says a trade id may not repeat across a re-run."""
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    _commit.commit(_bench.save(_ready(item))["id"])
    with pytest.raises(KeyError):
        _commit.commit(item["id"])        # gone from the bench entirely


def test_an_item_with_no_rows_is_refused(item, store_copy):
    from portfusion.desk.doors import commit as _commit
    item["evidence"] = dict(GOOD_EVIDENCE)
    item["why"] = {"why_entered": "x" * 20, "why_exited": ""}
    _bench.save(item)
    with pytest.raises(_commit.Refused) as e:
        _commit.commit(item["id"])
    assert "no rows" in str(e.value)


def test_a_failure_on_the_SECOND_table_rolls_the_FIRST_one_back(item, store_copy, monkeypatch):
    """THE CASE THE MACHINERY EXISTS FOR. A two-table item whose second table fails must leave
    the first one untouched — a half-written store is the worst outcome available here, because
    the book would look complete and be wrong.

    Forced by making the income row render one cell short, which the loader rejects on the
    read-back. Both files must come out byte-identical."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit, envelope
    item["evidence"] = dict(GOOD_EVIDENCE)
    item["why"] = {"why_entered": "Entered on the services margin story, which the hardware "
                                 "cycle masks.", "why_exited": ""}
    item["rows"] = [{"table": "buys", "values": dict(GOOD_TRADE)},
                    {"table": "income", "values": dict(GOOD_INCOME)}]
    _bench.save(item)

    real = envelope.rendered
    monkeypatch.setattr(envelope, "rendered",
                        lambda t, v: real(t, v)[:-1] if t == "income" else real(t, v))

    before = {t: schema.TABLES[t].path.read_bytes() for t in ("buys", "income")}
    with pytest.raises(Exception):
        _commit.commit(item["id"])
    for t, original in before.items():
        assert schema.TABLES[t].path.read_bytes() == original, \
            f"{t}.csv was left modified after a refused commit"


def test_the_desks_reload_re_reads_every_table_in_the_store():
    """A STORE THAT MOVED MUST REACH A READER, WHATEVER MOVED IT.

    record/rules.py reads its tables ONCE, at import, and engine.load_store() reads those attributes
    rather than the files. So for a long-lived process there are two copies of the record, and
    the one on the page is the stale one until something re-reads.

    THE RELOAD IS TOTAL. The desk reloads whenever the store's mtime moves, however it moved, so a
    `git pull` and a hand-edited trade arrive by the same route as a bench commit, and neither is
    a replace. Reloading the whole record costs milliseconds.

    THE ASSERTION IS BEHAVIOURAL, NOT AN AST SCAN. Reading a hand-written reloader for the
    `schema.load` calls it contains could only ever prove it named the right tables. This
    watches what reload_store() actually asks the loader for, so it holds whatever the
    implementation becomes.

    `journal` is the one table excluded, and deliberately: `rules.journal_rows()` is a function
    rather than a module-level load, so the BUILD can never depend on WHEN a row was entered.
    """
    import json
    import subprocess
    import sys

    from portfusion.record import schema

    # IN A SUBPROCESS, BECAUSE reload_store() REBINDS THE MODULE'S NAMES to a new build, and a
    # module that copied a value out at its own import goes on holding the old one. Reloading
    # here could leave another file's tests reading two records at once, which is a test
    # poisoning the suite rather than a defect in the code it is describing.
    probe = (
        "import json;"
        "from portfusion.record import schema, rules;"
        "asked = []; real = schema.load;"
        "schema.load = lambda ref, *a, **k: (asked.append(ref), real(ref, *a, **k))[1];"
        "rules.reload_store();"
        "print(json.dumps(asked))"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                         cwd=str(SRC))
    assert out.returncode == 0, f"the probe failed:\n{out.stderr}"
    asked = json.loads(out.stdout.strip().splitlines()[-1])

    expected = set(schema.TABLES) - {"journal"}
    missed = expected - set(asked)
    assert not missed, (
        f"rules.reload_store() did not re-read these tables: {sorted(missed)}. A desk holding "
        f"a stale copy of one of them serves a figure the store no longer holds, and the page "
        f"says nothing. Every table but `journal` is read at import and must be re-read here.")


def test_every_table_a_door_replaces_is_covered_by_the_reload():
    """THE DOORS' OWN HALF, still derived from the doors rather than from a list here.

    A door that REPLACES a row writes twice — the CSV, and the copy every long-lived process
    holds. A desk that misses the second serves a stale reading, and another door, or a second
    table under an existing one, must not be able to do that quietly.

    IT IS SUBSUMED BY THE TEST ABOVE and kept anyway, because the two say different things: that
    one says the reload is total, this one says the doors are known. If the reload is ever
    narrowed, this is the test that names which door lost its refresh.
    """
    from portfusion.record import schema
    from portfusion.desk.doors import marks, observations

    replaced = set(marks.KEYED_BY) | {observations.TABLE}
    unknown = replaced - set(schema.TABLES)
    assert not unknown, (
        f"a desk door replaces rows in a table the schema does not declare: {sorted(unknown)}")


def test_reading_the_desk_leaves_every_store_file_byte_identical():
    """THE RUNTIME HALF. The structural guards read source; none of them runs the desk. A write
    that arrived through a name none of those scans knows would pass every structural check.

    So: render every panel and take every read-only route, then compare every file in the
    store byte for byte. Nothing the desk does to SHOW you the book may change it.

    BY GLOB, NOT schema.TABLES. The histories and the account statements are read through
    their own doors and are not in it, so a write to any of them would pass unseen.
    """
    from portfusion.record import schema
    from portfusion.desk import panels, engine, actions
    from portfusion.desk.intake import research

    files = sorted(schema.STORE.glob("*.csv"))
    before = {f.name: f.read_bytes() for f in files}
    assert {t.path.name for t in schema.TABLES.values()} <= set(before), \
        "the glob missed a table the schema declares — it is looking in the wrong place"

    for module in panels.all_panels():
        module.data()
    engine.freshness()
    engine.book().findings()
    engine.palette()
    engine.tokens_css()
    actions.all_actions()
    actions.reaching_actions()
    actions.writing_actions()
    research.notes()
    research.by_ref()

    after = {f.name: f.read_bytes() for f in files}
    changed = sorted(n for n in before if before[n] != after[n])
    assert not changed, f"reading the desk modified {changed} — the desk shows, it does not write"


def test_health_says_when_the_code_was_loaded():
    """WHO IS ANSWERING ON THIS PORT, AND WHEN IT LOADED ITS CODE.

    `app.js` polls it to know when a replacement has finished starting, which is the case that
    reads as a crash if the page guesses instead of waiting.

    Whole seconds, so a caller can compare it with a file mtime without arithmetic.
    """
    import json
    body = json.loads(app.health().body)
    assert body["desk"] is True
    assert isinstance(body["started"], int)
    assert isinstance(body["pid"], int)


def test_nothing_on_the_bench_writes_to_the_store(repo_root):
    """THE CLAIM THAT MATTERS, for bench.py specifically. It works on a JSON note in
    _inbox/.bench/ and produces text to paste. THE WRITE LIVES IN desk/doors/commit.py, which is a
    separate module on purpose: this guard stays sharp.

    CHECKED ON THE SYNTAX TREE (`harness.file_calls`), not by grepping the source. Prose is not
    behaviour; the calls are. Every write, a removal among them, is of the item note, through
    `_path()`.
    """
    from harness import file_calls
    writes = file_calls(SRC / "desk" / "intake" / "bench.py")
    elsewhere = [(line, call, target) for line, call, target in writes
                 if not target.startswith("_path(")]
    assert not elsewhere, f"bench.py writes somewhere but its own item note: {elsewhere}"


def test_the_bench_writes_only_inside_its_own_directory(item, tmp_path, monkeypatch):
    """The behavioural half of the test above: exercise a full item and prove nothing outside
    _inbox/.bench/ was touched."""
    from portfusion.record import schema
    store = schema.STORE
    before = {p: p.stat().st_mtime for p in store.glob("*.csv")}
    _ready(item)
    _bench.save(item)
    _bench.paste_block(item)
    assert {p: p.stat().st_mtime for p in store.glob("*.csv")} == before, \
        "a store CSV was modified by working a bench item"


@needs("accounts", "buys")
def test_THE_SAME_SALE_CANNOT_BE_ENTERED_TWICE_UNNOTICED(item, store_copy):
    """A SALE ENTERED TWICE, pinned by name and by the real row.

    A note dropped again would write its sale a SECOND time under a fresh id, which the id check
    passes.

    TWO INDEPENDENT SIGNALS, because they fail separately: the DOCUMENT's reference is already
    in the book, and the EVENT's date/account/holding/size/money is already in the book.
    """
    from portfusion.record import schema as _schema
    sale, ref = _recorded_share_sale()
    assert ref, "no recorded sale carries a reference — the premise is gone"
    item["evidence"] = {"dated": str(sale["date"]), "authority": "ii contract note",
                        "reference": ref}
    item["rows"] = [{"table": "sales", "values": {
        "sale_id": _EID, "date": str(sale["date"]), "account": sale["account"],
        "ticker": sale["ticker"], "qty": str(sale["qty"]), "traded_price": str(sale["traded_price"]), "cur": "GBP",
        "proceeds": str(sale["proceeds"]),
        "source": f"ii contract note {ref}",
        "broker_ref": ref, "note": "n"}}]
    findings = _bench.already_in_the_record(item)

    assert any(f"{ref} already appears in sales.csv" in f for f in findings), findings
    # The archive signal fires only where the cited document is actually filed.
    if any(ref.lower() in n.lower() for n in _schema.filed_statements()):
        assert any("_archive/statements/" in f for f in findings), findings
    assert any(f"already in the record as {sale['sale_id']}" in f for f in findings), findings

    gate = next(g for g in _bench.gates(item) if g["name"] == "not already in the record")
    assert not gate["ok"], "the duplicate sale passed the gate"


@needs("accounts", "buys")
def test_a_duplicate_is_acknowledged_and_not_silently_overridden(item):
    """IT CANNOT BE A REFUSAL (`bench.already_in_the_record` says why), so it costs a
    deliberate acknowledgement — and acknowledging one finding must not pre-approve
    the next, or the gate would be spent the first time it fired."""
    sale, ref = _recorded_share_sale()
    _ready(item)
    item["evidence"] = {"dated": str(sale["date"]), "authority": "ii contract note",
                        "reference": ref}
    gate = next(g for g in _bench.gates(item) if g["name"] == "not already in the record")
    assert not gate["ok"] and gate["findings"]

    item["acknowledged"] = list(gate["findings"])
    assert next(g for g in _bench.gates(item)
                if g["name"] == "not already in the record")["ok"]

    # A NEW FINDING RAISES IT AGAIN. The acknowledgement is per finding, not a switch.
    item["rows"].append({"table": "sales", "values": {
        "sale_id": _EID_NEXT, "date": str(sale["date"]), "account": sale["account"],
        "ticker": sale["ticker"], "qty": str(sale["qty"]), "traded_price": str(sale["traded_price"]), "cur": "GBP",
        "proceeds": str(sale["proceeds"]), "source": "s", "broker_ref": "", "note": "n"}})
    assert not next(g for g in _bench.gates(item)
                    if g["name"] == "not already in the record")["ok"]


@needs("accounts", "buys")
def test_the_screen_shows_the_whys_already_on_file(item):
    """A new why is added beside the ones on file, so the screen shows them as the record so far,
    each with its date: the thesis an addition builds on, the reason a trim departs from. Written
    blind, a second why would repeat or contradict the first with nothing on screen to say so."""
    from portfusion.desk.panels import bench as panel
    from portfusion.record import schema as _schema
    rh = _schema.TABLES["reasoning"].header
    why = next(dict(zip(rh, r)) for r in _schema.load("reasoning") if r[rh.index("why_exited")])
    item["rows"] = [{"table": "sales", "values": {"ticker": why["ticker"]}}]
    _bench.save(item)
    existing = panel.detail(item["id"])["existing_why"]
    assert [r["date"] for r in existing[why["ticker"]]
            if r["why_exited"] == why["why_exited"]] == [str(why["date"])]

    js = desk_script()
    assert "existing_why" in js and ">on file<" in js, \
        "the screen no longer shows the whys already on file"


def test_an_item_is_not_approvable_until_every_gate_is_green(item):
    assert not _bench.approved(item)
    # THE GATES ARE A NAMED SET, the shape test_boundaries.py's WRITERS uses. A new one
    # joins by being written down here, on purpose — a gate that appears without a decision is a
    # gate nobody chose. "the reference retrieves it" is statement-grade checked at the door,
    # rather than asserted about a row afterwards.
    assert {g["name"] for g in _bench.gates(item)} == {
        "statement-grade", "the reference retrieves it", "rows", "every line read",
        "not already in the record", "why_entered", "why_exited"}
    assert _bench.approved(_ready(item))


def test_all_three_statement_grade_limbs_are_required(item):
    """Dated · an authority that can be asked again · a named reference that retrieves it.
    The third is the one that gets skipped, and it is the one that makes the row retrievable."""
    _ready(item)
    for limb, _label, _help in _bench.LIMBS:
        item["evidence"] = dict(GOOD_EVIDENCE, **{limb: ""})
        gate = next(g for g in _bench.gates(item) if g["name"] == "statement-grade")
        assert not gate["ok"], f"a missing {limb!r} was accepted"


def test_a_new_position_must_carry_its_reasoning(item):
    """The one field no document supplies. Required for a trade being OPENED, and not for a
    dividend — a rationale is owed for a decision, not for an event that merely happened.

    TWO FIELDS, because the record has two, and Holdings and Round Trips show both. One field
    could only fill one.
    """
    _ready(item)
    item["why"] = {"why_entered": "", "why_exited": ""}
    assert not next(g for g in _bench.gates(item) if g["name"] == "why_entered")["ok"]

    # A dividend is not a decision, so no ENTRY reason is owed for one.
    item["rows"] = [{"table": "income", "values": {"ticker": "CRNT", "category": "Dividend"}}]
    assert next(g for g in _bench.gates(item) if g["name"] == "why_entered")["ok"]


def test_a_sale_owes_an_exit_reason(item):
    """`why_exited` is Round Trips' Why we exited. A sale owes one; a purchase does not."""
    _ready(item)
    assert next(g for g in _bench.gates(item) if g["name"] == "why_exited")["ok"], \
        "a purchase was asked for an exit reason"
    item["rows"] = [{"table": "sales", "values": {"ticker": "PENR.L"}}]
    assert not next(g for g in _bench.gates(item) if g["name"] == "why_exited")["ok"]


def test_an_item_written_before_the_split_still_reads(item):
    """An item written before the two fields existed holds `reasoning` as one string, which was
    always the ENTRY reason — that is what its gate keyed on. It reads as `why_entered`, and
    `bench.why` says why it is not rewritten on disk."""
    legacy = {"rows": [], "reasoning": "the old single field"}
    assert _bench.why(legacy) == {"why_entered": "the old single field", "why_exited": ""}


def test_a_reason_is_never_refused_for_its_length(item):
    """NO WORD CAP. The gate asks whether a reason is owed and written, and nothing about how long
    it runs."""
    _ready(item)
    item["why"] = {"why_entered": "word " * 200, "why_exited": ""}
    gate = next(g for g in _bench.gates(item) if g["name"] == "why_entered")
    assert gate["ok"], gate


@needs("accounts", "buys")
def test_a_closed_vocabulary_refuses_an_invented_spelling(item):
    """Accounts, types, currencies, modes and statuses are closed. A value outside them is a typo
    every time — and record/schema.py checks a cell's TYPE, not its VALUE, so a mistyped account
    name would load cleanly."""
    _ready(item, account=SHARES_ACCOUNT.lower())
    gate = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not gate["ok"] and "is not one of" in gate["detail"]


def test_an_open_vocabulary_accepts_a_value_the_record_has_never_seen(item):
    """A FIRST-EVER PURCHASE OF A NEW COMPANY MUST NOT BE REFUSED: an enforced derived list would
    fail a ticker not yet in buys.csv, blocking precisely the event the bench exists for. Tickers
    and income categories grow in the ordinary course of business; accounts and currencies do
    not."""
    assert _bench.approved(_ready(item, ticker="NEVER-HELD.L"))


@needs("accounts", "buys")
def test_a_row_id_already_in_the_store_is_refused(item):
    """A duplicate id is a silent overwrite waiting to happen."""
    from portfusion.record import rules as D
    _ready(item, trade_id=D.buys[0].trade_id)
    gate = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not gate["ok"] and "already in the store" in gate["detail"]


def test_the_next_id_is_allocated_from_the_store_not_guessed(item):
    from portfusion.record import rules as D
    ids = _bench.next_ids()
    assert ids["buys"] not in {t.trade_id for t in D.buys}
    assert ids["sales"] not in {e.sale_id for e in D.sales}


@needs("accounts", "buys")
def test_every_gate_is_reported_not_just_the_first(item):
    """A form that stops at the first problem makes the reader find them one at a time.

    The claim is that every problem is reported, so the row carries several DIFFERENT KINDS of
    fault and each must come back named.
    """
    item["rows"] = [{"table": "sales", "values": {
        "sale_id": "E-999", "date": "2026-09-01", "account": "XXX", "ticker": GOOD_TRADE["ticker"],
        "qty": "", "price": "not-a-number", "cur": "GBP", "proceeds": "",
        "source": "s", "broker_ref": "", "note": ""}}]
    gate = next(g for g in _bench.gates(item) if g["name"] == "rows")
    detail = gate["detail"]
    for field in ("qty", "price", "account", "proceeds"):
        assert field in detail, f"{field}'s problem was not reported: {detail}"
    assert not gate["ok"]


def test_validation_runs_through_schema_itself():
    """schema._parse is the very function the CSV loader runs on every cell. Using it is
    deliberate — a second copy of the parsing rules would drift — so this pins the name."""
    from portfusion.record import schema
    assert hasattr(schema, "_parse"), \
        "schema._parse was renamed; desk/intake/bench.py validates through it"
    assert _bench.validate_row("income", {"date": "2026-09-01", "account": SHARES_ACCOUNT,
                                          "category": "Dividend", "detail": "d",
                                          "amount": "not-a-number", "source": "s",
                                          "note": "n"})


def test_the_form_is_generated_from_the_schema():
    """A hand-written form would be a third statement of the store's shape, after the schema
    and the CSV header. A new column joins the screen by existing."""
    from portfusion.record import schema
    for table in _bench.TABLES:
        assert [f["name"] for f in _bench.form_for(table)] == \
               [f.name for f in schema.TABLES[table].fields]



def test_a_currency_with_a_rate_is_offered_before_anything_trades_in_it(monkeypatch):
    """THE FIRST TRADE IN A NEW CURRENCY. The bench offers every currency with a rate on file, so a
    new book offers one before anything trades in it."""
    from portfusion.record import rules
    monkeypatch.setattr(rules, "buys", [])
    monkeypatch.setattr(rules, "fx_rows", [("JPY", 190.0, "2026-09-30", "test", "close")])
    assert _bench.vocabulary()["cur"] == ["GBP", "JPY"]


def test_the_vocabulary_is_derived_from_the_record():
    """docs/store.md states these as a markdown table, which is a SECOND statement of what the
    record already holds — so the bench reads the record, not the table."""
    from portfusion.record import rules as D
    v = _bench.vocabulary()
    assert v["account"] == list(D.ACCOUNT_ORDER)


def test_the_paste_block_is_a_row_the_store_would_accept(item):
    """What approving produces. It must be the real CSV line, not an approximation."""
    import csv
    import io
    from portfusion.record import schema
    _ready(item)
    block = _bench.paste_block(item)
    assert len(block) == 1 and block[0]["target"] == "store/buys.csv"
    cells = next(csv.reader(io.StringIO(block[0]["line"])))
    assert len(cells) == len(schema.TABLES["buys"].fields)


def test_discarding_an_item_never_touches_a_document(item, tmp_path):
    """docs/intake.md forbids deleting a document. An item is a note ABOUT one."""
    item["document"] = {"name": "some statement.pdf"}
    _bench.save(item)
    _bench.discard(item["id"])
    assert _bench.all_items() == []


# =====================================================================================
# THE RESEARCH REPO, READ ONLY
#
# `research_note` is a ref into the research repo, and that repo is the source of truth for a
# ref — so the bench READS it and OFFERS what it finds.
#
# THESE USE A FIXTURE REPO, for the reason `tests/desk/test_research_notes.py` gives.
# =====================================================================================

@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    from portfusion.desk.intake import research
    folder = tmp_path / research.INSIGHTS
    folder.mkdir(parents=True)
    (folder / "widget-co-2026-05.mdx").write_text(
        '---\ntitle: "Widget Co: a test note"\nref: NOTE-0099\nkind: Initiation\n'
        'ticker: "LSE: WDGT"\ndate: 2026-05-04\ncompanyTicker: WDGT\n'
        'company: "Widget Co plc"\nposition: long\n'
        'stat:\n  label: "nested, and not wanted"\n  value: "£1.00"\n---\nbody\n')
    (folder / "_example.mdx").write_text(
        '---\ntitle: "Template"\nref: NOTE-XXXX\ndate: 2026-01-01\ncompanyTicker: EXMPL\n---\n')
    monkeypatch.setattr(research, "REPO", tmp_path)
    monkeypatch.setattr(research, "INSIGHTS_URL", "https://example.test/insights")
    return research


def test_a_book_that_names_no_research_repo_offers_no_notes(fake_repo, monkeypatch):
    monkeypatch.setattr(fake_repo, "REPO", None)
    assert not fake_repo.available() and fake_repo.notes() == []


def test_a_book_that_names_no_insights_page_gives_a_note_no_url(fake_repo, monkeypatch):
    monkeypatch.setattr(fake_repo, "INSIGHTS_URL", "")
    assert [n["url"] for n in fake_repo.notes()] == [""]


def test_a_note_is_read_from_its_frontmatter(fake_repo):
    notes = fake_repo.notes()
    assert len(notes) == 1, "the _example template must not be offered as a real note"
    n = notes[0]
    assert (n["ref"], n["ticker"], n["date"]) == ("NOTE-0099", "WDGT", "2026-05-04")
    assert n["url"] == "https://example.test/insights/widget-co-2026-05/"


def test_the_nested_stat_block_is_not_parsed_as_fields(fake_repo):
    """The reader is deliberately not a YAML parser — pulling in a dependency to read six
    keys would put a third-party package in the path of the record. Indented lines are
    skipped, so `stat:`'s children must not leak in as note fields."""
    n = fake_repo.notes()[0]
    assert "label" not in n and "value" not in n
    assert n["title"] == "Widget Co: a test note", "quotes are stripped"


def test_the_ticker_suffix_is_stripped_when_matching(fake_repo):
    """The book's codes carry a mode — ORLA and ORLA SB are one company, and the note is
    about the company."""
    assert [n["ref"] for n in fake_repo.for_ticker("WDGT SB")] == ["NOTE-0099"]
    assert [n["ref"] for n in fake_repo.for_ticker("WDGT")] == ["NOTE-0099"]


def test_the_book_works_with_no_research_repo_at_all(tmp_path, monkeypatch):
    """THE RESEARCH REPO IS ANOTHER PROJECT, so its absence must be silent: the Bench shows no
    research notes waiting, and nothing raises."""
    from portfusion.desk.doors import research_notes
    from portfusion.desk.intake import research
    monkeypatch.setattr(research, "REPO", tmp_path / "nowhere")
    assert research.available() is False
    assert research.notes() == []
    assert research.for_ticker("ORLA") == []
    assert research_notes.owed() == []
    assert bench_panel.data()["notes"] == []


# =====================================================================================
# IG EVENTS ONTO THE BENCH — the third route on
#
# After `+ new item` and a document. The marks rule sends an event to the bench rather than into the
# record: a trade, close, dividend or capital movement happened once and is history, so it needs
# evidence, a reason and approval. `ig-events` REPORTS; this carries one of its events onto the
# bench.
# =====================================================================================

# The event's numbers are canned (an API reply is checked for shape, not against holdings);
# its ACCOUNT and TICKER are the loaded book's, because the closed vocabulary refuses others.
_IG_CLOSE = {
    "table": "sales", "ref": "DIAAAATESTCLOSE", "kind": "close",
    "account": SPREAD_BET_ACCOUNT, "what": f"{SYNTHETIC_TICKER} · Sell · £3/pt · 4,210 pts",
    "values": {"sale_id": _EID, "date": "2026-08-28", "account": SPREAD_BET_ACCOUNT,
               "ticker": SYNTHETIC_TICKER, "qty": "", "stake": 3, "traded_price": 4210.0,
               "cur": "GBP", "rate": "", "proceeds": 12630.0, "source": "IG REST /history/activity 28 Aug 2026",
               "broker_ref": "DIAAAATESTCLOSE", "realisation_id": "R-TEST99", "closes": "",
               "note": "Closes DIAAAAOLD"},
}


@pytest.fixture
def swept(tmp_path, monkeypatch):
    """A carried event, on a bench of its own: never the loaded book's `_inbox/.bench/`."""
    from portfusion.desk.intake import bench as _b
    monkeypatch.setattr(_b, "BENCH_DIR", tmp_path / "bench")
    made = []

    def _carry(event=None, marks=None):
        item = _b.for_event(event or dict(_IG_CLOSE), marks=marks)
        made.append(item["id"])
        return item

    yield _carry
    for i in made:
        _b.discard(i)


def _set_up(code="NEWCO SB", contract="NEWCO-JUN27", company="Newco Inc.", ticker=None):
    """A first bet on a contract the book lacks, as the sweep's set-up sends it: the trade, with
    its new line, company and contract. Invented names; the account is the loaded book's."""
    from portfusion.record import schema
    trade = {"trade_id": free_id("buys"), "date": "2026-08-12",
             "source": _rules.trade_source("ig-api", "2026-08-12", endpoint="/history/activity"),
             "account": SPREAD_BET_ACCOUNT, "ticker": code if ticker is None else ticker,
             "cur": "GBP", "qty": "", "stake": 1, "cost": "", "level_points": 50.0,
             "broker_ref": "DIAAAATESTNEWOPEN", "note": "", "contract": contract,
             "traded_price": "", "rate": ""}

    def row(table, **v):
        return {"table": table, "values": {f.name: v.get(f.name, "") for f in schema.TABLES[table].fields}}
    return {"table": "buys", "ref": "DIAAAATESTNEWOPEN", "kind": "open",
            "account": SPREAD_BET_ACCOUNT, "what": "Newco Inc (24 Hours) · Buy · £1/pt · 50 pts",
            "values": trade, "with": [
                row("securities", ticker=code, company=company, held_as="spread bet",
                    currency="USD", symbol="XNYS:NEWCO", points_per_unit="100"),
                row("companies", company=company, sector="Industrials", region="US"),
                row("contracts", contract=contract, epic="DM.D.NEWCOUS.JUN.IP", funding="dated",
                    ticker=code)]}


#: The new contract's first mark, as the set-up press reads it from IG.
_FIRST_MARK = {"mark_key": "NEWCO-JUN27", "price": 50.4, "currency": "USD", "as_of": "2026-08-12",
               "source": "IG REST LIVE DM.D.NEWCOUS.JUN.IP, bid 50.4", "struck": "live",
               "at": "2026-08-12T10:00:00Z"}


@needs("accounts", "buys")
def test_a_set_up_writes_its_line_company_contract_and_trade_together(swept, store_copy,
                                                                      tmp_path, monkeypatch):
    """The first bet on a new contract lands with everything it stands on, in one write, and
    the line it sets up reads as the bet's own."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    item = swept(_set_up(), marks=[_FIRST_MARK])
    item["why"] = {"why_entered": "A first position on the thesis in the note.", "why_exited": ""}
    _bench.save(item)
    assert [g["name"] for g in _bench.gates(item) if not g["ok"]] == []

    done = _commit.commit(item["id"])
    assert done["written"] == {"securities": 1, "companies": 1, "contracts": 1, "buys": 1}
    assert done["marked"] == ["NEWCO-JUN27"]
    assert schema.load("contracts")[-1][0::3] == ("NEWCO-JUN27", "NEWCO SB")
    assert _rules.CONTRACT_CODE["NEWCO-JUN27"] == "NEWCO SB"
    assert schema.load("current-prices")[-1][:2] == ("NEWCO-JUN27", 50.4)
    jh = schema.TABLES["journal"].header
    assert ("append", "current-prices") in {(r[jh.index("op")], r[jh.index("table")])
                                            for r in schema.load("journal")
                                            if r[jh.index("ref")] == item["id"]}


@pytest.mark.parametrize("event, says", [
    (dict(_set_up(), values=dict(_set_up()["values"], ticker="")), "a new line needs its trade"),
    (_set_up(ticker="OTHER SB"), "a new contract needs its trade, on its line"),
    (dict(_set_up(), **{"with": _set_up()["with"][:1] + _set_up()["with"][2:]}),
     "has no company row"),
    (_set_up(), "a new contract needs its first mark"),
])
def test_a_set_up_that_does_not_stand_with_its_trade_is_refused(swept, event, says):
    """A line, company or contract is written only with the trade that first needs it, and
    agreeing with it: the register holds nothing no trade stands on."""
    item = swept(event)
    rows = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not rows["ok"] and says in rows["detail"], rows["detail"]


@pytest.mark.parametrize("priced", [True, False])
def test_the_set_up_press_reads_the_contracts_first_mark_or_refuses(swept, monkeypatch, priced):
    """The set-up press asks IG for the new contract's level: a priced one rides on the item as
    its first mark, and an unpriced one opens no item at all."""
    from portfusion.desk.intake import bench as _b, sweep
    from portfusion.feeds import ig
    level = {"priced": priced, "level": 50.4 if priced else None, "currency": "USD",
             "as_of": "2026-08-12", "source": _FIRST_MARK["source"] if priced else "",
             "struck": "live", "at": _FIRST_MARK["at"], "status": "TRADEABLE" if priced else "CLOSED"}
    asked = []
    monkeypatch.setattr(ig, "contract_levels", lambda mapped=None: asked.append(mapped)
                        or {"rows": [dict(level, contract="NEWCO-JUN27")]})
    got = sweep.set_up(_set_up())
    assert asked == [{"NEWCO-JUN27": (None, "DM.D.NEWCOUS.JUN.IP")}]
    if priced:
        item = _b.get(got["id"])
        assert item["marks"] == [_FIRST_MARK]
        _b.discard(item["id"])
    else:
        assert got == {"ok": False, "error": "IG gave no level for DM.D.NEWCOUS.JUN.IP: CLOSED"}


def test_a_swept_event_reaches_the_bench_with_its_evidence_filled(swept):
    """THE EVIDENCE IS THE HALF AN API CAN HONESTLY SUPPLY. The class is `ig-api`, whose
    reference_is is "the dealId the row stores"; the authority is the endpoint; the date is the
    event's own. All three statement-grade limbs, none of them typed by anybody."""
    item = swept()
    assert item["evidence_class"] == "ig-api"
    assert item["evidence"]["reference"] == "DIAAAATESTCLOSE"
    # ITS TITLE IS THE EVENT'S OWN WORDS, as the Trades page says it; the deal is the reference
    # beside it.
    assert item["title"] == _IG_CLOSE["what"]
    assert item["evidence"]["dated"] == "2026-08-28"
    assert "IG REST" in item["evidence"]["authority"]
    assert [g["ok"] for g in _bench.gates(item) if g["name"] == "statement-grade"] == [True]


def test_a_swept_event_never_arrives_with_its_reason_written(swept):
    """THE WHOLE REASON AN EVENT GOES TO THE BENCH. No API supplies the why, the generated row
    carries an explicit *** NOT YET RECORDED — owed *** marker, and the item cannot be approved
    until a human writes one. If this ever passes with a reason pre-filled, the bench has become
    a formality."""
    item = swept()
    assert item["why"] == {"why_entered": "", "why_exited": ""}
    blocked = [g["name"] for g in _bench.gates(item) if not g["ok"]]
    assert blocked == ["why_exited"], f"a close owes an exit reason; blocked={blocked}"
    assert not _bench.approved(item)


def test_pressing_work_it_twice_lands_on_the_same_item(swept):
    """Idempotent on the DEAL ID, the same shape for_document() has for a document."""
    first, second = swept(), swept()
    assert first["id"] == second["id"]
    from portfusion.desk.intake import bench as _b
    assert len([i for i in _b.all_items()
                if i.get("event_ref") == "DIAAAATESTCLOSE"]) == 1


def test_an_event_whose_row_does_not_fit_its_table_is_refused(swept):
    """The event arrives from the BROWSER — the sweep's result is held client-side and posted
    back — so it is checked rather than trusted. A half-filled row must not be staged and then
    discovered at commit."""
    from portfusion.desk.intake import bench as _b
    half = dict(_IG_CLOSE, values={"sale_id": _EID})
    with pytest.raises(ValueError) as e:
        _b.for_event(half)
    assert "must fill exactly" in str(e.value)

    with pytest.raises(ValueError):
        _b.for_event(dict(_IG_CLOSE, table="not-a-table"))


def test_an_event_with_no_deal_reference_is_refused(swept):
    """The reference IS the evidence for an `ig-api` row. Without it the item could never
    satisfy limb 3, and the duplicate gate would have nothing to match on."""
    from portfusion.desk.intake import bench as _b
    with pytest.raises(ValueError) as e:
        _b.for_event(dict(_IG_CLOSE, ref=""))
    assert "deal reference" in str(e.value)


def test_carrying_an_event_writes_nothing_to_the_record(swept):
    """It creates a bench item, which is staging — `_inbox/.bench/`, gitignored, and not a
    figure until commit.py writes it."""
    from portfusion.record import schema
    before = {n: t.path.read_bytes() for n, t in schema.TABLES.items()}
    swept()
    after = {n: t.path.read_bytes() for n, t in schema.TABLES.items()}
    assert before == after


def test_the_carry_action_is_declared_and_does_not_write():
    """The marks rule: an action may never declare writes='events' — Action refuses to be
    constructed. This one is what the marks rule prescribes, not an exception to it, so it writes
    nothing and names the human step that runs it."""
    from portfusion.desk import actions
    a = actions.get("ig-event-to-bench")
    assert a.writes is None
    assert a.gate, "a button that stages a record row names the human step that presses it"
    # ON THE BENCH, with the sweep that produces the event it carries: pressed from another
    # tab, it would move you across tabs to what you had just made.
    assert a.panel == "bench"


def test_a_row_scoped_action_is_not_a_panel_button():
    """"Work this event" means anything only against ONE event from a sweep, and it is rendered on
    that event's row.

    The property, not the name: an action declares `inline` and the panel filters on that, so
    the next row-scoped action does not have to be special-cased in the UI.
    """
    from portfusion.desk import actions
    a = actions.get("ig-event-to-bench")
    assert a.inline is True
    assert a.as_json()["inline"] is True, "the client filters on this, so it must be exposed"

    listed = [x.name for x in actions.all_actions() if x.panel == "accounts" and not x.inline]
    assert "ig-event-to-bench" not in listed
    # RECONCILE HOLDS NONE. A share account's reading is filed with its holdings export on the
    # Bench; IG equity is read with its levels on the Price Refresh; and the event sweep lives on
    # the Bench, where its output goes.
    assert listed == []
    bench_listed = [x.name for x in actions.all_actions()
                    if x.panel == "bench" and not x.inline]
    assert "ig-events" in bench_listed, "the sweep must be offered where its output goes"


def test_the_panel_list_in_the_browser_skips_inline_actions(repo_root):
    """The filter has to be in app.js too — the desk renders the list client-side, and a
    correct flag nothing reads is not a fix."""
    js = desk_script()
    assert "!a.inline" in js, "app.js still lists every action for the panel, inline or not"


# =====================================================================================
# THE BENCH IS NOT STRICTER THAN THE STORE
# =====================================================================================

def test_a_column_the_store_lets_be_blank_is_not_required_here():
    """`required = not field.null` would be stricter than the store. `schema._parse` returns ""
    for a blank str column whatever `null` says — only a blank NUMBER raises — and income.note's
    own schema comment reads: often `""`, "and that is a real value".

    The bench refuses nothing the store accepts, as it accepts nothing the store refuses.
    """
    required = {f["name"]: f["required"] for f in _bench.form_for("income")}
    assert required["note"] is False, "the store accepts a blank note; the bench must too"
    assert required["amount"] is True, "a blank number is a GAP and must still be refused"

    row = {"date": "2026-08-21", "account": SPREAD_BET_ACCOUNT,
           "category": "Funding interest", "detail": "Funding charge",
           "amount": -1.34, "source": "IG REST /history/transactions", "note": ""}
    assert _bench.validate_row("income", row) == []


def test_a_blank_number_is_still_refused():
    """Blank is accepted exactly as far as the store accepts it."""
    row = {"date": "2026-08-21", "account": SPREAD_BET_ACCOUNT,
           "category": "Funding interest", "detail": "d", "amount": "",
           "source": "s", "note": ""}
    assert any("amount" in p for p in _bench.validate_row("income", row))


def test_required_is_the_stores_own_answer_for_every_table():
    """The property, not the column. Anything the loader would accept blank must be accepted
    blank here, across every table the bench produces — so the two cannot drift apart."""
    from portfusion.record import schema
    for table in _bench.TABLES:
        for spec in _bench.form_for(table):
            field = next(f for f in schema.TABLES[table].fields if f.name == spec["name"])
            try:
                schema._parse(field, "", table, 0)
                store_refuses = False
            except ValueError:
                store_refuses = True
            assert spec["required"] is store_refuses, (
                f"{table}.{spec['name']}: the bench says required={spec['required']} and the "
                f"store says {store_refuses}")


def test_an_empty_list_says_nothing_and_the_page_explains_itself_once(repo_root):
    """An empty list is not drawn. The page explains itself in one place, its fold, in a reader's
    words and in the order the work comes in."""
    js = desk_script()
    rendered = [line for line in js.splitlines() if "<li" in line and "clear</span>" in line]
    assert not any("nothing on the bench" in line or "no documents waiting" in line
                   or "the workbench is clear" in line for line in rendered)
    acts = js[js.index("async function wireActions("):js.index("const ACTION_VIEW")]
    assert "a.summary" not in acts, "the sweep's description is the fold's, not the button's"
    titles = [t for t, _ in bench_panel.WHY]
    assert titles == ["A dropped document", "A swept event", "Writing it to the record"]
    words = " ".join(text for _, text in bench_panel.WHY).lower()
    assert not [w for w in ("decision c", "git", "commit", "_archive", "_inbox", "store/", "csv")
                if w in words], words
    assert bench_panel.data()["why"] == bench_panel.WHY


def test_a_swept_event_row_is_not_held_to_the_prose_measure(repo_root):
    """A swept row carries a generated CSV line. `body.data #main .items li` caps a list item at
    the PROSE measure, which is right for every other list here and wrong for this one."""
    css = (SRC / "desk" / "static" / "app.css").read_text()
    assert ".items li.swept { max-width: none; }" in css
    assert ".swept-do" in css and "white-space: nowrap" in css


def test_the_sweep_can_ask_what_became_of_its_events():
    """A SNAPSHOT DOES NOT KNOW WHAT HAPPENED NEXT. The sweep's result is held in the browser so
    that returning to its tab is not another 30-day call to the broker; each row's state is asked
    here, or a carried row offers "work it" again and a WRITTEN one reads as missing.

    The events come from the snapshot; their state comes from here, fresh every render.
    """
    from portfusion.desk.intake import bench
    out = bench.sweep_status(["NOT-A-REAL-REFERENCE", ""])
    assert "" not in out, "a blank reference is not a question worth asking"
    assert out["NOT-A-REAL-REFERENCE"] == {"in_record": False, "tables": [], "item": None}


def test_an_event_on_the_bench_is_reported_as_such(swept):
    from portfusion.desk.intake import bench
    item = swept()
    st = bench.sweep_status(["DIAAAATESTCLOSE"])["DIAAAATESTCLOSE"]
    assert st["item"]["id"] == item["id"]
    assert st["item"]["blocked"] == ["Why we exited"], "it must say what the item still owes"
    assert st["in_record"] is False


def test_a_reference_already_in_the_record_is_found():
    """The same scan the duplicate gate runs — one implementation, two callers."""
    from portfusion.desk.intake import bench
    from portfusion.record import schema
    # any reference the store actually carries; the IG sweep writes one into income.source
    known = None
    for row in schema.load("income"):
        for cell in row:
            if isinstance(cell, str) and "ref CS" in cell:
                known = cell.split("ref ")[-1].strip().strip('"')
                break
        if known:
            break
    if not known:
        pytest.skip("no IG-referenced row in the record to check against")
    st = bench.sweep_status([known])[known]
    assert st["in_record"] is True and "income" in st["tables"]


def test_a_negative_income_row_is_labelled_a_cost(repo_root):
    """income.csv holds both, and its own schema doc says so: "COSTS ARE NEGATIVE, income
    positive". A -1.41 funding charge headed simply "income" reads as the opposite of what it
    is. The sign is the record's rule, so the label follows it rather than a second list."""
    js = desk_script()
    assert 'r.table === "income" && parseFloat(r.values.amount) < 0' in js
    assert "a cost — negative" in js


def test_the_header_is_re_read_on_every_panel_switch(repo_root):
    """The status line has to be current when the reader arrives at it.

    Fetched at boot alone, `/api/state` would quote its page-load stamp while a bench commit
    moved the store.

    THE HOOK IS THE SWITCH, NOT THE WRITE, for the reason `book()` keys its cache on the
    store's mtime rather than trusting its callers: the desk's writers are not the only way
    the record moves, and a hand edit, a git pull, a checkout or a revert leaves no handler to
    hang this on.
    """
    js = desk_script()
    show = js[js.index("async function show(name)"):]
    show = show[:show.index("\n(async function start()")]
    assert '/api/state' in show, (
        "show() does not re-read /api/state, so the freshness line goes stale when anything "
        "writes to the store")
    assert "drawFreshness" in show, (
        "show() fetches the state but never repaints the header with it")


# =====================================================================================
# `evidence` IS A CLASS KEY, `source` IS THE LINE — on every table
# =====================================================================================

def test_the_bench_accepts_the_source_line_every_trade_already_carries():
    """THE CENSUS, and it is the strongest form this check has: if the bench would refuse a
    value the store already holds on every row, the bench is wrong and not the store.
    """
    from portfusion.record import rules as D
    from portfusion.desk.intake import bench
    refused = []
    for t in D.buys:
        if not (t.source or "").strip():
            continue
        row = {"trade_id": free_id("buys"), "date": "2026-09-05", "source": t.source,
               "account": t.acct, "ticker": t.ticker, "cur": t.cur,
               "qty": t.qty, "cost": t.cost}
        if [p for p in bench.validate_row("buys", row) if p.startswith("source:")]:
            refused.append(t.source)
    assert not refused, (
        f"the bench would refuse the source line on {len(refused)} row(s) the store already "
        f"holds, e.g. {sorted(set(refused))[:3]} — trades.source is prose, not a vocabulary")


def test_the_cash_observation_evidence_is_still_a_closed_class_key():
    """THE OTHER HALF. On `cash-readings` `evidence` holds an EVIDENCE_CLASSES KEY, and
    `test_record.py` refuses a row citing a class the record does not know — so a free text box
    there would let the bench build a row the suite then rejects. No table may use the name
    for anything else."""
    from portfusion.desk.intake import bench
    complaints = bench.validate_row("cash-readings", {
        "account": "Rowe HL ISA", "as_of": "2026-09-08", "cash": 1.0, "evidence": "made-up"})
    assert any(c.startswith("evidence:") for c in complaints), \
        "cash-readings.evidence no longer refuses a class the record does not know"
    assert "evidence" in bench.closed_for("cash-readings")
    from portfusion.record import schema
    assert "evidence" not in schema.TABLES["buys"].header, \
        "trades has an `evidence` column again — its provenance line is `source`"


def test_a_free_prose_column_offers_no_choices_either(repo_root):
    """Not just an open vocabulary — NO vocabulary. Offering the class keys as suggestions
    under a field that wants a sentence would invite the wrong value into the one column whose
    whole job is naming the document. The browser renders a `choices` list as a combobox
    whatever `closed` says."""
    from portfusion.desk.intake import bench
    spec = {f["name"]: f for f in bench.form_for("buys")}["source"]
    assert spec["choices"] is None and spec["closed"] is False, \
        f"trades.source offers a vocabulary: {spec}"


def test_the_archive_name_carries_the_instant_the_document_states(tmp_path, monkeypatch):
    """THREE HL EXPORTS ARRIVE THE SAME DAY UNDER THE SAME TITLE, and two of them can differ
    for no reason but being pulled minutes apart — HL values shares at a bid delayed
    fifteen minutes, and New York may be open. Without the time the archive disambiguates
    them with a bench item id, which tells a later reader nothing about which instant the
    figures were struck at.

    ONLY WHEN THE DOCUMENT AGREES WITH THE LIMB. A time spliced from a document onto a date the
    operator typed for a different day would invent a third thing.
    """
    from portfusion.desk.intake import filing

    inbox = tmp_path / "_inbox"
    inbox.mkdir()
    (inbox / "export.csv").write_bytes(
        'Portfolio Summary\nValuation as at,03-03-2025 14:10\n'
        'Account,Stock value,Total cash,Total value,Available to invest,\n'.encode("cp1252"))
    monkeypatch.setattr(filing, "BOOK", tmp_path)

    item = {"id": "B-T", "document": {"name": "export.csv"}, "rows": [],
            "evidence": {"dated": "2025-03-03", "authority": "HL Portfolio Summary totals "
                         "download", "reference": "3 Mar 2025 14:10"}}
    assert filing.archive_name(item, "export.csv").startswith("03 Mar 2025 14.10 "), \
        filing.archive_name(item, "export.csv")

    # A different day: the stamp is withheld rather than spliced.
    item["evidence"]["dated"] = "2026-09-07"
    assert filing.archive_name(item, "export.csv").startswith("07 Sep 2026 HL"), \
        filing.archive_name(item, "export.csv")


def test_a_document_that_states_no_instant_still_gets_a_name():
    """The time is provenance the file happens to carry, not something the archive depends on.
    A document sitting unarchived is the worse outcome by a distance."""
    from portfusion.desk.intake import filing
    assert filing._document_stamp("does-not-exist.csv", __import__("datetime").date(2026, 9, 8)) == ""


def test_a_recognised_document_prefills_only_what_it_states(tmp_path, monkeypatch):
    """DERIVATION, NOT A PROPOSAL. Every value filled here is read out of the document's own text —
    `propose._derived()` works this way: fill a blank from something checkable, never overwrite, and
    say where it came from.

    ONE MATCH ONLY. Two is ambiguous, and a class decides which columns mean what, so guessing
    between them is worse than leaving both blank — a pre-filled wrong answer is the one nobody
    re-reads.
    """
    from portfusion.record import rules as D
    from portfusion.desk.intake import bench, read_document

    inbox = tmp_path / "_inbox"
    (inbox / ".bench").mkdir(parents=True)
    (inbox / "export.csv").write_bytes(
        'Portfolio Summary\nValuation as at,03-03-2025 14:10\n'
        'Account,Stock value,Total cash,Total value,Available to invest,\n'.encode("cp1252"))
    monkeypatch.setattr(read_document, "INBOX", str(inbox))
    monkeypatch.setattr(bench, "BENCH_DIR", inbox / ".bench")

    item = bench.for_document("export.csv")
    assert item["evidence_class"] == "hl-account-totals", item["evidence_class"]
    assert item["evidence"]["authority"] == D.EVIDENCE_BY_KEY["hl-account-totals"].authority
    assert item["evidence"]["dated"] == "2025-03-03", item["evidence"]
    # The two limbs the document cannot answer stay empty — a supplied value is a claim.
    assert item["evidence"]["reference"] == "", "a reference was invented"
    assert item["recognised"]["instant"] == "2025-03-03 14:10"


@needs("accounts", "buys")
def test_a_contract_note_fills_all_three_limbs_from_its_own_text(tmp_path, monkeypatch):
    """A CONTRACT NOTE STATES ALL THREE: who issued it, when the trade was dealt, and its
    number. A copy of a filed note opened on the bench fills each from the document. The date
    is the dealing date, never the day the file was downloaded. The archive name then carries
    the dealing time, which `rules.ARCHIVE_CONVENTION` asks of any document that states its
    own instant.

    THE LOADED BOOK'S NEWEST NOTE FILED WITH ITS TIME, and what to expect is read from that
    name, so the test runs on any book with one on file."""
    import datetime as dt
    import re
    import shutil
    from portfusion.record import rules as D
    from portfusion.record import schema
    from portfusion.desk.intake import bench, filing, read_document

    inbox = tmp_path / "_inbox"
    (inbox / ".bench").mkdir(parents=True)
    named = [(m, p) for p in schema.STATEMENTS.glob("*.pdf") if (m := re.match(
        r"(\d{2} \w{3} \d{4}) (\d{2})\.(\d{2}) ii contract note ([A-Z0-9]{5,})", p.name))]
    assert named, "the loaded book files no contract note under its dealing time"
    m, filed = max(named, key=lambda n: (dt.datetime.strptime(n[0].group(1), "%d %b %Y"), n[1].name))
    day = dt.datetime.strptime(m.group(1), "%d %b %Y").date()
    ref, time = m.group(4), f"{m.group(2)}:{m.group(3)}"
    shutil.copy(filed, inbox / "note.pdf")
    monkeypatch.setattr(read_document, "INBOX", str(inbox))
    monkeypatch.setattr(bench, "BENCH_DIR", inbox / ".bench")
    monkeypatch.setattr(filing, "BOOK", tmp_path)

    item = bench.for_document("note.pdf")
    assert item["evidence_class"] == "ii-contract-note"
    assert item["evidence"] == {"dated": day.isoformat(), "reference": ref,
                                "authority": D.EVIDENCE_BY_KEY["ii-contract-note"].authority}
    assert item["recognised"]["instant"] == f"{day} {time}"
    assert item["recognised"]["instant_from"] == "document"
    assert filing.archive_name(item, "note.pdf").startswith(
        f"{day:%d %b %Y} {time.replace(':', '.')} ii contract note {ref}"), \
        filing.archive_name(item, "note.pdf")


def test_an_unrecognised_document_is_left_entirely_blank(tmp_path, monkeypatch):
    """Most classes carry no fingerprint, because no sample has been seen. Filling nothing is
    the honest answer and the item is still workable by hand."""
    from portfusion.desk.intake import bench, read_document

    inbox = tmp_path / "_inbox"
    (inbox / ".bench").mkdir(parents=True)
    (inbox / "mystery.csv").write_text("something,else\n1,2\n", encoding="utf-8")
    monkeypatch.setattr(read_document, "INBOX", str(inbox))
    monkeypatch.setattr(bench, "BENCH_DIR", inbox / ".bench")

    item = bench.for_document("mystery.csv")
    assert item["evidence_class"] == ""
    assert item["evidence"]["authority"] == ""
    assert item["recognised"]["classes"] == []


def test_a_document_read_in_full_that_yields_nothing_can_still_be_closed():
    """NONE PROPOSED AND NONE LEFT ARE NOT THE SAME STATE.

    A document whose every dealing line is already in the record is not unfinished work — it is
    the PROOF that the dealing side reconciles, which is the question it was pulled to answer, so
    it has to be archivable.
    """
    from portfusion.desk.intake import bench
    read = {"evidence": {"dated": "2025-03-03", "authority": "HL Portfolio Summary download",
                         "reference": "Capital, 3 Mar 2025 14:08"},
            "rows": [], "acknowledged": [],
            "examined": [{"line": "B000000011 Kappel", "why": "already in the record as T-999",
                          "in_record": "buys"}]}
    gate = next(g for g in bench.gates(read) if g["name"] == "rows")
    assert gate["ok"], gate
    assert "none of them new" in gate["detail"]

    unread = dict(read, examined=[])
    gate = next(g for g in bench.gates(unread) if g["name"] == "rows")
    assert not gate["ok"], "an item that has read nothing is still not approvable"
    assert gate["detail"] == "no rows proposed yet"


def test_a_zero_row_document_keeps_its_account_in_the_archived_name():
    """`_covers()` reads the tickers or accounts off the ROWS, so a document that yields none would
    be filed under a name that does not say whose account it is. The reader derives the account from
    the client number the document prints; this is that derivation, one step later."""
    from portfusion.desk.intake import filing
    item = {"rows": [], "account": "Rowe HL ISA"}
    assert filing._covers(item) == "Rowe HL ISA"
    # A row's own account still wins — the fallback is a fallback.
    item = {"rows": [{"values": {"account": "Voss ii ISA"}}], "account": "Rowe HL ISA"}
    assert filing._covers(item) == "Voss ii ISA"


def test_a_withdrawn_document_leaves_the_workbench_and_is_not_destroyed(workbench):
    """The exit, and the whole of its claim: the document is somewhere afterwards."""
    from portfusion.desk.intake import withdraw
    box, out = workbench
    (box / "note.csv").write_bytes(b"a,b\n1,2\n")

    r = withdraw.withdraw("note.csv", why="not needed")

    assert not (box / "note.csv").exists(), "it did not leave the workbench"
    assert (out / "note.csv").read_bytes() == b"a,b\n1,2\n", "the bytes did not survive"
    assert r["returned"] is False, "nothing was already at the destination"


def test_withdrawing_refuses_a_destination_inside_the_repository(workbench):
    """A withdrawn document is not evidence, so it must not come to rest where evidence does.

    `_archive/statements/` is the case that matters: a file resting there is citable by a row,
    and a row citing a document that was never entered is the defect the archive exists to
    make impossible.

    BOTH HALVES OF THE RULE: the loaded book's own evidence folder, wherever the book sits, and
    a folder inside the checkout, which every copy of the code has.
    """
    from portfusion.record import schema
    from portfusion.desk.intake import withdraw, dropoff
    box, _ = workbench
    (box / "note.csv").write_bytes(b"x")
    for inside in (schema.STATEMENTS, SRC / "tests"):
        with pytest.raises(dropoff.Refused) as e:
            withdraw.withdraw("note.csv", destination=str(inside))
        assert "inside the repository" in str(e.value), inside
        assert (box / "note.csv").exists(), "a refused withdrawal moved something"


def test_withdrawing_removes_the_workbench_copy_ONLY_when_the_bytes_match(workbench):
    """The one path in desk/ that deletes a file, and the only thing standing in front of it.

    `dropoff.accept()` COPIES bytes onto the workbench, so the original is usually still in the
    folder it was downloaded to and the destination already holds the name. Removing the
    workbench copy is then provably not a deletion — the bytes are demonstrably still there.

    A different file wearing the same name is the dangerous case, and it is refused exactly as
    an overwrite is. If this test ever fails, the failure is a document destroyed.
    """
    from portfusion.desk.intake import withdraw, dropoff
    box, out = workbench

    (box / "same.csv").write_bytes(b"identical")
    (out / "same.csv").write_bytes(b"identical")
    r = withdraw.withdraw("same.csv")
    assert r["returned"] is True
    assert not (box / "same.csv").exists()
    assert (out / "same.csv").read_bytes() == b"identical", "the surviving copy was touched"

    (box / "diff.csv").write_bytes(b"one")
    (out / "diff.csv").write_bytes(b"another")
    with pytest.raises(dropoff.Refused) as e:
        withdraw.withdraw("diff.csv")
    assert "NOT the same file" in str(e.value)
    assert (box / "diff.csv").read_bytes() == b"one", "the workbench copy was destroyed"
    assert (out / "diff.csv").read_bytes() == b"another", "the destination was overwritten"


# =====================================================================================
# STATEMENT-GRADE, AT THE DOOR
#
# "Nothing enters the record except through the door — an authenticated feed read, or a
# broker document filed in _archive/statements/." Checked only afterwards, by the audit's
# evidence chain, it finds a row already written and hands somebody an errand. A gate is a
# refusal, and no row.
# =====================================================================================

def _gate(item, name="the reference retrieves it"):
    return next(g for g in _bench.gates(item) if g["name"] == name)


def test_a_document_class_owes_a_document(item):
    """A contract note is retrieved by its FILE. Citing one with nothing on the bench is a
    row pointing at a document nobody can open."""
    _ready(item)
    item["evidence_class"] = "ii-contract-note"
    item["document"] = None
    g = _gate(item)
    assert not g["ok"], "a document class was accepted with no document"
    assert "on the bench" in g["detail"]

    item["document"] = {"name": GOOD_DOCUMENT}
    assert _gate(item)["ok"], "a document class was refused WITH its document"


def test_a_document_named_but_not_on_the_workbench_is_refused(item):
    """A NAME IS NOT A FILE. A document taken off the workbench after its item was opened lets no
    row commit."""
    _ready(item)
    assert _gate(item)["ok"], "the fixture's own document, on its workbench, was refused"
    item["document"] = {"name": "Contract_Note_NOT_ON_THE_BENCH.pdf"}
    g = _gate(item)
    assert not g["ok"], "a document nobody dropped in passed on its name alone"
    assert "not on the workbench" in g["detail"]


def test_a_document_gone_before_it_is_filed_writes_nothing(item, store_copy, tmp_path,
                                                          monkeypatch):
    """THE DOOR'S OWN REFUSAL, behind the gate's. The document is filed INSIDE the write's
    envelope, so if it is gone when the filing comes — whatever a gate said a moment before —
    every row and the journal are taken back out and the item stays on the bench."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    _bench.save(_ready(item))
    held = {t: schema.TABLES[t].path.read_bytes() for t in ("buys", "reasoning", "journal")}
    # The gates as they read with the document still there, so only the door stands in the way.
    passed = _bench.gates(item)
    assert all(g["ok"] for g in passed), passed
    monkeypatch.setattr(_bench, "gates", lambda _item: passed)
    (tmp_path / "_inbox" / GOOD_DOCUMENT).unlink()

    with pytest.raises(_commit.Refused, match="not on the workbench"):
        _commit.commit(item["id"])
    for table, before in held.items():
        assert schema.TABLES[table].path.read_bytes() == before, f"{table}.csv kept a row"
    assert _bench.get(item["id"])["state"] not in _commit.TERMINAL, \
        "the item left the bench without its rows"
    assert not (tmp_path / "archive").exists() or not list((tmp_path / "archive").iterdir())


def test_an_api_read_owes_no_file(item):
    """An authenticated endpoint and a stored dealId ARE the retrieval. Asking an IG sweep for
    a PDF would refuse the strongest evidence in the book for not being paper."""
    _ready(item)
    item["evidence_class"] = "ig-api"
    item["document"] = None
    g = _gate(item)
    assert g["ok"], f"an api class was asked for a file: {g['detail']}"


def test_a_screenshot_is_refused_at_the_door(item):
    """THE CLASS THAT SAYS SO ITSELF. `retrieval="none"` means nothing retrieves the figure a
    second time, which is exactly what statement-grade forbids.

    It stays on the list of classes — an honest weak claim that shows up as one is better than
    a figure filed under "statement" — and the door is where it stops.
    """
    from portfusion.record import rules as _rules
    _ready(item)
    shots = [e.key for e in _rules.EVIDENCE_CLASSES if e.retrieval == "none"]
    assert shots, "no class declares retrieval='none' any more — has the vocabulary moved?"
    for key in shots:
        item["evidence_class"] = key
        g = _gate(item)
        assert not g["ok"], f"{key} passed the door"
        assert "nothing retrieves it" in g["detail"]


def test_the_bench_offers_no_closed_class_and_refuses_one_chosen_anyway(item):
    """`not-on-file` is closed because nothing retrieves it. The bench lists it as closed, and
    its gate refuses an item that cites it."""
    from portfusion.record import rules as D
    listed = {c["key"]: c for c in _bench.evidence_classes()}
    for key in D.CLOSED_TO_NEW_ENTRIES:
        assert listed[key]["closed"], key
        ready = _ready(item)
        ready["evidence_class"] = key
        gate = next(g for g in _bench.gates(ready) if g["name"] == "the reference retrieves it")
        assert not gate["ok"], (key, gate)
    assert not listed["hl-transactions"]["closed"]


def test_a_download_is_named_with_its_instant_once_and_still_resolves():
    """A download's reference IS the instant it was pulled, and the filed name leads with the
    date and time — so the time is written once, and the row citing the document must still
    find it under that name."""
    from portfusion.desk.intake import filing
    from portfusion.record import rules as D
    cases = [
        ("hl-valuation", "HL Account Summary download", "30 Sep 2026 22:35", "Rowe HL ISA",
         "30 Sep 2026 22.35 HL Account Summary download (Rowe HL ISA).csv"),
        ("hl-transactions", "HL Portfolio Summary download", "Capital sub-account, 30 Sep 2026 22:38",
         "Rowe HL ISA",
         "30 Sep 2026 22.38 HL Portfolio Summary download Capital sub-account (Rowe HL ISA).csv"),
        ("ii-valuation", "ii valuation download", "30 Sep 2026 22:41", "Voss ii Trading",
         "30 Sep 2026 22.41 ii valuation download (Voss ii Trading).csv"),
    ]
    for key, authority, reference, account, expected in cases:
        item = {"evidence_class": key, "account": account, "rows": [],
                "evidence": {"dated": "2026-09-30", "authority": authority, "reference": reference}}
        name = filing.archive_name(item, "download.csv")
        assert name == expected, name
        source = D.evidence_source(key, reference=reference, account=account)
        assert D.reference_resolves(source, [name]) is True, (source, name)


# =====================================================================================
# A PAGE LEFT OPEN CANNOT SAVE OVER A READING — the item's revision
# =====================================================================================


def test_every_save_raises_the_revision_and_an_old_item_starts_at_nought(item):
    item.pop("revision", None)                    # an item saved before revisions
    _bench._path(item["id"]).write_text(json.dumps(item), encoding="utf-8")
    assert _bench.save(_bench.get(item["id"]))["revision"] == 1
    assert _bench.save(_bench.get(item["id"]))["revision"] == 2
    with pytest.raises(_bench.Stale):
        _bench.save(_bench.get(item["id"]), drawn=1)


def test_a_page_drawn_before_a_reading_cannot_save_over_it(item):
    """The page draws the item; a session hands in a reading, which adds a row; the page, still
    showing the item without it, removes a row and saves its own copy. That save is refused, the
    reading's row stands, and a save from the item as it now is goes in."""
    from fastapi.testclient import TestClient
    client = TestClient(app.app, base_url="http://127.0.0.1:8765")
    url = f"/api/bench/{item['id']}"
    drawn = client.get(url).json()["item"].get("revision", 0)

    read = _bench.get(item["id"])                 # the session's hand-in, as propose.py saves it
    read["rows"] = [{"table": "sales", "values": {"ticker": "READ"}, "machine": True}]
    _bench.save(read)

    stale = client.put(url, json={"rows": [], "revision": drawn})
    assert stale.status_code == 409
    assert [r["values"].get("ticker") for r in _bench.get(item["id"])["rows"]] == ["READ"]

    now = client.get(url).json()["item"]["revision"]
    assert client.put(url, json={"rows": [], "revision": now}).status_code == 200
    assert _bench.get(item["id"])["rows"] == []


# =====================================================================================
# A SPLIT OR CONSOLIDATION — a trades row of nil cost, derived from its ratio and the holding
# =====================================================================================

def _a_held_share():
    """(account, ticker, held, the day after its last event) for a share the loaded book holds."""
    import datetime as dt
    from portfusion.record import rules as D
    for acct, ticker in dict.fromkeys((t.acct, t.ticker) for t in D.buys):
        if D.KIND_OF_CODE.get(ticker) != "shares":
            continue
        held = (sum(t.qty or 0 for t in D.buys if (t.acct, t.ticker) == (acct, ticker))
                - sum(e.qty or 0 for e in D.sales if (e.acct, e.ticker) == (acct, ticker)))
        days = [d for d in [t.date for t in D.buys if (t.acct, t.ticker) == (acct, ticker)]
                + [e.date for e in D.sales if (e.acct, e.ticker) == (acct, ticker)] if d]
        if held > 0 and days:
            return acct, ticker, held, (dt.date.fromisoformat(max(days)) + dt.timedelta(1)).isoformat()
    pytest.skip("the loaded book holds no share")


def _adjusted(item, old, new):
    acct, ticker, held, day = _a_held_share()
    item["evidence_class"] = GOOD_CLASS
    item["evidence"] = dict(GOOD_EVIDENCE)
    item["rows"] = [{"table": "buys", "adjustment": {"from": old, "to": new},
                     "values": {"account": acct, "ticker": ticker, "date": day}}]
    return held


@pytest.mark.parametrize("old, new", [(2, 1), (1, 3)])
def test_a_split_or_consolidation_is_derived_from_the_holding_and_its_ratio(item, old, new):
    from portfusion.desk.intake import propose
    held = _adjusted(item, old, new)
    row = propose.refresh_derived(item)["rows"][0]
    after = held * new // old
    assert int(row["values"]["qty"]) == after - held and row["values"]["cost"] == "0"
    assert row["values"]["source"].startswith(f"Derived: {old}-to-{new} ")
    assert row["values"]["note"].endswith(f"{held:,} shares became {after:,}."), row["values"]["note"]
    assert row["values"]["trade_id"] and {"qty", "cost", "source", "trade_id"} <= set(row["derived"])
    gates = {g["name"]: g for g in _bench.gates(item)}
    assert gates["rows"]["ok"], gates["rows"]["detail"]
    assert not _bench._why_needed(item, "why_entered"), "a split owes nobody's reason"


def test_a_ratio_or_holding_that_cannot_be_read_stops_the_row(item):
    _adjusted(item, 20, 20)
    assert "ratio" in next(g for g in _bench.gates(item) if g["name"] == "rows")["detail"]
    _adjusted(item, 2, 1)
    item["rows"][0]["values"]["date"] = "1900-01-01"
    assert "held no" in next(g for g in _bench.gates(item) if g["name"] == "rows")["detail"]


def test_a_written_consolidation_moves_the_holding_alone_and_reads_as_an_adjustment(
        item, store_copy, tmp_path, monkeypatch):
    """Through the door to the store: the holding takes the ratio, no money moves, and Trades
    calls the row an Adjustment."""
    from portfusion import engine
    from portfusion.desk.doors import commit as _commit
    from portfusion.desk.intake import propose
    from portfusion.record import rules as D
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    deployed = engine.Book().capital_deployed()
    held = _adjusted(item, 2, 1)
    acct, ticker = item["rows"][0]["values"]["account"], item["rows"][0]["values"]["ticker"]
    proposed = _bench.save(propose.refresh_derived(item))["rows"][0]["values"]["trade_id"]
    out = _commit.commit(item["id"])
    assert out["written"] == {"buys": 1}
    written = out["ids"][proposed]

    now = (sum(t.qty or 0 for t in D.buys if (t.acct, t.ticker) == (acct, ticker))
           - sum(e.qty or 0 for e in D.sales if (e.acct, e.ticker) == (acct, ticker)))
    assert now == held // 2
    b = engine.Book()
    assert b.capital_deployed().equals(deployed), "a consolidation moved money"
    a = b.activity()
    assert a.loc[a["trade_id"] == written, "direction"].tolist() == ["Adjustment"]


def test_a_backdated_row_renumbers_what_follows_and_the_review_says_so_first(
        item, store_copy, tmp_path, monkeypatch):
    """A buy written before others already on file takes its place in date order, every buy after
    it moves up one, and a sale's `closes` follows the leg it named. The Bench's review names the
    moves before the press; the journal and the archived item say what was written."""
    import json
    from portfusion.desk.doors import commit as _commit
    from portfusion.desk.intake import propose
    from portfusion.desk.panels import bench as panel
    from portfusion.record import rules as D, schema
    monkeypatch.setattr(_commit, "ARCHIVE", tmp_path / "archive")
    _adjusted(item, 2, 1)
    day = item["rows"][0]["values"]["date"]
    after = [t.trade_id for t in D.buys if str(t.date) > day]
    if not after:
        pytest.skip("no buy on file is dated after the loaded book's first held share's last event")
    leg_of = {e.sale_id: e.closes for e in D.sales if e.closes}
    _bench.save(propose.refresh_derived(item))
    said = panel.detail(item["id"])["renumbers"]
    assert said and said[0].startswith(f"{after[0]} "), said

    out = _commit.commit(item["id"])
    up = {t: f"T-{int(t[2:]) + 1:03d}" for t in after}
    assert [t.trade_id for t in D.buys] == [f"T-{n:03d}" for n in range(1, len(D.buys) + 1)]
    assert {e.sale_id: e.closes for e in D.sales if e.closes} == {
        s: up.get(leg, leg) for s, leg in leg_of.items()}, "a sale lost the leg it closes"
    written = out["ids"][next(iter(out["ids"]))]
    assert written == f"T-{int(after[0][2:]):03d}", "the new buy took the first moved place"
    replaced = {r[3]: r[4] for r in schema.load("journal") if r[1:3] == ("bench", "replace")}
    assert replaced.get("buys") == len(after), replaced
    if any(leg in up for leg in leg_of.values()):
        assert replaced.get("sales"), "a sale's closes moved and the journal does not say so"
    archived = json.loads((tmp_path / "archive" / f"{item['id']}.json").read_text())
    assert archived["rows"][0]["values"]["trade_id"] == written


def test_a_contract_reopened_in_the_same_item_is_not_retired():
    """THE ITEM'S OWN NEW LEG HOLDS THE CONTRACT OPEN. A sale of its only open leg retires it,
    which is the premise; the same sale beside a fresh trade on that contract retires nothing.
    Retired, its live price would go and the item be refused whole."""
    from portfusion.desk.doors import commit
    from portfusion.record import rules as D
    closed = {e.closes for e in D.sales if e.closes}
    epics = {r[0] for r in D.schema.load("contracts") if r[1]}     # as the door reads them
    legs = {}
    for leg, c in D.LEG_CONTRACT.items():
        if c in epics and leg not in closed:
            legs.setdefault(c, []).append(leg)
    pick = next(((c, ls[0]) for c, ls in legs.items() if len(ls) == 1), None)
    if pick is None:
        pytest.skip("no contract with an epic and one open leg")
    contract, leg = pick
    sale = {"table": "sales", "values": {"closes": leg}}
    assert commit.retired_by([sale]) == [contract], "the premise: the sale closes it"
    reopen = {"table": "buys", "values": {"trade_id": "T-NEWLEG", "contract": contract}}
    assert commit.retired_by([sale, reopen]) == []


def _drawn_js():
    import re
    return re.sub(r"/\*.*?\*/", "", desk_script(), flags=re.S)


def test_a_row_the_owner_edited_is_no_longer_the_machines():
    """A HAND CORRECTION SURVIVES A RE-READ. A re-read replaces the rows a reading put there
    (`machine`), so an edited row sent back still marked would go with the reading it corrects.
    `collect()` clears the mark the moment any field differs from what was drawn."""
    js = _drawn_js()
    assert "const mine = Object.keys(values).some((k) => !untouched(k));" in js
    assert "machine: r.machine && !mine" in js


def test_bench_saves_go_one_at_a_time_and_keep_the_field_being_typed():
    """EVERY CHANGE SAVED AT ONCE: two in flight would race to a spurious 409, and a redraw would
    overwrite a field being typed. Each save waits for the one before; the field in hand is put back
    after the redraw; any refusal is said."""
    js = _drawn_js()
    assert "const run = SAVING.then(() => saveNow(patch));" in js
    assert js.count("keepingTheField(() => drawItem(d))") == 2
    assert '<span class="tag">not saved</span>' in js
    import re
    callers = re.findall(r"\bsaveNow\(", js)
    assert len(callers) == 2, "something saves round the queue"          # its definition, its one call


def test_a_dated_statement_filed_before_is_named_as_filed(monkeypatch):
    """WHETHER A DOCUMENT IS ALREADY FILED IS THE ARCHIVE'S RULE TO SAY: a valuation pulled at an
    instant is filed under a name that writes the instant another way."""
    from portfusion.record import schema
    account = "Rowe HL ISA"
    filed = f"03 Mar 2025 14.05 HL Account Summary download 3 Mar 2025 14-05 ({account}).csv"
    monkeypatch.setattr(schema, "filed_statements", lambda: [filed])
    item = {"evidence_class": "hl-valuation",
            "evidence": {"reference": "3 Mar 2025 14:05"},
            "rows": [{"table": "account-readings", "values": {"account": account}}]}
    said = _bench.already_in_the_record(item)
    assert any("already filed" in s and filed in s for s in said), said
