"""The Book at a past date, and what moved since."""

from __future__ import annotations

import pandas as pd

from portfusion.engine.bases import BasisError, MissingMark
from portfusion.engine.ledger import _buy_cost
from portfusion.engine.valuation import rate_now
from portfusion.engine.core import Core


class PastDates(Core):

    # ---- VALUING AT A PAST DATE  —  what makes a report REPRODUCIBLE -----------------

    #
    # Freeze the INPUTS, not the output: a report regenerates identically because the marks it
    # valued at are dated rows in the histories, which keep every mark a dated figure takes. Valuing a past quarter at today's
    # prices would give a number that changes every time it is asked for.
    def _marks_at(self, as_of: str, window: int | None = None) -> tuple[dict, dict]:
        """Prices and FX as at a date — the newest mark ON OR BEFORE it, per instrument.

        On or before, because a mark does not exist for every instrument every day; never AFTER,
        which would value a quarter with information that did not exist yet.

        WITH A `window`, A QUARTER END BEING FROZEN: each
        instrument takes its mark NEAREST `as_of` within `window` days either side, the earlier on
        a tie, and falls back to the newest on or before when none is that near — `freeze_rows()`
        names every line the window did not reach.

        """
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
        px = pick(ph, "mark_key", "price")
        fx = pick(fh[fh["kind"] == "spot"], "currency", "rate")
        return px, fx

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
        sold_on = dict(zip(sells["event_id"], sells["date"]))
        leg_sold = {tid: sold_on[eid] for eid, tid in self.D.EXIT_LEG_MATCH.items()}
        out: dict[str, dict] = {}
        for r in self.ledger.to_dict("records"):
            if not (r["pre_baseline"] or r["date"] <= d) or r["begins"] > d:
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
                    sold = leg_sold.get(r["event_id"], closed_on.get(rid))
                    if sold is not None and sold <= d:
                        continue        # this leg was gone by the date asked about
            key = self.D.LEG_CONTRACT.get(r["event_id"]) if r["mode"] == "sb" else r["ticker"]
            if key is None:
                continue
            held = -r["qty"] if r["direction"] == "Sell" else r["qty"]
            out[r["event_id"]] = {"ticker": r["ticker"], "key": key, "qty": held,
                            "cost": r["cost"], "level_points": r["level_points"],
                            "mode": r["mode"], "date": r["date"],
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
        its marks are keyed by contract (`load_store()` refuses one under the bet's own code): a
        lookup keyed by ticker keeps one contract and values a multi-contract position at one
        level, saying nothing.
        """
        lots = {k: q for (tk, k), q in self._held_by_mark_key(as_of, account).items()
                if tk == ticker}
        splittable = (lots and ticker not in lots
                      and abs(sum(lots.values()) - qty) < 1e-9
                      and all(k in px for k in lots))
        if splittable:
            return [(k, px[k][1], lots[k]) for k in sorted(lots)]
        if ticker in px:
            return [(ticker, px[ticker][1], qty)]
        missing = sorted(k for k in lots if k not in px) or [ticker]
        raise MissingMark(missing,
            f"no price for {missing[0]} on or before {as_of}: nothing is valued from a mark "
            f"that does not exist.")

    @staticmethod
    def _converts_from(ticker: str, ident: pd.DataFrame) -> str | None:
        """The currency a line's local value is converted from at a date, or None: a spread bet
        is £/point at parity, so NO FX applies, and a sterling line needs no rate."""
        if ident.at[ticker, "held_as"] == "spread bet":
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
        ident = self._identity().set_index("ticker")
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
        converts at with no TradingView close on file to serve it. These dates need one:

          quarter end   each quarter end on file, for every currency a share held then is priced in
          income        each income row paid in another currency, on its own date, unless its
                        broker states the rate
          typed         each date fx-history.csv holds a typed rate on, which that day's close
                        replaces
          deal          each share deal priced in sterling on a share in another currency, on its
                        own date: the close gives the share's own price (`deal_prices()`)
          life          each sale, share leg still held, dividend and funding charge of an open
                        company life priced in another currency, on its own date: the close
                        puts it into that currency (`company_lives()`'s life cost per share)
          bet           each open spread-bet leg, on its own date, in its listing's currency
                        and its company's share listings' where either is not sterling: the
                        closes turn its stake into share-equivalents and its level into the
                        shares' currency (`company_positions()`)

        A DATE IS SERVED BY ITS NEWEST SESSION'S CLOSE: the newest spot rate on or before it
        is a close, dated that day or on the weekday before a weekend. A date not yet past is
        owed nothing. Rows {currency, date, why, rate}, oldest first, as the audit and the Price
        Refresh name them. Side effects: none.
        """
        day = (pd.Timestamp(today) if today else pd.Timestamp.today()).normalize()
        fh = self.store["history.fx"]
        spot = fh[fh["kind"] == "spot"]
        ident = self._identity().set_index("ticker")
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
        priced = L[L["traded_price"].notna() & L["cur"].eq("GBP")]
        for ticker, date in zip(priced["ticker"], priced["date"]):
            cur = ident.at[ticker, "currency"] if ticker in ident.index else "GBP"
            if cur != "GBP":
                wanted.setdefault((cur, date.date().isoformat()), "deal")
        held = self.ledger[self.ledger["open_leg"]]
        listed = held[held["held_as"].eq("shares")]["ticker"].map(ident["currency"]).groupby(
            held["ticker"].map(ident["company"])).agg(set)
        bets = held[held["held_as"].eq("spread bet")]
        for ticker, date in zip(bets["ticker"], bets["date"]):
            own = ident.at[ticker, "currency"] if ticker in ident.index else "GBP"
            for cur in {own} | listed.get(ident.at[ticker, "company"], set()):
                if cur != "GBP":
                    wanted.setdefault((cur, date.date().isoformat()), "bet")

        priced_in = self.holdings(by="issuer").set_index("company")["currency"]
        earned, _ = self._life_income()
        for life in self._lives():
            cur = priced_in.get(life["company"])
            if life["closed"] is None and cur not in (None, "GBP"):
                inc = earned[(life["company"], life["opened"])]
                days = ([r["date"] for r in life["sales"]]
                        + [r["date"] for r in life["buys"]
                           if r["held_as"] == "shares" and r["open_leg"]]
                        + [d for d, _ in inc["dividends"] + inc["funding_interest"]])
                for d in days:
                    wanted.setdefault((cur, pd.Timestamp(d).date().isoformat()), "life")

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
        ident = self._identity().set_index("ticker")

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
                         "held_as": ident.at[ticker, "held_as"],
                         "qty": r["qty"], "cost": r["cost"], "value": value,
                         "priced_at": priced_at})
        # NAMED COLUMNS, so an account holding nothing that day is an empty frame rather than a
        # KeyError on "value": an IG account unfunded at a quarter end can still be frozen.
        out = pd.DataFrame(rows, columns=["ticker", "company", "sector", "region", "currency",
                                          "held_as", "qty", "cost", "value", "priced_at"])
        out["unrealised"] = out["value"] - out["cost"]
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
        L = L[(L["pre_baseline"] | (L["date"] <= d)) & ~(L["begins"] > d)].copy()

        def qty(r):
            return -r["qty"] if r["direction"] == "Sell" else r["qty"]

        def cost(r):
            return (_buy_cost(r["qty"], r["cost"], r["level_points"], r["mode"])
                    if r["direction"] == "Buy" else 0.0)

        L["signed_qty"] = L.apply(qty, axis=1)
        L["signed_cost"] = L.apply(cost, axis=1)
        out = (L.groupby("ticker", as_index=False)
                .agg(qty=("signed_qty", "sum"), cost=("signed_cost", "sum")))

        # EVERY SALE RELEASES ITS OWN COST, ON THE DAY IT HAPPENED — the leg it names or its
        # pool's average, whichever `cost_released` holds. A parcel released all at once on its
        # LAST sale would count each earlier sale's cost twice until then: once as still held,
        # once as released.
        sold = L[L["direction"] == "Sell"]
        rel = sold["event_id"].map(self.cost_released).groupby(sold["ticker"]).sum()
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

        `quarter_snapshots` is one row per line of each account's block, exactly as HOLDINGS shows
        it: a spread-bet leg at NOTIONAL, its local price the value over the quantity, an account
        holding nothing as "(no positions)". `quarter_nav` is each account's contribution to net
        asset value — positions at market, or a spread-bet account's equity with its notional
        beside it for the exposure archive.

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
        order = [a for a in self.accounts_open(as_of) if accounts is None or a in accounts]
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
                              "qty": None, "price": None, "currency": None, "value": 0.0,
                              "cost": 0.0, "quality": "derived",
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
                sources = [str(ph[(ph["mark_key"] == k) & (ph["date"] == px[k][0])]["source"]
                               .iloc[-1]) for k in keys]
                snaps.append({"as_of": as_of, "account": account, "ticker": r.ticker,
                              "qty": int(r.qty) if float(r.qty).is_integer() else float(r.qty),
                              "price": round(local / r.qty, 6), "currency": r.currency,
                              "value": round(float(r.value), 2),
                              "cost": round(float(r.cost), 2), "quality": "derived",
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
        sale's date as `priced_at`. Left out, it would vanish while a part-close beside it shows.
        One sold before the newest outgoing mark belongs to an earlier window.

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
        dates_of = {k: sorted(set(g["date"])) for k, g in prices.groupby("mark_key")}
        ident = self._identity().set_index("ticker")

        # AN EXIT BELONGS TO THE MARK KEY ITS REALISATION'S BUY LEGS SAT ON. A pool sale
        # consumed no named leg, so it falls back to the ticker — which is right, because a
        # pooled position is a share and a share is priced by ticker.
        rid_keys: dict[str, set] = {}
        for r in self.ledger[self.ledger["direction"] == "Buy"].to_dict("records"):
            rid = r["realisation_id"]
            if rid is None or pd.isna(rid):
                continue
            k = self.D.LEG_CONTRACT.get(r["event_id"]) if r["mode"] == "sb" else r["ticker"]
            if k:
                rid_keys.setdefault(rid, set()).add(k)

        by_id = {t.trade_id: t for t in self.D.buys}

        def _exit_key(e):
            # A SALE THAT NAMES ITS LEG SAT ON THAT LEG'S LINE, whatever else its parcel held.
            leg = by_id.get(self.D.EXIT_LEG_MATCH.get(e.sale_id))
            if leg is not None:
                return (self.D.LEG_CONTRACT.get(leg.trade_id) if leg.mode == "sb" else leg.ticker) \
                    or e.ticker
            ks = rid_keys.get(self.D.REALISATION_BY_EXIT.get(e.sale_id), set())
            return next(iter(ks)) if len(ks) == 1 else e.ticker

        # THE POPULATION IS THE LIVE BOOK'S OWN LINES, which makes the totals tie back to owned()
        # and exposure(); keyed off price-history instead, long-closed lines would join the frame.
        live_keys = set()
        for r in self.ledger[self.ledger["valued"]].to_dict("records"):
            k = self.D.LEG_CONTRACT.get(r["event_id"]) if r["mode"] == "sb" else r["ticker"]
            if k:
                live_keys.add(k)

        live_on = {r["mark_key"]: str(r["as_of"])[:10] for r in self.store["prices"].to_dict("records")}

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
        for e in self.D.sales:
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
            p1 = (float(sorted(sold, key=lambda e: str(e.date)[:10])[-1].traded_price) if ended
                  else px1[key][1])

            ticker = next(iter((legs1 or legs0).values()))["ticker"]
            known = ticker in ident.index
            synthetic = known and ident.at[ticker, "held_as"] == "spread bet"
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
            transacted = sum(_buy_cost(leg["qty"], leg["cost"], leg["level_points"], leg["mode"])
                             for i, leg in legs1.items()
                             if i not in legs0 and leg["direction"] == "Buy")
            transacted -= sum(e.proceeds for e in sold)

            change = value_to - value_from
            rows.append({
                "mark_key": key, "ticker": ticker,
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
            "mark_key", "ticker", "company", "held_as", "currency", "priced_from", "priced_at",
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

        A share's marks are under its ticker, a spread bet's under each contract it held, so a
        multi-contract line shows every contract's. A retired, unpriced contract adds nothing.

        `level` says which marks are a spread bet's LEVEL IN POINTS, as IG states it, rather than a
        price in the line's currency: a contract's.
        """
        if by == "issuer":
            company = self._identity().set_index("ticker")["company"]
            tickers = {code for code, name in company.items() if name == key}
        else:
            tickers = {key}

        # A SHARE'S TICKER IS ITS MARK KEY; a spread bet's contracts join from the open legs.
        keys = set(tickers)
        for leg in self._valued_legs_at(self.valued_at(), account).values():
            if leg["ticker"] in tickers:
                keys.add(leg["key"])

        prices = self.store["history.prices"]
        out = prices[prices["mark_key"].isin(keys)].copy()
        out["level"] = out["mark_key"].isin(set(self.D.CONTRACTS))
        return out.sort_values(["date", "mark_key"], ascending=[False, True]) \
                  .reset_index(drop=True)
