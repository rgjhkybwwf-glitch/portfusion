"""ACCOUNTS — the book against the broker, cash, and the reading that writes both halves."""
from __future__ import annotations

import datetime as _dt
import pytest
from portfusion import engine as _engine
from portfusion.record import rules as _rules
from portfusion.desk import actions, app, panels, engine
from portfusion.desk.intake import bench as _bench
from portfusion.desk.intake import recorded
from harness import SRC, append_rows, needs, write_rows, desk_script


# =====================================================================================
# ACCOUNTS — the book against the broker, and the two rules that are not the same rule.
# =====================================================================================

def test_the_tie_rule_has_one_implementation():
    """EVERY ROW IS DECIDED BY ONE FUNCTION, ON THE ENGINE — Book.reconciliation_verdict — and
    this pins each branch. A verdict is a classification, so it cannot live in a renderer.

    TWO CHECKS, told apart by the evidence class: an IG reading is held to one band when struck in
    one pass with the marks; a share account's holdings export agreed on units at the door, so no
    value is judged and no band applies.
    """
    from portfusion.record import rules as D
    v = _engine.Book.reconciliation_verdict

    live = v(20000.0, 25.30, "ig-accounts", True, "read in one pass")
    assert live["live"] and live["verdict"] == "within-band"
    assert live["band"] == 20000.0 * D.RECON_LIVE_TOLERANCE_PCT
    assert v(20000.0, 500.0, "ig-accounts", True, "")["verdict"] == "differs"
    apart = v(20000.0, 25.30, "ig-accounts", False, "not one pass")
    assert apart["verdict"] == "struck-apart" and not apart["checkable"]

    for cls in D.HOLDINGS_COLUMNS:
        units = v(50250.00, None, cls)
        assert units["verdict"] == "units-agree" and units["checkable"], cls
        assert units["band"] is None, "a units check has no band: nothing is valued"
    assert v(50250.00, None, "hl-valuation")["rule"] == "units agree with the broker's holdings", \
        "the sentence carries no date: the page heads the reading's day in its own column"
    shot = v(52000.00, None, "not-on-file")
    assert shot["verdict"] == "no-holdings" and not shot["checkable"]

    # AN UNKNOWN KEY IS NOT LIVE AND NOT A PASS: a class the record does not declare buys a row
    # neither the band nor the units verdict.
    unknown = v(20000.0, 25.30, "not-a-class")
    assert not unknown["live"] and not unknown["checkable"]

    # No statement is NOT a pass. Saying "ties" here would be the worst answer available.
    for missing in (None, float("nan")):
        out = v(missing, None, "whenever")
        assert out["verdict"] == "no-statement" and not out["checkable"] and out["ties"] is None


def test_the_accounts_panel_asks_that_function_rather_than_deciding():
    """Every verdict on the panel must equal what the shared rule says for that row."""
    b = _engine.Book()
    rows = {r["account"]: r for r in panels.get("reconcile").data()["rows"]}
    for r in b.reconciliation().itertuples(index=False):
        # THE EVIDENCE CLASS, not the date. A test that calls the shared rule must call it the
        # way the panel does, or it is pinning its own mistake.
        expected = _engine.Book.reconciliation_verdict(r.statement, r.difference, r.evidence,
                                                 r.comparable, r.comparability)
        assert rows[r.account]["verdict"] == expected["verdict"]


@needs("accounts", "account-readings", "buys")
def test_each_reconcile_row_names_the_reading_its_broker_side_rests_on():
    """EACH ROW CARRIES THE DAY ITS BROKER FIGURE WAS READ AND WHAT FROM: the report's two cells,
    from the same engine answer the report asks — and for the SAME reading the row compares, which
    is the half that could quietly drift."""
    b = engine.book()
    rests = b.quarter_evidence(None).set_index("account")
    struck = b.reconciliation().set_index("account")["struck_on"]
    d = panels.get("reconcile").data()
    assert d["rows"], "no account — this asserts nothing"
    for r in d["rows"]:
        e = rests.loc[r["account"]]
        assert str(e["as_of"])[:10] == struck[r["account"]], (
            f"{r['account']}: the document is the reading of {e['as_of']}, the figures are of "
            f"{struck[r['account']]}")
        day = f"{_dt.date.fromisoformat(struck[r['account']]):%-d %b %Y}"
        assert r["last_check"] == f"{e['document']}, {day}", (
            f"{r['account']}: the page says {r['last_check']!r}, and its figures are of {day}")
        assert r["document"] == e["held"], r["document"]


def test_an_account_with_no_broker_figure_is_a_gap_not_a_pass():
    """THREE KINDS OF GAP, and the panel says which: no broker figure at all, a share reading
    that lists no units, and an IG reading not struck in one pass with the marks. None can be
    judged, and each is missing something different, so one "nothing to check against" for all
    three would misdescribe two of them."""
    # ON THE RULE, NOT ON A NAMED ACCOUNT. Which account sits in which gap changes every time a
    # document arrives, so a test naming them goes stale on exactly the event it exists for.
    v = _engine.Book.reconciliation_verdict
    assert v(None, None, "ii-valuation")["verdict"] == "no-statement"
    apart = v(100.0, 1.0, "ig-accounts", False, "the marks are not one pass")
    assert apart["verdict"] == "struck-apart"
    assert apart["rule"] == "the marks are not one pass", "the verdict prints comparability's words"
    assert not apart["checkable"], "a struck-apart row is not a pass"
    # ALL THREE KINDS, ON THE RULE: the loop below reads the book's own gaps, and on a book with
    # none it checks nothing, so each kind says why here whatever the book holds.
    none = v(100.0, 1.0, "ii-statement")
    assert none["verdict"] == "no-holdings" and not none["checkable"], none
    for gap in (v(None, None, "ii-valuation"), apart, none):
        assert len(gap["rule"].split()) >= 4, f"{gap['verdict']} must say why: {gap['rule']!r}"

    d = panels.get("reconcile").data()
    for r in d["gaps"]:
        assert r["verdict"] in ("no-statement", "no-holdings", "struck-apart"), r["verdict"]
        assert len(r["rule"].split()) >= 4, f"{r['verdict']} must say why, and said {r['rule']!r}"
    assert all(r["verdict"] not in ("within-band", "units-agree") for r in d["gaps"])


