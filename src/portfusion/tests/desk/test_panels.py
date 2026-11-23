"""THE PANELS — the registry, and what each tab renders from the engine."""
from __future__ import annotations

import pytest
from portfusion import engine as _engine
from portfusion.desk import app, panels, engine
from portfusion.desk.panels import _shape
from desk_support import SHARES_ACCOUNT, SPREAD_BET_ACCOUNT, registered
from harness import SRC, needs, desk_script


def _blank(v):
    """A figure as the page carries one: None for a blank (NaN) one."""
    return None if v is None or v != v else v


def _a_month() -> tuple[str, str] | None:
    """The calendar month of the loaded book's newest trade: a window it did something in."""
    from portfusion.record import rules
    days = sorted(str(t.date)[:10] for t in rules.buys)
    if not days:
        return None
    first = days[-1][:8] + "01"
    import pandas as pd
    return first, (pd.Timestamp(first) + pd.offsets.MonthEnd(0)).date().isoformat()


_MONTH = _a_month() or ("", "")


# =====================================================================================
# Panels join by existing, and render what the engine says.
# =====================================================================================

def test_every_panel_declares_the_full_contract():
    """all_panels() raises on an incomplete module rather than skipping it — a panel that
    silently fails to appear is worse than one that fails loudly."""
    for mod in panels.all_panels():
        assert mod.NAME and mod.TITLE and callable(mod.data)


def test_a_panel_has_one_name():
    """THE FILE, THE URL AND THE TAB ARE ONE NAME: three would keep a reader from getting from the
    screen to its code. A renamed tab renames its file."""
    for mod in panels.all_panels():
        stem = mod.__name__.rsplit(".", 1)[-1]
        assert mod.NAME == stem.replace("_", "-") == mod.TITLE.lower().replace(" ", "-"), (
            f"{stem}.py is served at /{mod.NAME} and titled {mod.TITLE!r}: one name, please")


@needs("buys")
def test_the_snapshot_ties_to_the_engine():
    """THE TIE-CHECK, APPLIED TO THE SECOND RENDERER. Every figure on the panel against the
    engine's own answer. The desk formats; it must never calculate."""
    b = _engine.Book()
    money = _shape.money      # the one rounding every panel uses; test_money_rounds_half_up
    figs = {f["label"]: f["value"] for f in panels.get("dashboard").data()["figures"]}
    assert figs["Total market exposure"] == money(b.total_exposure())
    assert figs["Net asset value"] == money(b.nav())
    assert figs["— of which securities owned"] == money(b.owned())
    assert figs["— of which spread-bet notional"] == money(b.exposure())
    assert figs["Unrealised gain / loss"] == money(b.unrealised())
    assert figs["Realised gain / loss to date"] == money(b.realised())
    # BLANK IS None ON THE PAGE AND NaN IN THE ENGINE, compared as the page carries it (`_blank`).
    assert figs["YTD return"] == _blank(b.totals()["ytd"])
    assert figs[b.SINCE_START] == _blank(b.since_start())
    # THE COUNT ROUND TRIPS LEADS TO is that page's own "Closed out" total, and the lines its link
    # narrows the page to are the ones it counts: as many, each closed out, totalled by the engine.
    assert figs["Round trips closed out"] == panels.get("round-trips").data()["whole"]["closed_out"]
    counted = panels.get("round-trips").query(closed_only=True)
    assert counted["closed_only"] is True and counted["narrowed"] is True
    assert counted["total"] == figs["Round trips closed out"] == len(counted["rows"])
    assert all(r["fully_closed"] is True for r in counted["rows"])
    assert counted["totals"] == b.round_trip_totals(closed_only=True)


@needs("buys")
def test_a_blank_year_reaches_the_desk_as_a_blank(monkeypatch):
    """Until a new year's 31 December is frozen its return is blank, and a NaN would stop the
    Dashboard rather than show a dash: JSON has no NaN, so the panel route would answer 500."""
    import json
    from quarter_support import book_in_the_next_year
    monkeypatch.setattr(engine, "book", lambda: book_in_the_next_year(frozen=False))
    data = panels.get("dashboard").data()
    json.dumps(data, allow_nan=False)
    figs = {f["label"]: f["value"] for f in data["figures"]}
    assert figs["YTD return"] is None
    assert figs[_engine.Book.SINCE_START] is None
    assert figs["Capital employed (opening + deployed)"] is None


@needs("buys")
def test_the_dashboard_says_which_year_ytd_is_and_why_it_is_blank(monkeypatch):
    """The page says which year a year-to-date figure is of and why one is blank. The newest mark's
    date cannot say it, because the year rolls at a new year's first row as well as its first price;
    the engine's ytd_window() does, and "not frozen" is drawn exactly when the year's figures are
    blank."""
    from quarter_support import book_in_the_next_year
    live = panels.get("dashboard").data()["ytd"]
    assert live == _engine.Book().ytd_window()
    assert live["opens"] == f"{live['year'] - 1}-12-31"
    assert live["first_day"] == f"{live['year']}-01-01", "the first day counted is the day after"
    for frozen in (False, True):
        b = book_in_the_next_year(frozen=frozen)
        monkeypatch.setattr(engine, "book", lambda b=b: b)
        data = panels.get("dashboard").data()
        figs = {f["label"]: f["value"] for f in data["figures"]}
        assert data["ytd"] == {"year": live["year"] + 1, "opens": f"{live['year']}-12-31",
                               "first_day": f"{live['year'] + 1}-01-01", "frozen": frozen}
        assert (figs["YTD return"] is None) is not frozen


