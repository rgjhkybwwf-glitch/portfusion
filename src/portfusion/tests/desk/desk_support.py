"""What more than one file in tests/desk/ uses: the helpers and the constants they share.

The fixtures built on them, `item`, `workbench` and `inbox`, are in `tests/conftest.py`. A test
imports from here by name, never by star, because a helper whose name starts with an underscore
is not exported by `import *`.
"""
from __future__ import annotations

from portfusion.record import schema

from harness import SRC, an_account, free_id


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
_DIRECT = next((s for s in _rows("securities") if s["kind"] == "shares"), None)
SYNTHETIC_TICKER = next((s["code"] for s in _rows("securities") if s["kind"] == "spread bet"),
                        None)

# A REFERENCE THAT IS NOT IN THE REAL RECORD. A real contract note's reference — one really in
# exits.csv — fires the "already in the record" gate on every fixture that uses it, and the gate
# is right: the suite would be quietly asserting against evidence the book already holds.
GOOD_TRADE = {
    "id": free_id("trades"), "date": "2026-09-01", "source": "ii contract note 01 Sep 2026",
    "account": SHARES_ACCOUNT,
    "ticker": (_DIRECT or {}).get("code"), "cur": (_DIRECT or {}).get("currency"), "qty": "10",
    "stake": "", "val": "3197.00", "broker_ref": "TESTREF1",
    "note": "n",
}


GOOD_CLASS = "ii-contract-note"
GOOD_DOCUMENT = "Contract_Note_TESTREF1.pdf"
GOOD_EVIDENCE = {"dated": "2026-09-01", "authority": "ii contract note", "reference": "TESTREF1"}


def _ready(item, **over):
    item["evidence"] = dict(GOOD_EVIDENCE)
    item["why"] = {"why_entered": "Entered on the services margin story, which the hardware "
                                 "cycle masks.", "why_exited": ""}
    item["rows"] = [{"table": "trades", "values": dict(GOOD_TRADE, **over)}]
    return item


def _static(name):
    return (SRC / "desk" / "static" / name).read_text()
