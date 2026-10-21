"""
engine.py — THE ENGINE.

Events in, book out: one implementation of every derived figure, so every caller asking the same
question gets the same answer. The renderers — the desk and the report — read from here and
compute nothing of their own (tests/test_figures.py), and `Book.HEADLINE` registers
every headline figure with its basis and unit.

It reads the record through ONE seam, `load_store()`, and imports only pandas and the record's
rules (tests/test_store_doors.py).

THE BASIS IS A COLUMN, NOT A WARNING: a figure is money or notional, and roll_up() refuses to add
across the two.

PANDAS TRAPS this code has fallen into, each commented where it bites:
  1. `r.mode` in `df.apply(axis=1)` is `Series.mode`, the METHOD — silently truthy. Use `r["mode"]`.
  2. A share sale from a holding still held is VALUED at minus its quantity: two flags, not one.
  3. A pooled S.104 disposal releases cost from a position that stays OPEN — `share_pools()`.
  4. pandas 3.0's `str` dtype refuses a `datetime.date`; convert with isoformat().

New to pandas? A DataFrame is a table in memory. `df["cost"].sum()` totals a column;
`df[df.direction == "Buy"]` filters rows; `df.groupby("account")["amount"].sum()` totals by
account; `a.merge(b, on="realisation_id")` joins two tables. Most of this file is those four.
"""

from __future__ import annotations

import pandas as pd

from portfusion.record import rules as D


# =====================================================================================
# 1 · THE STORE  —  record in, DataFrames out
# =====================================================================================
#
# pd.DataFrame() on a list of NamedTuples takes the column names off the tuple itself, so there
# is no mapping layer to write or keep in step. AN EMPTY TABLE HAS NO TUPLE TO TAKE THEM OFF, so
# each frame also names its tuple's fields: a new book, whose tables are empty, still has columns.

def utc_of(at: str) -> str:
    """A journal instant on its one clock (`schema.record_instant`): UTC, to the second, marked
    `Z`. One written so is returned as it is; an older one, a UK wall-clock time with no zone, is
    read as UK time."""
    at = str(at)
    if not at or at.endswith("Z"):
        return at
    t = pd.Timestamp(at).tz_localize("Europe/London").tz_convert("UTC")
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def uk_instant(at: str) -> str:
    """A journal instant as UK wall-clock time, for a reader: "2026-10-21T15:29:09"."""
    return pd.Timestamp(utc_of(at)).tz_convert("Europe/London").strftime("%Y-%m-%dT%H:%M:%S")


def _on_one_clock(journal: pd.DataFrame) -> pd.DataFrame:
    """The journal with every instant in UTC (`utc_of`), so its rows compare and order as they
    happened, whichever clock wrote them."""
    journal["at"] = journal["at"].map(utc_of)
    return journal


def load_store() -> dict[str, pd.DataFrame]:
    """The tables the engine reads as frames: the dated ones, the marks, the histories and the
    quarter rows. The rest of the record it reads as the record's own rows, through `self.D`, and a
    frame here that nothing reads is refused (`test_store_doors.py`).

    The histories' folder comes from `D.store_dir()`, as every other table's comes from
    `schema.STORE`, so a store that moves moves all of them together.

    Side effects: reads every file in the store directory.
    """
    # A HISTORY IS THE ONLY COPY OF EVERY MARK IT HOLDS, so an absent one is refused BY NAME
    # rather than read as empty, which would value every past date at nothing and say nothing.
    # `portfusion init` writes all three with a book.
    for name in ("price-history.csv", "fx-history.csv", "account-statements.csv"):
        if not (D.store_dir() / name).is_file():
            raise SystemExit(f"{name} is missing from {D.store_dir()}: a new book is given it by "
                             f"`portfusion init`, so restore this book's copy rather than start "
                             f"an empty one — a history is the only copy of every mark it holds")
    store = {
        "income":    pd.DataFrame(D.ci_rows, columns=D.CostIncomeRow._fields),
        "movements": pd.DataFrame(D.movements,
                                  columns=["date", "account", "amount", "source", "detail"]),
        # THE SCHEMA'S HEADER, not a typed copy of it — the copy here went stale the day
        # current-prices.csv gained `struck` and `at`.
        "prices":    pd.DataFrame(D.CURRENT_PRICES,
                                  columns=D.schema.TABLES["current-prices"].header),
        # THE APPEND-ONLY HISTORIES, so the engine can value a past date. Here, because
        # load_store() is the ONE seam into the store.
        "history.prices": pd.read_csv(D.store_dir() / "price-history.csv", dtype={"date": str}),
        "history.fx":    pd.read_csv(D.store_dir() / "fx-history.csv", dtype={"date": str}),
        # The account statements: what a broker said an account was worth, and when. The LIVE
        # readings, without their lifecycle: a superseded one stays on file and is no reading.
        "statements":    _live(pd.read_csv(D.store_dir() / "account-statements.csv",
                                           dtype={"as_of": str})),
        # Every account's CONTRIBUTION to net asset value at each 2026 quarter end.
        # `contribution` is a column here, not a footnote: a share account contributes its
        # POSITIONS AT MARKET and a spread-bet account its ACCOUNT EQUITY, never its
        # notional. That is the one rule this table exists to enforce.
        "quarter_nav": pd.DataFrame(D.QUARTER_NAV, columns=D.QuarterNAV._fields),
        # RECORD TIME — the one table ABOUT the record rather than part of it. Through the record,
        # like the row counts it reconciles against, so both come from the same store.
        # `rules.journal_rows()` is a function, never loaded at import: the build must never
        # depend on WHEN a row was entered. COLUMNS FROM THE SCHEMA, never typed here: a typed
        # list is a second copy of it.
        # ON ONE CLOCK: rows written before UTC record time carry UK time with no zone.
        "journal":       _on_one_clock(pd.DataFrame(D.journal_rows(),
                                                    columns=list(D.JOURNAL_FIELDS))),
    }
    # Dates as real dates, not strings. Doing this once, here, is what makes every
    # "give me Q2" question downstream a one-liner instead of string slicing.
    for name in ("income", "movements"):
        store[name]["date"] = pd.to_datetime(store[name]["date"], errors="coerce")
    return store


def _lookup(keys: pd.Series, by: pd.Series) -> pd.Series:
    """`keys.map(by)` for a `by` with a unique index. pandas cannot map through an EMPTY datetime
    series — it casts it to float and fails — and on a new book every such series is empty."""
    return pd.Series(by.reindex(keys).to_numpy(), index=keys.index)


def _live(frame: pd.DataFrame) -> pd.DataFrame:
    """A history's live rows, without the `status` column every reader would otherwise filter on."""
    return frame[frame["status"] == D.LIVE_MARK].drop(columns="status").reset_index(drop=True)


# =====================================================================================
# THE BASELINE  —  the book's own starting line
# =====================================================================================
#
# The record begins on the book's `record_begins` date. Positions opened before then are in the
# book so their COST BASIS is known; they are not part of the performance record. A pre-baseline
# leg is an opening holding, HELD AT THE BASELINE, and carries a flag.
BASELINE = pd.Timestamp(D.SETTINGS["record_begins"])


# The same date as a store key. QUARTER_NAV is keyed by ISO string, so the baseline
# is spelled once here rather than typed at each lookup.
BASELINE_ASOF = (BASELINE - pd.Timedelta(days=1)).date().isoformat()


def record_begins() -> pd.Timestamp:
    """The day the record begins, read from the record as it stands now: what code that has no
    Book reads. `BASELINE` is the same date as the book loaded at import, which a reload of a
    changed setting, or a Book built from another store, does not move; a Book reads its own
    (`Book.baseline`)."""
    return pd.Timestamp(D.SETTINGS["record_begins"])


# =====================================================================================
# THE TWO BASES  —  as code rather than as a warning. rules.SPREAD_BET is the definition.
# =====================================================================================
#
# Every published metric is on ONE of two bases — money (what the book has: NAV, capital, income,
# growth) or notional (the size of an economic interest) — and roll_up() refuses to add across
# them, so the wrong sum is impossible rather than forbidden. A spread-bet account contributes its
# EQUITY to NAV and its NOTIONAL to exposure; both are on the frame, and the basis decides which
# total each may touch.
#
# A LINE'S KIND — `shares` / `spread bet`, the register's own words (schema.KINDS) — asks a
# different question: DO WE OWN IT, OR HAVE EXPOSURE TO IT. Not `basis` (what kind of number,
# Book.HEADLINE), `measure`, `evidence` or `contribution`: four names for four questions
# (docs/glossary.md §2). Every frame carries it as `held_as`, the heading a reader meets.
MONEY_KINDS = frozenset({"shares"})
assert MONEY_KINDS < set(D.schema.KINDS), "book.MONEY_KINDS and the schema disagree"

MEASURE_BASIS = {
    "exposure":       "notional",
    "nav":            "capital",
    "capital_employed": "capital",
    "opening_capital": "capital",
    "capital_deployed": "capital",
    "return_income":  "capital",
    "capital_growth": "capital",
    "income":         "capital",
}


class BasisError(TypeError):
    """Raised when a caller tries to add a notional figure to a money figure."""


class MissingMark(KeyError):
    """No mark on or before a date for a line: `keys` names the mark keys that have none. A
    KeyError, so every caller that catches one still does; `Book.valuation_gaps()` reads the keys
    rather than the sentence."""

    def __init__(self, keys: list[str], message: str):
        super().__init__(message)
        self.keys = keys


def roll_up(frame: pd.DataFrame, *measures: str) -> dict[str, float]:
    """Total the named measures over an account-level frame.

    REFUSES TO ADD ACROSS BASES. Asking for exposure and nav in one call is the
    mistake this function exists to make impossible; ask twice instead.
    """
    unknown = [m for m in measures if m not in MEASURE_BASIS]
    if unknown:
        raise KeyError(f"no basis declared for {unknown}; add it to MEASURE_BASIS")
    bases = {MEASURE_BASIS[m] for m in measures}
    if len(bases) > 1:
        raise BasisError(
            f"refusing to total {list(measures)} together: that mixes "
            f"{sorted(bases)}. Total one basis or the other, "
            f"never a figure from each.")
    # A TOTAL WITH A BLANK IN IT IS BLANK. pandas reads a blank as nothing and returns a figure,
    # and a year whose opening is not yet frozen would open at £0.00.
    return {m: float(frame[m].sum(min_count=len(frame))) for m in measures}


# =====================================================================================
# 2 · THE DERIVED LEDGER  —  which buy legs a sale consumed, and what cost that released
# =====================================================================================

def _buy_cost(qty, val, mode):
    """GBP cost of a buy leg.

    A spread bet holds its entry level in points rather than a total, so its cost is its
    size — the ledger's `qty` on a bet is its stake per point — times the level. Shares hold
    the settled GBP total. This asymmetry is real and it is why `mode` exists.
    """
    return qty * val if mode == "sb" else val


def realised_legs() -> dict[str, str]:
    """Spread-bet leg -> the realisation that consumed it: the leg a sale names in
    `rules.EXIT_LEG_MATCH`. A share leg has no such match — it sits in a pool, and
    `share_pools()` says which realisation emptied it."""
    return {tid: D.REALISATION_BY_EXIT[eid] for eid, tid in D.EXIT_LEG_MATCH.items()}


def share_pools(ledger: pd.DataFrame) -> pd.DataFrame:
    """EVERY SHARE HOLDING'S POOL, walked from its own events — the one implementation of what a
    share sale released and what an account still holds.

    A holding is one account's shares in one ticker, and every share in it costs the average
    (S.104). Each is walked in date order — undated pre-baseline buys first, buys before sales on
    a day, sales in eid order. A buy adds its quantity and cost; a corporate action is a buy of
    nil cost, so it moves the quantity alone. A sale releases quantity x the average, or ALL that
    remains when it empties the pool, so rounding leaves nothing behind. An emptied pool bought
    again is a new holding, opened on its own date and closed under its own realisation.

    One row per share buy and share sale, indexed by id:
      released  a sale's released cost; NaN on a buy
      opened    the day its holding opened: the first buy since the pool was last empty
      emptied   the day its holding was sold out; NaT while it is still held
      parcel    the realisation that emptied it; None while it is still held

    REFUSES, in words the bench shows: a sale larger than its holding on its date; a holding whose
    sales name two realisations; a realisation spanning two holdings. Each passes the schema and
    books a wrong gain.
    """
    shares = ledger[(ledger["held_as"] == "shares") & ledger["direction"].isin(("Buy", "Sell"))]
    walk = (shares.assign(_sale=(shares["direction"] == "Sell").astype(int))
                  .sort_values(["acct", "ticker", "date", "_sale", "id"],
                               na_position="first", kind="stable"))
    out: dict[str, dict] = {}
    home: dict[str, tuple] = {}
    wrong: list[str] = []
    for (acct, ticker), g in walk.groupby(["acct", "ticker"], sort=False):
        qty = cost = 0.0
        members: list[str] = []
        opened, parcels, n = pd.NaT, set(), 0
        for r in g.to_dict("records"):
            if not members:
                opened = r["date"]
            members.append(r["id"])
            row = {"released": float("nan"), "opened": opened, "emptied": pd.NaT, "parcel": None}
            out[r["id"]] = row
            if r["direction"] == "Buy":
                qty += r["qty"]
                cost += _buy_cost(r["qty"], r["val"], r["mode"])
                continue
            rid = D.REALISATION_BY_EXIT[r["id"]]
            parcels.add(rid)
            if home.setdefault(rid, (acct, ticker, n)) != (acct, ticker, n):
                wrong.append(f"{rid} spans two holdings — {home[rid][0]} {home[rid][1]} and "
                             f"{acct} {ticker}")
            day = "an undated day" if pd.isna(r["date"]) else f"{r['date']:%Y-%m-%d}"
            if r["qty"] > qty + 1e-9:
                raise ValueError(
                    f"{r['id']} ({rid}) sells {r['qty']:g} {ticker} from {acct}, which held "
                    f"{max(qty, 0.0):g} on {day}. A sale cannot be larger than the holding it "
                    f"comes from.")
            empties = abs(qty - r["qty"]) < 1e-9
            row["released"] = round(cost, 2) if empties else round(cost * r["qty"] / qty, 2)
            qty -= r["qty"]
            cost -= row["released"]
            if empties:
                if len(parcels) > 1:
                    wrong.append(f"{acct} {ticker}'s sales name {len(parcels)} realisations: "
                                 f"{', '.join(sorted(parcels))}")
                for i in members:
                    out[i]["emptied"], out[i]["parcel"] = r["date"], rid
                qty = cost = 0.0
                members, parcels, n = [], set(), n + 1
        if len(parcels) > 1:
            wrong.append(f"{acct} {ticker}'s sales name {len(parcels)} realisations: "
                         f"{', '.join(sorted(parcels))}")
    if wrong:
        raise ValueError("A SHARE SALE IS FILED UNDER THE WRONG PARCEL:\n  " + "\n  ".join(wrong))
    frame = pd.DataFrame.from_dict(out, orient="index",
                                   columns=["released", "opened", "emptied", "parcel"])
    frame["opened"] = pd.to_datetime(frame["opened"])
    frame["emptied"] = pd.to_datetime(frame["emptied"])
    return frame


def build_ledger() -> pd.DataFrame:
    """The trade ledger with Direction and Realisation ID attached: one row per event, buys and
    sells. The spine everything else hangs off."""
    buys = pd.DataFrame(D.trades, columns=D.Trade._fields)
    buys["direction"] = "Buy"
    # HOW EACH LEG IS COSTED, from its code's kind (`rules.Trade.mode`): a frame of NamedTuples
    # carries their fields and not their properties.
    buys["mode"] = [t.mode for t in D.trades]
    # THE LEDGER'S `qty` IS THE LINE'S SIZE IN ITS OWN UNIT: a share's count, a bet's stake per
    # point (`Trade.size`). The store keeps the two in their own columns; every roll-up here is
    # size x price, which on a bet is stake x level, the notional.
    buys["qty"] = [t.size for t in D.trades]

    # Exits map onto the ledger's own shape. One slot changes meaning on a sell row: `val` holds
    # the GBP proceeds. `price`, `cur` and `rate` are the sale's own, as a buy's are its.
    sells = pd.DataFrame([
        {"id": e.eid, "date": e.date, "source": e.source, "acct": e.acct, "ticker": e.ticker,
         "cur": e.cur, "qty": e.size, "stake": e.stake,
         # `broker_ref` from its column: the reference that retrieves the sale.
         "price": e.price, "rate": e.rate, "val": e.proceeds, "mode": "sell",
         "broker_ref": e.broker_ref, "note": e.note}
        for e in D.exits
    ], columns=["id", "date", "source", "acct", "ticker", "cur", "qty", "stake", "price", "rate",
                "val", "mode", "broker_ref", "note"])
    sells["direction"] = "Sell"

    ledger = pd.concat([buys, sells], ignore_index=True)

    # EVERY EVENT IS DATED, in ISO (tests/test_record.py holds trades.date to it), so a date that
    # will not parse is a fault to stop on, never a leg to quietly read as undated.
    ledger["date"] = pd.to_datetime(ledger["date"], format="%Y-%m-%d")

    # --- THE COLUMN THAT MATTERS MOST -------------------------------------------------
    # `held_as` says what KIND of line this row is, from its code (`rules.KIND_OF_CODE`, the one
    # place it is stored): a share leg is money you own; a spread-bet leg is a contract value, an
    # economic interest, not money. Encoding it here is the whole point: as data, not a warning a
    # reader has to remember, so a function that totals "money" can refuse to include exposure,
    # and the wrong number stops being something you can type by accident.
    ledger["held_as"] = ledger["ticker"].map(D.KIND_OF_CODE)

    # A SHARE BUY BELONGS TO THE REALISATION THAT EMPTIED ITS HOLDING, and to none while the
    # holding is still held — a pool trim consumes no leg. A spread-bet leg to the sale naming it.
    pools = share_pools(ledger)
    rid = {e.eid: D.REALISATION_BY_EXIT[e.eid] for e in D.exits}
    rid.update(realised_legs())
    rid.update(pools["parcel"].dropna().to_dict())
    ledger["realisation_id"] = ledger["id"].map(rid)
    ledger["released"] = _lookup(ledger["id"], pools["released"])
    ledger["pool_opened"] = _lookup(ledger["id"], pools["opened"])
    ledger["pool_emptied"] = _lookup(ledger["id"], pools["emptied"])

    # THE PROVENANCE IS `source` FROM THE STORE TO THE LEDGER (1 Oct 2026), as on every other
    # table, so nothing is copied under a second name. A copy that stood here once read a column
    # only the sales had, and most rows lost their source with the suite green;
    # tests/test_engine_invariants.py now holds every ledger row to having one.

    # An OPEN buy leg is a buy that no realisation has consumed. Drives QUANTITY and COST.
    ledger["open_leg"] = (ledger["direction"] == "Buy") & ledger["realisation_id"].isna()

    # VALUED is deliberately a different set: it adds each SHARE SALE FROM A HOLDING STILL HELD.
    # A pool trim consumes no buy leg, so every buy stays open at its full quantity and cost; the
    # sale beside them is valued at minus what it sold and costed at minus what it released, which
    # is the only way a partial disposal comes off when value is computed leg by leg. A holding
    # sold out carries nothing: its buys are consumed and its sales are not valued.
    #
    # Two flags rather than one is the honest encoding. Collapsing them into `open_leg`
    # is how this special case would quietly disappear.
    ledger["valued"] = ledger["open_leg"] | ((ledger["direction"] == "Sell")
                                             & (ledger["held_as"] == "shares")
                                             & ledger["pool_emptied"].isna())

    # PRE-record_begins(): opened before the record began.
    ledger["pre_baseline"] = ledger["date"] < record_begins()
    return ledger


def cost_released(ledger: pd.DataFrame) -> dict[str, float]:
    """GBP cost released by each sale, by eid. Two conventions, one per kind of holding:
      * pool      -- a share sale releases its holding's average, from `share_pools()` by way of
                     the ledger's `released` column
      * leg-exact -- a spread-bet sale names the bet it closed, and releases that leg's cost
    """
    by_id = {t.id: t for t in D.trades}
    released = ledger.set_index("id")["released"]
    out, unmatched = {}, []
    for e in D.exits:
        if pd.notna(released.get(e.eid)):
            out[e.eid] = float(released[e.eid])
        elif e.eid in D.EXIT_LEG_MATCH:
            leg = by_id[D.EXIT_LEG_MATCH[e.eid]]
            out[e.eid] = round(_buy_cost(leg.size, leg.val, leg.mode), 2)
        else:
            unmatched.append(f"{e.eid} ({D.REALISATION_BY_EXIT[e.eid]})")
    if unmatched:
        raise ValueError(
            f"{', '.join(unmatched)} released no cost: a spread-bet sale names the leg it closed "
            f"in exits.csv `closes`, and only a share sale is released from its pool.")
    return out


# =====================================================================================
# 3 · VALUATION
# =====================================================================================

def _price_lookup():
    return {r[0]: r[1] for r in D.CURRENT_PRICES}


def _rate_now_lookup(record=None):
    """Currency -> the rate the book converts it at RIGHT NOW: fx.csv, one row per currency.

    FROM THE TABLE, not a list: a currency missing from a list fell through to PARITY, a silent
    wrong answer. A new currency joins by having a row.
    """
    return {cur: rate for cur, rate, *_ in (record or D).fx_rows}


def rate_now(cur: str, record=None) -> float:
    """THE ONE ANSWER to "what rate does this book convert `cur` at now". GBP per unit.

    Every present-tense figure comes through here — `value_legs()` and `changes_since()`'s
    `value_to` — so two readings of one figure cannot use two rates. A DATED figure does NOT:
    `_marks_at()` answers that, because a past valuation has to reproduce next year.

    Raises for an unknown currency rather than assuming parity: 1.0 is a real rate and a
    plausible wrong answer.
    """
    if cur == "GBP":
        return 1.0
    rates = _rate_now_lookup(record)
    if cur not in rates:
        raise KeyError(
            f"no live rate for {cur}. fx.csv carries a `-NOW` row per convertible currency; "
            f"it has {sorted(rates)}. A figure cannot be converted at a rate nobody banked.")
    return rates[cur]


def value_legs(ledger: pd.DataFrame) -> pd.DataFrame:
    """Attach cost and current market value to every leg.

    Two valuation routes, never merged:
      * Share      -- qty x price / fx      (price is local, fx is GBP-per-unit)
      * Spread bet -- stake x level         (sterling at parity; the ledger's qty is the stake)

    BRACKET ACCESS — r["mode"], never r.mode: `.mode` is the pandas METHOD, every comparison
    against it is silently False, and every spread bet becomes worth nothing.
    """
    px = _price_lookup()
    # A MARK CONVERTS AT ITS SHARE'S CURRENCY, never the deal's: a deal's `cur` is the
    # currency its price was stated in — sterling on an HL deal in a US share — so every leg is
    # priced in the currency its identity row quotes the holding in.
    _h = D.schema.TABLES["securities"].header
    quote = {r[_h.index("code")]: r[_h.index("currency")] for r in D.SECURITIES}

    def cost(r):
        """Cost attaches to OPEN BUY LEGS, and comes off by what each share sale from a holding
        still held released."""
        if r["direction"] == "Sell":
            return -r["released"] if r["valued"] else 0.0
        if not r["open_leg"]:
            return 0.0
        return _buy_cost(r["qty"], r["val"], r["mode"])

    def market(r):
        """Market value attaches to VALUED legs -- open buys, less each share sale from a holding
        still held."""
        if not r["valued"]:
            return 0.0
        if r["mode"] == "sb":
            contract = D.LEG_CONTRACT[r["id"]]
            if contract not in px:
                raise MissingMark([contract], f"{r['id']} is open on {contract}, which has no "
                                              f"mark: take one on the Price Refresh first.")
            return r["qty"] * px[contract]
        if r["held_as"] == "shares":
            sign = -1 if r["direction"] == "Sell" else 1
            return sign * r["qty"] * px[r["ticker"]] / rate_now(quote[r["ticker"]])
        return 0.0

    out = ledger.copy()
    out["gbp_cost"] = out.apply(cost, axis=1)
    out["gbp_value"] = out.apply(market, axis=1)
    return out