def test_money_rounds_half_up_the_same_way_on_every_panel():
    """Every panel rounds money one way, or a notional on a half-penny reads a penny apart on two
    screens."""
    assert _shape.money(1234.565) == 1234.57
    assert _shape.money(0.125) == 0.13 and _shape.money(-0.125) == -0.13
    assert _shape.money(None) is None and _shape.money(float("nan")) is None
    from portfusion.desk.panels import holdings
    snap = {f["label"]: f["value"] for f in panels.get("dashboard").data()["figures"]}
    assert holdings.query(by="ticker")["notional"] == snap["— of which spread-bet notional"]


def test_the_panels_share_one_shaping_helper():
    """ONE SHAPING MODULE, desk/panels/_shape.py.

    Copies drift: a fix reaches one and not the others, and one name returns two types.

    A count of copies would go stale. This asserts the property instead: no panel defines a
    shaping helper of its own, because there is one and it is importable. The helpers are what
    `_shape.py` defines, read from it, so a new one is held by existing and a copy is caught
    under its own name or a private one; a panel's `_rows` that calls `_shape.rows` builds on it.
    """
    import ast
    shape = SRC / "desk" / "panels" / "_shape.py"
    owned = {n.name for n in ast.parse(shape.read_text()).body if isinstance(n, ast.FunctionDef)}

    def own(src):
        return sorted({n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)
                       and n.name.lstrip("_") in owned
                       and f"_shape.{n.name.lstrip('_')}(" not in ast.unparse(n)})
    assert own("def plain(v):\n    return v\ndef _iso(v):\n    return v\n") == ["_iso", "plain"]
    offenders = {path.name: own(path.read_text()) for path in sorted(shape.parent.glob("*.py"))
                 if path != shape and own(path.read_text())}
    assert not offenders, (
        f"these panels define their own shaping helpers: {offenders}. "
        f"desk/panels/_shape.py has {sorted(owned)} — import them.")


def test_the_shared_shaping_survives_a_column_named_for_a_keyword():
    """A column named `return`, pinned by behaviour rather than by reading the source. itertuples()
    renames `return`; to_dict("records") does not."""
    import pandas as pd
    frame = pd.DataFrame({"quarter_end": [pd.Timestamp("2026-06-30")], "return": [0.0721]})
    row = _shape.rows(frame, ["quarter_end", "return"], dates=("quarter_end",))[0]
    assert row["return"] == pytest.approx(0.0721), \
        "the return column came back None — the namedtuple rename is back"
    assert row["quarter_end"] == "2026-06-30"


def test_the_shared_shaping_is_tolerant_where_a_panel_needs_it():
    """A column the frame does not carry, and a NaN date, are both ordinary here — a panel
    rendering a subset of a wider frame should not raise."""
    import pandas as pd
    frame = pd.DataFrame({"a": [1.0, float("nan")], "date": [pd.NaT, pd.Timestamp("2026-01-02")]})
    out = _shape.rows(frame, ["a", "date", "absent"], dates=("date",))
    assert out[0] == {"a": 1.0, "date": None, "absent": None}
    assert out[1] == {"a": None, "date": "2026-01-02", "absent": None}


def test_the_one_asserted_reconciliation_holds_on_the_desk_too():
    """total market exposure - net asset value = leverage. The build asserts it; so does this,
    because a renderer showing a leverage that does not reconcile is showing a figure from one
    view beside a figure from the other."""
    figs = {f["label"]: f["value"] for f in panels.get("dashboard").data()["figures"]}
    assert round(figs["Total market exposure"] - figs["Net asset value"], 2) == \
        figs["Exposure above net asset value"]


def test_no_figure_is_classified_by_the_desk_itself():
    """EVERY basis comes from Book.HEADLINE — the registry decides, never this panel."""
    for f in panels.get("dashboard").data()["figures"]:
        # NO EXEMPTIONS. The guard is absolute.
        assert f["label"] in _engine.Book.HEADLINE, \
            f"{f['label']!r} has no entry in the registry — it is being classified by default"
        assert f["notional_basis"] == (f["basis"] in _engine.Book.NOTIONAL_BASES)


def test_the_report_and_the_desk_agree_about_what_is_notional_basis():
    """One map, two renderers. If these ever disagreed, one of them would be telling a reader
    that a notional figure is the book's capital. Both ask `Book.basis_of()` and neither keeps a
    copy; these three are the labels a renderer could get wrong."""
    assert _engine.Book.basis_of("Spread-bet notional at entry") == "notional"
    assert _engine.Book.basis_of("Net asset value") == "capital"
    assert _engine.Book.basis_of("Total market exposure") == "notional"


# =====================================================================================
# ACTIVITY — the ledger, interrogable.
# =====================================================================================

@needs("buys")
def test_filtering_is_the_engines_not_the_panels():
    """book.activity(start, end, account) already takes those arguments. Re-implementing a date
    comparison in the panel would be a second answer to a question the engine answers."""
    from portfusion.desk.panels import trades as A
    b = _engine.Book()
    window = b.activity(start=_MONTH[0], end=_MONTH[1])
    assert len(window), "the loaded book did nothing in the window; move it"
    account = window["account"].iloc[0]
    got = A.query(start=_MONTH[0], end=_MONTH[1], account=account)
    want = b.activity(start=_MONTH[0], end=_MONTH[1], account=account)
    assert 0 < got["total"] == len(want)
    assert [r["trade_id"] or r["sale_id"] for r in got["rows"]] == list(
        want["trade_id"].fillna(want["sale_id"]))


