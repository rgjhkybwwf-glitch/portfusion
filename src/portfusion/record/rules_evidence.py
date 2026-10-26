"""rules_evidence.py — WHAT A DOCUMENT IS, and what retrieves it a second time.

A vocabulary and the functions that read it, holding no state and touching no table. That purity
is what lets `rules.reload_store()` rebuild the record alone and still be right: nothing here
derives from the store, so nothing here needs reloading.

`rules` re-exports every name, so `D.EVIDENCE_CLASSES` and `D.identify()` work. Import THIS
module only for the vocabulary without the record.
"""
from __future__ import annotations

import datetime as _dt
import re as _re
from typing import NamedTuple


# ==============================================================================================
# THE EVIDENCE CLASSES — what a document IS, and what retrieves it a second time.
# ==============================================================================================
# ALL THREE LIMBS APPLY TO EVERY CLASS. A class knows the SHAPE of each — which authority to name,
# what its reference looks like, how its `source` line reads — so a provenance line comes out in
# the form the record already uses.
#
# A REFERENCE NEED NOT BE A NUMBER: it is whatever GETS YOU BACK TO THE SAME FIGURES, and for a
# download that is the query reproducing it — broker, account, date range.
#
# `retrieval` IS A SECOND AXIS BESIDE `official`. `official` asks "is this the document a quarter
# is reconciled against"; `retrieval` asks "what would I go and look at". A download is not
# official and is perfectly retrievable. It is structure where `reference_is` is prose, which is
# what lets the door check limb 3.
RETRIEVAL_KINDS = (
    "document",   # a file that should be sitting in _archive/statements/
    "api",        # an authenticated read; the stored reference (a dealId) retrieves it
    "reading",    # an authenticated read of a LIVE figure. The endpoint answers again, with a
                  # DIFFERENT number: the value is an instant, not a record. Stronger than
                  # `none` (named account, broker's figure, no transcription); weaker than
                  # `api`, where a stored dealId retrieves the SAME answer for ever.
    "none",       # NOTHING retrieves it: `not-on-file`, which is CLOSED.
)

# ==============================================================================================
# NOT ON FILE — the one class for a row whose document the archive does not hold.
# ----------------------------------------------------------------------------------------------
# It describes rows already written and no door offers it, so a new row cannot cite it
# (CLOSED_TO_NEW_ENTRIES, below). A row's figure stays as it was; only its label says the
# document is not in `_archive/statements/`. Filing the document later moves the row back to
# that document's own class.

#: What a document can account for. A share account's total is positions plus cash; a spread bet's
#: is its equity. Named separately because `Book.NAV_BASES` refuses to let one stand for the other.
COVERAGE_LIMBS = ("positions", "cash", "equity")

#: The coverages that amount to a WHOLE account, and so to a figure a quarter can be struck
#: against. Anything less is a real document about part of an account.
_WHOLE_ACCOUNT = ({"positions", "cash"}, {"equity"})


def reconciles_an_account(ev) -> bool:
    """Is this the dated document a quarter's total is reconciled against?

    Two conditions: the strongest thing obtainable for what it covers (`official`), AND what it
    covers is a whole account. A contract note passes the first and fails the second;
    `hl-account-totals` covers the whole account and fails the first, restating the valuation
    rather than being it.

    Side effects: none.
    """
    if ev is None or not ev.official:
        return False
    held = set(ev.covers)
    return any(held >= whole for whole in _WHOLE_ACCOUNT)


def states_cash(ev) -> bool:
    """Does this kind of document state an account's cash? ii's holdings export does not. What
    follows from that is the readings door's (`SHARE_CASH`) and `Book.reconciliation()`'s.

    Side effects: none.
    """
    return ev is not None and "cash" in ev.covers


class Evidence(NamedTuple):
    key: str
    label: str            # what the desk offers
    authority: str        # limb 2 — the authority that can be asked again
    reference_is: str     # limb 3, in words: what retrieves this a second time
    source: str           # how `source` reads. {reference} {date} {account}
    official: bool        # is this the strongest thing obtainable for what it covers?
    retrieval: str        # limb 3, as STRUCTURE: one of RETRIEVAL_KINDS
    # HOW TO RECOGNISE ONE: literals that must all appear in the document's own text. Empty means
    # no sample has been seen, so the class cannot be recognised by machine. Never the FILENAME:
    # HL exports three different reports titled "Portfolio Summary", and a -2 or -3 on disk is
    # only macOS numbering downloads.
    fingerprint: tuple = ()
    # HOW MUCH OF AN ACCOUNT this document accounts for — one of COVERAGE_LIMBS, or empty where it
    # covers no account total. `official` says how strong a document is for what it covers; this
    # says how much that is. A contract note is the strongest record of a trade and reconciles no
    # quarter.
    covers: tuple = ()