def marks_replaceable() -> dict:
    """WHICH MARKS A REFRESH CAN REPLACE, which are carried, and how old each one is.

    THE WHOLE SET, deliberately: the book is refreshed whole or not at all (`docs/prices.md`), so
    the form lists everything replaceable and each row says whether it is `stale` against
    `rules.PRICE_AGE_LIMIT`, rather than filtering by age.

    A classification, so it lives in the engine and not a renderer. A module function, not a
    `Book` method: it needs no ledger.

      replaceable  every mark a refresh may replace, with its outgoing price, its age and whether
                   that age is past the limit — because a price updated without its DATE makes the
                   book claim a freshness it does not have.
      held         CARRIED lines (the key stays `held` — glossary §5): no feed and immaterial, at
                   the last broker price by decision. Kept apart, because a fresh date on a price
                   nobody can look up is the error being guarded against.
      fx           the live rate of each currency, saying whether it is carried and why
                   (`rules.RATE_CARRIED`), and how old it is, as a price and a reading say.
      readings     each spread-bet account's IG reading — its outgoing equity and date — the one
                   account figure a refresh replaces, read in the same pass as the levels.
    """
    today = pd.Timestamp.today().normalize()
    stmt = D.STATEMENT_PRICED
    frozen = D.RATE_CARRIED

    def _dated(text: str) -> dict:
        day = pd.to_datetime(text, errors="coerce")
        return ({"as_of": None, "age_days": None} if pd.isna(day)
                else {"as_of": day.date().isoformat(), "age_days": int((today - day).days)})

    def _row(t: str, price: float, cur: str, as_of: str, src: str, struck: str, at: str) -> dict:
        age = int((today - pd.Timestamp(as_of)).days)
        return {"ticker": t, "price": price, "currency": cur, "as_of": as_of, "source": src,
                "struck": struck, "at": at, "age_days": age, "stale": age > D.PRICE_AGE_LIMIT,
                # AN IG CONTRACT'S PRICE IS A LEVEL IN POINTS, beside the market's currency.
                "contract": t in D.CONTRACTS}

    return {
        "today": today.date().isoformat(),
        "age_limit": D.PRICE_AGE_LIMIT,
        "replaceable": [_row(*r) for r in D.CURRENT_PRICES if r[0] not in stmt],
        "held": [dict(_row(*r), why=stmt[r[0]]) for r in D.CURRENT_PRICES if r[0] in stmt],
        "fx":   [{"currency": cur, "rate": rate, "source": src, "struck": struck,
                  "carried": cur in frozen, "why": frozen.get(cur), **_dated(as_of)}
                 for cur, rate, as_of, src, struck in D.fx_rows],
        "readings": [{"account": r.acct, "equity": r.equity, "as_of": str(r.as_of)[:10],
                      "age_days": int((today - pd.Timestamp(r.as_of)).days)}
                     for r in D.ac_rows if D.ACCOUNT_KIND.get(r.acct) == "spread bet"],
    }


# =====================================================================================
# 4 · THE BOOK  —  what you actually call
# =====================================================================================

class _Pinned:
    """The record's names as they stood when a Book was built.

    `rules.reload_store()` re-executes the module, which REBINDS every table to a new object
    rather than changing the old one, so references taken here keep the version the Book's
    frames came from. A reference, not a copy: nothing is duplicated.

    What it holds that is a FUNCTION still reads the module when called. Two of those read the
    store — `cash_latest()` and `store_rows()` — and the Book takes both when it is built.
    """

    def __init__(self, module):
        self.__dict__.update(vars(module))