@needs("buys")
def test_one_holding_can_be_followed_across_its_whole_life():
    """A holding's whole life is one query, whatever its span — a pre-record opening
    included, because entry dates older than the record are load-bearing.

    THE LINE IS THE BOOK'S OWN BUSIEST with both directions, and the expectation is the
    engine's whole unfiltered activity sliced here — so a panel query that windowed the
    dates, or dropped the sells, reads short against it."""
    from collections import Counter
    from portfusion.desk.panels import trades as A
    act = _engine.Book().activity()
    counts = Counter(act["ticker"])
    both = [t for t in counts if len(set(act[act["ticker"] == t]["direction"])) > 1]
    assert both, "no line has been both bought and sold — this follows nothing"
    line = max(both, key=lambda t: (counts[t], t))
    mine = act[act["ticker"] == line]

    q = A.query(ticker=line)
    assert q["total"] == len(mine) >= 2
    assert q["span"]["first"] == str(min(mine["date"]))[:10]
    assert q["span"]["last"] == str(max(mine["date"]))[:10]
    assert {r["direction"] for r in q["rows"]} == {"Buy", "Sell"}


@needs("buys")
def test_a_note_is_one_line():
    """A note says what happened that the row's own columns do not, in one line, or is blank. The
    reason for a trade is reasoning.csv's, never the note's."""
    from portfusion.desk.panels import trades as A
    rows = A.data()["rows"]
    assert rows and not [r["trade_id"] or r["sale_id"] for r in rows if "\n" in (r["note"] or "")]


def test_price_precision_is_the_houses_not_reinvented():
    """GBP is 4dp because LSE prices are quoted in pence and stored /100 — a line at 12.35p is
    0.1235, which 2dp would round to 0.12. One rule, house/precision.py's: every panel answer
    carries it beside its heads — the places per currency and which fields are local prices —
    and the report reads the same module, so no two renderers can differ. app.js types neither.
    The house's on-screen words travel the same way: every panel answer carries house/words.py's."""
    import re
    from portfusion.desk import app as desk_app
    from portfusion.desk import panels
    from portfusion.house import precision as P
    from portfusion.house import words as W
    assert P.LOCAL_PRICE_DP["GBP"] == 4 and P.LOCAL_PRICE_DP["USD"] == 2
    for name in ("holdings", "trades"):
        got = desk_app.panel(name)["precision"]
        assert got["local_price_dp"] == P.LOCAL_PRICE_DP, name
        assert got["local_price_default"] == P.DEFAULT_LOCAL_PRICE_DP, name
        assert got["local_price_fields"] == list(P.LOCAL_PRICE_FIELDS), name
    for mod in panels.all_panels():
        assert desk_app.panel(mod.NAME)["words"] == W.WORDS, mod.NAME
    js = desk_script()
    lp = re.search(r"const localPrice = [\s\S]*?;\n", js).group(0)
    assert not re.search(r"toFixed\(\d|\?\?\s*\d", lp), f"app.js types a local price's places: {lp}"

def test_holdings_totals_tie_to_the_engine_on_every_grouping():
    """THE TIE-CHECK FOR THIS PANEL: owned and notional are the engine's on every grouping.

    Grouped by ISSUER, a company held both ways collapses to one row carrying one basis:
    Orlant is ORLA and ORLA SB. The label stops being a partition, and summing on it
    misstates BOTH sides. Every other grouping keeps the partition, which is exactly why a
    test over ALL of them is the one worth having — a check on the default alone would pass a
    wrong panel.
    """
    from portfusion.desk.panels import holdings
    b = _engine.Book()
    for by in holdings.GROUPINGS:
        d = holdings.query(by=by)
        assert d["owned"] == _shape.money(b.owned()), f"owned, grouped by {by}"
        assert d["notional"] == _shape.money(b.exposure()), f"notional, grouped by {by}"


def test_an_issuer_row_is_sent_no_ticker():
    """GROUPED BY ISSUER, ONE ROW CAN BE SEVERAL INSTRUMENTS, so it has no single ticker. The
    column is left out rather than sent as a column of blanks; by ticker it is sent and filled.
    An issuer row is one position, so its prices are sent."""
    from portfusion.desk.panels import holdings
    by_ticker, by_issuer = holdings.query(by="ticker"), holdings.query(by="issuer")
    for c in holdings.BY_TICKER_ONLY:
        assert c in by_ticker["columns"], f"{c} is not sent grouped by ticker"
        assert c not in by_issuer["columns"], f"{c} is sent grouped by issuer"
        assert all(r[c] is not None for r in by_ticker["rows"]), f"a ticker row has no {c}"
    assert {"price", "priced_at"} <= set(by_issuer["columns"])


@needs("buys")
def test_an_issuer_held_both_ways_reads_mixed_and_the_panel_adds_no_marker():
    """Reported rather than hidden, in the one word: grouped by issuer, a company held as shares
    and as a bet is one row held as `mixed`, the engine's word, so a reader looking at one line
    knows part of it is money the book owns. The panel adds no marker and no list of its own
    beside the word."""
    from portfusion.desk.panels import holdings
    d = holdings.query(by="issuer")
    assert any(r["held_as"] == "mixed" for r in d["rows"]), "no issuer is held both ways"
    assert "mixed" not in d
    assert all("mixed" not in r and "notional_basis" not in r for r in d["rows"])


def test_a_per_account_holdings_split_never_calls_notional_money():
    """A spread-bet account contributes NO owned value, and a share account no notional.
    Taken from by_account()'s own `kind`, not decided here."""
    from portfusion.desk.panels import holdings
    assert holdings.query(account=SPREAD_BET_ACCOUNT)["owned"] == 0.0
    assert holdings.query(account=SHARES_ACCOUNT)["notional"] == 0.0


@needs("buys")
def test_holdings_says_what_a_weight_is_a_share_of():
    """THE TWO TOTALS ARE SHOWN APART, AND A LINE'S WEIGHT IS ITS SHARE OF BOTH TOGETHER: the
    page says so in its note and its scope, and never that the two are never added, since the
    weights it shows make up all exposure, owned and notional."""
    from portfusion.desk.panels import holdings
    for by in holdings.GROUPINGS:
        d = holdings.query(by=by)
        assert abs(sum(r["weight"] for r in d["rows"]) - 1) < 1e-9, by
        assert "never added" not in d["note"] and "share of all exposure" in d["note"], by
    scope = desk_script("holdings.js")
    assert "never added" not in scope and "share of all exposure" in scope


