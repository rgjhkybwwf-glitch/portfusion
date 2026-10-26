"""The Book's quarter ends, and the returns measured over them."""

from __future__ import annotations

import pandas as pd

from portfusion.record import rules as D
from portfusion.engine.store import record_begins
from portfusion.engine.core import Core
from portfusion.house import precision as P


class Quarters(Core):

    # ---- THE QUARTER ENDS  —  what each one froze ------------------------------------

    def quarter_nav(self) -> pd.DataFrame:
        """Each account's NAV contribution at each quarter end: statement-grade where a statement
        exists, reconstructed where not. `quality` says which; `contribution` says how the account
        contributes."""
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

        The loader refuses a value outside `schema.CONTRIBUTIONS`; this refuses one the two sets
        do not classify. A basis nobody has classified must not be silently dropped OR silently
        summed; refusing is the only answer that cannot be quietly wrong.
        """
        q = self.quarter_nav()
        unknown = set(q["contribution"]) - self.NAV_BASES - self.EXPOSURE_BASES
        if unknown:
            raise ValueError(
                f"quarter-nav.csv carries contribution {sorted(unknown)}, which is in neither "
                f"NAV_BASES nor EXPOSURE_BASES. Classify it in engine/quarters.py before it "
                f"can be totalled — do not guess which side it belongs on.")
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
                   .reindex(self.accounts_open(as_of)))
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
             for d in dates}).T.reindex(columns=self.D.ACCOUNT_ORDER).fillna(0.0)
        wide.index.name = "as_of"
        wide["TOTAL"] = wide.sum(axis=1).round(2)
        return wide.round(2).reset_index()

    @staticmethod
    def quarter_label(date: str, opens: str | None = None) -> str:
        """A quarter-end date -> the quarter's NAME. "2026-06-30" -> "Q2 2026". A quarter that
        `opens` after the quarter end before it, the one the record began inside, names the day it
        opens at, as the year does ("from 31 Dec"): "Q2 2026, from 17 May".

        DERIVED, NEVER TYPED: deriving the name here is what lets the quarter blocks key on
        identical values and be read across — typing "Q1 2026" in a second place is how they
        would drift apart.
        """
        d = pd.Timestamp(date)
        name = f"Q{(d.month - 1) // 3 + 1} {d.year}"
        if opens is not None and pd.Timestamp(opens) > d - pd.offsets.QuarterEnd(1):
            name += f", from {P.day_month(opens)}"
        return name

    @staticmethod
    def quarter_start(quarter_end: str) -> str:
        """A quarter-end date -> the first day of that quarter. "2026-06-30" -> "2026-04-01".
        Derived, never typed: hand arithmetic on months can file a trade in the wrong quarter."""
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
        df = pd.DataFrame(held, columns=["as_of", "account", "ticker", "qty", "price",
                                         "currency", "value", "cost", "quality", "source"])
        order = list(self.D.ACCOUNT_ORDER)
        out = df.groupby("ticker", as_index=False).agg(
            value=("value", "sum"), cost=("cost", "sum"),
            accounts=("account", lambda s: " · ".join(a for a in order if a in set(s))))
        ident = self._identity().set_index("ticker")
        out["company"] = out["ticker"].map(ident["company"]).fillna(out["ticker"])
        out["sector"] = out["ticker"].map(ident["sector"])
        out["region"] = out["ticker"].map(ident["region"])
        out["currency"] = out["ticker"].map(ident["currency"])
        out["held_as"] = out["ticker"].map(ident["held_as"])
        out["unrealised"] = out["value"] - out["cost"]
        out["weight"] = out["value"] / out["value"].sum()
        return (out.sort_values(["company", "ticker"]).reset_index(drop=True)
                   [["ticker", "company", "sector", "region", "currency", "held_as", "accounts",
                     "cost", "value", "unrealised", "weight"]])

    def quarter_lines_total(self, quarter_end: str) -> dict[str, float]:
        """The frozen composition's total row: the `cost`, `value` and `unrealised` of `quarter_lines()`,
        and the `gap`, how far that value falls short of the exposure frozen beside it. The gap is
        nothing, to the penny, where one valuation froze both — every quarter end the freeze wrote;
        a composition reconstructed by hand can be short a line. KeyError if never frozen."""
        lines = self.quarter_lines(quarter_end)
        value = float(lines["value"].sum())
        return {"cost": float(lines["cost"].sum()), "value": value,
                "unrealised": float(lines["unrealised"].sum()),
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
            rows.append({"quarter": self.quarter_label(end, prev),
                         **self._dietz(prev, end, navs[prev], navs[end])})

        # THE QUARTER IN PROGRESS, when asked for: it ends at valued_at(), and its label says "to
        # date". Off by default, because the report must not see it — a quarterly report is about a
        # CLOSED quarter, and an open row would change every time the page was generated.
        if include_open and dates:
            prev = dates[-1]
            end = self.valued_at()
            if end > prev:
                rows.append({"quarter": f"{self.quarter_label(end, prev)} to date",
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
        """The day-weighted return per account per quarter, in ACCOUNT_ORDER, from the one it opens in.

        Each account's NAV CONTRIBUTION against the CAPITAL DEPLOYED into its positions: for a
        share account, positions at market against purchases less sales; for a spread-bet
        account, EQUITY against FUNDS (rules.SPREAD_BET). One basis, as the book-level block
        uses. Never notional against entry notional — a return on a number that never moved
        through the account.

        THE SAME NUMERATOR AS THE BOOK'S: the change in value, less the capital deployed, plus
        `return_income()`.

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
            # A QUARTER THAT ENDS BEFORE THE ACCOUNT OPENS is not its own: it held nothing then.
            spans = [s for s in spans if account in self.accounts_open(s[1])]
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
                label = self.quarter_label(end, start)
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
        opening = before.set_index("ticker")["unrealised"]
        closing = after.set_index("ticker")["unrealised"]
        exits = [e for e in self.D.sales if prev < str(e.date)[:10] <= quarter_end]
        sold = [{"ticker": e.ticker, "realised": e.proceeds - self.cost_released[e.sale_id]}
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
        out["company"] = out["ticker"].map(self._identity().set_index("ticker")["company"]) \
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
        the net asset value at `year_opens()` to the quarter end's. Unlike the live year to
        date, both ends are frozen, so a report regenerates it the same. Labelled "2026 to 30 Sep"
        under `quarter`, and "2026 to 30 Sep, from 17 May" in the year the record began inside.
        KeyError if either end is not frozen."""
        navs = self.quarter_nav_total()
        year = int(quarter_end[:4])
        start = self.year_opens(year)
        label = f"{year} to {P.day_month(quarter_end)}"
        if start != f"{year - 1}-12-31":
            label += f", from {P.day_month(start)}"
        return {"quarter": label,
                **self._dietz(start, quarter_end, navs[start], navs[quarter_end])}

    def since_start(self, ytd: float | None = None) -> float:
        """THE RETURN SINCE THE RECORD BEGAN: each full year's, fixed at its frozen 31 December by
        `year_to_quarter()` (the first from the record's opening), linked with the year to date —
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
