"""The Book, its headline figures and their registry, `Book.HEADLINE`."""

from __future__ import annotations

from portfusion.record import rules as D
from portfusion.engine.bases import MONEY_KINDS
from portfusion.engine.positions import Positions
from portfusion.engine.trades import Trades
from portfusion.engine.accounts import Accounts
from portfusion.engine.reconciliation import Reconciliation
from portfusion.engine.quarters import Quarters
from portfusion.engine.past import PastDates
from portfusion.engine.findings import Findings


# =====================================================================================
# 4 · THE BOOK  —  what you actually call
# =====================================================================================

class _OfTheRecord:
    """A Book attribute the record decides: on a Book, read from that Book's own (`self.D`); asked
    of the class, from the record loaded now, so a reload moves it. With `method`, the function
    takes the record first, as a method takes self."""

    def __init__(self, read, method: bool = False):
        self.read, self.method = read, method

    def __get__(self, book, owner=None):
        d = D if book is None else book.D
        return (lambda *args: self.read(d, *args)) if self.method else self.read(d)


def _since_start(d) -> str:
    """The since-start return's label, which carries the day the record begins."""
    return f"Return since {d.RECORD_BEGINS:%-d %b %Y} (MWR)"


def _registry(d) -> dict[str, dict]:
    """`Book.HEADLINE` for the record `d`: the since-start entry named with its date."""
    return {k or _since_start(d): v for k, v in Book._HEADLINE.items()}


def _basis_of(d, label) -> str:
    """`Book.basis_of`: the basis a registered figure carries, by its label. KeyError for a label
    nobody registered: a figure is classified before any renderer shows it."""
    try:
        return _registry(d)[label]["basis"]
    except KeyError:
        raise KeyError(f"{label!r} is not in Book.HEADLINE: register it, with its basis and "
                       f"unit, before showing it") from None


class Book(Positions, Trades, Accounts, Reconciliation, Quarters, PastDates, Findings):
    """The book: every derived figure the desk and the report show, as methods.

    There is ONE of it, so two renderers asking the same question get the same answer.

    IT ANSWERS FROM THE RECORD IT WAS BUILT FROM, however the process's record moves after:
    every method reads `self.D`, the record pinned at construction, and never `rules` itself.
    `test_store_doors.py` holds that, by source and by behaviour.
    """

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
        proceeds = sum(e.proceeds for e in self.D.sales)
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
    # `report_only` marks a quarter's own figure, which the report shows and the Dashboard, of the
    # live book, does not; it is point_in_time.
    #
    # SINCE_START carries the day the record begins, which is the book's setting, so each Book
    # names it from its own record and a renderer looking the figure up asks for it rather than
    # typing the date. Its entry here is keyed None and named as the registry is read.
    SINCE_START = _OfTheRecord(_since_start)

    _HEADLINE = {
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
        # notional. The two costs stand apart above, as exposure's two parts do.
        "Unrealised gain / loss":                {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "Realised gain / loss to date":          {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "Total gain":                            {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "YTD income":                            {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "Capital employed (opening + deployed)": {"basis": "capital", "unit": "gbp", "point_in_time": False},
        "YTD return (MWR)":                      {"basis": "capital", "unit": "pct", "point_in_time": False},
        None:                                    {"basis": "capital", "unit": "pct", "point_in_time": False},
        "Return this quarter":                   {"basis": "capital", "unit": "pct", "point_in_time": True, "report_only": True},
        "Open positions":                        {"basis": "count", "unit": "count", "point_in_time": True},
        # The accounts open at the quarter end, which the report sets beside "Open positions".
        "Accounts / positions":                  {"basis": "count", "unit": "count", "point_in_time": True, "report_only": True},
        "Closed round trips":                    {"basis": "count", "unit": "count", "point_in_time": False},
    }

    HEADLINE = _OfTheRecord(_registry)

    #: The bases that mean "this is NOT the book's capital". A renderer marks these; the
    #: definition is rules.SPREAD_BET; this is the basis stated per figure.
    NOTIONAL_BASES = frozenset({"notional"})

    basis_of = _OfTheRecord(_basis_of, method=True)

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
        returns = self.quarter_returns().set_index("quarter_end")["return"]
        return {
            "Net asset value": nav,
            "Total market exposure": exposure,
            "— of which securities owned": exposure - sb,
            "— of which spread-bet notional": sb,
            "Exposure above net asset value": exposure - nav,
            # NO RETURN for the record's first quarter end, which opens on nothing: never zero.
            "Return this quarter": float(returns.get(as_of, float("nan"))),
            # THE FROZEN COMPOSITION'S LINES, as the exposure above is its accounts' frozen rows: a
            # ledger count at the marks takes in lines no frozen account holds.
            "Open positions": float(len(self.quarter_lines(as_of))),
            "Accounts / positions": float(len(self.accounts_open(as_of))),
        }
