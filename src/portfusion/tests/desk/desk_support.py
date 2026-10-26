"""What more than one file in tests/desk/ uses: the helpers and the constants they share.

The fixtures built on them, `item`, `workbench` and `inbox`, are in `tests/harness.py`. A test
imports from here by name, never by star, because a helper whose name starts with an underscore
is not exported by `import *`.
"""
from __future__ import annotations

from portfusion.record import schema

from harness import SRC, an_account, free_id


#: An invented ii GBP ledger, in ii's shape, BOM and all: `test_read_rows` reads it, and
#: `test_intake` opens it on the bench.
LEDGER = (
    "﻿﻿Date,Settlement Date,Symbol,Sedol,Quantity,Price,Description,Reference,"
    "Debit,Credit,Running Balance\n"
    "25/02/2025,25/02/2025,n/a,n/a,n/a,n/a,Gross interest to 24/02/25,n/a,n/a,£1.50,£950.00\n"
    "14/01/2025,16/01/2025,QNLR,B000000,1500,£0.045,1500 QUENLAN ROBOTICS  Del     .04 S Date "
    "16/01/25,12345ABC123,n/a,£67.50,£948.50\n"
    '02/02/2025,02/02/2025,n/a,n/a,n/a,n/a,PAYMENT Q0000000000000 N VOSS,n/a,"£2,200.00",n/a,'
    "£200.00\n"
    "11/01/2025,11/01/2025,n/a,n/a,n/a,n/a,Fee Transfer,n/a,£12.50,n/a,£400.00\n"
    "10/02/2025,10/02/2025,KELS,B000001,n/a,n/a,Div 1000   KELSTRAND FOODS   ORD GBP0.01,n/a,"
    "n/a,£40.00,£245.00\n"
    "12/02/2025,12/02/2025,ZQX,B000002,n/a,n/a,Div 500   ZEQUAX MINING   ORD,n/a,n/a,£5.00,"
    "£250.00\n"
    "01/02/2025,01/02/2025,n/a,n/a,n/a,n/a,Transfer in from somewhere,n/a,n/a,£5.00,£205.00\n"
)


def _rows(table):
    return [dict(zip(schema.TABLES[table].header, r)) for r in schema.load(table)]


def to_crlf(*tables) -> None:
    """Rewrite these tables of a COPIED store in CRLF. The store is LF; a door must
    still write a file back in the ending it found, or every line shows as changed."""
    for t in tables:
        path = schema.TABLES[t].path
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))


def all_crlf(table) -> bool:
    """Does every line of this table end CRLF?"""
    raw = schema.TABLES[table].path.read_bytes()
    return raw.count(b"\n") == raw.count(b"\r\n") > 0


# THE LOADED BOOK'S OWN NAMES, derived once. The register's vocabulary is closed — a door
# rightly refuses an account or a ticker the book does not hold — so a fixture that typed
# this repo's names could only ever commit on this repo's book. The first account of each
# kind, and a line the book holds directly, serve any book the suite is pointed at.
SHARES_ACCOUNT = an_account("shares")
SPREAD_BET_ACCOUNT = an_account("spread bet")
_DIRECT = next((s for s in _rows("securities") if s["held_as"] == "shares"), None)
SYNTHETIC_TICKER = next((s["ticker"] for s in _rows("securities") if s["held_as"] == "spread bet"),
                        None)

# A REFERENCE THAT IS NOT IN THE REAL RECORD. A real contract note's reference — one really in
# sales.csv — fires the "already in the record" gate on every fixture that uses it, and the gate
# is right: the suite would be quietly asserting against evidence the book already holds.
GOOD_TRADE = {
    "trade_id": free_id("buys"), "date": "2026-09-01", "source": "ii contract note 01 Sep 2026",
    "account": SHARES_ACCOUNT,
    "ticker": (_DIRECT or {}).get("ticker"), "cur": (_DIRECT or {}).get("currency"), "qty": "10",
    "stake": "", "cost": "3197.00", "broker_ref": "TESTREF1",
    "note": "n",
}


GOOD_CLASS = "ii-contract-note"
GOOD_DOCUMENT = "Contract_Note_TESTREF1.pdf"
GOOD_EVIDENCE = {"dated": "2026-09-01", "authority": "ii contract note", "reference": "TESTREF1"}


def _ready(item, **over):
    item["evidence"] = dict(GOOD_EVIDENCE)
    item["why"] = {"why_entered": "Entered on the services margin story, which the hardware "
                                 "cycle masks.", "why_exited": ""}
    item["rows"] = [{"table": "buys", "values": dict(GOOD_TRADE, **over)}]
    return item


def _static(name):
    return (SRC / "desk" / "static" / name).read_text()