class Book:
    """The book: every derived figure the desk and the report show, as methods.

    There is ONE of it, so two renderers asking the same question get the same answer.

    IT ANSWERS FROM THE RECORD IT WAS BUILT FROM, however the process's record moves after:
    every method reads `self.D`, the record pinned at construction, and never `rules` itself.
    `test_store_doors.py` holds that, by source and by behaviour.
    """

    @property
    def baseline(self) -> pd.Timestamp:
        """The day this Book's record begins: its own setting, pinned with the rest of the record
        it was built from, so a Book of another store, or one built after the setting changed,
        is measured from its own start, not from the date the loaded book held at import."""
        return pd.Timestamp(self.D.SETTINGS["record_begins"])

    @property
    def baseline_asof(self) -> str:
        """The baseline's quarter-end key: the day before the record begins, as an ISO date."""
        return (self.baseline - pd.Timedelta(days=1)).date().isoformat()

    def __init__(self, store_dir=None):
        """`store_dir` builds the Book from another store. The process's record is pointed there
        for the construction and put back after (`rules.store_at()`), so another thread reading
        the record meanwhile would see the other store; nothing in the build or the desk does.
        """
        if store_dir is None:
            self._build()
            return
        with D.store_at(store_dir):
            self._build()

    def _build(self):
        self.D = _Pinned(D)
        self.store = load_store()
        self.ledger = value_legs(build_ledger())
        self.cost_released = cost_released(self.ledger)
        self._cash_latest = D.cash_latest()
        # THE CASH AT EACH READING'S DATE, for a share reading whose document states none.
        self._cash_at_reading = {r.acct: D.cash_latest(on=r.as_of).get(r.acct)
                                 for r in D.ac_rows if r.as_of}
        self._rows_on_file = D.store_rows()

        # Held quantity walks the whole ledger, and holdings_at() asks once per ticker. Keyed by
        # DATE AND ACCOUNT: the date alone would hand one account's caller the whole book's legs —
        # an answer correct in itself, which is the worst kind of wrong to cache.
        self._held_cache: dict[tuple[str, str | None], dict[str, dict]] = {}

        # changes_since() walks the ledger twice per line, and What Changed asks for the frame
        # and both basis totals. Keyed by what the answer depends on, as above.
        self._changes_cache: dict[tuple[str | None, str | None], pd.DataFrame] = {}

    # ---- THE HEADLINE FIGURES, for every renderer ------------------------------------

    def owned(self) -> float:
        """Securities owned, at market. THIS IS MONEY."""
        L = self.ledger
        return L.loc[L["held_as"].isin(MONEY_KINDS), "gbp_value"].sum()

    def exposure(self) -> float:
        """Spread-bet NOTIONAL. See rules.SPREAD_BET."""
        L = self.ledger
        return L.loc[~L["held_as"].isin(MONEY_KINDS), "gbp_value"].sum()

    def total_exposure(self) -> float:
        """Owned + contract value. A measure of position size, NOT of capital."""
        return self.owned() + self.exposure()

    def portfolio_cost(self) -> float:
        return self.ledger["gbp_cost"].sum()

    def unrealised(self) -> float:
        return self.total_exposure() - self.portfolio_cost()

    def realised(self) -> float:
        """Realised gain: proceeds less the cost each sale released."""
        proceeds = sum(e.proceeds for e in self.D.exits)
        return proceeds - sum(self.cost_released.values())

    #
    # THE REGISTRY: label -> its basis, its unit, and whether a dated page may quote it. Here, in
    # the engine, so no renderer holds its own opinion of whether a figure is money.
    #
    # THESE STRINGS ARE THE READER-FACING WORDS; changing one changes the desk and the report
    # together. point_in_time says whether a figure has a value AT A DATE: the YTD
    # return does not, so headline("2026-06-30") omits it and a Q2 page cannot quote it.
    #
    # THE ORDER IS THE ORDER A LIST OF THEM READS IN, on the Dashboard and in the report's Section 1
    # alike (test_figures.py): net asset value, exposure and the parts that make it, the costs and
    # the gains, the year's income and capital, the returns, then the counts.
    #
    # SINCE_START carries the day the record begins, which is the book's setting, so it is named
    # once here and a renderer looking the figure up asks for it rather than typing the date.
    SINCE_START = f"Return since {BASELINE:%-d %b %Y} (MWR)"

    HEADLINE = {
        "Net asset value":                       {"basis": "capital", "unit": "gbp", "point_in_time": True},
        "Total market exposure":                 {"basis": "notional", "unit": "gbp", "point_in_time": True},
        "— of which securities owned":           {"basis": "capital", "unit": "gbp", "point_in_time": True},
        "— of which spread-bet notional":        {"basis": "notional", "unit": "gbp", "point_in_time": True},
        "Exposure above net asset value":        {"basis": "notional", "unit": "gbp", "point_in_time": True},
        "Cost of securities owned":              {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "Spread-bet notional at entry":          {"basis": "notional", "unit": "gbp", "point_in_time": False},
        # A GAIN IS MONEY ON EITHER KIND OF LINE: a bet's unrealised gain is stake x (level now
        # less entry level), IG's running profit or loss, inside its equity (rules.SPREAD_BET),
        # as its realised gain is money. Only the VALUE a bet's gain is measured from is
        # notional. "Cost and entry notional", the mixed sum both costs made, retired on 13 Oct
        # 2026; the two costs stand apart above, as exposure's two parts do.
        "Unrealised gain / loss":                {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "Realised gain / loss to date":          {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "Total gain":                            {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "YTD income":                            {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "Capital employed (opening + deployed)": {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "YTD return (MWR)":                      {"basis": "capital", "unit": "pct", "point_in_time": False},
        SINCE_START:                             {"basis": "capital", "unit": "pct", "point_in_time": False},
        "Open positions":                        {"basis": "count", "unit": "count", "point_in_time": True},
        "Closed round trips":                    {"basis": "count", "unit": "count", "point_in_time": False},
    }

    #: The bases that mean "this is NOT the book's capital". A renderer marks these; the
    #: definition is rules.SPREAD_BET; this is the basis stated per figure.
    NOTIONAL_BASES = frozenset({"notional"})

    @classmethod
    def basis_of(cls, label) -> str:
        """The basis a registered figure carries, by its label. KeyError for a label nobody
        registered: a figure is classified before any renderer shows it."""
        try:
            return cls.HEADLINE[label]["basis"]
        except KeyError:
            raise KeyError(f"{label!r} is not in Book.HEADLINE: register it, with its basis and "
                           f"unit, before showing it") from None

    def headline(self, as_of: str | None = None) -> dict[str, float]:
        """Every headline figure, keyed by the label every renderer must use.

        as_of=None  — live, from the current marks. The desk's Dashboard.
        as_of=DATE  — the quarter end, from the STORE's own quarter rows. Returns ONLY the
                      labels HEADLINE marks point_in_time, so a dated page cannot quote a
                      year-to-date figure.

        A DATED VIEW READS THE STORE, NOT THE LEDGER. The two disagree slightly at a past date,
        entirely in the share accounts, and the store's figure ships because a quarter's inputs
        are FROZEN and a reconstruction is not. The reconstruction stays available through
        holdings_at().

        Side effects: none.
        """
        if as_of is None:
            # BY TICKER, NOT THE by="issuer" DEFAULT: an issuer roll-up is not a partition by basis,
            # and summing cost by basis on it understates owned cost.
            h = self.holdings(by="ticker")
            # THE YEAR, BUILT ONCE: net asset value and both returns are read off it.
            t = self.totals()
            realised = self.realised()
            unrealised = self.unrealised()
            exposure = self.total_exposure()
            nav = t["nav"]
            return {
                "Net asset value": nav,
                "Total market exposure": exposure,
                "— of which securities owned": self.owned(),
                "— of which spread-bet notional": self.exposure(),
                "Exposure above net asset value": exposure - nav,
                "Cost of securities owned": float(h.loc[h["held_as"] == "shares", "cost"].sum()),
                "Spread-bet notional at entry": float(h.loc[h["held_as"] == "spread bet", "cost"].sum()),
                "Unrealised gain / loss": unrealised,
                "Realised gain / loss to date": realised,
                "Total gain": unrealised + realised,
                "YTD income": t["income"],
                "YTD return (MWR)": t["ytd"],
                self.SINCE_START: self.since_start(t["ytd"]),
                "Capital employed (opening + deployed)": t["capital_employed"],
                "Open positions": float(len(h)),
                "Closed round trips": float(len(self.round_trips().query("fully_closed"))),
            }

        # ONE TABLE, so the parts and the total cannot disagree. Splitting the same rows by
        # is_spread_bet() is what makes "— of which" mean it.
        rows = self.quarter_nav_rows(as_of, "exposure").set_index("account")["amount"]
        sb = float(sum(v for a, v in rows.items() if self.is_spread_bet(a)))
        exposure = float(rows.sum())
        nav = float(self.quarter_nav_total()[as_of])
        return {
            "Net asset value": nav,
            "Total market exposure": exposure,
            "— of which securities owned": exposure - sb,
            "— of which spread-bet notional": sb,
            "Exposure above net asset value": exposure - nav,
            # THE FROZEN COMPOSITION'S LINES, as the exposure above is its accounts' frozen rows: a
            # count of the ledger at the marks once took in lines no frozen account held.
            "Open positions": float(len(self.quarter_lines(as_of))),
        }

    # ---- THE MARKS  —  where the live figures stand, and how old they are ------------

    def valued_at(self) -> str:
        """The date the LIVE figures stand at — the newest mark in the current price set.

        One answer to "now" for every live figure, so the two Dashboards and the open quarter
        cannot disagree. THE NEWEST MARK, not today: printing today's date over marks
        struck days ago would be the more confident lie. The spread between newest and oldest is
        on the Dashboard's price line. A book with no mark yet stands where its record begins.
        """
        return self.price_ageing()["newest"] or self.baseline.date().isoformat()

    def price_ageing(self, today: str | None = None) -> dict:
        """How stale the marks are. The FIRST thing to check before reading any value.

        Only market-fed holdings count: a CARRIED line (`rules.STATEMENT_PRICED`) is held at its
        last broker price by decision, and counting it would make this read old for a reason
        nobody will act on.

        `age_days` is the OLDEST mark against `today` (an ISO date; today's if omitted): the
        figure `rules.PRICE_AGE_LIMIT` judges, so the Dashboard and `findings()` read one age.
        With no mark to age — a new book — both dates are None and nothing is old.
        """
        p = self.store["prices"]
        p = p[~p["ticker"].isin(set(self.D.STATEMENT_PRICED))]
        dates = pd.to_datetime(p["as_of"], errors="coerce").dropna()
        if dates.empty:
            return {"newest": None, "oldest": None, "spread_days": 0, "marks": 0, "age_days": 0}
        newest, oldest = dates.max(), dates.min()
        day = pd.Timestamp(today or pd.Timestamp.today().date())
        return {"newest": newest.date().isoformat(), "oldest": oldest.date().isoformat(),
                "spread_days": int((newest - oldest).days), "marks": int(len(dates)),
                "age_days": int((day - oldest).days)}

    # ---- IDENTITY  —  code -> issuer -> sector / region ------------------------------

    #
    # Joined securities.company -> issuers.company, by full legal name, because one issuer can
    # hold several codes.
    def _identity(self) -> pd.DataFrame:
        """code -> company, sector, region, kind. One row per holding code."""
        # COLUMNS FROM THE SCHEMA, never typed: a typed list broke the day the table grew one.
        sec = pd.DataFrame(self.D.SECURITIES, columns=list(self.D.schema.TABLES["securities"].header))
        iss = pd.DataFrame(self.D.COMPANY_MASTER, columns=list(self.D.schema.TABLES["issuers"].header))
        return sec.merge(iss[["company", "sector", "region"]], on="company", how="left")

    def codes_held(self) -> list[str]:
        """EVERY CODE THE BOOK HAS HELD SINCE THE RECORD BEGAN, sorted: those open at the baseline
        and those bought or sold on or after it. A line closed before the baseline is not one of
        them; it is carried for its cost basis only (`as_of()`). Which codes a research note
        covers is read from this (`desk/doors/research_notes.py`)."""
        L = self.ledger
        since = set(L.loc[L["date"] >= self.baseline, "ticker"])
        return sorted(since | set(self.as_of(self.baseline.date().isoformat())["ticker"]))

    # ---- HOLDINGS --------------------------------------------------------------------

    def holdings(self, account: str | None = None, by: str = "issuer") -> pd.DataFrame:
        """What is held, at issuer level or ticker level.

        BY ISSUER IS THE PUBLISHED VIEW and MERGES each share/spread-bet pair into one row —
        Orlant's ORLA and ORLA SB are one holding there. Per-account tables keep them apart.

        AN ISSUER ROLL-UP IS NOT A PARTITION BY BASIS: summing cost or value by basis on it
        understates the owned figure. Pass `by="ticker"` for the split.

        No quantity on the issuer view: a share count plus an effective-share count means nothing.
        By ticker, a spread bet also carries `stake_per_point`; a share carries none.
        `weight` is a share of TOTAL MARKET EXPOSURE, not of cost.
        """
        L = self.ledger
        if account is not None:
            L = L[L["acct"] == account]

        rows = L[L["valued"]].copy()
        ident = self._identity().set_index("code")
        rows["company"] = rows["ticker"].map(ident["company"])
        rows["sector"] = rows["ticker"].map(ident["sector"])
        rows["region"] = rows["ticker"].map(ident["region"])
        # CURRENCY COMES FROM IDENTITY, NOT THE LEDGER ROW: a holding has one currency, but a
        # STRM.DE sale carries GBP because its proceeds are sterling. Summed by row, one EUR
        # position would split across two currencies while the total still tied.
        rows["currency"] = rows["ticker"].map(ident["currency"])

        unknown = sorted(rows.loc[rows["company"].isna(), "ticker"].unique())
        if unknown:
            raise KeyError(f"no identity row for {unknown} — every held code needs one in "
                           f"securities.csv, or its sector and region are silently blank")

        # A share sale from a holding still held counts at minus what it sold — trap 2.
        rows["qty"] = rows["qty"].where(rows["direction"] != "Sell", -rows["qty"])

        key = "company" if by == "issuer" else "ticker"
        agg = {"cost": ("gbp_cost", "sum"), "value": ("gbp_value", "sum")}
        if by != "issuer":
            agg["qty"] = ("qty", "sum")
        out = rows.groupby(key, as_index=False).agg(**agg)

        # OPEN DATE is the earliest buy leg STILL HELD, so a position's age is that of what is held.
        open_legs = rows[rows["open_leg"]]
        first_buy = open_legs.groupby(key)["date"].min()

        meta = rows.groupby(key).agg(sector=("sector", "first"), region=("region", "first"),
                                     currency=("currency", "first"), held_as=("held_as", "first"),
                                     company=("company", "first"))

        # A COLLAPSED ROW SAYS SO: at issuer level a share/spread-bet pair is one row, labelled
        # "mixed" rather than taking either side's kind, so a renderer classifying by basis treats
        # it as not-money — the safe way to be wrong about a row that is part of each.
        if key == "company":
            kinds = rows.groupby(key)["held_as"].nunique()
            mixed = kinds[kinds > 1].index
            meta.loc[meta.index.isin(mixed), "held_as"] = "mixed"
        # Which accounts hold it, in the canonical order.
        order = {a: i for i, a in enumerate(self.D.ACCOUNT_ORDER)}
        meta["accounts"] = open_legs.groupby(key)["acct"].apply(
            lambda s: " · ".join(sorted(set(s), key=lambda a: order.get(a, 99))))
        meta["open_date"] = first_buy
        out = out.merge(meta, left_on=key, right_index=True, how="left")
        out["gain"] = out["value"] - out["cost"]
        out["gain_pct"] = (out["gain"] / out["cost"]).where(out["cost"] != 0)
        total = out["value"].sum()
        out["weight"] = out["value"] / total if total else float("nan")
        out["days_held"] = (pd.Timestamp.today().normalize() - out["open_date"]).dt.days
        if by != "issuer":
            # A bet's size in its own terms: the ledger's qty on a bet IS its stake per point.
            out["stake_per_point"] = out["qty"].where(out["held_as"].eq("spread bet"))

        # ENTRY PRICE, in the holding's own currency: a QUANTITY-WEIGHTED MEAN of the legs still
        # held, each at its deal's price (`deal_prices()`), so a sold leg does not drag it. Blank
        # when any of them has none, rather than a mean of the ones that do.
        legs = open_legs.copy()
        legs["own"] = legs["id"].map(self.deal_prices()["price_own"])
        legs["weighted"] = legs["own"] * legs["qty"]
        agg = legs.groupby(key).agg(w=("weighted", "sum"), q=("qty", "sum"),
                                    gap=("own", lambda v: v.isna().any()))
        out["entry_price"] = out[key].map((agg["w"] / agg["q"]).where(~agg["gap"]))

        # CURRENT PRICE. A share is looked up by ticker. A SPREAD BET IS DERIVED as value / qty,
        # and that is deliberate: it is priced by CONTRACT, and one ticker can hold legs on two
        # contracts at two different levels — so there is no single "current price" to look up.
        # The implied average is the honest answer.
        px = {r[0]: (r[1], r[3]) for r in self.D.CURRENT_PRICES}

        # PRICE DATE, FROM THE OPEN LEGS' CONTRACTS — and one date per TICKER is a
        # simplification the tab has to make, so it must be the honest one. A ticker's legs can
        # sit on several contracts, so a lookup keyed by ticker alone keeps whichever leg comes
        # last: a closed contract's blank, or one contract's date with nothing to say which.
        #
        # So: gather every OPEN leg's contract and take the OLDEST mark among them. A position
        # is only as fresh as its stalest leg, which is the same rule price_ageing() applies to
        # the book as a whole. Closed legs are excluded: a closed contract is not priced because
        # nothing holds it any more, and that is correct, not a gap.
        open_contract_dates: dict[str, list[str]] = {}
        if by == "ticker":
            leg_ticker = dict(zip(open_legs["id"], open_legs[key]))
            for tid, tk in leg_ticker.items():
                c = self.D.LEG_CONTRACT.get(tid)
                if c and c in px:
                    open_contract_dates.setdefault(tk, []).append(px[c][1])

        def _current(row):
            if row["held_as"] == "spread bet":
                return row["value"] / row["qty"] if row.get("qty") else None
            return px[row[key]][0] if row[key] in px else None

        def _priced_at(row):
            dates = open_contract_dates.get(row[key])
            if dates:
                return min(dates)
            return px[row[key]][1] if row[key] in px else None

        if by == "ticker":
            out["current_price"] = out.apply(_current, axis=1)
            out["priced_at"] = out.apply(_priced_at, axis=1)
        return out.sort_values(key).reset_index(drop=True)

    # ---- THE JUDGEMENT  —  store/reasoning.csv, beside each position's numbers -------

    def with_reasoning(self, frame: pd.DataFrame, opened: str = "open_date",
                       closed: str | None = None) -> pd.DataFrame:
        """`frame` with every why on each row's position beside it, and whether each half is OWED.

        `whys` is the rows of `store/reasoning.csv` for the row's ticker dated within the
        position's life — on or after its `opened` column and, where the frame has a `closed`
        one, on or before that — oldest first, each {date, half, text}, `half` being
        `why_entered` or `why_exited`. A name bought again after a full exit starts a new life,
        and the old one's whys stay with the round trip they explain.

        Adds `research_notes` (a list of {ref, date, url}; an empty one is not a gap) and
        `why_entered_owed`, with `why_exited_owed` when `closed` is given: no why of that half in
        the window, and the position opened (or closed) on or after `rules.REVIEW_FROM`. An
        out-of-scope blank is NOT owed, and the difference is the point of the flag.

        Side effects: none. The frame passed in is not changed.
        """
        out = frame.copy()
        reasons, notes = self.D.REASONING, self.D.RESEARCH_NOTES
        start = pd.to_datetime(out[opened], errors="coerce")
        end = (pd.to_datetime(out[closed], errors="coerce") if closed
               else pd.Series(pd.NaT, index=out.index))

        def whys(ticker, lo, hi) -> list[dict]:
            got = []
            for r in reasons.get(ticker, []):
                when = pd.Timestamp(r.date)
                if (pd.notna(lo) and when < lo) or (pd.notna(hi) and when > hi):
                    continue
                got += [{"date": r.date.isoformat(), "half": half, "text": text}
                        for half, text in (("why_entered", r.why_entered),
                                           ("why_exited", r.why_exited))
                        if isinstance(text, str) and text.strip()]
            return got

        out["whys"] = [whys(t, lo, hi) for t, lo, hi in zip(out["ticker"], start, end)]
        out["research_notes"] = out["ticker"].map(
            lambda t: [{"ref": r, "date": d, "url": u} for r, d, u in notes.get(t, [])])
        cut = pd.Timestamp(self.D.REVIEW_FROM)
        for half, when in (("why_entered", start),) + ((("why_exited", end),) if closed else ()):
            written = out["whys"].map(lambda ws, h=half: any(w["half"] == h for w in ws))
            out[f"{half}_owed"] = (~written) & (when >= cut)
        return out

    def theses_owed(self) -> list[dict]:
        """Every judgement owed today, open positions and closed ones together: one dict per
        missing half, {ticker, account, half, since}. Empty is the state the book is kept in."""
        held = self.with_reasoning(self.holdings(by="ticker"))
        trips = self.with_reasoning(self.round_trips(), opened="opened", closed="closed")
        owed = [{"ticker": r["ticker"], "account": None, "half": "why we entered",
                 "since": str(r["open_date"])[:10]}
                for r in held[held["why_entered_owed"]].to_dict("records")]
        for half, field, col in (("why we entered", "why_entered", "opened"),
                                 ("why we exited", "why_exited", "closed")):
            owed += [{"ticker": r["ticker"], "account": r["account"], "half": half,
                      "since": str(r[col])[:10]}
                     for r in trips[trips[f"{field}_owed"]].to_dict("records")]
        return owed

    # ---- ALLOCATION ------------------------------------------------------------------

    ALLOCATION_DIMENSIONS = ("currency", "region", "sector", "held_as")

    def allocation(self, by: str = "currency", account: str | None = None,
                   as_of: str | None = None) -> pd.DataFrame:
        """Exposure split by one dimension. Grouping is free once identity is a join.

        Columns: the dimension, `value`, `share` of the total, and `share_of_largest`, so a bar's
        width is a lookup rather than a renderer's division. `as_of` reads a FROZEN quarter end's
        composition (`quarter_lines()`) instead of today's marks, so the report's split adds to
        the exposure it publishes and it asks here rather than grouping for itself. A new cut is a
        parameter, not a tab.
        """
        if by not in self.ALLOCATION_DIMENSIONS:
            raise KeyError(f"{by!r} is not an allocation dimension; "
                           f"expected one of {self.ALLOCATION_DIMENSIONS}")
        h = self.quarter_lines(as_of) if as_of else self.holdings(account=account, by="ticker")
        out = h.groupby(by, as_index=False)["value"].sum()
        total = out["value"].sum()
        largest = out["value"].max()
        out["share"] = out["value"] / total if total else float("nan")
        out["share_of_largest"] = out["value"] / largest if largest else float("nan")
        return out.sort_values("value", ascending=False).reset_index(drop=True)

    # ---- ROUND TRIPS -----------------------------------------------------------------

    def round_trips(self, ticker: str | None = None, account: str | None = None,
                    start: str | None = None, end: str | None = None,
                    company: str | None = None) -> pd.DataFrame:
        """Closed round trips, per realisation. THE JOIN -- three tables, one key.

        Carries the ENTRY DATE and PRICE PAID as well as the exit, because those show the return
        on an investment; a position opened before the baseline and closed in 2026 is a complete
        round trip. Entry and exit prices are in the share's own currency (`currency`), each a
        quantity-weighted mean of its deals' own prices (`deal_prices()`); the money is sterling.
        `start` and `end` bound the day a trip closed, and `start` counts its day, as the Round
        Trips page's From asks.
        """
        ex = pd.DataFrame([{"eid": e.eid, "date": e.date, "account": e.acct,
                            "ticker": e.ticker, "qty": e.size, "price": e.price,
                            "proceeds": e.proceeds} for e in self.D.exits],
                          columns=["eid", "date", "account", "ticker", "qty", "price", "proceeds"])
        ex["realisation_id"] = ex["eid"].map(self.D.REALISATION_BY_EXIT)
        ex["cost_released"] = ex["eid"].map(self.cost_released)
        ex["date"] = pd.to_datetime(ex["date"])

        rt = (ex.groupby("realisation_id", as_index=False)
                .agg(ticker=("ticker", "first"), account=("account", "first"),
                     sells=("eid", "count"), closed=("date", "max"),
                     qty=("qty", "sum"), proceeds=("proceeds", "sum"),
                     cost=("cost_released", "sum")))

        # Entry date: a share realisation's is the day its holding opened (`share_pools()`), a
        # spread bet's the earliest leg its sales named. Falls back to the closed-position record,
        # which is where the pre-2026 entries are stated.
        L = self.ledger
        sold = L[L["direction"] == "Sell"].sort_values(["date", "id"])
        legs = L[(L["direction"] == "Buy") & L["realisation_id"].notna()]
        rt["opened"] = _lookup(rt["realisation_id"],
                               sold.groupby("realisation_id")["pool_opened"].min())
        rt["opened"] = rt["opened"].fillna(
            _lookup(rt["realisation_id"], legs.groupby("realisation_id")["date"].min()))
        closed_open = {c.realisation: pd.Timestamp(c.open_date) for c in self.D.closed}
        rt["opened"] = rt["opened"].fillna(rt["realisation_id"].map(closed_open))

        rt["held_days"] = (rt["closed"] - rt["opened"]).dt.days

        # EVERY ROUND TRIP IS NAMED ALIKE: its company from identity, its kind from its sales. The
        # note comes from the `closed` record where it has the realisation's row — every one
        # realised before 1 Oct 2026 — and from a later one's latest sale, whose note says what
        # happened.
        meta = {c.realisation: c for c in self.D.closed}
        company_of = self._identity().set_index("code")["company"]
        kind = sold.groupby("realisation_id")["held_as"].first()
        last_note = sold.groupby("realisation_id")["note"].last()
        rt["company"] = rt["ticker"].map(company_of)
        rt["held_as"] = rt["realisation_id"].map(kind)
        rt["note"] = [meta[r].note if r in meta else last_note.get(r)
                      for r in rt["realisation_id"]]
        # CLOSED OUT versus a PARTIAL TRIM — two different populations, and the book keeps
        # them apart deliberately: the realised total spans both, while trade counts and
        # holding-period statistics cover closed-out round trips only. A trim is a parcel out
        # of a position you still hold. JUDGED PER HOLDING, one account's line, which is what a
        # realisation is (rules.REALISATION_FORM): a line sold out of one account and still held
        # in another is closed out there.
        held = {(r.acct, r.ticker) for r in L[L["open_leg"]].itertuples(index=False)}
        rt["fully_closed"] = [(a, t) not in held for a, t in zip(rt["account"], rt["ticker"])]
        # ENTRY AND EXIT PRICE, IN THE SHARE'S OWN CURRENCY: a quantity-weighted
        # mean of the deals' own prices — the sales' for
        # the exit; for the entry the buys the realisation consumed, or, for a trim of a pool
        # still held, that holding's open buys up to its last sale, whose average it released.
        # Blank when any of them has no price on file, rather than a mean of the ones that do.
        own = self.deal_prices()["price_own"]
        buys = L[L["direction"] == "Buy"]

        def _mean(deals):
            p = deals["id"].map(own)
            if deals.empty or p.isna().any() or not deals["qty"].sum():
                return float("nan")
            return float((p * deals["qty"]).sum() / deals["qty"].sum())

        entry, exit_ = {}, {}
        for r in rt.to_dict("records"):
            rid = r["realisation_id"]
            exit_[rid] = _mean(sold[sold["realisation_id"] == rid])
            mine = buys[buys["realisation_id"] == rid]
            if mine.empty:
                mine = buys[buys["open_leg"] & (buys["acct"] == r["account"])
                            & (buys["ticker"] == r["ticker"]) & (buys["date"] <= r["closed"])]
            entry[rid] = _mean(mine)
        rt["entry_price"] = rt["realisation_id"].map(entry)
        rt["exit_price"] = rt["realisation_id"].map(exit_)
        # A SPREAD BET IN ITS OWN TERMS, as Trades reads one: its stake per point, its entry and
        # exit as levels in points, and sterling for a currency. Blank on a share.
        is_sb = rt["held_as"].eq("spread bet")
        rt["currency"] = rt["ticker"].map(
            self._identity().set_index("code")["currency"]).where(~is_sb, "GBP")
        rt["stake_per_point"] = rt["qty"].where(is_sb)
        rt["entry_level_points"] = rt["entry_price"].where(is_sb).round(2)
        rt["exit_level_points"] = rt["exit_price"].where(is_sb).round(2)
        rt["gain"] = rt["proceeds"] - rt["cost"]
        rt["gain_pct"] = rt["gain"] / rt["cost"]
        rt["pre_baseline"] = rt["opened"] < self.baseline
        # BY EXIT DATE, MOST RECENT FIRST — a realisation log reads what happened lately first —
        # with a stable tie-break on the realisation id, as activity() uses: several realisations
        # share an exit date, and an unstable order would reshuffle rows with nothing changed.
        # Sorted here, once, for every renderer. SELECTION lives here too: `closed` is the EXIT
        # date, the date a round trip is filed under.
        if ticker:
            rt = rt[rt["ticker"] == ticker]
        # A COMPANY IS EVERY CODE IT IS HELD UNDER, shares and spread bets both (14 Oct 2026):
        # how Stormvik has gone for us is its share's round trips and its spread bet's together.
        if company:
            rt = rt[rt["company"] == company]
        if account:
            rt = rt[rt["account"] == account]
        if start:
            rt = rt[rt["closed"] >= pd.Timestamp(start)]
        if end:
            rt = rt[rt["closed"] <= pd.Timestamp(end)]
        return (rt.sort_values(["closed", "realisation_id"], ascending=False)
                  .reset_index(drop=True))

    def round_trip_totals(self, ticker: str | None = None, account: str | None = None,
                          start: str | None = None, end: str | None = None,
                          company: str | None = None) -> dict[str, float]:
        """Totals over every realisation, or over a selection of them.

        `gain` here and realised() are one figure reached two ways — per realisation, and over the
        raw exits — and if they part company the apportionment is wrong. That identity holds for
        the UNFILTERED call. A renderer narrowing by account asks here rather than summing its own
        rows.
        """
        rt = self.round_trips(ticker=ticker, account=account, start=start, end=end, company=company)
        return {"realisations": int(len(rt)),
                # CLOSED OUT, the Dashboard's count, so the two pages read one population.
                "closed_out": int(rt["fully_closed"].sum()),
                "sells": int(rt["sells"].sum()),
                "quantity": float(rt["qty"].sum()),
                "proceeds": round(float(rt["proceeds"].sum()), 2),
                "cost": round(float(rt["cost"].sum()), 2),
                "gain": round(float(rt["gain"].sum()), 2)}

    def parcel(self, account: str, ticker: str) -> str:
        """The realisation a sale from this holding is filed under — THE ONE ANSWER, which the
        bench asks when it fills a sale, the IG sweep asks when it proposes a close, and
        `share_pools()` holds on load.

        A HOLDING IS ONE ACCOUNT'S, share or spread bet alike. The parcel it already has, when a
        sale from it is on file and the holding has not emptied since: a share's pool, a spread
        bet's legs opened by that sale and still open. Otherwise a new one: `R-` and the root the
        ticker's realisations already use (R-ABC for ABC.L, or whatever its first holding was
        named), numbered on when another holding has the name — a share may sit in several
        accounts, two spread-bet accounts may bet on the same ticker, and a holding sold out and
        bought again is a new holding. Named by ticker alone, one account's close would be filed
        under another account's round trip.
        """
        L = self.ledger
        sold = L[(L["direction"] == "Sell") & (L["ticker"] == ticker)]
        if any(t.ticker == ticker and t.mode == "sb" for t in self.D.trades):
            mine = sold[sold["acct"] == account].sort_values("date")
            if not mine.empty:
                last = mine.iloc[-1]
                held = L[(L["direction"] == "Buy") & (L["acct"] == account)
                         & (L["ticker"] == ticker) & L["open_leg"] & (L["date"] <= last["date"])]
                if not held.empty:
                    return str(last["realisation_id"])
        else:
            mine = sold[(sold["held_as"] == "shares") & (sold["acct"] == account)
                        & sold["pool_emptied"].isna()]
            if not mine.empty:
                return str(mine["realisation_id"].iloc[0])
        named = sorted({head if tail.isdigit() and head else str(r)
                        for r in sold["realisation_id"].dropna()
                        for head, _, tail in [str(r).rpartition("-")]})
        root = named[0] if named else (
            "R-" + "".join(c for c in ticker.split(".")[0].upper() if c.isalnum()))
        taken = set(self.D.REALISATION_BY_EXIT.values())
        name, n = root, 1
        while name in taken:
            n += 1
            name = f"{root}-{n}"
        return name

    # ---- INVESTMENT ACTIVITY ---------------------------------------------------------

    def deal_prices(self) -> pd.DataFrame:
        """EACH DEAL'S PRICE IN ITS SHARE'S OWN CURRENCY, and the rate it stands at, by ledger
        id: `price_own`, `rate`, and `rate_from` — whose rate it is, the broker firm's or a
        TradingView close.

        THE PRICE ON FILE is the deal document's own, in `cur`:
          · in the share's own currency     that price, beside the broker's rate where stated
          · in sterling, on a foreign share that price at the deal day's TradingView close —
                                            HL prices a deal in pence whatever the share
          · stated by no document on file   a London share's cost per share; a foreign one blank
        A spread bet's is its level in points, at parity. A rate is never worked out from a deal:
        its sterling carries the dealing charge. A deal day's close the record lacks leaves
        the price blank, and `rate_gaps()` names the date. Side effects: none.
        """
        currency = self._identity().set_index("code")["currency"]
        reg = self.account_register()
        firm = dict(zip(reg["account"], reg["broker"]))
        out = {}
        for r in self.ledger.to_dict("records"):
            own, rate, whose = None, None, None
            if r["held_as"] == "spread bet":
                own = r["val"] if r["direction"] == "Buy" else r["price"]
            else:
                share = currency.get(r["ticker"], "GBP")
                if pd.notna(r["price"]) and r["cur"] == share:
                    own = r["price"]
                    if pd.notna(r["rate"]):
                        rate, whose = r["rate"], firm.get(r["acct"])
                elif pd.notna(r["price"]):
                    day, close = self._close_on(share, r["date"])
                    if day == r["date"].date().isoformat():
                        own, rate, whose = r["price"] * close, close, "TradingView close"
                elif share == "GBP" and r["direction"] == "Buy" and r["qty"]:
                    own = r["val"] / r["qty"]
            out[r["id"]] = (own, rate, whose)
        return pd.DataFrame.from_dict(out, orient="index",
                                      columns=["price_own", "rate", "rate_from"]).astype(
            {"price_own": float, "rate": float})

    def activity(self, start=None, end=None, account: str | None = None) -> pd.DataFrame:
        """Buys and sells in a window, most recent first. `start` COUNTS ITS DAY: it is a reader's
        From date on the desk's Trades, where the engine's own periods start after it (`_window()`).

        A POOL'S RELEASE IS NOT ACTIVITY. It is derived from the sale itself (`share_pools()`):
        reporting it as investment activity would invent a trade.

        A CORPORATE ACTION READS AS AN ADJUSTMENT. A split or consolidation is a share row of nil
        cost that moves the quantity alone (`share_pools()` walks it as a buy of nothing), so
        calling it a Buy would say money went in. The label is the Trades view's: the ledger
        keeps it a buy, and every figure reads it as one.
        """
        L = self.ledger
        L = L[L["direction"].isin(("Buy", "Sell"))]
        if account is not None:
            L = L[L["acct"] == account]
        if start is not None:
            L = L[L["date"] >= pd.Timestamp(start)]
        if end is not None:
            L = L[L["date"] <= pd.Timestamp(end)]
        out = L[["date", "id", "direction", "acct", "ticker", "qty", "stake",
                 "val", "realisation_id", "broker_ref", "held_as",
                 "source", "note", "contract"]].copy()
        out = out.rename(columns={"id": "trade_id", "acct": "account", "val": "value"})
        out.loc[out["direction"].eq("Buy") & out["held_as"].eq("shares") & out["value"].eq(0),
                "direction"] = "Adjustment"
        # A BET LEG'S CONTRACT AND HOW IG FUNDS IT (schema.FUNDINGS): blank on a share and on a
        # sale, which names its leg instead.
        out["funding"] = out["contract"].map(self.D.CONTRACT_FUNDING)
        # WHAT A SALE REALISED, on the sale's own row: its GBP proceeds less the cost it released
        # (`cost_released`). Blank on a buy. Two legs closed at one price read alike without it.
        out["realised"] = (out["value"] - out["trade_id"].map(self.cost_released)) \
            .where(out["direction"] == "Sell")
        # On a sell row `val` carries GBP proceeds; on a buy it is the settled cost, or the
        # entry LEVEL for a spread bet. Reconstruct the money so one column means one thing.
        sb = out["trade_id"].isin({t.id for t in self.D.trades if t.mode == "sb"})
        out.loc[sb & (out["direction"] == "Buy"), "value"] *= out.loc[
            sb & (out["direction"] == "Buy"), "qty"]

        # THE TRADED PRICE, in the share's own currency, and the rate it stands at with whose it
        # is (`deal_prices()`): the deal's own price, never one worked out from its sterling.
        # Blank where no document on file states one, and FX at trade blank on a sterling deal in
        # a London share, which needed no rate. A SPREAD BET TRADES AT PARITY whatever the
        # underlying's currency: its price is its level, and its currency sterling.
        deal = self.deal_prices()
        out["currency"] = out["ticker"].map(self._identity().set_index("code")["currency"]) \
            .where(out["held_as"].ne("spread bet"), "GBP")
        out["traded_price"] = out["trade_id"].map(deal["price_own"])
        out["fx_at_trade"] = out["trade_id"].map(deal["rate"])
        out["fx_from"] = out["trade_id"].map(deal["rate_from"])

        # A SPREAD BET IN ITS OWN TERMS: a stake per point, at a level in points, as the record
        # keeps them — the ledger's qty on a bet is its stake, and its prices are levels. Blank
        # on a share.
        is_sb = out["held_as"].eq("spread bet")
        out["stake_per_point"] = out["qty"].where(is_sb)
        out["level_points"] = out["traded_price"].where(is_sb).round(2)
        # NEWEST FIRST, then trade id: the event-log rule test_trades_are_newest_first_with_a_stable_tie_break holds,
        # with a stable tie-break so rows sharing a date cannot reorder between builds.
        return (out.sort_values(["date", "trade_id"], ascending=[False, False])
                   .reset_index(drop=True))

    # ---- THE REGISTER  —  who holds what, named as filed -----------------------------

    @staticmethod
    def account_order() -> list[str]:
        """Every account in the record's canonical order — shares first, then spread bets.

        An order, not a sort: the break separates the two valuation bases, and alphabetically a
        spread-bet account lands among the share ones.
        """
        return list(D.ACCOUNT_ORDER)

    #: Words in a holder's name that do not name them, kept when a holder is taken out.
    HOLDER_TITLES = frozenset({"Mr", "Mrs", "Ms", "Miss", "Mx", "Dr"})

    def account_register(self) -> pd.DataFrame:
        """The account register as filed, with `holder_names`: the words of each holder's name
        that name them, titles off. THE OWNER'S: holders and numbers are in it, and anything read
        by anyone else names an account by `account_codes()`."""
        reg = pd.DataFrame(self.D.register, columns=self.D.schema.TABLES["accounts"].header)
        reg["holder_names"] = [tuple(w for w in str(h).split() if w not in self.HOLDER_TITLES)
                               for h in reg["holder"]]
        return reg

    def account_codes(self) -> pd.DataFrame:
        """Each account as it is named to anyone but the owner (decided 6 Oct 2026): its register
        code, and a `label` that is the code beside the account's name with the holder taken out,
        `A3 · IG Spread bet`. Columns account, code, label; one row per account, in
        ACCOUNT_ORDER."""
        reg = self.account_register().set_index("account").loc[list(self.D.ACCOUNT_ORDER)]
        rest = [" ".join(w for w in a.split() if w not in names)
                for a, names in zip(reg.index, reg["holder_names"])]
        return pd.DataFrame({"account": reg.index, "code": reg["code"].to_numpy(),
                             "label": [f"{c} · {r}" if r else c
                                       for c, r in zip(reg["code"], rest)]})

    # ---- ACCOUNT LEVEL  —  every metric, per account, rolling up to a parent total ---

    #
    # Ask once, get it per account and the parent total from the same numbers, so the two cannot
    # disagree. The valuation rule is per ACCOUNT KIND:
    #
    #   share account       nav = positions at market — CASH IS NEVER IN NAV
    #   spread-bet account  nav = ACCOUNT EQUITY — capital in, plus what trading did to it
    #
    # `exposure` is a different question: a spread-bet account's exposure is its NOTIONAL, not its
    # contribution to NAV. Both columns are on the frame; roll_up() stops them being added.
    def is_spread_bet(self, account: str) -> bool:
        """Whether an account is a spread-bet one, and therefore on the exposure basis.

        THE ONE IMPLEMENTATION of the most consequential classification in the book — whether a
        figure is money or notional. The register's `kind` says, for the record this Book was
        built from; never test an account's name.
        """
        return self.D.ACCOUNT_KIND.get(account) == "spread bet"

    #: WHAT A RETURN MEANS WHEN ITS PERIOD OPENED ON NOTHING, stated once for every renderer. With
    #: no opening balance the denominator is the flows alone, each weighted by the days it was in
    #: the period — so money put in late in a period makes a small gain or loss read large.
    #: `opened_in_period` flags the rows it applies to, in `by_account()` and
    #: `account_quarter_returns()`; test_engine_ties.py holds every return to the arithmetic.
    OPENED_IN_PERIOD = ("Opened on a zero balance in the period, so the return is the gain or "
                        "loss on the money put in, each flow weighted by the days it was in.")

    def ytd_year(self, as_of: str | None = None) -> int:
        """The year the year-to-date figures are of: `as_of`'s, or for the live book the newer of
        `valued_at()`'s and its newest dated row's. THE NEWEST MARK, NOT THE CALENDAR: on
        1 January a book still valued at 31 December goes on showing that year, and rolls at the
        first price of the new one, OR AT ITS FIRST ROW if that comes sooner.
        The year's terms run to now, so a new year's row would otherwise be counted under notes
        naming the old one."""
        if as_of is not None:
            return int(str(as_of)[:4])
        rows = [d.max().year for d in (self.ledger["date"], self.store["movements"]["date"],
                                       self.store["income"]["date"]) if d.notna().any()]
        return max([int(str(self.valued_at())[:4]), *rows])

    def ytd_opens(self, as_of: str | None = None) -> str:
        """The 31 December the year-to-date figures measure from, as a store key."""
        return f"{self.ytd_year(as_of) - 1}-12-31"

    def ytd_window(self) -> dict:
        """What the live year-to-date figures measure, for a page to state: `year`, the 31 December
        they open at (`opens`), and whether that day's net asset value is `frozen` on file.

        Until it is, every year-to-date figure is BLANK (`by_account()`), and `frozen` is the
        reason a page gives — the newest mark alone cannot say which year a "YTD" is of, because
        `ytd_year()` rolls at a new year's first row as well as its first price.
        """
        opens = self.ytd_opens()
        return {"year": self.ytd_year(), "opens": opens,
                "frozen": opens in self.quarter_nav_total().index}

    def by_account(self, as_of: str | None = None, window: int | None = None) -> pd.DataFrame:
        """Every headline metric, per account, in the canonical account order.

        `as_of` answers the same questions at a PAST date, so a reconciliation can pin the book's
        side to the instant the broker's figure was struck; the difference is only in the
        INPUTS (holdings at that date's marks, exits, income and deployments up to it).
        `as_of=None` is the live book. `window` is `_marks_at()`'s, for a quarter end being frozen.

        Columns, and the basis each one is measured on (see MEASURE_BASIS):
          exposure          NOTIONAL  market exposure now — SB accounts at contract value
          opening_capital   money     NAV at `ytd_opens()`, from QUARTER_NAV; BLANK until that
                                      quarter end is frozen
          capital_deployed  money     the year's money INTO POSITIONS — purchases less sale
                                      proceeds for shares, funds for spread bets. NOT cash
                                      across the boundary; see capital_deployed()
          capital_employed  money     opening + deployed
          return_income     money     the return's income term, each row counted once:
                                      see return_income()
          nav               money     net asset value now
          capital_growth    money     nav − capital_employed: what the holdings did
          income            money     the year's dividends + interest − fees
          opened_in_period  —         the year opened on a zero balance: OPENED_IN_PERIOD
          ytd               —         the day-weighted return on money: `_dietz_row()`

        THE YEAR ROLLS AND THE BALANCE DOES NOT. Every column but `exposure` and `nav` is the
        year's, from `ytd_opens()`. A spread-bet account's `nav` is built from the baseline.
        """
        L = self.ledger
        order = list(self.D.ACCOUNT_ORDER)

        def per_account(series) -> pd.Series:
            return series.reindex(order).fillna(0.0).astype(float)

        # WHICH EXITS HAD HAPPENED. Unbounded for the live book; bounded by date for a dated
        # one, because a sale made after `as_of` had realised nothing at `as_of`.
        exits = [e for e in self.D.exits
                 if as_of is None or str(e.date)[:10] <= str(as_of)[:10]]

        # Market value of what the account holds, and the cost of the legs still open; SB accounts
        # land at NOTIONAL. At a date both come from `holdings_at()`, at that day's marks, and an
        # account the dated view cannot value is left absent rather than guessed at zero. A pooled
        # disposal's cost is already off both: the live ledger costs a share sale at minus what it
        # released, and as_of() nets each sale's release on its day — trap 3.
        if as_of is None:
            exposure = per_account(L.groupby("acct")["gbp_value"].sum())
            open_cost = per_account(L.groupby("acct")["gbp_cost"].sum())
        else:
            vals, costs = {}, {}
            for a in order:
                try:
                    h = self.holdings_at(as_of, a, window=window)
                except (KeyError, ValueError):
                    continue
                vals[a], costs[a] = float(h["value"].sum()), float(h["cost"].sum())
            # BLANK, NOT ZERO, for an account the day's marks cannot value: `per_account()` would
            # fill it with 0.0, and its net asset value would read as nothing. A blank carries
            # through every sum it reaches.
            exposure = pd.Series(vals, dtype="float64").reindex(order)
            open_cost = pd.Series(costs, dtype="float64").reindex(order)

        unrealised = exposure - open_cost

        is_sb = pd.Series({a: self.is_spread_bet(a) for a in order})
        # A spread-bet account's net asset value is its EQUITY: the money put in, plus
        # what trading has done to it. Never its notional — the gap between those two
        # numbers is the most expensive mistake available against this record.
        #
        # FROM THE self.baseline, WHATEVER THE YEAR. Realised and unrealised are everything since the
        # baseline, so an opening a year later would count that year's gains twice.
        # The terms add in this order because a float sum is not associative: an account on a
        # half-penny shows a penny lower when income is added to the capital first.
        #
        # WHAT THE self.baseline EQUITY ALREADY HOLDS IS NOT COUNTED AGAIN. It is the account's worth on
        # the baseline day, a sale made before then and a leg's gain up to then inside it. So the
        # realised term takes only the sales after the baseline, and the unrealised term only the
        # move since: a leg open on the baseline is measured from its mark that day, not from its
        # entry.
        at_baseline = self.quarter_nav_rows(self.baseline_asof).set_index("account")["amount"]
        employed_since = (per_account(at_baseline)
                          + per_account(self.capital_deployed(start=self.baseline_asof, end=as_of)))
        income_since = per_account(self.income_by_account(start=self.baseline_asof, end=as_of))
        after = [e for e in exits if str(e.date)[:10] > self.baseline_asof]
        by_after = [e.acct for e in after]
        realised_since = (per_account(pd.Series([e.proceeds for e in after], index=by_after,
                                                dtype=float).groupby(level=0).sum())
                          - per_account(pd.Series([self.cost_released[e.eid] for e in after],
                                                  index=by_after, dtype=float)
                                        .groupby(level=0).sum()))
        nav = exposure.where(~is_sb, employed_since + realised_since
                             + (unrealised - self._unrealised_at_baseline(order))
                             + income_since)

        # THE YEAR'S TERMS open at the previous 31 December's frozen net asset value. Before
        # that quarter end is frozen there is nothing to measure from, so the opening is BLANK —
        # never zero, which would read as every account opened in the year.
        opens = self.ytd_opens(as_of)
        opening = (per_account(self.quarter_nav_rows(opens).set_index("account")["amount"])
                   if opens in self.quarter_nav_total().index
                   else pd.Series(float("nan"), index=order))
        # MONEY INTO POSITIONS, not cash across the boundary: a share account's net asset value
        # holds no cash, so a withdrawal counted against it would read as a gain
        # (`_dated_flows()`).
        deployed = per_account(self.capital_deployed(start=opens, end=as_of))
        capital_employed = opening + deployed
        income = per_account(self.income_by_account(start=opens, end=as_of))
        # THE RETURN'S NUMERATOR TAKES ONLY WHAT THE CAPITAL EARNS, ONCE. `income` above stays
        # whole because the year's income is a true figure about the book; this is the return's.
        ret_income = per_account(self.return_income(start=opens, end=as_of))

        out = pd.DataFrame({
            "account": order,
            "held_as": ["spread bet" if is_sb[a] else "shares" for a in order],
            "exposure": exposure.values,
            "opening_capital": opening.values,
            "capital_deployed": deployed.values,
            "capital_employed": capital_employed.values,
            "nav": nav.values,
            "capital_growth": (nav - capital_employed).values,
            "return_income": ret_income.values,
            "income": income.values,
        })
        # THE ONE FORMULA, `_dietz_row()`, for the year as for a quarter: each flow weighted by
        # the days from its date to the newest mark, which is where the live figures stand.
        weighted = per_account(self.weighted_flows(start=opens, end=as_of or self.valued_at()))
        out["ytd"] = [self._dietz_row(bv, ev, cf, wcf, inc)["return"]
                      for bv, ev, cf, wcf, inc in zip(opening, nav, deployed, weighted, ret_income)]
        out["opened_in_period"] = (out["opening_capital"] == 0) & out["ytd"].notna()
        return out

    def totals(self) -> dict[str, float]:
        """The ALL ACCOUNTS row. Money measures only — exposure is asked for separately."""
        by = self.by_account()
        t = roll_up(by, "opening_capital", "capital_deployed", "capital_employed",
                    "nav", "capital_growth", "income", "return_income")
        # THE ONE FORMULA, as every account row: the year's flows weighted to the newest mark.
        weighted = float(self.weighted_flows(start=self.ytd_opens(), end=self.valued_at()).sum())
        t["ytd"] = self._dietz_row(t["opening_capital"], t["nav"], t["capital_deployed"],
                                   weighted, t["return_income"])["return"]
        return t

    def nav(self) -> float:
        """Net asset value. THIS IS MONEY — unlike total_exposure()."""
        return roll_up(self.by_account(), "nav")["nav"]

    # ---- MONEY IN AND OUT, AND INCOME  —  each bounded by one window, `_window()` ----

    def capital_movements(self, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        """Every capital movement as its own row, newest first, `date` a plain date.

        A log is scanned for what happened lately, so newest first here, while the store keeps
        the table ascending for hand-edits appended at the foot. `start` and `end` bound it, as
        every window is bounded (`_window()`).
        """
        out = self._window(self.store["movements"], start, end).copy()
        out = out.sort_values("date", ascending=False)
        out["date"] = out["date"].dt.date
        return out.reset_index(drop=True)

    @staticmethod
    def _window(frame: pd.DataFrame, start=None, end=None, year: int | None = None) -> pd.DataFrame:
        """`frame`'s rows dated in THE WINDOW, (start, end]: after `start`, up to and on `end`,
        and in `year` when one is given. Every period the engine measures is bounded here, so a
        row on a quarter end falls in the quarter it closes and never in the next. A bound left
        out is open. `activity()` and `round_trips()` take a reader's From date instead, which
        counts its day."""
        if year is not None:
            frame = frame[frame["date"].dt.year == year]
        if start is not None:
            frame = frame[frame["date"] > pd.Timestamp(start)]
        if end is not None:
            frame = frame[frame["date"] <= pd.Timestamp(end)]
        return frame

    def _dated_flows(self, start=None, end=None) -> pd.DataFrame:
        """Every flow into POSITIONS in the window, dated: columns account, date, amount.

        NAV for a share account excludes cash, so counting cash movements against it made a
        withdrawal read as gain and a sale as loss — errors that roughly cancel over a
        sale-then-withdraw cycle, which is why they went unseen. So a flow is a PURCHASE: buying
        with cash nets to zero, a price move is the whole gain, and a deposit or withdrawal touches
        nothing. Cash is still recorded, for the reconciliation; it does not reach the return.

        TWO RULES THAT ARE NOT INTERCHANGEABLE:

          SHARES      a purchase at its GBP cost and a sale at minus its proceeds, off the ledger
                      (`val` is the cost on a buy and the proceeds on a sell).
          SPREAD BETS the cash movements, UNCHANGED — funds are the money behind a bet, never
                      its entry notional, which is the size of an interest.

        `qty > 0` IS LOAD-BEARING: a share consolidation carries negative quantity and moves no
        money. The window is `_window()`'s. `capital_deployed()` sums these and `weighted_flows()`
        weights them by date; both read here, so the two cannot disagree about what a flow is.
        """
        L = self.ledger
        mv = self.store["movements"]
        is_sb = {a: self.is_spread_bet(a) for a in self.D.ACCOUNT_ORDER}
        buys = L[(L["direction"] == "Buy") & (L["qty"] > 0)]
        sells = L[L["direction"] == "Sell"]
        shares = pd.concat([
            pd.DataFrame({"account": buys["acct"], "date": buys["date"], "amount": buys["val"]}),
            pd.DataFrame({"account": sells["acct"], "date": sells["date"], "amount": -sells["val"]}),
        ])
        shares = shares[~shares["account"].map(is_sb).fillna(False).astype(bool)]
        funds = mv[mv["account"].map(is_sb).fillna(False).astype(bool)][["account", "date", "amount"]]
        out = self._window(pd.concat([shares, funds], ignore_index=True), start, end)
        return out.astype({"amount": float}).reset_index(drop=True)

    def capital_deployed(self, start=None, end=None) -> pd.Series:
        """Money committed to POSITIONS in the window, per account: the return's flow term, the
        sum of `_dated_flows()`."""
        order = list(self.D.ACCOUNT_ORDER)
        flows = self._dated_flows(start, end)
        return (flows.groupby("account")["amount"].sum()
                .reindex(order).fillna(0.0).astype(float).round(2))

    def weighted_flows(self, start, end) -> pd.Series:
        """The denominator's flow term, per account: each flow in (start, end] weighted by the
        share of the period after its date, (D − d) ÷ D, with D the period's days and d the
        flow's days from `start`. Money in on the day after the start weighs almost whole; money
        in on the last day weighs nothing. The live book passes `valued_at()` as `end`, where its
        figures stand. Zero when the period has no days or no flows."""
        order = list(self.D.ACCOUNT_ORDER)
        first, last = pd.Timestamp(start), pd.Timestamp(end)
        days = (last - first).days
        flows = self._dated_flows(start, end)
        if days <= 0 or flows.empty:
            return pd.Series(0.0, index=order)
        weight = ((last - flows["date"]).dt.days / days).clip(0.0, 1.0)
        return ((flows["amount"] * weight).groupby(flows["account"]).sum()
                .reindex(order).fillna(0.0).astype(float))

    def position_income(self, year: int | None = None, start=None, end=None) -> pd.Series:
        """The income the CAPITAL earns and costs, per account — the return's numerator term.

        Dividends and funding interest are the positions'; platform fees and idle-cash interest
        are the account's and stay out. The split is `rules.POSITION_INCOME`. `income_by_account()`
        still returns everything — only the return filters.
        """
        df = self._window(self.store["income"], start, end, year)
        df = df[df["category"].isin(self.D.POSITION_INCOME)]
        return df.groupby("account")["amount"].sum().round(2)

    def return_income(self, year: int | None = None, start=None, end=None) -> pd.Series:
        """The income a RETURN adds to the change in net asset value, per account, so that
        every income row reaches the return exactly once.

        A share account's net asset value is its positions, so the POSITION_INCOME it was paid
        went to cash the NAV does not hold, and is added here. A spread-bet account's is its
        EQUITY, which already holds every income row: its POSITION_INCOME is in the return once
        without help, and its ACCOUNT_INCOME is taken back out, as a share account's never goes
        in. Adding a spread-bet account's funding here as well counted it twice. Bounded by
        `_window()`; an account with no such row is absent.
        """
        df = self._window(self.store["income"], start, end, year)
        sb = df["account"].map(self.is_spread_bet).astype(bool)
        added = df[~sb & df["category"].isin(self.D.POSITION_INCOME)]
        removed = df[sb & df["category"].isin(self.D.ACCOUNT_INCOME)]
        return (added.groupby("account")["amount"].sum()
                .sub(removed.groupby("account")["amount"].sum(), fill_value=0.0).round(2))

    def income_summary(self, start: str | None = None, end: str | None = None,
                       year: int | None = None) -> pd.DataFrame:
        """Income and costs in a window: one row per account in ACCOUNT_ORDER and a closing
        "Total" row, one column per category — POSITION_INCOME's first, which reach the
        return, then ACCOUNT_INCOME's — and `total`. Bounded by `_window()`; `year` keeps that
        calendar year's rows, as `income_rows()` does.
        An account with none reads 0.00, never absent."""
        df = self._window(self.store["income"], start, end, year)
        cats = list(self.D.POSITION_INCOME) + list(self.D.ACCOUNT_INCOME)
        wide = (df.groupby(["account", "category"])["amount"].sum().unstack()
                  .reindex(index=list(self.D.ACCOUNT_ORDER), columns=cats).fillna(0.0))
        wide["total"] = wide[cats].sum(axis=1)
        wide.loc["Total"] = wide.sum()
        wide.index.name = "account"
        return wide.round(2).reset_index()

    def income_by_account(self, year: int | None = None, start=None,
                          end: str | None = None) -> pd.Series:
        """Income per account, dated after `start` and on or before `end`. The end is what
        `by_account(as_of=...)` needs to state an account's worth at a past date."""
        df = self._window(self.store["income"], start, end, year)
        return df.groupby("account")["amount"].sum().round(2)

    def income_rows(self, year: int | None = None) -> pd.DataFrame:
        """Every income and cost row, account then date, with `rate_date`: the day of the close a
        foreign row converts at (`_income_rates()`), blank on a sterling row and on one whose
        broker states its rate, which is that row's own conversion and no market's.

        COSTS ARE NEGATIVE and income positive, so one column sums to the book's income
        figure. NEWEST FIRST WITHIN AN ACCOUNT, as every log on the desk reads (14 Oct 2026); a
        broker's statement lists them the other way, one press of the Date heading off.
        """
        df = self.store["income"].copy()
        if year is not None:
            df = df[df["date"].dt.year == year]
        order = {a: i for i, a in enumerate(self.D.ACCOUNT_ORDER)}
        df["_o"] = df["account"].map(lambda a: order.get(a, 99))
        df = df.sort_values(["_o", "date"], ascending=[True, False], kind="stable").drop(columns="_o")
        df["rate_date"] = self._income_rates()["rate_date"].reindex(df.index)
        return df.reset_index(drop=True)

    def _close_on(self, currency: str, date) -> tuple[str | None, float | None]:
        """THE CLOSE A DATED CONVERSION TAKES: the newest live TradingView close of
        `currency` on or before `date`, as (its date, its rate), or (None, None) when none is on
        file. A close, never a live read: a dated figure has to come out the same next year."""
        fh = self.store["history.fx"]
        on = fh[(fh["currency"] == currency) & (fh["kind"] == "spot")
                & (fh["status"] == self.D.LIVE_MARK) & (fh["struck"] == "close")
                & (fh["date"].astype(str) <= pd.Timestamp(date).date().isoformat())]
        if on.empty:
            return None, None
        row = on.sort_values("date").iloc[-1]
        return str(row["date"]), float(row["rate"])

    def _income_rates(self) -> pd.DataFrame:
        """Each foreign income row's conversion, indexed as the income table: `rate`, the rate it
        converts at — the broker's where the row states one, else the day's close
        (`_close_on()`) — and `rate_date`, that close's date, blank for the broker's."""
        inc = self.store["income"]
        rows = inc[inc["currency"].fillna("").astype(str) != ""]
        out = []
        for i, r in rows.iterrows():
            if pd.notna(r["rate"]):
                out.append((i, float(r["rate"]), None))
            else:
                day, rate = self._close_on(r["currency"], r["date"])
                out.append((i, rate, day))
        return pd.DataFrame(out, columns=["i", "rate", "rate_date"]).set_index("i")

    def conversions(self) -> pd.DataFrame:
        """Every income row paid in a foreign currency, and how stale its rate was that day.

        Both a figure and its rate can be sourced while the row is still approximate, because
        the rate belongs to another date — no provenance flag can catch that. A row without the
        broker's rate takes the newest close ON OR BEFORE the event, as `_marks_at()` does for
        prices, and `rules.FX_RATE_AGE_LIMIT_DAYS` says how far back that may reach before
        someone looks. A broker's rate is the row's own conversion, and is never stale.

        Columns: date, account, detail, currency, local_amount, amount, rate, rate_date,
        days_apart, stale. Empty when no row is foreign.

        Side effects: none.
        """
        cols = ["date", "account", "detail", "currency", "local_amount", "amount",
                "rate", "rate_date", "days_apart", "stale"]
        conv = self._income_rates()
        if conv.empty:
            return pd.DataFrame(columns=cols)
        rows = self.store["income"].loc[conv.index].drop(columns="rate").join(conv)
        broker = self.store["income"].loc[conv.index, "rate"].notna()
        apart = [0 if b else ((pd.Timestamp(d) - pd.Timestamp(rd)).days if pd.notna(rd) else None)
                 for d, rd, b in zip(rows["date"], rows["rate_date"], broker)]
        limit = self.D.FX_RATE_AGE_LIMIT_DAYS
        # STALE FROM THE LIST, not from the column: beside a row with a rate, pandas stores a row
        # with none as NaN, which is not None and is not past the limit, so a missing rate read
        # as a fresh one and was never reported.
        rows["stale"] = [dd is None or dd > limit for dd in apart]
        rows["days_apart"] = pd.Series(apart, index=rows.index, dtype=object)
        return rows[cols].sort_values("days_apart", ascending=False).reset_index(drop=True)

    # ---- RECONCILIATION  —  the book against the brokers' statements -----------------

    def statements(self) -> pd.DataFrame:
        """Every broker statement reading, as loaded: one row per account per as_of date. Callers
        ask here rather than reading the file, so the file has one parser, not three."""
        return self.store["statements"].copy()

    def reconciliation(self) -> pd.DataFrame:
        """Each account against its statement: what the book says, what the broker said.

        THE DIFFERENCE COLUMN IS THE POINT: near zero means the book's own figures explain the
        account's movement; anything else is a question. `cash_at_recon` is the cash at the
        reading's own date, which a share reading's total rests on; an account's newest cash is
        `newest_cash()`, a different fact.
        """
        # THE BOOK'S OWN NUMBER FOR A SPREAD-BET ACCOUNT IS THE DERIVED ONE — capital in, plus
        # realised, unrealised and income — because that is the figure with something to prove.
        # Using the broker's equity here compares the statement with itself: a reconciliation that
        # cannot fail is a decoration.
        #
        # PINNED TO THE READING, NOT TO NOW: valued at the marks of the reading's own instant, so a
        # later sweep cannot move a verdict already struck. A difference that appears only at later
        # marks is the market, not the book.
        _nav_cache: dict[str, dict] = {}

        def _nav_at(day: str | None) -> dict:
            key = str(day)[:10] if day else ""
            if key not in _nav_cache:
                _nav_cache[key] = (self.by_account(key) if key else self.by_account()) \
                    .set_index("account")["nav"].to_dict()
            return _nav_cache[key]
        rows = []
        for a in self.D.ACCOUNT_ORDER:
            r = next((x for x in self.D.ac_rows if x.acct == a), None)
            if r is None:
                continue
            # TWO CHECKS, ONE PER KIND OF ACCOUNT. A SPREAD-BET ACCOUNT'S BOOK SIDE IS ITS
            # DERIVED EQUITY — never cells typed off the statement it is compared against, which
            # can only ever agree with it — valued at the reading's own instant and compared by
            # value. A SHARE ACCOUNT IS CHECKED ON UNITS at the door that
            # took its holdings document, so nothing is valued here: its verdict follows from the
            # evidence class, in `reconciliation_verdict()`.
            sb = self.is_spread_bet(a)
            if sb:
                comparable, why = self.comparability(a, r.as_of, r.evidence)
                book_total = _nav_at(r.as_of).get(a)
            else:
                comparable, why, book_total = None, "", None
            struck_on = str(r.as_of)[:10] if r.as_of else ""
            # A SHARE READING WHOSE DOCUMENT STATES NO CASH — ii's holdings export — holds its
            # stock alone, so its cash and its total are derived here from the account's newest
            # cash reading on or before the reading's date, and are never stored beside the stock.
            # Every other reading's cash is its own document's, of the reading's own date.
            # A SPREAD-BET READING IS IG'S FIVE FIGURES: its cash is the funds, its total the
            # equity. A share reading's are its document's cash and total.
            if sb:
                cash, cash_on, total = r.funds, struck_on if r.funds is not None else None, r.equity
            else:
                cash, cash_on, total = r.recon_cash, \
                    struck_on if r.recon_cash is not None else None, r.stmt_value
            if not self._reading_states_cash(r):
                held = self._cash_at_reading.get(a)
                cash = held.cash if held else None
                cash_on = held.as_of.isoformat() if held else None
                total = (round(r.positions + held.cash, 2)
                         if held and r.positions is not None else None)
            rows.append({
                "account": a,
                "positions": r.positions,
                "cash_at_recon": cash,
                "cash_at_recon_at": cash_on,
                "equity": r.equity,
                # IG'S OWN FIGURES on a spread-bet reading, under IG's names; None on a share.
                "funds": r.funds, "running_pl": r.running_pl, "deposit": r.deposit,
                "available": r.available,
                "book": book_total,
                "statement": total,
                "difference": (book_total - total)
                              if (total is not None and book_total is not None) else None,
                "as_of": r.asof,
                # The typed date the book's side is pinned to, beside the display string, so a
                # reader of this frame never parses the sentence back.
                "struck_on": struck_on,
                "at": r.at,
                # FOR AN IG READING: do the two sides describe the same market state, and why.
                # Measured here; CLASSIFIED by reconciliation_verdict().
                "comparable": comparable,
                "comparability": why,
                # THE EVIDENCE CLASS, so a reader of this frame can ask what KIND of figure the
                # broker side is without parsing `as_of`. `reconciliation_verdict()` takes this.
                "evidence": r.evidence,
            })
        return pd.DataFrame(rows, columns=[
            "account", "positions", "cash_at_recon", "cash_at_recon_at", "equity", "funds",
            "running_pl", "deposit", "available", "book", "statement", "difference", "as_of",
            "struck_on", "at", "comparable", "comparability", "evidence"])

    def _reading_states_cash(self, r) -> bool:
        """Whether an account reading's own document gives the account's cash: a spread-bet
        account's always does, and a share account's when its evidence class says so. ii's
        holdings export does not, and a cash figure beside one is not the document's."""
        return self.is_spread_bet(r.acct) or bool(
            self.D.states_cash(self.D.EVIDENCE_BY_KEY.get(r.evidence)))

    def newest_cash(self) -> pd.DataFrame:
        """Each account's newest cash on file and what it was read from: one row per account in
        ACCOUNT_ORDER — account, cash, as_of (ISO), and document, the evidence class's label —
        None throughout where the record holds none.

        FROM EITHER KIND OF READING. A cash reading (`cash_latest()`) is the record's own place
        for cash, but an account reading whose document states the cash holds as good a figure,
        and the feed's IG read writes only that kind, so an IG account's cash readings fall behind
        its account readings. The account reading's cash is taken only when it is NEWER than every
        cash reading.
        """
        rows = []
        for a in self.D.ACCOUNT_ORDER:
            o = self._cash_latest.get(a)
            best = (o.as_of, o.cash, o.evidence) if o else None
            r = next((x for x in self.D.ac_rows if x.acct == a), None)
            # A spread-bet reading's cash is its FUNDS, under IG's own name.
            stated = (r.funds if self.is_spread_bet(a) else r.recon_cash) if r is not None else None
            if (r is not None and stated is not None and r.as_of
                    and self._reading_states_cash(r) and (best is None or r.as_of > best[0])):
                best = (r.as_of, stated, r.evidence)
            ev = self.D.EVIDENCE_BY_KEY.get(best[2]) if best else None
            rows.append({"account": a, "cash": best[1] if best else None,
                         "as_of": best[0].isoformat() if best else None,
                         "document": ev.label if ev else None})
        # OBJECT, so None stays None (quarter_evidence() says why).
        return pd.DataFrame(rows, columns=["account", "cash", "as_of", "document"], dtype=object)

    def units_check(self, account: str, as_of: str,
                    broker_units: dict[str, float]) -> pd.DataFrame:
        """THE SHARE-ACCOUNT CHECK: each holding's units in the book at
        `as_of` against a broker's holdings export. Units are COUNTED, not valued, so the check
        is exact — no mark, no band, no time of day. A holding one side has and the other does
        not is a row with 0 on the empty side.

        Columns: ticker, book, broker, agrees. Side effects: none.
        """
        held = self.as_of(as_of, account)
        book = {str(t): float(q) for t, q in zip(held["ticker"], held["qty"]) if float(q)}
        rows = [{"ticker": t, "book": book.get(t, 0.0), "broker": float(broker_units.get(t, 0.0))}
                for t in sorted(set(book) | set(broker_units))]
        out = pd.DataFrame(rows, columns=["ticker", "book", "broker"])
        out["agrees"] = (out["book"] - out["broker"]).abs() < 1e-9
        return out

    def comparability(self, account: str, as_of, evidence) -> tuple[bool, str]:
        """Does a SPREAD-BET account's broker reading describe the SAME STATE OF THE MARKET as the
        book's side?

        An IG reading is an instant on the broker's server that cannot be fetched again, so it
        compares only against marks struck LIVE in the same pass — which `feeds/refresh.py`
        produces by fetching the levels and the equity in one visit. A band wide enough to absorb
        a session is wider than the errors a reconciliation exists to catch, so the test is
        comparability, not tolerance. A SHARE ACCOUNT IS NOT ASKED THIS: it
        is checked on units at the door, which a close does not move.

        A MARK THAT DOES NOT SAY WHICH INSTANT IT DESCRIBES COMPARES WITH NOTHING.

        Returns `(comparable, why)`, `why` in a reader's words, so a renderer never composes it.

        Side effects: none.
        """
        ev = self.D.EVIDENCE_BY_KEY.get(str(evidence or ""))
        if ev is None or ev.retrieval != "reading":
            return False, f"{evidence!r} is not a live reading, and only a reading is compared"
        day = str(as_of)[:10]
        try:
            held = self.holdings_at(day, account)
        except (KeyError, ValueError) as exc:
            return False, f"the book cannot be valued at {day} — {exc}"
        if held.empty:
            return False, f"the book holds nothing in this account at {day}"

        # BY MARK KEY, NOT BY HOLDING TICKER. A spread bet holds "HALV SB" and is priced from
        # "HALV-DEC26" and "HALV-MAR27"; looking the holding's own name up in the price history
        # finds nothing and reports every IG account as unable to say what it was struck at.
        struck = self._struck_at(day)
        keys = {k for (_tk, k) in self._held_by_mark_key(day, account)}
        kinds = {struck.get(k, "") for k in keys} or {""}
        newest = max(str(d)[:10] for d in held["priced_at"])
        stalest = min(str(d)[:10] for d in held["priced_at"])
        if "" in kinds:
            return False, "a mark on this account does not say which instant it describes"
        if kinds != {"live"}:
            return False, "a live read compares only with live marks, and these are closes"
        if not (stalest == newest == day):
            return False, (f"the equity was read on {day} and the marks are from "
                           f"{stalest if stalest == newest else stalest + ' to ' + newest}"
                           f" — not one pass")
        return True, "read in one pass"

    def _struck_at(self, as_of: str) -> dict:
        """What instant each live mark on or before a date was struck at — `close` or `live`.

        Beside `_marks_at()`, not inside it: four callers unpack that one's (date, price) tuples
        positionally.

        Side effects: none.
        """
        ph = self.store["history.prices"]
        out: dict[str, tuple] = {}
        for row in ph[(ph["date"] <= as_of) & (ph["status"] == self.D.LIVE_MARK)].itertuples():
            cur = out.get(row.ticker)
            if cur is None or row.date >= cur[0]:
                out[row.ticker] = (row.date, str(getattr(row, "struck", "") or ""))
        return {k: v[1] for k, v in out.items()}

    #
    # A VERDICT IS A CLASSIFICATION, and a renderer may not classify, so it sits here beside the
    # frame it judges. Sharing a constant stops a band drifting between readers; sharing the
    # function stops the LOGIC drifting, and the logic is the part with branches.
    @staticmethod
    def reconciliation_verdict(statement: float | None, difference: float | None,
                               evidence: str | None, comparable: bool | None = None,
                               why: str = "") -> dict:
        """Whether one reconciliation row ties, and on which of the rules.

        TWO CHECKS, ONE PER KIND OF ACCOUNT, told apart by the evidence class
        (`rules.EVIDENCE_BY_KEY`):

          a READING (an IG account)  its equity against the book's, struck in one pass, held to
                                     `rules.RECON_LIVE_TOLERANCE_PCT` — the DERIVATION band: FX,
                                     rounding, bid against last. Not struck in one pass, it is
                                     not judged but reported as a gap.
          a HOLDINGS EXPORT          a share account, checked on UNITS at the door that took it.
                                     A reading on file means they agreed,
                                     and the audit re-reads the document. No value is compared.
          anything else              lists no units, so a gap, owed an export.

        AN ACCOUNT WITH NO STATEMENT IS NEITHER A PASS NOR A FAILURE; "ties" would be the worst
        answer available.

        Returns {checkable, live, band, ties, verdict, rule}. `verdict` is one of:
          "no-statement"  nothing to check against — a GAP
          "no-holdings"   a share account whose reading lists no units — a GAP
          "units-agree"   a share account whose holdings export agreed on units
          "struck-apart"  an IG reading not struck in one pass with the marks — a GAP
          "within-band"   an IG pair inside the derivation band
          "differs"       past the band. A difference is a defect until explained.

        `rule` is the verdict in a reader's words, here so every renderer says it the same way.
        It carries no date: agreement is of the reading's day, and a page heads that day itself,
        with the document behind it (`quarter_evidence()`).

        Side effects: none.
        """
        missing = statement is None or (isinstance(statement, float) and statement != statement)
        if missing:
            return {"checkable": False, "live": False, "band": None, "ties": None,
                    "verdict": "no-statement", "rule": "nothing to check against"}
        ev = D.EVIDENCE_BY_KEY.get(str(evidence or ""))
        if ev is None or ev.retrieval != "reading":
            if ev is not None and ev.key in D.HOLDINGS_COLUMNS:
                return {"checkable": True, "live": False, "band": None, "ties": True,
                        "verdict": "units-agree",
                        "rule": "units agree with the broker's holdings"}
            return {"checkable": False, "live": False, "band": None, "ties": None,
                    "verdict": "no-holdings",
                    "rule": f"{ev.label if ev else evidence} lists no units — a holdings export "
                            f"is owed"}
        if comparable is False:
            return {"checkable": False, "live": True, "band": None, "ties": None,
                    "verdict": "struck-apart",
                    "rule": why or "the equity and the marks were not read in one pass"}
        band = abs(statement) * D.RECON_LIVE_TOLERANCE_PCT
        ties = abs(difference or 0) < band
        return {"checkable": True, "live": True, "band": band, "ties": ties,
                "verdict": "within-band" if ties else "differs",
                "rule": f"{why or 'live read'} — band {band:,.2f}"}

    def quarter_readings(self, quarter_end: str | None, latest: bool = False,
                         checks: bool = False) -> pd.DataFrame:
        """Each account's broker reading that checks a quarter end: its FIRST dated from the
        quarter end to `rules.CLOSE_CHECK_WINDOW_DAYS` after it. One row per account that has
        one, in `statements()`'s shape.

        The quarter is valued at its own closes whenever they were banked; this is the broker's
        side, which may follow. A reading before the quarter end describes a different book and
        does not count.

        `latest=True` asks a different question: each account's NEWEST reading up to the end of
        that window, whenever it fell — the last check a report can cite. A share account is
        checked on units at any hour, so a check before the quarter end
        still stands. Bounded by the window, so the page regenerates the same once it has passed.
        With no `quarter_end`, it is each account's newest reading, unbounded: what the desk's
        Reconcile compares.

        `checks=True` keeps A BROKER'S CHECKS ALONE: a reading whose source names an evidence
        class. The history also copies the record's own figures where no freeze wrote them — the
        engine's derivation, an account not yet funded — and those check nothing.
        """
        st = self.statements()
        if checks:
            st = st[st["source"].map(lambda s: self.D.evidence_from_source(str(s)) is not None)]
        if quarter_end is None:
            return (st.sort_values("as_of").groupby("account", sort=False).tail(1)
                    .reset_index(drop=True))
        end = pd.Timestamp(quarter_end)
        day = pd.to_datetime(st["as_of"])
        until = end + pd.Timedelta(days=self.D.CLOSE_CHECK_WINDOW_DAYS)
        if latest:
            return (st[day <= until].sort_values("as_of").groupby("account", sort=False).tail(1)
                    .reset_index(drop=True))
        inside = st[(day >= end) & (day <= until)]
        return inside.sort_values("as_of").groupby("account", sort=False).head(1) \
                     .reset_index(drop=True)

    def quarter_evidence(self, quarter_end: str | None,
                         filed: list[str] | None = None) -> pd.DataFrame:
        """What each account's figure at a quarter end rests on: its last check, the kind of
        document behind it, and whether that document can be found again. One row per account,
        in ACCOUNT_ORDER — the three limbs of statement-grade, as a reader outside the repo meets
        them.

        The check is `quarter_readings(latest=True)`'s, and AT A QUARTER END ONLY A BROKER'S
        (`checks=True`): the newest reading whose source names an evidence class, so a page never
        cites the record's own figure as its check. `as_of` is None where there is none.
        `document` is its evidence class's label, None where the source names no class — which
        only the undated answer can give, since Reconcile shows the reading its row compares. `held`:

          "on file"                the cited document sits in `_archive/statements/`
          "NOT on file"            it cites one, and the archive does not hold it — whether
                                   the row says so (`not-on-file`) or not
          "read live"              A LIVE READ KEEPS NO DOCUMENT: nothing can be asked what the
                                   account was worth at that instant, and the row is the only
                                   copy
          "retrieved another way"  a classified source that cites no file
          None                     no classified source, or no check

        `filed` is the archive's names, so a test can say what is filed; None lists the folder.
        With no `quarter_end`, each account's newest reading: the reconciliation the desk shows.
        """
        if filed is None:
            filed = self.D.schema.filed_statements()
        at = self.quarter_readings(quarter_end, latest=True,
                                   checks=quarter_end is not None).set_index("account")
        rows = []
        for account in self.D.ACCOUNT_ORDER:
            if account not in at.index:
                rows.append({"account": account, "as_of": None, "document": None, "held": None})
                continue
            src = str(at.loc[account, "source"])
            ev = self.D.evidence_from_source(src)
            # THE ACCOUNT TOO: a line citing a dated statement and naming no account would
            # otherwise be "on file" on the strength of another account's statement.
            resolves = self.D.reference_resolves(src, filed, account=account)
            if ev and ev.retrieval == "none":
                ev, held = self.D.document_not_on_file(src) or ev, "NOT on file"
            elif resolves is not None:
                held = "on file" if resolves else "NOT on file"
            elif ev and ev.retrieval == "reading":
                held = "read live"
            else:
                held = "retrieved another way" if ev else None
            rows.append({"account": account, "as_of": str(at.loc[account, "as_of"]),
                         "document": ev.label if ev else None, "held": held})
        # OBJECT, so None stays None. pandas 3 infers its str dtype for a column of text and
        # None, and stores the None as NaN — which is truthy, so `document or ...` printed "nan".
        return pd.DataFrame(rows, columns=["account", "as_of", "document", "held"], dtype=object)

    # ---- THE QUARTER ENDS  —  what each one froze ------------------------------------

    def quarter_nav(self) -> pd.DataFrame:
        """Each account's NAV contribution at each 2026 quarter end: statement-grade where a
        statement exists, reconstructed where not. `quality` says which; `contribution` says how
        the account contributes."""
        return self.store["quarter_nav"].copy()

    #: Which contributions in quarter-nav.csv are MONEY, and may be summed into NAV. `notional` is
    #: deliberately absent: a blind sum would add exposure to net asset value the day a notional
    #: row arrived, and no test would know why the number moved.
    NAV_BASES = frozenset({"positions at market", "account equity"})

    EXPOSURE_BASES = frozenset({"positions at market", "notional"})

    #: The two names a caller may ask for, and the contribution set each one means. `nav` and
    #: `exposure` are MEASURES — which set of figures do you want — and `measure` is the word this
    #: engine pairs with `basis` in `MEASURE_BASIS` and `roll_up()` (glossary §2).
    MEASURE_SETS = {"nav": NAV_BASES, "exposure": EXPOSURE_BASES}

    def _classified(self) -> pd.DataFrame:
        """quarter-nav.csv, with every basis checked against the two sets above.

        The ONE place the table is validated. A basis nobody has classified must not be
        silently dropped OR silently summed; refusing is the only answer that cannot be
        quietly wrong.
        """
        q = self.quarter_nav()
        unknown = set(q["contribution"]) - self.NAV_BASES - self.EXPOSURE_BASES
        if unknown:
            raise ValueError(
                f"quarter-nav.csv carries contribution {sorted(unknown)}, which is in neither "
                f"NAV_BASES nor EXPOSURE_BASES. Classify it in engine.py before it can be "
                f"totalled — do not guess which side it belongs on.")
        return q

    def quarter_nav_rows(self, as_of: str, measure: str = "nav") -> pd.DataFrame:
        """Each account's contribution at ONE quarter end, on ONE stated measure.

        Columns: account, amount, contribution, quality, source — one row per account, in
        ACCOUNT_ORDER; `source` is what the figure was taken from, as the record words it.
        `measure` is "nav" (money) or "exposure" (NOT money) — WHICH SET OF FIGURES you want,
        which is a different question from what kind of number one is; `nav` and `exposure` are
        literally keys in `MEASURE_BASIS`.

        THE AMOUNT AND THE BASIS BESIDE IT COME FROM THE SAME SURVIVING ROWS, and that is
        the whole point of the method. An account can hold two rows at one date — one notional,
        one account equity — and an amount taken from one with the basis from the other prints a
        NAV figure under the exposure label, the one mistake this book says out loud it must
        never make.

        An account with no row on this basis gets 0.00 and "—", never a KeyError.
        """
        bases = self.MEASURE_SETS[measure]
        q = self._classified()
        rows = q[(q["as_of"] == as_of) & (q["contribution"].isin(bases))]

        def joined(s):
            return " + ".join(sorted(set(s)))

        out = (rows.groupby("account")
                   .agg(amount=("amount", "sum"), contribution=("contribution", joined),
                        quality=("quality", joined), source=("source", joined))
                   .reindex(self.D.ACCOUNT_ORDER))
        out["amount"] = out["amount"].fillna(0.0).round(2)
        out["contribution"] = out["contribution"].fillna("—")
        out["quality"] = out["quality"].fillna("—")
        out["source"] = out["source"].fillna("—")
        out.index.name = "account"
        return out.reset_index()

    def _quarter_quality(self, account: str, as_of: str) -> str:
        """How well evidenced this account's NAV contribution is at a quarter end.

        `sourced` means a statement or an authenticated read said so. `derived` means the figure
        stands in for one the record does not
        have, and a RETURN measured across it inherits that weakness without showing it.
        """
        q = self._classified()
        rows = q[(q["as_of"] == as_of) & (q["account"] == account)
                 & (q["contribution"].isin(self.NAV_BASES))]
        if rows.empty:
            return "missing"
        return str(rows.iloc[0]["quality"])

    def _quarter_observed(self, account: str, as_of: str) -> bool:
        """Did anyone OBSERVE this account at this quarter end? Sourced there, or a figure the
        engine froze at that day's closes and a SOURCED broker reading then checked within
        `rules.CLOSE_CHECK_WINDOW_DAYS` (`quarter_readings()`) — the flexible close, where the
        check follows the quarter by a few days. What the blank-return rule asks.
        """
        if self._quarter_quality(account, as_of) == "sourced":
            return True
        # THE READING MUST ITSELF BE AN OBSERVATION: a statement row carried back or
        # reconstructed confirms nothing, and would un-blank a closed quarter.
        r = self.quarter_readings(as_of)
        return bool(((r["account"] == account) & (r["quality"] == "sourced")).any())

    def _quarter_series(self, bases: frozenset[str], label: str) -> pd.Series:
        q = self._classified()
        out = q[q["contribution"].isin(bases)].groupby("as_of")["amount"].sum().round(2).sort_index()
        out.name = label
        return out

    def quarter_nav_total(self) -> pd.Series:
        """Net asset value at each quarter end. Indexed by date, in date order.

        MONEY. A spread-bet account contributes its ACCOUNT EQUITY here.
        """
        return self._quarter_series(self.NAV_BASES, "nav")

    def quarter_exposure_total(self) -> pd.Series:
        """Total market exposure at each quarter end. Indexed by date, in date order.

        NOT money, and never divide a return by it. A spread-bet account contributes its
        NOTIONAL here. It answers a different question from quarter_nav_total(), and keeping the
        two apart is the point.
        """
        return self._quarter_series(self.EXPOSURE_BASES, "exposure")

    def quarter_nav_by_account(self, measure: str = "nav") -> pd.DataFrame:
        """The quarter series broken out per account: dates down, accounts across.

        `measure` is "nav" (money) or "exposure" (NOT money), passed deliberately: two totals on
        one tab, one money and one exposure, with no heading saying which, differ with no stated
        reason. Naming it is the fix.
        """
        dates = sorted(self._classified()["as_of"].unique())
        wide = pd.DataFrame(
            {d: self.quarter_nav_rows(d, measure).set_index("account")["amount"]
             for d in dates}).T.reindex(columns=self.D.ACCOUNT_ORDER, fill_value=0.0)
        wide.index.name = "as_of"
        wide["TOTAL"] = wide.sum(axis=1).round(2)
        return wide.round(2).reset_index()

    @staticmethod
    def quarter_label(date: str) -> str:
        """A quarter-end date -> the quarter's NAME. "2026-06-30" -> "Q2 2026".

        DERIVED, NEVER TYPED: deriving the name here is what lets the quarter blocks key on
        identical values and be read across — typing "Q1 2026" in a second place is how they
        would drift apart.
        """
        d = pd.Timestamp(date)
        return f"Q{(d.month - 1) // 3 + 1} {d.year}"

    @staticmethod
    def quarter_start(quarter_end: str) -> str:
        """A quarter-end date -> the first day of that quarter. "2026-06-30" -> "2026-04-01".
        Derived, never typed: first-of-month arithmetic once put a March trade on a Q2 page."""
        d = pd.Timestamp(quarter_end)
        return f"{d.year}-{(d.month - 1) // 3 * 3 + 1:02d}-01"

    @staticmethod
    def quarter_to_close() -> pd.Timestamp:
        """The quarter end the next close is for: the first after the last one frozen.

        Derived from `rules.QSNAP_FROZEN`, so it moves on when a quarter is FROZEN, not when the
        calendar turns — a quarter that has ended unfrozen is still the one to close. With
        nothing frozen, the first quarter after the baseline.
        """
        last = max(D.QSNAP_FROZEN,
                   default=(record_begins() - pd.Timedelta(days=1)).date().isoformat())
        return pd.Timestamp(last) + pd.offsets.QuarterEnd(1)

    def quarter_lines(self, quarter_end: str) -> pd.DataFrame:
        """The FROZEN composition at a quarter end, one row per ticker across its accounts: what
        `store/quarter-snapshots.csv` holds for that date, so the values add to the exposure
        `quarter_exposure_total()` froze, not to a later revaluation of the same day.

        Columns: ticker, company, sector, region, currency, held_as (the code's kind, shares or
        spread bet),
        accounts, cost, value, gain (value less cost), weight (share of the lines' value). A
        spread bet's cost and value are notional (`rules.SPREAD_BET`). Sorted by company.
        KeyError if the date was never frozen.
        """
        at = [r for r in self.D.QSNAP_ROWS if r[0] == quarter_end]
        if not at:
            raise KeyError(f"{quarter_end} has no frozen composition")
        # An account frozen with nothing open carries one placeholder row with no quantity.
        held = [r for r in at if r[3] not in (None, "") and r[3] == r[3]]
        df = pd.DataFrame(held, columns=["as_of", "account", "ticker", "qty", "local_price",
                                         "currency", "value", "cost", "quality", "source"])
        order = list(self.D.ACCOUNT_ORDER)
        out = df.groupby("ticker", as_index=False).agg(
            value=("value", "sum"), cost=("cost", "sum"),
            accounts=("account", lambda s: " · ".join(a for a in order if a in set(s))))
        ident = self._identity().set_index("code")
        out["company"] = out["ticker"].map(ident["company"]).fillna(out["ticker"])
        out["sector"] = out["ticker"].map(ident["sector"])
        out["region"] = out["ticker"].map(ident["region"])
        out["currency"] = out["ticker"].map(ident["currency"])
        out["held_as"] = out["ticker"].map(ident["kind"])
        out["gain"] = out["value"] - out["cost"]
        out["weight"] = out["value"] / out["value"].sum()
        return (out.sort_values(["company", "ticker"]).reset_index(drop=True)
                   [["ticker", "company", "sector", "region", "currency", "held_as", "accounts",
                     "cost", "value", "gain", "weight"]])

    def quarter_lines_total(self, quarter_end: str) -> dict[str, float]:
        """The frozen composition's total row: the `cost`, `value` and `gain` of `quarter_lines()`,
        and the `gap`, how far that value falls short of the exposure frozen beside it. The gap is
        nothing, to the penny, where one valuation froze both — every quarter end the freeze wrote;
        a composition reconstructed by hand can be short a line. KeyError if never frozen."""
        lines = self.quarter_lines(quarter_end)
        value = float(lines["value"].sum())
        return {"cost": float(lines["cost"].sum()), "value": value,
                "gain": float(lines["gain"].sum()),
                "gap": round(float(self.quarter_exposure_total()[quarter_end]) - value, 2)}

    # ---- THE RETURNS  —  every period measured one way -------------------------------

    def quarter_returns(self, include_open: bool = False) -> pd.DataFrame:
        """One implementation of the quarter return, so nothing can quote the wrong one.

        MODIFIED DIETZ on net asset value, day-weighted: (EV − BV − CF + income) ÷ (BV + the
        flows each weighted by the share of the period after its date), `_dietz_row()`. A
        period whose opening NAV does not exist gets NO RETURN — never zero, which is a claim.
        A row is the `quarter`, the quarter end it `opens` at, its `quarter_end`, and
        `_dietz_row()`'s six figures. `opens` is not `quarter_start()`, the quarter's first day.
        """
        navs = self.quarter_nav_total()
        rows = []
        dates = list(navs.index)
        for prev, end in zip(dates, dates[1:]):
            rows.append({"quarter": self.quarter_label(end),
                         **self._dietz(prev, end, navs[prev], navs[end])})

        # THE QUARTER IN PROGRESS, when asked for: it ends at valued_at(), and its label says "to
        # date". Off by default, because the report must not see it — a quarterly report is about a
        # CLOSED quarter, and an open row would change every time the page was generated.
        if include_open and dates:
            prev = dates[-1]
            end = self.valued_at()
            if end > prev:
                rows.append({"quarter": f"{self.quarter_label(end)} to date",
                             **self._dietz(prev, end, navs[prev], self.nav())})
        return pd.DataFrame(rows, columns=["quarter", "opens", "quarter_end",
                                           *self.RESULT_FIGURES])

    #: What a closed quarter is held to, in `quarter-results.csv`'s order.
    RESULT_FIGURES = ("opening_nav", "capital_deployed", "return_income", "closing_nav", "gain",
                      "return")

    def quarter_results(self, as_of: str) -> list[dict]:
        """A closed quarter's six figures, the book's first and then each account's, as
        `quarter-results.csv` holds them: money to the penny, the return to six places, a figure
        with nothing to measure from blank. The freeze writes these, and `test_engine_ties.py`
        holds the engine to the newest row on file for each.

        KeyError if `as_of` is not the end of a closed quarter.
        """
        def held(account: str, row) -> dict:
            out = {"as_of": as_of, "account": account}
            for f in self.RESULT_FIGURES:
                out[f] = None if pd.isna(row[f]) else round(float(row[f]), 6 if f == "return" else 2)
            return out

        firm = self.quarter_returns()
        firm = firm[firm["quarter_end"].astype(str).str[:10] == as_of]
        if firm.empty:
            raise KeyError(f"{as_of} is not the end of a closed quarter")
        accounts = self.account_quarter_returns()
        accounts = accounts[accounts["quarter_end"].astype(str).str[:10] == as_of]
        return [held("", firm.iloc[0])] + [held(r["account"], r) for _, r in accounts.iterrows()]

    def account_quarter_returns(self, include_open: bool = False) -> pd.DataFrame:
        """The day-weighted return per account per quarter — every account, in ACCOUNT_ORDER.

        Each account's NAV CONTRIBUTION against the CAPITAL DEPLOYED into its positions: for a
        share account, positions at market against purchases less sales; for a spread-bet
        account, EQUITY against FUNDS (rules.SPREAD_BET). One basis, as the book-level block
        uses. Never notional against entry notional — a return on a number that never moved
        through the account.

        THE SAME NUMERATOR AS THE BOOK'S: the change in value, less the
        capital deployed, plus `return_income()`. Until then these counted no income at all, so
        a share account's dividends reached the book's return and never its own.

        `opened_in_period` marks a quarter that opened on nothing and still has a return, the
        case OPENED_IN_PERIOD describes.
        """
        wide = self.quarter_nav_by_account("nav").set_index("as_of")
        dates = list(wide.index)
        rows = []

        # THE OPEN QUARTER, when asked for: it ends at valued_at(), the newest mark, and its end
        # value is the account's NAV contribution at TODAY's marks.
        live = None
        if include_open and dates:
            end = self.valued_at()
            if end > dates[-1]:
                nav_now = self.by_account().set_index("account")["nav"]
                live = (dates[-1], end, nav_now)

        for account in self.D.ACCOUNT_ORDER:
            spans = list(zip(dates, dates[1:]))
            if live:
                spans.append(live[:2])
            for start, end in spans:
                is_open = live is not None and end == live[1]
                bv = float(wide.loc[start, account])
                ev = (float(live[2].get(account, float("nan"))) if is_open
                      else float(wide.loc[end, account]))
                cf = float(self.capital_deployed(start=start, end=end).get(account, 0.0))
                wcf = float(self.weighted_flows(start=start, end=end).get(account, 0.0))
                inc = float(self.return_income(start=start, end=end).get(account, 0.0))
                # NEITHER END SOURCED MEANS NOTHING ANYONE OBSERVED MOVED, so the quarter is BLANK
                # — never a flat 0.00%, which would read as "nothing moved" where the truth is "not
                # known". A SOURCED END AGAINST A DERIVED START IS STILL SHOWN: that P/L is real,
                # and the `quality` column says what it rests on. The open quarter's end is today's
                # marks, which no reading has sourced, so there the start alone decides.
                blank = (self.is_spread_bet(account)
                         and not self._quarter_observed(account, start)
                         and (is_open or not self._quarter_observed(account, end)))
                label = self.quarter_label(end)
                rows.append({"account": account,
                             "quarter": f"{label} to date" if is_open else label,
                             "opens": start, "quarter_end": end,
                             **self._dietz_row(bv, ev, cf, wcf, inc, blank=blank)})
        frame = pd.DataFrame(rows, columns=["account", "quarter", "opens", "quarter_end",
                                            *self.RESULT_FIGURES])
        # A quarter that opened on nothing, and still has a return: OPENED_IN_PERIOD applies.
        frame["opened_in_period"] = ((frame["opening_nav"] == 0) & frame["return"].notna()
                                     if len(frame) else pd.Series(dtype=bool))
        return frame

    def _dietz(self, start: str, end: str, bv: float, ev: float) -> dict:
        """The day-weighted return between two dates for the whole firm, given its net asset
        value at each."""
        # THE SAME BASIS AS THE YEAR, or the quarters and the year measure different things
        # and nothing says which. Money into POSITIONS, and the income the capital earned, once.
        cf = float(self.capital_deployed(start=start, end=end).sum())
        wcf = float(self.weighted_flows(start=start, end=end).sum())
        inc = float(self.return_income(start=start, end=end).sum())
        return {"opens": start, "quarter_end": end,
                **self._dietz_row(bv, ev, cf, wcf, inc)}

    @staticmethod
    def _dietz_row(bv: float, ev: float, cf: float, wcf: float, inc: float,
                   blank: bool = False) -> dict:
        """THE RETURN'S ONE FORMULA, for the year, the book and each account alike, under the
        same six names — so a book row and an account row read across, and the accounts' gains
        add to the book's.

        MODIFIED DIETZ, DAY-WEIGHTED: (EV − BV − CF + income) ÷ (BV + WCF), where CF is the
        capital deployed in the period and WCF the same flows each weighted by the share of the
        period after its date (`weighted_flows()`), so money put in late in a period barely
        moves the figure. Nothing to measure from gets NO RETURN, never zero, which is a claim.
        `blank` is the caller saying nothing anyone observed moved; the gain is then blank too,
        because a 0.00 gain beside a blank return says the thing the blank refuses to.
        """
        denom = bv + wcf
        gain = ev - bv - cf + inc
        known = not blank and bool(denom)
        return {"opening_nav": bv, "capital_deployed": cf, "return_income": inc,
                "closing_nav": ev,
                "gain": gain if known else float("nan"),
                "return": gain / denom if known else float("nan")}

    def quarter_contributions(self, quarter_end: str) -> pd.DataFrame:
        """What each line did to a quarter: its unrealised gain at the quarter end, less its
        unrealised gain at the previous one, plus what its sales realised in between. One row
        per ticker, largest loss first. Columns: ticker, company, held_as, opening, closing,
        realised, contribution.

        BOTH ENDS ARE FROZEN COMPOSITIONS (`quarter_lines()`), so a line reads the same whenever
        it is asked. Income is not a line's — `income.csv` names an account, not a holding — so
        `quarter_attribution()` carries it beside the lines. KeyError if either end was never
        frozen.
        """
        navs = self.quarter_nav_total()
        prev = max(d for d in navs.index if d < quarter_end)
        before, after = self.quarter_lines(prev), self.quarter_lines(quarter_end)
        opening = before.set_index("ticker")["gain"]
        closing = after.set_index("ticker")["gain"]
        exits = [e for e in self.D.exits if prev < str(e.date)[:10] <= quarter_end]
        sold = [{"ticker": e.ticker, "realised": e.proceeds - self.cost_released[e.eid]}
                for e in exits]
        # HELD AS, so a company held both ways reads as two lines: from either end's
        # composition, and for a line bought and sold inside the quarter from its account.
        held_as = {e.ticker: self.D.KIND_OF_CODE.get(e.ticker) for e in exits}
        held_as.update(dict(zip(before["ticker"], before["held_as"])))
        held_as.update(dict(zip(after["ticker"], after["held_as"])))
        realised = (pd.DataFrame(sold).groupby("ticker")["realised"].sum() if sold
                    else pd.Series(dtype=float))
        out = pd.concat({"opening": opening, "closing": closing, "realised": realised},
                        axis=1).fillna(0.0)
        out["contribution"] = out["closing"] - out["opening"] + out["realised"]
        out.index.name = "ticker"
        out = out.reset_index()
        out["company"] = out["ticker"].map(self._identity().set_index("code")["company"]) \
            .fillna(out["ticker"])
        out["held_as"] = out["ticker"].map(held_as)
        return (out.sort_values(["contribution", "ticker"]).reset_index(drop=True)
                   [["ticker", "company", "held_as", "opening", "closing", "realised",
                     "contribution"]])

    def quarter_attribution(self, quarter_end: str) -> dict:
        """A quarter's gain taken apart: `lines`, the sum of `quarter_contributions()`;
        `position_income`, every POSITION_INCOME row in the quarter — a share account's added by
        the return, a spread-bet account's already inside its equity; and `unattributed`, what
        neither explains — the gap between the frozen compositions and the frozen net asset
        values beside them, such as a composition reconstructed short of its NAV. The three add
        to `gain`, `quarter_returns()`'s."""
        q = self.quarter_returns().set_index("quarter_end").loc[quarter_end]
        lines = float(self.quarter_contributions(quarter_end)["contribution"].sum())
        income = float(self.position_income(start=q["opens"], end=quarter_end).sum())
        return {"lines": lines, "position_income": income,
                "unattributed": float(q["gain"]) - lines - income, "gain": float(q["gain"])}

    def year_to_quarter(self, quarter_end: str) -> dict:
        """The year to a FROZEN quarter end, measured exactly as its quarters are: `_dietz()` from
        the previous 31 December's net asset value to the quarter end's. Unlike the live year to
        date, both ends are frozen, so a report regenerates it the same. Labelled "2026 to 30 Sep"
        under `quarter`. KeyError if either end is not frozen."""
        navs = self.quarter_nav_total()
        start = f"{int(quarter_end[:4]) - 1}-12-31"
        return {"quarter": f"{quarter_end[:4]} to {pd.Timestamp(quarter_end):%-d %b}",
                **self._dietz(start, quarter_end, navs[start], navs[quarter_end])}

    def since_start(self, ytd: float | None = None) -> float:
        """THE RETURN SINCE THE RECORD BEGAN: each full year's, fixed at its
        frozen 31 December by `year_to_quarter()`, linked with the year to date —
        (1 + 2026) × (1 + 2027 to date) − 1. LINKED, NOT ONE PERIOD: one money-weighted figure
        over several years would let one year's flows weigh on another's; linked, each year's
        weighting stays inside it, as the YTD return's does.
        Blank whenever the year to date is; through the first year, the same figure. `ytd` is the
        year to date's return, for a caller already holding it; left out, it is asked for."""
        linked = 1.0 + (self.totals()["ytd"] if ytd is None else ytd)
        if linked != linked:
            return float("nan")
        for year in range(self.baseline.year, self.ytd_year()):
            linked *= 1.0 + self.year_to_quarter(f"{year}-12-31")["return"]
        return linked - 1.0

    # ---- VALUING AT A PAST DATE  —  what makes a report REPRODUCIBLE -----------------

    #
    # Freeze the INPUTS, not the output: a report regenerates identically because the marks it
    # valued at are dated rows in the histories, which only grow. Valuing a past quarter at today's
    # prices would give a number that changes every time it is asked for.
    def _marks_at(self, as_of: str, window: int | None = None) -> tuple[dict, dict]:
        """Prices and FX as at a date — the newest LIVE mark ON OR BEFORE it, per instrument.

        On or before, because a mark does not exist for every instrument every day; never AFTER,
        which would value a quarter with information that did not exist yet.

        WITH A `window`, A QUARTER END BEING FROZEN: each
        instrument takes its mark NEAREST `as_of` within `window` days either side, the earlier on
        a tie, and falls back to the newest on or before when none is that near — `freeze_rows()`
        names every line the window did not reach.

        A SUPERSEDED MARK IS NOT AN ANSWER: this filters on `status` (`rules.LIVE_MARK`), the
        lifecycle, and not on `quality`, the grade.
        """
        live_status = self.D.LIVE_MARK
        day = pd.Timestamp(as_of)

        def pick(rows, key, value):
            out, near = {}, {}
            for row in rows.itertuples():
                k, mark = getattr(row, key), (row.date, float(getattr(row, value)))
                if row.date <= as_of and (k not in out or row.date >= out[k][0]):
                    out[k] = mark
                if window is not None:
                    rank = (abs((pd.Timestamp(row.date) - day).days), row.date)
                    if rank[0] <= window and (k not in near or rank <= near[k][0]):
                        near[k] = (rank, mark)
            return {**out, **{k: mark for k, (_, mark) in near.items()}}

        ph = self.store["history.prices"]
        fh = self.store["history.fx"]
        px = pick(ph[ph["status"] == live_status], "ticker", "price")
        fx = pick(fh[(fh["kind"] == "spot") & (fh["status"] == live_status)], "currency", "rate")
        return px, fx

    def _contracts_open_at(self, ticker: str, as_of: str) -> set[str]:
        """Which spread-bet contracts this ticker had open on a date."""
        out = set()
        for t in self.D.trades:
            if t.ticker != ticker or t.mode != "sb":
                continue
            c = self.D.LEG_CONTRACT.get(t.id)
            if c and str(t.date) <= as_of:
                out.add(c)
        return out

    def _valued_legs_at(self, as_of: str, account: str | None = None) -> dict[str, dict]:
        """Every VALUED leg at a date, by leg id, with the MARK KEY it is priced from.

        VALUED means what the live ledger means: open buys, plus each share sale from a holding
        still held at minus what it sold — the only way a pooled partial disposal is de-valued leg
        by leg. A share holding sold out by the date carries nothing.

        THE MARK KEY IS A CONTRACT FOR A SPREAD BET and the ticker for a share: one underlying sits
        on several contracts at several levels.

        A spread-bet leg with no `LEG_CONTRACT` entry is OMITTED, so a per-contract split may
        undercount; callers compare the total against as_of() and fall back rather than value half
        a holding.

        `account` narrows the LEGS and nothing else — a mark is the same whoever holds it. What is
        deliberately NOT narrowed is `closed_on`: a parcel was consumed by its realisation whoever
        asks, and scoping it would resurrect a sold parcel for an account-level caller.
        """
        cache_key = (as_of, account)
        if cache_key in self._held_cache:
            return self._held_cache[cache_key]
        d = pd.Timestamp(as_of)
        sells = self.ledger[self.ledger["direction"] == "Sell"]
        closed_on = sells.groupby("realisation_id")["date"].max().to_dict()
        # A LEG A SALE NAMES WENT ON THAT SALE'S DAY, not on its parcel's last: a later sale
        # joining the realisation does not put the leg back.
        sold_on = dict(zip(sells["id"], sells["date"]))
        leg_sold = {tid: sold_on[eid] for eid, tid in self.D.EXIT_LEG_MATCH.items()}
        out: dict[str, dict] = {}
        for r in self.ledger.to_dict("records"):
            if not (r["pre_baseline"] or r["date"] <= d):
                continue
            if account is not None and r["acct"] != account:
                continue
            if r["held_as"] == "shares":
                if not pd.isna(r["pool_emptied"]) and r["pool_emptied"] <= d:
                    continue            # its holding had been sold out by the date asked about
            elif r["direction"] == "Sell":
                continue
            else:
                rid = r["realisation_id"]
                if rid is not None and not pd.isna(rid):
                    sold = leg_sold.get(r["id"], closed_on.get(rid))
                    if sold is not None and sold <= d:
                        continue        # this leg was gone by the date asked about
            key = self.D.LEG_CONTRACT.get(r["id"]) if r["mode"] == "sb" else r["ticker"]
            if key is None:
                continue
            held = -r["qty"] if r["direction"] == "Sell" else r["qty"]
            out[r["id"]] = {"ticker": r["ticker"], "key": key, "qty": held,
                            "val": r["val"], "mode": r["mode"], "date": r["date"],
                            "direction": r["direction"], "acct": r["acct"]}
        self._held_cache[cache_key] = out
        return out

    def _held_by_mark_key(self, as_of: str,
                          account: str | None = None) -> dict[tuple[str, str], float]:
        """Open quantity per (ticker, MARK KEY) at a date: the sum of _valued_legs_at().

        `account` is passed through, so a per-contract split is compared against the same
        account's quantity — never the whole book's.
        """
        out: dict[tuple[str, str], float] = {}
        for leg in self._valued_legs_at(as_of, account).values():
            k = (leg["ticker"], leg["key"])
            out[k] = out.get(k, 0.0) + leg["qty"]
        return out

    def _marks_for(self, ticker: str, as_of: str, px: dict,
                   qty: float, account: str | None = None) -> list[tuple[str, float, float]]:
        """Every (key, level, quantity) lot needed to value one holding at a date.

        A SHARE IS ONE LOT, keyed by its ticker. A SPREAD BET IS ONE LOT PER CONTRACT, which is why
        the live price table is keyed by contract: a lookup keyed by ticker keeps one contract and
        values a multi-contract position at one level, saying nothing.

        THE TICKER FALL-BACK. The older price-history rows are keyed by TICKER, from when each
        spread-bet ticker had one contract open. They are used when the per-contract split cannot
        answer, and only when the ticker had at most one contract open.
        """
        lots = {k: q for (tk, k), q in self._held_by_mark_key(as_of, account).items()
                if tk == ticker}
        splittable = (lots and ticker not in lots
                      and abs(sum(lots.values()) - qty) < 1e-9
                      and all(k in px for k in lots))
        if splittable:
            return [(k, px[k][1], lots[k]) for k in sorted(lots)]
        if ticker in px:
            open_contracts = self._contracts_open_at(ticker, as_of)
            if len(open_contracts) > 1:
                raise KeyError(
                    f"{ticker} had {len(open_contracts)} contracts open on {as_of} "
                    f"({sorted(open_contracts)}) and price-history holds only a ticker-keyed "
                    f"mark. One level cannot value a position held at several — bank a "
                    f"contract-keyed mark for that date.")
            return [(ticker, px[ticker][1], qty)]
        missing = sorted(k for k in lots if k not in px) or [ticker]
        raise MissingMark(missing,
            f"no price for {missing[0]} on or before {as_of}: nothing is valued from a mark "
            f"that does not exist.")

    @staticmethod
    def _converts_from(ticker: str, ident: pd.DataFrame) -> str | None:
        """The currency a line's local value is converted from at a date, or None: a spread bet
        is £/point at parity, so NO FX applies, and a sterling line needs no rate."""
        if ident.at[ticker, "kind"] == "spread bet":
            return None
        cur = ident.at[ticker, "currency"] if ticker in ident.index else "GBP"
        return None if cur == "GBP" else cur

    def valuation_gaps(self, as_of: str) -> dict[str, list[str]]:
        """EVERYTHING that stops the book being valued at `as_of`, at once: `prices`, the mark
        keys with no mark on or before the date; `rates`, the currencies with no rate; `other`,
        any other refusal of `_marks_for()`, in its own words. All empty when `holdings_at()` can
        value the date.

        `holdings_at()` stops at the first gap, which is right for a figure. A report's gate asks
        for all of them, so a quarter's page says what it lacks rather than what it lacks first.
        """
        held = self.as_of(as_of).set_index("ticker")
        px, fx = self._marks_at(as_of)
        ident = self._identity().set_index("code")
        prices, rates, other = set(), set(), []
        for ticker, r in held.iterrows():
            try:
                self._marks_for(ticker, as_of, px, r["qty"])
            except MissingMark as e:
                prices.update(e.keys)
            except KeyError as e:
                other.append(str(e.args[0]))
            cur = self._converts_from(ticker, ident)
            if cur is not None and cur not in fx:
                rates.add(cur)
        return {"prices": sorted(prices), "rates": sorted(rates), "other": other}

    def rate_gaps(self, today: str | None = None) -> list[dict]:
        """THE DATED RATES THE RECORD LACKS: each currency and date a dated figure
        converts at with no TradingView close on file to serve it. Three kinds of date need one:

          quarter end   each quarter end on file, for every currency a share held then is priced in
          income        each income row paid in another currency, on its own date, unless its
                        broker states the rate
          typed         each date fx-history.csv holds a typed rate on, which that day's close
                        replaces
          deal          each share deal priced in sterling on a share in another currency, on its
                        own date: the close gives the share's own price (`deal_prices()`)

        A DATE IS SERVED BY ITS NEWEST SESSION'S CLOSE: the newest live spot rate on or before it
        is a close, dated that day or on the weekday before a weekend. A date not yet past is
        owed nothing. Rows {currency, date, why, rate}, oldest first, as the audit and the Price
        Refresh name them. Side effects: none.
        """
        day = (pd.Timestamp(today) if today else pd.Timestamp.today()).normalize()
        fh = self.store["history.fx"]
        spot = fh[(fh["kind"] == "spot") & (fh["status"] == self.D.LIVE_MARK)]
        ident = self._identity().set_index("code")
        wanted: dict[tuple[str, str], str] = {}

        # A quarter end: the currencies of the shares held that day, from the ledger, so a date
        # before the baseline is answered as one after it is.
        L = self.ledger[self.ledger["held_as"] == "shares"]
        signed = L["qty"].where(L["direction"] != "Sell", -L["qty"])
        for end in sorted(set(self.store["quarter_nav"]["as_of"].astype(str))):
            on = signed[L["date"] <= pd.Timestamp(end)].groupby(L["ticker"]).sum()
            for ticker in on[on > 0].index:
                cur = ident.at[ticker, "currency"] if ticker in ident.index else "GBP"
                if cur != "GBP":
                    wanted.setdefault((cur, end), "quarter end")
        inc = self.store["income"]
        for cur, date, rate in zip(inc["currency"].fillna(""), inc["date"], inc["rate"]):
            if cur and cur != "GBP" and pd.isna(rate):
                wanted.setdefault((cur, pd.Timestamp(date).date().isoformat()), "income")
        typed = spot[spot["struck"].fillna("") == ""]
        for cur, date in zip(typed["currency"], typed["date"]):
            wanted.setdefault((cur, str(date)), "typed")
        priced = L[L["price"].notna() & L["cur"].eq("GBP")]
        for ticker, date in zip(priced["ticker"], priced["date"]):
            cur = ident.at[ticker, "currency"] if ticker in ident.index else "GBP"
            if cur != "GBP":
                wanted.setdefault((cur, date.date().isoformat()), "deal")

        def newest(cur: str, date: str):
            on = spot[(spot["currency"] == cur) & (spot["date"] <= date)]
            return None if on.empty else on.sort_values("date").iloc[-1]

        def served(cur: str, date: str) -> bool:
            row = newest(cur, date)
            last_weekday = pd.Timestamp(date) - pd.Timedelta(
                days=max(0, pd.Timestamp(date).weekday() - 4))
            return (row is not None and row["struck"] == "close"
                    and pd.Timestamp(row["date"]) >= last_weekday)

        # `rate`: what the date converts at TODAY — the newest spot rate on or before it, or None —
        # so the close that replaces it can be read against it before it is taken.
        return [{"currency": cur, "date": date, "why": why,
                 "rate": None if newest(cur, date) is None else float(newest(cur, date)["rate"])}
                for (cur, date), why in sorted(wanted.items(), key=lambda kv: (kv[0][1], kv[0][0]))
                if pd.Timestamp(date) < day and not served(cur, date)]

    def _unrealised_at_baseline(self, order: list) -> pd.Series:
        """Each spread-bet account's open gain on the baseline day, at that day's marks: what its
        baseline equity already holds of the legs open then. Zero for an account holding nothing
        that day; BLANK for one whose legs that day's marks cannot value, so its net asset value
        is blank rather than counted twice. Share accounts are zero: their value is not built
        from the baseline."""
        out = {}
        for a in order:
            if not self.is_spread_bet(a) or self.as_of(self.baseline_asof, a).empty:
                out[a] = 0.0
                continue
            try:
                h = self.holdings_at(self.baseline_asof, a)
                out[a] = float(h["value"].sum() - h["cost"].sum())
            except (KeyError, ValueError):
                out[a] = float("nan")
        return pd.Series(out, dtype="float64").reindex(order)

    def holdings_at(self, as_of: str, account: str | None = None,
                    window: int | None = None) -> pd.DataFrame:
        """Holdings as at a past date, valued at that date's marks. Optionally ONE account's.

        Quantity and cost come from as_of(), reconstructed from the events; VALUE from the dated
        marks, so the same call next year returns the same figures. `account` is what makes a share
        reconciliation possible — one account's holdings against its own statement, at its date —
        and it also values dates the whole book cannot, when the missing mark is another account's.
        """
        held = self.as_of(as_of, account).set_index("ticker")
        px, fx = self._marks_at(as_of, window)
        ident = self._identity().set_index("code")

        rows = []
        for ticker, r in held.iterrows():
            cur = ident.at[ticker, "currency"] if ticker in ident.index else "GBP"
            lots = self._marks_for(ticker, as_of, px, r["qty"], account)
            local = sum(q * price for _, price, q in lots)
            rate = self._converts_from(ticker, ident)
            if rate is None:
                value = local
            else:
                if rate not in fx:
                    raise KeyError(f"no {rate} rate on or before {as_of}")
                value = local / fx[rate][1]
            # A POSITION IS ONLY AS FRESH AS ITS STALEST LEG, as in holdings() and price_ageing().
            priced_at = min(px[k][0] for k, _, _ in lots)
            rows.append({"ticker": ticker, "company": ident.at[ticker, "company"],
                         "sector": ident.at[ticker, "sector"],
                         "region": ident.at[ticker, "region"], "currency": cur,
                         "held_as": ident.at[ticker, "kind"],
                         "qty": r["qty"], "cost": r["cost"], "value": value,
                         "priced_at": priced_at})
        # NAMED COLUMNS, so an account holding nothing that day is an empty frame rather than a
        # KeyError on "value": an IG account not yet funded at a quarter end could not be frozen.
        out = pd.DataFrame(rows, columns=["ticker", "company", "sector", "region", "currency",
                                          "held_as", "qty", "cost", "value", "priced_at"])
        out["gain"] = out["value"] - out["cost"]
        total = out["value"].sum()
        out["weight"] = out["value"] / total if total else float("nan")
        return out.sort_values("company").reset_index(drop=True)

    def as_of(self, date: str, account: str | None = None) -> pd.DataFrame:
        """Positions held on any date from the baseline onwards, optionally in ONE account.

        A leg counts if it was opened before the date — and every PRE-self.baseline leg does, because it
        was held when the record began; its date may be unknown, its era is not.

        COST NETS OUT WHAT HAD BEEN SOLD BY THAT DATE: each sale releases what `cost_released`
        says it released, on the day it happened.

        ANSWERS FROM THE OPENING DAY, the baseline's eve (`self.baseline_asof`): what the record opened
        with — every pre-baseline leg — held at that day's close, so the opening can be valued at
        its own closes like any quarter end. Refuses any earlier day: the book does
        not claim to know what was held before it. Gives QUANTITY and COST; market value needs a
        mark for that day.

        `account` narrows the ledger and nothing else. A realisation lives in one account, so
        its sales are narrowed with it.
        """
        d = pd.Timestamp(date)
        if d < pd.Timestamp(self.baseline_asof):
            raise ValueError(
                f"as_of({date!r}) is before the book's baseline of {self.baseline.date()}, which "
                f"opens on {self.baseline_asof}'s close. The record begins at {self.baseline:%-d %b %Y}; "
                f"positions opened earlier are carried for their cost basis only.")

        L = self.ledger
        if account is not None:
            L = L[L["acct"] == account]
            if L.empty:
                raise ValueError(
                    f"as_of({date!r}, account={account!r}): no legs at all. An account with "
                    f"nothing in the ledger is a name that does not match — check it against "
                    f"rules.ACCOUNT_ORDER rather than reading the empty frame as a holding.")
        L = L[L["pre_baseline"] | (L["date"] <= d)].copy()

        def qty(r):
            return -r["qty"] if r["direction"] == "Sell" else r["qty"]

        def cost(r):
            return _buy_cost(r["qty"], r["val"], r["mode"]) if r["direction"] == "Buy" else 0.0

        L["signed_qty"] = L.apply(qty, axis=1)
        L["signed_cost"] = L.apply(cost, axis=1)
        out = (L.groupby("ticker", as_index=False)
                .agg(qty=("signed_qty", "sum"), cost=("signed_cost", "sum")))

        # EVERY SALE RELEASES ITS OWN COST, ON THE DAY IT HAPPENED — the leg it names or its
        # pool's average, whichever `cost_released` holds. A parcel released all at once on its
        # LAST sale would count each earlier sale's cost twice until then: once as still held,
        # once as released.
        sold = L[L["direction"] == "Sell"]
        rel = sold["id"].map(self.cost_released).groupby(sold["ticker"]).sum()
        out["cost"] -= out["ticker"].map(rel).fillna(0.0)

        return out[out["qty"] > 0].sort_values("ticker").reset_index(drop=True)

    #: How a row the freeze door wrote says the engine derived it, in `freeze_rows()`'s own
    #: words: the rows `frozen_drift()` can derive again. A broker's figure, or one set by a
    #: decision, says otherwise and is left alone.
    FROM_THE_ENGINE = "from the engine at the marks nearest"

    def frozen_drift(self) -> pd.DataFrame:
        """Every live quarter-nav row the freeze door derived from the engine that the record, as
        it now stands, no longer reproduces: `as_of`, `account`, `contribution`, `frozen`, `now`
        (blank where the record can no longer value it at all).

        A ROW DATED BEFORE A FROZEN QUARTER END BUT ENTERED AFTER IT lands in the next period's
        gain: the frozen figure stays put and the live one moves. So does a correction to such a
        row. Empty means every engine-frozen quarter end still describes the record. A row here is
        restated through `desk/doors/freeze.py` on the owner's word, never by itself, because
        the frozen figure is what was believed at the time.

        Side effects: none.
        """
        qn = self.quarter_nav()
        ours = qn[qn["source"].astype(str).str.contains(self.FROM_THE_ENGINE, regex=False)]
        out = []
        for as_of, rows in ours.groupby(ours["as_of"].astype(str).str[:10]):
            accounts = [a for a in self.D.ACCOUNT_ORDER if a in set(rows["account"])]
            try:
                now = {(r["account"], r["contribution"]): r["amount"]
                       for r in self.freeze_rows(as_of, accounts=accounts)["quarter_nav"]}
            except (KeyError, ValueError):
                now = {}
            for r in rows.itertuples(index=False):
                again = now.get((r.account, r.contribution))
                if again is None or abs(float(again) - float(r.amount)) >= 0.005:
                    out.append({"as_of": as_of, "account": r.account,
                                "contribution": r.contribution, "frozen": float(r.amount),
                                "now": None if again is None else round(float(again), 2)})
        return pd.DataFrame(out, columns=["as_of", "account", "contribution", "frozen", "now"])

    def freeze_rows(self, as_of: str, accounts: list[str] | None = None,
                    restated: str | None = None) -> dict:
        """The rows that FREEZE a quarter end, from the engine at the marks nearest that date.

        What checklist steps 2 to 4 had a person copy off HOLDINGS into two CSVs — the one place
        a close typed figures. `quarter_snapshots` is one row per line of each account's block,
        exactly as HOLDINGS shows it: a spread-bet leg at NOTIONAL, its local price the value
        over the quantity, an account holding nothing as "(no positions)". `quarter_nav` is each
        account's contribution to net asset value — positions at market, or a spread-bet
        account's equity with its notional beside it for the exposure archive.

        QUANTITIES ARE THE QUARTER END'S; A PRICE IS THE MARK NEAREST IT within
        `rules.CLOSE_CHECK_WINDOW_DAYS` either side — a quarter end needs to be close, not an
        instant — and each snapshot row's `source` names the mark it took.
        `off_date` names every line whose mark, or whose rate, the window did not reach, and
        `off_keys` the mark keys among them, so the freeze door can say where each comes from. Empty
        means every figure here is near enough. `desk/doors/freeze.py` refuses to write while it is not.

        `accounts` narrows it to those accounts, in register order: what a RESTATEMENT strikes
        again, and the only way to value the opening, where an account with no closes on file
        would stop the rest. `restated` is the day of a restatement, which the rows' sources then
        name in place of "frozen".

        Side effects: none.
        """
        window = self.D.CLOSE_CHECK_WINDOW_DAYS
        day = pd.Timestamp(as_of)

        def outside(date):
            return abs((pd.Timestamp(date) - day).days) > window

        px, fx = self._marks_at(as_of, window)
        ph = self.store["history.prices"]
        live = ph[(ph["status"] == self.D.LIVE_MARK)]
        order = [a for a in self.D.ACCOUNT_ORDER if accounts is None or a in accounts]
        # A SPREAD-BET ACCOUNT'S EQUITY is by_account()'s, which values every account: asked only
        # when one is wanted, so a share account can be struck on a day the others cannot.
        nav = (self.by_account(as_of, window=window).set_index("account")["nav"]
               if any(self.is_spread_bet(a) for a in order) else None)
        snaps, navs, off, off_keys = [], [], [], set()
        where = (f"restated on {restated} {self.FROM_THE_ENGINE} {as_of}" if restated
                 else f"frozen {self.FROM_THE_ENGINE} {as_of}")
        for account in order:
            held = self.holdings_at(as_of, account, window=window)
            sb = self.is_spread_bet(account)
            if held.empty:
                snaps.append({"as_of": as_of, "account": account, "ticker": "(no positions)",
                              "qty": None, "local_price": None, "currency": None, "gbp_value": 0.0,
                              "gbp_cost": 0.0, "quality": "derived",
                              "source": f"No open position at {as_of}, {where}"})
            for r in held.itertuples(index=False):
                lots = self._marks_for(r.ticker, as_of, px, r.qty, account)
                keys = [k for k, _, _ in lots]
                local = sum(q * price for _, price, q in lots)
                # A CARRIED LINE OR RATE is priced by decision at its last figure, so it is never
                # "another day's price" here — `rules.STATEMENT_PRICED`, `rules.RATE_CARRIED`.
                for k in keys:
                    if outside(px[k][0]) and r.ticker not in self.D.STATEMENT_PRICED:
                        off.append(f"{account} {r.ticker}: {k}'s nearest mark is {px[k][0]}")
                        off_keys.add(k)
                if (r.held_as != "spread bet" and r.currency != "GBP"
                        and outside(fx[r.currency][0])
                        and r.currency not in self.D.RATE_CARRIED):
                    off.append(f"{account} {r.ticker}: its nearest {r.currency} rate is "
                               f"{fx[r.currency][0]}")
                sources = [str(live[(live["ticker"] == k) & (live["date"] == px[k][0])]["source"]
                               .iloc[-1]) for k in keys]
                snaps.append({"as_of": as_of, "account": account, "ticker": r.ticker,
                              "qty": int(r.qty) if float(r.qty).is_integer() else float(r.qty),
                              "local_price": round(local / r.qty, 6), "currency": r.currency,
                              "gbp_value": round(float(r.value), 2),
                              "gbp_cost": round(float(r.cost), 2), "quality": "derived",
                              "source": " + ".join(sources)})
            value = round(float(held["value"].sum()), 2) if not held.empty else 0.0
            if sb:
                navs.append({"as_of": as_of, "account": account,
                             "amount": round(float(nav[account]), 2),
                             "contribution": "account equity", "quality": "derived",
                             "source": f"Equity {where}: funds plus the legs at those levels"})
                navs.append({"as_of": as_of, "account": account, "amount": value,
                             "contribution": "notional", "quality": "derived",
                             "source": f"Notional {where}, the EXPOSURE measure — NOT part of NAV"})
            else:
                navs.append({"as_of": as_of, "account": account, "amount": value,
                             "contribution": "positions at market", "quality": "derived",
                             "source": f"Positions at market {where}"})
        return {"as_of": as_of, "quarter_snapshots": snaps, "quarter_nav": navs,
                "off_date": off, "off_keys": sorted(off_keys)}

    # ---- WHAT MOVED, AND WHY ---------------------------------------------------------

    def changes_since(self, since: str | None = None,
                      account: str | None = None) -> pd.DataFrame:
        """What moved on each priced line, split into price, FX and dealing.

        ONE ROW PER MARK KEY — a contract for a spread bet, a ticker for a share — the granularity
        at which a price exists.

        EVERY LINE CARRIES ITS OWN TWO DATES. Lines are not all struck on one date — a line a sweep
        left unpriced keeps its older mark, and a market not yet open is its last session's close —
        so there is no single "since the last refresh": `since=None` compares each line against
        ITS OWN previous mark, and `priced_from`/`priced_at` say which two.

        THE THREE EFFECTS SUM TO THE CHANGE EXACTLY, in a stated order — every factor decomposition
        is path-dependent, so an unstated order drifts:

            transacted   what dealing put in or took out, AT WHAT WAS ACTUALLY TRANSACTED:
                         a share at the settled GBP cost off its contract note, a spread bet
                         at its entry notional, a disposal at its proceeds
            fx_effect    the rate's effect on the stake held through the WHOLE window
            price_effect the rest, which is what the marks did

        EACH LINE STARTS WHERE THE BOOK STOOD the day before its new mark: its previous mark, at
        the rate the book then held beside it. Not the rate banked on the mark's own date — a
        close is struck a session before the refresh that brings it, and the book valued it at
        that refresh's rate. With `since`, the book as it stood that day.

        THE TWO ENDS USE DIFFERENT RATES, on purpose. `value_to` is the figure the book publishes
        today, so it converts at the live rate through `rate_now()`, as `value_legs()` does. The
        cost: on a line whose mark is older than the rate, `fx_effect` spans to now while
        `price_effect` spans to the mark; the identity still holds, because `price_effect` is the
        residual.

        DEALING IS VALUED AT WHAT IT COST, not at the closing level: valued at the close, a stake
        added and underwater days later hides its loss inside the dealing figure.

        TWO IMPURITIES, stated: a disposal's proceeds are NET, so its dealing cost lands in
        `price_effect`; and a leg opened or closed inside the window contributes no `fx_effect`,
        because its GBP cost or proceeds already embed the broker's rate and splitting them would
        manufacture a division out of a guess.

        A LINE CLOSED INSIDE THE WINDOW ENDS AT ITS CLOSE, at nothing: its proceeds in
        `transacted`, the move from its last mark to its sale price in `price_effect`, and the
        sale's date as `priced_at`. Leaving it out started the window without it, while a
        part-close beside it showed. One sold before the newest outgoing mark belongs to an
        earlier window.

        A LINE WITH ONLY ONE MARK is included, `priced_from` blank and its whole move in
        `transacted`; dropping it breaks the tie back to the book.

        EACH WINDOW ENDS AT THE LINE'S LIVE MARK, the one the book publishes from, and never at a
        close banked after it: a past day's closes are banked into the history without touching
        the live table (`desk/doors/marks.py:bank_closes()`), and a window running on to one would end
        somewhere the book is not. That close joins the window when a refresh makes it live.

        `held_as` is `shares` or `spread bet` (glossary §2), and the two never sum together —
        change_totals() enforces it. `account` narrows to one account's slice of each line: the
        LEGS and the EXITS, never the marks.
        """
        cache_key = (since, account)
        if cache_key in self._changes_cache:
            # A COPY, because a caller that filters or assigns on the frame must not reach
            # the next caller's answer.
            return self._changes_cache[cache_key].copy()
        prices = self.store["history.prices"]
        dates_of = {k: sorted(set(g["date"])) for k, g in prices.groupby("ticker")}
        ident = self._identity().set_index("code")

        # AN EXIT BELONGS TO THE MARK KEY ITS REALISATION'S BUY LEGS SAT ON. A pool sale
        # consumed no named leg, so it falls back to the ticker — which is right, because a
        # pooled position is a share and a share is priced by ticker.
        rid_keys: dict[str, set] = {}
        for r in self.ledger[self.ledger["direction"] == "Buy"].to_dict("records"):
            rid = r["realisation_id"]
            if rid is None or pd.isna(rid):
                continue
            k = self.D.LEG_CONTRACT.get(r["id"]) if r["mode"] == "sb" else r["ticker"]
            if k:
                rid_keys.setdefault(rid, set()).add(k)

        by_id = {t.id: t for t in self.D.trades}

        def _exit_key(e):
            # A SALE THAT NAMES ITS LEG SAT ON THAT LEG'S LINE, whatever else its parcel held.
            leg = by_id.get(self.D.EXIT_LEG_MATCH.get(e.eid))
            if leg is not None:
                return (self.D.LEG_CONTRACT.get(leg.id) if leg.mode == "sb" else leg.ticker) \
                    or e.ticker
            ks = rid_keys.get(self.D.REALISATION_BY_EXIT.get(e.eid), set())
            return next(iter(ks)) if len(ks) == 1 else e.ticker

        # THE POPULATION IS THE LIVE BOOK'S OWN LINES, which makes the totals tie back to owned()
        # and exposure(); keyed off price-history instead, long-closed lines would join the frame.
        live_keys = set()
        for r in self.ledger[self.ledger["valued"]].to_dict("records"):
            k = self.D.LEG_CONTRACT.get(r["id"]) if r["mode"] == "sb" else r["ticker"]
            if k:
                live_keys.add(k)

        live_on = {r["ticker"]: str(r["as_of"])[:10] for r in self.store["prices"].to_dict("records")}

        windows: dict[str, tuple] = {}
        for key, dates in sorted(dates_of.items()):
            if key not in live_keys:
                continue
            if key in live_on:
                dates = [d for d in dates if d <= live_on[key]]
                if not dates:
                    continue
            t1 = dates[-1]
            t0 = since if since is not None else (dates[-2] if len(dates) > 1 else None)
            if t0 is not None and t0 >= t1:
                continue
            windows[key] = (t0, t1)

        sales: dict[str, list] = {}
        for e in self.D.exits:
            if account is None or e.acct == account:
                sales.setdefault(_exit_key(e), []).append(e)

        # AND EVERY LINE CLOSED INSIDE THE WINDOW, which ends at its close: held at its last mark
        # and sold after the outgoing marks, its start is where the book stood. The window opened
        # at the newest outgoing mark, so a line closed before that belongs to an earlier one.
        opened = since if since is not None else max(
            (t0 for t0, _ in windows.values() if t0 is not None), default=None)
        for key, dates in sorted(dates_of.items()):
            if key in live_keys or key not in sales or opened is None:
                continue
            closed = max(str(e.date)[:10] for e in sales[key])
            t0 = since if since is not None else next(
                (d for d in reversed(dates) if d < closed), None)
            if closed > opened and t0 is not None and t0 < closed:
                windows[key] = (t0, closed)

        rows = []
        for key, (t0, t1) in sorted(windows.items()):
            legs1 = {i: leg for i, leg in self._valued_legs_at(t1, account).items()
                     if leg["key"] == key}
            legs0 = ({i: leg for i, leg in self._valued_legs_at(t0, account).items()
                      if leg["key"] == key} if t0 is not None else {})
            # A SALE INSIDE THE WINDOW, which is all a line closed in it has left.
            sold = [e for e in sales.get(key, ()) if t0 is not None and t0 < str(e.date)[:10] <= t1]
            if not legs1 and not (legs0 and sold):
                continue                      # nothing holds this line at either end

            # The rates are not taken from `t1` — see the docstring.
            px1, _ = self._marks_at(t1)
            ended = key not in live_keys
            if key not in px1 and not ended:
                continue
            px0, _ = self._marks_at(t0) if t0 is not None else ({}, {})
            _, held_at = self._marks_at(
                since if since is not None
                else (pd.Timestamp(t1) - pd.Timedelta(days=1)).date().isoformat())
            p0 = px0[key][1] if key in px0 else None
            # A CLOSED LINE'S LAST LEVEL IS ITS CLOSE, in the units its marks are struck in.
            p1 = (float(sorted(sold, key=lambda e: str(e.date)[:10])[-1].price) if ended
                  else px1[key][1])

            ticker = next(iter((legs1 or legs0).values()))["ticker"]
            known = ticker in ident.index
            synthetic = known and ident.at[ticker, "kind"] == "spread bet"
            cur = ident.at[ticker, "currency"] if known else "GBP"
            # A spread bet is sterling at parity, so no rate applies at either end. `rate1` is the
            # LIVE rate and `rate0` the rate the book HELD the line at — see the docstring.
            # A LINE NO LONGER HELD IS ASKED NO RATE NOW: nothing of it is valued at the end, and
            # a currency nothing is held in has no live rate.
            rate1 = (1.0 if (synthetic or cur == "GBP")
                     else held_at[cur][1] if (ended and cur in held_at) else rate_now(cur, self.D))
            rate0 = (1.0 if (synthetic or cur == "GBP")
                     else (held_at[cur][1] if cur in held_at else rate1))

            q0 = sum(leg["qty"] for leg in legs0.values())
            q1 = sum(leg["qty"] for leg in legs1.values())
            held_throughout = sum(leg["qty"] for i, leg in legs1.items() if i in legs0)

            value_from = q0 * p0 / rate0 if p0 is not None else 0.0
            value_to = q1 * p1 / rate1
            fx_effect = (held_throughout * p1 * (1 / rate1 - 1 / rate0)
                         if p0 is not None else 0.0)

            # A SHARE SALE'S OWN LEG IS NOT A PURCHASE. It appears as a leg at minus what it
            # sold, which moves the quantity; the proceeds come from the sale itself, and
            # counting both would book the disposal twice.
            transacted = sum(_buy_cost(leg["qty"], leg["val"], leg["mode"])
                             for i, leg in legs1.items()
                             if i not in legs0 and leg["direction"] == "Buy")
            transacted -= sum(e.proceeds for e in sold)

            change = value_to - value_from
            rows.append({
                "key": key, "ticker": ticker,
                "company": ident.at[ticker, "company"] if known else ticker,
                "held_as": "spread bet" if synthetic else "shares",
                "currency": cur,
                "priced_from": px0[key][0] if key in px0 else None,
                "priced_at": t1 if ended else px1[key][0],
                "qty_from": q0, "qty_to": q1,
                "value_from": value_from, "value_to": value_to, "change": change,
                "price_effect": change - fx_effect - transacted,
                "fx_effect": fx_effect, "transacted": transacted,
                # THE MARK MOVE, LEVEL TO LEVEL, which is NOT the change in value: on a traded line
                # the mark can rise while the value falls. This is what a reader means by "+2.27%".
                "price_move_pct": (p1 / p0 - 1) if p0 else None})

        out = pd.DataFrame(rows, columns=[
            "key", "ticker", "company", "held_as", "currency", "priced_from", "priced_at",
            "qty_from", "qty_to", "value_from", "value_to", "change", "price_effect", "fx_effect",
            "transacted", "price_move_pct"])
        if not out.empty:
            # BIGGEST MOVER FIRST, within a basis: the ordering is part of "what moved".
            out = (out.assign(_size=out["change"].abs())
                      .sort_values(["held_as", "_size"], ascending=[True, False])
                      .drop(columns="_size").reset_index(drop=True))
        self._changes_cache[cache_key] = out
        return out.copy()

    def change_windows(self, since: str | None = None,
                       account: str | None = None) -> list[dict]:
        """The distinct two-date windows in changes_since(), and how many lines each covers.

        Lines can be marked on different dates, so "since the last refresh" may name several
        windows and a heading must say each; derived here so no panel computes it. A line with no previous mark
        (`priced_from` None) is its own window.
        """
        out: dict[tuple, int] = {}
        for row in self.changes_since(since, account).to_dict("records"):
            start = row["priced_from"] if isinstance(row["priced_from"], str) else None
            out[(start, row["priced_at"])] = out.get((start, row["priced_at"]), 0) + 1
        return [{"priced_from": a, "priced_at": b, "lines": n}
                for (a, b), n in sorted(out.items(), key=lambda kv: (kv[0][1], kv[0][0] or ""))]

    def change_opened(self, since: str | None = None,
                      account: str | None = None) -> str | None:
        """The earliest date a line in changes_since() is measured from: how far back market
        time reaches, so record time can be shown over the same span. None when no line has a
        previous mark."""
        starts = [w["priced_from"] for w in self.change_windows(since, account) if w["priced_from"]]
        return min(starts) if starts else None

    def change_totals(self, since: str | None = None, held_as: str = "shares",
                      account: str | None = None) -> dict:
        """The three effects and the change, totalled over ONE kind of line.

        REFUSES TO TOTAL BOTH: shares are money and spread bets notional. Ask twice. `account`
        gives that account's total — one of the two calls then has `lines` of zero, which is the
        partition, not a gap.
        """
        if held_as not in self.D.schema.KINDS:
            raise BasisError(
                f"held_as must be one of {self.D.schema.KINDS}, not {held_as!r} — one is money "
                f"and one is notional, and no total spans them.")
        frame = self.changes_since(since, account)
        frame = frame[frame["held_as"] == held_as]
        out = {c: float(frame[c].sum()) for c in ("value_from", "value_to", "change",
                                                  "price_effect", "fx_effect", "transacted")}
        out["held_as"] = held_as
        out["lines"] = int(len(frame))
        return out

    def mark_history(self, key: str, by: str = "ticker",
                     account: str | None = None) -> pd.DataFrame:
        """Every banked mark behind one HOLDINGS ROW, newest first, with its source string — the
        evidence under the row's value.

        A line's marks may sit under two keys: the older ticker-keyed rows and the contract-keyed
        ones, both shown, so a position's history starts where it really did. A retired, unpriced
        contract adds nothing.

        `level` says which marks are a spread bet's LEVEL IN POINTS, as IG states it, rather than a
        price in the line's currency: a contract's, and a bet's own ticker-keyed ones.
        """
        if by == "issuer":
            company = self._identity().set_index("code")["company"]
            tickers = {code for code, name in company.items() if name == key}
        else:
            tickers = {key}

        # THE TICKER IS ITSELF A MARK KEY — always for a share, and for a spread bet
        # wherever those legacy rows are. The contracts join it from the open legs.
        keys = set(tickers)
        for leg in self._valued_legs_at(self.valued_at(), account).values():
            if leg["ticker"] in tickers:
                keys.add(leg["key"])

        prices = self.store["history.prices"]
        # `ticker` is renamed at the door: in this table it is a MARK KEY, not an instrument code.
        out = (prices[prices["ticker"].isin(keys)]
               .rename(columns={"ticker": "mark_key"}))
        out["level"] = [k in self.D.CONTRACTS or self.D.KIND_OF_CODE.get(k) == "spread bet"
                        for k in out["mark_key"]]
        return out.sort_values(["date", "mark_key"], ascending=[False, True]) \
                  .reset_index(drop=True)

    # ---- RECORD TIME  —  what the book LEARNED, and when -----------------------------

    def journal_opened(self) -> str | None:
        """The instant the journal opened: every table's opening count is taken then.

        Every table's opening count carries it, and they all carry the SAME one, because
        staggered openings would make "since the journal opened" mean a different moment per
        table. Returns None on a journal with no baseline rows, which is a journal that cannot
        be reconciled and is reported as such rather than guessed at.
        """
        opened = self.store["journal"]
        opened = opened[opened["route"] == "baseline"]["at"]
        return None if opened.empty else str(opened.min())

    def journal(self, since: str | None = None, route: str | None = None,
                before: str | None = None) -> pd.DataFrame:
        """The journal, newest first, opening counts excluded — an opening count records what
        was already on file, not a change.

        `since` is an ISO instant or date; a plain date includes the whole of that day.
        `before` is the rest: the same date leaves out the whole of that day.
        """
        frame = self.store["journal"]
        frame = frame[frame["route"] != "baseline"]
        if since:
            frame = frame[frame["at"] >= (utc_of(since) if "T" in str(since) else str(since))]
        if before:
            frame = frame[frame["at"] < (utc_of(before) if "T" in str(before) else str(before))]
        if route:
            frame = frame[frame["route"] == route]
        # ONE SECOND CAN HOLD SEVERAL WRITES, and the later row in the file is the newer: reversed
        # first and sorted stably, they read newest first like everything else.
        return (frame.iloc[::-1].sort_values("at", ascending=False, kind="stable")
                .reset_index(drop=True))

    def journal_reconciliation(self) -> pd.DataFrame:
        """Per table: the opening count, what the journal accounts for, and what is on file.

        THE CLAIM: `opening + appends − removes = rows on file`, table by table. A difference is a
        row that reached the store by a route nobody journalled — the hand edits, which this lists
        rather than fails on. The counts come through the record (`rules.store_rows()`).

        A REPLACE IS NOT COUNTED: a refresh replacing marks leaves the file as long as it was.
        Only rows at or after the opening count are read; the seeded bench rows before it are
        already inside those figures.
        """
        frame = self.store["journal"]
        opened = self.journal_opened()
        on_file = self._rows_on_file
        out = []
        for name in sorted(on_file):
            base = frame[(frame["route"] == "baseline") & (frame["table"] == name)]
            since = frame[(frame["table"] == name) & (frame["route"] != "baseline")]
            if opened is not None:
                since = since[since["at"] >= opened]
            opening = int(base["rows"].sum()) if not base.empty else None
            added = int(since[since["op"] == "append"]["rows"].sum())
            removed = int(since[since["op"] == "remove"]["rows"].sum())
            expected = None if opening is None else opening + added - removed
            out.append({
                "table": name, "opening": opening, "appended": added, "removed": removed,
                "replaced": int(since[since["op"] == "replace"]["rows"].sum()),
                "expected": expected, "on_file": on_file[name],
                "unaccounted": None if expected is None else on_file[name] - expected,
            })
        return pd.DataFrame(out)

    def journal_unaccounted(self) -> pd.DataFrame:
        """Only the tables that do not close. Empty means every row is accounted for."""
        recon = self.journal_reconciliation()
        return recon[recon["unaccounted"].fillna(0) != 0].reset_index(drop=True)

    # ---- WHAT THE RECORD NEEDS TODAY -------------------------------------------------
    #
    # The findings `portfusion record` prints and the Dashboard lists under "Needs attention". Every
    # one is read from the record, never from a rendering.

    def findings(self, today: str | None = None) -> dict:
        """The record's state as data: {problems, gaps, notes, prices}.

        A PROBLEM is a defect until explained: an account past its reconciliation band, prices
        past their age or spread limit, a conversion at a stale rate, a row entered since the line
        whose document is not on file. A GAP is work owed: an account with no statement, a
        judgement owed. A NOTE is the state, stated, so a working check is visible as working.

        No expected figure is written in: every finding is a relationship in today's record. Each
        part that reads machinery outside the ledger — the journal, the conversions, the archive —
        reports that it could not look rather than raising.

        `today` is an ISO date for the price-age test; today's date if omitted.
        """
        problems, gaps, notes = [], [], []

        # ---- the book against the BROKERS' STATEMENTS -------------------------------------
        checked, ungrounded, apart = 0, [], []
        for r in self.reconciliation().to_dict("records"):
            statement = r["statement"]
            if statement is None or statement != statement:
                ungrounded.append(r["account"])
                continue
            difference = r["difference"]
            difference = None if difference is None or difference != difference else difference
            comparable = r["comparable"]
            v = self.reconciliation_verdict(statement, difference, r["evidence"] or "",
                                            comparable if comparable is not None else None,
                                            "" if comparable else str(r["comparability"] or ""))
            if not v["checkable"]:
                apart.append(f"{r['account']} — {v['rule']}")
                continue
            checked += 1
            if v["verdict"] == "units-agree":
                continue
            if difference is None or not v["ties"]:
                shown = "an unknown amount" if difference is None else f"{difference:,.2f}"
                problems.append(f"reconciliation failed — {r['account']}: book and broker differ "
                                f"by {shown}" + (f", past the {v['band']:,.2f} live band"
                                                 if v["live"] else ""))
            elif v["live"]:
                # A difference that rounds to nothing is 0.00, never -0.00 or +0.00.
                agree = f"{difference:+,.2f}" if round(difference, 2) else "0.00"
                notes.append(f"{r['account']}: book and broker agree to {agree} "
                             f"({abs(difference) / abs(statement) * 100:.2f}%) on a LIVE read, "
                             f"band {v['band']:,.2f}")
        notes.append(f"{checked} account(s) reconcile to statement")
        if ungrounded:
            gaps.append("NO STATEMENT to reconcile against: " + ", ".join(ungrounded))
        if apart:
            notes.append("GAPS, so not judged:")
            notes.extend(f"  {a}" for a in apart)

        # ---- PRICE FRESHNESS ------------------------------------------------------------
        p = self.price_ageing(today)
        newest, oldest = pd.Timestamp(p["newest"]), pd.Timestamp(p["oldest"])
        age, spread = p["age_days"], p["spread_days"]
        prices = ([f"newest {newest:%-d %b %Y}, oldest {oldest:%-d %b %Y}",
                   f"{age} days (oldest of {p['marks']} marks) · spread {spread}d"]
                  if p["marks"] else ["no marks yet", "nothing to age"])
        if age > self.D.PRICE_AGE_LIMIT:
            problems.append(f"prices are {age} days old — past the {self.D.PRICE_AGE_LIMIT}-day "
                            f"limit, refresh before relying on them")
        if spread > self.D.PRICE_SPREAD_LIMIT:
            problems.append(f"price marks span {spread} days ({oldest.date()} to {newest.date()}) "
                            f"— past the {self.D.PRICE_SPREAD_LIMIT}-day spread limit. A ticker "
                            f"was probably missed in the last sweep; the newest mark being fresh "
                            f"hides it")

        # ---- JUDGEMENTS OWED ------------------------------------------------------------
        owed = self.theses_owed()
        notes.append(f"reasoning: {len(owed)} owed (from "
                     f"{self.D.REVIEW_FROM:%-d %b %Y}, on entry and on exit)")
        gaps.extend(f"reasoning owed — {o['ticker']}"
                    + (f" in {o['account']}" if o["account"] else "")
                    + f": {o['half']}, since {o['since']}" for o in owed)

        # ---- FUNDING: every night a daily funded leg was held has its row -----------------
        unfunded = self.funding_gaps()
        notes.append(f"funding: {len(self.D.DAILY_FUNDED_LEGS)} daily funded leg(s), "
                     f"{len(unfunded)} night(s) with no funding-interest row")
        gaps.extend(f"funding interest missing — {a}: {leg} held overnight {night} with no row"
                    for a, leg, night in unfunded)

        # ---- DATED RATES: every date a figure converts at has that day's close ----------
        owed = self.rate_gaps(today)
        notes.append(f"dated rates: {len(owed)} owed a TradingView close")
        gaps.extend(f"rate owed — {g['currency']} {g['date']} ({g['why']}): no TradingView "
                    f"close on file for it" for g in owed)

        # ---- conversions: income in another currency, and its rate's age ---------------
        note, stale = self._conversion_state()
        if note:
            notes.append(note)
        problems.extend(stale)

        # ---- THE EVIDENCE CHAIN ---------------------------------------------------------
        note, problem = self._evidence_chain()
        notes.append(note)
        if problem:
            problems.append(problem)

        # ---- RECORD TIME ----------------------------------------------------------------
        notes.append(self._journal_state())

        return {"problems": problems, "gaps": gaps, "notes": notes, "prices": prices}

    def funding_gaps(self) -> list[tuple[str, str, str]]:
        """Nights a daily funded leg was held with no funding-interest row charging for them:
        (account, leg, night), from the later of the leg's opening and the account's first
        capital movement, to the night before it closed or last night while it is held. The load
        holds every row to such a leg; this asks the other way round, work the record is owed.
        PER ACCOUNT AND NIGHT: IG's row charges the account's daily legs for a night together,
        so a night one row names is charged for every such leg the account held.

        Side effects: none.
        """
        charged: dict[str, set] = {}
        for r in self.D.ci_rows:
            if r.category == "Funding interest":
                charged.setdefault(r.account, set()).update(
                    pd.Timestamp(n) for n in self.D.funding_nights(r.detail, r.date))
        moved = self.store["movements"]
        begins = pd.to_datetime(moved["date"]).groupby(moved["account"]).min().to_dict()
        today = pd.Timestamp.today().normalize()
        out = []
        for account, leg, opened, closed in self.D.DAILY_FUNDED_LEGS:
            night = max(pd.Timestamp(opened), begins.get(account, pd.Timestamp(opened)))
            end = pd.Timestamp(closed) if closed else today
            while night < end:
                if night not in charged.get(account, set()):
                    out.append((account, leg, night.date().isoformat()))
                night += pd.Timedelta(days=1)
        return out

    def _conversion_state(self) -> tuple[str, list[str]]:
        """Foreign-currency income, and how far its rate sat from the event: (note, problems).
        A PROBLEM past `rules.FX_RATE_AGE_LIMIT_DAYS`: the book would add a figure computed at a
        rate nobody fetched for the day, and the fix is to fetch one."""
        try:
            conv = self.conversions()
            if conv.empty:
                return "", []
            limit = self.D.FX_RATE_AGE_LIMIT_DAYS
            # THE ROWS WITH A RATE, for the furthest: a row with none has no distance, and taking
            # the max over it raised, which dropped every problem below — the row with no rate
            # among them, the one this check exists for.
            apart = [int(d) for d in conv["days_apart"] if d is not None and pd.notna(d)]
            note = (f"conversions: {len(conv)} foreign-currency income row(s) · "
                    + (f"rate up to {max(apart)}d before the event, limit {limit}d" if apart
                       else "none with a rate on file"))
            return note, [
                (f"{r.account} {str(r.date)[:10]}: {r.currency} {r.local_amount} converted at "
                 f"the close of {r.rate_date} — {r.days_apart} days before the event, past the "
                 f"{limit}-day limit. Fetch the rate for the day.") if pd.notna(r.days_apart)
                else (f"{r.account} {str(r.date)[:10]}: {r.currency} {r.local_amount} has no "
                      f"close on file on or before its date. Fetch the rate for the day.")
                for r in conv[conv["stale"]].itertuples()]
        except Exception as e:                       # noqa: BLE001 — never fail over this check
            # NOT CHECKED IS A PROBLEM, not a note: answered with no problems, a check that could
            # not run let the record read as in good order.
            return (f"conversions: unknown ({type(e).__name__})",
                    [f"conversions could not be checked: {type(e).__name__}: {e}"])

    def _evidence_chain(self) -> tuple[str, str | None]:
        """How many rows citing a broker document can reach it, in one line, and a problem if any
        cannot, whatever its date. A row that cites no document is not counted and is not a gap:
        an IG read is retrieved by the dealId it stores. The rows labelled `not-on-file` are
        counted beside it, so the line says how much of the record no document holds."""
        try:
            names = self.D.schema.filed_statements()
            if not names:
                return "evidence: _archive/statements/ is empty or absent — limb 3 unverifiable", None
            # THE ROW'S ACCOUNT TRAVELS WITH IT: a trade's source names the document's kind and
            # date only, and a date is not a document until the account narrows it.
            rows = ([(t.id, t.source, t.broker_ref, t.acct) for t in self.D.trades]
                    + [(e.eid, e.source, e.broker_ref, e.acct) for e in self.D.exits])
            cites, gaps, absent = 0, [], 0
            for rid, src, ref, acct in rows:
                ev = self.D.evidence_from_source(src)
                absent += bool(ev and ev.key in self.D.CLOSED_TO_NEW_ENTRIES)
                ok = self.D.reference_resolves(src, names, ref, acct)
                if ok is None:
                    continue
                cites += 1
                if not ok:
                    gaps.append(rid)
            line = (f"evidence: {cites - len(gaps)} of {cites} rows citing a document reach it "
                    f"in _archive/statements/ · {absent} not on file")
            if not gaps:
                return line, None
            return (f"{line} · {len(gaps)} cannot",
                    f"{len(gaps)} row(s) cite a document that is in no archived filename: "
                    f"{', '.join(sorted(gaps))} — file it, or correct the row's source")
        except Exception as e:                       # noqa: BLE001 — never fail over provenance
            return f"evidence: unknown ({type(e).__name__})", None

    def _journal_state(self) -> str:
        """What the journal accounts for, in one line. A difference is a FINDING, not a problem:
        a hand edit with a commit message is a correction the store allows."""
        try:
            opened = self.journal_opened()
            if opened is None:
                return "journal: no opening count — nothing to reconcile against"
            off = self.journal_unaccounted()
            wrote = self.journal(since=opened)
            if off.empty:
                return (f"journal: every row accounted for since {pd.Timestamp(opened):%-d %b %Y} · "
                        f"{len(wrote)} write(s) recorded")
            parts = "; ".join(f"{r['table']} {r['unaccounted']:+d}"
                              for r in off.to_dict("records"))
            return (f"journal: {len(off)} table(s) hold rows no route accounts for — {parts}. "
                    f"That is a hand edit; git log will say which.")
        except Exception as e:                       # noqa: BLE001 — never fail over the journal
            return f"journal: unknown ({type(e).__name__})"
