"""A FAR CONTRACT'S PAST CLOSE, off that day's filed IG statement — `desk/intake/statement_closes.py`.

The reading of the statements actually on file is the book's own check (`checks/`), because
the format is IG's and a fixture would only prove the pattern matches itself. What is here is
how the sweep uses what that reading gives.
"""


def _bar_closes(on):
    return {"on": on, "rows": [
        {"contract": "ZEPH-DEC26", "priced": True, "status": "CLOSE", "level": 75.5},
        {"contract": "ZEPH-MAR27", "priced": False, "status": "not quoted through the evening"},
        {"contract": "HALV-MAR27", "priced": False, "status": "not quoted through the evening"}]}


def test_the_past_day_fetch_fills_only_what_the_bar_left(monkeypatch):
    """The bar's close stands; a far contract takes the filed level; one the statements do not
    carry says so."""
    from portfusion.feeds import ig, refresh as R
    monkeypatch.setattr(ig, "contract_closes", _bar_closes)

    def filed(on):
        return {
            "rows": {"ZEPH-MAR27": {"contract": "ZEPH-MAR27", "priced": True, "origin": "filed",
                                    "level": 80.0},
                     "ZEPH-DEC26": {"contract": "ZEPH-DEC26", "priced": True, "level": 1.0}},
            "read": ["x.pdf"], "problems": []}

    by = {row["contract"]: row for row in R._ig_closes("2026-08-30", filed)["rows"]}
    assert by["ZEPH-DEC26"]["level"] == 75.5
    assert (by["ZEPH-MAR27"]["priced"], by["ZEPH-MAR27"]["origin"]) == (True, "filed")
    assert by["HALV-MAR27"]["status"].endswith("not on the IG statements filed for 2026-08-30")


def test_statements_that_cannot_be_read_cost_the_bar_closes_nothing(monkeypatch):
    from portfusion.feeds import ig, refresh as R

    def broken(on):
        raise RuntimeError("pypdf is not installed")
    monkeypatch.setattr(ig, "contract_closes", _bar_closes)
    r = R._ig_closes("2026-08-30", broken)
    assert r["ok"] and [row["priced"] for row in r["rows"]] == [True, False, False]
    assert "pypdf is not installed" in r["problems"][0]
    assert r["rows"][1]["status"] == "not quoted through the evening"


def test_the_desk_hands_the_sweep_its_statement_reader(monkeypatch):
    """`feeds/` may not import the desk, so the Price Refresh passes the reader in."""
    from portfusion.feeds import refresh
    from portfusion.desk.intake import statement_closes
    from portfusion.desk.panels import price_refresh as P
    seen = {}
    monkeypatch.setattr(refresh, "sweep", lambda on=None, filed=None: seen.update(
        on=on, filed=filed) or {"on": on})
    assert P._fetch_all(on="2026-09-30") == {"ok": True, "on": "2026-09-30"}
    assert seen == {"on": "2026-09-30", "filed": statement_closes.closes}
