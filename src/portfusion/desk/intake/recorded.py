"""RECORDED — what the record already holds, asked before a row is proposed: whether a row is
there already, which tables carry a reference, which accounts a reference or a broker names, the
currencies an account is paid in, and the account a document's number belongs to. The Bench's
gates, the readers and the sweep ask the one question each, here.
"""
from __future__ import annotations

import re

from portfusion.desk.engine import RecordUnavailable, _guarded
from portfusion.record import schema


#: The columns that identify an EVENT, per table. Not the whole row — a note and an id differ
#: between two records of one thing, and the id is allocated fresh every time, so a comparison
#: including them would never match the duplicate it is looking for.
SIGNATURE = {
    "buys": ("date", "account", "ticker", "qty", "stake", "cost", "level_points"),
    "sales": ("date", "account", "ticker", "qty", "stake", "proceeds"),
    "income": ("date", "account", "category", "amount"),
    "capital-movements": ("date", "account", "amount"),
    # ACCOUNT AND DATE, WITHOUT THE AMOUNT — and that asymmetry is deliberate. For an event the
    # amount is part of what identifies it: two £50 dividends on one day from one account are
    # two dividends. For a BALANCE they are not: one account has ONE cash balance on a given
    # date, so a second row for that pair is a re-reading, not a second fact. Including `cash`
    # would let a mistyped figure in as a "different" observation, which is the exact case this
    # gate exists to catch.
    "cash-readings": ("account", "as_of"),
}


def matching_row(table: str, values: dict):
    """The id of an existing row this one duplicates, `"unreadable"` if it cannot be checked,
    or None. Shared by the gate and by the reading, so both ask exactly one question.
    """
    cols = SIGNATURE.get(table)
    if not cols:
        return None

    def _load():
        fields = {f.name: f for f in schema.TABLES[table].fields}
        order = [f.name for f in schema.TABLES[table].fields]

        # MATCH ON WHAT THE ROW ACTUALLY HAS. A row whose account is still blank — because the
        # document named a number and not a name — would otherwise compare "" against
        # the account's name and miss a duplicate it plainly is. Date, holding, size and money
        # identify a sale perfectly well without the account, so the comparison uses the
        # columns that are filled and requires at least THREE of them: fewer than that is not
        # an identification, it is a coincidence waiting to happen.
        #
        # UNLESS THE SIGNATURE IS SHORTER THAN THREE. `cash-readings` is identified by
        # (account, as_of) and by nothing else, so a flat minimum of three would silently disable
        # the gate for it. The rule is "all of the columns that identify this thing": for a
        # five-column event signature three filled is enough to be sure, and for a two-column one
        # two IS all of them. Adding `cash` to reach three would be the wrong fix — a mistyped
        # figure would then read as a different observation and walk straight past.
        need = min(3, len(cols))
        present = [c for c in cols if str(values.get(c, "") or "").strip()]
        if len(present) < need:
            return None
        try:
            want = tuple(schema._parse(fields[c], schema.cell(fields[c], values.get(c, "")),
                                       table, 0) for c in present)
        except (ValueError, KeyError):
            return "unreadable"
        for existing in schema.load(table):
            if tuple(existing[order.index(c)] for c in present) == want:
                return existing[0]
        return None

    try:
        return _guarded(_load)
    except RecordUnavailable:
        return None


def reference_tables(reference: str) -> list[str]:
    """Which of `SIGNATURE`'s tables already carry this reference anywhere in a row. Empty means new.

    Shared so the SWEEP can ask the question the duplicate gate asks. A sweep is a snapshot
    taken before anything was committed, and without this an event already carried across would
    still be offered as "work it". One implementation, two callers.
    """
    ref = str(reference or "").strip().lower()
    if len(ref) < 4:
        return []
    out = []
    for table in SIGNATURE:
        for row in schema.load(table):
            if any(ref in str(c).lower() for c in row if c):
                out.append(table)
                break
    return out


def accounts_citing(reference: str) -> set:
    """The accounts of the trades and exits that carry this reference — which account a ledger's
    dealing line settled in. Empty when none do."""
    ref = str(reference or "").strip().lower()
    if len(ref) < 4:
        return set()

    def _load():
        out = set()
        for table in ("buys", "sales"):
            acct_col = schema.TABLES[table].header.index("account")
            out |= {row[acct_col] for row in schema.load(table)
                    if any(ref in str(c).lower() for c in row if c)}
        return out
    try:
        return _guarded(_load)
    except RecordUnavailable:
        return set()


def accounts_of_broker(broker: str) -> list[str]:
    """The accounts `store/accounts.csv` holds at this broker, in the order it lists them. The
    broker's name is matched without regard to case."""

    def _load():
        header = schema.TABLES["accounts"].header
        return [r[header.index("account")] for r in schema.load("accounts")
                if str(r[header.index("broker_firm")]).strip().lower() == broker.strip().lower()]
    try:
        return _guarded(_load)
    except RecordUnavailable:
        return []


def cash_currencies(account: str) -> set:
    """Every currency this account has been paid income in, GBP always among them. An account
    paid in EUR holds EUR cash, so one GBP ledger's balance is not the whole of its cash."""

    def _load():
        header = schema.TABLES["income"].header
        a, c = header.index("account"), header.index("currency")
        return {"GBP"} | {r[c] for r in schema.load("income") if r[a] == account and r[c]}
    try:
        return _guarded(_load)
    except RecordUnavailable:
        return {"GBP"}


def account_from(text: str) -> tuple[str | None, str]:
    """The account this document belongs to, matched on the number it prints.

    A DERIVATION, NOT A TRANSLATION. `store/accounts.csv` holds a `number` column — each
    account's number at its broker — so mapping the number a contract note prints onto the
    account it belongs to is the RECORD answering, not the reader guessing. That distinction is
    why the reader is still told to refuse the account outright: it does not know the mapping,
    and reasoning its way to one would be exactly the invention this bench exists to prevent.
    This function knows, because the book wrote it down.

    RETURNS NOTHING UNLESS EXACTLY ONE MATCHES. Two numbers in one document means a statement
    covering more than one account, and picking either would be a coin toss. Matched on a whole
    token, so a number that happens to be a substring of a larger figure is not a hit.
    """
    def _load():
        return [(r[0], str(r[3])) for r in schema.load("accounts") if str(r[3]).strip()]
    try:
        accounts = _guarded(_load)
    except RecordUnavailable:
        return None, ""

    hits = []
    for name, number in accounts:
        # DIGIT BOUNDARIES, NOT WORD BOUNDARIES. ii builds its payment references out of the
        # account number — "PAYMENT Q1234567AB1CDE A SMITH" — so word boundaries would miss the
        # account on a cash statement that names it on every line. What must still be rejected
        # is the number sitting inside a LONGER NUMBER, which is the actual false positive:
        # `21234567000` is not account 1234567.
        m = re.search(rf"(?<!\d){re.escape(number)}(?!\d)", text)
        if m:
            line = next((candidate for candidate in text.splitlines() if number in candidate), number)
            hits.append((name, " ".join(line.split())[:120]))
    return hits[0] if len(hits) == 1 else (None, "")
