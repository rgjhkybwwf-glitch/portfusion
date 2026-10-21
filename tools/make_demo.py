"""
THE DEMO BOOK'S GENERATOR: `demo/` is written whole from this file, and from nothing else.

`demo/` is an invented book (`tests/test_demo.py`): every holder, account, figure and document in
it is made up here, and this file is the source each of its rows names. It ships with the code
as the default book, so a stranger can install the app and see every page filled.

THE COLUMNS AND THE VOCABULARIES ARE THE SCHEMA'S. A row is a dict keyed by column name; a table's
cells are written in `schema.TABLES` order and each one is parsed by the loader's own `_parse`, so
a renamed column or a closed list that moved stops this file at the row, naming it, rather than
writing a demo the loader refuses. A source line is composed by `rules`, never typed.

THE ARCHIVE IS INVENTED TOO. Each ii deal but one has a contract note, written here as a small
PDF the bench reads the way it reads a real one; the sale of 20 Jun 2026 fell on a Saturday, so it
stays not on file. One IG statement holds the two legs opened on 6 Jul 2026, so a stored deal id
leads to a document as a real one must. The one bench record is the last note worked through the bench, in the shape
the bench writes today: `tests/test_demo.py` opens the filed note on a bench and compares.

THE JOURNAL IS DERIVED. It opens once with every table's count, takes the quarter freezes and the
bench write made before it opened, and the one hand edit after: the restatement of 13 Oct 2026.

    python3 tools/make_demo.py               write the demo's store/ and _archive/ afresh
    python3 tools/make_demo.py --into DIR    write the same book into DIR instead

A fresh run reproduces `demo/` byte for byte: `tests/test_demo.py` holds it to that. After a
schema or format change, run it, read the diff, and commit the two together.
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import shutil
import sys
import tempfile

# THE HISTORIES' FILES, NOT THE HISTORIES: those import the record, which loads a book, and this
# runs to write one — after a schema change, before any book holds the new shape.
from portfusion.history import files as history_files
from portfusion.record import rules_evidence as D
from portfusion.record import schema

HERE = pathlib.Path(__file__).resolve().parent.parent     # the checkout; this file is in tools/
DEMO = HERE / "src" / "portfusion" / "demo"     # inside the app, which ships it

NOT_ON_FILE = D.evidence_source("not-on-file", reference="invented for the demo")
INVENTED = "Invented for the demo"
UNFUNDED = "Account not yet funded"
#: `rules.LIVE_MARK`, which this file cannot import: `rules` loads a store, and none exists yet.
LIVE = "live"

ISA, TRADING, SPREAD = "Voss ii ISA", "Voss ii Trading", "Voss IG Spread bet"

#: When the journal opened, and every count in it is taken.
OPENED = "2026-09-30T18:00:00"


# =====================================================================================
# THE CONTRACT NOTES — each ii deal's document, and what its row takes from it
# =====================================================================================

def _note(ref: str, time: str, settles: str, *security: str, commission: float = 0.0) -> dict:
    """An ii deal's contract note: its number, its dealing time and settlement date, and the
    lines it prints about the security. It rides on its row as `_note`, so the row takes its
    `source` and `broker_ref` from the note, and the note prints the row's own quantity, price
    and sterling figure: the two cannot disagree."""
    return {"ref": ref, "time": time, "settles": settles, "security": security,
            "commission": commission}


#: The name the benched note arrived under (its row carries `_benched`), and the item's id.
BENCHED_AS = "ContractNote_DMW5ZG.pdf"
BENCH_ID = "B-20260812-4c7e2d"


def _allocate(rows: list[dict], key: str, prefix: str) -> None:
    """Ids in the order the rows were dealt, as the store hands them out: none is typed here."""
    for n, row in enumerate(rows, 1):
        row[key] = f"{prefix}-{n:03d}"


def _settle(T: dict) -> tuple[list, dict]:
    """Resolve what the rows point at and file each row under its document: returns each
    (side, row, note), and each IG statement's rows by its date, for the archive."""
    _allocate(T["trades"], "id", "T")
    _allocate(T["exits"], "eid", "E")
    noted, stated = [], {}
    for table, side in (("trades", "BOUGHT"), ("exits", "SOLD")):
        for row in T[table]:
            if "_closes" in row:
                row["closes"] = row.pop("_closes")["id"]
            if "_note" in row:
                row.update(source=D.trade_source("ii-contract-note", row["date"]),
                           broker_ref=row["_note"]["ref"])
                noted.append((side, row, row["_note"]))
            if "_statement" in row:
                row["source"] = D.trade_source("ig-statement", row["_statement"])
                stated.setdefault(row["_statement"], []).append(row)
    return noted, stated


# =====================================================================================
# THE BOOK — every row, by table
# =====================================================================================

