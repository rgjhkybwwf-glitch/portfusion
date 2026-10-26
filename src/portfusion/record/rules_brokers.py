"""rules_brokers.py — THE BROKERS' OWN CODES, and the ticker they mean.

A vocabulary and the functions that read it, holding no state and touching no table — the same
reason `rules_evidence.py` stands apart. Each broker's codes and words, and the maps saying how
each kind of export is read, keyed by evidence class: every column, label and line reader is its
map's, so `desk/intake/read_rows.py` names no broker. `rules` re-exports every name.
"""
from __future__ import annotations

import re as _re
from collections.abc import Callable
from typing import NamedTuple


# ============================================================================
# THE NAMING CONVENTION. Every holding is coded by its REAL ticker: bare for a US listing, an
# exchange suffix otherwise (.L LSE/AIM · .DE Xetra · .CO Copenhagen · .PA Paris · .ST Stockholm),
# and " SB" for a spread bet. Spread-bet CONTRACT keys are a separate namespace. One security held
# as two separate round trips keeps two join keys by a "(qualifier)". securities.csv registers
# every code, and a ledger row naming any other is refused on load.
# ============================================================================
def book_code(code: str, known) -> str:
    """The book's code for one a broker's document prints, or the code as printed.

    THE BOOK USES ITS FULL CODE EVERYWHERE; a broker's document does not. ii prints PENR for PENR.L
    and HL prints ASKE B for ASKE-B.CO, and their files are theirs. So the match is a RULE, not a
    list: the code itself, in any case; else the ONE known code that is this code plus an exchange
    suffix, a space read as a hyphen. A prefix with no dot never qualifies, so PRY is not PRYS.
    A code matching nothing, or two, comes back as printed, so a check against the book names it
    rather than guessing.

    Side effects: none.
    """
    code = (code or "").strip()
    if not code:
        return code
    known = list(known)
    exact = [k for k in known if k.lower() == code.lower()]
    if exact:
        return exact[0]
    stem = code.lower().replace(" ", "-") + "."
    suffixed = [k for k in known if k.lower().startswith(stem)]
    return suffixed[0] if len(suffixed) == 1 else code


# ==============================================================================================
# WHAT A LINE OF A BROKER'S TRANSACTION LIST IS
# ----------------------------------------------------------------------------------------------
# This answers which store table a line of a broker's transaction list becomes a
# row in, from the broker's transaction code — so a recognised document is read from its named
# cells rather than transcribed.
#
# `table` IS THE ANSWER, AND None IS ONE OF THEM. A transfer between an HL ISA's two sub-accounts
# changes no figure this book holds, and it appears on BOTH lists under one reference, once each
# way; entered from both it would be booked twice. It is REPORTED as seen and not entered.
#
# Named `table`, not `movement` (never used bare — glossary 2b) and not `entry` (the opening of a
# position).
class BrokerCode(NamedTuple):
    """What one line of a broker's transaction list is, in the record's own words."""
    table: str | None     # the store table this line becomes a row in; None means no row
    category: str         # `income.category` where table is "income"; "" otherwise
    why: str              # what the code means, for the screen and for a later reader


#: HL's codes, literal, read off its own exports. Add to this from a document, never from memory.
HL_CODES = {
    "OVR CR":     BrokerCode("income", "Dividend",
                             "an overseas dividend payment"),
    "MANAGE FEE": BrokerCode("income", "Fee",
                             "HL's platform fee, charged to the account"),
    "INTEREST":   BrokerCode("income", "Cash interest",
                             "interest paid on the cash balance"),
}

#: HL's codes that carry a deal or transfer reference after a prefix. The reference is the row's
#: `broker_ref`, so the prefix is the only part that classifies.
HL_CODE_PREFIXES = (
    (_re.compile(r"^B\d+$"),   BrokerCode("buys", "",
                                          "a purchase; the code is HL's deal reference")),
    (_re.compile(r"^S\d+$"),   BrokerCode("sales", "",
                                          "a sale; the code is HL's deal reference")),
    (_re.compile(r"^DRI\w*$"), BrokerCode(None, "",
                                          "a transfer between the ISA's Income and Capital "
                                          "sub-accounts — not an event, and recorded as seen "
                                          "rather than entered")),
)