#: Every column the desk draws, panel by panel. A census, not a target, in the shape
#: test_boundaries.py's `WRITERS` already uses.
#:
#: Why it exists: no content is added without acceptance. `tests/test_figures.py` holds both
#: renderers to `Book.HEADLINE` — but only for headline figures. A table column could be added,
#: removed or reordered with nothing failing anywhere. A new column fails this until somebody
#: writes down what it is.
#:
#: It pins what is SHOWN, not what the engine holds. `Book` may grow a field freely; the
#: decision this guards is the one about putting it in front of a reader.
PANEL_COLUMNS = {
    # WHO OPENS THE HOSTED DESK: readers, each one's devices, the sign-in log, and the key from an
    # account's code to its name, the one place the owner reads both.
    "access": {
        "CODE_COLUMNS": ("code", "label", "account"),
        "DEVICE_COLUMNS": ("device", "enrolled", "last_used"),
        "READER_COLUMNS": ("who", "level", "since", "devices", "last_signed_in", "now"),
        "SIGNIN_COLUMNS": ("at", "result", "who", "device", "address", "detail"),
    },
    # THE BENCH'S FORMS: every column of the five tables it writes, each headed in the desk's words
    # rather than its store name. Derived from the schema, so a new column joins.
    "bench": {
        "FORM_COLUMNS": ("trade_id", "date", "source", "account", "ticker", "cur", "qty",
                         "stake", "cost", "level_points", "broker_ref", "note", "contract",
                         "traded_price", "rate", "sale_id", "proceeds", "realisation_id",
                         "closes", "category", "detail", "amount", "currency", "local_amount",
                         "as_of", "cash", "evidence", "reference", "company", "held_as",
                         "symbol", "quote_unit",
                         "points_per_unit", "shares_per_unit",
                         "sector", "region", "epic", "funding"),
        "REVIEW_COLUMNS": ("retires", "renumbers"),
    },
    "reconcile": {
        # WHAT THE BROKER'S SIDE RESTS ON: the report's two columns, last.
        "COLUMNS": ("account", "book", "broker", "difference", "verdict", "last_check",
                    "document"),
    },
    "price-refresh": {
        "GRID_COLUMNS": ("mark_key", "was", "was_at", "new", "new_at", "source", "origin", "take"),
        "PRICE_COLUMNS": ("mark_key", "price", "currency", "as_of", "age_days", "stale", "contract"),
    },
    "what-changed": {
        "COLUMNS": (
            "mark_key", "company", "price_move_pct", "price_effect", "fx_effect", "transacted",
            "change", "value_to", "priced_from", "priced_at"
        ),
        "JOURNAL_COLUMNS": ("at", "route", "op", "table", "rows", "ref", "detail"),
        # A SPREAD BET HAS NO FX PART: the notional block drops From FX.
        "NOTIONAL_COLUMNS": (
            "mark_key", "company", "price_move_pct", "price_effect", "transacted", "change",
            "value_to", "priced_from", "priced_at"
        ),
    },
    "performance": {
        # WHAT A QUARTER-END NAV RESTS ON, under each account row's detail.
        "DETAIL_COLUMNS": ("source", "quality"),
        # NO START OR END DATE, as the report has none; the ACCOUNT a column, leading.
        "COLUMNS": (
            "account", "quarter", "opening_nav", "capital_deployed", "return_income",
            "closing_nav", "gain", "return"
        ),
        "YEAR_COLUMNS": ("account", "opening_nav", "capital_deployed", "return_income",
                         "nav", "capital_growth", "ytd", "capital_employed", "exposure",
                         "held_as"),
    },
    "holdings": {
        "HELD_COLUMNS": ("qty", "stake"),
        "COLUMNS": (
            "ticker", "company", "held_as", "accounts", "currency", "entry_price",
            "price", "priced_at", "cost", "value", "unrealised", "unrealised_pct", "weight",
            "opened", "days_held"
        ),
        "MARK_COLUMNS": ("date", "mark_key", "price", "currency", "source"),
        "REASON_COLUMNS": ("whys", "research_notes"),
        "DETAIL_COLUMNS": ("why_entered", "why_exited", "research_notes", "marks"),
    },
    "round-trips": {
        "COLUMNS": (
            "ticker", "company", "held_as", "account", "currency", "qty", "entry_price",
            "exit_price", "cost",
            "proceeds", "realised", "realised_pct", "opened", "closed", "days_held", "fully_closed"
        ),
        "REASON_COLUMNS": ("whys", "research_notes"),
        "DETAIL_COLUMNS": ("why_entered", "why_exited", "research_notes", "note"),
        # A SPREAD BET IN ITS OWN TERMS: its stake per point for a quantity, and its entry and
        # exit as levels in points, as Trades reads one.
        "BET_COLUMNS": ("stake", "entry_level_points", "exit_level_points"),
        # A COMPANY LIFE: Round Trips' second view.
        "LIFE_COLUMNS": ("company", "held_as", "accounts", "state", "opened", "closed",
                         "days_held", "realised", "unrealised", "dividends", "funding_interest",
                         "life_gain", "life_pct", "qty", "life_cost_per_share", "price", "currency"),
        "LIFE_DETAIL_COLUMNS": ("realisations", "lines"),
    },
    "accounts": {
        "REGISTER_COLUMNS": ("code", "account", "holder", "broker_firm", "number", "feed_key",
                             "record_begins", "cash", "cash_read"),
        "MOVEMENT_COLUMNS": ("date", "account", "amount", "source", "detail"),
        "SUMMARY_COLUMNS": ("account", "total"),
        "INCOME_COLUMNS": ("date", "category", "detail", "currency", "local_amount", "rate_date",
                           "amount", "source", "note"),
    },
    "trades": {
        "COLUMNS": ("ticker", "direction", "account", "currency", "qty", "traded_price",
                    "value", "date"),
        "BET_COLUMNS": ("stake", "level_points"),
        # A BET LEG'S CONTRACT AND ITS FUNDING: where the funding-interest rows rest.
        # A FOREIGN DEAL'S RATE AND WHOSE IT IS. A SALE'S OWN ID UNDER ITS OWN NAME.
        "DETAIL_COLUMNS": ("why_entered", "why_exited", "note", "source", "broker_ref",
                           "trade_id", "sale_id", "realisation_id", "contract", "funding",
                           "fx_at_trade", "fx_from"),
    },
}


def test_the_desk_draws_only_the_columns_that_were_agreed():
    """A panel that has grown or lost a column fails until the census is updated.

    Read the diff before editing the number, the same instruction `_EXPECTED_FLAGS` carries:
    a column appearing here that nobody chose is the finding, and a column disappearing may be
    a figure that quietly stopped being shown.

    Derived from the panels, so it cannot be satisfied by editing this file alone — the tuple
    on the left is read off the module, and a panel that renames its constant fails too.
    """
    from portfusion.desk import panels as _panels

    live = {}
    for m in _panels.all_panels():
        cols = {n: tuple(getattr(m, n)) for n in sorted(dir(m)) if n.endswith("COLUMNS")}
        if cols:
            live[m.NAME] = cols

    assert live == PANEL_COLUMNS, (
        "the desk's columns are not the ones on file. Panels that differ: "
        f"{sorted(set(live) ^ set(PANEL_COLUMNS)) or 'none added or removed'}; "
        f"changed: {sorted(k for k in set(live) & set(PANEL_COLUMNS) if live[k] != PANEL_COLUMNS[k])}. "
        "A column is content a reader is shown — find which moved before editing this census.")


