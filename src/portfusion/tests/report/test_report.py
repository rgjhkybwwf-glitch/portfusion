"""
THE REPORT PAGE — and its completeness gate.

The rendered page is the ONLY report artefact. A quarter's INPUTS are frozen: a report
regenerates identically forever because the marks it valued at cannot move.

THE GATE IS THE THING WORTH TESTING. A report built from a half-arrived quarter looks
finished and is wrong, which is the worst failure available to a document somebody reads.
"""
import subprocess
import sys

import pandas as pd
import pytest

from portfusion.engine import Book
from portfusion.record import rules as D
from portfusion.report.gate import completeness
from portfusion.report.page import first_reported, notice, render, summary_figures
from harness import ROOT, SRC, holds, needs

FIRST_REPORTED = first_reported()

#: A QUARTER WITH EVERY INPUT ON FILE, AND BEFORE THE FIRST REPORTED ONE: the loaded book's newest
#: such, never a typed date another book would not hold. None where there is none, and each test
#: reading it skips.
COMPLETE = next((q for q in sorted((str(d)[:10] for d in Book().quarter_nav_total().index),
                                   reverse=True) if q < FIRST_REPORTED and not completeness(q)),
                None)
NOT_YET = Book.quarter_to_close().date().isoformat()   # the quarter the next close is for


@needs("quarter-nav", "buys")
def test_a_closed_quarter_is_reportable():
    assert completeness(COMPLETE) == [], \
        f"{COMPLETE} should be complete: {completeness(COMPLETE)}"


def test_the_engine_names_every_price_and_rate_a_date_lacks():
    """THE WHOLE LIST, NOT THE FIRST: fetching only the first named would only reveal the next.
    The report reads no mark, so the list is the freeze door's to give (`freeze.plan()`).

    For every quarter the desk lists: a line whose marks cannot be found has every missing key in
    `valuation_gaps()`, a line that can be priced has none there, and every currency without a
    rate is named. With no gap, the date values."""
    from portfusion.engine import MissingMark
    from portfusion.desk import engine
    b = Book()
    for q in [x["quarter_end"] for x in engine.reports()["quarters"]]:
        gaps = b.valuation_gaps(q)
        px, fx = b._marks_at(q)
        ident = b._identity().set_index("ticker")
        lacking, rates = set(), set()
        for ticker, r in b.as_of(q).set_index("ticker").iterrows():
            try:
                b._marks_for(ticker, q, px, r["qty"])
            except MissingMark as e:
                lacking.update(e.keys)
            cur = b._converts_from(ticker, ident)
            if cur is not None and cur not in fx:
                rates.add(cur)
        assert set(gaps["prices"]) == lacking and set(gaps["rates"]) == rates, (q, gaps)
        if not any(gaps.values()):
            b.holdings_at(q)


@holds(COMPLETE, what="a complete quarter before the first report")
def test_the_gate_asks_for_the_frozen_composition_the_page_reads(monkeypatch):
    """A quarter end without its holdings frozen is not ready, whatever its marks."""
    monkeypatch.setattr(D, "QSNAP_FROZEN", [d for d in D.QSNAP_FROZEN if d != COMPLETE])
    said = " ".join(completeness(COMPLETE))
    assert "quarter-snapshots" in said and "frozen composition" in said, said
    assert "marks" not in said, said


@needs("quarter-nav", "buys")
def test_the_gate_asks_for_the_quarters_opening():
    """The page reads the quarter's opening as well as its end: its return runs from the previous
    quarter end's net asset value. The record's opening has none before it, so however much is
    frozen there it is never offered as a page of its own."""
    said = " ".join(completeness(Book().baseline_asof))
    assert "opening" in said and "quarter-nav" in said, said


def test_the_gate_and_the_page_read_no_mark(monkeypatch):
    """A frozen quarter end is reported from what was frozen: the marks may have moved since, and
    a page that read them could not regenerate as it first printed."""
    def no_marks(self, *a, **k):
        raise AssertionError("a mark was read")
    monkeypatch.setattr(Book, "_marks_at", no_marks)
    for d in _frozen_quarters():
        assert completeness(d) == [], d
        render(d)


