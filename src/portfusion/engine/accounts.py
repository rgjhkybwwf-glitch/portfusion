"""The Book's register, its figures per account, and the money in and out."""

from __future__ import annotations

import pandas as pd

from portfusion.engine.bases import roll_up
from portfusion.engine.core import Core


class Accounts(Core):

    # ---- THE REGISTER  —  who holds what, named as filed -----------------------------

    def account_order(self) -> list[str]:
        """Every account in this book's register order — shares first, then spread bets.

        An order, not a sort: the break separates the two valuation bases, and alphabetically a
        spread-bet account lands among the share ones.
        """
        return list(self.D.ACCOUNT_ORDER)

    def accounts_open(self, date) -> list[str]:
        """The accounts whose record had begun by `date`, in register order: those a quarter end
        on that day holds a row for (`rules.accounts_open()`, read from this book's record)."""
        return [a for a in self.D.ACCOUNT_ORDER if self.D.ACCOUNT_BEGINS.get(a, "") <= str(date)[:10]]

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
        """Each account as it is named to anyone but the owner: its register code, and a `label`
        that is the code beside the account's name with the holder taken out, `A3 · IG Spread bet`.
        Columns account, code, label; one row per account, in ACCOUNT_ORDER."""
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
        figure is money or notional. The register's `held_as` says, for the record this Book was
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
        """The day the year-to-date figures measure from, as a store key (`year_opens()`)."""
        return self.year_opens(self.ytd_year(as_of))

    def year_opens(self, year: int) -> str:
        """The day `year`'s figures measure from: the 31 December before it, but in the year the
        record began, its opening, since nothing earlier was recorded."""
        return max(f"{year - 1}-12-31", self.baseline_asof)

    def quarter_opens(self, quarter_end: str) -> str:
        """The day a quarter's figures measure from: the previous quarter end, but in the quarter the
        record began, its opening (`quarter_label()` names such a quarter by it). The opening itself
        has nothing recorded before it, so its own is the quarter end before."""
        before = (pd.Timestamp(quarter_end) - pd.offsets.QuarterEnd(1)).date().isoformat()
        return max(before, self.baseline_asof) if quarter_end > self.baseline_asof else before

    def ytd_window(self) -> dict:
        """What the live year-to-date figures measure, for a page to state: `year`, the day they
        open at (`opens`, `year_opens()`), and whether that day's net asset value is `frozen` on file.

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
          opening_nav   money     NAV at `ytd_opens()`, from QUARTER_NAV; BLANK until that
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
        exits = [e for e in self.D.sales
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
                          - per_account(pd.Series([self.cost_released[e.sale_id] for e in after],
                                                  index=by_after, dtype=float)
                                        .groupby(level=0).sum()))
        nav = exposure.where(~is_sb, employed_since + realised_since
                             + (unrealised - self._unrealised_at_baseline(order))
                             + income_since)

        # THE YEAR'S TERMS open at the frozen net asset value of `year_opens()`'s day. Before
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
            "opening_nav": opening.values,
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
        out["opened_in_period"] = (out["opening_nav"] == 0) & out["ytd"].notna()
        return out

    def totals(self) -> dict[str, float]:
        """The ALL ACCOUNTS row. Money measures only — exposure is asked for separately."""
        by = self.by_account()
        t = roll_up(by, "opening_nav", "capital_deployed", "capital_employed",
                    "nav", "capital_growth", "income", "return_income")
        # THE ONE FORMULA, as every account row: the year's flows weighted to the newest mark.
        weighted = float(self.weighted_flows(start=self.ytd_opens(), end=self.valued_at()).sum())
        t["ytd"] = self._dietz_row(t["opening_nav"], t["nav"], t["capital_deployed"],
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

        NAV for a share account excludes cash, so counting cash movements against it reads a
        withdrawal as gain and a sale as loss. So a flow is a PURCHASE: buying with cash nets to
        zero, a price move is the whole gain, and a deposit or withdrawal touches nothing. Cash is
        still recorded, for the reconciliation; it does not reach the return.

        TWO RULES THAT ARE NOT INTERCHANGEABLE:

          SHARES      a purchase at its GBP cost and a sale at minus its proceeds, off the ledger
                      (a buy's `cost` and a sale's `proceeds`).
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
            pd.DataFrame({"account": buys["acct"], "date": buys["date"], "amount": buys["cost"]}),
            pd.DataFrame({"account": sells["acct"], "date": sells["date"],
                          "amount": -sells["proceeds"]}),
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
        in. Adding a spread-bet account's funding here would count it twice. Bounded by
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
        An account with none reads 0.00, never absent — but a window that ends before an account
        opened (`accounts_open()`) has no row for it unless the account earned in it, as a quarter's
        other tables have none."""
        df = self._window(self.store["income"], start, end, year)
        cats = list(self.D.POSITION_INCOME) + list(self.D.ACCOUNT_INCOME)
        shown = set(self.accounts_open(end)) | set(df["account"]) if end else set(self.D.ACCOUNT_ORDER)
        wide = (df.groupby(["account", "category"])["amount"].sum().unstack()
                  .reindex(index=[a for a in self.D.ACCOUNT_ORDER if a in shown], columns=cats)
                  .fillna(0.0))
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
        figure. NEWEST FIRST WITHIN AN ACCOUNT, as every log on the desk reads; a broker's
        statement lists them the other way, one press of the Date heading off.
        """
        df = self.store["income"].copy()
        if year is not None:
            df = df[df["date"].dt.year == year]
        order = {a: i for i, a in enumerate(self.D.ACCOUNT_ORDER)}
        df["_o"] = df["account"].map(lambda a: order.get(a, 99))
        df = df.sort_values(["_o", "date"], ascending=[True, False], kind="stable").drop(columns="_o")
        df["rate_date"] = self._income_rates()["rate_date"].reindex(df.index)
        return df.reset_index(drop=True)

    def _per_pound(self, currency: str, day) -> float | None:
        """`currency` per pound at `day`'s close, the Friday's for a weekend day, or None when
        the record holds no such close (`rate_gaps()` names the date). One for sterling."""
        if currency == "GBP":
            return 1.0
        on, rate = self._close_on(currency, day)
        day = pd.Timestamp(day)
        served = day - pd.Timedelta(days=max(0, day.weekday() - 4))
        return rate if on is not None and pd.Timestamp(on) >= served else None

    def _close_on(self, currency: str, date) -> tuple[str | None, float | None]:
        """THE CLOSE A DATED CONVERSION TAKES: the newest TradingView close of
        `currency` on or before `date`, as (its date, its rate), or (None, None) when none is on
        file. A close, never a live read: a dated figure has to come out the same next year."""
        fh = self.store["history.fx"]
        on = fh[(fh["currency"] == currency) & (fh["kind"] == "spot")
                & (fh["struck"] == "close")
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
        # with none as NaN, which is not None and is not past the limit, so a missing rate would
        # read as fresh.
        rows["stale"] = [dd is None or dd > limit for dd in apart]
        rows["days_apart"] = pd.Series(apart, index=rows.index, dtype=object)
        return rows[cols].sort_values("days_apart", ascending=False).reset_index(drop=True)