@needs("accounts", "buys")
def test_a_reading_page_names_each_account_by_its_label():
    """ONE NAME ON THE READING PAGES AND IN THE REPORT: every account cell and filter is the
    account's label (`Book.account_codes()`), as the report names it; the register on Accounts,
    and the Bench and Price refresh, which write it, keep the register's name."""
    b = engine.book()
    labels = set(_shape.labels(b).values())
    register = set(_shape.labels(b))
    cells = {"account", "accounts"}

    def found(v, at=()):
        if isinstance(v, dict):
            for k, x in v.items():
                yield from found(x, (*at, k))
        elif isinstance(v, list):
            for x in v:
                yield from found(x, at)
        elif at and at[-1] in cells and isinstance(v, str) and v:
            yield at, v

    for name in ("holdings", "round-trips", "trades", "performance", "reconcile", "accounts"):
        # THE REGISTER ITSELF holds the register's name, beside the code.
        seen = [(at, v) for at, v in found(panels.get(name).data()) if at[0] != "register"]
        assert seen, f"{name} names no account — this asserts nothing"
        for at, v in seen:
            # A HOLDING IN SEVERAL ACCOUNTS names each by its label, joined as the engine joins.
            rest = v
            for lab in sorted(labels, key=len, reverse=True):
                rest = rest.replace(lab, "")
            assert v == "The book" or (rest.replace("·", "").strip() == "" and rest != v), (
                f"{name} {'.'.join(map(str, at))}: {v!r} is not an account's label")
            assert not register & {p.strip() for p in v.split("·")}, (name, at, v)
    assert [r["account"] for r in panels.get("accounts").data()["register"]] == \
        list(b.account_register()["account"])
    # THE BENCH WRITES THE REGISTER'S NAME, so it offers it.
    offered = {c for f in panels.get("bench").data()["forms"]["buys"] for c in f.get("choices") or []}
    assert register <= offered


@needs("buys")
def test_round_trip_totals_follow_the_selection():
    """THE TOTALS FOLLOW THE SELECTION: kept whole-book while the table narrows, they would answer
    a question nobody asked.

    THE TOTALS ARE STILL THE ENGINE'S: round_trip_totals() takes the selection, so the panel
    asks rather than summing its own rows. The whole book is carried alongside so the screen
    can say what a selection is part of.
    """
    from portfusion.desk.panels import round_trips
    b = _engine.Book()

    whole = round_trips.data()
    assert whole["narrowed"] is False
    assert whole["totals"] == whole["whole"]
    assert whole["totals"]["realised"] == round(b.round_trip_totals()["realised"], 2)

    # THE PAGE'S OWN FILTER, through its route: the page names an account by its label.
    label = whole["accounts"][0]
    acct = registered(b)[label]
    one = app.round_trips(account=label)
    assert one["rows"], f"{label!r} narrows to nothing — this asserts nothing"
    assert one["narrowed"] is True
    assert one["totals"]["realisations"] == one["total"], (
        "the headline count must be the selection's, not the book's")
    assert one["totals"] == {k: v for k, v in b.round_trip_totals(account=acct).items()}, (
        "the selection's totals must be the ENGINE's, not re-summed here")
    assert one["whole"] == whole["totals"], "the whole book stays available as context"


@needs("buys")
def test_round_trips_can_be_narrowed_to_a_range_of_exit_dates():
    """A date-range filter on the tab. `closed` is the date a round trip is filed under, and the
    SELECTION IS THE ENGINE'S — book.round_trips() takes start and end for the same reason
    book.activity() does."""
    from portfusion.desk.panels import round_trips
    b = _engine.Book()
    got = round_trips.query(start=_MONTH[0], end=_MONTH[1])
    want = b.round_trips(start=_MONTH[0], end=_MONTH[1])
    assert got["total"] == len(want)
    assert [r["realisation_id"] for r in got["rows"]] == list(want["realisation_id"])
    assert got["totals"]["realised"] == round(b.round_trip_totals(
        start=_MONTH[0], end=_MONTH[1])["realised"], 2)
    # and the picker bounds itself on the record's own span
    assert got["span"]["first"] <= got["span"]["last"]


def test_performance_says_which_basis_every_return_is_on():
    """Dividing a gain by a total that includes spread-bet notional is the arithmetic the basis
    split exists to prevent. The panel states the basis rather than trusting a reader to
    remember it."""
    from portfusion.desk.panels import performance
    d = performance.data()
    assert d["measure"] == "net asset value"
    assert any("exposure" in c["detail"] for c in d["caveats"])
    # SINCE THE RECORD BEGAN: the record's day and the engine's figure under the engine's label.
    from portfusion.desk import engine
    b = engine.book()
    assert d["since"]["begins"] == b.baseline.date().isoformat()
    assert d["since"]["label"] == b.SINCE_START
    since = b.headline()[b.SINCE_START]         # blank on a book with no year to date yet
    assert d["since"]["return"] == (pytest.approx(since) if since == since else None)