def _book() -> dict[str, list[dict]]:
    T = {}
    T["issuers"] = [
        {"company": "Bryncoed Minerals plc", "sector": "Mining", "region": "UK"},
        {"company": "Kelstrand Foods plc", "sector": "Consumer Staples", "region": "UK"},
        {"company": "Quenlan Robotics Inc.", "sector": "Industrials", "region": "US"},
        {"company": "Tarnwell Hotels plc", "sector": "Travel & Leisure", "region": "UK"},
        {"company": "Veldrome Metals Inc.", "sector": "Materials", "region": "US"},
    ]
    T["securities"] = [
        {"code": "BRYC.L", "company": "Bryncoed Minerals plc", "kind": "shares",
         "currency": "GBP", "tv_symbol": "LSE:BRYC", "tv_unit": "GBX"},
        {"code": "KELS.L", "company": "Kelstrand Foods plc", "kind": "shares",
         "currency": "GBP", "tv_symbol": "LSE:KELS", "tv_unit": "GBX"},
        {"code": "QNLR", "company": "Quenlan Robotics Inc.", "kind": "shares",
         "currency": "USD", "tv_symbol": "NASDAQ:QNLR", "tv_unit": "USD"},
        {"code": "TARN.L", "company": "Tarnwell Hotels plc", "kind": "shares", "currency": "GBP"},
        {"code": "VELD SB", "company": "Veldrome Metals Inc.", "kind": "spread bet",
         "currency": "USD", "tv_symbol": "NYSE:VELD"},
        {"code": "QNLR SB", "company": "Quenlan Robotics Inc.", "kind": "spread bet",
         "currency": "USD", "tv_symbol": "NASDAQ:QNLR"},
    ]
    T["accounts"] = [
        {"account": ISA, "holder": "Ms Nia Voss", "broker": "interactive investor",
         "number": "7421950", "code": "A1", "kind": "shares"},
        {"account": TRADING, "holder": "Ms Nia Voss", "broker": "interactive investor",
         "number": "7421951", "code": "A2", "kind": "shares"},
        {"account": SPREAD, "holder": "Ms Nia Voss", "broker": "IG Index Ltd",
         "number": "XK9P3", "code": "A3", "kind": "spread bet", "feed_key": "VOSS_IG"},
    ]
    T["capital-movements"] = [
        {"date": d, "account": a, "amount": v, "source": NOT_ON_FILE, "detail": "Deposit"}
        for d, a, v in (("2026-01-15", ISA, 6000.0), ("2026-02-27", TRADING, 1500.0),
                        ("2026-05-05", ISA, 3000.0), ("2026-07-01", SPREAD, 5000.0),
                        ("2026-08-05", SPREAD, 1500.0))]
    T["closed-positions"] = [
        {"ticker": "TARN.L", "realisation": "R-TARN", "open_date": "2026-02-10",
         "note": "Sold whole, 20 Jun 2026; nothing stays open."},
        {"ticker": "KELS.L", "realisation": "R-KELS", "open_date": "2026-05-20",
         "note": "Half sold; 1,000 shares stay open."},
        {"ticker": "VELD SB", "realisation": "R-VELDSB", "open_date": "2026-07-06",
         "note": "The September leg closed whole; December and March stay open."},
        {"ticker": "QNLR SB", "realisation": "R-QNLRSB", "open_date": "2026-08-14",
         "note": "The smaller leg closed; the December leg stays open."},
    ]
    shares = dict(source=NOT_ON_FILE, cur="GBP")
    bets = dict(source=NOT_ON_FILE, account=SPREAD, cur="GBP")
    T["trades"] = [
        {"date": "2025-11-10", "account": ISA, "ticker": "BRYC.L", "qty": 1000, "val": 2000.0,
         "price": 2.0, **shares,
         "_note": _note("DMQ4TA", "09:42", "12/11/2025", "BRYNCOED MINERALS PLC", "ORD GBP0.10")},
        {"date": "2026-02-10", "account": ISA, "ticker": "TARN.L", "qty": 800, "val": 2000.0,
         "price": 2.5, **shares,
         "_note": _note("DMR8KB", "10:05", "12/02/2026", "TARNWELL HOTELS PLC", "ORD GBP0.25")},
        {"date": "2026-03-02", "account": TRADING, "ticker": "BRYC.L", "qty": 500, "val": 1025.0,
         "price": 2.05, **shares,
         "_note": _note("DMS2LC", "14:20", "04/03/2026", "BRYNCOED MINERALS PLC", "ORD GBP0.10")},
        {"date": "2026-04-14", "account": ISA, "ticker": "QNLR", "qty": 50, "val": 3800.0,
         "price": 100.0, "rate": 1.3158, **shares, "cur": "USD",
         "_note": _note("DMT6WD", "15:31", "16/04/2026", "QUENLAN ROBOTICS INC", "COM USD0.001",
                        commission=0.03)},
        {"date": "2026-05-20", "account": ISA, "ticker": "KELS.L", "qty": 2000, "val": 3000.0,
         "price": 1.5, **shares,
         "_note": _note("DMU3XE", "11:12", "22/05/2026", "KELSTRAND FOODS PLC", "ORD GBP0.05")},
        {"date": "2026-07-06", "ticker": "VELD SB", "stake": 1, "val": 9850.0,
         "contract": "VELD-SEP26", **bets, "broker_ref": "DIAAAADEMOVELD06",
         "_statement": "2026-07-06"},
        {"date": "2026-07-06", "ticker": "VELD SB", "stake": 1, "val": 9900.0,
         "contract": "VELD-DEC26", **bets, "broker_ref": "DIAAAADEMOVELD07",
         "_statement": "2026-07-06"},
        {"date": "2026-08-03", "ticker": "VELD SB", "stake": 0.8, "val": 10100.0,
         "contract": "VELD-MAR27", **bets},
        {"date": "2026-08-14", "ticker": "QNLR SB", "stake": 0.5, "val": 10200.0,
         "contract": "QNLR-DEC26", **bets},
        {"date": "2026-08-14", "ticker": "QNLR SB", "stake": 0.3, "val": 10300.0,
         "contract": "QNLR-DEC26", **bets},
    ]
    # A CONSOLIDATION, so the shipping check walks one: Tarnwell's 2-to-1 between its quarter-end
    # mark and its sale, the row the Bench derives (`bench.adjustment_cells`), and the sale takes
    # the new count at twice the price, so no figure moves.
    tarn = next(t for t in T["trades"] if t["ticker"] == "TARN.L")
    T["trades"].append(
        {"date": "2026-05-11", "account": ISA, "ticker": "TARN.L", "qty": tarn["qty"] // 2 - tarn["qty"],
         "val": 0.0, "cur": "GBP",
         "source": "Derived: 2-to-1 consolidation of TARN.L, effective 11 May 2026, invented for the demo",
         "note": f"2-to-1 share consolidation: {tarn['qty']:,} shares became {tarn['qty'] // 2:,}."})

    def leg(contract, stake):
        return next(t for t in T["trades"] if t.get("contract") == contract and t["stake"] == stake)

    # The sale of 20 Jun 2026 fell on a Saturday, so no note is invented for it.
    T["exits"] = [
        {"date": "2026-06-20", "account": ISA, "ticker": "TARN.L", "qty": 400, "price": 5.6,
         "proceeds": 2240.0, "broker_ref": "WDEMO441", "realisation": "R-TARN", **shares},
        {"date": "2026-08-12", "account": ISA, "ticker": "KELS.L", "qty": 1000, "price": 1.8,
         "proceeds": 1800.0, "realisation": "R-KELS", **shares, "_benched": True,
         "_note": _note("DMW5ZG", "09:47", "14/08/2026", "KELSTRAND FOODS PLC", "ORD GBP0.05")},
        {"date": "2026-09-01", "ticker": "VELD SB", "stake": 1, "price": 10420.0,
         "proceeds": 10420.0, "realisation": "R-VELDSB", "_closes": leg("VELD-SEP26", 1), **bets},
        {"date": "2026-09-15", "ticker": "QNLR SB", "stake": 0.3, "price": 10400.0,
         "proceeds": 3120.0, "realisation": "R-QNLRSB", "_closes": leg("QNLR-DEC26", 0.3),
         **bets},
    ]
    T["income"] = [
        {"date": "2026-06-15", "account": ISA, "category": "Dividend",
         "detail": "BRYC.L final dividend", "amount": 30.0, "source": NOT_ON_FILE},
        {"date": "2026-08-20", "account": SPREAD, "category": "Funding interest",
         "detail": "Long interest 06/07/26 to 31/08/26, ref CS00DEMO0000001", "amount": -1.2,
         "source": NOT_ON_FILE},
        {"date": "2026-09-25", "account": ISA, "category": "Cash interest",
         "detail": "Gross interest", "amount": 1.1, "source": NOT_ON_FILE},
        {"date": "2026-09-26", "account": TRADING, "category": "Dividend",
         "detail": "BRYC.L interim dividend", "amount": 12.5, "source": NOT_ON_FILE},
    ]
    T["quarter-nav"] = _quarter_nav()
    T["quarter-snapshots"] = _quarter_snapshots()
    T["fx"] = [{"currency": "USD", "rate": 1.33, "as_of": "2026-09-30", "source": INVENTED,
                "struck": "close"}]
    T["current-prices"] = (
        [{"ticker": t, "price": p, "currency": c, "as_of": "2026-09-30", "source": INVENTED,
          "struck": "close"}
         for t, p, c in (("BRYC.L", 2.35, "GBP"), ("KELS.L", 1.7, "GBP"), ("QNLR", 112.0, "USD"))]
        + [{"ticker": t, "price": p, "currency": "USD", "as_of": "2026-09-30",
            "source": _ig_bid(p), "struck": "live", "at": "2026-09-30T15:00Z"}
           for t, p in (("VELD-DEC26", 10610.0), ("VELD-MAR27", 10340.0),
                        ("QNLR-DEC26", 10480.0))])
    T["baseline-reconstruction"] = [
        {"as_of": "2025-12-31", "ticker": "BRYC.L", "qty": 1000, "price": 2.0,
         "source": NOT_ON_FILE, "fx": 1.0, "quality": "derived"}]
    T["account-observations"] = [
        {"account": SPREAD, "as_of": "2026-09-30", "at": "2026-09-30T15:00Z", "funds": 6500.0,
         "equity": 8140.8, "evidence": "ig-accounts",
         "reference": "XK9P3, read 2026-09-30 at 16:00"}]
    T["reasoning"] = [
        {"ticker": t, "date": d, **({"why_entered": w} if entered else {"why_exited": w})}
        for t, d, entered, w in (
            ("TARN.L", "2026-02-10", True, "Invented for the demo: why the position was taken."),
            ("TARN.L", "2026-06-20", False,
             "Invented for the demo: why the position was closed whole."),
            ("QNLR", "2026-04-14", True, "Invented for the demo: why the position was taken."),
            ("KELS.L", "2026-05-20", True, "Invented for the demo: why the position was taken."),
            ("KELS.L", "2026-08-12", False, "Invented for the demo: why half was sold."),
            ("VELD SB", "2026-07-06", True, "Invented for the demo: why the position was taken."),
            ("QNLR SB", "2026-08-14", True, "Invented for the demo: why the position was taken."),
            ("QNLR SB", "2026-09-15", False,
             "Invented for the demo: why the smaller leg closed."),
        )]
    T["cash-observations"] = [
        {"account": a, "as_of": "2026-09-30", "cash": c, "evidence": "not-on-file",
         "reference": "invented for the demo"}
        for a, c in ((ISA, 4271.1), (TRADING, 487.5))]
    T["research-notes"] = []
    T["quarter-results"] = _quarter_results()
    T["settings"] = [{"key": k, "value": v} for k, v in (
        ("record_begins", "2026-01-01"), ("reasoning_owed_from", "2026-04-01"),
        ("first_report", "2026-09-30"), ("tv_list_live", "100000001"),
        ("tv_list_exit", "100000002"), ("tv_list_entry", "100000003"),
        ("rate_carried", ""), ("trade_id_floor", ""),
        # An invented hosted desk on a reserved test domain; no deploy or research repository,
        # so --publish and the research notes decline on the demo, as on a new book.
        ("hosted_origin", "https://desk.example.test"), ("passkey_domain", "example.test"),
        ("deploy_repo", ""), ("research_repo", ""),
        ("insights_url", "https://example.test/insights"))]
    T["contracts"] = [
        {"contract": "VELD-SEP26", "funding": "daily"},
        {"contract": "VELD-DEC26", "epic": "DM.D.VELDUS.DEC.IP", "funding": "dated"},
        {"contract": "VELD-MAR27", "epic": "DM.D.VELDUS.MAR.IP", "funding": "dated"},
        {"contract": "QNLR-DEC26", "epic": "DM.D.QNLRUS.DEC.IP", "funding": "dated"},
    ]
    return T