@needs("quarter-nav", "buys")
def test_an_unclosed_quarter_is_refused_and_says_why():
    """Naming what is missing is half the value. 'Not ready' on its own sends someone
    hunting through four stores.

    NO MARKS GAP, and asserting its absence is the stronger check: a gap here would be an open leg
    keyed to a closed contract, unpriced by design. An unclosed quarter lacks only its own NAV
    rows, which arrive when it is frozen.

    A MISSING BROKER READING IS NOT A GAP: the report prints each account's check as status, so
    the gate never asks for one.
    """
    gaps = completeness(NOT_YET)
    assert gaps, f"{NOT_YET} has not closed — the gate must refuse it"
    joined = " ".join(gaps)
    assert "quarter-nav" in joined
    assert "account-statements" not in joined, "the broker checks gate the report"
    assert "marks" not in joined, (
        "a marks gap means a held position cannot be valued from the record, and every open "
        f"leg has a contract-keyed mark: {gaps}")
    for account in D.ACCOUNT_ORDER:
        assert account in joined, f"{account} is missing but is not named"


def test_the_report_is_rendered_and_never_written(tmp_path, monkeypatch):
    """The desk renders every report for the request, so a page written to a folder is a second
    copy left to age. Nothing in report/ writes a file, and its command line only asks whether a
    quarter is ready."""
    import re
    import portfusion.report.__main__ as cli
    import portfusion.report.page as page
    assert not hasattr(page, "generate"), "report.page writes a page"
    for path in sorted((SRC / "report").glob("*.py")):
        src = path.read_text()
        assert not re.search(r"write_text|write_bytes|\.mkdir\(|open\([^)]*['\"][wa]", src), path.name
    monkeypatch.chdir(tmp_path)
    assert cli.main([COMPLETE]) == 2, "a bare date is answered with the usage"
    assert list(tmp_path.iterdir()) == []


@needs("quarter-nav", "buys")
def test_a_page_asks_one_engine(monkeypatch):
    """ONE PAGE, ONE `Book()`. `summary_figures()` takes the page's engine, and alone builds its
    own, which is how the registry's test calls it."""
    import portfusion.report.page as page
    made = []

    class Counted(page.Book):
        def __init__(self, *args, **kwargs):
            made.append(self)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(page, "Book", Counted)
    page.render(COMPLETE)
    assert len(made) == 1, f"one page built {len(made)} engines"