@needs("buys")
def test_the_opened_on_nothing_caveat_appears_when_the_condition_does():
    """A spread-bet account whose first quarter opens on a zero balance has its return on the
    money put in, weighted by the days it was in, and the page must say so. The condition is
    live, not hypothetical: an account funded in a quarter it opened on nothing.

    Both halves are checked: the derivation on a made-up frame, so it cannot depend on today's
    data, and then the real one, so a caveat that stopped firing would be caught.
    """
    from portfusion.desk.panels import performance
    import pandas as pd

    from portfusion.engine import Book

    class _Fake:
        OPENED_IN_PERIOD = Book.OPENED_IN_PERIOD

        def account_codes(self):
            return pd.DataFrame(columns=["account", "code", "label"])

        def account_quarter_returns(self, include_open=False):
            return pd.DataFrame([{"account": "An invented account", "quarter": "Q3 2026",
                                  "opening_nav": 0.0, "return": 0.75,
                                  "opened_in_period": True}])

    caveats = performance._caveats(_Fake())
    assert any("An invented account" in c["scope"] for c in caveats), caveats
    assert any(c["detail"] == Book.OPENED_IN_PERIOD for c in caveats), \
        "the caveat must be the engine's own wording, not a second telling"

    # THE LIVE HALF, on whichever book is loaded: every account the engine flags as opened
    # in a period must be named by a caveat on the page, or the caveat stopped firing.
    flagged = Book().account_quarter_returns(include_open=True)
    flagged = sorted(set(flagged[flagged["opened_in_period"]]["account"]))
    assert flagged, "no account opened in a period — the live condition is gone"
    live = performance.data()["caveats"]
    labels = _shape.labels(engine.book())
    for account in flagged:
        assert any(labels[account] in c["scope"] for c in live), (
            f"{account} opened in a period and no caveat names it")


def test_the_tabs_run_in_the_order_of_the_work():
    """THE ORDER OF THE WORK: where the book stands, then the work, then the book's own pages, then
    the reports, which end the thread; Method apart, below the rule.
    `desk/panels/__init__.py` says why each sits where it does. Pinned on TITLE, so a renamed or
    moved tab is a decision written here."""
    assert [m.TITLE for m in panels.all_panels()] == [
        "Dashboard",
        "Bench", "Price Refresh", "What Changed", "Reconcile",
        "Performance", "Holdings", "Round Trips", "Trades", "Accounts",
        "Reports",
        "Method"]
    assert [m.TITLE for m in panels.all_panels() if getattr(m, "APART", False)] == \
        ["Method"], "the pages below the rule are a decision written here"


def test_the_query_routes_defer_to_their_panels():
    """The routes do no narrowing of their own — same rule as run_action and bench_commit.
    A bad grouping is a 400 from the PANEL's own refusal, not a second validation here."""
    from fastapi import HTTPException
    assert app.holdings(by="ticker")["by"] == "ticker"
    assert app.holdings(account=SHARES_ACCOUNT)["notional"] == 0.0
    assert app.round_trips(ticker="PENR.L")["ticker"] == "PENR.L"
    assert app.round_trips(closed_only=True)["closed_only"] is True
    with pytest.raises(HTTPException) as e:
        app.holdings(by="nonsense")
    assert e.value.status_code == 400


# =====================================================================================
# WHAT CHANGED — the panel that must not add the two bases
# =====================================================================================

def test_the_refresh_panel_shows_the_two_bases_apart():
    """Two blocks, never one total, and each carries the engine's own figures.

    A single "Total market exposure" change cannot be decomposed: a combined `transacted` row
    adds spread-bet notional to money, which is the mistake NAV_BASES, EXPOSURE_BASES and
    roll_up() exist to make impossible. The panel shows the bases apart instead, and this is
    the test that stops a later tidy-up putting them back together.
    """
    d = panels.get("what-changed").data()
    assert [b["held_as"] for b in d["blocks"]] == ["shares", "spread bet"]
    assert [b["label"] for b in d["blocks"]] == ["Shares", "Spread bets"], \
        "each block is headed by its kind of line, the record's word"

    b = engine.book()
    for block in d["blocks"]:
        totals = b.change_totals(held_as=block["held_as"])
        for figure in ("value_from", "change", "price_effect", "fx_effect", "transacted",
                       "value_to"):
            assert block["totals"][figure] == totals[figure], (
                f"{block['label']} {figure} is not the engine's — a panel that computes a "
                f"figure is a second answer to something the engine already decided")


@needs("buys")
def test_the_notional_block_leaves_out_only_what_is_nought():
    """A SPREAD BET HAS NO FX PART, so the notional block draws no From FX column or total —
    and that is only safe while the engine agrees: every spread-bet line's fx_effect is nought.
    The owned block keeps it, since a foreign share's rate does move its value."""
    d = panels.get("what-changed").data()
    by = {blk["held_as"]: blk for blk in d["blocks"]}
    assert "fx_effect" in by["shares"]["columns"], "the owned block lost its From FX"
    assert "fx_effect" not in by["spread bet"]["columns"], "the notional block still draws From FX"
    frame = engine.book().changes_since()
    bets = frame[frame["held_as"] == "spread bet"]
    assert not bets.empty, "no spread-bet line — this asserts nothing"
    assert (bets["fx_effect"] == 0).all(), (
        "a spread-bet line has an FX part, and the notional block is hiding it")


def test_the_refresh_panel_says_which_clock_each_block_is_on():
    """TWO CLOCKS ON ONE SCREEN, and each block naming its own.

    A mark banked on 31 Aug and a July dividend entered on 3 Sep sit three weeks apart on this
    page and answer different questions. Unlabelled, a reader cannot tell which sense of *when*
    is in front of them; that is `docs/glossary.md` §4 stated as layout.
    """
    d = panels.get("what-changed").data()
    assert "market time" in d["caveat"].lower(), \
        "the marks block no longer names its clock"
    assert "record time" in d["record"]["caveat"].lower(), \
        "the journal block no longer names its clock"

    js = desk_script()
    for heading in ("Market time", "Record time"):
        assert heading in js, f"the panel draws no {heading!r} heading"

    # AND THE RECORD BLOCK SAYS HOW FAR BACK IT REACHES. It is forward-only by construction,
    # and a list with no stated start reads as a complete history of the book.
    assert d["record"]["opened"], "the record block does not say when the journal opened"
    assert "forward-only" in d["record"]["caveat"].lower()