def hl_code(reference: str) -> BrokerCode | None:
    """What an HL transaction line is, from its Reference cell. None means unrecognised.

    Unrecognised is a real answer, never guessed at: deciding by pattern is how a fee becomes a
    dividend. Side effects: none.
    """
    ref = " ".join(str(reference or "").split())
    if ref in HL_CODES:
        return HL_CODES[ref]
    for pattern, code in HL_CODE_PREFIXES:
        if pattern.match(ref):
            return code
    return None


#: How a recognised document's own columns become a row, keyed by evidence class.
#:
#: ONLY WHERE THE DOCUMENT IS UNAMBIGUOUS. `hl-transactions` buys and sells carry their security
#: inside prose ("Kelstrand Foods plc Ordinary Shares 40 @ 512.250000"), and resolving a name to a code is
#: the guess this map exists to avoid; those lines are REPORTED with their deal reference, which
#: is what the record stores anyway.
#:
#: `code` names the column that says what the line is, and `line` is its own broker's reader of it
#: (`hl_code()`). `date` is parsed with `date_format`: a broker writes DD/MM/YYYY, and reading it
#: backwards moves a July row to January.
class ColumnMap(NamedTuple):
    header: tuple         # the column header row, as the document writes it
    code: str             # which column carries the transaction code
    date: str             # which column is the row's date
    date_format: str      # how that column writes a date
    fields: dict          # store column -> document column, for the cells lifted verbatim
    line: Callable[[str], BrokerCode | None]   # what a code means; None is unrecognised
    codes: str            # where `line`'s codes are written, named for a code it does not know


COLUMN_MAPS = {
    "hl-income": ColumnMap(
        header=("Date", "Type", "Description", "Amount"),
        code="Type", date="Date", date_format="%d/%m/%Y",
        fields={"detail": "Description", "amount": "Amount"},
        line=hl_code, codes="rules.HL_CODES"),
    # SETTLE DATE, NOT TRADE DATE, for income. HL dates a dividend twice on this export, and its
    # income export carries only the settle date, every time. The duplicate gate keys on the date,
    # so taking the trade date here would let one dividend enter twice. A dealing line would take
    # the trade date, but this map emits income rows only.
    "hl-transactions": ColumnMap(
        header=("Trade date", "Settle date", "Reference", "Description",
                "Unit cost (p)", "Quantity", "Value"),
        code="Reference", date="Settle date", date_format="%d/%m/%Y",
        fields={"detail": "Description", "amount": "Value"},
        line=hl_code, codes="rules.HL_CODES"),
}


#: WHAT AN ii LEDGER LINE IS. ii prints no transaction code, so a line is known by how its
#: Description BEGINS — literal, off ii's own ledgers, case aside, never a pattern guessed at. A
#: dividend's line names its security too. Any other line naming one (a Symbol other than "n/a")
#: is a DEALING line and is not here: its contract note is the entry, and the line is reported
#: against it (`II_DEALING`).
II_LEDGER_LINES = (
    ("Gross interest", BrokerCode("income", "Cash interest",
                                  "interest paid on the cash balance")),
    ("Div ",           BrokerCode("income", "Dividend", "a dividend payment")),
    ("Fee Transfer",   BrokerCode("income", "Fee", "ii's monthly fee, charged to the account")),
    ("PAYMENT",        BrokerCode("capital-movements", "",
                                  "a payment out of the account to its holder")),
)
II_DEALING = BrokerCode(None, "", "a dealing line — its contract note is the entry")

#: The broker whose ledger these lines are, as `accounts.csv` names it — matched without regard
#: to case, so a register spelling it with capitals is the same broker.
II_BROKER = "interactive investor"


def ii_line(description: str, symbol: str) -> BrokerCode | None:
    """What one ii ledger line is, by its Description first and only then its Symbol. None means
    unrecognised, which is a real answer."""
    text = " ".join(str(description or "").split()).lower()
    code = next((code for prefix, code in II_LEDGER_LINES if text.startswith(prefix.lower())),
                None)
    if code is None and str(symbol or "").strip().lower() not in ("", "n/a"):
        return II_DEALING
    return code