def test_the_cli_says_not_ready_and_exits_nonzero():
    """The gate's voice in a terminal: a quarter not yet complete is NOT READY, with its gaps,
    exit 1, and no traceback."""
    r = subprocess.run([sys.executable, "-m", "portfusion.report", "--check", NOT_YET],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "NOT READY" in r.stdout and "·" in r.stdout
    assert "Traceback" not in r.stderr, "it refused by crashing, not by refusing"


@needs("quarter-nav", "buys")
def test_the_page_carries_the_statements_that_must_travel_with_the_figures():
    """WHAT MUST TRAVEL WITH THE FIGURES.

    The page carries the BASIS of each figure rather than a paragraph explaining the split:
    the concept is stated once, in rules.SPREAD_BET, and a basis per figure makes the same
    claim where a reader cannot skip it.

    The method's name stays, because it names the METHOD behind a published return and a
    reader cannot derive it from the figure."""
    page = render(COMPLETE)
    assert "Modified Dietz" in page
    # The basis travels with every headline figure, from the registry.
    from portfusion.engine import Book
    for f in summary_figures(COMPLETE):
        assert f["basis"] == Book.basis_of(f["label"])
    assert {f["basis"] for f in summary_figures(COMPLETE)} & {"notional", "capital"}


@needs("quarter-nav", "buys")
def test_every_report_says_the_positions_are_the_firms_own():
    """What `notice()` says reaches the page, both halves of it."""
    page = render(COMPLETE)
    assert "not a recommendation" in page
    assert "not a reported period" in page


@needs("quarter-nav", "buys")
@pytest.mark.parametrize("quarter_end", [COMPLETE, FIRST_REPORTED])
def test_the_report_names_every_account_by_its_code_and_no_holder(quarter_end):
    """THE REPORT IS THE DOCUMENT THAT LEAVES THE BOOK, so wherever it is read, on the Mac or on
    the hosted desk, an account is its register code and label, and no holder's name, register
    name or account number is on the page."""
    import re
    b = Book()
    page = render(quarter_end)
    for r in b.account_register().itertuples(index=False):
        for word in (r.account, r.number, *r.holder_names):
            assert not re.search(rf"\b{re.escape(word)}\b", page), f"the report names {word!r}"
    for label in b.account_codes()["label"]:
        assert label in page, f"{label} is not on the page"


@needs("quarter-nav", "buys")
def test_a_reported_quarter_does_not_claim_to_be_unreported():
    """The narrower fact drops away from Q3; the standing one must not, in 2027 or after.

    Tested on notice() directly, because it is a property of the page rather than of the
    completeness gate.
    """
    reported = notice(FIRST_REPORTED)
    assert "not a recommendation" in reported
    assert "not a reported period" not in reported, "Q3 onward IS a reported period"
    assert "not a reported period" in notice("2026-06-30")
    assert "not a recommendation" in notice("2027-12-31")


@needs("quarter-nav", "buys")
def test_the_report_is_reproducible():
    """THE POINT OF FREEZING THE INPUTS. Two renderings of the same quarter are identical."""
    assert render(COMPLETE) == render(COMPLETE)


def test_it_values_at_the_quarter_end_not_today(tmp_path):
    """A report valued at today's prices would change every time it was asked for. Every
    mark used must be dated ON OR BEFORE the quarter end — never after, which would value
    a quarter using information that did not exist at the time."""
    from portfusion.engine import Book
    h = Book().holdings_at(COMPLETE)
    assert (h["priced_at"] <= COMPLETE).all(), \
        f"a mark dated after the quarter end was used: {h.loc[h['priced_at'] > COMPLETE].to_dict()}"


# THE PAGE COMPUTES NOTHING ITSELF — tests/test_figures.py holds that for both
# renderers, walking the syntax tree for aggregation calls against an allow-list that carries
# a reason per line.


# =====================================================================================
# THE FIGURES ON THE PAGE
# =====================================================================================

def _section(page: str, heading: str) -> str:
    """The HTML of one section, found by its HEADING and not by its number.

    ANCHORED ON THE TITLE: renumbering the sections breaks no test that is not testing the
    numbering.

    It is the rule this suite follows for a table: anchor on a heading's text, never on a
    position, because a positional literal goes stale silently. A section number is the
    same literal wearing different clothes.
    """
    marker = f"<h2>{heading}</h2>"
    assert marker in page, f"no section headed {heading!r} — the page's headings have changed"
    return page.split(marker, 1)[1].split('<div class="snum">', 1)[0]


def _account_rows(page: str) -> list[tuple[str, str, str]]:
    """(account, net asset value, basis) off each By account row — opening, capital deployed and
    return sit between the account and its value and are not what these tests hold."""
    import re
    return re.findall(
        r'<tr><td>([^<]+)</td><td class="n">[^<]+</td><td class="n">[^<]+</td>'
        r'<td class="n">([^<]+)</td><td class="n">[^<]+</td><td class="dim">([^<]+)</td></tr>',
        _section(page, "By account"))


@needs("quarter-nav", "buys")
def test_the_by_account_amount_and_its_basis_come_from_the_same_row():
    """THE AMOUNT AND ITS BASIS COME FROM ONE ROW: a spread-bet account holds a notional row and
    an equity row, and NAV must never wear the exposure word.
    """
    b = Book()
    label = dict(zip(b.account_codes()["account"], b.account_codes()["label"]))
    expected = {label[r.account]: (round(r.amount, 2), r.contribution)
                for r in b.quarter_nav_rows(COMPLETE).itertuples()}
    for account, amount, basis in _account_rows(render(COMPLETE)):
        want_amount, want_basis = expected[account]
        assert basis == want_basis, \
            f"{account}: page says basis '{basis}', the record says '{want_basis}'"
        assert float(amount.replace(",", "")) == pytest.approx(want_amount, abs=1.0), \
            f"{account}: page says {amount}, the record says {want_amount}"


@needs("quarter-nav", "buys")
def test_a_net_asset_value_column_never_shows_an_exposure_basis():
    """The general form of the rule above. The By account amount is headed "Net asset value",
    so every basis beside it must be one the engine is willing to SUM INTO NAV. `notional` is
    not, and a page that shows it there is claiming exposure is money."""
    b = Book()
    for account, _amount, basis in _account_rows(render(COMPLETE)):
        assert basis in b.NAV_BASES, \
            f"{account} shows basis '{basis}' under Net asset value — not in NAV_BASES"


@needs("quarter-nav", "buys")
def test_the_by_account_rows_total_to_the_engines_net_asset_value():
    page = render(COMPLETE)
    rows = _account_rows(page)
    assert rows, "Section 8 rendered no account rows"
    total = sum(float(a.replace(",", "")) for _, a, _ in rows)
    assert total == pytest.approx(Book().quarter_nav_total()[COMPLETE], abs=len(rows))


@needs("quarter-nav", "buys")
def test_the_activity_section_covers_the_quarter_and_nothing_before_it():
    """Its start is `Book.quarter_start()`, never a hand-rolled offset."""
    import datetime as dt
    import re
    shown = re.findall(r'<td class="dim">(\d{1,2} [A-Z][a-z]{2} \d{4})</td>',
                       _section(render(COMPLETE), "Investment activity"))
    dates = [dt.datetime.strptime(d, "%d %b %Y").date().isoformat() for d in shown]
    assert dates, "Section 6 rendered no activity"
    start = Book().quarter_start(COMPLETE)
    assert min(dates) >= start, f"activity begins {min(dates)}, before the quarter's {start}"
    assert max(dates) <= COMPLETE, f"activity runs to {max(dates)}, past the quarter end"


def test_the_quarter_start_is_derived_not_typed():
    from portfusion.engine import Book
    assert Book.quarter_start("2026-03-31") == "2026-01-01"
    assert Book.quarter_start("2026-06-30") == "2026-04-01"
    assert Book.quarter_start("2026-09-30") == "2026-07-01"
    assert Book.quarter_start("2026-12-31") == "2026-10-01"


@needs("quarter-nav", "buys")
def test_a_quarter_opens_where_the_last_one_closed():
    """ONE NAME, ONE DATE. `Book.quarter_start()` is a quarter's first day; the day its return is
    measured FROM is the quarter end before, which the returns carry as `opens`, the engine's word
    for that day (`ytd_opens()`)."""
    from portfusion.engine import Book
    b = Book()
    frozen = set(b.quarter_nav_total().index)
    for frame in (b.quarter_returns(), b.account_quarter_returns()):
        assert "quarter_start" not in frame.columns
        assert set(frame["opens"].astype(str).str[:10]) <= frozen
    for r in b.quarter_returns().itertuples():
        assert str(r.opens)[:10] < Book.quarter_start(str(r.quarter_end)[:10])
    year_end = next(d for d in sorted(frozen, reverse=True) if f"{int(d[:4]) - 1}-12-31" in frozen)
    assert "opens" in b.year_to_quarter(year_end) and "quarter_start" not in b.year_to_quarter(year_end)


# =====================================================================================
# THE FROZEN QUARTER END, READ WHOLE
#
# The holdings, the split and the contributions read the composition the freeze wrote, so the
# page adds to its own headline instead of explaining a gap to a revaluation of the same day.
# =====================================================================================

def _engine_frozen():
    """Every quarter end the freeze wrote — the first report onward. Earlier compositions were
    reconstructed by hand and may be short a line, which the page says."""
    return [d for d in D.QSNAP_FROZEN if d >= FIRST_REPORTED]


def _frozen_quarters():
    """Every frozen quarter end with a quarter behind it, each a page. The record's opening may be
    frozen too, and opens the first quarter rather than closing one."""
    closed = {str(q)[:10] for q in Book().quarter_returns()["quarter_end"]}
    return [d for d in sorted(D.QSNAP_FROZEN) if d in closed]


def test_a_quarter_the_freeze_wrote_adds_up_to_its_exposure():
    """The Holdings total row is the engine's, and the lines add to it and to the exposure frozen
    beside them, less the gap the page states."""
    b = Book()
    for d in _engine_frozen():
        lines, total = b.quarter_lines(d), b.quarter_lines_total(d)
        assert total["gap"] == pytest.approx(0.0, abs=0.05), d
        for f in ("cost", "value", "unrealised"):
            assert total[f] == pytest.approx(lines[f].sum(), abs=0.005), (d, f)
        assert total["value"] + total["gap"] == pytest.approx(b.quarter_exposure_total()[d], abs=0.005)
        assert lines["weight"].sum() == pytest.approx(1.0)


def test_a_quarter_end_counts_the_positions_it_froze():
    """THE PAGE QUOTES THE REGISTRY, AND THE REGISTRY READS THE STORE. Every frozen quarter end,
    the page's count and the registry's are the composition's own."""
    b = Book()
    for d in _frozen_quarters():
        n = b.headline(d)["Open positions"]
        assert n == len(b.quarter_lines(d)), d
        assert f"{len(D.accounts_open(d))} / {n:,.0f}" in render(d), d


@needs("quarter-nav", "buys")
def test_a_composition_apart_from_its_exposure_says_both_figures(monkeypatch):
    """A gap either way reads true: the lines' total beside Section 1's exposure. A negative one
    never reads "short"."""
    q = max(D.QSNAP_FROZEN)
    real = Book.quarter_lines_total
    monkeypatch.setattr(Book, "quarter_lines_total", lambda self, d: {**real(self, d), "gap": -500.0})
    page = render(q)
    exposure = Book().headline(q)["Total market exposure"]
    assert "short" not in page
    assert "These lines total &pound;" in page
    assert f"Section 1&rsquo;s exposure is &pound;{exposure:,.0f}." in page


def test_a_line_is_named_by_its_ticker_first():
    """The frozen composition is one row per ticker, and a company
    held both ways is two rows told apart by Held as alone without one. Holdings and both of the
    contributors' tables lead with the Ticker, as the desk's Holdings does."""
    from portfusion.house.headings import heading
    tick = heading("Holdings", "ticker")
    b = Book()
    for d in _frozen_quarters():
        page = render(d)
        holdings = _section(page, "Holdings")
        assert holdings.split("<thead><tr><th")[1].split(">", 1)[1].startswith(tick), d
        first = b.quarter_lines(d)["ticker"].iloc[0]
        assert f"<tr><td>{first}</td>" in holdings, d
        movers = _section(page, "Contributors and detractors")
        heads = [h.split(">", 1)[1] for h in movers.split("<thead><tr><th")[1:]]
        assert all(h.startswith(tick) for h in heads), (d, heads)
        assert heads or "Not available" in movers, d


def test_the_quarters_trades_read_as_the_desks_trades():
    """Section 6 takes the desk's Trades columns in their order, the deal as struck with a spread
    bet in its own terms, then Realised gain, which the report keeps because it has no Round
    Trips page to carry it. A price prints one way on both."""
    import re
    from portfusion.desk.panels import trades
    from portfusion.house.headings import heading
    from portfusion.house.precision import local_price, points
    want = [heading("Trades", c) for c in trades.COLUMNS] + [heading("Trades", "realised")]
    b = Book()
    for d in _frozen_quarters():
        act = _section(render(d), "Investment activity")
        assert re.findall(r"<th[^>]*>([^<]*)</th>", act) == want, d
        for r in b.activity(start=b.quarter_start(d), end=d).itertuples():
            bet = r.level_points == r.level_points
            price = points(r.level_points) if bet else local_price(r.traded_price, r.currency)
            assert f'<td class="n">{price}</td>' in act, (d, r.ticker, price)


def test_the_contributions_close_on_the_lines_and_the_sales():
    """Each line's closing figure is its unrealised gain in the frozen composition, and the
    realised column is every sale in the quarter — nothing sold inside it is missed."""
    b = Book()
    for d in _engine_frozen():
        c = b.quarter_contributions(d).set_index("ticker")
        lines = b.quarter_lines(d).set_index("ticker")["unrealised"]
        assert (c.loc[lines.index, "closing"] - lines).abs().max() < 0.01, d
        prev = b.quarter_returns().set_index("quarter_end").loc[d, "opens"]
        act = b.activity(start=prev, end=d)
        sold = act[(act["direction"] == "Sell") & (act["date"] > pd.Timestamp(prev))]
        assert c["realised"].sum() == pytest.approx(sold["realised"].sum(), abs=0.01), d
        parts = b.quarter_attribution(d)
        assert parts["lines"] + parts["position_income"] + parts["unattributed"] == \
            pytest.approx(parts["gain"], abs=0.01)


def test_the_income_table_is_the_income_the_return_counts_and_the_rest():
    b = Book()
    for d in _engine_frozen():
        prev = b.quarter_returns().set_index("quarter_end").loc[d, "opens"]
        t = b.income_summary(start=prev, end=d).set_index("account")
        assert t.loc["Total", list(D.POSITION_INCOME)].sum() == pytest.approx(
            float(b.position_income(start=prev, end=d).sum()), abs=0.01), d
        assert list(t.index) == b.accounts_open(d) + ["Total"]


@needs("quarter-nav", "income")
def test_a_quarters_income_table_lists_the_accounts_open_then():
    """A quarter's income table names the accounts its other tables do: one whose record had not
    begun by the quarter end has no 0.00 line, as it has no NAV row, unless it earned in it."""
    b = Book()
    if not D.ACCOUNT_BEGINS:
        pytest.skip("no account in this book opened after it")
    for d in D.QSNAP_FROZEN:
        start = b.quarter_opens(d)
        earned = {r.account for r in D.ci_rows if start < str(r.date)[:10] <= d}
        want = [a for a in D.ACCOUNT_ORDER if a in set(b.accounts_open(d)) | earned]
        t = b.income_summary(start=start, end=d).set_index("account")
        assert list(t.index)[:-1] == want, (d, list(t.index))


@needs("quarter-nav", "buys")
def test_the_year_to_a_quarter_is_the_quarters_own_measure():
    """Over the first quarter the year and the quarter are the same span, so one formula must
    give one answer."""
    b = Book()
    first = b.quarter_returns().iloc[0]
    ytd = b.year_to_quarter(first["quarter_end"])
    assert ytd["return"] == pytest.approx(first["return"])
    assert ytd["gain"] == pytest.approx(first["gain"])


def test_the_last_check_is_the_newest_up_to_the_window_and_no_later():
    """The newest reading up to the window's end, whenever it fell, and none after it: a
    later one reaching the page would make it regenerate differently."""
    b = Book()
    st = b.statements()
    for d in _engine_frozen():
        until = pd.Timestamp(d) + pd.Timedelta(days=D.CLOSE_CHECK_WINDOW_DAYS)
        got = b.quarter_readings(d, latest=True).set_index("account")["as_of"]
        for account, as_of in got.items():
            dates = pd.to_datetime(st.loc[st["account"] == account, "as_of"])
            assert pd.Timestamp(as_of) == dates[dates <= until].max(), account


#: Every answer `Book.quarter_evidence()` may give for `held`.
HELD = {"on file", "NOT on file", "read live", "retrieved another way", None}


def test_what_a_figure_rests_on_is_decided_by_the_engine_not_the_page():
    """Section 9 prints `Book.quarter_evidence()`."""
    for path in sorted((SRC / "report").glob("*.py")):
        src = path.read_text()
        for name in ("_archive", "reference_resolves", "evidence_from_source"):
            assert name not in src, f"report/{path.name} uses {name}; ask Book.quarter_evidence()"


@needs("quarter-nav", "buys")
def test_the_archive_decides_on_file_and_a_live_read_needs_none():
    """The same checks against an empty archive and the real one, at the newest frozen quarter
    end: a cited document is on file only where the archive holds it, and a live read is one
    either way."""
    b = Book()
    q = str(b.quarter_nav_total().index.max())[:10]
    listed = b.quarter_evidence(q).set_index("account")["held"]
    if "read live" not in set(listed):
        pytest.skip(f"no account at {q} was read live")
    empty = b.quarter_evidence(q, filed=[]).set_index("account")["held"]
    assert set(listed) | set(empty) <= HELD
    assert "on file" not in set(empty), "an empty archive filed a document"
    for account, held in listed.items():
        assert empty[account] == ("NOT on file" if held == "on file" else held), account



@needs("quarter-nav", "buys")
def test_another_accounts_statement_does_not_put_this_one_on_file():
    """A DATE IS NOT A DOCUMENT, AND NEITHER IS A DATE AND A BROKER. A statement is on file for
    its own account only, never on the strength of another's of the same day. Here every
    statement the archive holds is another account's."""
    b = Book()
    q = str(b.quarter_nav_total().index.max())[:10]
    at = b.quarter_readings(q, latest=True, checks=True).set_index("account")
    others = []
    for account in at.index:
        src = str(at.loc[account, "source"])
        ev, ref = D.evidence_from_source(src), D.archive_reference(src)
        if ev is not None and ev.found_by == "date" and ref:
            others.append(f"{ref} {ev.authority} (an account not in this book).pdf")
    if not others:
        pytest.skip(f"no reading at {q} cites a dated statement")
    held = b.quarter_evidence(q, filed=others).set_index("account")["held"]
    assert "on file" not in set(held), held.to_dict()


@needs("quarter-nav", "buys")
def test_no_check_answers_none_never_nan(monkeypatch):
    """No reading at all answers None in every column. pandas 3 stores a missing str as NaN,
    which is truthy, and the page would print "nan". A quarter that opens at nothing has no
    gain, and its cell is a dash in no colour."""
    import re
    b = Book()
    before = b.quarter_evidence("2020-03-31")
    assert list(before["account"]) == list(D.ACCOUNT_ORDER)
    assert before[["as_of", "document", "held"]].map(lambda v: v is None).all().all()

    real = Book.quarter_returns

    def opened_at_nothing(self, *a, **k):
        q = real(self, *a, **k)
        return pd.concat([q.iloc[:1].assign(**Book._dietz_row(0.0, 0.0, 0.0, 0.0, 0.0)), q],
                         ignore_index=True)
    monkeypatch.setattr(Book, "quarter_returns", opened_at_nothing)
    page = render(_frozen_quarters()[-1])
    assert not re.search(r"\bnan\b", page, re.I), "a blank printed as nan"
    assert '<td class="n dim">—</td>' in page, "a blank gain wears a colour or a figure"


def test_a_quarter_end_cites_a_broker_check_or_says_there_is_none():
    """THE LAST BROKER CHECK, NEVER THE RECORD'S OWN FIGURE. The statements
    history mirrors the frozen quarter-nav rows, so an account's newest reading at a quarter end
    could be the engine's own derivation, or "Account not yet funded". A reading whose source
    names no evidence class is no check: the account shows the check before it, or "no broker
    check"."""
    b = Book()
    for d in _frozen_quarters():
        rows = b.quarter_evidence(d).to_dict("records")
        assert all(r["document"] is not None for r in rows if r["as_of"] is not None), (d, rows)
        page = render(d)
        assert "not a classified document" not in page, d
        assert ("no broker check" in page) == any(r["as_of"] is None for r in rows), d


@needs("quarter-nav", "buys")
def test_the_reports_footer_says_whose_it_is():
    """The desk's footer says whose it is, and the report, the document that leaves the book,
    says it too, in the same words from the book's brand, beside the stamp of the code and data
    that made it. A book whose brand gives none has the stamp alone."""
    import datetime
    import html
    from portfusion import brand
    footer = render(COMPLETE).split("<footer>")[1].split("</footer>")[0]
    assert footer.startswith(html.escape(brand.ownership(datetime.date.today().year) or "built "))
    from portfusion import about
    assert about.release() in footer and "store " in footer, "the stamp must stay beside it"


def test_check_is_read_wherever_it_stands(monkeypatch):
    """`--check` is read wherever it stands, and a command with no date says how it is used
    rather than raising."""
    import portfusion.report.__main__ as cli
    monkeypatch.setattr(cli, "completeness", lambda date: [])
    assert cli.main(["--check", COMPLETE]) == 0
    assert cli.main([COMPLETE, "--check"]) == 0
    assert cli.main(["--check"]) == 2


# =====================================================================================
# THE REPORT'S OWN WORDS
# =====================================================================================

#: EVERY WORD THE REPORT TYPES ABOUT ITSELF, counted one way (`_report_words()`): the notes
#: beneath its tables, the figure strip's lines, its sub-titles, the words an empty or unavailable
#: table prints, its row labels, the lede and the notice, the evidence words, and the engine's one
#: sentence it prints (`Book.OPENED_IN_PERIOD`). Headings are house/headings.py's and section
#: titles are headings, so neither counts. DESK_CHROME_WORDS holds the desk's in the same way.
REPORT_PROSE_WORDS = 160

#: Where the page types prose, in report/page.py's own source.
_PROSE = (r'<p \{_NOTE\}>(.*?)</p>', r'<div class="sub">(.*?)</div>', r'<h3[^>]*>(.*?)</h3>',
          r'<p style="color:var\(--muted\)">(.*?)</p>', r'class="dim">([A-Z][^<{]*?)</td>',
          r'<tr(?: class="total")?><td>([A-Z][^<{]*?)</td>', r'<p class="lede">(.*?)</p>',
          r'<div class="eyebrow">(.*?)</div>', r'return \("([a-z][^"]*)", "&mdash;"\)',
          r'f"(read live), \{on\}"', r'"(n/a &mdash; retrieved another way)"')


def _report_words() -> int:
    import re
    from portfusion.report import page
    src = (SRC / "report" / "page.py").read_text(encoding="utf-8")
    words = sum(len(re.sub(r"<[^>]+>|\{[^}]*\}|&\w+;", " ", hit).split())
                for pattern in _PROSE for hit in re.findall(pattern, src, re.S))
    words += len(re.sub(r"<[^>]+>", " ", page.notice("2000-03-31")).split())
    return words + len(Book.OPENED_IN_PERIOD.split())


@holds(COMPLETE, what="a complete quarter before the first report")
def test_the_reports_own_prose_rises_only_with_a_reason():
    """Its figures are the engine's and its headings the registry's; this holds its sentences. A
    sentence added is a decision, so the count goes down, or rises with a reason written
    beside it, as DESK_CHROME_WORDS does."""
    words = _report_words()
    assert words <= REPORT_PROSE_WORDS, (
        f"the report now types {words} words of its own, above the {REPORT_PROSE_WORDS} on file. "
        f"Take a sentence out, or raise this with the reason beside it.")