@needs("buys")
def test_the_record_block_covers_the_span_the_marks_do():
    """RECORD TIME OVER THE SAME SPAN AS MARKET TIME. It lists the writes since the earliest window
    above opened and folds the rest — and between the two, every write is still there."""
    b = engine.book()
    r = panels.get("what-changed").data()["record"]
    starts = [w["priced_from"] for w in b.change_windows() if w["priced_from"]]
    assert starts, "no window has a start — this asserts nothing"
    assert r["since"] == min(starts), "the record block does not start where the marks do"
    assert all(row["at"] >= r["since"] for row in r["rows"])
    assert all(row["at"] < r["since"] for row in r["earlier"])
    assert len(r["rows"]) + len(r["earlier"]) == len(b.journal()), (
        "a write is in neither half of the record block")


@needs("buys")
def test_an_accounts_quarter_names_what_its_closing_nav_rests_on():
    """THE RECORD SAYS WHAT EACH QUARTER END RESTS ON: a statement, a reconstruction, a freeze from
    the engine — and whether that is sourced or derived. Each account's frozen quarter row carries
    its quarter end's source and quality, for the row's detail; the open quarter, at today's marks,
    carries none. A BOOK ROW CARRIES WHAT ITS FIGURE IS MADE OF instead: the engine's rows for
    that quarter end, one an account, which add to the closing figure on the row."""
    b = engine.book()
    d = panels.get("performance").data()
    assert d["detail"] == ["source", "quality"]
    series = b.account_quarter_returns(include_open=True)
    frozen = set(b.quarter_nav_total().index)
    checked = 0
    for row, end in zip(d["accounts"], series["quarter_end"].astype(str).str[:10]):
        if end in frozen:
            q = b.quarter_nav_rows(end).set_index("account").loc[registered(b)[row["account"]]]
            assert (row["source"], row["quality"]) == (q["source"], q["quality"]), (
                f"{row['account']} {row['quarter']}")
            checked += 1
        else:
            assert row.get("source") is None, f"{row['account']} {row['quarter']} is not frozen"
    assert checked, "no frozen quarter — this asserts nothing"
    assert all(r.get("source") is None for r in d["firm"]), "a book row has an account's source"
    firm = b.quarter_returns(include_open=True)
    made = 0
    for row, end in zip(d["firm"], firm["quarter_end"].astype(str).str[:10]):
        if end not in frozen:
            assert "nav_rows" not in row, f"{row['quarter']} is not frozen"
            continue
        parts = b.quarter_nav_rows(end).to_dict("records")
        assert [{c: _shape.label(p[c], _shape.labels(b)) for c in d["nav_columns"]}
                for p in parts] == row["nav_rows"], row["quarter"]
        assert abs(sum(p["amount"] for p in row["nav_rows"]) - row["closing_nav"]) < 0.005, (
            f"{row['quarter']}: the accounts' parts do not add to the book's closing NAV")
        made += 1
    assert made, "no frozen quarter — this asserts nothing"
    assert not any("nav_rows" in r for r in d["accounts"]), "an account's row has the book's parts"


@needs("buys")
def test_a_year_row_rebuilds_its_own_return():
    """THE YEAR TABLE SHOWS THE RETURN'S INCOME AND THE GAIN WITH IT, so every row's YTD return
    is its own figures: the gain, which is capital growth plus that income, ÷ (opening NAV + the
    capital deployed, each flow weighted by the days after it — the engine's weights, since the
    row carries the flows' sum)."""
    d = panels.get("performance").data()
    assert "return_income" in d["year_columns"] and "income" not in d["year_columns"]
    rows = [r for r in d["year"] if r["ytd"] is not None]
    assert rows, "no year row has a return — this asserts nothing"
    b = engine.book()
    weighted = b.weighted_flows(b.ytd_opens(), b.valued_at())
    for r in rows:
        wcf = float(weighted.sum() if r["account"] == "The book"
                    else weighted[registered(b)[r["account"]]])
        assert abs(r["gain"] - (r["capital_growth"] + r["return_income"])) < 1e-9, r["account"]
        rebuilt = r["gain"] / (r["opening_nav"] + wcf)
        assert abs(rebuilt - r["ytd"]) < 1e-9, (
            f"{r['account']}: the row rebuilds to {rebuilt:.4%}, the page says {r['ytd']:.4%}")


@needs("buys")
def test_the_refresh_panel_names_every_window_the_engine_drew():
    """The heading names every window it drew from, however many the marks make, and gets
    them from the engine rather than deriving them. Whether each line keeps its OWN window is
    the engine's rule: test_engine_invariants.py::test_a_line_carries_its_own_two_dates.
    """
    d = panels.get("what-changed").data()
    assert d["windows"], "no window at all"
    assert d["windows"] == engine.book().change_windows(), \
        "the panel is deriving its own windows rather than asking the engine"
    for w in d["windows"]:
        assert w["priced_from"] is None or w["priced_from"] < w["priced_at"]


# =====================================================================================
# A HOLDINGS ROW: HOW MUCH IS HELD, AND THE MARKS BEHIND IT
# =====================================================================================

