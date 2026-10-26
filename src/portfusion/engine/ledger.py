"""The derived ledger, walked from the record's buys and sales."""

from __future__ import annotations

import pandas as pd

from portfusion.record import rules as D
from portfusion.engine.store import _lookup, record_begins


# =====================================================================================
# 2 · THE DERIVED LEDGER  —  which buy legs a sale consumed, and what cost that released
# =====================================================================================

def _buy_cost(qty, cost, level_points, mode):
    """GBP cost of a buy leg.

    A spread bet holds its entry level in points rather than a total, so its cost is its
    size — the ledger's `qty` on a bet is its stake per point — times the level. Shares hold
    the settled GBP total. This asymmetry is real and it is why `mode` exists.
    """
    return qty * level_points if mode == "sb" else cost


def realised_legs() -> dict[str, str]:
    """Spread-bet leg -> the realisation that consumed it: the leg a sale names in
    `rules.EXIT_LEG_MATCH`. A share leg has no such match — it sits in a pool, and
    `share_pools()` says which realisation emptied it."""
    return {tid: D.REALISATION_BY_EXIT[eid] for eid, tid in D.EXIT_LEG_MATCH.items()}


def share_pools(ledger: pd.DataFrame) -> pd.DataFrame:
    """EVERY SHARE HOLDING'S POOL, walked from its own events — the one implementation of what a
    share sale released and what an account still holds.

    A holding is one account's shares in one ticker, and every share in it costs the average
    (S.104). Each is walked in date order — buys before sales on a day, sales in sale id
    order. A buy adds its quantity and cost; a corporate action is a buy of
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
                  .sort_values(["acct", "ticker", "date", "_sale", "event_id"], kind="stable"))
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
            members.append(r["event_id"])
            row = {"released": float("nan"), "opened": opened, "emptied": pd.NaT, "parcel": None}
            out[r["event_id"]] = row
            if r["direction"] == "Buy":
                qty += r["qty"]
                cost += _buy_cost(r["qty"], r["cost"], r["level_points"], r["mode"])
                continue
            rid = D.REALISATION_BY_EXIT[r["event_id"]]
            parcels.add(rid)
            if home.setdefault(rid, (acct, ticker, n)) != (acct, ticker, n):
                wrong.append(f"{rid} spans two holdings — {home[rid][0]} {home[rid][1]} and "
                             f"{acct} {ticker}")
            day = f"{r['date']:%Y-%m-%d}"
            if r["qty"] > qty + 1e-9:
                raise ValueError(
                    f"{r['event_id']} ({rid}) sells {r['qty']:g} {ticker} from {acct}, which held "
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
    # THE STORE'S NAMES: a buy's `cost` or `level_points` and a sale's `proceeds`, each blank on
    # the rows it is not, and `event_id`, a buy's trade id or a sale's sale id.
    buys = pd.DataFrame(D.buys, columns=D.Buy._fields).rename(columns={"trade_id": "event_id"})
    buys["direction"] = "Buy"
    # HOW EACH LEG IS COSTED, from its code's kind (`rules.Trade.mode`): a frame of NamedTuples
    # carries their fields and not their properties.
    buys["mode"] = [t.mode for t in D.buys]
    # THE LEDGER'S `qty` IS THE LINE'S SIZE IN ITS OWN UNIT: a share's count, a bet's stake per
    # point (`Trade.size`). The store keeps the two in their own columns; every roll-up here is
    # size x price, which on a bet is stake x level, the notional.
    buys["qty"] = [t.size for t in D.buys]

    # A sale's `traded_price`, `cur` and `rate` are its own, as a buy's are its.
    sells = pd.DataFrame([
        {"event_id": e.sale_id, "date": e.date, "source": e.source, "acct": e.acct,
         "ticker": e.ticker, "cur": e.cur, "qty": e.size, "stake": e.stake,
         # `broker_ref` from its column: the reference that retrieves the sale.
         "traded_price": e.traded_price, "rate": e.rate, "proceeds": e.proceeds, "mode": "sell",
         "broker_ref": e.broker_ref, "note": e.note}
        for e in D.sales
    ], columns=["event_id", "date", "source", "acct", "ticker", "cur", "qty", "stake",
                "traded_price", "rate", "proceeds", "mode", "broker_ref", "note"])
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
    rid = {e.sale_id: D.REALISATION_BY_EXIT[e.sale_id] for e in D.sales}
    rid.update(realised_legs())
    rid.update(pools["parcel"].dropna().to_dict())
    ledger["realisation_id"] = ledger["event_id"].map(rid)
    ledger["released"] = _lookup(ledger["event_id"], pools["released"])
    ledger["pool_opened"] = _lookup(ledger["event_id"], pools["opened"])
    ledger["pool_emptied"] = _lookup(ledger["event_id"], pools["emptied"])

    # THE PROVENANCE IS `source` FROM THE STORE TO THE LEDGER, as on every other table, so nothing
    # is copied under a second name; tests/test_engine_invariants.py holds every ledger row to
    # having one.

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
    # AN ACCOUNT OPENED AFTER THE BOOK holds nothing on a day before it (`rules.ACCOUNT_BEGINS`),
    # though a leg the statement it opened at carries keeps its own deal date.
    ledger["begins"] = pd.to_datetime(ledger["acct"].map(D.ACCOUNT_BEGINS))
    return ledger


def cost_released(ledger: pd.DataFrame) -> dict[str, float]:
    """GBP cost released by each sale, by sale id. Two conventions, one per kind of holding:
      * pool      -- a share sale releases its holding's average, from `share_pools()` by way of
                     the ledger's `released` column
      * leg-exact -- a spread-bet sale names the bet it closed, and releases that leg's cost
    """
    by_id = {t.trade_id: t for t in D.buys}
    released = ledger.set_index("event_id")["released"]
    out, unmatched = {}, []
    for e in D.sales:
        if pd.notna(released.get(e.sale_id)):
            out[e.sale_id] = float(released[e.sale_id])
        elif e.sale_id in D.EXIT_LEG_MATCH:
            leg = by_id[D.EXIT_LEG_MATCH[e.sale_id]]
            out[e.sale_id] = round(_buy_cost(leg.size, leg.cost, leg.level_points, leg.mode), 2)
        else:
            unmatched.append(f"{e.sale_id} ({D.REALISATION_BY_EXIT[e.sale_id]})")
    if unmatched:
        raise ValueError(
            f"{', '.join(unmatched)} released no cost: a spread-bet sale names the leg it closed "
            f"in sales.csv `closes`, and only a share sale is released from its pool.")
    return out
