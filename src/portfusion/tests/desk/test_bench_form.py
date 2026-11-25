"""THE BENCH'S FORM — each column the store's, each choice the record's, each check the loader's."""
from __future__ import annotations

import pytest
from portfusion.desk.intake import bench as _bench
from desk_support import SPREAD_BET_ACCOUNT
from harness import free_id


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


def test_the_next_id_is_allocated_from_the_store_not_guessed(item):
    from portfusion.record import rules as D
    ids = _bench.next_ids()
    assert ids["buys"] not in {t.trade_id for t in D.buys}
    assert ids["sales"] not in {e.sale_id for e in D.sales}


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
    """The choices are the record's own, read from it: a guide names no account, and a list of
    them written down would be a SECOND statement of what the record already holds."""
    from portfusion.record import rules as D
    v = _bench.vocabulary()
    assert v["account"] == list(D.ACCOUNT_ORDER)


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


def test_a_free_prose_column_offers_no_choices_either():
    """Not just an open vocabulary — NO vocabulary. Offering the class keys as suggestions
    under a field that wants a sentence would invite the wrong value into the one column whose
    whole job is naming the document. The browser renders a `choices` list as a combobox
    whatever `closed` says."""
    from portfusion.desk.intake import bench
    spec = {f["name"]: f for f in bench.form_for("buys")}["source"]
    assert spec["choices"] is None and spec["closed"] is False, \
        f"trades.source offers a vocabulary: {spec}"