def ii_contract_number(reference: str) -> str:
    """The contract note number inside an ii ledger reference: its last six characters. The
    ledger writes 12345ABC123 for contract note ABC123 (KELS.L, 3 Mar 2025) and 12345ABD456 for
    ABD456 (QNLR, 7 Apr 2025)."""
    ref = str(reference or "").strip()
    return ref[-6:] if len(ref) > 6 else ref


#: A CASH LEDGER, read line by line: no transaction code, so `line` knows a line by its
#: description and symbol. A line `line` gives no table is a dealing line, reported against the
#: contract note `contract` reads out of its reference; a ledger printing no client number is
#: matched to one of `broker`'s accounts.
class LedgerMap(NamedTuple):
    header: tuple         # the column header row, as the document writes it
    date: str             # which column is the line's date
    date_format: str      # how that column writes a date
    description: str      # the column saying what the line is
    symbol: str           # the column naming its security, or "n/a"
    reference: str        # the column carrying a dealing line's reference
    debit: str            # money out
    credit: str           # money in
    balance: str          # the running balance after the line
    currencies: dict      # a money cell's leading symbol -> its currency
    line: Callable[[str, str], BrokerCode | None]   # what a line is; None is unrecognised
    contract: Callable[[str], str]                  # the contract note number in a reference
    broker: str           # whose ledger it is, as `accounts.csv` names the broker


LEDGER_MAPS = {
    # THE COLUMNS OF AN ii LEDGER ("broker direct" transactions download), as ii writes them.
    "ii-transactions": LedgerMap(
        header=("Date", "Settlement Date", "Symbol", "Sedol", "Quantity", "Price",
                "Description", "Reference", "Debit", "Credit", "Running Balance"),
        date="Settlement Date", date_format="%d/%m/%Y", description="Description",
        symbol="Symbol", reference="Reference", debit="Debit", credit="Credit",
        balance="Running Balance", currencies={"£": "GBP", "€": "EUR", "$": "USD"},
        line=ii_line, contract=ii_contract_number, broker=II_BROKER),
}


#: WHERE A HOLDINGS EXPORT SAYS HOW MANY UNITS, per evidence class: the column naming the security
#: and the column holding its units: a share account is checked on units. A
#: row with no security is a totals line. Each broker writes its own codes, which `book_code()`
#: matches to the book's.
#:
#: THE READING'S FIGURES ARE THE DOCUMENT'S OWN: its header block's labelled stock, cash and total,
#: or, where it labels none, its holdings' `value` summed for the stock. A labelled cash is also
#: filed as the account's cash reading.
class HoldingsMap(NamedTuple):
    code: str             # the column naming the security
    units: str            # the column holding its units
    stock: str = ""       # the header block's label for the holdings' value
    cash: str = ""        # ... for the account's cash
    total: str = ""       # ... for the two together
    value: str = ""       # where it labels none, the column of each holding's value


HOLDINGS_COLUMNS = {
    "hl-valuation": HoldingsMap("Code", "Units held", stock="Stock value:", cash="Total cash:",
                                total="Total value:"),
    "ii-valuation": HoldingsMap("Symbol", "Qty", value="Market Value £"),
}


#: WHAT AN IG LEDGER LINE IS (/history/transactions), by its `transactionType`. A `DEPO` or `WITH`
#: is money crossing the account's boundary, but IG files its funding charges under `WITH` too:
#: one is known by the words IG prints on it ("Long Interest for US/Can shares 10/08/26"). Any
#: other type becomes no row.
IG_CAPITAL_TYPES = ("DEPO", "WITH")
IG_FUNDING_WORDS = ("interest", "funding")
IG_FUNDING = BrokerCode("income", "Funding interest", "a funding cost, charged to the account")
IG_CAPITAL = BrokerCode("capital-movements", "", "money paid into or out of the account")


def ig_line(transaction_type: str, instrument_name) -> BrokerCode | None:
    """What one IG ledger line is, by its type and then its words. None means no row."""
    if transaction_type == "WITH" and any(w in str(instrument_name or "").lower()
                                          for w in IG_FUNDING_WORDS):
        return IG_FUNDING
    return IG_CAPITAL if transaction_type in IG_CAPITAL_TYPES else None