@needs("buys")
def test_by_ticker_every_line_says_how_much_is_held_in_its_own_terms():
    """A share line carries the engine's count and no stake; a spread bet its stake per point.

    BY ISSUER, ONE POSITION: the engine's count in shares, a bet as share-equivalents, and no
    stake per point, which is a bet line's own measure.
    """
    b = engine.book()
    held = b.holdings(by="ticker").set_index("ticker")
    rows = panels.get("holdings").query(by="ticker")["rows"]
    by_company = {}
    for e in held.reset_index().to_dict("records"):
        by_company.setdefault(e["company"], []).append(e)
    seen = {"shares": 0, "spread bet": 0}
    for row in rows:
        e = next(x for x in by_company[row["company"]] if x["held_as"] == row["held_as"])
        seen[row["held_as"]] += 1
        if row["held_as"] == "spread bet":
            assert row["stake"] == e["stake"], row["company"]
        else:
            assert row["qty"] == e["qty"] and row["stake"] is None, row["company"]
    assert all(seen.values()), f"a kind of line is missing, so half of this asserts nothing: {seen}"
    companies = b.holdings(by="issuer").set_index("company")["qty"]
    for row in panels.get("holdings").query(by="issuer")["rows"]:
        assert row["qty"] == companies[row["company"]] and row["stake"] is None, \
            row["company"]


@needs("buys")
def test_every_holdings_row_says_what_it_is_held_as():
    """A spread bet's value is NOTIONAL (rules.SPREAD_BET), and a reader must not meet the figure
    without the word beside it: every row's Held as is one of the record's two words, or `mixed`
    on an issuer row holding both, and nothing else on the row says it."""
    from portfusion.record import schema
    words = set(schema.KINDS) | {"mixed"}
    for by in ("issuer", "ticker"):
        rows = panels.get("holdings").query(by=by)["rows"]
        assert any(r["held_as"] == "spread bet" for r in rows), f"by {by}: no spread-bet rows"
        for row in rows:
            assert row["held_as"] in words, f"{row['company']}: held as {row['held_as']!r}"


def test_each_row_opens_the_marks_behind_it_with_every_source_string():
    """The detail's mark history is the evidence behind a value: the source notes written at each
    refresh carry the corroboration, the symbol actually queried and the session's own range.

    THE LAST FIVE REFRESHES: every mark stays on file; the detail shows the newest five dates,
    each mark carrying its `status` so a correction is drawn under its replacement."""
    from portfusion.desk.panels import holdings as H
    for by in ("issuer", "ticker"):
        for row in panels.get("holdings").query(by=by)["rows"]:
            marks = row["marks"]
            assert marks, f"{row['company']} opens no mark history at all"
            for mark in marks:
                assert mark["source"], f"{row['company']} has a mark with no source string"
                assert mark["mark_key"], "a mark arrives without the key it was banked under"
            dates = [m["date"] for m in marks]
            assert dates == sorted(dates, reverse=True), \
                f"{row['company']}'s history is not newest-first"
            assert len(set(dates)) <= H.MARK_REFRESHES, \
                f"{row['company']} shows {len(set(dates))} refreshes"


@needs("buys")
def test_a_multi_contract_line_opens_both_contracts():
    """HALV SB is priced by two contracts at two levels, and its marks show both."""
    keys = engine.book().changes_since().groupby("ticker")["mark_key"].apply(set)
    several = {t: k for t, k in keys.items() if len(k) > 1}
    assert several, "no line sits on two mark keys — this asserts nothing"
    rows = {r["company"]: r for r in panels.get("holdings").query(by="ticker")["rows"]}
    tickers = engine.book().holdings(by="ticker").set_index("ticker")["company"]
    for key, keys in several.items():
        opened = {m["mark_key"] for m in rows[tickers[key]]["marks"]}
        assert keys <= opened, f"{key} is priced by {keys} but opens {opened}"


def test_the_expansion_spans_the_whole_row_however_many_columns_there_are():
    """The colspan is DERIVED from what was rendered, never typed.

    A hardcoded number goes stale the first time a column joins — silently, by leaving the
    last cell of every expansion hanging outside the table.
    """
    js = desk_script()
    assert "cols.length + inserts.length" in js, \
        "the expansion's colspan is no longer derived from the rendered columns"


# =====================================================================================
# ONE WORD FOR A SPREAD-BET POSITION, on the desk as in the engine
# =====================================================================================

def test_the_desk_says_notional_too():
    """A RENDERER NO CHECK COVERS DRIFTS. `notional` is the store's own word, and the desk's labels
    say it too.

    LABELS, NOT PROSE: the phrase survives where it DEFINES the term — "notional is the size of
    an economic interest" is the sentence that teaches it — and not where it replaces it.
    """
    js = desk_script()
    offenders = []
    for line in js.splitlines():
        low = line.lower()
        if "economic interest" not in low and "contract value" not in low:
            continue
        # A comment is prose. A quoted string on a render line is a label.
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        offenders.append(stripped[:100])
    assert not offenders, (
        "these lines label a spread-bet position by something other than 'notional':\n  "
        + "\n  ".join(offenders))


@needs("buys")
def test_the_judgement_reaches_holdings_and_round_trips():
    """THE REASONING IS SHOWN WHERE THE POSITION IS: under each row of Holdings and Round Trips,
    from Book.with_reasoning() — an issuer row carrying every instrument it collapses."""
    from portfusion.desk import engine
    from portfusion.desk.panels import holdings, round_trips
    b = engine.book()
    by_ticker = {r["ticker"]: r["whys"] for r in
                 b.with_reasoning(b.holdings(by="ticker")).to_dict("records")}
    assert any(by_ticker.values()), "no held position shows a why"
    rows = holdings.query(by="ticker")["rows"]
    assert all(len(r["reasons"]) == 1 for r in rows)
    assert {x["ticker"]: x["whys"] for r in rows for x in r["reasons"]} == by_ticker
    issuer = holdings.query(by="issuer")["rows"]
    assert sum(len(r["reasons"]) for r in issuer) == len(by_ticker), \
        "an issuer row dropped an instrument's thesis"
    trip = round_trips.data()["rows"][0]
    assert {"opened", "whys", "research_notes", "why_entered_owed", "why_exited_owed"} <= set(trip)
    # THE HISTORY UNDER A HOLDING: the engine's life gain, and the income naming the line.
    lives = b.company_lives()
    lives = lives[lives["closed"].isna()].set_index("company")["life_gain"]
    income = b.income_rows().groupby("ticker")["amount"].sum()
    for r in rows:
        whole, *each = r["life"]
        assert whole["life_gain"] == pytest.approx(lives[r["company"]])
        assert not each or sum(x["life_gain"] for x in each) == pytest.approx(whole["life_gain"])
        assert len(each) != 1, "a life in one account repeats itself"
        assert sum(x["amount"] for x in r["income"]) == pytest.approx(income.get(r["ticker"], 0))