def _ig_bid(level: float) -> str:
    return f"{INVENTED}: an IG read would state bid {level}"


def _frozen(as_of: str, what: str) -> str:
    """The source line `desk/doors/freeze.py` writes for a frozen quarter end."""
    return {"positions at market": f"Positions at market frozen from the engine at the marks "
                                   f"nearest {as_of}",
            "account equity": f"Equity frozen from the engine at the marks nearest {as_of}: "
                              f"funds plus the legs at those levels",
            "notional": f"Notional frozen from the engine at the marks nearest {as_of}, the "
                        f"EXPOSURE measure — NOT part of NAV"}[what]


def _quarter_nav() -> list[dict]:
    rows = [
        {"as_of": "2025-12-31", "account": ISA, "amount": 2000.0,
         "contribution": "positions at market", "quality": "derived", "source": NOT_ON_FILE},
        {"as_of": "2025-12-31", "account": TRADING, "amount": 0.0,
         "contribution": "positions at market", "quality": "sourced", "source": UNFUNDED},
        {"as_of": "2025-12-31", "account": SPREAD, "amount": 0.0,
         "contribution": "account equity", "quality": "sourced", "source": UNFUNDED},
        {"as_of": "2025-12-31", "account": SPREAD, "amount": 0.0, "contribution": "notional",
         "quality": "sourced", "source": UNFUNDED},
    ]
    for as_of, isa, trading, equity, notional in (("2026-03-31", 4180.0, 1050.0, 0.0, 0.0),
                                                  ("2026-06-30", 9377.27, 1100.0, 0.0, 0.0),
                                                  ("2026-09-30", 8260.53, 1175.0, 8140.8,
                                                   24122.0)):
        rows += [{"as_of": as_of, "account": a, "amount": v, "contribution": c,
                  "quality": "derived", "source": _frozen(as_of, c)}
                 for a, v, c in ((ISA, isa, "positions at market"),
                                 (TRADING, trading, "positions at market"),
                                 (SPREAD, equity, "account equity"),
                                 (SPREAD, notional, "notional"))]
    return [{**r, "status": LIVE} for r in rows]


