"""
ROWS FROM A RECOGNISED DOCUMENT — read from its own named cells, never interpreted.

`read_document.py` gets a document's TEXT. This gets its ROWS, and only for a document the
record recognises: `rules.identify()` names the class, `rules.COLUMN_MAPS` says which column is
which, and `rules.hl_code()` says what each line is.

WHY THIS EXISTS BESIDE `propose.py` RATHER THAN INSTEAD OF IT. A Claude session reads anything
and has to be checked: every proposed cell carries a verbatim quote, and `verify.py` matches that
quote back to the document before it reaches the screen. That check is what makes the proposal
legal, and it is real work. But on a document whose columns we already know, there is nothing to
check — the value IS the cell, and matching a quote back to the page would be proving something
we started from. So a recognised document is read here, with nothing to verify; anything
unrecognised is read by a session through `propose.py`.

IT RUNS WHEN THE DOCUMENT IS OPENED: a download need not be sent anywhere to be read. Built
on 9 Sep, it was never connected, so every CSV went to the model; `bench.read_here()` now calls
it for any class in `LOCAL`, and a proposal is asked for only for the rest.

IT PRODUCES THE SAME ROW SHAPE. `table`, `values`, `sources`, `machine` — so the gates, the
duplicate check and `commit.py` never learn there were two ways in.

WHAT IT WILL NOT DO:

  · GUESS A TICKER. HL writes a purchase as "Kelstrand Foods plc Ordinary Shares 40 @ 512.250000", and
    turning a company's prose name into a code is the judgement this module exists to avoid. A
    dealing line is REPORTED with its reference instead — which is stronger than proposing it,
    because the reference is what the record already stores, so the report can say whether the
    book has that line already.
  · ENTER AN INTERNAL TRANSFER. A movement between an ISA's Capital and Income sub-accounts
    changes no figure this book holds and appears on both lists under one reference. It is
    reported as seen, with the reason, and archived with the item.
  · INVENT AN ACCOUNT. The client number in the document is matched against the record; two
    matches or none leaves the cell empty for a person.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import re

from portfusion.record import rules as D
from portfusion.desk.intake import read_document


def _cells(text: str, header: tuple) -> tuple[list, list]:
    """The document's rows below its header, and the header as the document writes it.

    MATCHED ON THE FIRST COLUMN NAME, not on the whole row: HL pads a header with empty cells
    (`Account,Stock value,...,` with a trailing comma) and a strict comparison would miss it.
    """
    rows = list(csv.reader(io.StringIO(text)))
    for i, row in enumerate(rows):
        cleaned = [c.strip() for c in row]
        if cleaned and cleaned[0] == header[0] and len(cleaned) >= len(header):
            return rows[i + 1:], cleaned
    return [], []


def _value(row: list, header: list, name: str) -> str:
    """One named cell, or "" — a column the document does not carry is not an error here."""
    # STARTSWITH, because a broker labels a money column with its currency: HL writes
    # "Value (£)" where the map says "Value", and pinning the currency symbol into the map
    # would make it a CP1252 question rather than a naming one.
    for i, col in enumerate(header):
        if col == name or col.startswith(name):
            return row[i].strip() if i < len(row) else ""
    return ""


def _labelled(text: str, label: str) -> str:
    """The value beside a labelled cell in a document's header block, or "".

    A broker writes its headline figures as `Total cash:,1,000.00` rather than in a table, so this
    is the header-block equivalent of `_value()` — the first non-empty cell after the label.
    """
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if cells and cells[0] == label:
            return next((c for c in cells[1:] if c), "")
    return ""


def _number(text: str) -> str:
    """A money cell as the store holds it. Separators and symbols out, sign kept."""
    return text.replace(",", "").replace("£", "").replace("$", "").replace("€", "").strip()


def holdings(text: str, key: str) -> dict[str, float]:
    """UNITS PER HOLDING off a holdings export, keyed by the record's own ticker.

    `rules.HOLDINGS_COLUMNS` says which two columns; a class it does not name lists no units and
    returns {}. Read from the named cells like everything else here, never interpreted.

    Side effects: none.
    """
    cols = D.HOLDINGS_COLUMNS.get(key)
    if cols is None:
        return {}
    body, header = _cells(text.lstrip("\ufeff"), cols)
    out: dict[str, float] = {}
    for row in body:
        code, units = _value(row, header, cols[0]), _number(_value(row, header, cols[1]))
        if not code or not units:
            continue                     # a totals line, a blank, or the notes under the table
        try:
            n = float(units)
        except ValueError:
            continue
        ticker = D.book_code(code, (r[0] for r in D.SECURITIES))
        out[ticker] = out.get(ticker, 0.0) + n
    return out


#: THE CLASSES READ HERE, and so never given to a reader. Derived from the maps that read them.
LOCAL = frozenset(D.COLUMN_MAPS) | frozenset(D.HOLDINGS_COLUMNS) | {"ii-transactions"}

#: A currency as ii writes it in a money cell.
_II_SYMBOLS = {"£": "GBP", "€": "EUR", "$": "USD"}


def read(name: str) -> dict:
    """Rows this document states, and every line it does not.

    Returns {class, rows, seen, unrecognised, account, instant}. `seen` is the audit half and is
    the point of the exercise as much as `rows` are: a line that was read and deliberately not
    entered has to be visible, or the next person to open this document wonders whether it was
    missed.

    Side effects: none. It reads a file and returns; `bench.save()` is what writes.
    """
    doc = read_document.extract(name)
    text = doc.get("text") or ""
    classes = D.identify(text)
    out = {"class": classes[0] if len(classes) == 1 else "", "rows": [], "seen": [],
           "unrecognised": [], "account": "", "instant": None, "reference": "",
           "ambiguous": classes if len(classes) > 1 else []}
    if len(classes) != 1:
        return out

    key = classes[0]
    # THE DOCUMENT'S OWN INSTANT, ELSE WHEN IT WAS DOWNLOADED — ii's exports state none.
    inst = D.document_instant(text) or read_document.modified(name)
    out["instant"] = inst.isoformat(sep=" ", timespec="minutes") if inst else None
    # THE REFERENCE IS THE INSTANT, IN THE RECORD'S OWN DATE STYLE — "1 Mar 2026 09:30", not
    # ISO. `rules.archive_reference()` reads the date back out of a source line in the shape
    # `ARCHIVE_CONVENTION` leads with, so an ISO reference would compose a line the evidence
    # chain could not resolve.
    out["reference"] = f"{inst:%-d %b %Y %H:%M}" if inst else ""

    from portfusion.desk.intake import propose
    # A PAIR, and only the first half is the account. `account_from()` returns the name and the
    # line it was found on, so the derivation stays checkable; taking the tuple whole put a
    # Python repr into a store cell.
    found = propose.account_from(text)
    out["account"] = found[0] if found else ""

    if key == "ii-transactions":
        return _ii_ledger(text, out)
    if key in D.HOLDINGS_COLUMNS:
        _holdings_reading(text, key, out)
        if key == "ii-valuation":
            return out

    cmap = D.COLUMN_MAPS.get(key)
    if cmap is None:
        # NOT EVERY DOCUMENT IS A LIST OF LINES. A valuation is a header block of labelled
        # totals with a holdings table under it, and the one row the record takes from it is the
        # cash: `Total cash:` is the account's own figure at the instant stated, which is half
        # of what a share account reconciles on.
        if key == "hl-valuation":
            cash = _labelled(text, "Total cash:")
            if cash and out["account"]:
                # The row's columns and no more: cash-readings carries its provenance
                # as evidence + reference, and a stray "source" key is refused at commit —
                # the column left the schema and this writer had kept it.
                values = {"account": out["account"], "as_of": (out["instant"] or "")[:10],
                          "cash": _number(cash), "evidence": key,
                          "reference": out["reference"]}
                already = bench_matching("cash-readings", values)
                line = f"Total cash: {cash}"
                if already and already != "unreadable":
                    out["seen"].append({"line": line, "in_record": already,
                                        "why": _on_file("cash-readings", already)})
                else:
                    out["rows"].append({
                        "table": "cash-readings", "values": values,
                        "sources": {k: line for k in values},
                        "machine": True, "derived": [], "drafted": []})
        return out

    body, header = _cells(text, cmap.header)
    for row in body:
        code = _value(row, header, cmap.code)
        raw_date = _value(row, header, cmap.date)
        if not code or not raw_date:
            continue                     # a total line, or a blank between blocks
        try:
            when = _dt.datetime.strptime(raw_date, cmap.date_format).date().isoformat()
        except ValueError:
            out["unrecognised"].append(f"{raw_date} {code} — the date does not read as "
                                       f"{cmap.date_format}")
            continue

        entry = D.hl_code(code)
        line = f"{when} {code} {_value(row, header, cmap.fields.get('detail', ''))}".strip()
        if entry is None:
            out["unrecognised"].append(f"{line} — this code is not in rules.HL_CODES")
            continue
        if entry.table is None:
            out["seen"].append({"line": line, "why": entry.why, "in_record": None})
            continue
        if entry.table != "income":
            # A DEALING LINE, reported rather than proposed — see the module docstring.
            out["seen"].append({"line": line, "why": entry.why,
                                "in_record": _in_record(code)})
            continue

        values = {"date": when, "account": out["account"], "category": entry.category,
                  "source": D.evidence_source(key, reference=out["reference"],
                                              account=out["account"])}
        for store_col, doc_col in cmap.fields.items():
            cell = _value(row, header, doc_col)
            values[store_col] = _number(cell) if store_col == "amount" else cell
        # A LINE ALREADY IN THE BOOK IS NOT READ AGAIN — the same rule `propose.py` follows,
        # and it matters more here: these five exports overlap by design. The income list and
        # the Income-side transaction list carry the same dividends, so without this the second
        # document worked would offer every row the first one entered.
        #
        # REPORTED, NEVER SILENT. It goes in `seen` naming the row it matched, so the reading
        # answers the question a statement actually poses: which of these are new.
        already = bench_matching(entry.table, values)
        if already and already != "unreadable":
            out["seen"].append({"line": line, "in_record": already,
                                "why": _on_file(entry.table, already)})
            continue

        out["rows"].append({
            "table": entry.table,
            "values": {k: v for k, v in values.items() if v != ""},
            # THE SOURCE IS THE DOCUMENT'S OWN ROW. `propose.py` stores a quote here because a
            # reader's cell has to be matched back to the page; here the row IS the evidence, so
            # the screen shows the line the value was lifted from.
            "sources": {k: line for k in values if values[k] != ""},
            "machine": True, "derived": [], "drafted": []})
    return out


def _holdings_reading(text: str, key: str, out: dict) -> None:
    """A holdings export's UNITS against the book, and the account reading it files.

    THE ACCOUNT IS THE ONE WHOSE UNITS AGREE when the export names none: ii's names nothing,
    and arithmetic is what identifies it (`docs/reconciling.md`). Two or none leaves it blank.

    THE READING'S FIGURES ARE THE DOCUMENT'S OWN, and only those — HL's Stock value, Total cash
    and Total value. ii's states only each holding's £ value, so its stock is their sum and its
    cash and total are blank (`observations.SHARE_CASH` says why) — blank, not absent, so filing
    it clears the cash the account's previous reading carried.
    Nothing is typed: filing the export writes its reading.
    """
    from portfusion.desk import engine
    book = engine.book()
    units = holdings(text, key)
    as_of = (out["instant"] or "")[:10]
    if not out["account"] and as_of:
        agree = [a for a in book.account_order() if not book.is_spread_bet(a)
                 and bool(book.units_check(a, as_of, units)["agrees"].all())]
        out["account"] = agree[0] if len(agree) == 1 else ""
    account = out["account"]
    out["units"] = []
    if account and as_of:
        check = book.units_check(account, as_of, units)
        out["units"] = [{"ticker": r.ticker, "book": r.book, "broker": r.broker,
                         "agrees": bool(r.agrees)} for r in check.itertuples(index=False)]
    out["seen"] += [{"line": f"{u['ticker']} {u['broker']:,.0f} units",
                     "in_record": "agrees" if u["agrees"] else "",
                     "tag": "agrees" if u["agrees"] else "differs",
                     "why": f"the book holds {u['book']:,.0f}"} for u in out["units"]]

    if key == "hl-valuation":
        stock, cash, total = (_number(_labelled(text, label)) for label in
                              ("Stock value:", "Total cash:", "Total value:"))
    else:
        body, header = _cells(text.lstrip("\ufeff"), D.HOLDINGS_COLUMNS[key])
        values = [_number(_value(r, header, "Market Value £")) for r in body
                  if _value(r, header, D.HOLDINGS_COLUMNS[key][0])]
        stock, cash, total = f"{sum(float(v) for v in values if v):.2f}", "", ""
    out["reading"] = {"account": account, "positions": stock, "recon_cash": cash,
                      "stmt_value": total,
                      "at": D.utc_instant(out["instant"]) if out["instant"] else ""}


def _ii_ledger(text: str, out: dict) -> dict:
    """An ii ledger: its interest, dividends, fees and payments as rows, its dealing lines
    reported against their contract notes, and its closing balance as the account's cash when
    that balance is the whole of it. `rules.ii_line()` says what each line is.

    ONE CURRENCY, GBP. A EUR or USD line needs the day's rate to become a row, and a rate from
    the wrong day is the error `rules.FX_RATE_AGE_LIMIT_DAYS` describes; such a ledger's lines are left unread, for
    a person.
    """
    body, header = _cells(text.lstrip("\ufeff"), D.II_LEDGER_HEADER)
    lines = []
    for row in body:
        raw, desc = _value(row, header, "Settlement Date"), _value(row, header, "Description")
        if not raw or not desc:
            continue
        try:
            when = _dt.datetime.strptime(raw, "%d/%m/%Y").date()
        except ValueError:
            out["unrecognised"].append(f"{raw} {desc} — the date does not read as DD/MM/YYYY")
            continue
        cells = {c: _value(row, header, c) for c in ("Debit", "Credit", "Running Balance")}
        lines.append({"when": when, "desc": " ".join(desc.split()), "cells": cells,
                      "symbol": _value(row, header, "Symbol"),
                      "ref": _value(row, header, "Reference")})
    if not lines:
        return out

    currencies = {_II_SYMBOLS[v[0]] for ln in lines for v in ln["cells"].values()
                  if v and v[0] in _II_SYMBOLS}
    ccy = currencies.pop() if len(currencies) == 1 else ""
    first, last = min(ln["when"] for ln in lines), max(ln["when"] for ln in lines)
    span = (f"{first:%-d %b}-{last:%-d %b %Y}" if first.year == last.year
            else f"{first:%-d %b %Y}-{last:%-d %b %Y}")
    out["reference"] = f"{ccy} {span}".strip()
    if ccy != "GBP":
        why = (f"a {ccy} ledger: its lines need the day's rate to become rows, so they are "
               f"entered by hand" if ccy else "the ledger's money is in more than one currency")
        out["unrecognised"] += [f"{ln['when']} {ln['desc']} — {why}" for ln in lines]
        return out

    out["account"] = out["account"] or _ii_account(lines)
    account = out["account"]
    source = D.evidence_source("ii-transactions", reference=out["reference"], account=account)

    for ln in sorted(lines, key=lambda x: x["when"]):
        line = f"{ln['when']} {ln['desc']}"
        code = D.ii_line(ln["desc"], ln["symbol"])
        if code is None:
            out["unrecognised"].append(f"{line} — not a line this reader knows")
            continue
        if code.table is None:
            number = D.ii_contract_number(ln["ref"])
            found = _in_record(number)
            out["seen"].append({"line": f"{line} (contract note {number})", "why": code.why,
                                "in_record": found})
            if not found:
                out["unrecognised"].append(f"{line} — its contract note {number} is not in the "
                                           f"record; work the contract note")
            continue
        credit, debit = _number(ln["cells"]["Credit"]), _number(ln["cells"]["Debit"])
        amount = credit if credit and credit != "n/a" else f"-{debit}"
        values = {"date": ln["when"].isoformat(), "account": account, "amount": amount,
                  "source": source, "detail": ln["desc"]}
        if code.table == "income":
            values["category"] = code.category
        already = bench_matching(code.table, values)
        if already and already != "unreadable":
            out["seen"].append({"line": line, "in_record": already,
                                "why": _on_file(code.table, already)})
            continue
        out["rows"].append({"table": code.table,
                            "values": {k: v for k, v in values.items() if v != ""},
                            "sources": {k: line for k in values if values[k] != ""},
                            "machine": True, "derived": [], "drafted": []})

    _ii_cash(lines, out, account)
    return out


def _ii_cash(lines: list, out: dict, account: str) -> None:
    """The newest line's running balance as the account's cash — only when the account keeps
    its cash in GBP alone, because a GBP ledger's balance is then the whole of it. An account
    that has been paid in another currency holds cash there too, and its cash is that ledger
    and this one together."""
    newest = max(lines, key=lambda x: x["when"])
    balance = _number(newest["cells"]["Running Balance"])
    line = f"{newest['when']} running balance £{balance}"
    if not account:
        out["seen"].append({"line": line, "in_record": None,
                            "why": "no account identified, so no cash reading proposed"})
        return
    others = bench_currencies(account) - {"GBP"}
    if others:
        out["seen"].append({"line": line, "in_record": None,
                            "why": f"{account} also holds {', '.join(sorted(others))} cash, so "
                                   f"its cash is that ledger and this one together — not "
                                   f"proposed from one"})
        return
    values = {"account": account, "as_of": (out["instant"] or str(newest["when"]))[:10],
              "cash": balance, "evidence": "ii-transactions", "reference": out["reference"]}
    already = bench_matching("cash-readings", values)
    if already and already != "unreadable":
        out["seen"].append({"line": line, "in_record": already,
                            "why": _on_file("cash-readings", already)})
        return
    out["rows"].append({"table": "cash-readings", "values": values,
                        "sources": {k: line for k in values}, "machine": True,
                        "derived": [], "drafted": []})


def _on_file(table: str, already: str) -> str:
    """Where a matched line already sits. `matching_row()` returns a row's first cell, which is
    an id on trades and exits and only a date elsewhere, so a date names the table instead."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(already)):
        return f"already in {table}.csv"
    return f"already in the record as {already}"