# THE ORDER: the two brokers that send documents first, each strongest to weakest, then IG, then
# `not-on-file`. Reading down the list is reading down the source hierarchy.
#
# THE LIST IS FLAT ON PURPOSE, though it looks like a broker-by-shape grid wanting collapse. Of the
# shapes more than one broker has, most share every property and two do not — and the two are
# load-bearing: a `statement` covers positions plus cash for a share account but equity for a
# spread bet, and a `valuation` carries cash from HL and not from ii. Collapsing it would bury the
# differences that matter in an override list.
EVIDENCE_CLASSES = (
    # Every filed note is a sample, and no other document in the archive carries all three — the
    # ii statements included. The third is the firm's FCA number, not its name: ii's notes before
    # 2017 were issued by the same firm as TD Direct Investing, and the number survived the rename.
    #
    # ITS NUMBER IS THE DEAL'S, so the row stores it in `broker_ref` and the source line names
    # only the kind and the date (`trade_source()`); the archive finds the note by that number.
    Evidence("ii-contract-note", "ii contract note", "ii contract note",
             "the contract note number, e.g. ABD789",
             "ii contract note {date}", True, "document",
             ("We thank you for your instructions", "CONTRACT No.", "141282"), covers=()),
    Evidence("ii-statement", "ii statement", "ii statement",
             "the statement's date, e.g. 30 Jun 2026",
             "ii statement {reference}", True, "document", covers=("positions", "cash")),
    # THE MARKS ON DEMAND — ii's holdings export, the ii analogue of `hl-valuation`: every holding
    # with quantity, local price and value, per-currency totals, and ii's FX rates.
    #
    # Official, and it carries NO CASH: the strongest statement of these marks ii gives, but the
    # cash lives in the per-currency ledgers, so a quarter cannot be struck against this alone
    # (`reconciles_an_account()`). There is no all-currency total anywhere in ii; the account's
    # is assembled per currency at the rates printed here, and that assembly is the reconciliation.
    # A total ASSEMBLED from several documents is a derivation, however strong each one is.
    Evidence("ii-valuation", "ii valuation (holdings export)", "ii valuation download",
             "the instant it was pulled, e.g. 3 Mar 2025 14:05",
             "ii valuation {reference} ({account})", True, "document",
             ("Day Gain/Loss %,Market Value", "Book Cost,Gain/Loss"),
             covers=("positions",)),
    # RETRIEVES BY `document`: the reference is the query that reproduces it, but the file is kept
    # and archived. THE CURRENCY IS PART OF THE REFERENCE — ii ledgers are pulled per currency,
    # and an account's GBP and EUR ledgers over one window are different documents. The account's
    # cash is the two summed.
    Evidence("ii-transactions", "ii transaction history", "ii broker direct",
             "the currency and the query that reproduces it: the date range you asked for, "
             "e.g. GBP 1 Jan-3 Mar 2025",
             "ii transactions {reference} ({account})", False, "document",
             ("Settlement Date,Symbol,Sedol", "Debit,Credit,Running Balance"), covers=("cash",)),
    Evidence("hl-statement", "HL statement", "HL statement",
             "the date the statement's quarter ends, e.g. 31 Jan 2025",
             "HL statement {reference}", True, "document", covers=("positions", "cash")),
    # The valuation — HL's "Account Summary" download: total, cash, every holding with units,
    # price, value and cost, and HL's three FX rates. It exists because HL issues statements on
    # HL's own dates, never at a quarter end.
    #
    # ITS FIGURES ARE STRUCK AT AN INSTANT. Shares are valued at a bid delayed fifteen minutes, so
    # a pull taken while New York is open is a mid-session figure; to compare with a closing
    # mark, pull after the 21:00 close.
    Evidence("hl-valuation", "HL valuation (Account Summary download)",
             "HL Account Summary download",
             "the instant it was pulled, e.g. 3 Mar 2025 14:05",
             "HL valuation {reference} ({account})", True, "document",
             ("Code,Stock,Units held", "Amount available to invest"), covers=("positions", "cash")),
    # THE YEAR'S INCOME — HL's "Income transactions" download. One row per payment, with a
    # total, and it is the only HL class that states a period rather than an instant.
    Evidence("hl-income", "HL income transactions", "HL income transactions download",
             "the period, and the instant it was pulled, e.g. 2025 to 3 Mar 2025",
             "HL income transactions {reference} ({account})", False, "document",
             ("Income transactions for my", "Date,Type,Description,Amount"), covers=()),
    # THE DEALING AND CASH LIST — HL's "Portfolio Summary" download, a transaction list and not a
    # summary. AN HL ISA HAS TWO SUB-ACCOUNTS, Capital and Income, and this report is pulled per
    # sub-account with nothing in its shape to say which, so THE REFERENCE SAYS WHICH.
    #
    # A transfer between the two is not an event: it appears on both lists, once each way, under
    # one reference, and entering it from both would book it twice.
    Evidence("hl-transactions", "HL transaction list (Portfolio Summary download)",
             "HL Portfolio Summary download",
             "which sub-account and the instant it was pulled, "
             "e.g. Capital, 3 Mar 2025 14:05",
             "HL transactions {reference} ({account})", False, "document",
             ("Portfolio Summary", "Trade date,Settle date,Reference"), covers=("cash",)),
    # THE ONE-LINE TOTALS — the same "Portfolio Summary" title again, over a different table.
    # It restates what the valuation already says and carries no holdings, so it is a
    # cross-check rather than a source. Kept apart from the valuation precisely BECAUSE the two
    # disagree when pulled minutes apart.
    Evidence("hl-account-totals", "HL account totals (Portfolio Summary download)",
             "HL Portfolio Summary totals download",
             "the instant it was pulled, e.g. 3 Mar 2025 14:10",
             "HL account totals {reference} ({account})", False, "document",
             ("Portfolio Summary", "Account,Stock value,Total cash"), covers=("positions", "cash")),
    # THE MOVEMENTS OF ONE SECURITY — HL's "Security movements" download: every purchase of one
    # holding, each with HL's own reference. It states no date of its own, so its reference is
    # the security and the instant it was pulled; a trade's source names only the day
    # (`trade_source()`), its security and account being the row's own.
    Evidence("hl-movements", "HL security movements", "HL security movements download",
             "the security and the instant it was pulled, e.g. Quenlan Robotics Inc., 3 Mar 2025 14:05",
             "HL security movements {date}", False, "document",
             ("Security movements for:", "DATE, TYPE, REFERENCE, UNIT COST (p), QUANTITY"),
             covers=()),
    Evidence("ig-statement", "IG statement", "IG statement",
             "the statement's own date, e.g. 7 Mar 2025",
             "IG statement {reference}", True, "document", covers=("equity",)),
    # WHICH ENDPOINT ANSWERED IS PART OF THE AUTHORITY: /accounts, /history/activity and
    # /history/transactions are three different claims, so the template carries it. The
    # "IG REST" prefix is what classifies every row feeds/ig.py has composed.
    Evidence("ig-api", "IG API read", "IG REST /history/activity",
             "the dealId or transaction reference the row stores",
             "IG REST {endpoint}, ref {reference}", True, "api", covers=()),
    # THE BALANCE READ, WHICH IS NOT THE ACTIVITY READ: a balance has no dealId.
    #
    # OFFICIAL. STATEMENT_GRADE admits an authenticated API read, and IG issues no statement for an
    # account that has not traded; this figure is what the account is worth — close the positions
    # and that is the money. Levels and /accounts read 0.3s apart reproduce IG's running P/L to the
    # penny, so a reading struck WITH its marks ties exactly.
    Evidence("ig-accounts", "IG account read", "IG REST /accounts, authenticated to the account",
             "the account id and the instant it was read, e.g. AB1CD, 8 Sep 2026 11:23",
             "IG REST /accounts {reference}", True, "reading", covers=("equity",)),
    Evidence("not-on-file", "Not on file", "not on file",
             "what the figure was read from, and when, e.g. ii statement Q1 2026",
             "Not on file: {reference}", False, "none", covers=()),
)


