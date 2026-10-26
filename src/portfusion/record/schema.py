"""
schema.py — THE STORE'S SCHEMA. CSV in, typed rows out, validated on load.

WHY CSV AND NOT SQLITE. A change to a figure should read as a diff, by a person. A binary store
ends that; the cost is that CSV has no types, which is what this module supplies.

NO THIRD-PARTY IMPORTS. The record loads on the standard library alone, and test_schema.py holds
this module to that.

THE TYPE PROBLEM. Every cell is a string, and the record holds `str`, `int`, `float`,
`datetime.date` and `None`. Three round-trip badly if guessed:

  * `None` and `""` are DIFFERENT and both occur. The schema decides: `null=True` reads a blank as
    None; `null=False` reads it as "" (or fails, for a number).
  * `int` and `float` are not interchangeable: quantities are integers and money is not, and
    `4375.0` where `4375` belongs would show on the desk.
  * A date is written ISO and read back as `datetime.date`.

Anything a field cannot hold raises on LOAD, naming the table, the row and the column, so a bad
cell fails at the door rather than becoming a plausible number downstream.
"""
from __future__ import annotations

import csv
import datetime as _dt
import os
import pathlib
import threading
from typing import Any, NamedTuple

#: THE APP'S OWN FOLDER, the package: installed or checked out, the demo ships inside it.
APP = pathlib.Path(__file__).resolve().parents[1]
#: THE CHECKOUT the app runs from, when it runs from one; None on an installed copy.
ROOT = APP.parents[1] if (APP.parents[1] / "pyproject.toml").is_file() else None

#: THE BOOK: the folder one book lives in. Its store, the documents filed behind it, its inbox,
#: its reports, and the files that reach its brokers and readers (credentials, sessions,
#: passkeys) are all inside it, so a book read from elsewhere can touch nothing of this one.
#: The PORTFUSION_BOOK environment variable names it, absolute or relative to where the command
#: was typed, as any path on a command line is; the word `demo` is the invented demo book the
#: app ships. UNSET, IT IS THE BOOK IN THE FOLDER THE COMMAND WAS TYPED IN, and with none there it
#: is refused: falling back to the demo would show invented figures as a book's own. `portfusion
#: init` makes a book. READ HERE AND NOWHERE ELSE: every other path to a book's files derives from
#: this one. An environment setting rather than a flag, because every process the desk starts (the
#: restart, the audit's test run) inherits it — which is why the book is written back ABSOLUTE once
#: resolved: a child started in another folder reads the same book. `about.book_line()` says which
#: book a run loaded.
ENV = "PORTFUSION_BOOK"
#: THE DEMO BOOK, inside the app. Read in place; `portfusion init --practice <folder>` gives a
#: copy to work in.
DEMO = APP / "demo"


def _book() -> pathlib.Path:
    named = os.environ.get(ENV)
    if named == "demo":
        path = DEMO
    else:
        path = pathlib.Path(named or ".").expanduser().resolve()
        if not named and not (path / "store").is_dir():
            raise SystemExit(f"no book here ({path}): run this in a book's folder, or name one "
                             f"with {ENV} or --book. `--book demo` is the demo the app ships; "
                             f"`portfusion init <folder>` makes a book.")
    os.environ[ENV] = str(path)
    return path


#: Whether the book was NAMED (`PORTFUSION_BOOK`, `--book`) or found in the folder the command ran
#: in: `_book()` writes the one it found back, so the environment no longer says.
NAMED = bool(os.environ.get(ENV))
BOOK = _book()
STORE = BOOK / "store"

#: THE RECORD'S ONE LOCK, for a process that serves more than one request at a time — the desk,
#: whose routes run on a pool of threads. Held by every write to the store (`desk/doors/commit.py`
#: `atomic()` and each door's entry point, from its first read to its reload), by the record's
#: reload (`rules.reload_store()`), and by the desk's rebuild of the engine. Without it another
#: request can fall between a check and its write, a refusal's restore put back bytes another
#: write has moved on from, and a Book be built over a half-read record.
#: REENTRANT, because a door's envelope holds it while the reload inside takes it again.
LOCK = threading.RLock()