def _quarter_snapshots() -> list[dict]:
    def held(as_of, account, ticker, qty, price, value, cost, currency="GBP", source=INVENTED):
        return {"as_of": as_of, "account": account, "ticker": ticker, "qty": qty,
                "local_price": price, "currency": currency, "gbp_value": value,
                "gbp_cost": cost, "source": source}

    def empty(as_of):
        return {"as_of": as_of, "account": SPREAD, "ticker": "(no positions)", "gbp_value": 0.0,
                "gbp_cost": 0.0, "source": f"No open position at {as_of}, frozen from the "
                                           f"engine at the marks nearest {as_of}"}
    rows = [
        held("2026-03-31", ISA, "BRYC.L", 1000, 2.1, 2100.0, 2000.0),
        held("2026-03-31", ISA, "TARN.L", 800, 2.6, 2080.0, 2000.0),
        held("2026-03-31", TRADING, "BRYC.L", 500, 2.1, 1050.0, 1025.0),
        empty("2026-03-31"),
        held("2026-06-30", ISA, "BRYC.L", 1000, 2.2, 2200.0, 2000.0),
        held("2026-06-30", ISA, "KELS.L", 2000, 1.6, 3200.0, 3000.0),
        held("2026-06-30", ISA, "QNLR", 50, 105.0, 3977.27, 3800.0, "USD"),
        held("2026-06-30", TRADING, "BRYC.L", 500, 2.2, 1100.0, 1025.0),
        empty("2026-06-30"),
        held("2026-09-30", ISA, "BRYC.L", 1000, 2.35, 2350.0, 2000.0),
        held("2026-09-30", ISA, "KELS.L", 1000, 1.7, 1700.0, 1500.0),
        held("2026-09-30", ISA, "QNLR", 50, 112.0, 4210.53, 3800.0, "USD"),
        held("2026-09-30", TRADING, "BRYC.L", 500, 2.35, 1175.0, 1025.0),
        held("2026-09-30", SPREAD, "QNLR SB", 0.5, 10480.0, 5240.0, 5100.0, "USD",
             _ig_bid(10480.0)),
        held("2026-09-30", SPREAD, "VELD SB", 1.8, 10490.0, 18882.0, 17980.0, "USD",
             f"{_ig_bid(10610.0)} + {_ig_bid(10340.0)}"),
    ]
    return [{**r, "quality": "derived", "status": LIVE} for r in rows]