EVIDENCE_BY_KEY = {e.key: e for e in EVIDENCE_CLASSES}

#: CLOSED TO NEW ENTRIES — every class that retrieves nothing (the reasoning is at RETRIEVAL_KINDS
#: above). Derived here because it needs the classes.
CLOSED_TO_NEW_ENTRIES = tuple(sorted(e.key for e in EVIDENCE_CLASSES if e.retrieval == "none"))


def identify(text: str) -> list[str]:
    """Which evidence classes this document's own text matches. Longest fingerprint first.

    On CONTENT, never the filename (see the `fingerprint` note on the classes). A LIST, and more
    than one is an honest answer: a caller that finds two should ask, not take the first, since
    this decides which columns mean what. Empty means no class recognised it — also honest.

    Side effects: none.
    """
    body = text or ""
    hits = [e for e in EVIDENCE_CLASSES if e.fingerprint
            and all(mark in body for mark in e.fingerprint)]
    return [e.key for e in sorted(hits, key=lambda e: -sum(len(m) for m in e.fingerprint))]


#: Where a broker states the instant its figures were struck at, and how it writes the date. HL
#: uses both spellings of the first; an ii contract note states when the trade was dealt.
_DOC_INSTANT = (
    (_re.compile(r"(?:Valuation as at|Spreadsheet created at)[,\s]+(\d{2}-\d{2}-\d{4})"
                 r"[\s,]+(\d{2}:\d{2})"), "%d-%m-%Y %H:%M"),
    (_re.compile(r"\bDATE (\d{2}/\d{2}/\d{4}) TIME (\d{2}:\d{2})\b"), "%d/%m/%Y %H:%M"),
    # ii's notes before 2023 print the dealing line alone, a two-digit year and the time.
    (_re.compile(r"^(\d{2}/\d{2}/\d{2}) (\d{2}:\d{2})$", _re.M), "%d/%m/%y %H:%M"),
)