#: How many of a ledger's lines must match one account's rows on file, and no other account's,
#: before the ledger is taken for that account's. One coincidence — an interest payment of the
#: same pennies on the same day in a second account — was enough to file a whole ledger there.
LINES_TO_NAME_AN_ACCOUNT = 2


def _ii_account(lines: list) -> str:
    """Which ii account a ledger is, when it prints no client number: the account a dealing line
    settled in (its contract note's number names one), or else the one account that at least
    `LINES_TO_NAME_AN_ACCOUNT` of its lines match on file and no other matches. Anything less
    leaves it blank for a person."""
    from portfusion.desk.intake import bench
    found = set()
    for ln in lines:
        code = D.ii_line(ln["desc"], ln["symbol"])
        if code is D.II_DEALING:
            found |= bench.accounts_citing(D.ii_contract_number(ln["ref"]))
    if found:
        return found.pop() if len(found) == 1 else ""
    matched = {}
    for account in bench.accounts_of_broker(D.II_BROKER):
        for ln in lines:
            code = D.ii_line(ln["desc"], ln["symbol"])
            if code is None or code.table is None:
                continue
            credit = _number(ln["cells"]["Credit"])
            amount = credit if credit and credit != "n/a" else f"-{_number(ln['cells']['Debit'])}"
            values = {"date": ln["when"].isoformat(), "account": account, "amount": amount,
                      "category": code.category}
            hit = bench_matching(code.table, values)
            if hit and hit != "unreadable":
                matched[account] = matched.get(account, 0) + 1
    if len(matched) == 1 and next(iter(matched.values())) >= LINES_TO_NAME_AN_ACCOUNT:
        return next(iter(matched))
    return ""


def bench_currencies(account: str) -> set:
    """The currencies this account has been paid in — `bench.cash_currencies()`, imported late."""
    from portfusion.desk.intake import bench
    return bench.cash_currencies(account)


def bench_matching(table: str, values: dict):
    """What the record already holds for this row, if anything. Imported late, as `bench` does.

    A thin wrapper so the import stays out of module scope: `desk/intake/bench.py` reaches the record
    and this module is read by tests that never need one.
    """
    from portfusion.desk.intake import bench
    return bench.matching_row(table, values)


def _in_record(reference: str) -> str:
    """Which store tables already carry this broker reference. "" means none do."""
    from portfusion.desk.intake import bench
    return ", ".join(bench.reference_tables(reference))
