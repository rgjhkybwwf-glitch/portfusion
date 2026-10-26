"""
ROWS READ FROM A RECOGNISED DOCUMENT.

`desk/intake/read_rows.py` exists so a document whose columns the record already knows is read from its
own named cells rather than transcribed by a model and checked back against the page. There is
nothing to verify when the value IS the cell — the check `verify.py` performs on a proposed cell
would be proving what we started from.

These fixtures are shaped like HL's exports, in CP1252, which is what HL writes; every
figure in them is invented. If a column header changes, these fail and the column map is what wants looking at.
"""
import pytest

from portfusion.record import schema
from portfusion.desk.intake import read_document, read_rows, recorded

from harness import an_account, holds

# THE DOCUMENT SHAPES ARE HL'S EXPORTS, in CP1252, with invented rows. The CLIENT
# NUMBER inside them is the loaded register's own, so the reader's number-to-account
# resolution is exercised on whichever book is loaded rather than wired to one account.
_HDR = schema.TABLES["accounts"].header
SHARE_ACCOUNT = an_account("shares")
_CLIENT = next((r[_HDR.index("number")] for r in schema.load("accounts")
                if r[_HDR.index("account")] == SHARE_ACCOUNT), None)
pytestmark = holds(_CLIENT, what="a share account")

INCOME = (
    "Income transactions for my HL Stocks & Shares ISA during 2025\n"
    f"Client Number:,{_CLIENT}\n"
    "Valuation as at,03-03-2025 14:05\n"
    "\n"
    "Date,Type,Description,Amount\n"
    '"18/02/2025","OVR CR","Kelstrand Foods Ordinary Dividend Payment","120.00"\n'
    '"09/02/2025","INTEREST","Interest From 10/01/2025 TO 09/02/2025","0.50"\n'
    '"Total income received over selected period","","","120.50"\n'
)

TRANSACTIONS = (
    "Portfolio Summary\n"
    f"Client Number:,{_CLIENT}\n"
    "Valuation as at,03-03-2025 14:10\n"
    "\n"
    "Trade date,Settle date,Reference,Description,Unit cost (p),Quantity,Value (£)\n"
    '"19/02/2025","18/02/2025","OVR CR","Kelstrand Foods Dividend Payment",'
    '"n/a","300.000000","120.00"\n'
    '"14/01/2025","16/01/2025","B000000001","Tarnwell Hotels Ordinary Shares 40 @ 512.25",'
    '"512.250000","40.000000","-204.90"\n'
    '"14/01/2025","14/01/2025","DRI0000001","Dividend Transfer From Acc 00X0000000000",'
    '"n/a","n/a","60.00"\n'
)


@pytest.fixture
def on_the_workbench(inbox, monkeypatch):
    """A document on a workbench, and an EMPTY record behind it.

    The suppression is stubbed out here on purpose. These tests are about reading a document,
    and leaving the live record wired in makes them fail the day a fixture's dividend is
    entered for real, reporting one row instead of two. What the suppression does has its own test,
    with the matcher stubbed the other way.
    """
    monkeypatch.setattr(recorded, "matching_row", lambda table, values: None)
    def put(name, body):
        (inbox / name).write_bytes(body.encode("cp1252"))
        return name
    return put


def test_a_line_already_in_the_record_is_reported_and_not_read_again(inbox, monkeypatch):
    """HL'S EXPORTS OVERLAP BY DESIGN. The income list and the Income-side transaction list
    carry the same dividends, so without this the second document worked would offer every
    row the first one entered.

    AND IT ONLY WORKS IF THE DATES AGREE. The gate keys on (date, account, category, amount),
    so a dividend the book holds at a date HL does not use is offered again as new.
    """
    monkeypatch.setattr(recorded, "matching_row", lambda table, values: "an existing row")
    (inbox / "income.csv").write_bytes(INCOME.encode("cp1252"))

    out = read_rows.read("income.csv")
    assert out["rows"] == [], "a row already in the record was read again"
    assert len(out["seen"]) == 2
    assert all(s["in_record"] == "an existing row" for s in out["seen"])
    assert all("already in the record" in s["why"] for s in out["seen"])