#: Where a document prints its own reference. An ii contract note prints its number twice, and
#: this is the line that carries nothing else.
_DOC_REFERENCE = (_re.compile(r"\bCONTRACT No\.\s*([A-Z0-9]{5,})\b"),
                  # before 2023 the number stands alone under the BOUGHT or SOLD line
                  _re.compile(r"^(?:BOUGHT|SOLD)\n([A-Z0-9]{6})$", _re.M))


def document_instant(text: str):
    """The instant the document says its own figures were struck at, or None.

    The INSTANT, not the day: these figures move within the day, and a document that states its
    own instant states the only thing that makes its figures comparable with anything. The
    archive name carries it for that reason.

    Returns a `datetime`, or None where the document does not say. Side effects: none.
    """
    for pattern, shape in _DOC_INSTANT:
        m = pattern.search(text or "")
        if m:
            try:
                return _dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", shape)
            except ValueError:
                return None
    return None


def document_reference(text: str) -> str:
    """The reference the document prints for itself, or "".

    Only where it prints one: a contract note's number. A download's reference is the query
    that reproduces it, which the document cannot state, so it stays for a person to type.

    Side effects: none.
    """
    for pattern in _DOC_REFERENCE:
        m = pattern.search(text or "")
        if m:
            return m.group(1)
    return ""


def evidence_source(key, reference="", date="", account="", endpoint=""):
    """The provenance line for this class, in the shape the record already uses.

    "" for an unknown class, never an invented shape: a `source` cell is read by a person looking
    for the document. `endpoint` serves ig-api alone, whose authority depends on which read
    answered.
    """
    ev = EVIDENCE_BY_KEY.get(key)
    if not ev:
        return ""
    line = ev.source.format(reference=str(reference or "").strip(),
                            date=str(date or "").strip(),
                            account=str(account or "").strip(),
                            endpoint=str(endpoint or "").strip())
    # An unfilled slot leaves "()" or a double space behind; tidy rather than emit it.
    line = line.replace("()", "").replace("  ", " ")
    return line.strip().rstrip("(").strip()


