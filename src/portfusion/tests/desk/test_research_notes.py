"""THE RESEARCH NOTES DOOR — a published note's rows, on one press from the Bench.

A FIXTURE REPO, never the owner's: a test reading the real one would pass or fail on whatever was
published that week. Its note names a company the LOADED book has held, so the suite says the
same on any book.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from harness import needs

_REF, _NEVER = "NOTE-9001", "NOTE-9002"


def _held():
    """A company the loaded book has held since its record began, and every code it covers."""
    from portfusion.engine import Book
    held = Book().codes_held()
    base = held[0].split()[0]
    return base, [c for c in held if c.split()[0].upper() == base.upper()]


@pytest.fixture
def notes(tmp_path, monkeypatch):
    """One published note on a held company and one on a company never held."""
    from portfusion.desk.intake import research
    base, codes = _held()
    folder = tmp_path / "research" / research.INSIGHTS
    folder.mkdir(parents=True)
    for slug, ref, ticker in (("held-co-2026-10", _REF, base), ("never-co-2026-10", _NEVER, "ZZZQ")):
        (folder / f"{slug}.mdx").write_text(
            f'---\ntitle: "A test note"\nref: {ref}\nkind: Position Review\ndate: 2026-10-08\n'
            f'companyTicker: {ticker}\ncompany: "Test Co"\nposition: long\n---\nbody\n')
    monkeypatch.setattr(research, "REPO", tmp_path / "research")
    monkeypatch.setattr(research, "INSIGHTS_URL", "https://example.test/insights")
    return codes


@needs("trades", "securities")
def test_a_note_on_a_held_company_is_owed_a_row_for_each_code_it_covers(notes):
    from portfusion.desk.doors import research_notes
    owed = research_notes.owed()
    assert [n["ref"] for n in owed] == [_REF], "a note on a company never held was offered"
    assert owed[0]["codes"] == notes
    assert owed[0]["url"] == "https://example.test/insights/held-co-2026-10/"


@needs("trades", "securities")
def test_a_press_writes_the_rows_and_journals_them_once(store_copy, notes):
    from portfusion.record import rules as D
    from portfusion.record import schema
    from portfusion.desk.doors import research_notes
    before = len(schema.load("research-notes"))
    out = research_notes.write(_REF)
    assert out["written"] == len(notes) and out["codes"] == notes
    rows = [r for r in schema.load("research-notes") if r[1] == _REF]
    assert len(schema.load("research-notes")) == before + len(notes)
    assert sorted(r[0] for r in rows) == sorted(notes)
    assert {str(r[2]) for r in rows} == {"2026-10-08"}
    last = schema.load("journal")[-1]
    assert (last[1], last[2], last[3], str(last[4]), last[5]) == (
        "bench", "append", "research-notes", str(len(notes)), _REF)
    assert all(_REF in [ref for ref, _, _ in D.RESEARCH_NOTES[c]] for c in notes), \
        "the record in memory does not follow the file"
    assert research_notes.owed() == [], "a note recorded is still owed"


@needs("trades", "securities")
@pytest.mark.parametrize("ref", [_REF, _NEVER, "NOTE-0000"])
def test_what_is_owed_nothing_is_refused_and_every_file_is_left_as_it_was(store_copy, notes,
                                                                         ref):
    """A second press, a note on a company never held, and a ref the repo does not have."""
    from portfusion.record import schema
    from portfusion.desk.doors import research_notes
    if ref == _REF:
        research_notes.write(_REF)
    paths = [schema.TABLES[t].path for t in ("research-notes", "journal")]
    held = [p.read_bytes() for p in paths]
    with pytest.raises(research_notes.Refused, match="owed no row"):
        research_notes.write(ref)
    assert [p.read_bytes() for p in paths] == held




@needs("trades", "securities")
def test_the_bench_lists_what_is_owed_and_the_route_writes_it(store_copy, notes):
    from portfusion.desk import app
    from portfusion.desk.panels import bench
    assert [n["ref"] for n in bench.data()["notes"]] == [_REF]
    client = TestClient(app.app, base_url="http://127.0.0.1:8765")
    url = f"/api/bench/notes/{_REF}"
    assert client.post(url, headers={"Origin": "https://example.com"}).status_code == 403
    assert client.post("/api/bench/notes/NOTE-0000").status_code == 409
    r = client.post(url)
    assert r.status_code == 200 and r.json()["written"] == len(notes)
    assert client.post(url).status_code == 409, "a second press wrote again"


@needs("trades", "securities")
def test_the_codes_held_are_those_open_at_the_baseline_or_dealt_in_since():
    """`Book.codes_held()`, the rule's other half. A line dealt in only before the record began
    covers no note; one dealt in since, or open when it began, does. Two invented lines are laid
    on the ledger, one each side of the baseline, with the holdings at the baseline held fixed."""
    import pandas as pd
    from portfusion.engine import BASELINE, Book
    b = Book()
    at_baseline = b.as_of(BASELINE.date().isoformat())
    b.as_of = lambda date, account=None: at_baseline
    leg = b.ledger.head(1)
    b.ledger = pd.concat([b.ledger,
                          leg.assign(ticker="ZZZQ", date=BASELINE - pd.Timedelta(days=400)),
                          leg.assign(ticker="ZZZR", date=BASELINE + pd.Timedelta(days=10))],
                         ignore_index=True)
    held = b.codes_held()
    assert "ZZZQ" not in held, "a line dealt in only before the record began covers a note"
    assert "ZZZR" in held and set(at_baseline["ticker"]) <= set(held)