def test_every_value_comes_from_a_named_cell(on_the_workbench):
    """The whole argument for this module. Each cell is lifted from a column the map names, so
    it is right by construction — there is no quote to match back to the page because the row
    IS the page."""
    out = read_rows.read(on_the_workbench("income.csv", INCOME))
    assert out["class"] == "hl-income"
    assert out["account"] == SHARE_ACCOUNT, "the client number did not resolve to an account"
    assert out["reference"] == "3 Mar 2025 14:05"
    assert len(out["rows"]) == 2, out["rows"]

    div = next(r for r in out["rows"] if r["values"]["category"] == "Dividend")
    assert div["values"]["date"] == "2025-02-18"
    assert div["values"]["amount"] == "120.00"
    assert "Kelstrand Foods" in div["values"]["detail"]
    # Every filled cell names the document line it was lifted from.
    assert set(div["sources"]) == set(div["values"])

    interest = next(r for r in out["rows"] if r["values"]["category"] == "Cash interest")
    assert interest["values"]["date"] == "2025-02-09"


def test_the_total_line_is_not_a_row(on_the_workbench):
    """HL ends its income export with a total whose Date column holds a sentence. A row without
    a readable date and a code is not an entry."""
    out = read_rows.read(on_the_workbench("income.csv", INCOME))
    assert all(r["values"]["amount"] != "120.50" for r in out["rows"]), \
        "the document's own total was read as an income row"
    assert not out["unrecognised"], out["unrecognised"]


def test_a_dividend_takes_its_SETTLE_date_so_both_documents_agree(on_the_workbench):
    """HL dates a dividend twice on the transaction export and once on the income export, and
    the one date it gives is the SETTLE date. Taking the trade date would date one payment two
    ways depending which document it was read from — and the duplicate gate keys on the date,
    so the same dividend would enter twice with nothing noticing."""
    a = read_rows.read(on_the_workbench("income.csv", INCOME))
    b = read_rows.read(on_the_workbench("transactions.csv", TRANSACTIONS))
    seen_a = {(r["values"]["date"], r["values"]["amount"]) for r in a["rows"]}
    seen_b = {(r["values"]["date"], r["values"]["amount"]) for r in b["rows"]}
    assert ("2025-02-18", "120.00") in seen_a and ("2025-02-18", "120.00") in seen_b, \
        f"the two documents date one dividend differently: {seen_a} vs {seen_b}"


def test_an_internal_transfer_is_reported_and_never_entered(on_the_workbench):
    """It changes no figure this book holds, and it appears on BOTH transaction lists under one
    reference — once negative, once positive. Entering it from both sides books it twice."""
    out = read_rows.read(on_the_workbench("transactions.csv", TRANSACTIONS))
    assert all("DRI" not in str(r["values"].get("detail", "")) for r in out["rows"]), \
        "a sub-account transfer became a row"
    transfer = next(s for s in out["seen"] if "DRI0000001" in s["line"])
    assert "not an event" in transfer["why"]


def test_a_dealing_line_is_reported_with_whether_the_book_has_it(on_the_workbench):
    """STRONGER THAN PROPOSING IT. The reference is what the record already stores, so the
    report can answer "is this in the book" instead of offering a row that the duplicate gate
    then has to catch. B000000001 is HL's deal-reference shape and deliberately in no book,
    so the honest answer here is "no" — and a dealing line is never proposed as a row."""
    out = read_rows.read(on_the_workbench("transactions.csv", TRANSACTIONS))
    deal = next(s for s in out["seen"] if "B000000001" in s["line"])
    assert (deal["in_record"] or "") == "", \
        f"the reader claims the book holds a reference no book holds: {deal}"
    assert all(r["table"] == "income" for r in out["rows"]), \
        "a dealing line was proposed rather than reported"


