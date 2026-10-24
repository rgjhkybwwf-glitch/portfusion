"""
rules.py — THE RECORD'S RULES. It loads the facts from store/ and holds what they must satisfy:
the assertions, the derivations and the caps. It knows nothing about pages; the desk and the
report render the record through the engine.

The rules code must render or check live here,
once — SOURCE_HIERARCHY, STATEMENT_GRADE, SPREAD_BET, ARCHIVE_CONVENTION, the caps — and
everything that shows one reads it from here.

A book's store must hold every table the schema registers, checked just below before anything
is read.
"""
import collections as _collections
import contextlib as _contextlib
import datetime as _dt
import re as _re
from typing import NamedTuple

# ==============================================================================================
# THE BOOK'S STORE IS WHOLE, OR NOTHING IS READ. This module LOADS the facts, so a book whose
# folder lacks a table would still build, from fewer facts. The file list is DERIVED from
# schema.TABLES: a new table cannot be left out.
# ==============================================================================================
from portfusion.record import schema         # THE SCHEMA — column types, and it validates on load
from portfusion.record import order as _order

if not schema.STORE.is_dir():
    raise SystemExit(
        "\nSTOPPED — there is no store/ folder.\n"
        f"  looked for: {schema.STORE}\n"
        "  Every fact in this record lives in there. Checked separately from the file list\n"
        "  below so a missing FOLDER does not report as seventeen missing files.\n")

_MISSING = sorted(f"{t.name}.csv" for t in schema.TABLES.values() if not t.path.exists())
if _MISSING:
    raise SystemExit(
        "\nSTOPPED — the store is incomplete.\n"
        f"  looked in: {schema.STORE}\n"
        f"  missing:   {', '.join(_MISSING)}\n"
        "  A book's store holds every table the schema registers, empty or not. Reading it\n"
        "  without them would build from fewer facts than the book has.\n")


# ==============================================================================================
# THE DERIVATION BAND — and why it is not zero.
# ----------------------------------------------------------------------------------------------
# Two figures struck at the same instant still differ a little: the book values each holding at the
# level it fetched, the broker at ITS instant with ITS rates, leaving FX, rounding, and bid against
# last. Two reads minutes apart can differ by a few tenths of a percent.
#
# HALF A PERCENT, and the difference is PRINTED whether or not it passes, so drift inside the band
# stays visible. A figure approaching the band means the DERIVATION has drifted, not the market;
# widening it would be the wrong response. It governs every pair `Book.comparability()` finds
# comparable. Tighten it from measurement once a comparable document pair is on file.
RECON_LIVE_TOLERANCE_PCT = 0.005

# THE CLOSE WINDOW: a missed evening or two does not matter, and a quarter end needs only to be
# close. Two uses, one span. A frozen quarter end takes
# each line's mark NEAREST it within this many days either side — `Book.freeze_rows()`. A broker
# reading up to this many days after it confirms it — `Book.quarter_readings()`.
CLOSE_CHECK_WINDOW_DAYS = 7


# ==============================================================================================
# NO BAND BY DAYS. A tolerance scaled by the gap between two figures either fired whenever the book
# moved (by several percent in a day) or was wider than a wrong quantity. `Book.comparability()` asks the
# real question instead — do the two describe the same state of the market? The retired code is
# in the project's history.

# ==============================================================================================
# THE TWO RULES THAT CODE RENDERS. The Legend has to show them, so the words exist here, once.
# CLAUDE.md points at them, and test_record.py refuses a second telling anywhere else.
# ----------------------------------------------------------------------------------------------
SOURCE_HIERARCHY = (
    "contract note / statement / authenticated broker API read carrying its own reference "
    "> broker platform or app > web > recollection")

SOURCE_HIERARCHY_NOTE = (
    "An API read qualifies for the top rung only when it is authenticated to the account and the "
    "row stores the reference that retrieves it - a dealId, a transaction reference, or for a "
    "live balance the account and the instant it was read. A reading without that reference "
    "ranks below.")

STATEMENT_GRADE = (
    "Statement-grade means three things, and the format is not one of them. The figure is dated; "
    "it comes from an authority that can be asked again - the broker, not a recollection; and it "
    "carries a named reference that retrieves it: a contract note number, a statement, or a deal "
    "reference. A PDF satisfies this. So does an authenticated API read. A figure that nothing "
    "retrieves a second time does not.")
# WHAT THE DOOR CHECKS: statement-grade is asked once, at entry, rather than a column asserting it
# about a row afterwards.

SPREAD_BET = (
    "A spread bet has the figures IG prints, and they are not interchangeable. The FUNDS are the "
    "money in the account; the RUNNING PROFIT OR LOSS is the open positions' gain or loss, run on "
    "the full notional; the EQUITY is funds plus running profit or loss, the account's money; the "
    "DEPOSIT is the part of that equity IG sets against the open positions, the margin in IG's "
    "word; the AVAILABLE is equity less deposit; and the NOTIONAL, IG's Position (net), is the "
    "full exposure to the instruments, which is not money. The same hold for one instrument or "
    "across many.")
# THE ONLY DEFINITION OF A SPREAD BET IN THIS PROJECT. Told in many files, each telling slightly
# different, it kept tripping the book up; it is stated here, and CLAUDE.md and the Method page
# point here. What actually stops the mistake is structure —
# `Book.NAV_BASES`/`EXPOSURE_BASES` and `roll_up()`'s BasisError — not these words.


ARCHIVE_CONVENTION = (
    "A document in _archive/statements/ is named "
    "DD Mon YYYY [HH.MM] <broker> <doc kind> <REF> (<what it covers>).<ext>, and the name is "
    "DERIVED from the three evidence limbs rather than typed: `dated` is the date, `authority` "
    "is the broker and the doc kind, `reference` is the REF. The date is the DOCUMENT's, never "
    "the day it was filed. The instant appears once, after the date: the one the document states "
    "for itself on that date, or else the one the reference says it was pulled at, which then "
    "leaves the REF - two pulls of one account five minutes apart are different figures, and a "
    "name that cannot tell them apart loses one of them.")
# THE ONLY STATEMENT OF THE ARCHIVE CONVENTION, for the same reason: five tellings had gone stale
# in five places. test_record.py refuses a second one. Point at it.

#: THE BOOK'S SETTINGS, store/settings.csv — `schema.SETTING_KEYS` says what each one is.
SETTINGS = dict(schema.load("settings"))
assert len(SETTINGS) == len(schema.load("settings")), "settings.csv names a key twice"

#: THE RECORD BEGINS ON A 1 JANUARY. The year's return and the return since the start are each
#: measured from a frozen 31 December (`Book.year_to_quarter()`), and a record beginning on any
#: other day has no such date. Refused here, where the setting is read, rather than as a
#: KeyError on the first page that asks.
_begins = _dt.date.fromisoformat(SETTINGS["record_begins"])
if (_begins.month, _begins.day) != (1, 1):
    raise ValueError(
        f"settings.csv record_begins is {_begins}, and the record must begin on a 1 January: "
        f"the year's return is measured from the 31 December before it.")