def record_instant() -> str:
    """NOW, AS RECORD TIME: UTC, to the second, marked `Z`. One clock whatever the machine's zone,
    so a book written on one machine and read on another orders its journal as it happened."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def set_store(path) -> None:
    """Point the schema at a different store directory. `Table.path` reads this global at every
    call, so rebinding it moves every table at once. Callers use `rules.set_store()`.

    Side effects: rebinds this module's STORE. Reads nothing; the next load() does.
    """
    global STORE
    STORE = pathlib.Path(path)


# THE BOOK'S FOLDERS ARE READ FROM `BOOK` WHEN ASKED, so a test that moves the book rebinds
# `BOOK` alone and every reader and writer follows.

def statements() -> pathlib.Path:
    """Where the broker document behind a row is filed; `rules.ARCHIVE_CONVENTION` says how it
    is named."""
    return BOOK / "_archive" / "statements"


def inbox() -> pathlib.Path:
    """The intake workbench: a broker document lands here and leaves for `statements()` once its
    rows are in the record (`docs/intake.md`)."""
    return BOOK / "_inbox"


def filed_statements() -> list[str]:
    """The documents in `statements()`, by name and sorted — THE ONE LISTING of the archive.

    A hidden file is not a document, and Finder writes `.DS_Store` into any folder it opens.
    Empty where the folder is absent.
    """
    folder = statements()
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir()
                  if p.is_file() and not p.name.startswith("."))
# The module is schema.py, not store.py: `store.py` beside `store/` would read as a mistake, and
# become one the moment anyone added an __init__.py.


class Field(NamedTuple):
    """One column. `kind` is how it is parsed; `null` says whether blank means None.

    `enum` is a CLOSED VOCABULARY: a value outside it fails on load. Empty means open, as most
    columns are.

    `required` says a blank string is NOT a value. `null` cannot say it — a blank `str` column
    reads as "" whatever `null` holds, rightly, since most notes are empty — so a string that
    must be filled says so here, where the loader enforces it on every route a row can arrive by.
    Off by default.

    `places` is how many decimal places a figure may hold, and `exact` that it holds exactly that
    many: MONEY, written to the penny, and QUOTE, a price, rate or level to at most six. The loader
    refuses a cell written otherwise, and `cell()` writes every figure so.
    """
    name: str
    kind: str                    # str | int | float | number | date
    null: bool = False
    enum: tuple = ()
    required: bool = False
    places: int | None = None
    exact: bool = False


#: A SUM OF MONEY, in sterling or its line's own currency: written to the penny, always two places.
MONEY: dict[str, Any] = {"places": 2, "exact": True}
#: A PRICE, A RATE OR A LEVEL: at most six places, a trailing nought never written.
QUOTE: dict[str, Any] = {"places": 6}


class Table(NamedTuple):
    """One CSV file, and what its columns mean."""
    name: str                    # the store name, and the file stem
    fields: tuple[Field, ...]
    doc: str = ""

    @property
    def path(self) -> pathlib.Path:
        return STORE / f"{self.name}.csv"

    @property
    def header(self) -> list[str]:
        return [f.name for f in self.fields]


# =====================================================================================
# THE SCHEMA
# =====================================================================================
#
# ONE ISSUER CAN HOLD SEVERAL CODES, which is why these are two tables and not one.
# Orlant is `ORLA` and `ORLA SB`; Askel is the Copenhagen line and the NYSE ADR.
# Collapsing them loses the company-level exposure view, so the join runs
# securities.company -> companies.company rather than the two being merged.

COMPANIES = Table(
    name="companies",
    doc=("One row per ISSUER — the company, not the holding. The sole source of sector "
         "and region; every holding code inherits them through securities.company, so a "
         "code cannot carry a sector its issuer disagrees with."),
    fields=(
        Field("company", "str"),
        # REQUIRED, so no line drops out of a split by sector or region.
        Field("sector", "str", required=True),
        Field("region", "str", required=True),
    ),
)

#: DO WE OWN IT, OR HAVE EXPOSURE TO IT — glossary §2.
#: WHAT KIND OF LINE, AND OF ACCOUNT, which decides whether its figures are money or notional
#: (`rules.SPREAD_BET`). One vocabulary for both: `securities.kind` and `accounts.kind`.
KINDS = ("shares", "spread bet")

#: THE CLOSED VOCABULARIES, declared to the loader: a value outside one fails on load naming the
#: table, the row and the column. An account needs none — `REFERENCES` holds every account column
#: to the register.
#: Currency, region, sector and ticker stay open, so a first holding in a new one is not refused;
#: a line's currency, sector and region are `required` all the same, so none is ever blank.
#: `rules.POSITION_INCOME` and `rules.ACCOUNT_INCOME` split these, each into exactly one.
INCOME_CATEGORIES = ("Dividend", "Funding interest", "Cash interest", "Fee")
#: THE SIGN AN INCOME AMOUNT USUALLY CARRIES, by category: money in is positive. Funding interest
#: is either, as a short bet is paid it. The Bench asks the owner to confirm another sign
#: (`bench.gates()`): a dividend charged on a short, or a fee refunded, is real.
USUAL_SIGN = {"Dividend": 1, "Cash interest": 1, "Fee": -1}

SECURITIES = Table(
    name="securities",
    doc=("One row per CODE held, reserved or closed. Carries `held_as`, the distinction the "
         "whole book turns on, in the register's own two words (KINDS): a share is money "
         "owned, a spread bet is exposure through a contract. THE ONE PLACE THE FACT IS "
         "STORED PER LINE: a leg takes its kind from its code, and the load holds it to its "
         "account's."),
    fields=(
        Field("ticker", "str"),
        Field("company", "str"),           # joins to companies.company
        Field("held_as", "str", enum=KINDS),
        Field("currency", "str", required=True),   # a split by currency drops a blank one
        # THE LISTING: the market's ISO code and the ticker as that market spells it
        # (XLON:BRYC, XCSE:HALD B), and the unit the market quotes it in (GBX is pence). A unit
        # means the book prices the line from a feed, which translates the symbol into its own
        # form; a spread bet has a symbol, the listing it is a bet on, and no unit, because IG
        # prices it.
        Field("symbol", "str", null=True),
        Field("quote_unit", "str", null=True),
        # A SPREAD BET'S POINT AGAINST ITS LISTING'S PRICE: how many points make one unit of
        # `currency` (100 where IG quotes the market in cents or pence), and how many of the
        # company's shares one unit of the listing stands for (a depositary receipt's ratio;
        # blank is one). Together with the stake they turn a bet into share-equivalents.
        # Blank on a share.
        Field("points_per_unit", "float", null=True, **QUOTE),
        Field("shares_per_unit", "float", null=True, **QUOTE),
    ),
)

ACCOUNTS = Table(
    name="accounts",
    doc=("The account register. One row per account, in the order every page lists them: "
         "share accounts, then spread bets."),
    fields=(
        Field("account", "str"),
        Field("holder", "str"),
        Field("broker_firm", "str"),
        Field("number", "str"),            # STRING, not int — "0123456" keeps its zero
        # WHAT THE ACCOUNT IS CALLED TO ANYONE BUT THE OWNER: A1, A2… in register order, never
        # reused. `Book.account_codes()` gives each its label.
        Field("code", "str", required=True),
        Field("held_as", "str", enum=KINDS, required=True),
        # THE LABEL OF THE ACCOUNT'S BLOCK IN credentials.json, for an account a feed reads.
        Field("feed_key", "str", null=True),
        # THE DAY THE ACCOUNT'S RECORD BEGINS, for one opened after the book's; blank for one held
        # from the book's opening. Before it the account holds nothing and has no quarter-end
        # row (`rules.accounts_open()`), whatever deal dates the statement it opened at carries.
        Field("record_begins", "date", null=True),
    ),
)

CAPITAL_MOVEMENTS = Table(
    name="capital-movements",
    doc=("External capital in and out, one row per event. NEGATIVE IS A WITHDRAWAL. "
         "This is money crossing the book's boundary — not money moving between "
         "positions, which is a trade, and not the value of anything."),
    fields=(
        # AN EVENT IS DATED, refused on load when blank.
        Field("date", "str", required=True),   # ISO string: the ledger's own date convention
        Field("account", "str"),
        Field("amount", "float", **MONEY),
        Field("source", "str"),
        Field("detail", "str"),
    ),
)

BUYS = Table(
    name="buys",
    doc=("THE LEDGER — one row per buy leg.\n\n"
         "a leg's kind (its code's, securities.csv) is why several columns are nullable rather than a shape defect. A SHARE "
         "leg records its quantity in `qty` and the settled GBP total in `cost`; a SPREAD-BET "
         "leg records its stake in `stake` and its entry level in points in `level_points`, as "
         "IG states them, and its notional is stake x level. The columns only one kind fills — qty "
         "and cost on a share; stake, level and contract on a bet — are absent on the other "
         "because they do not exist for it — a GAP, not a zero.\n\n"
         "`broker_ref` IS NOT ONE OF THEM. One column holds every broker reference: IG bet "
         "ref, ii contract number, HL ref. `source` says what KIND of document and its date, "
         "in one format for every account (`rules.trade_source()`); this says WHICH ONE. "
         "Never a SEDOL, which HL statements print beside each deal, so two deals would "
         "share one; the movements downloads print each deal's own reference."),
    fields=(
        Field("trade_id", "str"),
        Field("date", "str", required=True),   # ISO; tests/record/test_record.py holds it; never blank
        # `source`: WHAT DOCUMENT IS THIS ROW'S EVIDENCE — its kind and its date, "ii contract
        # note 14 Apr 2026" (`rules.trade_source()`) — the provenance line every other table
        # calls `source`. Not `evidence`, which names an EVIDENCE_CLASSES key wherever it appears
        # (glossary §2). `broker_ref` says WHICH ONE; this says what KIND.
        Field("source", "str"),
        Field("account", "str"),
        Field("ticker", "str"),            # the security's code in securities.csv
        # `cur`: THE CURRENCY `traded_price` IS STATED IN — the share's own where the broker dealt in it,
        # GBP where it priced the deal in sterling (HL, in pence) and on a spread bet, IG's
        # "Curr £". Never the share's currency by default: securities.csv holds that.
        Field("cur", "str"),
        Field("qty", "int", null=True),    # shares; blank on a spread bet, whose size is its stake
        Field("stake", "number", null=True),      # £ per point, a bet's size; blank on a share
        Field("cost", "float", null=True, **MONEY),          # a share's settled GBP; blank on a bet
        # A BET'S ENTRY LEVEL IN POINTS; blank on a share.
        Field("level_points", "float", null=True, **QUOTE),
        Field("broker_ref", "str", null=True),
        Field("note", "str"),
        # WHICH IG CONTRACT A SPREAD-BET LEG IS ON — what prices it, open or closed. Blank on a
        # share leg. Joins to contracts.csv.
        Field("contract", "str", null=True),
        # THE DEAL'S OWN PRICE, per share in `cur` (HL's pence as pounds), and the broker's RATE
        # where the document gives one, units of the share's currency per £1. Never worked out
        # from `cost`: that carries the dealing charge. Empty when nothing filed
        # gives it, and on a spread bet, whose level is `level_points`.
        Field("traded_price", "float", null=True, **QUOTE),
        Field("rate", "float", null=True, **QUOTE),
    ),
)

#: HOW IG FUNDS A CONTRACT, in IG's two kinds of bet: a DAILY funded bet is charged interest for
#: every night a leg is held; a DATED bet, a quarterly future, carries its cost in its price and is
#: charged none. A funding-interest row therefore belongs to a daily contract's leg held on the
#: nights the row names (rules.funding_nights), and a night such a leg was held with no row is a
#: gap the audit names (Book.funding_gaps).
FUNDINGS = ("daily", "dated")

#: THE IG CONTRACTS a spread-bet leg can be on, each with the epic IG prices it by and the way IG
#: funds it. A contract with no epic is closed: nothing reads its level again.
CONTRACTS = Table(
    name="contracts",
    doc=("One row per IG contract a spread-bet leg names, with the epic that prices it, "
         "how IG funds it, and the ticker of the line it is on."),
    fields=(
        Field("contract", "str"),
        Field("epic", "str", null=True),
        Field("funding", "str", enum=FUNDINGS),
        Field("ticker", "str", required=True),
    ),
)

SALES = Table(
    name="sales",
    doc=("One row per sale. `proceeds` is the sterling settled — every sale in this book "
         "settles in sterling. `traded_price` is stated in `cur`, as the sale's document states "
         "it, with the broker's `rate` beside a price in the share's own currency; the "
         "engine reads a round trip's entry and exit in the share's currency.\n\n"
         "`traded_price` IS THE EXECUTION PRICE off the contract note, NOT "
         "net proceeds / qty. Every commissioned sale carries the traded price, so "
         "`traded_price x qty` reads GROSS and the gap to `proceeds` is the DEALING COST. Keeping "
         "the sourced figure: net/qty is a derivation, and smearing a commission "
         "into a price hides both the price and the cost.\n\n"
         "THAT GAP IS NOT AN UNRECORDED COST. `proceeds` is NET of dealing costs on every "
         "row, so the commission is already in the book — it comes off REALISED GAIN, which "
         "is the right place for a cost attached to a disposal. It is deliberately NOT in "
         "income.csv, which holds the costs that attach to no transaction: platform fees, "
         "management fees, funding interest. Booking a dealing commission there as well "
         "would subtract it twice."),
    fields=(
        Field("sale_id", "str"),
        Field("date", "str", required=True),   # an event is dated
        Field("account", "str"),
        Field("ticker", "str"),            # the security's code in securities.csv
        Field("qty", "int", null=True),    # shares; blank on a spread-bet sale
        Field("stake", "number", null=True),      # £ per point, a bet sale's size; blank on a share
        Field("traded_price", "float", **QUOTE),    # per share, or a bet's closing level in points
        Field("cur", "str", required=True),  # the currency `traded_price` is stated in, as buys.cur
        Field("rate", "float", null=True, **QUOTE),   # the broker's, where the document states one
        Field("proceeds", "float", **MONEY),        # GBP, always
        Field("source", "str"),
        # THE BROKER'S REFERENCE FOR THIS SALE: an IG close's closing deal, an ii contract
        # number, HL's sale reference. Nullable where no document on file prints one. ONE
        # reference — the one that retrieves THIS row. The leg an IG close closes is a link
        # between two rows: `closes`. `source` names the document's kind and date, as a trade's.
        Field("broker_ref", "str", null=True),
        # WHICH PARCEL THIS SALE BELONGS TO — stated per row, never inferred. A realisation is a
        # PARCEL and accumulates sales over time (a trimmed pool, a bet closed leg by leg); it, not
        # the ticker, is the join.
        Field("realisation_id", "str", required=True),
        # THE BUY LEG THIS SALE CLOSED, by the book's own id, when the broker names one: an IG
        # close names the opening deal, which is a leg's `broker_ref`. The sale then releases that
        # leg's own entry cost. Blank for a pooled or apportioned sale.
        Field("closes", "str", null=True),
        Field("note", "str"),
    ),
)

INCOME = Table(
    name="income",
    doc=("Dividends, interest and fees. COSTS ARE NEGATIVE, income positive, and the "
         "whole table sums to the book's income figure. May span earlier years and the "
         "desk counts the year to date only, so any total taken from here needs "
         "an explicit year filter."),
    fields=(
        Field("date", "str", required=True),   # an event is dated
        Field("account", "str"),
        Field("category", "str", enum=INCOME_CATEGORIES),
        Field("detail", "str"),
        Field("amount", "float", **MONEY),         # ALWAYS GBP — the figure the book adds up
        Field("source", "str"),
        Field("note", "str"),              # often "", and that is a real value
        # THE CONVERSION, AS DATA. A foreign-currency income row states its currency and its
        # amount in it, and `rate` where the broker's document states the rate it was converted
        # at; a blank `rate` converts at the day's TradingView close on fx-history.csv, as a
        # deal's does. Blank on every GBP row, meaning "no conversion".
        Field("currency", "str"),          # the currency the income was PAID in
        Field("local_amount", "float", null=True, **MONEY),
        Field("rate", "float", null=True, **QUOTE),  # units of the currency per £1, the broker's
        # THE LINE A DIVIDEND WAS PAID ON, a code in securities.csv, so a company's life can count
        # it. Blank on interest, fees and funding, which no one line earns.
        Field("ticker", "str"),
    ),
)

#: THE PROVENANCE VOCABULARY — how the record knows a figure: `sourced` or `derived`, each
#: defined in docs/glossary.md §3.
#:
#: It is here because the loader enforces it and schema.py imports nothing; `rules.py` reads it
#: from here. Each history declares the subset it permits, held by a test.
QUALITIES = ("sourced", "derived")

#: WHAT INSTANT A MARK DESCRIBES. `close` is a session close — a settled figure for a named day
#: that can be fetched again and got the same. `live` is a read struck at an instant that cannot
#: be reproduced. Declared here for the same reason as QUALITIES; `history/prices.py` reads it.
STRUCK_KINDS = ("close", "live")

#: HOW AN ACCOUNT CONTRIBUTES TO NET ASSET VALUE at a quarter end: its positions at market, a
#: spread-bet account's equity, or that account's notional, the exposure measure and never NAV.
#: Not `basis` (docs/glossary.md §2). `Book.NAV_BASES` and `Book.EXPOSURE_BASES` sort them.
CONTRIBUTIONS = ("positions at market", "account equity", "notional")


QUARTER_NAV = Table(
    name="quarter-nav",
    doc=("Each account's CONTRIBUTION to net asset value at each quarter end.\n\n"
         "THE ONE RULE THIS TABLE ENFORCES: a share account contributes its POSITIONS AT "
         "MARKET and a spread-bet account its ACCOUNT EQUITY, never its notional. One IG "
         "statement prints the equity beside a notional four times its size, "
         "and the gap between those two is the most expensive mistake available against "
         "this record. `contribution` is that rule, as a column."),
    fields=(
        Field("as_of", "str"),
        Field("account", "str"),
        Field("amount", "float", **MONEY),
        # Declared to the loader, so a stray value fails at the door rather than in review.
        Field("contribution", "str", enum=CONTRIBUTIONS),
        Field("quality", "str", enum=QUALITIES),
        Field("source", "str"),
    ),
)

FX = Table(
    name="fx",
    doc=("The rate each currency is converted at NOW, one row per currency, as "
         "current-prices.csv holds what each line is worth now: replaced at every refresh, "
         "banked into fx-history.csv first. A rate ON A DATE is fx-history.csv's, where "
         "every dated rate the record converts at is kept."),
    fields=(
        # `currency` IS THE KEY, as a ticker is current-prices.csv's; a currency held in nothing
        # has no row.
        Field("currency", "str"),
        Field("rate", "float", **QUOTE),            # units of the currency per £1
        Field("as_of", "str"),
        Field("source", "str"),
        # `struck`: a session close or a live read, as current-prices.csv says it.
        Field("struck", "str", enum=STRUCK_KINDS, required=True),
    ),
)

CURRENT_PRICES = Table(
    name="current-prices",
    doc=("What things are worth NOW — never what was paid, which is the ledger. Spread "
         "bets are keyed by CONTRACT and not by ticker, because legs of the same "
         "underlying sit on different contracts at different levels; a contract's price is "
         "its level in points, as IG quotes it.\n\n"
         "DO NOT COMPACT `source`. It carries load-bearing derivations — the Askel ADR "
         "cross and the IG intraday caveat — that the price history depends on.\n\n"
         "`struck` and `at` ARE THE FEED'S, written with the price: whether the mark is a "
         "session close or a live read, and the UTC instant a live read describes. A close "
         "is a date, so its `at` is blank. The feed is the only party that knows, so it says "
         "so in a column."),
    fields=(
        Field("mark_key", "str"),          # a share's ticker, or a spread bet's CONTRACT
        Field("price", "float", **QUOTE),
        Field("currency", "str"),
        Field("as_of", "str"),
        Field("source", "str"),
        Field("struck", "str", enum=STRUCK_KINDS, required=True),
        Field("at", "str"),                # ISO UTC, e.g. 2026-09-29T14:02:11Z; blank for a close
    ),
)

QUARTER_SNAPSHOTS = Table(
    name="quarter-snapshots",
    doc=("Every account's HOLDINGS, line by line, at each quarter end — the working "
         "behind quarter-nav.csv's per-account totals. `as_of` lets one table hold every "
         "quarter.\n\n"
         "NOT THE SAME QUESTION AS quarter-nav.csv, which carries each account's CONTRIBUTION "
         "to net asset value and enforces the basis rule. This is the composition underneath "
         "it. A spread-bet account's legs appear here at NOTIONAL, as Holdings shows them — "
         "`qty` the stake per point, `price` the level in points — while "
         "quarter-nav.csv carries its equity.\n\n"
         "APPENDED BY desk/doors/freeze.py from Book.freeze_rows().\n\n"
         "`quality` is the line's provenance in the record's one vocabulary (glossary §3)."),
    fields=(
        Field("as_of", "str"),
        Field("account", "str"),
        Field("ticker", "str"),            # "(no positions)" for an account holding none
        # NULLABLE, and only on the "(no positions)" rows: an account holding nothing has no
        # quantity, price or currency to state. Blank, never zero — a zero quantity is a holding
        # of nothing, a different claim. value and cost are 0.0 there, rightly: the
        # account adds nothing to either total.
        Field("qty", "number", null=True),
        Field("price", "float", null=True, **QUOTE),
        Field("currency", "str", null=True),
        Field("value", "float", **MONEY),
        Field("cost", "float", **MONEY),
        Field("quality", "str", enum=QUALITIES),
        Field("source", "str"),
    ),
)

ACCOUNT_READINGS = Table(
    name="account-readings",
    doc=("What the book holds each account to be worth RIGHT NOW, and the observation it "
         "rests on. The Accounts tab reconciles these against the broker.\n\n"
         "`as_of` is a real date here and `at` the instant it was read, ISO and UTC, as on "
         "current-prices. The two are recombined for DISPLAY.\n\n"
         "TWO KINDS OF READING, EACH IN ITS OWN COLUMNS. A share account's is "
         "its document's stock, `positions`; the cash its document states is a cash reading "
         "of the same day (cash-readings.csv), and its total is the two together. A "
         "spread-bet account's is IG's five figures under IG's names, once each: `funds`, "
         "`running_pl`, `equity`, `deposit` (IG's word for the margin) and `available`; its "
         "notional is not typed here but derived, and the load holds funds + running P/L to "
         "the equity and equity − deposit to the available (record/rules.py)."),
    fields=(
        Field("account", "str"),
        Field("as_of", "date"),            # A REAL DATE.
        Field("at", "str"),                # ISO UTC, e.g. 2026-09-30T17:40Z; blank if unknown
        # A SHARE ACCOUNT'S READING, blank on a spread-bet row.
        Field("positions", "float", null=True, **MONEY),   # positions at market
        # A SPREAD-BET ACCOUNT'S READING, IG'S OWN FIGURES, blank on a share row.
        Field("funds", "float", null=True, **MONEY),
        Field("running_pl", "float", null=True, **MONEY),
        Field("equity", "float", null=True, **MONEY),
        Field("deposit", "float", null=True, **MONEY),     # IG's word for the margin
        Field("available", "float", null=True, **MONEY),   # the feed's; a statement prints none
        # PROVENANCE, STRUCTURALLY: the evidence class and the reference, the same pair
        # cash-readings.csv carries. Without them nothing could bank an observation into
        # history (a banked row needs a source and a quality) or colour a row from its own file.
        # `quality` is DERIVED from the class, never stored beside it, and so is the source line
        # a banked row carries. REQUIRED: this is the figure the reconciliation is judged against,
        # and must say what it rests on.
        Field("evidence", "str", required=True),   # an EVIDENCE_CLASSES key
        Field("reference", "str", required=True),  # what retrieves it — limb 3, per the class
    ),
)

RESEARCH_NOTES = Table(
    name="research-notes",
    doc=("WHICH RESEARCH NOTES COVER WHICH INSTRUMENT. One row per (ticker, ref) pair — a note "
         "on a company held as both shares and a spread bet covers both codes, so it appears twice, and that mapping is a "
         "BOOK decision rather than a fact in the note.\n\n"
         "THE RESEARCH REPO IS THE SOURCE OF TRUTH FOR A REF, not this table, and the rules "
         "governing a ref — never reused, never computed, gaps are legitimate — are that "
         "repo's own. THIS TABLE IS A "
         "RECORD OF WHAT WAS CITED, so the book builds on a machine that does not have the "
         "research repo; `desk/doors/research_notes.py` writes a published note's rows from "
         "that repo's own frontmatter on the Bench's press, so no ref is typed. "
         "Tests tie the two together both ways wherever both exist, the way quarter-nav is tied "
         "to account-statements.csv."),
    fields=(
        Field("ticker", "str"),
        Field("ref", "str"),
        Field("published", "date"),
        Field("url", "str"),
    ),
)

CASH_READINGS = Table(
    name="cash-readings",
    doc=("HOW MUCH CASH A SHARE ACCOUNT HELD, AND WHEN: THE RECORD'S ONE PLACE FOR CASH. "
         "Append-only: a new reading adds a row and never replaces one. The Accounts tab's "
         "'Cash now' is the NEWEST row per account, and a share reading's total is its stock "
         "plus the cash here on or before its date.\n\n"
         "ONE PLACE, so a day's cash cannot disagree with itself: a reading off a document that "
         "states cash writes it here, the same day. Not in account-statements.csv, which "
         "answers 'what was this account WORTH': a cash-only row there would become an "
         "account's latest statement, with no net asset value.\n\n"
         "THIS DOES NOT REACH NAV OR THE RETURN, and there is no date on which it starts to. "
         "This is a RECORD of cash and a cell on a tab.\n\n"
         "NOT FOR A SPREAD-BET ACCOUNT. Its funds are on its reading, under IG's own name "
         "(account-readings.funds), and the Accounts page reads them there; a row here would "
         "name that figure twice."),
    fields=(
        Field("account", "str"),
        Field("as_of", "date"),
        Field("cash", "float", **MONEY),
        # REQUIRED, with account-readings' matching pair.
        Field("evidence", "str", required=True),   # an EVIDENCE_CLASSES id
        Field("reference", "str", required=True),   # what retrieves it: a statement, or the query
    ),
)

REASONING = Table(
    name="reasoning",
    doc=("WHY a position was taken and why it was closed — one row per DECISION: the ticker, "
         "the date of the trade or sale it explains, and the why. APPENDED, NEVER REPLACED: a "
         "second why on a name is a row of its own, so a thesis written when a position opened "
         "is still there when it is added to or trimmed. Holdings and Round Trips show every "
         "why dated within the position's life, oldest first.\n\n"
         "Both why columns are nullable: a purchase has no why_exited, and a sale no "
         "why_entered. A row that closes one leg and opens another the same day carries both."),
    fields=(
        Field("ticker", "str"),
        Field("date", "date"),             # the trade's or the sale's own date
        Field("why_entered", "str", null=True),
        Field("why_exited", "str", null=True),
    ),
)

QUARTER_RESULTS = Table(
    name="quarter-results",
    doc=("Each closed quarter's six figures, for the book and for each account, as the engine "
         "gave them — what a closed quarter is HELD TO, never what a renderer shows.\n\n"
         "Every renderer shows the engine's figure. `test_engine_ties.py` fails when that "
         "figure stops matching the row here for its quarter end and account, so a "
         "change to how a quarter is computed cannot move a closed one quietly: a RESTATEMENT "
         "replaces the row, its note saying why, the journal when, and git what it was.\n\n"
         "APPENDED BY desk/doors/freeze.py from Book.quarter_results(), once the inputs are in. A "
         "blank `account` is the book."),
    fields=(
        Field("as_of", "str"),
        Field("account", "str"),           # blank for the book
        Field("opening_nav", "float", **MONEY),
        Field("capital_deployed", "float", **MONEY),
        Field("return_income", "float", **MONEY),
        Field("closing_nav", "float", **MONEY),
        Field("gain", "float", null=True, **MONEY),  # blank where there is nothing to measure from
        Field("return", "float", null=True, places=6),   # a fraction, to six places
        Field("note", "str"),
    ),
)

#: WHAT MAKES THIS BOOK THIS BOOK — its dates and names, which the code may not type. One row per
#: key; `rules.SETTINGS` reads them and refuses a key twice. A blank value is none.
SETTING_KEYS = (
    "record_begins",        # the first day of the record; the opening is the day before
    "reasoning_owed_from",  # a thesis or an exit reason is owed for a position opened or closed from here
    "first_report",         # the first quarter end the quarterly report is built for
    "rate_carried",         # currencies whose live rate is not refreshed, space-separated
    # WHERE THIS BOOK IS PUBLISHED AND WHAT IT READS BESIDE ITSELF. Each is optional: without one,
    # the feature that needs it declines and names the key, so a new book starts with none.
    "hosted_origin",        # the hosted desk's own origin, the one page whose writes the remote door takes
    "passkey_domain",       # whose passkeys the hosted desk's are: a domain the origin sits under
    "deploy_repo",          # the deploy-only repository's local clone, which `--publish` writes
    "research_repo",        # the research repository, read for published notes
    "insights_url",         # where a published note is read, its slug appended
    # WHAT KIND OF BOOK THIS IS, when it is not a real one.
    "practice",             # set in a practice book, a copy of the demo: its figures are invented
)

SETTINGS = Table(
    name="settings",
    doc="The book's own settings: one row per key in SETTING_KEYS.",
    fields=(
        Field("key", "str", enum=SETTING_KEYS),
        Field("value", "str"),
    ),
)

#: Every table the record holds, before the journal — which needs their names as a vocabulary.
_RECORD = (
    COMPANIES, SECURITIES, ACCOUNTS, CAPITAL_MOVEMENTS, BUYS, SALES,
    INCOME, QUARTER_NAV, QUARTER_SNAPSHOTS, FX, CURRENT_PRICES,
    ACCOUNT_READINGS, REASONING, CASH_READINGS,
    RESEARCH_NOTES, QUARTER_RESULTS, SETTINGS, CONTRACTS)

JOURNAL = Table(
    name="journal",
    doc=("RECORD TIME — when the book LEARNED a thing, as against when the thing HAPPENED.\n\n"
         "The record keeps three clocks. MARKET TIME is in the price and FX histories; EVENT "
         "TIME is every `date` and `as_of` column in this store. RECORD TIME is this table: one "
         "row per WRITE, in git, diffable, and answerable.\n\n"
         "ONE ROW PER WRITE, NEVER PER CHANGED FIGURE. A bench item landing three rows in "
         "`buys` is one journal row saying so. A refresh replacing twelve marks is one row. "
         "The detail of what changed is in the table that changed and in the archive the `ref` "
         "retrieves; this says WHEN, BY WHAT ROUTE, and HOW MUCH MOVED.\n\n"
         "FORWARD-ONLY BY CONSTRUCTION. It reaches back to the day it opened, and to the "
         "writes it was seeded from, no further. Never rebuilt from the commit log: a commit "
         "message is prose that cannot be queried.\n\n"
         "THE OPENING COUNT IS WHAT MAKES IT CHECKABLE. Each table opens with a "
         "`route=baseline, op=open` row carrying the rows on file that day. Then "
         "`opening + appends − removes` "
         "must equal the rows on file, table by table, and any difference is precisely the set "
         "of hand edits nobody journalled. `portfusion record` prints it.\n\n"
         "ROUTE AND OP ARE TWO QUESTIONS. Route says WHO wrote; op says WHAT IT DID to the row "
         "count. They correlate for baseline, bench and marks and come apart on `hand`, which "
         "may append, replace or remove — so deriving one from the other would be a "
         "classification, and this book deletes those. A REPLACE ADDS NO ROWS: without `op` a "
         "fortnightly refresh would read as twelve unaccounted rows and the check would train "
         "its reader to ignore it.\n\n"
         "ITS VOCABULARIES ARE DECLARED TO THE LOADER: a stray route fails ON LOAD naming the "
         "table, the row and the column, rather than joining to nothing downstream."),
    fields=(
        # RECORD TIME, to the second, IN UTC (`record_instant()`) — a `str`, because
        # `date.fromisoformat` would refuse a time. One without its `Z` is refused
        # (`rules.journal_rows()`).
        Field("at", "str"),
        # WHO WROTE. `baseline` opens a table; `bench` is a press on the Bench: commit.py, which
        # appends an event, or research_notes.py, a published note's rows; `marks` is marks.py,
        # which replaces a mark; `freeze` is desk/doors/freeze.py, which appends a quarter end
        # from the engine; `hand` is a person editing the CSV and saying so, which
        # docs/store.md allows; `migrate` is `portfusion migrate` moving a book's rows.
        Field("route", "str", enum=("baseline", "bench", "marks", "freeze", "hand", "migrate")),
        # WHAT IT DID TO THE ROW COUNT: the desk's two words for its two doors.
        Field("op", "str", enum=("open", "append", "replace", "remove")),
        Field("table", "str", enum=tuple(sorted(t.name for t in _RECORD))),
        # HOW MANY ROWS THE WRITE TOUCHED. For `open`, the rows already on file.
        Field("rows", "int"),
        # WHAT RETRIEVES THIS WRITE: a bench item id, which fetches the whole archived item and
        # its evidence; a research note's ref, which fetches its rows; a mark date; a commit for
        # a hand edit. Blank on an opening count, which retrieves nothing because nothing was
        # written.
        Field("ref", "str", null=True),
        Field("detail", "str", null=True),
    ),
)

TABLES: dict[str, Table] = {t.name: t for t in _RECORD + (JOURNAL,)}


# =====================================================================================
# READING AND WRITING
# =====================================================================================


def _parse(field: Field, raw: str, table: str, row_no: int):
    """One cell, string in, typed out. Raises rather than guessing."""
    text = "" if raw is None else raw
    where = f"{table}.csv row {row_no}, column {field.name!r}"

    if field.enum and text != "" and text not in field.enum:
        raise ValueError(
            f"{where}: {text!r} is not one of {list(field.enum)}. This column is a CLOSED "
            f"vocabulary — a value outside it would load cleanly and then join to nothing.")

    if text == "":
        if field.required:
            raise ValueError(
                f"{where}: blank, and this column may not be. A row that cannot say what it "
                f"rests on is a recollection with a number attached.")
        if field.null:
            return None
        if field.kind == "str":
            return ""
        raise ValueError(
            f"{where}: blank, but the column is {field.kind} and not nullable. "
            f"A missing number is a GAP, never zero — declare the field null=True if "
            f"absence is meaningful here.")

    try:
        if field.kind == "str":
            return text
        if field.kind == "int":
            # Reject "4375.0": a float written where an integer belongs is exactly the
            # kind of quiet type drift this schema exists to stop.
            return int(text)
        if field.kind == "float":
            if field.places is not None:
                _held_to_places(field, text)
            return float(text)
        if field.kind == "number":
            # INT OR FLOAT, WHICHEVER THE TEXT SAYS. A spread-bet stake is 1 or 0.25, a limit
            # level 11300 or 8922.1; collapsing them to float would be a reshape no test could
            # see, because 1 == 1.0.
            return float(text) if any(c in text for c in ".eE") else int(text)
        if field.kind == "date":
            return _dt.date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{where}: {exc}") from None
    raise KeyError(f"{where}: unknown field kind {field.kind!r}")


def _held_to_places(field: Field, text: str) -> None:
    """Raise unless `text` is written to the field's places: exactly, for money; at most, else."""
    digits = text.strip().partition(".")[2]
    if any(c in text for c in "eE") or (len(digits) != field.places if field.exact
                                        else len(digits) > field.places):  # pyright: ignore[reportOperatorIssue]
        raise ValueError(f"{text!r} is not written to {'exactly' if field.exact else 'at most'} "
                         f"{field.places} decimal places")