#: The note a restated quarter-results row carries.
RESTATED = ("Restated: the return is day-weighted (modified Dietz), each flow weighted by the days "
            "from its date to the quarter end")


def _quarter_results() -> list[dict]:
    cols = ("as_of", "account", "opening_nav", "capital_deployed", "return_income",
            "closing_nav", "gain", "return")
    frozen = [
        ("2026-03-31", "", 2000.0, 3025.0, 0.0, 5230.0, 205.0, 0.058363),
        ("2026-03-31", ISA, 2000.0, 2000.0, 0.0, 4180.0, 180.0, 0.06),
        ("2026-03-31", TRADING, 0.0, 1025.0, 0.0, 1050.0, 25.0, 0.04878),
        ("2026-03-31", SPREAD, 0.0, 0.0, 0.0, 0.0, None, None),
        ("2026-06-30", "", 5230.0, 4560.0, 30.0, 10477.27, 717.27, 0.095509),
        ("2026-06-30", ISA, 4180.0, 4560.0, 30.0, 9377.27, 667.27, 0.103293),
        ("2026-06-30", TRADING, 1050.0, 0.0, 0.0, 1100.0, 50.0, 0.047619),
        ("2026-06-30", SPREAD, 0.0, 0.0, 0.0, 0.0, None, None),
        ("2026-09-30", "", 10477.27, 4700.0, 12.5, 17576.33, 2411.56, 0.188003),
        ("2026-09-30", ISA, 9377.27, -1800.0, 0.0, 8260.53, 683.26, 0.080599),
        ("2026-09-30", TRADING, 1100.0, 0.0, 12.5, 1175.0, 87.5, 0.079545),
        ("2026-09-30", SPREAD, 0.0, 6500.0, 0.0, 8140.8, 1640.8, 0.504862),
    ]
    restated = [
        ("2026-03-31", "", 2000.0, 3025.0, 0.0, 5230.0, 205.0, 0.059956),
        ("2026-03-31", ISA, 2000.0, 2000.0, 0.0, 4180.0, 180.0, 0.058273),
        ("2026-03-31", TRADING, 0.0, 1025.0, 0.0, 1050.0, 25.0, 0.075694),
        ("2026-06-30", "", 5230.0, 4560.0, 30.0, 10477.27, 717.27, 0.0751),
        ("2026-06-30", ISA, 4180.0, 4560.0, 30.0, 9377.27, 667.27, 0.078494),
        ("2026-09-30", "", 10477.27, 4700.0, 12.5, 17576.33, 2411.56, 0.156826),
        ("2026-09-30", ISA, 9377.27, -1800.0, 0.0, 8260.53, 683.26, 0.081161),
        ("2026-09-30", SPREAD, 0.0, 6500.0, 0.0, 8140.8, 1640.8, 0.280062),
    ]
    return ([dict(zip(cols, r)) for r in frozen]
            + [{**dict(zip(cols, r)), "note": RESTATED} for r in restated])