#: REASONING IS OWED FROM HERE. A reason written once the outcome is known is worth close to
#: nothing, so an earlier blank is never owed. A DATE, NOT A PURGE: a position opened next week
#: is in scope and one opened last year is not, with no list to keep. PER HALF: the thesis is
#: dated by the entry and the exit reason by the exit. `Book.with_reasoning()` applies it.
REVIEW_FROM = _dt.date.fromisoformat(SETTINGS["reasoning_owed_from"])


# ==============================================================================================
# THE TWO PRICE-FRESHNESS LIMITS, together because they catch different defects:
#
#   PRICE_AGE_LIMIT     the OLDEST mark against TODAY: the book has not been refreshed in a while.
#                       Generous, because the practice is weekly or wider (`docs/prices.md`), and
#                       a rule that fires on a normal week gets ignored.
#   PRICE_SPREAD_LIMIT  the oldest mark against the NEWEST: a ticker missed in a sweep, which the
#                       age limit cannot see. Four days covers the two-feed split (shares at a
#                       close, IG levels live the next trading day) with slack.
#
# Here and not in a renderer, because the engine must ask both. CALENDAR days, not trading days:
# trading days would need an exchange calendar per venue, a dependency not worth a warning.
PRICE_AGE_LIMIT = 21
PRICE_SPREAD_LIMIT = 4


# ==============================================================================================
# WHEN EACH VENUE CLOSES, IN UK TIME. `feeds/tv.py` reads it to tell a line still trading, whose
# live quote is a price, from one that has shut, whose day bar is. KEYED BY CURRENCY, so a new
# market joins by existing. (Until 30 Sep 2026 it also set when a share account's document could
# be judged; a share account is checked on units now, which a close does not move.)
VENUE_CLOSE_UK = {"GBP": "16:30", "EUR": "16:30", "DKK": "16:00", "USD": "21:00"}
#: A currency not listed is taken to close with London; add its venue's close above when it is
#: held, so a line is never refused for want of one.
VENUE_CLOSE_UK_DEFAULT = "16:30"


def uk_date(at: str) -> str:
    """The UK calendar date of a UTC instant (`YYYY-MM-DDTHH:MM:SSZ`). The book dates everything
    in UK days, and a read at 00:30 BST is 23:30 UTC on the day before.

    Side effects: none.
    """
    return _in_uk(at).date().isoformat()


def _in_uk(at: str) -> "_dt.datetime":
    """A UTC instant, as UK wall-clock time."""
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromisoformat(str(at).replace("Z", "+00:00")).astimezone(
        ZoneInfo("Europe/London"))


