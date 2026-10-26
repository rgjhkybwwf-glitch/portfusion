"""The Book's marks, holdings, judgement and allocation."""

from __future__ import annotations

import pandas as pd

from portfusion.engine.core import Core


class Positions(Core):

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
        p = p[~p["mark_key"].isin(set(self.D.STATEMENT_PRICED))]
        dates = pd.to_datetime(p["as_of"], errors="coerce").dropna()
        if dates.empty:
            return {"newest": None, "oldest": None, "spread_days": 0, "marks": 0, "age_days": 0}
        newest, oldest = dates.max(), dates.min()
        day = pd.Timestamp(today or pd.Timestamp.today().date())
        return {"newest": newest.date().isoformat(), "oldest": oldest.date().isoformat(),
                "spread_days": int((newest - oldest).days), "marks": int(len(dates)),
                "age_days": int((day - oldest).days)}

    def marks_replaceable(self) -> dict:
        """WHICH MARKS A REFRESH CAN REPLACE, which are carried, and how old each one is.

        THE WHOLE SET, deliberately: the book is refreshed whole or not at all
        (`docs/prices.md`), so the form lists everything replaceable and each row says whether it
        is `stale` against `rules.PRICE_AGE_LIMIT`, rather than filtering by age.

        A classification, so it lives in the engine and not a renderer; a `Book` method, though it
        needs no ledger, so it reads the record this Book pinned, as every desk read does.

          replaceable  every mark a refresh may replace, with its outgoing price, its age and
                       whether that age is past the limit — because a price updated without its
                       DATE makes the book claim a freshness it does not have.
          held         CARRIED lines (key `held`, glossary §5b): no feed and immaterial, at the
                       last broker price by decision. Kept apart, because a fresh date on a price
                       nobody can look up is the error being guarded against.
          fx           the live rate of each currency, saying whether it is carried and why
                       (`rules.RATE_CARRIED`), and how old it is, as a price and a reading say.
          readings     each spread-bet account's IG reading — its outgoing equity and date — the
                       one account figure a refresh replaces, read in the same pass as the levels.
        """
        R = self.D
        today = pd.Timestamp.today().normalize()
        stmt = R.STATEMENT_PRICED
        frozen = R.RATE_CARRIED

        def _dated(text: str) -> dict:
            day = pd.to_datetime(text, errors="coerce")
            return ({"as_of": None, "age_days": None} if pd.isna(day)
                    else {"as_of": day.date().isoformat(), "age_days": int((today - day).days)})

        def _row(t: str, price: float, cur: str, as_of: str, src: str, struck: str, at: str) -> dict:
            age = int((today - pd.Timestamp(as_of)).days)
            return {"mark_key": t, "price": price, "currency": cur, "as_of": as_of, "source": src,
                    "struck": struck, "at": at, "age_days": age, "stale": age > R.PRICE_AGE_LIMIT,
                    # AN IG CONTRACT'S PRICE IS A LEVEL IN POINTS, beside the market's currency.
                    "contract": t in R.CONTRACTS}

        return {
            "today": today.date().isoformat(),
            "age_limit": R.PRICE_AGE_LIMIT,
            "replaceable": [_row(*r) for r in R.CURRENT_PRICES if r[0] not in stmt],
            "held": [dict(_row(*r), why=stmt[r[0]]) for r in R.CURRENT_PRICES if r[0] in stmt],
            "fx":   [{"currency": cur, "rate": rate, "source": src, "struck": struck,
                      "carried": cur in frozen, "why": frozen.get(cur), **_dated(as_of)}
                     for cur, rate, as_of, src, struck in R.fx_rows],
            "readings": [{"account": r.acct, "equity": r.equity, "as_of": str(r.as_of)[:10],
                          "age_days": int((today - pd.Timestamp(r.as_of)).days)}
                         for r in R.ac_rows if R.ACCOUNT_KIND.get(r.acct) == "spread bet"],
        }

    def priced_unheld(self) -> list[str]:
        """The lines `current-prices.csv` prices that nothing holds, sorted: a share no account
        holds a share of, or a contract no open leg is on. A sale retires its line's price as it
        empties it (`desk/doors/marks.py`), so any here is a mark nobody needs."""
        L = self.ledger
        open_legs = L[L["open_leg"]]
        held = set(open_legs.loc[open_legs["held_as"] == "shares", "ticker"])
        held |= {self.D.LEG_CONTRACT[i] for i in open_legs["event_id"] if i in self.D.LEG_CONTRACT}
        return sorted(set(self.store["prices"]["mark_key"]) - held)

    # ---- IDENTITY  —  code -> issuer -> sector / region ------------------------------

    #
    # Joined securities.company -> companies.company, by full legal name, because one issuer can
    # hold several codes.
    def _identity(self) -> pd.DataFrame:
        """ticker -> company, sector, region, held_as. One row per line."""
        # COLUMNS FROM THE SCHEMA, never typed: a typed list breaks when the table grows one.
        sec = pd.DataFrame(self.D.SECURITIES, columns=list(self.D.schema.TABLES["securities"].header))
        iss = pd.DataFrame(self.D.COMPANIES, columns=list(self.D.schema.TABLES["companies"].header))
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

        BY ISSUER A ROW IS ONE POSITION (`company_positions()`): its quantity in shares, a bet's
        stake counted as share-equivalents, its entry and current price per share and its
        currency, the share listing's. By ticker, a spread bet also carries `stake`;
        a share carries none.
        `weight` is a share of TOTAL MARKET EXPOSURE, not of cost.
        """
        L = self.ledger
        if account is not None:
            L = L[L["acct"] == account]

        rows = L[L["valued"]].copy()
        ident = self._identity().set_index("ticker")
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
        meta["opened"] = first_buy
        out = out.merge(meta, left_on=key, right_index=True, how="left")
        out["unrealised"] = out["value"] - out["cost"]
        out["unrealised_pct"] = (out["unrealised"] / out["cost"]).where(out["cost"] != 0)
        total = out["value"].sum()
        out["weight"] = out["value"] / total if total else float("nan")
        out["days_held"] = (pd.Timestamp.today().normalize() - out["opened"]).dt.days
        if by != "issuer":
            # A bet's size in its own terms: the ledger's qty on a bet IS its stake per point.
            out["stake"] = out["qty"].where(out["held_as"].eq("spread bet"))

        # ENTRY PRICE, in the holding's own currency: a QUANTITY-WEIGHTED MEAN of the legs still
        # held, each at its deal's price (`deal_prices()`), so a sold leg does not drag it. Blank
        # when any of them has none, rather than a mean of the ones that do.
        legs = open_legs.copy()
        legs["own"] = legs["event_id"].map(self.deal_prices()["price_own"])
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
            leg_ticker = dict(zip(open_legs["event_id"], open_legs[key]))
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
            out["price"] = out.apply(_current, axis=1)
            out["priced_at"] = out.apply(_priced_at, axis=1)
        else:
            # A COMPANY ROW IS ONE POSITION: its quantity, prices and currency are the company's,
            # bets counted as share-equivalents (`company_positions()`), not its first line's.
            pos = self.company_positions(rows, open_legs)
            out = out.drop(columns=["currency", "entry_price"]).merge(
                pos, left_on="company", right_index=True, how="left")
        return out.sort_values(key).reset_index(drop=True)

    def company_positions(self, rows: pd.DataFrame, open_legs: pd.DataFrame) -> pd.DataFrame:
        """EACH COMPANY HELD AS ONE POSITION, by company: `qty`, `entry_price`, `price`,
        `priced_at` and `currency`. `rows` are `holdings()`'s valued rows and `open_legs` its open
        buy legs, each with its company.

        A SPREAD BET COUNTS AS SHARE-EQUIVALENTS: its stake per point, times the points that make
        one unit of its listing's price (`points_per_unit`), times that currency's rate per pound on
        the deal date, times the shares one unit of the listing stands for (`shares_per_unit`,
        blank is one). Its entry is its level in the listing's price, per share.

        THE POSITION'S CURRENCY is its share listing's: the line with the most value held where
        the company has more than one. A company held only as bets takes the bets' currency.
        Every entry is converted into it at its own deal date's close (`_close_on()`), and the
        entry price is the mean over shares and share-equivalents. The current price is the
        listing's live price; held only as bets, the bets' own marks over the same share-equivalents.

        Blank, rather than a figure from part of the position, wherever a leg has no price, a bet
        line no `points_per_unit`, or a deal date no close: the audit names the line or the date.
        `qty` is whole share-equivalents. `bet_qty` and `bet_cost` are the open bets' part, unrounded:
        their share-equivalents and what they cost at entry in the position's currency, blank on
        any gap among the bets. Side effects: none.
        """
        ident = self._identity().set_index("ticker")
        own = self.deal_prices()["price_own"]
        px = {r[0]: (r[1], r[3]) for r in self.D.CURRENT_PRICES}

        def fact(code, name):
            v = ident.at[code, name] if code in ident.index else None
            return None if v is None or v != v or v == "" else float(v)

        out = {}
        for company, g in rows.groupby("company"):
            shares = g[g["held_as"] == "shares"]
            counts = shares.groupby("ticker")["qty"].sum()
            counts = counts[counts > 0]
            listing = (shares[shares["ticker"].isin(counts.index)].groupby("ticker")["gbp_value"]
                       .sum().idxmax() if len(counts) else None)
            legs = open_legs[open_legs["company"] == company]
            bets = legs[legs["held_as"] == "spread bet"]
            bet_ccys = sorted(set(bets["ticker"].map(ident["currency"])))
            ccy = (ident.at[listing, "currency"] if listing
                   else bet_ccys[0] if len(bet_ccys) == 1 else None)

            weighted, n_total, equivalents, gap = 0.0, 0.0, [], ccy is None
            bet_cost, bet_gap = 0.0, ccy is None
            for leg in legs.to_dict("records"):
                code, day = leg["ticker"], leg["date"]
                leg_ccy = ident.at[code, "currency"]
                price = own.get(leg["event_id"])
                price = None if price is None or price != price else float(price)
                if leg["held_as"] == "spread bet":
                    ppu, spu = fact(code, "points_per_unit"), fact(code, "shares_per_unit") or 1.0
                    rate = self._per_pound(leg_ccy, day)
                    if ppu is None or rate is None:
                        gap = bet_gap = True
                        continue
                    n = leg["qty"] * ppu * rate * spu
                    equivalents.append((leg["event_id"], n, ppu, spu))
                    price = None if price is None else price / ppu / spu
                else:
                    n = leg["qty"]
                convert = 1.0
                if ccy is not None and leg_ccy != ccy:
                    to, frm = self._per_pound(ccy, day), self._per_pound(leg_ccy, day)
                    convert = None if to is None or frm is None else to / frm
                if price is None or convert is None or ccy is None:
                    gap = True
                    bet_gap = bet_gap or leg["held_as"] == "spread bet"
                    continue
                weighted += price * convert * n
                n_total += n
                if leg["held_as"] == "spread bet":
                    bet_cost += price * convert * n

            bet_n = sum(e[1] for e in equivalents)
            qty = float(round(counts.sum() + bet_n)) if len(equivalents) == len(bets) else None
            entry = weighted / n_total if n_total and not gap else None

            current, priced_at = None, None
            if listing and listing in px:
                current, priced_at = px[listing]
            elif not listing and equivalents and len(equivalents) == len(bets):
                marks = [(px[self.D.LEG_CONTRACT[i]], n, ppu, spu) for i, n, ppu, spu in equivalents
                         if self.D.LEG_CONTRACT.get(i) in px]
                if len(marks) == len(equivalents):
                    current = sum(m[0] / ppu / spu * n for m, n, ppu, spu in marks) / bet_n
                    priced_at = min(m[1] for m, *_ in marks)
            bets_whole = not bet_gap and len(equivalents) == len(bets)
            out[company] = {"qty": qty, "entry_price": entry, "price": current,
                            "priced_at": priced_at, "currency": ccy,
                            "bet_qty": bet_n if bets_whole else None,
                            "bet_cost": bet_cost if bets_whole else None}
        return pd.DataFrame.from_dict(out, orient="index",
                                      columns=["qty", "entry_price", "price",
                                               "priced_at", "currency", "bet_qty", "bet_cost"])

    # ---- THE JUDGEMENT  —  store/reasoning.csv, beside each position's numbers -------

    def with_reasoning(self, frame: pd.DataFrame, opened: str = "opened",
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
                 "since": str(r["opened"])[:10]}
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