def _histories() -> dict[str, tuple[list[str], list[dict]]]:
    """The three append-only histories, by file name: (their columns, their rows)."""
    prices = [
        {"ticker": t, "date": d, "price": p, "currency": c, "quality": "derived",
         "struck": "close", "status": s, "source": INVENTED}
        for t, d, p, c, s in (
            ("BRYC.L", "2025-12-31", 2.0, "GBP", LIVE), ("BRYC.L", "2026-03-31", 2.1, "GBP", LIVE),
            ("TARN.L", "2026-03-31", 2.6, "GBP", LIVE), ("BRYC.L", "2026-06-30", 2.2, "GBP", LIVE),
            ("KELS.L", "2026-06-30", 1.6, "GBP", LIVE), ("QNLR", "2026-06-30", 105.0, "USD", LIVE),
            ("VELD SB", "2026-07-31", 10020.0, "USD", LIVE),
            ("BRYC.L", "2026-09-30", 2.35, "GBP", LIVE), ("KELS.L", "2026-09-30", 1.7, "GBP", LIVE),
            ("QNLR", "2026-09-30", 111.5, "USD", "superseded"),
            ("QNLR", "2026-09-30", 112.0, "USD", LIVE))
    ] + [
        {"ticker": t, "date": "2026-09-30", "price": p, "currency": "USD", "quality": "derived",
         "struck": "live", "status": LIVE, "source": _ig_bid(p)}
        for t, p in (("VELD-DEC26", 10610.0), ("VELD-MAR27", 10340.0), ("QNLR-DEC26", 10480.0))]
    fx = [
        {"currency": c, "date": d, "rate": r, "kind": "spot", "quality": "derived",
         "struck": s, "status": LIVE, "source": INVENTED}
        for c, d, r, s in (("USD", "2026-04-14", 1.3158, ""), ("USD", "2026-06-30", 1.32, "close"),
                           ("USD", "2026-09-30", 1.33, "close"), ("SEK", "2026-09-30", 12.4, ""))]
    unfunded_ig = {"account": SPREAD, "equity": 0.0, "source": UNFUNDED, "quality": "derived"}
    statements = []
    for as_of, isa, trading in (("2025-12-31", (2000.0, 0.0), None),
                                ("2026-03-31", (4180.0, 4000.0), (1050.0, 475.0)),
                                ("2026-06-30", (9377.27, 2470.0), (1100.0, 475.0))):
        statements += [
            {"account": ISA, "as_of": as_of, "positions_value": isa[0], "cash": isa[1],
             "source": NOT_ON_FILE, "quality": "derived"},
            {"account": TRADING, "as_of": as_of, "positions_value": (trading or (0.0, 0.0))[0],
             "cash": (trading or (0.0, 0.0))[1], "source": NOT_ON_FILE if trading else UNFUNDED,
             "quality": "derived"},
            {**unfunded_ig, "as_of": as_of}]
    statements += [
        {"account": ISA, "as_of": "2026-09-30", "positions_value": 8260.53, "cash": 4271.1,
         "source": NOT_ON_FILE, "quality": "sourced"},
        {"account": TRADING, "as_of": "2026-09-30", "positions_value": 1175.0, "cash": 487.5,
         "source": NOT_ON_FILE, "quality": "sourced"},
        {"account": SPREAD, "as_of": "2026-09-30", "positions_value": 24122.0, "equity": 8140.8,
         "source": "IG REST /accounts XK9P3, read 2026-09-30 at 16:00", "quality": "sourced"}]
    return {history_files.PRICES: (history_files.PRICE_FIELDS, prices),
            history_files.FX: (history_files.FX_FIELDS, fx),
            history_files.ACCOUNTS: (history_files.ACCOUNT_FIELDS,
                                       [{**r, "status": LIVE} for r in statements])}


# =====================================================================================
# THE BENCH RECORD AND THE JOURNAL
# =====================================================================================

