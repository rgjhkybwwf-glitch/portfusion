"""The Book's round trips, company lives and investment activity."""

from __future__ import annotations

import pandas as pd

from portfusion.engine.store import _lookup
from portfusion.engine.ledger import _buy_cost
from portfusion.engine.core import Core


class Trades(Core):

    # ---- ROUND TRIPS -----------------------------------------------------------------

    def round_trips(self, ticker: str | None = None, account: str | None = None,
                    start: str | None = None, end: str | None = None,
                    company: str | None = None) -> pd.DataFrame:
        """Closed round trips, per realisation. THE JOIN -- three tables, one key.

        Carries the ENTRY DATE and PRICE PAID as well as the exit, because those show the return
        on an investment; a position opened before the baseline and closed after it is a complete
        round trip. Entry and exit prices are in the share's own currency (`currency`), each a
        quantity-weighted mean of its deals' own prices (`deal_prices()`); the money is sterling.
        `start` and `end` bound the day a trip closed, and `start` counts its day, as the Round
        Trips page's From asks.
        """
        ex = pd.DataFrame([{"sale_id": e.sale_id, "date": e.date, "account": e.acct,
                            "ticker": e.ticker, "qty": e.size, "traded_price": e.traded_price,
                            "proceeds": e.proceeds} for e in self.D.sales],
                          columns=["sale_id", "date", "account", "ticker", "qty", "traded_price",
                                   "proceeds"])
        ex["realisation_id"] = ex["sale_id"].map(self.D.REALISATION_BY_EXIT)
        ex["cost_released"] = ex["sale_id"].map(self.cost_released)
        ex["date"] = pd.to_datetime(ex["date"])

        rt = (ex.groupby("realisation_id", as_index=False)
                .agg(ticker=("ticker", "first"), account=("account", "first"),
                     sells=("sale_id", "count"), closed=("date", "max"),
                     qty=("qty", "sum"), proceeds=("proceeds", "sum"),
                     cost=("cost_released", "sum")))

        # Entry date: a share realisation's is the day its holding opened (`share_pools()`), a
        # spread bet's the earliest leg its sales named.
        L = self.ledger
        sold = L[L["direction"] == "Sell"].sort_values(["date", "event_id"])
        legs = L[(L["direction"] == "Buy") & L["realisation_id"].notna()]
        rt["opened"] = _lookup(rt["realisation_id"],
                               sold.groupby("realisation_id")["pool_opened"].min())
        rt["opened"] = rt["opened"].fillna(
            _lookup(rt["realisation_id"], legs.groupby("realisation_id")["date"].min()))

        rt["days_held"] = (rt["closed"] - rt["opened"]).dt.days

        # EVERY ROUND TRIP IS NAMED ALIKE: its company from identity, its kind from its sales, and
        # its note from its latest sale, which says what happened.
        company_of = self._identity().set_index("ticker")["company"]
        kind = sold.groupby("realisation_id")["held_as"].first()
        last_note = sold.groupby("realisation_id")["note"].last()
        rt["company"] = rt["ticker"].map(company_of)
        rt["held_as"] = rt["realisation_id"].map(kind)
        rt["note"] = [last_note.get(r) for r in rt["realisation_id"]]
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
            p = deals["event_id"].map(own)
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
            self._identity().set_index("ticker")["currency"]).where(~is_sb, "GBP")
        rt["stake"] = rt["qty"].where(is_sb)
        rt["entry_level_points"] = rt["entry_price"].where(is_sb).round(2)
        rt["exit_level_points"] = rt["exit_price"].where(is_sb).round(2)
        rt["realised"] = rt["proceeds"] - rt["cost"]
        rt["realised_pct"] = rt["realised"] / rt["cost"]
        rt["pre_baseline"] = rt["opened"] < self.baseline
        # BY EXIT DATE, MOST RECENT FIRST — a realisation log reads what happened lately first —
        # with a stable tie-break on the realisation id, as activity() uses: several realisations
        # share an exit date, and an unstable order would reshuffle rows with nothing changed.
        # Sorted here, once, for every renderer. SELECTION lives here too: `closed` is the EXIT
        # date, the date a round trip is filed under.
        if ticker:
            rt = rt[rt["ticker"] == ticker]
        # A COMPANY IS EVERY CODE IT IS HELD UNDER, shares and spread bets both:
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
                "realised": round(float(rt["realised"].sum()), 2)}

    # ---- THE COMPANY LIFE  —  a company's shares and bets, first purchase to final sale ------

    def _lives(self) -> list[dict]:
        """EVERY COMPANY LIFE: {company, opened, closed, buys, sales}, `closed` None while held.
        A purchase while nothing of the company is held opens one; the day nothing is held closes
        it. A day's buys come before its sales, as in `share_pools()`."""
        if "walk" not in self._lives_cache:
            self._lives_cache["walk"] = self._walk_lives()
        return self._lives_cache["walk"]

    def _walk_lives(self) -> list[dict]:
        ident = self._identity().set_index("ticker")
        L = self.ledger[self.ledger["direction"].isin(("Buy", "Sell"))]
        L = L.assign(company=L["ticker"].map(ident["company"]),
                     _sale=(L["direction"] == "Sell").astype(int))
        leg_of = self.D.EXIT_LEG_MATCH
        out = []
        for company, g in L.sort_values(["date", "_sale", "event_id"], kind="stable").groupby(
                "company", sort=True):
            shares, bets, life = {}, set(), None
            for day, d in g.groupby("date", sort=True):
                for r in d.to_dict("records"):
                    held = bets or any(q > 0 for q in shares.values())
                    if r["direction"] == "Buy" and life is None and not held:
                        life = {"company": company, "opened": day, "closed": None,
                                "buys": [], "sales": []}
                    if life is None:
                        raise ValueError(f"{r['event_id']} sells {r['ticker']} "
                                         f"on {day:%Y-%m-%d} with "
                                         f"nothing of {company} held")
                    if r["held_as"] == "shares":
                        key = (r["acct"], r["ticker"])
                        shares[key] = shares.get(key, 0) + (
                            r["qty"] if r["direction"] == "Buy" else -r["qty"])
                    elif r["direction"] == "Buy":
                        bets.add(r["event_id"])
                    else:
                        bets.discard(leg_of.get(r["event_id"]))
                    life["buys" if r["direction"] == "Buy" else "sales"].append(r)
                if life and not bets and not any(q > 0 for q in shares.values()):
                    life["closed"] = day
                    out.append(life)
                    life = None
            if life:
                out.append(life)
        return out

    def _life_income(self) -> tuple[dict, list]:
        """EACH LIFE'S DIVIDENDS AND FUNDING, {(company, opened): {"dividends": [(date, amount)],
        "funding_interest": [...]}}, and the income rows no life takes. A dividend goes to the life open on
        its date, else the last one closed before it. Funding goes to the daily-funded legs held on
        the nights it names, split by entry size; a dated contract's is in its level already."""
        if "income" not in self._lives_cache:
            self._lives_cache["income"] = self._attribute_income(self._lives())
        return self._lives_cache["income"]

    def _attribute_income(self, lives: list[dict]) -> tuple[dict, list]:
        ident = self._identity().set_index("ticker")
        by_company: dict[str, list] = {}
        for lv in lives:
            by_company.setdefault(lv["company"], []).append(lv)
        out = {(lv["company"], lv["opened"]): {"dividends": [], "funding_interest": []} for lv in lives}
        loose = []

        def life_on(company, day):
            day = pd.Timestamp(day)
            held = [lv for lv in by_company.get(company, []) if lv["opened"] <= day
                    and (lv["closed"] is None or day <= lv["closed"])]
            after = [lv for lv in by_company.get(company, [])
                     if lv["closed"] is not None and lv["closed"] < day]
            return held[0] if held else after[-1] if after else None

        life_of_leg = {r["event_id"]: lv for lv in lives for r in lv["buys"]}
        size = {r["event_id"]: abs(r["qty"] * r["level_points"]) for lv in lives for r in lv["buys"]
                if r["held_as"] == "spread bet"}
        for r in self.D.ci_rows:
            if r.category == "Dividend":
                company = ident.at[r.ticker, "company"] if r.ticker in ident.index else None
                lv = life_on(company, r.date) if company else None
                if lv is None:
                    loose.append(r)
                    continue
                out[(lv["company"], lv["opened"])]["dividends"].append(
                    (pd.Timestamp(r.date), r.amount))
            elif r.category == "Funding interest":
                pairs = [(leg, n) for n in self.D.funding_nights(r.detail, r.date)
                         for account, leg, opened, closed in self.D.DAILY_FUNDED_LEGS
                         if account == r.account and opened <= n and (closed is None or n < closed)
                         and leg in life_of_leg]
                weight = sum(size.get(leg, 0.0) for leg, _ in pairs)
                if not pairs or not weight:
                    loose.append(r)
                    continue
                for leg, _ in pairs:
                    lv = life_of_leg[leg]
                    out[(lv["company"], lv["opened"])]["funding_interest"].append(
                        (pd.Timestamp(r.date), r.amount * size.get(leg, 0.0) / weight))
        return out, loose

    def company_lives(self, company: str | None = None, start: str | None = None,
                      end: str | None = None) -> pd.DataFrame:
        """EACH COMPANY LIFE (`_lives()`), one row; the by-holding view is `round_trips()`.

          life_gain            realised + unrealised (open lives) + dividends + funding
                               interest, sterling
          life_pct             life_gain over exposure at entry: shares at cost, bets at notional
          qty                  shares plus open bets as share-equivalents, whole
          life_cost_per_share  (cost of what is held − realised − dividends − funding interest)
                               / qty, in the position's currency, dealing included, each sum at
                               its own day's close: the break-even price of what is held

        `pre_baseline`: opened before the record, so earlier dividends are not on file. `start` and
        `end` bound the close; either one drops open lives. Blank wherever a rate is not on file.
        """
        if "frame" not in self._lives_cache:
            self._lives_cache["frame"] = self._life_rows()
        out = self._lives_cache["frame"]
        if company:
            out = out[out["company"] == company]
        if start or end:
            out = out[out["closed"].notna()]
        if start:
            out = out[out["closed"] >= pd.Timestamp(start)]
        if end:
            out = out[out["closed"] <= pd.Timestamp(end)]
        return out.reset_index(drop=True)

    def _life_rows(self) -> pd.DataFrame:
        """`company_lives()`'s rows, every life, in its order."""
        gain = {e.sale_id: e.proceeds - self.cost_released[e.sale_id] for e in self.D.sales}
        lines = self.holdings(by="ticker")
        companies = self.holdings(by="issuer").set_index("company")
        order = {a: i for i, a in enumerate(self.D.ACCOUNT_ORDER)}
        today = pd.Timestamp.today().normalize()

        lives = self._lives()
        income, _ = self._life_income()
        rows = []
        for life in lives:
            name, buys, sales = life["company"], life["buys"], life["sales"]
            earned = income[(name, life["opened"])]
            dividends = float(sum(a for _, a in earned["dividends"]))
            funding = float(sum(a for _, a in earned["funding_interest"]))
            is_open = life["closed"] is None
            kinds = {r["held_as"] for r in buys + sales}
            realised = float(sum(gain[r["event_id"]] for r in sales))
            mine = lines[lines["company"] == name] if is_open else lines.iloc[0:0]
            unrealised = float(mine["unrealised"].sum()) if is_open else 0.0
            held = mine[mine["held_as"] == "shares"]
            shares_held = float(held["qty"].sum()) if len(held) else None
            row = companies.loc[name] if is_open and name in companies.index else None
            ccy = row["currency"] if row is not None else None

            bet_qty = row["bet_qty"] if row is not None else None
            bet_qty = None if bet_qty is None or bet_qty != bet_qty else float(bet_qty)
            whole = (shares_held or 0.0) + (bet_qty or 0.0)
            net = None
            if whole and ccy and (bet_qty is not None or not mine["held_as"].eq("spread bet").any()):
                cost, complete = (float(row["bet_cost"]) if bet_qty else 0.0), True
                # EACH ACCOUNT'S POOL AT ITS OWN AVERAGE: its open legs' cost over their quantity,
                # times what that account holds, as `share_pools()` keeps a pool.
                pools: dict[tuple, list] = {}
                for r in buys + sales:
                    if r["held_as"] == "shares":
                        pools.setdefault((r["acct"], r["ticker"]), []).append(r)
                for rs in pools.values():
                    h = sum(r["qty"] if r["direction"] == "Buy" else -r["qty"] for r in rs)
                    legs = [r for r in rs if r["direction"] == "Buy" and r["open_leg"]]
                    n = sum(r["qty"] for r in legs)
                    if h <= 0:
                        continue
                    paid = 0.0
                    for r in legs:
                        rate = self._per_pound(ccy, r["date"])
                        if rate is None:
                            complete = False
                            break
                        paid += r["cost"] * rate
                    if not complete or not n:
                        complete = False
                        break
                    cost += paid / n * h
                taken = 0.0
                for day, amount in ([(r["date"], gain[r["event_id"]]) for r in sales]
                                    + earned["dividends"] + earned["funding_interest"]):
                    rate = self._per_pound(ccy, day)
                    if rate is None or amount != amount:
                        complete = False
                        break
                    taken += amount * rate
                net = (cost - taken) / whole if complete else None

            # WHAT WAS BOUGHT: shares at their cost, bets at their size at entry (stake x level).
            bought = sum(_buy_cost(r["qty"], r["cost"], r["level_points"], r["mode"])
                         for r in buys)
            accounts = sorted({r["acct"] for r in buys + sales}, key=lambda a: order.get(a, 99))
            rows.append({
                "life": f"{name} · {life['opened']:%Y-%m-%d}",
                "company": name,
                "held_as": kinds.pop() if len(kinds) == 1 else "mixed",
                "accounts": " · ".join(accounts),
                "opened": life["opened"],
                "closed": life["closed"],
                "days_held": int(((life["closed"] if not is_open else today)
                                  - life["opened"]).days),
                "state": "closed" if not is_open else "part closed" if sales else "open",
                "sales": len(sales),
                "realised": realised,
                "unrealised": unrealised if is_open else None,
                "dividends": dividends,
                "funding_interest": funding,
                "life_gain": realised + unrealised + dividends + funding,
                "life_pct": (realised + unrealised + dividends + funding) / bought if bought else None,
                "shares_held": shares_held,
                "qty": float(round(whole)) if is_open and (bet_qty is not None or not len(
                    mine[mine["held_as"] == "spread bet"])) and whole else None,
                "life_cost_per_share": net,
                "entry_price": row["entry_price"] if row is not None else None,
                "price": row["price"] if row is not None else None,
                "currency": ccy,
                "pre_baseline": life["opened"] < self.baseline,
                "realisations": sorted({r["realisation_id"] for r in sales
                                        if isinstance(r["realisation_id"], str)}),
                "lines": sorted(mine["ticker"]),
            })

        out = pd.DataFrame(rows, columns=[
            "life", "company", "held_as", "accounts", "opened", "closed", "days_held", "state",
            "sales", "realised", "unrealised", "dividends", "funding_interest", "life_gain", "life_pct",
            "shares_held", "qty", "life_cost_per_share", "entry_price", "price", "currency",
            "pre_baseline",
            "realisations", "lines"])
        out = out.assign(_open=out["closed"].isna(),
                         _when=out["closed"].fillna(out["opened"]))
        return (out.sort_values(["_open", "_when", "life"], ascending=[False, False, True])
                   .drop(columns=["_open", "_when"]).reset_index(drop=True))

    def company_life_totals(self, company: str | None = None, start: str | None = None,
                            end: str | None = None) -> dict[str, float]:
        """Totals over every company life, or a selection of them. Unfiltered, `realised` is
        realised() and `unrealised` is unrealised(), reached by company rather than by line, and
        `dividends` and `funding_interest` are the income rows a life takes (`_life_income()`)."""
        lv = self.company_lives(company=company, start=start, end=end)
        return {"lives": int(len(lv)),
                "open": int(lv["closed"].isna().sum()),
                "realised": round(float(lv["realised"].sum()), 2),
                "unrealised": round(float(lv["unrealised"].fillna(0).sum()), 2),
                "dividends": round(float(lv["dividends"].sum()), 2),
                "funding_interest": round(float(lv["funding_interest"].sum()), 2),
                "life_gain": round(float(lv["life_gain"].sum()), 2)}

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
        if any(t.ticker == ticker and t.mode == "sb" for t in self.D.buys):
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
        currency = self._identity().set_index("ticker")["currency"]
        reg = self.account_register()
        firm = dict(zip(reg["account"], reg["broker_firm"]))
        out = {}
        for r in self.ledger.to_dict("records"):
            own, rate, whose = None, None, None
            if r["held_as"] == "spread bet":
                own = r["level_points"] if r["direction"] == "Buy" else r["traded_price"]
            else:
                share = currency.get(r["ticker"], "GBP")
                if pd.notna(r["traded_price"]) and r["cur"] == share:
                    own = r["traded_price"]
                    if pd.notna(r["rate"]):
                        rate, whose = r["rate"], firm.get(r["acct"])
                elif pd.notna(r["traded_price"]):
                    day, close = self._close_on(share, r["date"])
                    if day == r["date"].date().isoformat():
                        own, rate, whose = r["traded_price"] * close, close, "TradingView close"
                elif share == "GBP" and r["direction"] == "Buy" and r["qty"]:
                    own = r["cost"] / r["qty"]
            out[r["event_id"]] = (own, rate, whose)
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
        out = L[["date", "event_id", "direction", "acct", "ticker", "qty", "stake",
                 "realisation_id", "broker_ref", "held_as",
                 "source", "note", "contract"]].copy()
        # THE MONEY, one column meaning one thing: a buy's cost, a bet's at its stake times its
        # level, and a sale's proceeds.
        bought = L["cost"].where(L["mode"] != "sb", L["qty"] * L["level_points"])
        out.insert(out.columns.get_loc("stake") + 1, "value",
                   bought.where(L["direction"] == "Buy", L["proceeds"]))
        out = out.rename(columns={"acct": "account"})
        out.loc[out["direction"].eq("Buy") & out["held_as"].eq("shares") & out["value"].eq(0),
                "direction"] = "Adjustment"
        # A BET LEG'S CONTRACT AND HOW IG FUNDS IT (schema.FUNDINGS): blank on a share and on a
        # sale, which names its leg instead.
        out["funding"] = out["contract"].map(self.D.CONTRACT_FUNDING)
        # WHAT A SALE REALISED, on the sale's own row: its GBP proceeds less the cost it released
        # (`cost_released`). Blank on a buy. Two legs closed at one price read alike without it.
        out["realised"] = (out["value"] - out["event_id"].map(self.cost_released)) \
            .where(out["direction"] == "Sell")

        # THE TRADED PRICE, in the share's own currency, and the rate it stands at with whose it
        # is (`deal_prices()`): the deal's own price, never one worked out from its sterling.
        # Blank where no document on file states one, and FX at trade blank on a sterling deal in
        # a London share, which needed no rate. A SPREAD BET TRADES AT PARITY whatever the
        # underlying's currency: its price is its level, and its currency sterling.
        deal = self.deal_prices()
        out["currency"] = out["ticker"].map(self._identity().set_index("ticker")["currency"]) \
            .where(out["held_as"].ne("spread bet"), "GBP")
        out["traded_price"] = out["event_id"].map(deal["price_own"])
        out["fx_at_trade"] = out["event_id"].map(deal["rate"])
        out["fx_from"] = out["event_id"].map(deal["rate_from"])

        # A SPREAD BET IN ITS OWN TERMS: a stake per point, at a level in points, as the record
        # keeps them — the ledger's qty on a bet is its stake, and its prices are levels. Blank
        # on a share.
        is_sb = out["held_as"].eq("spread bet")
        out["stake"] = out["qty"].where(is_sb)
        out["level_points"] = out["traded_price"].where(is_sb).round(2)
        # EACH ROW'S OWN ID UNDER ITS OWN NAME, as the store keeps it: a buy's (an adjustment is
        # one) its `trade_id`, a sale's its `sale_id`, the other blank.
        sold = out["direction"].eq("Sell")
        at = out.columns.get_loc("event_id")
        out.insert(at, "sale_id", out["event_id"].where(sold))
        out.insert(at, "trade_id", out["event_id"].where(~sold))
        # NEWEST FIRST, then id: the event-log rule test_trades_are_newest_first_with_a_stable_tie_break holds,
        # with a stable tie-break so rows sharing a date cannot reorder between builds.
        return (out.sort_values(["date", "event_id"], ascending=[False, False])
                   .drop(columns="event_id").reset_index(drop=True))
