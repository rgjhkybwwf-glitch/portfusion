"""A FAR CONTRACT'S PAST CLOSE, off that day's filed IG statement — `desk/intake/statement_closes.py`.

The statement is written here in IG's layout, with the loaded book's own deals on it: a fixture
proves only that the pattern matches itself, but what the reader does with each position does
not depend on the pattern. How the sweep uses what the reading gives follows.
"""
import datetime as dt
import pathlib

import pytest

from harness import holds

_ON = dt.date(2026, 5, 17)
_DAY = _ON.isoformat()


def _legs():
    """The loaded book's legs a statement can name: (deal, contract, account)."""
    from portfusion.record import rules as D
    return [(t.broker_ref, D.LEG_CONTRACT[t.trade_id], t.acct) for t in D.buys
            if D.LEG_CONTRACT.get(t.trade_id) and t.broker_ref]


def _priced_leg():
    """A leg whose contract has a live mark, and that mark's currency: (deal, contract,
    account, currency), or None."""
    from portfusion.record import rules as D
    currency = {r[0]: r[2] for r in D.CURRENT_PRICES}
    return next(((*leg, currency[leg[1]]) for leg in _legs() if leg[1] in currency), None)


_LEG = next(iter(_legs()), None)


def _position(deal, level):
    return f"{deal}\nA market (24 Hours) £ +1 1,000.0 {level} 0.00 0.00 0.00 0.00"


def _filed(monkeypatch, tmp_path, *statements, printed=f"{_ON:%d %B %Y}"):
    """Each of `statements` (an account, then its positions) on file for `_DAY`, printing
    `printed` as its date, and what the reader makes of them."""
    from portfusion.desk.intake import read_document, statement_closes as S
    from portfusion.record import schema
    texts = {}
    for account, *positions in statements:
        name = f"{_ON:%d %b %Y} IG statement ({account}).pdf"
        (tmp_path / name).write_bytes(b"%PDF-1.4")
        texts[name] = (f"Page 1\n{printed}\nFINANCIAL CURRENT OPEN POSITIONS\n"
                       + "\n".join(positions) + "\n")
    monkeypatch.setattr(schema, "STATEMENTS", tmp_path)
    monkeypatch.setattr(read_document, "extract_file", lambda path: {
        "text": texts[pathlib.Path(path).name], "scanned": False,
        "name": pathlib.Path(path).name})
    return S.closes(_DAY)


@holds(_LEG, what="a bet leg with its deal reference")
def test_a_position_is_read_as_its_contracts_close_placed_by_its_deal(monkeypatch, tmp_path):
    """The deal places it, never the market's name, which is the same for every expiry. A deal
    confirmation on the same page is laid out differently and is not a position."""
    deal, contract, account = _LEG
    r = _filed(monkeypatch, tmp_path, (account, f"Deal confirmation\n{deal}\nA market £ +1 2,000.0",
                                       _position(deal, "1,234.5")))
    assert r["problems"] == [] and list(r["rows"]) == [contract], r
    row = r["rows"][contract]
    assert (row["level"], row["struck"], row["at"], row["as_of"], row["origin"]) == (
        1234.5, "close", "", _DAY, "filed")
    assert row["source"].endswith(f"({account}), A market (24 Hours) current level 1,234.5, "
                                  f"deal {deal}")


@holds(_LEG, what="a bet leg with its deal reference")
@pytest.mark.parametrize("case, says", [
    ("a deal the book does not hold", "is not in the book"),
    ("two levels for one contract", "so neither is used"),
    ("a document dated another day", "so it was not read"),
])
def test_what_cannot_be_placed_or_agreed_is_reported_and_not_priced(
        monkeypatch, tmp_path, case, says):
    deal, contract, account = _LEG
    if case == "a deal the book does not hold":
        r = _filed(monkeypatch, tmp_path, (account, _position("DIAAAANOTINBOOK", "1,234.5")))
    elif case == "two levels for one contract":
        r = _filed(monkeypatch, tmp_path, (account, _position(deal, "1,234.5")),
                   ("Another account", _position(deal, "1,240.0")))
    else:
        r = _filed(monkeypatch, tmp_path, (account, _position(deal, "1,234.5")),
                   printed=f"{_ON - dt.timedelta(days=1):%d %B %Y}")
    assert r["rows"] == {}, r
    assert any(says in p for p in r["problems"]), r["problems"]


@holds(_priced_leg(), what="a priced bet leg with its deal reference")
def test_a_filed_close_goes_through_the_door_for_a_past_days_closes(store_copy, monkeypatch,
                                                                     tmp_path):
    """What the desk sends when the line is ticked, banked as that day's close and sourced to
    the document."""
    from portfusion.desk.doors import marks
    from portfusion.history import prices as PH
    deal, contract, account, currency = _priced_leg()
    row = _filed(monkeypatch, tmp_path, (account, _position(deal, "1,234.5")))["rows"][contract]
    out = marks.bank_closes(_DAY, prices=[{
        "mark_key": contract, "price": row["level"], "currency": currency,
        "as_of": row["as_of"], "source": row["source"], "struck": row["struck"],
        "at": row["at"]}])
    assert out["banked"]["prices"] == 1, out
    banked = next(r for r in PH.load() if (r["mark_key"], r["date"]) == (contract, _DAY))
    assert (banked["price"], banked["struck"], banked["source"]) == (
        1234.5, "close", row["source"])


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


def test_the_demos_ig_statement_gives_each_contract_its_level():
    """THE DEMO SHOWS THE ROUTE: its filed IG statement prints its date alone and its open
    positions, so a far contract's close for that day comes off the statement on file."""
    from portfusion.desk.intake import statement_closes as S
    from portfusion.record import rules as D, schema
    if D.store_dir().resolve() != (schema.DEMO / "store").resolve():
        pytest.skip("the demo's own statement, read with the demo loaded")
    got = S.closes("2026-07-06")
    assert not got["problems"], got["problems"]
    assert {c: r["level"] for c, r in got["rows"].items()} == {"VELD-SEP26": 9930.0,
                                                               "VELD-DEC26": 9920.0}, got["rows"]