def _bench_item(T: dict) -> dict:
    """The last contract note, worked through the bench: read by a Claude session
    (`desk/intake/propose.py`), approved and written (`desk/doors/commit.py`)."""
    row = next(r for r in T["exits"] if r.get("_benched"))
    note = row["_note"]
    day = row["date"]
    instant = f"{day} {note['time']}"
    why = next(r["why_exited"] for r in T["reasoning"]
               if r["ticker"] == row["ticker"] and r["date"] == day)
    line = f"{row['qty']:,} {row['price']:.2f} {row['proceeds']:,.2f}"
    values = {k: _cell(row[k]) for k in ("eid", "date", "account", "ticker", "qty", "price", "cur",
                                         "proceeds", "source", "broker_ref", "realisation")}
    ev = D.EVIDENCE_BY_KEY["ii-contract-note"]
    return {
        "id": BENCH_ID,
        # One per save (`bench.save()`): opened for the note, read by a session, the why typed.
        "revision": 3,
        "created": f"{day}T{note['time']}:40",
        "state": "archived",
        "origin": "document",
        "title": BENCHED_AS,
        "document": {"name": BENCHED_AS},
        "evidence_class": ev.key,
        "evidence": {"dated": day, "authority": ev.authority, "reference": note["ref"]},
        "why": {"why_entered": "", "why_exited": why},
        "rows": [{"table": "exits", "values": values,
                  "sources": {"date": f"DATE {_ddmmyyyy(day)} TIME {note['time']}",
                              "qty": line, "price": line, "proceeds": line,
                              "broker_ref": f"CONTRACT No. {note['ref']}"},
                  "derived": ["account", "eid", "realisation"], "machine": True, "drafted": []}],
        "recognised": {"name": BENCHED_AS, "classes": [ev.key], "instant": instant,
                       "instant_from": "document", "reference": note["ref"], "encoding": None,
                       "scanned": False, "why": ""},
        "proposed": {"at": f"{day}T{note['time']}:52", "by": "a Claude session",
                     "document": BENCHED_AS, "kind": "ii contract note", "not_found": [],
                     "dropped": [], "directives": []},
        "written_at": WRITTEN_AT,
        "written_to": {"exits": 1},
        "reasoning_written": {row["ticker"]: {"date": day, "why_exited": why}},
        "document_archived_to": f"_archive/statements/{_note_name(row, note)}",
    }


WRITTEN_AT = "2026-08-12T10:03:15"


def _journal(T: dict, item: dict) -> list[dict]:
    """Every table's count when the journal opened, then each write, oldest first."""
    after = {"quarter-results": sum(1 for r in T["quarter-results"] if r.get("note") == RESTATED)}
    opened = [{"at": OPENED, "route": "baseline", "op": "open", "table": t,
               "rows": len(T[t]) - after.get(t, 0), "detail": "rows on file when the journal opened"}
              for t in schema.TABLES if t != "journal"]
    writes = []
    for as_of in ("2026-03-31", "2026-06-30", "2026-08-12", "2026-09-30"):
        if as_of == item["written_at"][:10]:
            writes += [{"at": item["written_at"], "route": "bench", "op": "append",
                        "table": "exits", "rows": 1, "ref": item["id"], "detail": item["title"]},
                       {"at": item["written_at"], "route": "bench", "op": "append",
                        "table": "reasoning", "rows": 1, "ref": item["id"],
                        "detail": "why for " + ", ".join(item["reasoning_written"])}]
            continue
        for table in ("quarter-snapshots", "quarter-nav", "quarter-results"):
            n = sum(1 for r in T[table] if r["as_of"] == as_of and r.get("note") != RESTATED)
            writes.append({"at": f"{as_of}T17:30:00", "route": "freeze", "op": "append",
                           "table": table, "rows": n, "ref": as_of,
                           "detail": f"{n} row(s) freezing {as_of}, from the engine"})
    writes.append({"at": "2026-10-13T20:31:10", "route": "hand", "op": "append",
                   "table": "quarter-results", "rows": after["quarter-results"],
                   "ref": "restatement 2026-10-13",
                   "detail": f"restatements of the three closed quarters, "
                             f"{after['quarter-results']} rows: the return is day-weighted, so "
                             f"every return on a quarter with a flow moves and nothing else does"})
    return opened + writes


# =====================================================================================
# WRITING IT DOWN
# =====================================================================================

def _cell(value) -> str:
    """A value as the store writes it: blank for a gap, never zero."""
    return "" if value is None else str(value)


def _csv(header: list[str], rows: list[dict], table: str | None = None) -> str:
    """The rows as CSV, cells in `header` order. A key the header lacks is refused, never
    dropped; a record table's every cell is parsed as the loader will parse it."""
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator="\n")
    out.writerow(header)
    fields = schema.TABLES[table].fields if table else None
    for i, row in enumerate(rows, 1):
        stray = set(row) - set(header)
        if stray:
            raise ValueError(f"{table or header}: row {i} has no column for {sorted(stray)}")
        cells = [_cell(row.get(c)) for c in header]
        for field, cell in zip(fields or (), cells):
            schema._parse(field, cell, table, i)
        out.writerow(cells)
    return buf.getvalue()


