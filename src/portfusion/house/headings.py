"""house/headings.py — what a column is called, on every renderer.

ONE WORD PER COLUMN, AND ONE PLACE IT IS WRITTEN. A heading typed in each renderer drifts: the
desk kept its own map in `app.js`, the report typed its `<th>` inline, and "Entry" came to mean
two figures on the desk alone. The words are `docs/glossary.md` §5's with one sterling suffix,
`(GBP)`. This list is the authority.

KEYED BY TAB AND FIELD. `COMMON` holds a field that reads the same wherever it is shown, a store
column under its own name (#43); `BY_TAB` holds the ones only one tab shows, or that a tab heads
in its own words (Dashboard's `currency`, a category). The tab is the desk panel's title. One
heading names one field (`tests/test_figures.py`).

WHAT IS REGISTERED is every field the desk or the report shows, and nothing else: `tests/test_figures.py`
refuses a heading typed anywhere else, and a heading here that no renderer heads (13 Oct 2026), since a column retired from its page left its word behind four times in the desk
review.

Imports nothing, so the desk and the report can read it without loading the record.
"""
from __future__ import annotations

COMMON = {
    # ---- what a line is -----------------------------------------------------------------------
    "ticker": "Ticker",
    "company": "Company",
    "account": "Account",
    "accounts": "Accounts",                 # a cell naming several accounts (§5)
    "code": "Code",                         # an account's register code, A1 onwards
    "holder": "Holder",
    "number": "Account no.",
    "category": "Category",                 # an income row's kind, never an instrument's type
    "sector": "Sector",
    "region": "Region",
    "currency": "Ccy",
    "cur": "Deal ccy",                      # the currency a deal's price is stated in (glossary §4)
    "held_as": "Held as",
    "direction": "Direction",
    "trade_id": "Trade ID",
    "sale_id": "Sale ID",
    "realisation_id": "Realisation ID",
    "broker_ref": "Broker ref",
    "contract": "IG contract",              # a bet leg's; on the Price Refresh, whether a line is one
    "funding": "Funding",                   # how IG funds the contract: daily or dated
    # ---- when ---------------------------------------------------------------------------------
    "date": "Date",
    "as_of": "As at",
    # ONE WORD FOR WHEN A POSITION WAS ENTERED: a holding's first buy still held, a round trip's
    # first leg beside its exit date (glossary §5).
    "opened": "Entry date",
    "closed": "Exit date",
    "days_held": "Days held",
    "priced_at": "Price as at",
    "age_days": "Age (days)",
    "quarter": "Quarter",
    # ---- how much -----------------------------------------------------------------------------
    "qty": "Quantity",
    "stake": "Stake (£/pt)",
    "level_points": "Level (points)",
    # A LOCAL PRICE IS NAMED BY THE Ccy COLUMN BESIDE IT, so its heading carries no unit
    # ("(local)" retired 12 Oct 2026). house/precision.py's LOCAL_PRICE_FIELDS lists them.
    "price": "Price",                       # a line's mark, beside its entry price
    "entry_price": "Entry price",
    "traded_price": "Traded price",
    "exit_price": "Exit price",
    "cost": "Cost (GBP)",
    "value": "Value (GBP)",
    "proceeds": "Proceeds (GBP)",
    "amount": "Amount (GBP)",
    "unrealised": "Unrealised gain (GBP)",
    "unrealised_pct": "Unrealised gain (%)",
    "realised": "Realised gain (GBP)",
    "realised_pct": "Realised gain (%)",
    "quarter_gain": "Quarter gain (GBP)",
    "weight": "Weight",
    "share": "% of book",
    "total": "Total",
    "nav": "Net asset value",
    "exposure": "Market exposure",
    "capital_employed": "Capital employed",
    "capital_growth": "Capital growth",
    "ytd": "YTD return",
    # ---- the quarter, firm and account alike --------------------------------------------------
    "opening_nav": "Opening NAV",
    "capital_deployed": "Capital deployed",
    "return_income": "Income",
    "closing_nav": "Closing NAV",
    "return": "Return",
    "contribution": "Contribution",         # how an account counts towards NAV (§2)
    # ---- against the broker -------------------------------------------------------------------
    "book": "Book",
    "broker": "Broker",                     # the broker's figure; the firm is `broker_firm`
    "broker_firm": "Broker firm",
    "difference": "Difference",
    "verdict": "Verdict",
    "last_check": "Last broker check",
    "document": "Document",
    # ---- a round trip -------------------------------------------------------------------------
    "fully_closed": "Closed out",
    # ---- a mark -------------------------------------------------------------------------------
    "mark_key": "Mark key",
    "quality": "Quality",
    "stale": "Stale",
    "marks": "Mark history",                # a line's banked marks, the last part of its detail
    # ---- the judgement ------------------------------------------------------------------------
    "whys": "Why",
    "why_entered": "Why we entered",
    "why_exited": "Why we exited",
    "research_notes": "Research notes",
    # ---- where it came from -------------------------------------------------------------------
    "source": "Source",
    "fx_at_trade": "FX at trade",
    "fx_from": "FX from",
    "detail": "Detail",
    "note": "Notes",
}

