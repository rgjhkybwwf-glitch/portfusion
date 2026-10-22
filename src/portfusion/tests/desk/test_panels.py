"""THE PANELS — the registry, and what each tab renders from the engine."""
from __future__ import annotations

import pytest
from portfusion import engine as _engine
from portfusion.desk import app, panels, engine
from portfusion.desk.panels import _shape
from desk_support import SHARES_ACCOUNT, SPREAD_BET_ACCOUNT, _static
from harness import SRC, needs


def _blank(v):
    """A figure as the page carries one: None for a blank (NaN) one."""
    return None if v is None or v != v else v


def _a_month() -> tuple[str, str] | None:
    """The calendar month of the loaded book's newest trade: a window it did something in. Typed
    as August 2026, it was one only a book of that year acted in."""
    from portfusion.record import rules
    days = sorted(str(t.date)[:10] for t in rules.trades)
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
    """THE FILE, THE URL AND THE TAB ARE ONE NAME (the owner, 2 Oct 2026). Five tabs had grown
    three each — the URL `refresh` opened What Changed while Price Refresh sat at `refresh-bay`
    — so a reader could not get from the screen to its code. A renamed tab renames its file."""
    for mod in panels.all_panels():
        stem = mod.__name__.rsplit(".", 1)[-1]
        assert mod.NAME == stem.replace("_", "-") == mod.TITLE.lower().replace(" ", "-"), (
            f"{stem}.py is served at /{mod.NAME} and titled {mod.TITLE!r}: one name, please")


@needs("trades")
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
    assert figs["YTD return (MWR)"] == _blank(b.totals()["ytd"])
    assert figs[b.SINCE_START] == _blank(b.since_start())


@needs("trades")
def test_a_blank_year_reaches_the_desk_as_a_blank(monkeypatch):
    """Until a new year's 31 December is frozen its return is blank (the owner, 2 Oct 2026), and a
    NaN would stop the Dashboard rather than show a dash: JSON has no NaN, so the panel route
    would answer 500."""
    import json
    from quarter_support import book_in_the_next_year
    monkeypatch.setattr(engine, "book", lambda: book_in_the_next_year(frozen=False))
    data = panels.get("dashboard").data()
    json.dumps(data, allow_nan=False)
    figs = {f["label"]: f["value"] for f in data["figures"]}
    assert figs["YTD return (MWR)"] is None
    assert figs[_engine.Book.SINCE_START] is None
    assert figs["Capital employed (opening + deployed)"] is None


@needs("trades")
def test_the_dashboard_says_which_year_ytd_is_and_why_it_is_blank(monkeypatch):
    """K8 (the owner, 12 Oct 2026): the page said neither which year a year-to-date figure is of nor
    why one is blank. The newest mark's date cannot say it, because the year rolls at a new
    year's first row as well as its first price; the engine's ytd_window() does, and "not frozen"
    is drawn exactly when the year's figures are blank."""
    from quarter_support import book_in_the_next_year
    live = panels.get("dashboard").data()["ytd"]
    assert live == _engine.Book().ytd_window()
    assert live["opens"] == f"{live['year'] - 1}-12-31"
    for frozen in (False, True):
        b = book_in_the_next_year(frozen=frozen)
        monkeypatch.setattr(engine, "book", lambda b=b: b)
        data = panels.get("dashboard").data()
        figs = {f["label"]: f["value"] for f in data["figures"]}
        assert data["ytd"] == {"year": live["year"] + 1, "opens": f"{live['year']}-12-31",
                               "frozen": frozen}
        assert (figs["YTD return (MWR)"] is None) is not frozen


def test_money_rounds_half_up_the_same_way_on_every_panel():
    """Snapshot rounded with Python's round() and Holdings with numpy's, and a notional on a
    half-penny read one penny on one screen and the next on the other."""
    assert _shape.money(1234.565) == 1234.57
    assert _shape.money(0.125) == 0.13 and _shape.money(-0.125) == -0.13
    assert _shape.money(None) is None and _shape.money(float("nan")) is None
    from portfusion.desk.panels import holdings
    snap = {f["label"]: f["value"] for f in panels.get("dashboard").data()["figures"]}
    assert holdings.query(by="ticker")["notional"] == snap["— of which spread-bet notional"]


def test_the_one_asserted_reconciliation_holds_on_the_desk_too():
    """total market exposure - net asset value = leverage. The build asserts it; so does this,
    because a renderer showing a leverage that does not reconcile is showing a figure from one
    view beside a figure from the other."""
    figs = {f["label"]: f["value"] for f in panels.get("dashboard").data()["figures"]}
    assert round(figs["Total market exposure"] - figs["Net asset value"], 2) == \
        figs["Exposure above net asset value"]


def test_no_figure_is_classified_by_the_desk_itself():
    """EVERY basis comes from Book.HEADLINE. This panel once classified them by hand and got
    THREE wrong — portfolio cost as money when it is mixed and reads higher than NAV precisely
    because it contains notional; unrealised and total gain under a basis the registry had not
    settled. Each is the mislabel that put the entry notional inside 'capital added'.
    Since 13 Oct 2026 the registry says a gain is money on either kind of line and
    the mixed cost figure is retired; the guard is the same — the registry decides, never this
    panel."""
    for f in panels.get("dashboard").data()["figures"]:
        # NO EXEMPTIONS. The benchmark rows that once had one are gone, and the guard is
        # absolute.
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

@needs("trades")
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
    assert [r["trade_id"] for r in got["rows"]] == list(want["trade_id"])