def figure(value, places: int, exact: bool = False) -> str:
    """A number written to `places`: exactly that many for money, which must already be whole
    pennies (raises otherwise, never rounding a sum someone entered); at most that many for a
    quote, rounded there, its trailing noughts dropped."""
    v = float(value)
    if exact:
        if abs(v - round(v, places)) > 1e-9 * max(1.0, abs(v)):
            raise ValueError(f"{value!r} is not a sum to {places} decimal places")
        return f"{round(v, places) + 0.0:.{places}f}"      # + 0.0: never "-0.00"
    return repr(round(v, places) + 0.0)


def cell(field: Field, value) -> str:
    """One cell as every writer writes it: a figure to its field's places (`figure()`), anything
    else as given. Blank for None or an empty string; a figure that will not read as a number is
    left for the loader to refuse by name."""
    if value is None or value == "":
        return ""
    if field.kind == "float" and field.places is not None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        try:
            return figure(number, field.places, field.exact)
        except ValueError as e:
            raise ValueError(f"{field.name}: {e}") from None
    return str(value)


# WHICH COLUMNS POINT AT ANOTHER TABLE'S ROW. An account name mistyped with a lowercase L would
# otherwise load, join to nothing, and drop its rows out of every per-account figure while every
# total still added up — wrong in a way that still builds. The register, store/accounts.csv, is
# the authority, so adding an account is one edit.
REFERENCES = {
    ("capital-movements", "account"):    ("accounts", "account"),
    ("buys", "account"):                 ("accounts", "account"),
    ("buys", "contract"):                ("contracts", "contract"),
    ("contracts", "ticker"):             ("securities", "ticker"),
    ("sales", "account"):                ("accounts", "account"),
    ("sales", "closes"):                 ("buys", "trade_id"),
    ("income", "account"):               ("accounts", "account"),
    ("quarter-nav", "account"):          ("accounts", "account"),
    ("quarter-snapshots", "account"):    ("accounts", "account"),
    ("account-readings", "account"):     ("accounts", "account"),
    ("cash-readings", "account"):        ("accounts", "account"),
    ("quarter-results", "account"):      ("accounts", "account"),
}