BY_TAB = {
    "Holdings": {},
    "Dashboard": {
        "currency": "Currency",             # a currency as a category, not a line's quote
    },
    "Round Trips": {
        # A spread bet's two per-share cells read as its levels in points (BET_COLUMNS).
        "entry_level_points": "Entry level (points)",
        "exit_level_points": "Exit level (points)",
        # A COMPANY LIFE (the life view, Book.company_lives()).
        "state": "State",
        "dividends": "Dividends (GBP)",
        "funding_interest": "Funding interest (GBP)",
        "life_gain": "Life gain (GBP)",
        "life_pct": "Life gain (%)",
        "life_cost_per_share": "Life cost per share",
        "realisations": "Round trips",
        "lines": "Lines",
    },
    "Performance": {
        "gain": "Gain",
    },
    "Trades": {
        "value": "Trade value (GBP)",
    },
    # THE REFRESH GRID: each line's mark on file beside the one fetched, a pair of dates apart.
    "Price Refresh": {
        "was": "Was",
        "was_at": "Was as at",
        "new": "New",
        "new_at": "New as at",
        "origin": "From",
        "take": "Take",
    },
    # A WINDOW, from one mark to the next: its own pair of times.
    "What Changed": {
        "price_move_pct": "Mark move (%)",
        "price_effect": "From price (GBP)",
        "fx_effect": "From FX (GBP)",
        "transacted": "From dealing (GBP)",
        "change": "Change (GBP)",
        "value_to": "Value now (GBP)",
        "priced_from": "Was priced",
        "priced_at": "Priced",
        # THE JOURNAL. `at` is record time, headed "Recorded" so no reader takes it for the
        # date an event happened (glossary §4).
        "at": "Recorded",
        "route": "Route",
        "op": "Did",
        "table": "Table",
        "rows": "Rows",
        "ref": "Retrieves",
    },
    # THE BENCH'S FORMS, one field per store column (`desk/intake/bench.py:form_for()`). A field the
    # pages already head reads the same here; these are the ones only a form shows.
    "Bench": {
        "closes": "Closes trade",
        "local_amount": "Amount",
        "rate": "Rate (per £1)",
        "cash": "Cash (GBP)",
        "evidence": "Document kind",
        "reference": "Reference",
        "retires": "Also retires",          # an IG contract the sale leaves with no open leg
        "renumbers": "Renumbers",           # the ids a backdated row moves, in date order
        "symbol": "Symbol",
        "quote_unit": "Quote unit",
        "points_per_unit": "Points per unit",
        "shares_per_unit": "Shares per unit",
        "epic": "Epic",                     # the IG market a new contract is priced by
    },
    # A FOREIGN INCOME'S CONVERSION, beside the sterling the book adds up: the amount in the
    # currency the Ccy column names, as the Bench heads it, and the day of the rate.
    "Accounts": {
        "local_amount": "Amount",
        "rate_date": "FX rate as at",
        "cash": "Cash / Funds (GBP)",      # an IG row's is its funds, from its reading
        "cash_read": "Read from",           # the document, then its day, as Reconcile names one
        "feed_key": "Feed",
    },
    # WHO OPENS THE HOSTED DESK, on the Mac's Access page. `at` is when a sign-in was tried, so
    # it is not What Changed's "Recorded".
    "Access": {
        "who": "Reader",
        "level": "Level",
        "since": "Since",                   # when the reader was given their first level
        "devices": "Devices",
        "last_signed_in": "Last signed in",
        "now": "Now",
        "device": "Device",
        "enrolled": "Enrolled",
        "last_used": "Last used",
        "at": "At",
        "result": "Result",
        "address": "Address",               # where a sign-in came from
        "label": "Named as",
    },
    # PAGES WITH NO HEADING OF THEIR OWN, named so that a tab nobody named is refused rather than
    # read as one of them.
    "Method": {},
    "Reconcile": {},
    "Reports": {},
}


#: STORE COLUMNS NO PAGE HEADS, each with why; `table.column` where the name heads another idea.
#: Every other store column is headed under its own name (#43, `tests/test_figures.py`).
STORE_ONLY: dict[str, str] = {
    "struck": "whether a mark can be fetched again; the marks door reads it, no page since 13 Oct",
    "published": "a research note's date, inside the Research notes link",
    "url": "a research note's address, the Research notes link's",
    "settings.key": "a setting's name", "settings.value": "a setting's value, not sterling",
    **{c: "the broker's own figure on a reading (glossary §2b)" for c in (
        "positions", "stmt_value", "recon_cash", "funds", "running_pl", "equity", "deposit",
        "available")},
}


def store_heading(table: str, column: str) -> str | None:
    """What a store column is headed, or None for one on STORE_ONLY or headed nowhere."""
    if f"{table}.{column}" in STORE_ONLY or column in STORE_ONLY:
        return None
    return COMMON.get(column) or BY_TAB["Bench"].get(column) or next(
        (m[column] for m in BY_TAB.values() if column in m), None)


def heading(tab: str, field: str) -> str:
    """What `field` is called on `tab`. Raises KeyError for a tab that is not a desk page, and for
    a field nobody has named."""
    if tab not in BY_TAB:
        raise KeyError(f"{tab!r} is not a desk page: BY_TAB names every page by its title")
    try:
        return BY_TAB[tab].get(field) or COMMON[field]
    except KeyError:
        raise KeyError(f"no heading for {field!r} on {tab!r}: name it in house/headings.py") from None


def headings(tab: str, fields) -> dict[str, str]:
    """`heading()` for each of `fields`, as {field: heading}."""
    return {f: heading(tab, f) for f in fields}


def registered() -> set[str]:
    """Every field with a heading here, on any tab."""
    return set(COMMON).union(*(set(m) for m in BY_TAB.values()))
