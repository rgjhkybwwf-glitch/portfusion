"""THE BENCH'S GATES — whether an item may be approved, tested one gate at a time."""
from __future__ import annotations

from portfusion.desk.intake import bench as _bench
from desk_support import GOOD_DOCUMENT, GOOD_TRADE, GOOD_EVIDENCE, _ready


def test_a_trade_whose_source_is_not_its_kinds_format_is_refused(item):
    """The one format, checked at entry: a typed line in another shape is named with the line
    its document's kind composes, so the fix is a copy rather than a guess."""
    _ready(item, source="Contract note TESTREF1")
    rows = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not rows["ok"], rows["detail"]
    assert "'ii contract note 01 Sep 2026'" in rows["detail"], rows["detail"]
    _ready(item)
    assert next(g for g in _bench.gates(item) if g["name"] == "rows")["ok"]


def test_two_rows_of_one_item_under_one_id_are_refused(item):
    """AN ID ONCE: two rows of one item under one id fail the rows gate."""
    _ready(item)
    item["rows"].append({"table": "buys", "values": dict(GOOD_TRADE, broker_ref="TESTREF2")})
    rows = next(g for g in _bench.gates(item) if g["name"] == "rows")
    assert not rows["ok"] and f"id {GOOD_TRADE['trade_id']} is row 1's too" in rows["detail"], rows


def test_an_item_is_not_approvable_until_every_gate_is_green(item):
    assert not _bench.approved(item)
    # THE GATES ARE A NAMED SET, the shape test_boundaries.py's WRITERS uses. A new one
    # joins by being written down here, on purpose — a gate that appears without a decision is a
    # gate nobody chose. "the reference retrieves it" is statement-grade checked at the door,
    # rather than asserted about a row afterwards.
    assert {g["name"] for g in _bench.gates(item)} == {
        "statement-grade", "the reference retrieves it", "rows", "every line read",
        "not already in the record", "signs as the category's", "why_entered", "why_exited"}
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


def test_an_open_vocabulary_accepts_a_value_the_record_has_never_seen(item):
    """A FIRST-EVER PURCHASE OF A NEW COMPANY MUST NOT BE REFUSED: an enforced derived list would
    fail a ticker not yet in buys.csv, blocking precisely the event the bench exists for. Tickers
    and income categories grow in the ordinary course of business; accounts and currencies do
    not."""
    assert _bench.approved(_ready(item, ticker="NEVER-HELD.L"))


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