#: A REFERENCE WHOSE BLANK IS A VALUE: quarter-results' row for the book names no account.
BLANK_IS_THE_BOOK = {("quarter-results", "account")}


def check_references() -> None:
    """Every referencing column holds a value the target table actually has.

    RAISES rather than reporting, and is called once from rules.py after the store is
    loaded, so a hand-edited CSV fails at import — the same moment a bad TYPE fails.
    A check that runs only in the test suite would let a bad build reach the desk.
    """
    cache: dict[str, set] = {}
    problems = []
    for (table, column), (target, target_col) in REFERENCES.items():
        if table not in TABLES or target not in TABLES:
            continue
        if target not in cache:
            ti = TABLES[target].header.index(target_col)
            cache[target] = {r[ti] for r in load(target)}
        known = cache[target] | ({""} if (table, column) in BLANK_IS_THE_BOOK else set())
        ci = TABLES[table].header.index(column)
        for n, row in enumerate(load(table), start=2):
            if row[ci] is not None and row[ci] not in known:
                problems.append(
                    f"{table}.csv row {n}, {column}={row[ci]!r} is not in {target}.csv")
    if problems:
        known = sorted(cache.get(("accounts"), set()) or set())
        raise ValueError(
            "THE STORE DOES NOT JOIN UP:\n  " + "\n  ".join(problems)
            + (f"\n\naccounts.csv holds: {', '.join(known)}" if known else "")
            + "\n\nA name that is not in the register joins to nothing: its rows drop out of "
              "every per-account figure while every total still adds up.")


def load(ref) -> list[tuple]:
    """Every row of one table, typed, in file order.

    Returns plain tuples. The caller decides what NamedTuple to wrap them in — the store
    knows the shape of the data, not what the rest of the book calls it.
    """
    table = TABLES[ref]
    name = table.name
    with table.path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header != table.header:
            raise ValueError(
                f"{name}.csv header is {header}, schema expects {table.header}. "
                f"The store and the schema must agree before anything is read from it.")
        rows = []
        for row_no, raw in enumerate(reader, start=2):
            if len(raw) != len(table.fields):
                raise ValueError(
                    f"{name}.csv row {row_no}: {len(raw)} cells, expected "
                    f"{len(table.fields)}")
            rows.append(tuple(_parse(f, v, name, row_no)
                              for f, v in zip(table.fields, raw)))
    return rows