def test_an_unrecognised_document_yields_nothing_and_says_so(on_the_workbench):
    out = read_rows.read(on_the_workbench("mystery.csv", "a,b,c\n1,2,3\n"))
    assert out["class"] == "" and out["rows"] == [] and out["ambiguous"] == []


# =====================================================================================
# AN ii LEDGER — read here, never sent.
#
# An invented ii GBP ledger in ii's shape. ii prints no transaction code and no client number on a SIPP ledger, so a line is known by how
# its Description begins and the account by the rows its lines already match.
# =====================================================================================

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


@pytest.fixture
def ledger(inbox, monkeypatch):
    """The ledger on a workbench, with the record behind it stubbed: the account is decided by
    the contract note its dealing line settled, and the account keeps GBP cash only."""
    monkeypatch.setattr(recorded, "matching_row", lambda table, values: None)
    monkeypatch.setattr(read_rows, "_in_record", lambda ref: "sales" if ref == "ABC123" else "")
    monkeypatch.setattr(recorded, "accounts_citing",
                        lambda ref: {"Voss ii Trading"} if ref == "ABC123" else set())
    monkeypatch.setattr(recorded, "cash_currencies", lambda account: {"GBP"})
    # The register holds KELS.L and QNLR and nothing for ZQX, whichever book is loaded.
    monkeypatch.setattr(read_rows.D, "SECURITIES", [("KELS.L",), ("QNLR",)])
    (inbox / "ledger.csv").write_text(LEDGER, encoding="utf-8")
    return "ledger.csv"


def test_an_ii_ledger_is_read_line_by_line_by_how_each_description_begins(ledger):
    out = read_rows.read(ledger)
    assert out["class"] == "ii-transactions"
    assert out["account"] == "Voss ii Trading", "the dealing line's contract note names the account"
    assert out["reference"] == "GBP 11 Jan-25 Feb 2025", "the currency and the lines' own span"
    rows = {(r["table"], r["values"].get("category", "")): r["values"] for r in out["rows"]}
    assert rows[("income", "Cash interest")]["amount"] == "1.50"
    assert rows[("income", "Fee")]["amount"] == "-12.50", "a fee is a negative income row"
    assert rows[("capital-movements", "")]["amount"] == "-2200.00"
    # A DIVIDEND IS READ BY ITS DESCRIPTION, though its line names a Symbol as a deal's does, and
    # its ticker is that Symbol's code in the book — blank where the book registers none.
    divs = [r["values"] for r in out["rows"] if r["values"].get("category") == "Dividend"]
    assert [(d["amount"], d.get("ticker", "")) for d in divs] == [("40.00", "KELS.L"),
                                                                   ("5.00", "")], divs
    assert rows[("income", "Cash interest")]["date"] == "2025-02-25"
    # THE DEALING LINE IS REPORTED AGAINST ITS CONTRACT NOTE, never entered from the ledger.
    dealing = [s for s in out["seen"] if "ABC123" in s["line"]]
    assert dealing and dealing[0]["in_record"] == "sales"
    # A LINE IT DOES NOT KNOW IS LEFT FOR A PERSON, never guessed.
    assert any("Transfer in from somewhere" in u for u in out["unrecognised"])


def test_a_gbp_only_accounts_closing_balance_is_its_cash(ledger):
    out = read_rows.read(ledger)
    cash = [r["values"] for r in out["rows"] if r["table"] == "cash-readings"]
    assert cash and cash[0]["cash"] == "950.00", "the newest line's running balance"


def test_an_account_with_other_currency_cash_gets_no_cash_row_from_one_ledger(ledger, monkeypatch):
    """An account paid interest in EUR holds EUR cash: a GBP ledger's balance is half of it."""
    monkeypatch.setattr(recorded, "cash_currencies", lambda account: {"GBP", "EUR"})
    out = read_rows.read(ledger)
    assert not [r for r in out["rows"] if r["table"] == "cash-readings"]
    assert any("EUR" in s["why"] for s in out["seen"])