def utc_instant(uk_time: str) -> str:
    """A UK wall-clock time — "2025-03-03 14:05", as a document or its download states one — as
    the UTC instant an `at` column holds: "2026-09-30T17:40Z". To the minute when that is all the
    time says, so the column never claims a second nobody read.

    Side effects: none.
    """
    from zoneinfo import ZoneInfo
    t = _dt.datetime.fromisoformat(str(uk_time)).replace(tzinfo=ZoneInfo("Europe/London"))
    seconds = len(str(uk_time).replace("T", " ")) > 16
    return t.astimezone(_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ" if seconds else "%Y-%m-%dT%H:%MZ")


# ==============================================================================================
# THE EVIDENCE CLASSES and THE BROKERS' CODES live in their own pure modules, re-exported here, so
# `D.EVIDENCE_CLASSES`, `D.identify()`, `D.HL_CODES` and the rest read as ever. Neither derives
# anything from the store, so `reload_store()` re-executing this module alone stays correct.
#
#   rules_evidence.py   what a document IS, and what retrieves it a second time
#   rules_brokers.py    HL's own codes, and how an export is read
from portfusion.record.rules_evidence import *    # noqa: F401,F403
from portfusion.record.rules_brokers import *     # noqa: F401,F403


# ==============================================================================================
# IDENTITY — who the securities are
# ----------------------------------------------------------------------------------------------
# COMPANIES is one row per issuer and is the single source for names, sectors and regions.
# SECURITIES maps each code held, reserved or closed to its issuer and its kind.
# ==============================================================================================


# ============================================================================
# IDENTITY, from the store: companies.csv (one row per ISSUER) and securities.csv (one row per CODE
# held, reserved or closed). Two tables because ONE ISSUER CAN HOLD SEVERAL CODES — Orlant is
# ORLA and ORLA SB, Askel the Copenhagen line and the NYSE ADR — joined by full legal name.
#
# Two facts nothing else states: sector and region are an editorial first pass, not sourced
# data; the tickers were source-verified against Yahoo Finance and the exchanges. Rows stay tuples
# in file order, so positional reads downstream are unchanged.
# ============================================================================
COMPANIES = schema.load("companies")
SECURITIES = schema.load("securities")
#: THE ONE PLACE A LINE'S KIND IS STORED: code -> shares | spread bet (schema.KINDS). A leg reads
#: its kind here; the register's kind for its account is checked against it below.
KIND_OF_CODE = {r[0]: r[schema.TABLES["securities"].header.index("held_as")] for r in SECURITIES}


# ==============================================================================================
# MARKET DATA — what things are worth, and when that was true
# ----------------------------------------------------------------------------------------------
# Two separate things that must never be merged: the ledger records what was PAID; these record what
# things are worth NOW. Spread-bet pricing is keyed by CONTRACT (LEG_CONTRACT), never by ticker —
# one ticker can have legs on two contracts at two different levels.
#
# REFRESHING PRICES: update the price AND its date together. The Dashboard's freshness cell reads
# these dates, so a price changed without its date makes the whole book claim to be fresher than it is.
# ==============================================================================================

fx_rows = schema.load("fx")

CURRENT_PRICES = schema.load("current-prices")

# ==============================================================================================
# STATEMENT-PRICED HOLDINGS — no usable price feed AND immaterial, carried at the last broker or
# statement price rather than refreshed. Such a holding is excluded from `Book.price_ageing()`,
# printed apart by `--prices`, shown in the Price Refresh's Carried block where it cannot be
# ticked, and refused by `desk/doors/marks.py`.
#
# NARROW, AND IT MUST STAY SO: BOTH no feed AND immaterial. A line with no feed that IS material
# is NOT here: it is derived from a related listing instead. Adding to this dict is a
# decision about what the book stops watching, never a way to quiet a check.
# ==============================================================================================
# EMPTY by default. The mechanism stays.
STATEMENT_PRICED = {}

# ==============================================================================================
# CARRIED RATES — the FX half of the same idea. A currency here is deliberately NOT refreshed;
# its live rate is carried at its last level, still on file and still read. EMPTY by
# default. The mechanism stays.
#
# A second dict, because the reason differs: not "no feed and immaterial" but NOTHING THE BOOK
# VALUES IS DENOMINATED IN IT. Structure rather than a note in the row's source text, so the Price
# Refresh can know not to ask for it. Adding a key is a decision about what the book stops watching,
# made in settings.csv (`rate_carried`).
# ==============================================================================================
RATE_CARRIED_WHY = ("nothing the book values is denominated in it, so refreshing it would assert "
                    "an observation nobody made; it is kept for the rows that still read it")
RATE_CARRIED = {k: RATE_CARRIED_WHY for k in SETTINGS.get("rate_carried", "").split()}

# ==============================================================================================
# WHICH RESEARCH NOTES COVER WHICH INSTRUMENT — store/research-notes.csv: ticker -> (ref, date,
# URL), oldest first. A ticker with no entry is not missing data; the book publishes on a subset of
# what it holds.
#
# THE RESEARCH REPO IS THE SOURCE OF TRUTH FOR A REF (CLAUDE.md). This records what the BOOK cites,
# so the book builds without that repo; `desk/intake/research.py` reads the repo so the bench can
# OFFER a ref. THE REF IS NOT THE URL — never derive one from the other. One note can cover both
# sides of a pair: Orlant's is cited by ORLA and ORLA SB, a mapping that is the book's own.
# ==============================================================================================
RESEARCH_NOTES: dict[str, list[tuple[str, str, str]]] = {}
for _r in schema.load("research-notes"):
    RESEARCH_NOTES.setdefault(_r[0], []).append((_r[1], _r[2].isoformat(), _r[3]))

# AN OPEN SHARE WITH NO PRICE STOPS THE BUILD: `engine.value_legs()` raises on the missing mark. There
# is no hand-kept fallback. tests/test_record.py::test_every_open_share_has_a_price_route names
# every offender at once, without a build.


# ==============================================================================================
# THE LEDGER — every transaction, and the parcels they form
# ----------------------------------------------------------------------------------------------
# `trades` is the record: one row per transaction. A sale is entered ONCE, in `exits`, and the
# ledger's Sell rows are generated from it, so the two cannot disagree. REALISATION ID, not ticker,
# joins buys to sells, because a ticker can be an open holding and a realised parcel at once.
#
# ADDING A TRADE: date · direction · account · ticker · quantity · price · a NAMED source (document
# and broker reference). Missing one, THE TRADE WAITS FOR THE DOCUMENT, which is a gate.
# ==============================================================================================

# ==============================================================================================
# THE TRADE ROW. A NamedTuple, so positional reads (t[4]) still work and the names are additive —
# a declaration cannot drift from the tuple it declares.
#
# WHETHER A LEG IS STILL HELD IS DERIVED, never stored: which legs a sale consumed comes from
# `engine.share_pools()` and `EXIT_LEG_MATCH`, and the ledger's `open_leg` says it.
# ==============================================================================================
class Buy(NamedTuple):
    trade_id: str               # T-nnn, never renumbered and never reused
    date: str                   # ISO
    source: str                 # the NAMED source: document + broker ref. One of the seven fields.
                                # What DOCUMENT backs this row — never what kind of
                                # number it is (glossary §2).
    acct: str                   # must be in ACCOUNT_ORDER — matched as a STRING by every SUMIFS
    ticker: str                 # the security's code, as securities.csv registers it; its kind
    cur: str                    # the currency `traded_price` is stated in; GBP on a spread bet, IG's
                                # "Curr £" — the stake's, never the market's
    qty: int | None             # shares; blank on a spread bet, whose size is its stake
    stake: int | float | None   # £ per point, spread bets only. MIXED, deliberately — see schema.py
    cost: float | None          # a share leg's settled GBP; blank on a spread bet
    level_points: float | None  # a spread bet's entry level in points, as IG states it
    broker_ref: str | None      # the BROKER's reference — IG bet ref, ii contract no., HL ref.
                                # The broker's reference; `trade_id` (T-nnn) is the book's own.
    note: str                   # what happened, where the row's own columns do not say it
    contract: str | None        # the IG contract a spread-bet leg is on; contracts.csv holds its epic
    traded_price: float | None  # per share in `cur`, as the deal's document states it
    rate: float | None          # the broker's rate, where the document states one

    @property
    def mode(self) -> str:
        """HOW THE LEG IS COSTED, from its code's kind: `sb` for a spread bet's entry level,
        `cost` for a settled GBP total."""
        return "sb" if KIND_OF_CODE.get(self.ticker) == "spread bet" else "cost"

    @property
    def size(self) -> int | float:
        """HOW MUCH THE LEG IS, in its own unit: shares, or £ per point for a spread bet. The
        store keeps the two apart (`qty`, `stake`); the ledger rolls up on this."""
        return self.qty if self.qty is not None else self.stake

buys = [Buy(*_r) for _r in schema.load("buys")]

#: THE IG CONTRACTS, contract -> epic (None once closed), from store/contracts.csv; and how IG
#: funds each, contract -> daily | dated (schema.FUNDINGS).
_contract_rows = schema.load("contracts")
CONTRACTS = {_r[0]: _r[1] for _r in _contract_rows}
CONTRACT_FUNDING = {_r[0]: _r[2] for _r in _contract_rows}
#: The line each contract is on: contract -> its code on securities.csv.
CONTRACT_CODE = {_r[0]: _r[3] for _r in _contract_rows}

# WHICH CONTRACT EACH SPREAD-BET LEG IS ON, read off the legs themselves: trade id -> contract.
LEG_CONTRACT = {t.trade_id: t.contract for t in buys if t.contract}

# A SPREAD-BET LEG IS PRICED BY ITS CONTRACT, open or closed. One naming none would be valued at
# nothing and read as a loss of its whole entry notional.
_unpriced = [t.trade_id for t in buys if t.mode == "sb" and not t.contract]
assert not _unpriced, (f"spread-bet legs {_unpriced} name no contract: give each its contract "
                       f"on buys.csv, and the contract its row in contracts.csv")
# A LEG IS ON ITS CONTRACT'S LINE: the contract names its code, and the leg's ticker is that code.
_off_line = [t.trade_id for t in buys if t.contract and CONTRACT_CODE.get(t.contract) != t.ticker]
assert not _off_line, f"spread-bet legs {_off_line} name a contract on another line"

# --- NAMING MIGRATION: remap tickers to real codes before the sort ---
# ---- Exits: defined before the merged ledger, which is built from them ----
class Sale(NamedTuple):
    sale_id: str                # E-nnn
    date: str
    acct: str
    ticker: str                 # the security's code, as securities.csv registers it
    qty: int | None             # shares; blank on a spread-bet sale
    stake: int | float | None   # £ per point, a spread-bet sale's size; blank on a share sale
    traded_price: float         # the execution price as its document states it, or a bet's closing level
    cur: str                    # the currency `traded_price` is stated in, as `Buy.cur`
    rate: float | None          # the broker's rate, where the document states one
    proceeds: float             # GBP. Every exit in the book is GBP-denominated, spread bets included
    source: str
    broker_ref: str | None      # the reference that retrieves THIS sale: an IG close's deal
    realisation_id: str         # R-..., the parcel this sale belongs to — schema.py says what that is
    closes: str | None          # T-nnn, the buy leg it closed, when the broker names one
    note: str

    @property
    def size(self) -> int | float:
        """How much the sale is, in its own unit: shares, or £ per point (`Buy.size`)."""
        return self.qty if self.qty is not None else self.stake

sales = [Sale(*_r) for _r in schema.load("sales")]

# AN EVENT'S ID IS ITS NAME: an exit names the leg it closes by one, and a sale the parcel it
# realises. Two rows under one id are one row too many, with nothing to say which. Nothing refused
# it until 21 Oct 2026, so a bench item proposing two exits as one id reached the store.
for _table, _ids in (("buys", [t.trade_id for t in buys]), ("sales", [e.sale_id for e in sales])):
    assert len(set(_ids)) == len(_ids), (
        f"{_table}.csv ids must be distinct: "
        f"{sorted({i for i in _ids if _ids.count(i) > 1})} appear more than once")

# A DEAL'S PRICE IS STATED IN STERLING OR IN ITS SHARE'S OWN CURRENCY, and the broker's rate stands
# only beside a price in a currency that needed one. A spread bet is sterling.
_CURRENCY_OF = {r[0]: r[schema.TABLES["securities"].header.index("currency")] for r in SECURITIES}
_misstated = [
    i for i, code, cur, price, rate in
    [(t.trade_id, t.ticker, t.cur, t.traded_price, t.rate) for t in buys]
    + [(e.sale_id, e.ticker, e.cur, e.traded_price, e.rate) for e in sales]
    if cur not in ("GBP", _CURRENCY_OF.get(code))
    or (KIND_OF_CODE.get(code) == "spread bet" and cur != "GBP")
    or (rate is not None and (cur == "GBP" or price is None))]
assert not _misstated, (f"{_misstated} state a price in neither sterling nor the share's own "
                        f"currency, or a rate beside no foreign price: cur is the currency the "
                        f"document states the price in, and rate the broker's for it")


# ---- REASONING: why a position was taken and why it was closed, ONE ROW PER DECISION, dated by
# the trade it explains and appended, never replaced. A fact, so it is in the store, where the
# bench can write it. When a judgement is owed is `REVIEW_FROM`'s, above.
class Reasoning(NamedTuple):
    ticker: str
    date: _dt.date              # the date of the trade or sale this why explains
    why_entered: str | None     # None on a sale's row — a blank, not a gap
    why_exited: str | None      # None on a purchase's row

reasoning = [Reasoning(*_r) for _r in schema.load("reasoning")]

#: Every why on each ticker, oldest first: {ticker: [Reasoning, ...]}. `Book.with_reasoning()`
#: takes the ones dated within a position's life.
REASONING: dict[str, list[Reasoning]] = {}
for _r in sorted(reasoning, key=lambda r: r.date):
    REASONING.setdefault(_r.ticker, []).append(_r)

# ---- REALISATIONS: which sells belong together, and what cost each released ----
# A realisation is one closed parcel: the sell(s) that closed it, plus the buy cost they released.
# MEMBERSHIP IS STATED ON THE SALE'S OWN ROW — `sales.csv` `realisation` and `closes` — so the
# bench writes it with the sale, and nothing about a sale lives where the bench cannot reach.
#
#   REALISATION_BY_EXIT  exit_id -> the parcel it belongs to
#   EXIT_LEG_MATCH       exit_id -> the spread-bet leg it closed, whose own entry cost it releases.
#                        A share sale names none: it releases its pool's average, and
#                        `engine.share_pools()` says which realisation emptied which buy.
REALISATION_BY_EXIT = {e.sale_id: e.realisation_id for e in sales}
EXIT_LEG_MATCH = {e.sale_id: e.closes for e in sales if e.closes}

# ACCOUNT-LEVEL BREAKDOWN: a ticker held in more than one account shows a row per account under its
# aggregate, each summing back to it. DERIVED from the ledger (see the foot of this file), so a
# ticker traded in two accounts HAS a breakdown; a hand-kept list once missed one and nothing
# failed. The tests check the derivation.


# ==============================================================================================
# STATEMENT-SOURCED FIGURES — costs, income, cash, reconstructions
# ----------------------------------------------------------------------------------------------
# Typed from statements and contract notes, each row carrying its source reference. The
# quarter-end reconstructions and snapshots are FROZEN records of what was believed at a past date:
# never recomputed, and not expected to tie to today's ledger.
# ==============================================================================================

# Grouped by account, then quarter.
class CostIncomeRow(NamedTuple):
    date: str
    account: str
    category: str               # Cash interest | Dividend | Fee | Funding interest
    detail: str
    amount: float               # costs negative, income positive — ALWAYS GBP
    source: str
    note: str
    # THE CONVERSION, where there was one. Blank on every GBP row. schema.py says why.
    currency: str = ""
    local_amount: float | None = None
    rate: float | None = None   # the broker's, where its document states one; else the day's close
    ticker: str = ""            # the line a dividend was paid on; blank on every other row

ci_rows = [CostIncomeRow(*_r) for _r in schema.load("income")]

# ----------------------------------------------------------------------------------------------
# WHOSE INCOME IS IT — the capital's, or the account's?
# ----------------------------------------------------------------------------------------------
# THE RETURN IS ON CAPITAL INVESTED, so its numerator takes only what the POSITIONS earn and cost:
# dividends, and the funding interest that holds a spread bet open. Platform fees and interest on
# idle cash belong to the ACCOUNT and stay out of the return.
#
# THIS FILTERS THE RETURN AND NOTHING ELSE. `income_by_account()` returns every category, and
# YTD income on the Dashboard is the whole of it — a true figure about the book.
POSITION_INCOME = ("Dividend", "Funding interest")
ACCOUNT_INCOME = ("Cash interest", "Fee")
# EVERY CATEGORY IN EXACTLY ONE. The loader refuses a category `schema.INCOME_CATEGORIES` lacks;
# one declared there and placed in neither would fall silently out of the return.
assert sorted(POSITION_INCOME + ACCOUNT_INCOME) == sorted(schema.INCOME_CATEGORIES), \
    "an income category is in neither half, or in both"

# ----------------------------------------------------------------------------------------------
# FUNDING INTEREST IS THE CONTRACT'S, NOT THE ACCOUNT'S (13 Oct 2026). IG charges it on a daily
# funded bet for each night a leg is held and on a dated bet never (schema.FUNDINGS), so a row
# belongs to an account holding such a leg on the nights it names, in IG's own words on the row:
# "Long Interest for US/Can shares 03/02/25 to 05/02/25". The load refuses a row no such leg
# explains; the audit asks the other way round (Book.funding_gaps).
# ----------------------------------------------------------------------------------------------
_NIGHTS = _re.compile(r"(\d{2}/\d{2}/\d{2})(?:\s+to\s+(\d{2}/\d{2}/\d{2}))?")


def funding_nights(detail: str, dated) -> list[_dt.date]:
    """The nights a funding-interest row charges for: the day or span its detail names, or the
    night before the row's own date when it names none."""
    m = _NIGHTS.search(detail or "")
    if not m:
        return [_dt.date.fromisoformat(str(dated)[:10]) - _dt.timedelta(days=1)]
    first = _dt.datetime.strptime(m.group(1), "%d/%m/%y").date()
    last = _dt.datetime.strptime(m.group(2), "%d/%m/%y").date() if m.group(2) else first
    return [first + _dt.timedelta(days=i) for i in range((last - first).days + 1)]


#: EVERY LEG ON A DAILY FUNDED CONTRACT, built once with the tables: (account, leg, opened,
#: closed — None while held). A table of the record, so a Book pins it like the rest.
_sold_on = {e.sale_id: _dt.date.fromisoformat(str(e.date)[:10]) for e in sales}
_closed_on = {tid: _sold_on[eid] for eid, tid in EXIT_LEG_MATCH.items()}
DAILY_FUNDED_LEGS = [(t.acct, t.trade_id, _dt.date.fromisoformat(str(t.date)[:10]), _closed_on.get(t.trade_id))
                     for t in buys if t.contract and CONTRACT_FUNDING.get(t.contract) == "daily"]


def _held_overnight(account: str, night: _dt.date) -> bool:
    return any(a == account and opened <= night and (closed is None or night < closed)
               for a, _leg, opened, closed in DAILY_FUNDED_LEGS)


_unfunded = [f"{r.date} {r.account}: {r.detail!r} charges nights on which none of the account's "
             f"daily funded legs was held"
             for r in ci_rows if r.category == "Funding interest"
             and not any(_held_overnight(r.account, n) for n in funding_nights(r.detail, r.date))]
if _unfunded:
    raise ValueError("A FUNDING ROW NAMES NO DAILY FUNDED LEG HELD ON ITS NIGHTS:\n  "
                     + "\n  ".join(_unfunded))


#: How far a conversion's rate may sit from the event it converts, in days.
#:
#: Zero is not available: the record holds a GBP/EUR close for the days it fetched one, and ii
#: credits interest on the 25th whatever the market did. So a conversion takes the newest sourced
#: rate ON OR BEFORE the event, as `Book._marks_at()` does for prices, and this is how far back that
#: may reach. FOURTEEN DAYS, one monthly interest cycle; beyond it the record has not been
#: refreshed, which is a finding about the record rather than a defect in the row.
#: A CONVERSION CAN BE WRONG WHILE THE FIGURE AND THE RATE ARE BOTH SOURCED, if the rate is another
#: day's: this catches a rate older than the limit, not one a few days off.
FX_RATE_AGE_LIMIT_DAYS = 14


# ==============================================================================================
# CASH — one dated, sourced balance per account, recorded the way a price is: a value, the date it
# was true, and a named source.
#
# THE ONE PLACE FOR A SHARE ACCOUNT'S CASH: a reading's cash is a row here of its own day, and its
# total the stock plus that cash. Not account-statements.csv, which answers what an account was
# worth: a cash-only row there would become its latest statement, with no net asset value.
#
# None, NEVER ZERO, for an account with no figure: one silently contributing nothing would
# understate cash with no check to catch it. A spread-bet account's figure is FUNDS, already inside
# its equity — never add the two. Cash is recorded and never enters NAV.
# ==============================================================================================
class CashReading(NamedTuple):
    account: str
    as_of: _dt.date
    cash: float
    evidence: str        # an EVIDENCE_CLASSES key
    reference: str       # what retrieves it a second time


cash_readings = [CashReading(*r) for r in schema.load("cash-readings")]


def cash_latest(on: _dt.date | None = None) -> dict[str, CashReading]:
    """The NEWEST cash reading per account, which `Book.newest_cash()` weighs against the
    account's own reading. With `on`, the newest dated on or before it — the cash an account
    held at a reading that states none of its own."""
    out: dict[str, CashReading] = {}
    for o in cash_readings:
        if on is not None and o.as_of > on:
            continue
        cur = out.get(o.account)
        if cur is None or o.as_of > cur.as_of:
            out[o.account] = o
    return out


class AccountRow(NamedTuple):
    acct: str
    positions: float | None     # a share account's positions at market; None on a spread bet
    equity: float | None        # spread-bet accounts only: funds plus running P/L
    asof: str                   # DISPLAY ONLY — "19 Jul 15:21". Rebuilt from as_of + at.
    as_of: _dt.date             # THE REAL DATE, and the reason contradiction H existed
    evidence: str = ""          # an EVIDENCE_CLASSES key — limbs 2 and 3, structurally
    reference: str = ""         # what retrieves this reading a second time
    at: str = ""                # THE INSTANT IT WAS READ, ISO and UTC; blank if nobody knows
    # IG'S OWN FIGURES, a spread-bet account's reading (13 Oct 2026); None on a share account.
    funds: float | None = None
    running_pl: float | None = None
    deposit: float | None = None      # IG's word for the margin
    available: float | None = None


# ACCOUNT OBSERVATIONS, from store/account-readings.csv, read BY NAME. `asof` is a display string
# rebuilt from the date and the UK time of the instant.
#
# THE STORE MUST JOIN UP, and it is checked HERE, on load, rather than in the test suite — which
# would catch a broken reference only after a page had been built from rows that silently
# dropped out of every per-account figure.
schema.check_references()

_ac = [dict(zip(schema.TABLES["account-readings"].header, r))
       for r in schema.load("account-readings")]
ac_rows = [
    AccountRow(acct=r["account"], positions=r["positions"], equity=r["equity"],
               asof=(f"{r['as_of'].day} {r['as_of']:%b} {_in_uk(r['at']):%H:%M}" if r["at"]
                     else f"{r['as_of'].day} {r['as_of']:%b}"),
               as_of=r["as_of"], evidence=r["evidence"],
               reference=r["reference"], at=str(r["at"] or ""),
               funds=r["funds"], running_pl=r["running_pl"], deposit=r["deposit"],
               available=r["available"])
    for r in _ac
]

register = schema.load("accounts")
# AN ACCOUNT'S CODE IS ITS NAME TO EVERYONE BUT THE OWNER, so two accounts may never share one, and
# each is A and a number. The label beside it is the engine's, `Book.account_codes()`.
_codes = [r[schema.TABLES["accounts"].header.index("code")] for r in register]
assert len(set(_codes)) == len(_codes) and all(_re.fullmatch(r"A[1-9]\d*", c) for c in _codes), (
    f"accounts.csv codes must be distinct, each A and a number: {_codes}")

# EXTERNAL CAPITAL, in and out; negative is a withdrawal. In capital-movements.csv.
#
# TWO EQUAL ENTRIES IN DIFFERENT ACCOUNTS ARE NOT THE SAME MONEY, however close their dates. A warning about reading the table, not a fact in it;
# the Accounts page says the same to its reader.
movements = schema.load("capital-movements")
# Sorted by date: this is a chronological record of money entering and leaving the book. Every
# sum over it filters by account and date, never by row position, so sorting is safe — and it is
# what lands a hand-edit appended at the foot of the file in the right place.
movements = sorted(movements, key=lambda m: m[0])


# ---- THE CANONICAL ACCOUNT ORDER ---------------------------------------------------------------
# THE SINGLE ORDER FOR EVERY ACCOUNT VIEW, so the fourth row of one table is the same account as the
# fourth row of the next. Share accounts first, then spread bets: the break marks the two valuation
# bases, market value against equity. Event logs, which are chronological, are exempt.
# ==============================================================================================
# NET ASSET VALUE AT EACH QUARTER END
#
# THE ONE RULE THIS TABLE ENFORCES: a share account contributes its POSITIONS AT MARKET, a spread-bet
# account its ACCOUNT EQUITY — funds plus running P/L — and NEVER its notional. One IG
# statement prints the equity beside a notional four times its size, on the same page.
#
# CASH IS EXCLUDED AT BOTH ENDS, PERMANENTLY, which keeps the series consistent (history/accounts.py).
# ==============================================================================================
class QuarterNAV(NamedTuple):
    as_of: str
    account: str
    amount: float        # this account's CONTRIBUTION to net asset value
    contribution: str    # HOW it contributes: "positions at market" | "account equity" |
                         # "notional" (glossary §2).
    quality: str         # sourced | derived — schema.QUALITIES
    source: str


QUARTER_NAV = [QuarterNAV(*_r) for _r in schema.load("quarter-nav")]

# THE QUARTER TOTALS ARE THE ENGINE'S, AND ONLY THE ENGINE'S: Book.NAV_BASES, EXPOSURE_BASES and
# _classified(), which refuses an unclassified basis outright — a total with no stated basis is a
# defect waiting for its data. The baseline is asserted in tests/test_quarter_nav.py,
# test_engine_ties.py and test_history_accounts.py.


#: THE ACCOUNTS, in the register's own order, and what kind each is.
ACCOUNT_ORDER = [r[0] for r in register]
ACCOUNT_KIND = {r[0]: r[schema.TABLES["accounts"].header.index("held_as")] for r in register}
#: THE DAY EACH ACCOUNT'S RECORD BEGAN, FOR ONE OPENED AFTER THE BOOK'S OWN OPENING, as an ISO date; an account held from
#: the opening is not here.
ACCOUNT_BEGINS = {r[0]: str(o) for r in register
                 if (o := r[schema.TABLES["accounts"].header.index("record_begins")])}


def accounts_open(date) -> list[str]:
    """The accounts whose record had begun by `date`, in register order: the ones a quarter end on
    that day holds a row for, and the freeze values."""
    return [a for a in ACCOUNT_ORDER if ACCOUNT_BEGINS.get(a, "") <= str(date)[:10]]

# A READING IS ITS ACCOUNT'S KIND, AND IG'S ARITHMETIC HOLDS. A spread-bet reading is IG's five
# figures and no share figure; a share reading carries none of IG's. Where a spread-bet reading
# states them, funds + running P/L is the equity and equity − deposit the available, to the
# penny — IG's own identities, checked here so a mis-keyed figure stops the build rather than
# sitting under IG's name.
_reading_wrong = []
for _r in ac_rows:
    if ACCOUNT_KIND.get(_r.acct) == "spread bet":
        if _r.positions is not None:
            _reading_wrong.append(f"{_r.acct}: a spread-bet reading is IG's five figures; "
                                  f"positions are a share reading's")
        if (None not in (_r.funds, _r.running_pl, _r.equity)
                and abs(_r.funds + _r.running_pl - _r.equity) > 0.005):
            _reading_wrong.append(f"{_r.acct}: funds {_r.funds} + running P/L {_r.running_pl} is not "
                                  f"the equity {_r.equity}")
        if (None not in (_r.equity, _r.deposit, _r.available)
                and abs(_r.equity - _r.deposit - _r.available) > 0.005):
            _reading_wrong.append(f"{_r.acct}: equity {_r.equity} − deposit {_r.deposit} is not the "
                                  f"available {_r.available}")
    elif any(v is not None for v in (_r.funds, _r.running_pl, _r.equity, _r.deposit,
                                     _r.available)):
        _reading_wrong.append(f"{_r.acct}: a share reading carries none of IG's figures")
if _reading_wrong:
    raise ValueError("AN ACCOUNT READING IS NOT ITS KIND'S:\n  " + "\n  ".join(_reading_wrong))




#: The journal's columns, for the engine's frame, FROM THE SCHEMA, so the engine names them without
#: importing schema.py itself.
JOURNAL_FIELDS = tuple(f.name for f in schema.TABLES["journal"].fields)


def next_free_ids() -> dict:
    """The next free row id per table, one above the last: what a proposed row is called until it
    is written, when the door gives it its place in date order (`record/order.py`).

    ONE ALLOCATOR, for the bench and the IG sweep alike: two copies of it had drifted.
    """
    return {"buys": f"T-{len(buys) + 1:03d}", "sales": f"E-{len(sales) + 1:03d}"}


def store_rows() -> dict:
    """How many rows each table holds ON FILE, right now.

    The journal's reconciliation needs it, and the engine may not fetch it — `engine.py` imports only
    pandas and this module (`test_store_doors.py`) — so the count comes through the record.
    A FUNCTION, because the desk is long-lived and writes rows while it runs; a count taken at
    import would blame a hand edit that never happened. The journal itself is excluded.
    """
    return {name: len(schema.load(name)) for name in schema.TABLES if name != "journal"}


def journal_rows() -> list:
    """The journal, as rows, right now.

    Through the record, not past it: read from its own path, the journal and `store_rows()` would
    come from different stores whenever a test moves the schema. A FUNCTION, never loaded on
    import, because nothing in the build may depend on WHEN a row was entered.

    ON ONE CLOCK: an instant without its `Z` is refused, since UK time and UTC differ by an hour
    half the year and the journal would no longer read as it happened.
    """
    rows = schema.load("journal")
    unzoned = [r[0] for r in rows if not str(r[0]).endswith("Z")]
    if unzoned:
        raise ValueError(f"A JOURNAL INSTANT IS IN UTC, MARKED Z; {len(unzoned)} are not, "
                         f"`portfusion migrate` writes a book's older ones so: {unzoned[:5]}")
    return rows

# THE QUARTER-END COMPOSITIONS — every account's holdings, line by line, at each quarter end, from
# store/quarter-snapshots.csv; `as_of` lets one table hold every quarter.
# Tuple shape: (account, ticker, qty, price, currency, value, cost, quality, source)
_qsnap             = schema.load("quarter-snapshots")

# WHICH QUARTER ENDS ARE FROZEN — asked by the build's close reminder, answered from `as_of`. The
# record's opening may hold lines too, the ones its first quarter is measured from: they
# open a quarter rather than close one, so a date before the record begins is not counted here.
QSNAP_FROZEN       = sorted({r[0] for r in _qsnap if r[0] >= SETTINGS["record_begins"]})

# WHAT EACH CLOSED QUARTER IS HELD TO — store/quarter-results.csv, the engine's six figures per
# account as the freeze wrote them. Read by the test that holds the engine to them; no renderer
# shows them.
QUARTER_RESULTS    = schema.load("quarter-results")

# A QUARTER END'S FIGURE IS ONE ROW. A restatement replaces it (desk/doors/freeze.py:restate()), so
# a second row for one key is two answers to one question, and nothing would say which is meant.
# The book's own quarter-results row has no account, and is named for what it is.
_twice_frozen = [f"{t}.csv holds {', '.join(map(str, k))} more than once"
                 for t, rows, at in (("quarter-nav", QUARTER_NAV, (0, 1, 3)),
                                     ("quarter-snapshots", _qsnap, (0, 1, 2)),
                                     ("quarter-results", QUARTER_RESULTS, (0, 1)))
                 for k, n in _collections.Counter(
                     tuple(r[i] or "the book" if i == 1 else r[i] for i in at)
                     for r in rows).items() if n > 1]
if _twice_frozen:
    raise ValueError("A QUARTER END IS FROZEN ONCE:\n  " + "\n  ".join(_twice_frozen))

# NO QUARTER-END ROW BEFORE AN ACCOUNT OPENS: it held nothing then, and a 0.00 row standing in for
# that reads as a figure. The day it opened is the register's (`ACCOUNT_BEGINS`).
_before_open = sorted({f"{t}.csv: {r[1]} at {r[0]}, before its record begins on {ACCOUNT_BEGINS[r[1]]}"
                       for t, rows in (("quarter-nav", QUARTER_NAV), ("quarter-snapshots", _qsnap),
                                       ("quarter-results", QUARTER_RESULTS))
                       for r in rows if r[1] in ACCOUNT_BEGINS and str(r[0]) < ACCOUNT_BEGINS[r[1]]})
if _before_open:
    raise ValueError("A QUARTER END HOLDS NO ROW FOR AN ACCOUNT BEFORE ITS RECORD BEGINS "
                     "(accounts.csv `record_begins`):\n  " + "\n  ".join(_before_open))


# A SALE THAT NAMES ITS LEG MUST NAME ONE OF ITS OWN, ONCE. `schema.REFERENCES` holds that the leg
# exists; this holds that it is the same account and ticker, and that no leg is closed twice — a
# wrong leg releases the wrong cost and loads without complaint.
_legs = {t.trade_id: t for t in buys}
_wrong = [f"{e.sale_id} closes {e.closes}, a {_legs[e.closes].acct} {_legs[e.closes].ticker} leg, "
          f"but sells {e.acct} {e.ticker}"
          for e in sales if e.closes
          and (_legs[e.closes].acct, _legs[e.closes].ticker) != (e.acct, e.ticker)]
_twice = sorted({e.closes for e in sales if e.closes
                 and sum(x.closes == e.closes for x in sales) > 1})
# A LEG'S CODE IS ITS ACCOUNT'S KIND, AND EVERY CODE IS REGISTERED. The fact is stored once per
# code (securities.kind) and once per account (accounts.kind); this is the check that the two
# agree on every leg and every sale, so the engine may decide a line from either.
_unregistered = sorted({t.ticker for t in buys if t.ticker not in KIND_OF_CODE}
                       | {e.ticker for e in sales if e.ticker not in KIND_OF_CODE})
_crossed = ([f"{t.trade_id} {t.ticker} is {KIND_OF_CODE[t.ticker]!r} in {t.acct}, a "
             f"{ACCOUNT_KIND.get(t.acct)!r} account" for t in buys
             if t.ticker in KIND_OF_CODE and KIND_OF_CODE[t.ticker] != ACCOUNT_KIND.get(t.acct)]
            + [f"{e.sale_id} {e.ticker} is {KIND_OF_CODE[e.ticker]!r} in {e.acct}, a "
               f"{ACCOUNT_KIND.get(e.acct)!r} account" for e in sales
               if e.ticker in KIND_OF_CODE and KIND_OF_CODE[e.ticker] != ACCOUNT_KIND.get(e.acct)])
if _unregistered or _crossed:
    raise ValueError("A LINE'S KIND IS NOT ITS ACCOUNT'S:\n  " + "\n  ".join(
        [f"{c} is on no securities.csv row, so has no kind" for c in _unregistered] + _crossed))
# AN INCOME ROW'S LINE IS A REGISTERED CODE, or a company's life could not count the dividend.
_unlined = [f"{r.date} {r.account} {r.detail!r}: ticker {r.ticker!r}" for r in ci_rows
            if r.ticker and r.ticker not in KIND_OF_CODE]
if _unlined:
    raise ValueError("AN INCOME ROW NAMES A LINE securities.csv DOES NOT HOLD:\n  "
                     + "\n  ".join(_unlined))
# AND A SALE RELEASES COST BY ITS KIND: a spread-bet sale names the leg it
# closed and releases that leg's entry cost; a share sale names none, because a pool has no legs,
# and releases the pool's average (`engine.share_pools()`). Either the wrong way round loads and
# releases a cost by the other rule.
_bets = {t.ticker for t in buys if t.mode == "sb"}
_kind = ([f"{e.sale_id} sells the spread bet {e.ticker} and names no leg — it closes one"
          for e in sales if e.ticker in _bets and not e.closes]
         + [f"{e.sale_id} sells the share {e.ticker} and names the leg {e.closes} — a share sale "
            f"releases its pool's average and names none"
            for e in sales if e.ticker not in _bets and e.closes])
if _wrong or _twice or _kind:
    raise ValueError("A SALE NAMES THE WRONG LEG:\n  " + "\n  ".join(
        _wrong + [f"{leg} is closed by more than one sale" for leg in _twice] + _kind))
# A SHARE HAS A QUANTITY AND A BET A STAKE, on a leg and on a sale alike: never both, never
# neither. The two are the record's own columns, so a bet's size is its stake per point as IG
# states it and a share's its count; a row filled the other way would roll up as the wrong thing.
_sized = ([f"{r.trade_id if hasattr(r, 'trade_id') else r.sale_id} {r.ticker}: a share row has a quantity and no stake"
           for r in [*buys, *sales] if KIND_OF_CODE.get(r.ticker) != "spread bet"
           and (r.qty is None or r.stake is not None)]
          + [f"{r.trade_id if hasattr(r, 'trade_id') else r.sale_id} {r.ticker}: a spread-bet row has a stake and no quantity"
             for r in [*buys, *sales] if KIND_OF_CODE.get(r.ticker) == "spread bet"
             and (r.stake is None or r.qty is not None)])
# AND A BUY'S FIGURE TOO: a share's settled cost, a bet's entry level, never both, never neither.
_sized += [f"{t.trade_id} {t.ticker}: a {'spread-bet' if t.mode == 'sb' else 'share'} buy has "
           f"{'a level and no cost' if t.mode == 'sb' else 'a cost and no level'}"
           for t in buys if (t.level_points is None, t.cost is None) != (t.mode != "sb", t.mode == "sb")]
if _sized:
    raise ValueError("A ROW'S SIZE IS NOT IN ITS KIND'S COLUMN:\n  " + "\n  ".join(_sized))

#: THE FORM OF A REALISATION'S NAME: `R-`, the root its holding was first named by, and a number
#: when another holding already has that name (`Book.parcel()` gives exactly these). Upper-case
#: letters and digits, joined by hyphens; one older name carries a word where the number would
#: go. Anything else reached the record as typed — an "R-ABC=2" passed every check on the bench
#: on 12 Oct 2026, caught only by reading it.
REALISATION_FORM = _re.compile(r"R-[A-Z0-9]+(?:-[A-Z0-9]+)*")
_misnamed = sorted({f"{name} ({where})" for name, where in
                    [(e.realisation_id, e.sale_id) for e in sales]
                    if not REALISATION_FORM.fullmatch(str(name))})
if _misnamed:
    raise ValueError("A REALISATION IS NOT NAMED IN THE RECORD'S FORM (R-ROOT, or R-ROOT-2 when "
                     "the name is taken):\n  " + "\n  ".join(_misnamed))

# A SPREAD BET'S REALISATION IS ONE HOLDING'S: one account, one ticker. Round Trips groups sales
# by it and takes the first sale's account, so another account's close filed under it joins the
# wrong round trip and loads without complaint — as a sweep naming the parcel by ticker alone
# would propose (`Book.parcel()` names it by holding).
# Two shares' sales under one are `engine.share_pools()`'s to refuse, which walks their pools.
_holdings = {}
for e in sales:
    _holdings.setdefault(e.realisation_id, set()).add((e.acct, e.ticker))
_spans = sorted(f"{r} spans two holdings — {' and '.join(f'{a} {t}' for a, t in sorted(h))}"
                for r, h in _holdings.items()
                if len(h) > 1 and any(t in _bets for _, t in h))
if _spans:
    raise ValueError("A SALE IS FILED UNDER ANOTHER HOLDING'S REALISATION:\n  "
                     + "\n  ".join(_spans))



def store_dir():
    """The folder the record is being read from: `schema.STORE`, by one name. The engine needs it
    for the histories it reads as frames, and cannot ask schema. Side effects: none."""
    return schema.STORE


def set_store(path) -> None:
    """Point the record at a different store directory and re-read it.

    THE RECORD IS PROCESS-GLOBAL, and this moves it; it does not hand a caller a private copy.
    A `Book` is unaffected by a later move — it pins the record it was built from — and
    `Book(store_dir=...)` is the way to build one from another store.

    Use `store_at()` in a test, so the record is put back however the test ends.

    Side effects: rebinds schema.STORE, then re-executes this module. Can raise, as
    `reload_store()` can, if the store it is pointed at does not hold together.
    """
    with schema.LOCK:
        schema.set_store(path)
        reload_store()


@_contextlib.contextmanager
def store_at(path):
    """Read the record from `path` for the duration of the block, then put it back.

    Side effects: those of `set_store()`, twice.

    PUT BACK HOWEVER THE BLOCK ENDS, its own start included: a store that would not load raised
    from `set_store()` before the block was entered, and left the record pointed at it.
    """
    was = schema.STORE
    try:
        set_store(path)
        yield schema.STORE
    finally:
        set_store(was)


def reload_store() -> None:
    """Re-read the WHOLE record from disk, into this module's own cached tables.

    The tables are read once, at import, and `engine.load_store()` reads those attributes; a
    long-lived process — the desk — would otherwise serve a store that has moved underneath it.
    `desk/engine.py` reloads whenever the store changes, however it changed.

    IT RE-EXECUTES THIS MODULE, because every table is wrapped, sliced
    and asserted by the code between them, and a hand-written reloader would be a second
    implementation of all of it. Consumers hold the MODULE, never its names — nothing does
    `from portfusion.record.rules import ...` — and `importlib.reload` keeps the namespace, so every holder
    sees the new tables.

    IT CAN RAISE: the record asserts itself on load, so a store caught mid-edit raises here rather
    than serving half a record. `desk/engine.py` turns that into `RecordUnavailable`.

    UNDER `schema.LOCK`, so a desk request never builds over a record another one is re-reading.
    """
    import importlib
    import sys
    with schema.LOCK:
        importlib.reload(sys.modules[__name__])

# EVERY QUARTER END'S COMPOSITION, in the tuple shape above with `as_of` kept in front. What
# `Book.quarter_lines()` reads.
QSNAP_ROWS = [tuple(r) for r in _qsnap]

# THE RECORD READS AS IT HAPPENED (`record/order.py`): every event table in its date order, and a
# buy's or a sale's id its place in it. The doors write so; a hand edit that does not stops here.
# LAST, so a row that is wrong in itself is named for that before it is named for where it sits.
_out_of_order = []
for _t in _order.DATED:
    _h, _rows = schema.TABLES[_t].header, schema.load(_t)
    if (_at := _order.out_of_order(_t, _h, _rows, ACCOUNT_ORDER)) is not None:
        _out_of_order.append(f"{_t}.csv row {_at} is dated before the row above it")
    elif _t in _order.NUMBERED and (_at := _order.misnumbered(_t, _h, _rows)) is not None:
        _out_of_order.append(f"{_t}.csv row {_at}'s id is not its place in date order")
if _out_of_order:
    raise ValueError("THE RECORD IS NOT IN DATE ORDER; `portfusion migrate` puts a book in it:\n  "
                     + "\n  ".join(_out_of_order))