def test_the_gap_list_quotes_the_engines_rule_rather_than_composing_one():
    """THE GAP LIST DRAWS EACH ROW'S OWN `rule`, never one sentence over every unjudgeable row:
    "no broker figure at all" is true of `no-statement` and false of the others. A struck-apart
    row has a tag of its own.

    The guard is on the FILE and not only on the data — a panel handing over a correct field
    proves nothing about what gets drawn.
    """
    import re
    js = desk_script()
    # Comments are stripped before the ban, because the ban is on what RENDERS.
    drawn = re.sub(r"/\*.*?\*/", "", js, flags=re.S)

    assert "esc(r.rule)" in drawn, \
        "the gap list no longer renders the engine's own rule for each row"
    assert "no broker figure at all" not in drawn, (
        "app.js hard-codes why a row cannot be judged; there are three gaps, and the "
        "engine's `rule` says which.")
    from portfusion.desk.panels import reconcile
    assert reconcile.VERDICT_TAG["struck-apart"] == "gap" and "esc(r.tag)" in drawn, \
        "a struck-apart row has no tag of its own and falls through to the default"


def test_the_ig_actions_are_reads_that_leave_the_machine():
    """Both call feeds/ig.py, which cannot deal — an allowlist refuses every dealing endpoint
    before a request is built. Nothing on the desk relaxes that.

    AND BOTH SAY THEY REACH OUT. They read nothing INTO the record and they do open a
    connection to a broker, which is exactly the pair of facts the two axes were built to hold
    apart: `writes` answers what may change here, `reaches` answers what leaves.

    Asserted here as well as in the pin because this is the test about THESE actions: the pin
    would still pass if one of them lost its declaration and something else gained one.
    """
    # `refresh-fetch-all` takes the contract levels and the equity in ONE pass (the reaching pin
    # says why), then TradingView.
    for name in ("refresh-fetch-all", "ig-events"):
        a = actions.get(name)
        assert a.writes is None
        assert a.reaches == "network", f"{name} calls IG's API and does not say so"
        assert a.gate, f"{name} reaches out and names nothing the human must do first"


def test_the_route_runs_a_writing_action_the_registry_declares(monkeypatch):
    """The REGISTRY is the gate, not the route: a declared writing action runs, with nothing
    standing here but test_every_writing_action_is_pinned."""
    ran = []
    immediate = actions.Action(name="test-now", label="Apply marks", panel="accounts",
                               run=lambda: ran.append(1), writes="marks",
                               gate="tick-each-line")
    monkeypatch.setitem(actions._REGISTRY, "test-now", immediate)
    assert app.run_action("test-now", {})["ran"] is True
    assert ran == [1]