def trade_source(key, date, endpoint=""):
    """A TRADE OR SALE'S `source`, ONE FORMAT FOR EVERY ACCOUNT: who issued the document and
    what it is, in its class's own words, then its date — "ii contract note 3 Mar 2025",
    "HL security movements 4 Mar 2025", "IG statement 7 Mar 2025". An API read names its endpoint
    before the day it was read: "IG REST /history/activity 10 Mar 2025".

    NOTHING ELSE. The deal's own reference is the row's `broker_ref`, and its account and
    security are its own columns, so a line repeating them says the same thing twice and the
    two copies can disagree. Other tables keep their class's template: they have no
    `broker_ref` to hold a reference.

    `date` is ISO. "" for an unknown class or an unreadable date, never an invented shape.
    """
    ev = EVIDENCE_BY_KEY.get(key)
    try:
        day = _dt.date.fromisoformat(str(date or "").strip()[:10])
    except ValueError:
        return ""
    if not ev:
        return ""
    return " ".join(p for p in (_source_prefix(ev), str(endpoint or "").strip(),
                                f"{day:%d %b %Y}") if p)


def in_trade_source_format(line, key):
    """Whether `line` is a trade or sale's `source` as `trade_source()` writes it for the class
    `key`: the class's own words, an API read's endpoint, then a date. The bench asks it before
    a row is written, so a typed line in another shape is refused at entry rather than found by
    the guard once it is in the store."""
    ev = EVIDENCE_BY_KEY.get(key)
    if ev is None:
        return False
    return bool(_re.fullmatch(rf"{_re.escape(_source_prefix(ev))}( /\S+)? \d{{2}} [A-Z][a-z]{{2}} "
                              rf"\d{{4}}", str(line or "").strip()))


#: THE CLASSES WHOSE REFERENCE IS THE DEAL'S OWN — one document per deal, named by its number. A
#: row citing one stores the number in `broker_ref`, and the archive finds the document by it.
REFERENCE_IS_THE_DEAL = {"ii-contract-note"}


_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


def _source_prefix(ev):
    """The literal text a class's source line begins with, before its first slot."""
    return ev.source.split("{")[0].strip()


def template_pattern(ev):
    """The pattern a line in this class's template matches, each slot a named group. An account
    slot left empty is tidied away with its brackets, as `evidence_source()` writes it."""
    pattern = _re.escape(ev.source).replace(_re.escape(" ({account})"),
                                            "(?: \\((?P<account>.*?)\\))?")
    for slot in ("reference", "date", "endpoint"):
        pattern = pattern.replace(_re.escape("{%s}" % slot), f"(?P<{slot}>.*?)")
    return _re.compile(pattern)


def evidence_from_source(line):
    """The Evidence class that composed this `source` line, or None.

    Matched on each class's OWN template, not a second list of spellings; the longest literal
    prefix wins, so "IG statement 11 Aug 2026" is ig-statement and not ig-api. None is a FINDING,
    not a defect to paper over: nothing can then say what would retrieve the row.
    """
    text = str(line or "").strip()
    if not text:
        return None
    for ev in sorted(EVIDENCE_CLASSES, key=lambda e: -len(_source_prefix(e))):
        prefix = _source_prefix(ev)
        if len(prefix) > 2 and text.startswith(prefix):
            return ev
    # The one template whose literal prefix is only the broker's name — "IG {reference}". Two
    # characters is not a match worth making on its own, so it is decided on what FOLLOWS.
    if _re.match(r"IG [A-Z0-9]{10,}$", text):
        return EVIDENCE_BY_KEY["ig-api"]
    return None


#: The classes whose reference IS A DATE (the statements, and the HL downloads, retrieved by
#: account, report and the instant pulled) as against a NUMBER (the contract notes). Public
#: because `desk/doors/commit.py:_covers()` asks the same question: a date does not identify an
#: account, and a contract note number does. The date is found wherever in the reference it sits.
REFERENCE_IS_A_DATE = {"ig-statement", "ii-statement", "hl-statement", "hl-movements",
                        "hl-valuation", "hl-income", "hl-transactions", "hl-account-totals",
                        "ii-valuation", "ii-transactions"}