def _ddmmyyyy(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def _note_name(row: dict, note: dict) -> str:
    """The name `rules.ARCHIVE_CONVENTION` gives the note: date, instant, authority, number,
    what it covers."""
    import datetime as dt
    day = dt.date.fromisoformat(row["date"])
    authority = D.EVIDENCE_BY_KEY["ii-contract-note"].authority
    return f"{day:%d %b %Y} {note['time'].replace(':', '.')} {authority} {note['ref']} ({row['ticker']}).pdf"


def _note_lines(row: dict, note: dict, account_number: str, side: str) -> list[str]:
    """What an invented ii contract note prints, in the order ii prints it. Its fingerprint, its
    number line and its dealing line are what `rules` reads; the rest makes it a document."""
    usd = row.get("cur") == "USD"
    qty, price = row["qty"], row["price"]
    gross = qty * price
    sterling = row.get("val", row.get("proceeds"))
    commission = note["commission"]
    amount = f"{gross:,.2f} {'USD' if usd else 'GBP'}"
    lines = [
        "INVENTED FOR THE DEMO BOOK - no such deal was made",
        "MS NIA VOSS",
        f"We thank you for your instructions and have today {side}",
        *note["security"],
        "Type of trade Market",
        "QUANTITY PRICE AMOUNT",
        f"{qty:,} {price:.2f} {amount}",
    ]
    if usd:
        lines.append(f"Exchange rate {row['rate']} USD/GBP")
    lines += [
        f"TOTAL {sterling:,.2f} GBP",
        f"Commission {commission:.2f} GBP",
        "Account Number Contract No Settlement Date Amount",
        f"{account_number} {side} {note['ref']} {note['settles']} {sterling:,.2f} GBP",
        f"ACCOUNT NUMBER {account_number}",
        f"CONTRACT No. {note['ref']}",
        f"SETTLEMENT DATE {note['settles']}",
        f"DATE {_ddmmyyyy(row['date'])} TIME {note['time']}",
        "Brokerage services by an invented firm, for the demo book alone.",
        "Financial Services Register Firm Reference Number 141282.",
    ]
    return lines


def _statement_name(day: str) -> str:
    """An IG statement is retrieved by its date, so its name carries the account it is for."""
    import datetime as dt
    authority = D.EVIDENCE_BY_KEY["ig-statement"].authority
    return f"{dt.date.fromisoformat(day):%d %b %Y} {authority} ({SPREAD}).pdf"


def _statement_lines(day: str, rows: list[dict], account_number: str) -> list[str]:
    """An invented IG statement of one day: the legs opened on it, each under its deal id, its
    stake in pounds per point and its opening level, as IG states them."""
    import datetime as dt
    lines = ["INVENTED FOR THE DEMO BOOK - no such statement was issued",
             f"Statement for account {account_number}, {dt.date.fromisoformat(day):%d %B %Y}",
             "Opening positions",
             "Date Deal ID Market Direction Size Opening level"]
    for row in rows:
        lines.append(f"{_ddmmyyyy(row['date'])} {row['broker_ref']} {row['contract']} Buy "
                     f"{row['stake']} {row['val']}")
    return lines


def _pdf(lines: list[str]) -> bytes:
    """A one-page PDF of these lines in Helvetica, built by hand so a run is byte for byte the
    same: no producer, no dates, no identifiers. pypdf reads it back line by line."""
    def text(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    body = "BT /F1 10 Tf 14 TL 50 800 Td\n" + "".join(
        f"({text(ln)}) Tj T*\n" for ln in lines) + "ET\n"
    stream = body.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def build(into: pathlib.Path) -> list[str]:
    """Write the demo book's store and archive under `into`. Returns the paths written,
    relative to it."""
    T = _book()
    noted, stated = _settle(T)
    item = _bench_item(T)
    for row in T["trades"] + T["exits"]:
        for key in [k for k in row if k.startswith("_")]:
            del row[key]
    histories = _histories()
    T["journal"] = _journal(T, item)
    written = []

    def put(rel: str, data: bytes | str) -> None:
        path = into / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        written.append(rel)

    for table, spec in schema.TABLES.items():
        put(f"store/{spec.path.name}", _csv(spec.header, T[table], table))
    for name, (fields, rows) in histories.items():
        put(f"store/{name}", _csv(fields, rows))

    numbers = {a["account"]: a["number"] for a in T["accounts"]}
    for side, row, note in noted:
        put(f"_archive/statements/{_note_name(row, note)}",
            _pdf(_note_lines(row, note, numbers[row["account"]], side)))
    for day, rows in stated.items():
        put(f"_archive/statements/{_statement_name(day)}",
            _pdf(_statement_lines(day, rows, numbers[SPREAD])))

    put(f"_archive/bench/{item['id']}.json", json.dumps(item, indent=2, ensure_ascii=False) + "\n")
    return sorted(written)


def main(argv: list[str]) -> int:
    into = pathlib.Path(argv[argv.index("--into") + 1]).resolve() if "--into" in argv else None
    if into:
        build(into)
        return 0
    # WRITTEN ASIDE, THEN SWAPPED IN: a run that fails part way leaves demo/ as it was.
    with tempfile.TemporaryDirectory(prefix="demo-") as tmp:
        build(pathlib.Path(tmp))
        for part in ("store", "_archive"):
            shutil.rmtree(DEMO / part, ignore_errors=True)
            shutil.copytree(pathlib.Path(tmp) / part, DEMO / part)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