def test_a_ledger_in_another_currency_is_left_for_a_person(inbox, monkeypatch):
    """A EUR line needs the day's rate to become a row; a rate from the wrong day is the error
    `rules.FX_RATE_AGE_LIMIT_DAYS` describes. So nothing is proposed and every line says why."""
    monkeypatch.setattr(recorded, "matching_row", lambda table, values: None)
    (inbox / "eur.csv").write_text(LEDGER.replace("£", "€"), encoding="utf-8")
    out = read_rows.read("eur.csv")
    assert out["rows"] == [] and len(out["unrecognised"]) == 7
    assert all("EUR ledger" in u for u in out["unrecognised"])


def test_the_ii_ledger_rules_are_literal_prefixes():
    from portfusion.record import rules as D
    assert D.ii_line("GROSS INTEREST", "n/a").category == "Cash interest", "case aside"
    assert D.ii_line("Div 1000 KELSTRAND FOODS", "KELS").category == "Dividend", \
        "a dividend's line names its security, and is no deal"
    assert D.ii_line("anything at all", "QNLR") is D.II_DEALING
    assert D.ii_line("Interest adjustment", "n/a") is None, "a prefix, not a keyword search"
    assert D.ii_contract_number("12345ABC123") == "ABC123"


def test_a_documents_download_time_is_uk_time_wherever_the_mac_is(inbox, monkeypatch):
    """A DOCUMENT THAT STATES NO INSTANT IS DATED BY ITS DOWNLOAD TIME, read as UK wall-clock time
    the way its own would be. A Mac in New York reads a 13:00 London download as 13:00, never
    08:00."""
    import calendar
    import datetime as dt
    import os
    import time
    doc = inbox / "export.csv"
    doc.write_text("x\n", encoding="utf-8")
    noon_utc = calendar.timegm((2026, 7, 1, 12, 0, 0))     # 13:00 in London, summer time
    os.utime(doc, (noon_utc, noon_utc))
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:
        assert read_document.modified("export.csv") == dt.datetime(2026, 7, 1, 13, 0)
    finally:
        monkeypatch.undo()
        time.tzset()


def test_one_coincidence_does_not_name_a_ledgers_account(monkeypatch):
    """AN ii LEDGER THAT PRINTS NO CLIENT NUMBER is given an account from its lines that match
    rows on file. One match may be a coincidence of pennies on a day, so it takes two lines
    agreeing, or a dealing line, and anything less is left blank for a person."""
    import datetime as dt
    from portfusion.record import rules as D
    monkeypatch.setattr(recorded, "accounts_of_broker", lambda broker: ["Account A", "Account B"])
    monkeypatch.setattr(D, "ii_line", lambda desc, symbol: D.BrokerCode("income", "Cash interest", ""))

    def line(day):
        return {"desc": "interest", "symbol": "", "ref": "", "when": dt.date(2026, 9, day),
                "cells": {"Credit": "1.00", "Debit": "n/a"}}
    on_file = set()
    monkeypatch.setattr(recorded, "matching_row",
                        lambda table, v: "row" if (v["account"], v["date"]) in on_file else None)
    on_file |= {("Account A", "2026-09-01")}
    assert read_rows._ii_account([line(1), line(2)]) == "", "one match named the account"
    on_file |= {("Account A", "2026-09-02")}
    assert read_rows._ii_account([line(1), line(2)]) == "Account A"
    on_file |= {("Account B", "2026-09-02")}
    assert read_rows._ii_account([line(1), line(2)]) == "", "two accounts matched, one was named"


def test_a_utf16_export_is_read_as_utf16(tmp_path):
    """A SPREADSHEET SAVED AS UTF-16 starts with its byte-order mark. cp1252 takes any byte, so the
    mark is read first, or each letter would carry a NUL."""
    doc = tmp_path / "export.csv"
    doc.write_bytes("Symbol,Qty\nWEND,100\n".encode("utf-16"))
    got = read_document.extract_file(doc)
    assert "Symbol,Qty" in got["text"] and "\x00" not in got["text"], got["text"][:40]