@needs("trades")
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


@needs("trades")
def test_a_note_is_one_line():
    """A note says what happened that the row's own columns do not, in one line, or is blank. The
    reason for a trade is reasoning.csv's, never the note's."""
    from portfusion.desk.panels import trades as A
    rows = A.data()["rows"]
    assert rows and not [r["trade_id"] for r in rows if "\n" in (r["note"] or "")]


def test_price_precision_is_the_houses_not_reinvented(repo_root):
    """GBP is 4dp because LSE prices are quoted in pence and stored /100 — a line at 12.35p is
    0.1235, which 2dp would round to 0.12. One rule, house/precision.py's: every panel answer
    carries it beside its heads — the places per currency and which fields are local prices —
    and the report reads the same module, so no two renderers can differ. app.js types neither."""
    import re
    from portfusion.desk import app as desk_app
    from portfusion.house import precision as P
    assert P.LOCAL_PRICE_DP["GBP"] == 4 and P.LOCAL_PRICE_DP["USD"] == 2
    for name in ("holdings", "trades"):
        got = desk_app.panel(name)["precision"]
        assert got["local_price_dp"] == P.LOCAL_PRICE_DP, name
        assert got["local_price_default"] == P.DEFAULT_LOCAL_PRICE_DP, name
        assert got["local_price_fields"] == list(P.LOCAL_PRICE_FIELDS), name
    js = _static("app.js")
    lp = re.search(r"const localPrice = [\s\S]*?;\n", js).group(0)
    assert not re.search(r"toFixed\(\d|\?\?\s*\d", lp), f"app.js types a local price's places: {lp}"