@needs("buys")
def test_a_trade_carries_its_source():
    """Every figure traces to a named source, and the reader can see which."""
    from portfusion.desk.panels import trades
    rows = trades.data()["rows"]
    assert rows and all(r["source"] for r in rows)


@needs("buys")
def test_the_accounts_page_and_the_year_are_the_engines():
    """The register, external capital, the year's income and the year so far per account are
    each the engine's frame, row for row; nothing on the page is summed."""
    from portfusion.desk import engine
    from portfusion.desk.panels import accounts, performance
    b = engine.book()
    a = accounts.data()
    assert [r["account"] for r in a["register"]] == list(b.account_register()["account"])
    assert len(a["movements"]) == len(b.capital_movements())
    assert sum(len(line["rows"]) for line in a["income"]) == len(b.income_rows(b.ytd_year()))
    year = performance.data()["year"]
    # The book leads the year, the engine's all-accounts row; then each account.
    assert year[0]["account"] == "The book" and year[0]["ytd"] == _blank(b.totals()["ytd"])
    assert [r["ytd"] for r in year[1:]] == [None if v != v else v for v in b.by_account()["ytd"]]


def test_the_method_page_renders_the_records_rules(monkeypatch):
    """The method's rules are the record's constants, interpolated rather than retyped, so a
    change to one reaches the page. ITS FIGURES ARE THE ENGINE'S: the row on the gains, incomes
    and capitals prints, in order, the year's `year_attribution()` and `totals()` and the
    headline trading gain, in the live year and in the next, where the year's trading gain and
    the headline's part; a gap the frozen opening leaves is said only where there is one."""
    import re
    from portfusion.desk.panels import method
    from portfusion.house import headings as H
    from portfusion.house.precision import money
    from portfusion.record import rules as D
    from quarter_support import book_in_the_next_year
    text = " ".join(r["text"] for s in method.data()["sections"] for r in s["rows"])
    for rule in (D.SPREAD_BET, D.STATEMENT_GRADE, D.SOURCE_HIERARCHY, D.SOURCE_HIERARCHY_NOTE):
        assert rule in text
    assert f"{D.REVIEW_FROM:%-d %b %Y}" in text

    def row():
        return next(r["text"] for s in method.data()["sections"] for r in s["rows"]
                    if r["topic"] == "How the gains, incomes and capitals differ")

    for b in (engine.book(), book_in_the_next_year(frozen=True)):
        monkeypatch.setattr(engine, "book", lambda b=b: b)
        t, y = b.totals(), b.year_attribution()
        shown = [money(v) for v in (
            y["trading_gain"], y["equity_income"], y["capital_growth"], t["nav"],
            t["capital_employed"], t["opening_nav"], t["capital_deployed"], t["gain"],
            b.headline()[H.FIGURES["total_gain"]], t["income"], t["return_income"],
            y["position_income"])]
        assert re.findall(r"-?£[\d,]+\.\d\d|—", row()) == shown, row()
    leaves = {**y, "unattributed": 0.25}
    monkeypatch.setattr(b, "year_attribution", lambda: leaves)
    assert f"{money(0.25)} of it neither explains" in row()


# =====================================================================================
# RECONCILE — each account in the engine's one voice
# =====================================================================================

@needs("accounts", "buys")
def test_reconcile_shows_what_each_account_was_last_checked_against():
    """EACH ROW QUOTES `Book.account_checks()`: compared, state, next step, page, sentence, and
    the last broker check's document and day (`test_findings.py` holds the other two pages)."""
    from portfusion.desk.doors import observations
    from portfusion.house import precision as P
    checks = engine.book().account_checks(observations.counted()).set_index("account")
    rows = panels.get("reconcile").data()["rows"]
    assert rows, "no account — this asserts nothing"
    back = registered(engine.book())
    for r in rows:
        c = checks.loc[back[r["account"]]]
        assert (r["verdict"], r["compared"], r["state"], r["next"], r["reads"], r["sentence"]) \
            == (c["verdict"], c["compared"], c["state"], c["next"], c["page"], c["sentence"])
        assert r["last_check"] == ("no broker check" if c["on"] is None
                                   else f"{c['against']}, {P.day(c['on'])}"), r["account"]


@needs("accounts", "buys")
def test_a_figure_an_ig_reading_lacks_is_left_out():
    """AN IG READING'S FIGURES ARE THE ONES IT HOLDS: one it lacks is left out, never a dash, and
    a share row has none."""
    frame = engine.book().reconciliation().set_index("account")
    rows = panels.get("reconcile").data()["rows"]
    names = {"funds": "funds", "running P/L": "running_pl", "deposit": "deposit",
             "available": "available"}
    assert rows, "no account — this asserts nothing"
    back = registered(engine.book())
    for r in rows:
        held = frame.loc[back[r["account"]]]
        want = [k for k, col in names.items() if held[col] is not None and held[col] == held[col]]
        assert [f["label"] for f in r["ig_figures"]] == want, r["account"]
        assert all(f["value"] is not None for f in r["ig_figures"])
    js = desk_script()
    assert "r.ig_figures.map" in js and "running P/L ${" not in js, \
        "the page draws IG's figures by name rather than the ones the reading holds"