def archive_reference(line, stored_reference=""):
    """What should name this row's document in `_archive/statements/`, or None.

    None means the row cites no retrievable DOCUMENT — an API read, a row not on file, an S.104
    adjustment, or a line no class composed — each of which answers limb 3 its own way or cannot.

    WHAT TO LOOK FOR COMES FROM THE CLASS: a statement by its DATE, read out of the line; a
    contract note by the deal's NUMBER, which the row stores (`REFERENCE_IS_THE_DEAL`), both
    matched against `ARCHIVE_CONVENTION`. "" for a statement whose line carries no date, or a
    contract note whose row stores no number: it cites a document and says nothing that could
    find it, which is a gap and not "no document". Never a reference pattern the class does not
    name: one invented out of English sends you looking for a document that was there.
    """
    ev = evidence_from_source(line)
    if ev is None or ev.retrieval != "document":
        return None
    text = str(line)
    if ev.key in REFERENCE_IS_A_DATE:
        m = _re.search(rf"\b(\d{{1,2}})\s+({_MONTHS})\s*(\d{{4}})?", text)
        # NO DATE IS A GAP, NOT "NO DOCUMENT": the line cites a statement and says nothing that
        # finds it.
        return f"{m.group(1).zfill(2)} {m.group(2)} {m.group(3) or ''}".strip() if m else ""
    return str(stored_reference or "").strip()


#: An IG deal reference. A row storing one answers limb 3 by itself: the dealId retrieves the deal
#: through IG's authenticated API and appears in every statement listing the position
#: (`rules.STATEMENT_GRADE`).
_DEAL_REFERENCE = _re.compile(r"^DIAAAA[A-Z0-9]{6,}$")


def is_deal_reference(ref) -> bool:
    """Is this stored reference one that retrieves the row on its own?"""
    return bool(_DEAL_REFERENCE.match(str(ref or "").strip()))


def _cited(ev, line, slot):
    """What a source line names through one of its class's own slots, or "".

    Read with the TEMPLATE, never a list of names: this module holds no store.
    """
    if "{" + slot + "}" not in ev.source:
        return ""
    parts = _re.split(r"(\{[a-z]+\})", ev.source)
    pattern = "".join(f"(?P<{p[1:-1]}>.+?)" if p.startswith("{") else _re.escape(p)
                      for p in parts)
    m = _re.match(pattern + r"\s*$", str(line or "").strip())
    return m.group(slot).strip() if m else ""


def _cited_account(ev, line):
    """The account a source line names through its class's own `{account}` slot, or ""."""
    return _cited(ev, line, "account")


def document_not_on_file(line):
    """For a `not-on-file` row, the class of the document it was read from, where its reference
    names one in that class's own words ("ii statement 30 Jun 2026"); None otherwise.

    Side effects: none.
    """
    ev = evidence_from_source(line)
    if ev is None or ev.retrieval != "none":
        return None
    return evidence_from_source(_cited(ev, line, "reference"))


def filed_as(line, archive_names, stored_reference="", account=""):
    """The archived names this row's cited document matches — `reference_resolves()`'s answer
    as the names themselves, for a caller that has to open the document. None for a row that
    cites none. The matching rules are `reference_resolves()`'s docstring.
    """
    if is_deal_reference(stored_reference):
        return None                       # the dealId retrieves it; no file is owed
    ref = archive_reference(line, stored_reference)
    if ref is None:
        return None
    if not ref:
        return []                         # a document cited, and nothing that could find it
    ev = evidence_from_source(line)
    must = [ref]
    if ev.key in REFERENCE_IS_A_DATE:
        who = _cited_account(ev, line) or str(account or "").strip()
        must += [ev.authority.lower()] + [a for a in [who] if a]
    return [name for name in archive_names if all(m.lower() in name.lower() for m in must)]


def reference_resolves(line, archive_names, stored_reference="", account=""):
    """Does this row's cited document actually sit in the archive?

    True / False for a row that cites one; None for a row that does not, so a caller can tell
    "answered another way" from "answered, and the answer is missing".

    THE ROW'S OWN STORED REFERENCE WINS. `broker_ref` says WHICH document; the date in the `source`
    line is when the statement was READ, and matching it against filenames would report archived
    documents missing.

    A DATE IS NOT A DOCUMENT. Where the reference is only a date, the name must also carry the
    class's authority, and the account: the one the line names, or else the row's own (`account`),
    which a trade's line leaves to its column. On a quarter end every broker's documents share
    the date, and a date alone would match one broker's document to another's. A contract note
    number identifies its document by itself.
    """
    names = filed_as(line, archive_names, stored_reference, account)
    return None if names is None else bool(names)