def test_holdings_totals_tie_to_the_engine_on_every_grouping():
    """THE TIE-CHECK FOR THIS PANEL, and it earns its place — the first version summed the
    rows by their basis label and was wrong by the whole of one basis.

    Grouped by ISSUER, a company held both ways collapses to one row carrying one basis:
    Orlant is ORLA and ORLA SB. The label stops being a partition, and summing on it
    misstates BOTH sides. Every other grouping keeps the partition, which is exactly why a
    test over ALL of them is the one worth having — a check on the default alone would have
    passed the day the panel was wrong, or failed forever after it was fixed.
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
    assert {"current_price", "priced_at"} <= set(by_issuer["columns"])


@needs("trades")
def test_an_issuer_held_both_ways_reads_mixed_and_the_panel_adds_no_marker():
    """Reported rather than hidden, in the one word: grouped by issuer, a company held as shares
    and as a bet is one row held as `mixed`, the engine's word, so a reader looking at one line
    knows part of it is money the book owns. The panel adds no marker and no list of its own
    beside the word (13 Oct 2026)."""
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


@needs("trades")
def test_round_trip_totals_follow_the_selection():
    """THE TOTALS FOLLOW THE SELECTION (the owner: "sorting by account does not change the headline
    figures to reflect the accounts selected").

    Kept whole-book while the table narrowed, the three headline numbers answered a question
    nobody had asked.

    THE TOTALS ARE STILL THE ENGINE'S: round_trip_totals() takes the selection, so the panel
    asks rather than summing its own rows. The whole book is carried alongside so the screen
    can say what a selection is part of.
    """
    from portfusion.desk.panels import round_trips
    b = _engine.Book()

    whole = round_trips.data()
    assert whole["narrowed"] is False
    assert whole["totals"] == whole["whole"]
    assert whole["totals"]["gain"] == round(b.round_trip_totals()["gain"], 2)

    acct = whole["accounts"][0]
    one = round_trips.query(account=acct)
    assert one["narrowed"] is True
    assert one["totals"]["realisations"] == one["total"], (
        "the headline count must be the selection's, not the book's")
    assert one["totals"] == {k: v for k, v in b.round_trip_totals(account=acct).items()}, (
        "the selection's totals must be the ENGINE's, not re-summed here")
    assert one["whole"] == whole["totals"], "the whole book stays available as context"


@needs("trades")
def test_round_trips_can_be_narrowed_to_a_range_of_exit_dates():
    """The owner: a date-range filter on the tab. `closed` is the date a round trip is filed under,
    and the SELECTION IS THE ENGINE'S — book.round_trips() takes start and end for the same
    reason book.activity() does."""
    from portfusion.desk.panels import round_trips
    b = _engine.Book()
    got = round_trips.query(start=_MONTH[0], end=_MONTH[1])
    want = b.round_trips(start=_MONTH[0], end=_MONTH[1])
    assert got["total"] == len(want)
    assert [r["realisation_id"] for r in got["rows"]] == list(want["realisation_id"])
    assert got["totals"]["gain"] == round(b.round_trip_totals(
        start=_MONTH[0], end=_MONTH[1])["gain"], 2)
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


@needs("trades")
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
    for account in flagged:
        assert any(account in c["scope"] for c in live), (
            f"{account} opened in a period and no caveat names it")


def test_the_tabs_run_in_the_order_of_the_work():
    """THE ORDER OF THE WORK (the owner): where the book stands, then the work, then the book's own
    pages, then the reports, which end the thread; Method and Access apart, below the rule (13 Oct
    2026). `desk/panels/__init__.py` says why each sits where it does. Pinned on
    TITLE, so a renamed or moved tab is a decision written here."""
    assert [m.TITLE for m in panels.all_panels()] == [
        "Dashboard",
        "Bench", "Price Refresh", "What Changed", "Reconcile",
        "Performance", "Holdings", "Round Trips", "Trades", "Accounts",
        "Reports",
        "Method", "Access"]
    assert [m.TITLE for m in panels.all_panels() if getattr(m, "APART", False)] == \
        ["Method", "Access"], "the pages below the rule are a decision written here"


def test_the_stage_5_query_routes_defer_to_their_panels():
    """The routes do no narrowing of their own — same rule as run_action and bench_commit.
    A bad grouping is a 400 from the PANEL's own refusal, not a second validation here."""
    from fastapi import HTTPException
    assert app.holdings(by="ticker")["by"] == "ticker"
    assert app.holdings(account=SHARES_ACCOUNT)["notional"] == 0.0
    assert app.round_trips(ticker="PENR.L")["ticker"] == "PENR.L"
    with pytest.raises(HTTPException) as e:
        app.holdings(by="nonsense")
    assert e.value.status_code == 400


# =====================================================================================
# WHAT CHANGED — the panel that must not add the two bases
# =====================================================================================

def test_the_refresh_panel_shows_the_two_bases_apart():
    """Two blocks, never one total, and each carries the engine's own figures.

    THE PLAN'S MOCK-UP HEADED THIS PANEL with a single "Total market exposure" change and
    a decomposition under it. That figure cannot be decomposed: a combined `transacted` row
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
                f"figure is a second answer to something engine.py already decided")


@needs("trades")
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

    The panel once reported only MARKET time and had to say it was silent on record time.
    `store/journal.csv` covers record time, so demanding that caveat would hold the panel to a
    limitation it no longer has.
    """
    d = panels.get("what-changed").data()
    assert "market time" in d["caveat"].lower(), \
        "the marks block no longer names its clock"
    assert "record time" in d["record"]["caveat"].lower(), \
        "the journal block no longer names its clock"

    js = _static("app.js")
    for heading in ("Market time", "Record time"):
        assert heading in js, f"the panel draws no {heading!r} heading"

    # AND THE RECORD BLOCK SAYS HOW FAR BACK IT REACHES. It is forward-only by construction,
    # and a list with no stated start reads as a complete history of the book.
    assert d["record"]["opened"], "the record block does not say when the journal opened"
    assert "forward-only" in d["record"]["caveat"].lower()


@needs("trades")
def test_the_record_block_covers_the_span_the_marks_do():
    """RECORD TIME OVER THE SAME SPAN AS MARKET TIME. The block listed every write since the
    journal opened, most of the page within weeks, and grew with every write.
    It lists the writes since the earliest window above opened and folds the rest — and
    between the two, every write is still there."""
    b = engine.book()
    r = panels.get("what-changed").data()["record"]
    starts = [w["priced_from"] for w in b.change_windows() if w["priced_from"]]
    assert starts, "no window has a start — this asserts nothing"
    assert r["since"] == min(starts), "the record block does not start where the marks do"
    assert all(row["at"] >= r["since"] for row in r["rows"])
    assert all(row["at"] < r["since"] for row in r["earlier"])
    assert len(r["rows"]) + len(r["earlier"]) == len(b.journal()), (
        "a write is in neither half of the record block")


@needs("trades")
def test_an_accounts_quarter_names_what_its_closing_nav_rests_on():
    """THE RECORD SAYS WHAT EACH QUARTER END RESTS ON and no page showed it: a
    statement, a reconstruction, a freeze from the engine — and whether that is sourced or
    derived. Each account's frozen quarter row carries its quarter end's source and quality, for
    the row's detail; the open quarter, at today's marks, and the book's rows carry none."""
    b = engine.book()
    d = panels.get("performance").data()
    assert d["detail"] == ["source", "quality"]
    series = b.account_quarter_returns(include_open=True)
    frozen = set(b.quarter_nav_total().index)
    checked = 0
    for row, end in zip(d["accounts"], series["quarter_end"].astype(str).str[:10]):
        if end in frozen:
            q = b.quarter_nav_rows(end).set_index("account").loc[row["account"]]
            assert (row["source"], row["quality"]) == (q["source"], q["quality"]), (
                f"{row['account']} {row['quarter']}")
            checked += 1
        else:
            assert row.get("source") is None, f"{row['account']} {row['quarter']} is not frozen"
    assert checked, "no frozen quarter — this asserts nothing"
    assert all(r.get("source") is None for r in d["firm"]), "a book row has an account's source"


@needs("trades")
def test_a_year_row_rebuilds_its_own_return():
    """THE YEAR TABLE SHOWED ALL INCOME BESIDE A RETURN BUILT ON POSITION INCOME:
    fees and cash interest reached its income column and never its return, so no row could be
    rebuilt. It shows the return's income now, and every row's YTD return is its own figures:
    (capital growth + income) ÷ (opening NAV + the capital deployed, each flow weighted by the
    days after it — the engine's weights, since the row carries the flows' sum)."""
    d = panels.get("performance").data()
    assert "return_income" in d["year_columns"] and "income" not in d["year_columns"]
    rows = [r for r in d["year"] if r["ytd"] is not None]
    assert rows, "no year row has a return — this asserts nothing"
    b = engine.book()
    weighted = b.weighted_flows(b.ytd_opens(), b.valued_at())
    for r in rows:
        wcf = float(weighted.sum() if r["account"] == "The book" else weighted[r["account"]])
        rebuilt = (r["capital_growth"] + r["return_income"]) / (r["opening_capital"] + wcf)
        assert abs(rebuilt - r["ytd"]) < 1e-9, (
            f"{r['account']}: the row rebuilds to {rebuilt:.4%}, the page says {r['ytd']:.4%}")


@needs("trades")
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
# MOVEMENT COLOUR
#
# `house/palette.py` heads UP and DOWN "movement, which is not provenance". That is
# the rule these two tests hold: a THIRD channel, beside font-colour-as-origin and
# fill-as-state, which must borrow from neither and must say only what a figure's SIGN is.
# =====================================================================================


def test_movement_colour_is_used_and_scoped(repo_root):
    """THE TOKENS EXISTED AND NOTHING USED THEM, which is why this test exists at all.

    `--up` and `--down` were generated into /tokens.css and referenced NOWHERE in app.css or
    app.js — so the desk rendered a loss in the same
    ink as a gain while carrying the colours to say otherwise. A token nobody consumes
    is a palette entry pretending to be a treatment.

    THE SECOND HALF IS THE JUDGEMENT, and it is the part worth guarding. Every column in the
    list is a GAIN — a figure whose sign says whether the book is better or worse off. The
    exclusions are deliberate and each would be wrong in a different way:

      difference  Reconcile. Book minus broker on a RECONCILIATION row. A gap is not a loss;
                  red on an account that ties within its band asserts something untrue.
      weight      a share of exposure, never negative, so it could only ever read green.

    If either turns up in MOVEMENTCOL later, this is the test that says why not.

    WHAT CHANGED'S COLUMNS: four are in and one is deliberately held back, which is the
    judgement worth pinning:

      change price_effect fx_effect price_move_pct
                  all four are RESULTS — the sign says whether the book is better or worse off,
                  which is the test this list has always applied.
      transacted  NOT a result, and never to be added. Buying shares is not a
                  gain and selling them is not a loss. Same exclusion as
                  `difference`: money, often negative, carrying no judgement. Colouring it
                  would turn every purchase green and every sale red.
    """
    css, js = _static("app.css"), _static("app.js")

    assert "var(--up)" in css and "var(--down)" in css, \
        "app.css does not consume the movement tokens — they are generated and unused again"

    import re
    m = re.search(r"const MOVEMENTCOL = \[(.*?)\]", js, re.S)
    assert m, "app.js no longer declares MOVEMENTCOL"
    cols = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert cols == {"gain", "gain_pct", "return",
                    "change", "price_effect", "fx_effect", "price_move_pct"}, \
        f"MOVEMENTCOL is {sorted(cols)}"

    for excluded, why in (("difference", "a reconciliation gap is not a loss"),
                          ("weight", "a share of exposure is never negative"),
                          ("transacted", "a purchase is not a gain and a sale is not a loss")):
        assert excluded not in cols, f"{excluded} must not wear movement colour — {why}"

    # ZERO WEARS NEITHER. A flat quarter is not a gain and must not read as one.
    assert "v === 0" in js, "movement() no longer leaves an exact zero uncoloured"


def test_every_screen_colour_is_legible_in_both_schemes(repo_root):
    """A COLOUR THAT CANNOT BE READ IS WORSE THAN NONE, and nothing else in the project can tell.

    It began with movement: the light scheme's two colours, #2C6A51 and #B3261E, scored 2.76 and
    2.70 against the dark paper, #141A19, below even
    the 3.0 that WCAG allows for large text. Then the sourced blue, which the desk had borrowed
    as its accent for the selected tab, links and focus: 2.23 on the dark paper, found on
    4 Oct 2026 when the desk took the book's look. So every text colour is held to 4.5 on the
    paper and on the band a header or a total row sits on, and an input's border to the 3.0 a
    control boundary needs.

    DERIVED, NOT A FIXTURE. The colours are read out of the generated tokens, both schemes,
    rather than written here, so a palette change is CHECKED instead of assumed.
    """
    def ratio(a, b):
        def lum(h):
            h = h.lstrip("#")
            ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
            return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    import re

    from portfusion.desk import theme

    light, dark = theme.tokens_css().split("@media", 1)

    def declared(text, name, fallback=None):
        """The LAST declaration of a custom property, since a later block overrides an earlier.

        `fallback` is what the scheme inherits when it does not override — which is the case
        that matters. Returning the inherited colour rather than raising is deliberate: a
        missing dark override is not a missing declaration, it is the light colour used on a
        dark ground, and the contrast assertion below is the honest way to report that.
        """
        m = re.findall(rf"--{name}:\s*(#[0-9A-Fa-f]{{6}})", text)
        if not m:
            assert fallback, f"--{name} is declared nowhere"
            return fallback
        return m[-1]

    AA, BOUNDARY = 4.5, 3.0
    pairs = ([("paper", t, AA) for t in ("ink", "muted", "heading", "link", "accent",
                                          "warn-ink", "up", "down")]
             + [("band", t, AA) for t in ("ink", "heading", "up", "down")]
             + [("recessed", "control", BOUNDARY)])
    for scheme, source in (("light", light), ("dark", dark)):
        for under, token, floor in pairs:
            ground = declared(source, under, fallback=declared(light, under))
            colour = declared(source, token, fallback=declared(light, token))
            r = ratio(colour, ground)
            assert r >= floor, (
                f"--{token} is {colour} on the {scheme} {under} {ground}, a contrast ratio of "
                f"{r:.2f} against the {floor} WCAG requires. A colour that cannot be read is "
                f"worse than one left plain.")


def test_no_panel_leaves_a_handler_on_the_frame(repo_root):
    """#main OUTLIVES EVERY PANEL, so a handler a panel adds to it on each draw stays behind and
    multiplies. The Price Refresh did, until 30 Sep 2026: four visits in, a filter change on
    another page threw four errors. A panel's handlers go on its own elements; a delegated one
    on #main is wired once, behind a guard, from a `main` it has looked up."""
    js = _static("app.js")
    assert '$("#main").addEventListener' not in js


def test_no_call_site_puts_anything_in_a_style_attribute(repo_root):
    """Every width, colour and spacing lives in app.css, so a call site sets none of them."""
    import re
    used = re.findall(r'style="([^"]*)"', _static("app.js"))
    assert not used, f"app.js sets style={used}; the style layer is app.css"


# =====================================================================================
# A HOLDINGS ROW: HOW MUCH IS HELD, AND THE MARKS BEHIND IT
# =====================================================================================

@needs("trades")
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
            assert row["stake_per_point"] == e["stake_per_point"], row["company"]
        else:
            assert row["qty"] == e["qty"] and row["stake_per_point"] is None, row["company"]
    assert all(seen.values()), f"a kind of line is missing, so half of this asserts nothing: {seen}"
    companies = b.holdings(by="issuer").set_index("company")["qty"]
    for row in panels.get("holdings").query(by="issuer")["rows"]:
        assert row["qty"] == companies[row["company"]] and row["stake_per_point"] is None, \
            row["company"]


@needs("trades")
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

    THE LAST FIVE REFRESHES (the owner, 12 Oct 2026): "we don't need to see more than five lines of
    mark changes for a trend". Every mark stays on file; the detail shows the newest five dates,
    each mark carrying its `status` so a correction is drawn under its replacement."""
    from portfusion.desk.panels import holdings as H
    for by in ("issuer", "ticker"):
        for row in panels.get("holdings").query(by=by)["rows"]:
            marks = row["marks"]
            assert marks, f"{row['company']} opens no mark history at all"
            for mark in marks:
                assert mark["source"], f"{row['company']} has a mark with no source string"
                assert mark["mark_key"], "a mark arrives without the key it was banked under"
                assert mark["status"], "a mark arrives without its lifecycle"
            dates = [m["date"] for m in marks]
            assert dates == sorted(dates, reverse=True), \
                f"{row['company']}'s history is not newest-first"
            assert len(set(dates)) <= H.MARK_REFRESHES, \
                f"{row['company']} shows {len(set(dates))} refreshes"


@needs("trades")
def test_a_multi_contract_line_opens_both_contracts():
    """HALV SB is priced by two contracts at two levels, and its marks show both."""
    keys = engine.book().changes_since().groupby("ticker")["key"].apply(set)
    several = {t: k for t, k in keys.items() if len(k) > 1}
    assert several, "no line sits on two mark keys — this asserts nothing"
    rows = {r["company"]: r for r in panels.get("holdings").query(by="ticker")["rows"]}
    tickers = engine.book().holdings(by="ticker").set_index("ticker")["company"]
    for key, keys in several.items():
        opened = {m["mark_key"] for m in rows[tickers[key]]["marks"]}
        assert keys <= opened, f"{key} is priced by {keys} but opens {opened}"


def test_the_expansion_spans_the_whole_row_however_many_columns_there_are(repo_root):
    """The colspan is DERIVED from what was rendered, never typed.

    A hardcoded number goes stale the first time a column joins — silently, by leaving the
    last cell of every expansion hanging outside the table.
    """
    js = _static("app.js")
    assert "cols.length + inserts.length" in js, \
        "the expansion's colspan is no longer derived from the rendered columns"


# =====================================================================================
# THE DESK'S OWN PROSE — a ratchet that only goes down
# =====================================================================================

#: How many words of CHROME the desk shows. A ratchet: it may only go down.
#:
#: the owner: the desk "has become very verbose growing references and notes from decisions made
#: during development and diluting the important data ... the purpose of the desk is account
#: management". It was right: Price Refresh and Reconcile each opened with four explanation
#: blocks, so the table on one and What disagrees on the other began below the fold.
#:
#: Chrome is what the desk says ABOUT ITSELF — a caveat, a note, a button's blurb. It is not the
#: record: a trade's note and a position's reasoning are FACTS and are not counted here, and they
#: are already behind a per-row toggle. Nor is anything inside a `.why-fold`, which is the whole
#: point of the fold — an explanation moved below the work it describes has stopped competing
#: with it, and pricing it the same would punish the fix.
#:
#: A ratchet, in the shape `tests/test_evidence.py:_UNCLASSIFIED_HIGH_WATER` uses. Cutting can
#: never fail it; only new prose can.
#:
#: The step line's quiet notes (`<span class="muted small">`, `quiet()`) are counted from
#: 1 Oct 2026: the steps moved out of `<li class="note">` and onto one line, and a pattern that
#: could not see them would have priced the move as a cut.
#:
#: 1075 → 834 with the page template (1 Oct 2026): the six note boxes went into the fold.
#: 834 → 752 the same day: the bench's read-it-for-me button and its registry blurb went, with
#: the API reading they belonged to.
#: 752 → 524 (12 Oct 2026, the Bench walk): it stood at 679; the Bench's paragraphs about the
#: document kind, the reasons and writing moved into its fold, rewritten for a reader, and the
#: sweep's sixty-word blurb under its button went.
#: 524 → 513 (12 Oct 2026, the Price Refresh walk): the Bank step's "all on file", the Review
#: step's counts and the sweep's "line(s) filled in below, ready to check and take".
#: 513 → 482 (13 Oct 2026, the What Changed walk): the fold's sentence saying a closed line is
#: not shown went when it was, the by-hand note's pointer to git, and both clocks' fold entries
#: rewritten shorter, the market one taking the status line's account of its windows.
#: 482 → 474 (13 Oct 2026, the Reconcile walk): the Events step's two quiet notes went with it.
#: +8 on 13 Oct 2026: the five labels under an IG reading's broker figure on Reconcile (funds ·
#: running P/L · deposit · available), figure labels the pattern counts as prose; the
#: reading keeps the figures once each and a figure kept is a figure shown.
#: 482 → 480 (14 Oct 2026): the Price Refresh's "asking …" line is one template
#: naming whom it asks, for the sweep and for the rates the record lacks alike.
#: 480 → 458: an IG event's bench action says what it does in one sentence.
DESK_CHROME_WORDS = 458


def _chrome_words(repo_root):
    """Every word the desk says about itself, counted one way. See DESK_CHROME_WORDS."""
    import re

    from portfusion.desk import actions
    from portfusion.desk import panels as _panels

    js = _static("app.js")
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)                    # source comments are not chrome
    js = re.sub(r"const RECONCILE_WHY = \[.*?\n\];", "", js, flags=re.S)   # lives in the fold
    js = re.sub(r'<details class="why-fold".*?</details>', "", js, flags=re.S)

    words = 0
    for pat in (r'<p class="caveat">(.*?)</p>', r'<p class="muted[^"]*">(.*?)</p>',
                r'<li class="note">(.*?)</li>', r'<li class="clear">(.*?)</li>',
                r'<span class="muted small"[^>]*>(.*?)</span>', r'quiet\("(.*?)"\)'):
        for hit in re.findall(pat, js, re.S):
            words += len(re.sub(r"<[^>]+>|\$\{[^}]*\}", " ", hit).split())

    for mod in _panels.all_panels():
        for name in ("CAVEAT", "NOTE", "SUMMARY"):
            value = getattr(mod, name, None)
            if isinstance(value, str):
                words += len(value.split())

    for act in actions.all_actions():
        words += len((act.summary or "").split()) + len((act.gate or "").split())
    return words


def test_the_desks_own_prose_only_goes_down(repo_root):
    """The desk is an operating interface, not a place to record decisions about it.

    Every explanation here was written for a good reason and the reasons accumulated: four
    numbered steps above the table on two panels, and about seventy-five words under each of ten
    buttons. None of it was wrong and all of it together pushed the work below the fold.

    The fix is not deletion, it is placement — `whyFold()` puts the reasons under the work they
    describe — so this counts only what still sits in the reader's way. Raising it needs a reason
    written down beside it; the ordinary way past it is to move prose into the fold or into a
    docstring, where a maintainer wants it and an operator never looks.
    """
    words = _chrome_words(repo_root)
    assert words <= DESK_CHROME_WORDS, (
        f"the desk now says {words} words about itself, above the {DESK_CHROME_WORDS} on file. "
        f"An explanation belongs below the work it describes — `whyFold()` — or in a docstring. "
        f"The ratchet only goes down; take prose out rather than raising this.")


# =====================================================================================
# THE PAGE TEMPLATE — every tab drawn the same way
# =====================================================================================

def _renderer(js, name):
    """The source of one panel's renderer, from its key to the next renderer's key."""
    import re
    key = re.compile(r'^  (?:async )?(?:"%s"|%s)\(d\) \{' % (re.escape(name), re.escape(name)),
                     re.M)
    m = key.search(js)
    assert m, f"app.js has no renderer for the {name!r} panel"
    nxt = re.compile(r'^  (?:async )?(?:"[a-z-]+"|[a-z]+)\(d\) \{', re.M).search(js, m.end())
    return js[m.start():nxt.start() if nxt else len(js)]


def test_the_dashboards_status_line_draws_what_it_is_sent(repo_root):
    """THE AGE LEADS THE PRICES STEP, and the year-to-date step names the 31 December the year
    opens at (the owner, 12 Oct 2026). A payload field the renderer drops is a figure shown nowhere.
    `year` is the one not drawn: `opens` names it."""
    js = _renderer(_static("app.js"), "dashboard")
    data = panels.get("dashboard").data()
    assert set(data["prices"]) == {"newest", "oldest", "spread_days", "marks", "age_days"}
    assert set(data["ytd"]) == {"year", "opens", "frozen"}
    missing = ([f"p.{k}" for k in data["prices"] if f"p.{k}" not in js]
               + [f"y.{k}" for k in ("opens", "frozen") if f"y.{k}" not in js])
    assert not missing, f"the Dashboard is sent {missing} and draws none of it"


def test_the_dashboard_lists_the_checks_the_audit_prints(repo_root):
    """WHAT WAS CHECKED, under what needs attention (the owner, 12 Oct 2026). The Dashboard showed
    only "clear" while `portfusion record` printed the checks behind it, and two of them — the
    evidence chain and the conversions — had no home on the desk at all: what is captured has
    a display home. The engine's notes, in its words and its order."""
    data = panels.get("dashboard").data()
    assert data["checks"] == _engine.Book().findings()["notes"]
    assert any(c.startswith("evidence:") for c in data["checks"])
    assert "d.checks" in _renderer(_static("app.js"), "dashboard")


def test_the_footer_says_whose_it_is_and_which_release(repo_root):
    """K3 (the owner, 12 Oct 2026): every page's footer said "Nothing here is typed", and the Bench
    is where rows are typed. It now says whose the desk is and which release it is, each held
    once — the book's words in its brand, the release in portfusion/__init__.py — and filled into
    the shell the Mac and the hosted desk both serve: "© <owner> · PortFusion 0.2.0 beta" (option
    C and V3, 20 Oct 2026), the app's half alone where a brand gives no ownership line."""
    import datetime
    from portfusion import about, brand
    from portfusion.desk import bundle
    template = (SRC / "desk" / "static" / "index.html").read_text()
    assert "<!-- footer -->" in template and "Nothing here is typed" not in template
    page = bundle.index().decode()
    whose = brand.ownership(datetime.date.today().year)
    line = " · ".join([*([whose] if whose else []), about.release()])
    assert f"<span>{line}</span>" in page, line


def test_every_page_is_drawn_through_the_template(repo_root):
    """The owner, 1 Oct 2026: "create a base page template so all pages have some form of synergy,
    I feel I am adjusting individual pages and tweaking without clear directions".

    Every page built its own layout, so each fix landed on one page and the others drifted: three
    pages at 992px and six at the window's width, six note boxes on five pages, three ways of
    explaining. `page()` draws the bands in one order, and a page that skips it is the drift
    starting again."""
    js = _static("app.js")
    skipped = [p.NAME for p in panels.all_panels() if "page({" not in _renderer(js, p.NAME)]
    assert not skipped, (
        f"these pages are not drawn through page(): {skipped}. A new band belongs in the "
        f"template, where every page gets it, not in one page's renderer.")


def test_the_template_has_no_note_box_and_no_pill(repo_root):
    """Two treatments the template retired (the owner, 1 Oct 2026), each of which added a second
    voice to a page: the note box between the figures and the table (explanations live in the
    fold), and the basis pill beside a figure whose label already says what it is.

    A third, NO CAPITALS, was retired in its turn on 6 Oct 2026: the design system sets its labels in condensed
    capitals, and the owner took the design system's rule over the desk's. What the 1 Oct rule protected still
    holds, because the capitals are the stylesheet's: every label is still WRITTEN in sentence
    case, which this checks instead — a heading typed in capitals would hide three spellings."""
    import re
    js, css = _static("app.js"), _static("app.css")
    assert 'class="caveat"' not in js and ".caveat" not in css, "a note box is back"
    assert 'class="basis"' not in js and ".basis" not in css, "a basis pill is back"
    typed = [h for h in re.findall(r"<(?:h2|th)[^>]*>([^<$]{4,})</", js) if h.isupper()]
    assert not typed, f"a heading is typed in capitals rather than styled so: {typed}"


def test_the_page_head_is_ruled_off_on_every_page(repo_root):
    """A rule under the title and its scope line, on every page (the owner, 1 Oct 2026): it was
    drawn only where a status line followed, as that line's own top border, so Round Trips and
    Performance had none. It belongs to the head, which every page draws through `page()`, and
    the status line no longer draws a second one beneath it."""
    import re
    css = _static("app.css")
    head = re.search(r"\.page-head \{([^}]*)\}", css).group(1)
    steps = re.search(r"\.steps \{([^}]*)\}", css).group(1)
    assert "border-bottom" in head, "the page head has lost its rule"
    assert "border-top" not in steps, "the status line draws a second rule under the head"


def test_every_wide_table_scrolls_in_its_own_box(repo_root):
    """A wide table scrolls in its own box, so the page never does. Reconcile's
    table was written by hand outside `.scroll`, and on a phone it pushed the whole page to 866px
    wide (found on the hosted desk, 15 Oct 2026). The two narrow kinds, a page's figures and
    Holdings' bars, are two or three columns and fit a phone as they are."""
    import re
    js = _static("app.js")
    narrow = ('<table class="figures">', '<table class="alloc">')
    boxed = lambda at: re.search(r'<div class="scroll"[^>]*>\s*$', js[max(0, at - 80):at])  # noqa: E731
    loose = [js[m.start():m.start() + 60].split("\n")[0] for m in re.finditer(r"<table", js)
             if not boxed(m.start()) and not js.startswith(narrow, m.start())]
    assert not loose, f"a table outside a scroll box: {loose}"


def test_the_dashboards_glance_stacks_on_a_phone(repo_root):
    """The Dashboard's figures stand beside Needs attention. On a phone that
    left the list one letter wide, off the screen's edge (found on the hosted desk, 15 Oct 2026),
    so at the phone's width, the 48rem the gutter narrows at, the list goes below them."""
    import re
    css = _static("app.css")

    def block(at):
        depth, i = 0, css.index("{", at)
        for j in range(i, len(css)):
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            if depth == 0:
                return css[i:j]
    phone = "".join(block(m.start()) for m in re.finditer(r"@media \(max-width: 48rem\)", css))
    glance = re.search(r"\.glance \{([^}]*)\}", phone)
    assert glance and "grid-template-columns: minmax(0, 1fr)" in glance.group(1), \
        "on a phone the Dashboard's glance still sets its two columns side by side"


def test_every_filter_row_can_be_cleared(repo_root):
    """The filters band is one shape on every page, and "clear filters" is part of it — it was on
    two of the three pages with filters."""
    import re
    js = _static("app.js")
    rows = re.findall(r"filters: \{([^\[]*)fields:", js)
    assert rows and all("clear:" in r for r in rows), \
        "a page's filters band has no clear link"


# =====================================================================================
# RETIRED TAB TITLES AND BUTTON LABELS — a rename leaves nothing calling the old name
# =====================================================================================

#: TAB TITLES THAT NO LONGER EXIST, and what replaced each. A renamed tab leaves its old name
#: scattered through docstrings, comments and guides that a reader then cannot find on screen —
#: prose drifting from behaviour, which is the defect this project is built to catch. Renaming
#: two tabs once touched 43 references across 17 files, and the risk was missing one. This is
#: what makes that checkable instead of careful.
RETIRED_TAB_TITLES = {
    # The keys are spelled out here rather than assembled, because a blanket rename over this
    # file rewrote them into their own replacements the first time — the list that polices a
    # rename cannot itself be a casualty of one. (tab-name-ok: this is the retired list)
    "Last Refresh": "What Changed",     # 7 Sep 2026
    "Refresh Bay": "Price Refresh",     # 8 Sep 2026
    "What changed": "What Changed",     # 8 Sep 2026 — title case, matching its neighbours
}


#: Action labels that no longer exist, policed by the same test for the same reason. A button
#: is a thing an operator is TOLD to press — by docs/reconciling.md, by the close checklist the
#: build prints — so a renamed one strands an instruction that cannot be followed. Renaming the
#: reading button touched four such references, in three files and two languages.
RETIRED_ACTION_LABELS = {
    "Take a reading": "Price Refresh",             # 9 Sep 2026, renamed for its scope
    "Read IG live valuations": "Price Refresh",    # 29 Sep 2026 — IG equity is read with the
                                                   # contract levels in the sweep
}


def test_no_file_names_a_tab_or_button_that_no_longer_exists(repo_root, project_files):
    """A retired tab title or button label may appear only on a line that also names what
    replaced it.

    THAT EXCEPTION IS THE POINT, not a loophole. "Last Refresh is now What Changed" is a
    sentence worth keeping — it tells a reader who remembers the old name where the thing
    went. What must not survive is prose that simply calls a tab by a name the tab strip no
    longer shows.

    `_archive/` IS READ: its evidence is none of the three file types scanned here, and its
    guide is kept current like any other.
    """
    stale = []
    for path in project_files(".py", ".js", ".md"):
        if "_inbox" in path.relative_to(repo_root).parts:
            continue
        rel = path.relative_to(repo_root).as_posix()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for old, new in {**RETIRED_TAB_TITLES, **RETIRED_ACTION_LABELS}.items():
                # The new name often CONTAINS the old ("What changed" / "What Changed" differ
                # by one letter), and the escape is the new name appearing in its own right on
                # the same line.
                if "tab-name-ok" in line:
                    continue                    # explicitly exempted, with its reason beside it
                # CAPITALS TOO. A retired name is also caught in capitals, the form headings
                # use; matching exactly let two headings keep old names for a fortnight
                # (tab-name-ok: "THE REFRESH BAY", "LAST REFRESH"). Not in lower case:
                # "since the last refresh" is English, not a tab. A rename of case alone
                # has no capital form of its own, so it stays exact (tab-name-ok).
                forms = (old,) if old.lower() == new.lower() else (old, old.upper())
                if any(f in line for f in forms) and new not in line and new.upper() not in line:
                    stale.append(f"{rel}:{n} names {old!r} (now {new!r}): {line.strip()[:70]}")
    assert not stale, (
        "these name a tab that no longer exists:\n  " + "\n  ".join(stale[:12]))


def test_every_live_tab_title_is_one_a_panel_declares(repo_root):
    """The other half: the retired list must not name something still in use. A rename that
    was reverted, or never finished, would otherwise be policed against the wrong answer."""
    live = {m.TITLE for m in panels.all_panels()}
    wrongly_retired = live & set(RETIRED_TAB_TITLES)
    assert not wrongly_retired, (
        f"{sorted(wrongly_retired)} are listed as retired but a panel still declares them")
    for new in RETIRED_TAB_TITLES.values():
        assert new in live, f"{new!r} is named as a replacement but no panel declares it"


# =====================================================================================
# ONE WORD FOR A SPREAD-BET POSITION, on the desk as in the engine
# =====================================================================================

def test_the_desk_says_notional_too(repo_root):
    """A RENDERER NO CHECK COVERS DRIFTS. `notional` won because it is the store's own word, and
    while the only check read another renderer's labels the desk's Holdings panel said "Economic
    interest" until the owner caught it by eye, which is exactly the job a test should have.

    LABELS, NOT PROSE: the phrase survives where it DEFINES the term — "notional is the size of
    an economic interest" is the sentence that teaches it — and not where it replaces it.
    """
    js = (SRC / "desk" / "static" / "app.js").read_text()
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


@needs("trades")
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


@needs("trades")
def test_a_trade_carries_its_source():
    """Every figure traces to a named source, and the reader can see which."""
    from portfusion.desk.panels import trades
    rows = trades.data()["rows"]
    assert rows and all(r["source"] for r in rows)


@needs("trades")
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


def test_the_method_page_renders_the_records_rules():
    """The method's rules are the record's constants, interpolated rather than retyped, so a
    change to one reaches the page."""
    from portfusion.desk.panels import method
    from portfusion.record import rules as D
    text = " ".join(r["text"] for s in method.data()["sections"] for r in s["rows"])
    for rule in (D.SPREAD_BET, D.STATEMENT_GRADE, D.SOURCE_HIERARCHY, D.SOURCE_HIERARCHY_NOTE):
        assert rule in text
    assert f"{D.REVIEW_FROM:%-d %b %Y}" in text