def test_the_registry_answers_without_being_primed():
    """An action registers when its panel is imported, so asking it before any panel loads would
    give the honest-but-useless answer "nothing" — and the whole claim about actions.py is that it
    is the ONE place with the answer. A registry the caller has to prime is not that."""
    import subprocess
    import sys as _sys
    r = subprocess.run(
        [_sys.executable, "-c",
         "from portfusion.desk import actions; print(sorted(a.name for a in actions.all_actions()))"],
        cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "refresh-fetch-all" in r.stdout and "ig-events" in r.stdout, r.stdout

    # IN A SUBPROCESS, not by reloading the module. A reload empties the registry while the
    # panel modules stay in sys.modules, so they never re-register — which tests an artificial
    # situation and fails for a reason that has nothing to do with the claim. The claim is
    # about a FRESH PROCESS, so this starts one.


# =====================================================================================
# CASH REACHES THE CELL
#
# "Cash now" on the Accounts tab derives from the newest dated reading in
# store/cash-readings.csv, and this is the route that writes one. An ii transactions
# download carries a Running Balance whose top row is dated and sourced; without a route from
# that row to that cell, the cell could not move without a hand edit.
#
# A CASH OBSERVATION IS NOT AN EVENT. The other four bench tables record things that
# happened once. This records a MEASUREMENT of a balance at a date, and the same account
# gets another one next month. It is on the bench because it ARRIVES the same way.
# =====================================================================================

def _shares_register():
    """(account, number) for the register's shares accounts, in register order — the loaded
    book's own, so these tests commit against whatever book the suite is pointed at."""
    from portfusion.record import schema
    h = schema.TABLES["accounts"].header
    return [(r[h.index("account")], r[h.index("number")])
            for r in schema.load("accounts") if r[h.index("held_as")] == "shares"]


def _book_units(account, date="2026-09-30"):
    from portfusion.engine import Book
    held = Book().holdings_at(date, account)
    return {r.ticker: float(r.qty) for r in held.itertuples(index=False)}


GOOD_CASH = {
    "account": None, "as_of": "2026-09-02", "cash": "140.00",
    "evidence": "ii-transactions",
    "reference": "TESTCASHREF1",
}


def _good_cash(**over):
    """GOOD_CASH on the loaded register's first shares account."""
    row = dict(GOOD_CASH, account=_shares_register()[0][0])
    row.update(over)
    return row


def _after_the_newest_reading(account) -> str:
    """The day after that account's newest reading on file. A test that commits a reading, or
    asks whether it is a duplicate, dates it here: a fixed date would collide with — or be
    outranked by — a real reading as the record grows, and go red on a correct record."""
    from portfusion.record import schema
    held = [r[1] for r in schema.load("cash-readings") if r[0] == account]
    return (max(held) + _dt.timedelta(days=1)).isoformat()


def test_the_bench_can_produce_a_cash_observation():
    """Its form is GENERATED from the schema, so the columns appear by existing."""
    names = [f["name"] for f in _bench.form_for("cash-readings")]
    assert names == ["account", "as_of", "cash", "evidence", "reference"]
    assert "cash-readings" in _bench.TABLES
    assert tuple(recorded.SIGNATURE) == _bench.TABLES, "a Bench table the duplicate check cannot see"


def test_the_evidence_class_is_a_closed_vocabulary_on_the_form():
    """A reading citing a class the record does not know has no stated authority and no
    reference shape — limbs 2 and 3. A free text box here would let the bench build a row
    that test_record.py then rejects, which is a defect discovered too late."""
    ev = next(f for f in _bench.form_for("cash-readings") if f["name"] == "evidence")
    assert ev["closed"] is True
    assert "ii-transactions" in ev["choices"] and "not-on-file" in ev["choices"]
    assert _bench.validate_row("cash-readings", dict(GOOD_CASH, evidence="invented"))


@needs("accounts", "account-readings", "buys")
def test_a_second_reading_for_one_account_on_one_date_is_a_duplicate():
    """ONE ACCOUNT HAS ONE CASH BALANCE ON A DATE. A second row for that pair is a
    re-reading, not a second fact.

    The signature is (account, as_of) and deliberately EXCLUDES the amount. For an event the
    amount identifies it — two £50 dividends on one day are two dividends. For a balance it
    does not, and including it would let a MISTYPED figure in as a "different" observation,
    which is the exact case this gate exists to catch. The figure below is wrong on purpose.
    """
    from portfusion.record import schema
    on_file = schema.load("cash-readings")
    assert on_file, "no cash reading on file — nothing to collide with"
    account, as_of = on_file[0][0], on_file[0][1].isoformat()
    held = {"account": account, "as_of": as_of, "cash": "999.99",
            "evidence": "ii-transactions", "reference": "x", "source": "y"}
    assert recorded.matching_row("cash-readings", held) == account
    fresh = _good_cash(as_of=_after_the_newest_reading(_shares_register()[0][0]))
    assert recorded.matching_row("cash-readings", fresh) is None, \
        "a reading on a NEW date is not a duplicate"


@needs("accounts", "account-readings", "buys")
def test_a_two_column_signature_is_required_in_full():
    """A SIGNATURE IS REQUIRED IN FULL: every column that identifies the thing. A minimum of three
    would silently disable cash-readings' two-column gate.

    Adding `cash` to reach three would be the wrong fix — see the test above.
    """
    assert len(recorded.SIGNATURE["cash-readings"]) == 2
    assert recorded.matching_row("cash-readings",
                               {"account": _shares_register()[0][0], "cash": "1"}) is None, \
        "without a date it cannot identify anything, and must not guess"


@needs("accounts", "account-readings", "buys")
def test_a_cash_observation_commits_and_reads_back(item, store_copy, tmp_path, monkeypatch):
    """END TO END, against a COPY of the store — never the record itself."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit
    was = len(schema.load("cash-readings"))
    good = _good_cash()
    after = _after_the_newest_reading(good["account"])

    # NOT a real download's reference — one really in the book would fire the evidence-reuse
    # gate, which correctly refuses to let the suite assert against evidence the record
    # already holds. Same reason GOOD_TRADE carries TESTREF1.
    item["evidence"] = {"dated": after, "authority": "ii transactions download",
                        "reference": "TESTCASHREF1"}
    item["rows"] = [{"table": "cash-readings", "values": dict(good, as_of=after)}]
    result = _commit.commit(_bench.save(item)["id"])

    assert result["written"] == {"cash-readings": 1}
    rows = schema.load("cash-readings")
    assert len(rows) == was + 1
    # WHERE ITS DATE PUTS IT, which on a book with later readings is not the end.
    written = [r[:3] for r in rows if (r[0], r[1].isoformat()) == (good["account"], after)]
    assert written == [(good["account"], _dt.date.fromisoformat(after), 140.00)], written


@needs("accounts", "account-readings", "buys")
def test_the_committed_reading_becomes_the_newest_cash(store_copy, item, tmp_path, monkeypatch):
    """THE WHOLE POINT: the cell moves. `rules.cash_latest()` reads the NEWEST dated reading
    per account, so committing a reading dated after every one on file must displace them —
    without anybody editing record/rules.py."""
    from portfusion.record import schema
    from portfusion.desk.doors import commit as _commit

    good = _good_cash()
    after = _after_the_newest_reading(good["account"])

    item["evidence"] = {"dated": after, "authority": "ii transactions download",
                        "reference": "TESTCASHREF1"}
    item["rows"] = [{"table": "cash-readings", "values": dict(good, as_of=after)}]
    _commit.commit(_bench.save(item)["id"])

    newest = {}
    for r in schema.load("cash-readings"):
        if r[0] not in newest or r[1] > newest[r[0]][1]:
            newest[r[0]] = r
    assert newest[good["account"]][2] == 140.00
    assert newest[good["account"]][1].isoformat() == after


def test_the_panels_share_one_shaping_helper():
    """ONE SHAPING MODULE, desk/panels/_shape.py.

    Copies drift: a fix reaches one and not the others, and one name returns two types.

    A count of copies would go stale. This asserts the property instead: no panel defines a
    shaping helper of its own, because there is one and it is importable. The helpers are what
    `_shape.py` defines, read from it, so a new one is held by existing and a copy is caught
    under its own name or a private one; a panel's `_rows` that calls `_shape.rows` builds on it.
    """
    import ast
    shape = SRC / "desk" / "panels" / "_shape.py"
    owned = {n.name for n in ast.parse(shape.read_text()).body if isinstance(n, ast.FunctionDef)}

    def own(src):
        return sorted({n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)
                       and n.name.lstrip("_") in owned
                       and f"_shape.{n.name.lstrip('_')}(" not in ast.unparse(n)})
    assert own("def plain(v):\n    return v\ndef _iso(v):\n    return v\n") == ["_iso", "plain"]
    offenders = {path.name: own(path.read_text()) for path in sorted(shape.parent.glob("*.py"))
                 if path != shape and own(path.read_text())}
    assert not offenders, (
        f"these panels define their own shaping helpers: {offenders}. "
        f"desk/panels/_shape.py has {sorted(owned)} — import them.")


def test_the_shared_shaping_survives_a_column_named_for_a_keyword():
    """A column named `return`, pinned by behaviour rather than by reading the source. itertuples()
    renames `return`; to_dict("records") does not."""
    import pandas as pd
    from portfusion.desk.panels import _shape
    frame = pd.DataFrame({"quarter_end": [pd.Timestamp("2026-06-30")], "return": [0.0721]})
    row = _shape.rows(frame, ["quarter_end", "return"], dates=("quarter_end",))[0]
    assert row["return"] == pytest.approx(0.0721), \
        "the return column came back None — the namedtuple rename is back"
    assert row["quarter_end"] == "2026-06-30"


def test_the_shared_shaping_is_tolerant_where_a_panel_needs_it():
    """A column the frame does not carry, and a NaN date, are both ordinary here — a panel
    rendering a subset of a wider frame should not raise."""
    import pandas as pd
    from portfusion.desk.panels import _shape
    frame = pd.DataFrame({"a": [1.0, float("nan")], "date": [pd.NaT, pd.Timestamp("2026-01-02")]})
    out = _shape.rows(frame, ["a", "date", "absent"], dates=("date",))
    assert out[0] == {"a": 1.0, "date": None, "absent": None}
    assert out[1] == {"a": None, "date": "2026-01-02", "absent": None}


# =====================================================================================
# THE PRICE REFRESH'S LABELS
# =====================================================================================


@needs("accounts", "account-readings", "buys")
def test_the_bay_says_what_it_can_replace_rather_than_what_is_due():
    """THE BAY LISTS WHAT IT CAN REPLACE, and nothing calls those lines "due".

    The LIST is the whole set, never filtered by age: docs/prices.md's rule is that the book is
    refreshed whole or not at all. The step says the marks' age against the limit, as the
    Dashboard does, and a line past the limit says so in its own row.
    """
    from portfusion import engine
    js = desk_script()
    assert "price(s) due" not in js, "step 3 calls the replaceable lines due again"
    assert "limit ${d.age_limit} days" in js, "step 3 does not say what the threshold is"

    can = engine.Book().marks_replaceable()
    assert can["age_limit"] == _rules.PRICE_AGE_LIMIT
    assert can["replaceable"], "nothing is replaceable — this asserts nothing"
    for row in can["replaceable"]:
        assert row["stale"] == (row["age_days"] > can["age_limit"]), \
            f"{row['ticker']}: stale and its age disagree"


def test_the_age_limit_lives_where_the_classification_does(build_sources, repo_root):
    """A limit kept in a renderer is one `book.marks_replaceable()` — which decides whether a
    mark is old — cannot read, because `engine/` imports the record, `house` and pandas and
    nothing else; the engine would have no threshold and call everything due. The limits are the
    record's, and neither renderer — the report nor the desk — holds a name of its own for
    either."""
    import ast
    renderers = [*build_sources, *sorted((SRC / "desk").rglob("*.py"))]
    copies = [f"{f.relative_to(repo_root)}:{n.lineno}" for f in renderers
              for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
              if isinstance(n, (ast.Assign, ast.AnnAssign))
              and any(getattr(t, "id", None) in ("PRICE_AGE_LIMIT", "PRICE_SPREAD_LIMIT")
                      for t in getattr(n, "targets", [getattr(n, "target", None)]))]
    assert not copies, f"a renderer holds its own copy of a price limit: {copies}"


# =====================================================================================
# A SHARE ACCOUNT'S READING — off one filed broker document, through the same door
# =====================================================================================

#: AN INVENTED HOLDINGS EXPORT, filed, because the door opens the document to count its units.
#: These stubs list it, so the refusal branches run on any book.


_HL_REF = "30 Sep 2026 17:00"


def _hl_name(account):
    return f"30 Sep 2026 17.00 HL Account Summary download 30 Sep 2026 17-00 ({account}).csv"


def _hl_export(account, number, units):
    """An INVENTED HL Account Summary: the loaded book's own units under invented money
    figures, so the door is exercised end to end on any book and rests on no real
    document. The shape mirrors HL's own download, fingerprints included."""
    rows = [f'"{t}","{t} holding","{q:g}","100.00","0.00","0.00","0.00","0.00"'
            for t, q in sorted(units.items())]
    return "\n".join([
        "HL Stocks & Shares ISA, , , ,",
        "Client Name:,An Invented Holder, , ,",
        f"Client Number:, {number}, , ,",
        "Spreadsheet created at,30-09-2026 17:00, , ,",
        "",
        'Stock value:,"50,000.00", , ,',
        'Total cash:,"250.00", , ,',
        'Amount available to invest:,"0.00", , ,',
        'Total value:,"50,250.00", , ,',
        "",
        "Code,Stock,Units held,Price (pence),Value (\u00a3),Cost (\u00a3),"
        "Gain/loss (\u00a3),Gain/loss (%),",
    ] + rows) + "\n"


def _ensure_prior_reading(store_copy, account):
    """The observations door REPLACES a reading and refuses an account that has none — a
    new account is a decision. The real register's accounts all have one; a book whose
    account has not been observed yet gets a minimal prior row in the COPY."""
    from portfusion.record import schema, rules
    if any(r[0] == account for r in schema.load("account-readings")):
        return
    with (store_copy / "account-readings.csv").open("a", encoding="utf-8",
                                                        newline="") as fh:
        fh.write(f"{account},2026-09-28,,1.00,,,,,,not-on-file,"
                 f"a prior reading for the replace door\n")
    rules.reload_store()


def _clear_day(store_copy, account, day="2026-09-30"):
    """Clear any banked statement and any cash reading of `account` on `day` in the COPY, so
    what a reading writes there is its own."""
    from portfusion.record import rules
    for name in ("account-statements.csv", "cash-readings.csv"):
        path, pref = store_copy / name, f"{account},{day},".encode()
        path.write_bytes(b"".join(line for line in path.read_bytes().splitlines(keepends=True)
                                  if not line.startswith(pref)))
    rules.reload_store()


def _share_filed(store_copy):
    """File the invented export in the COPIED archive and clear any banked row and cash at its
    key, so what the write puts there is its own. Returns the account it reads for."""
    from portfusion.record import schema
    account, number = _shares_register()[0]
    _ensure_prior_reading(store_copy, account)
    schema.statements().mkdir(parents=True, exist_ok=True)
    (schema.statements() / _hl_name(account)).write_text(
        _hl_export(account, number, _book_units(account)), encoding="utf-8")
    _clear_day(store_copy, account)
    return account


def _share(**over):
    row = {"account": _shares_register()[0][0], "as_of": "2026-09-30", "at": "",
           "positions": 50000.00, "cash": 250.00, "total": 50250.00,
           "evidence": "hl-valuation", "reference": _HL_REF, "note": ""}
    row.update(over)
    return row


def _filed(monkeypatch, names):
    from portfusion.record import schema
    monkeypatch.setattr(schema, "filed_statements", lambda: list(names))


def _write(readings):
    """The readings door, as the Bench's commit calls it: refused whole or written whole."""
    from portfusion.record import rules as D
    from portfusion.desk.doors import envelope, observations
    try:
        with envelope.atomic(*observations.paths()):
            return {"ok": True, **observations.write(readings=readings)}
    except observations.Refused as e:
        D.reload_store()
        return {"ok": False, "refused": str(e)}



@needs("accounts", "account-readings", "buys")
def test_a_failed_reading_takes_back_the_banking_too(store_copy, monkeypatch):
    """THE HISTORY IS INSIDE THE ENVELOPE, as on the marks door, so a reading that fails after the
    bank moves no account-statements.csv. The outgoing reading is unbanked here, so the bank has
    work, and the write fails at its journal line, after the bank."""
    from portfusion.history import accounts as AH
    from portfusion.desk.doors import envelope, observations
    _share_filed(store_copy)
    live = {(m["as_of"], m["account"]) for m in AH.live_observations()}
    AH.save([r for r in AH.load() if (r["as_of"], r["account"]) not in live])
    history = store_copy / AH.CSV_NAME
    before = history.read_bytes()

    def fails(*a, **k):
        raise RuntimeError("the journal could not be written")
    monkeypatch.setattr(envelope, "journal", fails)
    # THE DOOR ITSELF, not `_write()`: that wraps it in an envelope of its own over
    # `observations.paths()`, which would restore the history whatever the door holds.
    with pytest.raises(RuntimeError):
        observations.write(readings=[_share()])

    assert history.read_bytes() == before, "a failed reading banked the outgoing readings"


def test_a_field_the_new_reading_does_not_carry_is_blank_not_the_old_value():
    """A READING IS WHOLE: a field it does not carry is blank, never the last read's."""
    from portfusion.record import schema
    from portfusion.desk.doors import observations
    header = schema.TABLES[observations.TABLE].header
    old = {"account": "X", "as_of": "2026-09-01", "at": "2026-09-01T09:00Z", "positions": "10",
           "funds": "", "running_pl": "", "equity": "",
           "deposit": "", "available": "7", "evidence": "hl-valuation", "reference": "old"}
    reading = {"account": "X", "as_of": "2026-09-30", "positions": 12.0,
               "evidence": "ii-valuation", "reference": "new", "available": None}
    merged = dict(zip(header, observations._merged([old[c] for c in header], reading)))
    assert merged["account"] == "X"
    assert (merged["as_of"], merged["positions"], merged["reference"]) == ("2026-09-30", "12.00", "new")
    assert [merged[c] for c in ("at", "available")] == [""] * 2, merged


@needs("accounts", "account-readings", "buys")
def test_a_share_reading_is_written_and_banked_with_its_account(store_copy, monkeypatch):
    """One write files the reading and banks it for the report, and the banked row names the
    account, because two ii valuations filed on one day differ in nothing else. ITS CASH IS A CASH
    READING of its own day, in the same write, and the journal says so. THE DOOR ASKS ITS OWN
    HISTORY ALONE: a price or rate history that cannot be read is the marks door's, and blocks no
    reading."""
    from portfusion.record import schema
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH
    account = _share_filed(store_copy)

    def unreadable():
        raise RuntimeError("a price or rate history that cannot be read")
    monkeypatch.setattr(PH, "check", unreadable)
    monkeypatch.setattr(FX, "check", unreadable)

    out = _write([_share()])

    assert out["ok"] is True, out.get("refused")
    h = schema.TABLES["account-readings"].header
    read = next(r for r in schema.load("account-readings") if r[0] == account)
    assert read[h.index("positions")] == 50000.00, read
    assert [(c.as_of.isoformat(), c.cash, c.evidence, c.reference) for c in _rules.cash_readings
            if c.account == account and c.as_of.isoformat() == "2026-09-30"] == [
        ("2026-09-30", 250.00, "hl-valuation", _HL_REF)]
    assert out["cash"] == 1 and ("marks", "append", "cash-readings") in {
        tuple(r[1:4]) for r in schema.load("journal")}
    from portfusion.history import accounts as AH
    banked = [r for r in AH.load() if r["account"] == account and r["as_of"] == "2026-09-30"]
    assert banked and f"({account})" in banked[0]["source"], banked


@needs("accounts", "account-readings", "buys")
def test_a_readings_cash_that_disagrees_with_its_days_cash_reading_is_refused(store_copy):
    """Two documents of one day stating two cash figures: one of them is wrong, and the door does
    not choose. Refused whole, at the Bench's gate as at the write, and nothing moves."""
    from portfusion.desk.doors import observations
    account = _share_filed(store_copy)
    write_rows("cash-readings", {"account": account, "as_of": "2026-09-30", "cash": "999.00",
                                 "evidence": "not-on-file", "reference": "another document's cash"})
    _rules.reload_store()
    before = {p: p.read_bytes() for p in observations.paths() if p.is_file()}

    out = _write([_share()])

    assert out["ok"] is False and "does not choose" in out["refused"], out
    assert all(p.read_bytes() == b for p, b in before.items()), "a refused write moved a file"


@needs("accounts", "account-readings", "buys")
def test_one_write_reading_a_day_twice_files_its_cash_once(store_copy):
    """The same account and day twice in one write is one cash reading, not two."""
    account = _share_filed(store_copy)
    out = _write([_share(), _share()])
    assert out["ok"] is True and out["cash"] == 1, out
    assert sum(1 for c in _rules.cash_readings
               if (c.account, c.as_of.isoformat()) == (account, "2026-09-30")) == 1


@needs("accounts", "account-readings", "buys")
def test_a_reading_writes_a_crlf_table_back_in_crlf(store_copy):
    """The readings door writes account-readings.csv back in the ending it found."""
    from desk_support import all_crlf, to_crlf
    _share_filed(store_copy)
    to_crlf("account-readings")
    out = _write([_share()])
    assert out["ok"] is True, out.get("refused")
    assert all_crlf("account-readings"), "the readings door wrote a CRLF table back as LF"


@needs("accounts", "account-readings", "buys")
def test_a_share_reading_whose_units_differ_from_the_book_is_refused_by_name(store_copy,
                                                                            monkeypatch):
    """A share account is checked on units. A contract note brings every trade, so a difference
    is what none carries — a reinvested dividend, a corporate action, a wrong quantity — and the
    door names each holding rather than writing a reading over it."""
    from portfusion.desk.doors import observations
    from portfusion.desk.intake import read_rows
    account = _share_filed(store_copy)
    units = _book_units(account)
    pick = sorted(units)[0]
    real = read_rows.holdings
    monkeypatch.setattr(read_rows, "holdings",
                        lambda text, key: {**real(text, key), pick: 51000.0})
    before = {p: p.read_bytes() for p in observations.paths() if p.is_file()}

    out = _write([_share()])

    assert out["ok"] is False and \
        f"{pick} book {units[pick]:,.0f}, broker 51,000" in out["refused"], out
    assert all(p.read_bytes() == b for p, b in before.items()), "a refused write moved a file"


@needs("accounts", "account-readings", "buys")
def test_a_share_reading_needs_no_pull_time(store_copy):
    """Units are what is checked, and a close does not move them, so the time the document was
    pulled decides nothing and is not asked for."""
    _share_filed(store_copy)
    out = _write([_share(at="")])
    assert out["ok"] is True, out.get("refused")


@needs("accounts", "account-readings", "buys")
def test_a_share_reading_that_does_not_add_up_is_refused_and_writes_nothing(store_copy,
                                                                            monkeypatch):
    """Stock plus cash is the total on the document, so a reading where it is not has one
    figure that was not read off it."""
    from portfusion.desk.doors import observations
    _filed(monkeypatch, [_hl_name(_shares_register()[0][0])])
    before = {p: p.read_bytes() for p in observations.paths() if p.is_file()}

    out = _write([_share(total=110501.00)])

    assert out["ok"] is False and "not the total £110,501.00" in out["refused"], out
    assert all(p.read_bytes() == b for p, b in before.items()), "a refused write moved a file"


@needs("accounts", "account-readings", "buys")
def test_a_share_reading_whose_document_is_not_filed_is_refused(store_copy, monkeypatch):
    """Refused at the door: a baseline citing a document nobody filed is a figure nothing
    retrieves. An IG statement of the same day is not the HL valuation."""
    _filed(monkeypatch, ["24 Sep 2026 IG statement (Voss IG Spread bet).pdf"])

    out = _write([_share()])

    assert out["ok"] is False and "filed on the Bench" in out["refused"], out


@needs("accounts", "account-readings", "buys")
def test_a_share_baseline_rests_only_on_the_brokers_own_holdings_document(store_copy,
                                                                          monkeypatch):
    """Not the totals line, which restates the valuation; not a closed class."""
    _filed(monkeypatch, [_hl_name(_shares_register()[0][0]),
                         "24 Sep 2026 22.36 HL Portfolio Summary totals download "
                         f"({_shares_register()[0][0]}).csv"])
    for key, why in (("hl-account-totals", "cannot rest on it"),
                     ("not-on-file", "NOTHING retrieves")):
        out = _write([_share(evidence=key)])
        assert out["ok"] is False and why in out["refused"], (key, out)




_II_REF = "30 Sep 2026 14:05"


def _ii_account():
    """The register's second shares account — the ii-export tests' subject, so the two
    document routes exercise two different accounts."""
    shares = _shares_register()
    return shares[1][0] if len(shares) > 1 else shares[0][0]


def _ii_name(account):
    return f"30 Sep 2026 14.05 ii valuation download ({account}).csv"


def _ii_export(account):
    """An INVENTED ii holdings export: units are the loaded book's own, each holding's
    pound value invented so the stock figure reads 40,000.00 — and no cash at all,
    which is ii's own shape and the point of these tests."""
    units = sorted(_book_units(account).items())
    head = ("Symbol,Name,Qty,Price,Day Gain/Loss,Day Gain/Loss %,Market Value \u00a3,"
            "Market Value,Book Cost,Gain/Loss,Gain/Loss %,Average Price")
    rows = []
    for n, (t, q) in enumerate(units):
        value = "\u00a340,000.00" if n == 0 else "\u00a30.00"
        rows.append(f'{t},{t} holding,{q:g},\u00a31.00,\u00a30.00,0.00%,"{value}",'
                    f'"{value}","\u00a30.00","\u00a30.00",0.00%,\u00a31.00')
    return head + "\n" + "\n".join(rows) + "\n"


def _ii_filed(store_copy):
    """File the invented ii export in the COPIED archive, dated 1 Oct so its reference
    matches ONE document even beside the archive's own 30 Sep exports; returns its account."""
    from portfusion.record import schema
    account = _ii_account()
    schema.statements().mkdir(parents=True, exist_ok=True)
    # The archive convention zero-pads the day — archive_reference() does too, and an
    # unpadded name matches nothing.
    (schema.statements() / f"01 Oct 2026 08.31 ii valuation download ({account}).csv").write_text(
        _ii_export(account), encoding="utf-8")
    _ensure_prior_reading(store_copy, account)
    return account


def _ii(**over):
    row = {"account": _ii_account(), "as_of": "2026-09-30", "at": "2026-09-30T14:05Z",
           "positions": 40000.00, "cash": "", "total": "",
           "evidence": "ii-valuation", "reference": _II_REF, "note": ""}
    row.update(over)
    return row


@needs("accounts", "account-readings", "buys")
def test_a_reading_off_a_document_that_states_no_cash_is_its_stock_alone(store_copy):
    """A reading off ii's holdings export is the stock alone, and writes no cash reading
    (`observations.SHARE_CASH`). The reconciliation still shows a total, from the account's cash
    readings."""
    from portfusion.record import schema
    from portfusion.engine import Book
    account = _ii_filed(store_copy)
    cash_before = len(_rules.cash_readings)

    out = _write([_ii(as_of="2026-10-01", at="2026-10-01T07:31Z",
                      reference="1 Oct 2026 08:31")])

    assert out["ok"] is True, out.get("refused")
    header = schema.TABLES["account-readings"].header
    read = next(dict(zip(header, r)) for r in schema.load("account-readings")
                if r[0] == account)
    assert read["positions"] == 40000.00 and out["cash"] == 0, (read, out)
    assert len(_rules.cash_readings) == cash_before, "a reading that states no cash wrote one"
    # CASH DATED AFTER THE READING, and after any on file, is the account's newest cash, a
    # different fact, and moves nothing at the reading.
    _rules.reload_store()
    on_file = _rules.cash_latest().get(account)
    later = max(_dt.date(2026, 10, 1), on_file.as_of if on_file else _dt.date.min)
    later += _dt.timedelta(days=1)
    append_rows(store_copy / "cash-readings.csv",
                [f"{account},{later},9999.99,ii-transactions,a later cash reading"])
    _rules.reload_store()
    held = _rules.cash_latest(on=_dt.date(2026, 10, 1))[account]
    row = Book().reconciliation().set_index("account").loc[account]
    assert (row["cash_at_recon"], row["cash_at_recon_at"]) == (held.cash, held.as_of.isoformat())
    assert row["statement"] == round(40000.00 + held.cash, 2)
    newest = Book().newest_cash().set_index("account").loc[account]
    assert (newest["cash"], newest["as_of"]) == (9999.99, later.isoformat()), newest


@needs("accounts", "account-readings", "buys")
def test_a_cash_figure_on_a_reading_whose_document_states_none_is_refused(store_copy):
    """Refused at the door: a cash figure on an ii export's reading is the account's ledger's,
    wearing the export's evidence."""
    from portfusion.desk.doors import observations
    before = {p: p.read_bytes() for p in observations.paths() if p.is_file()}

    out = _write([_ii(cash=1200.00, total=41200.00)])

    assert out["ok"] is False and "states no cash" in out["refused"], out
    assert all(p.read_bytes() == b for p, b in before.items()), "a refused write moved a file"


@needs("accounts", "account-readings", "buys")
def test_a_reading_off_a_document_that_states_its_cash_still_needs_it(store_copy):
    """The other half: HL's export states its cash and its total, so a reading off it without
    them is short of figures the document holds."""
    out = _write([_share(cash="", total="")])
    assert out["ok"] is False and "no cash, total" in out["refused"], out


# =====================================================================================
# A HOLDINGS EXPORT FILED ON THE BENCH WRITES ITS READING
# =====================================================================================

@pytest.fixture
def holdings_on_the_bench(store_copy):
    """The INVENTED Account Summary on the copy's workbench, with nothing yet filed in its
    archive. The export is built from the loaded book's own units."""
    import shutil
    inbox, statements = _rules.schema.inbox(), _rules.schema.statements()
    inbox.mkdir()
    shutil.rmtree(statements)
    statements.mkdir()
    account, number = _shares_register()[0]
    (inbox / "summary.csv").write_text(
        _hl_export(account, number, _book_units(account)), encoding="utf-8")
    # The history banks a reading once; forget any banked row at this export's key.
    _clear_day(store_copy, account)
    _ensure_prior_reading(store_copy, account)
    _ensure_prior_reading(store_copy, _ii_account())
    return inbox, statements



@needs("accounts", "account-readings", "buys")
def test_a_reading_whose_document_has_left_the_workbench_fails_its_gate(holdings_on_the_bench):
    """THE DOCUMENT GONE IS ONE GATE FAILING. The reading's gate reads the document from the
    workbench, and a file moved or withdrawn meanwhile fails that gate, saying what is missing,
    never a 500."""
    from portfusion.desk.intake import bench
    inbox, _ = holdings_on_the_bench
    it = bench.for_document("summary.csv")
    (inbox / "summary.csv").unlink()
    gate = next(g for g in bench.gates(it) if g["name"] == "the account's reading")
    assert not gate["ok"] and "no longer on the workbench" in gate["detail"], gate


@needs("accounts", "account-readings", "buys")
def test_a_holdings_export_is_filed_with_its_reading_in_one_step(holdings_on_the_bench):
    from portfusion.record import schema
    from portfusion.desk.doors import commit
    from portfusion.desk.intake import bench
    inbox, statements = holdings_on_the_bench

    account = _shares_register()[0][0]
    it = bench.for_document("summary.csv")
    assert it["reading"]["account"] == account, "the export's client number names it"
    assert all(u["agrees"] for u in it["units"])
    assert len(it["units"]) == len(_book_units(account))
    gate = next(g for g in bench.gates(it) if g["name"] == "the account's reading")
    assert gate["ok"], gate["detail"]
    it["acknowledged"] = next(g for g in bench.gates(it)
                              if g["name"] == "not already in the record")["findings"]
    bench.save(it)

    out = commit.commit(it["id"])

    assert out["reading"] == account and not (inbox / "summary.csv").exists()
    assert [p.name for p in statements.iterdir()], "the document was not filed"
    h = schema.TABLES["account-readings"].header
    read = next(r for r in schema.load("account-readings") if r[0] == account)
    assert read[h.index("positions")] == 50000.00, read
    assert (account, 250.00) in {(c.account, c.cash) for c in _rules.cash_readings
                                 if c.as_of.isoformat() == "2026-09-30"}


@needs("accounts", "account-readings", "buys")
def test_a_document_goes_back_to_the_workbench_when_the_book_will_not_load(
        holdings_on_the_bench, monkeypatch):
    """The document is filed before the reading, because the readings door asks for it in the
    archive; the book is loaded last of all. A refusal there puts the document back too, or it
    is filed evidence no row cites."""
    from portfusion.desk.doors import commit
    from portfusion.desk.intake import bench
    inbox, statements = holdings_on_the_bench
    it = bench.for_document("summary.csv")
    it["acknowledged"] = next(g for g in bench.gates(it)
                              if g["name"] == "not already in the record")["findings"]
    bench.save(it)

    def _refuse():
        raise commit.Refused("the book would not load with this written, so nothing was")
    monkeypatch.setattr(commit, "_the_book_loads", _refuse)
    with pytest.raises(commit.Refused):
        commit.commit(it["id"])

    assert (inbox / "summary.csv").exists() and not list(statements.iterdir())


@needs("accounts", "account-readings", "buys")
@pytest.mark.parametrize("typed", ["30 Sep 2026", "30 September 2026"])
def test_a_reading_dated_in_words_reads_its_date(holdings_on_the_bench, typed):
    """THE DATE AS THE FILING READS IT, whole."""
    from portfusion.desk.intake import bench
    it = bench.for_document("summary.csv")
    it["evidence"]["dated"] = typed
    assert bench.reading_of(it)["as_of"] == "2026-09-30"
    gate = next(g for g in bench.gates(it) if g["name"] == "the account's reading")
    assert gate["ok"], gate["detail"]


@needs("accounts", "account-readings", "buys")
def test_a_reading_whose_date_will_not_read_is_refused_by_name(holdings_on_the_bench):
    """A date that reads as no date is a refusal that names it, never an error, and never a filed
    name nobody would look for."""
    from portfusion.desk.intake import bench
    it = bench.for_document("summary.csv")
    it["evidence"]["dated"] = "end of September"
    gate = next(g for g in bench.gates(it) if g["name"] == "the account's reading")
    assert not gate["ok"] and "'end of September'" in gate["detail"], gate["detail"]


@needs("accounts", "account-readings", "buys")
def test_a_holdings_export_whose_units_differ_is_not_filed(holdings_on_the_bench, monkeypatch):
    """The gate asks the readings door before anything moves, and names the holding."""
    from portfusion.desk.doors import commit
    from portfusion.desk.intake import bench, read_rows
    inbox, statements = holdings_on_the_bench
    account = _shares_register()[0][0]
    units = _book_units(account)
    pick = sorted(units)[0]
    real = read_rows.holdings
    monkeypatch.setattr(read_rows, "holdings",
                        lambda text, key: {**real(text, key), pick: 51000.0})

    it = bench.for_document("summary.csv")
    gate = next(g for g in bench.gates(it) if g["name"] == "the account's reading")
    assert not gate["ok"] and \
        f"{pick} book {units[pick]:,.0f}, broker 51,000" in gate["detail"], gate
    with pytest.raises(commit.Refused):
        commit.commit(it["id"])
    assert (inbox / "summary.csv").exists() and not list(statements.iterdir())


@needs("accounts", "account-readings", "buys")
def test_an_ii_holdings_export_on_the_bench_reads_its_stock_alone(holdings_on_the_bench):
    """The reading the Bench files off ii's export is the stock alone, cash and total blank —
    never a cash reading copied in when the export was opened."""
    import os
    from portfusion.desk.intake import bench
    inbox, _ = holdings_on_the_bench
    account = _ii_account()
    (inbox / "ii.csv").write_text(_ii_export(account), encoding="utf-8")
    # ii's export states no date, so the file's time dates it: the minute it was pulled.
    pulled = _dt.datetime(2026, 9, 30, 15, 5).timestamp()
    os.utime(inbox / "ii.csv", (pulled, pulled))

    it = bench.for_document("ii.csv")

    assert it["reading"]["account"] == account, "the units name the account"
    r = bench.reading_of(it)
    assert (r["positions"], r["cash"], r["total"]) == ("40000.00", "", ""), r
    gate = next(g for g in bench.gates(it) if g["name"] == "the account's reading")
    assert gate["ok"] and gate["detail"].endswith("stock 40000.00"), gate["detail"]


@needs("accounts", "account-readings", "buys")
def test_a_cash_of_nothing_is_still_shown_as_a_cash(holdings_on_the_bench):
    """A cash of 0 is a cash, which `or ''` would read as none. The reader stores figures as text,
    where "0.00" is truthy; a saved item can hold the number."""
    from portfusion.desk.intake import bench
    it = bench.for_document("summary.csv")
    it["reading"].update(cash=0, total=float(it["reading"]["positions"]))
    gate = next(g for g in bench.gates(it) if g["name"] == "the account's reading")
    assert gate["ok"] and ", cash 0, total " in gate["detail"], gate["detail"]


def test_a_reading_takes_its_cash_and_total_from_their_own_fields_alone():
    """A holdings item's reading names its cash `cash` and its total `total`; a field by any other
    name is not read as either."""
    from portfusion.desk.intake import bench
    r = bench.reading_of({"reading": {"account": "x", "positions": "1.00", "recon_cash": "2.00",
                                      "stmt_value": "3.00"}})
    assert (r["cash"], r["total"]) == (None, None), r
