"""THE REPORTS PAGE, AND THE ROUTE THAT OPENS A REPORT — what each promises, held.

`desk/panels/reports.py` says what the page is for; these say what it may and may not do.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from portfusion.desk import app, engine, panels
from harness import needs


def test_the_reports_page_decides_nothing(monkeypatch):
    """The panel hands over the engine's answer as it stands, and every quarter's gaps are the
    gate's own list for that date.

    AGAINST AN ANSWER WORKED AGAIN, not the one the panel was handed: both read the same cache,
    so comparing them tests one object against itself and passes a page that edited it."""
    import copy
    from portfusion.report.gate import completeness
    data = copy.deepcopy(panels.get("reports").data())
    monkeypatch.setitem(engine._reports, "key", None)
    assert data == engine.reports()
    assert data["quarters"], "the Reports page lists no quarter at all"
    for q in data["quarters"]:
        assert q["gaps"] == completeness(q["quarter_end"]), q["quarter"]
    ends = [q["quarter_end"] for q in data["quarters"]]
    assert ends == sorted(ends, reverse=True), "the quarters are not newest first"
    assert all(not y["built"] for y in data["years"]), \
        "a year-end report is listed as built, and none is yet"
    # EVERYTHING SENT IS DRAWN: a year is its name and whether its report is built.
    assert all(set(y) == {"year", "built"} for y in data["years"]), data["years"]


@needs("quarter-nav")
def test_a_quarter_the_gate_allows_opens_as_the_report_page():
    """THE SAME PAGE THE COMMAND LINE WRITES, served with a policy of its own: the page embeds
    its face and inlines its style, and may do nothing else — no script, no request out."""
    from portfusion.report.page import render
    ready = [q for q in engine.reports()["quarters"] if q["closed"] and not q["gaps"]]
    assert ready, "no quarter is ready, so this asserts nothing"
    q = ready[0]
    response = app.report(q["quarter_end"])
    assert response.status_code == 200 and response.media_type == "text/html"
    assert response.body.decode() == render(q["quarter_end"]), \
        "the desk's report is not the page portfusion report writes"
    policy = response.headers["content-security-policy"]
    assert "default-src 'none'" in policy and "script-src" not in policy
    assert "no-store" in response.headers["cache-control"]


def test_a_quarter_the_gate_refuses_says_why():
    refused = [q for q in engine.reports()["quarters"] if q["gaps"]]
    assert refused, "every quarter is ready, so this asserts nothing"
    response = app.report(refused[0]["quarter_end"])
    assert response.status_code == 409
    assert refused[0]["gaps"][0] in response.body.decode()


@pytest.mark.parametrize("bad", ["2026-09-29", "Q3 2026", "../engine.py", "2026-9-30"])
def test_only_a_quarter_end_is_asked_for(bad):
    with pytest.raises(HTTPException) as e:
        app.report(bad)
    assert e.value.status_code == 400


@needs("quarter-nav")
def test_opening_a_report_writes_nothing():
    """The route renders for the request, or opening a page on the hosted desk would leave a file
    on the Mac. Held on the book's folder."""
    from portfusion.record import schema
    before = sorted(p for p in schema.BOOK.iterdir())
    ready = [q for q in engine.reports()["quarters"] if q["closed"] and not q["gaps"]]
    app.report(ready[0]["quarter_end"])
    assert sorted(p for p in schema.BOOK.iterdir()) == before


@needs("quarter-nav")
def test_the_dashboard_and_performance_link_only_to_reports_the_gate_allows():
    allowed = {q["quarter_end"] for q in engine.reports()["quarters"]
               if q["closed"] and not q["gaps"]}
    report = panels.get("dashboard").data()["report"]
    assert report and report["quarter_end"] in allowed
    assert report["quarter_end"] == max(allowed), "the Dashboard does not name the latest report"
    linked = [q["quarter_end"] for q in panels.get("performance").data()["reports"]]
    assert set(linked) == allowed and linked == sorted(linked)
