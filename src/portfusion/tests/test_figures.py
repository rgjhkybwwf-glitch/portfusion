"""
ONE REGISTRY, TWO RENDERERS — the cross-renderer guard.

This book renders its headline figures on the desk's Dashboard and in the quarterly report.

A per-cell tie test cannot scale across renderers: it costs N² comparisons and it only ever
covers the cells somebody remembered. So every renderer exposes its headline block AS DATA, and
every one is held against Book.HEADLINE — the registry — not against each other. A third renderer
joins by exposing `figures`.

THE REGISTRY IS THE CONTRACT. A label is in it or it may not be rendered; a value is the
engine's or it is wrong; a basis printed beside a number is the registry's or it is a
mislabel. That is the basis split stated as a mechanism rather than as a sentence in
six documents.
"""
import ast
import html
import re

import pytest

from portfusion.engine import Book
from portfusion.report.page import render, summary_figures

from harness import ROOT, SRC, needs_checkout, needs, desk_script, engine_files
PENNY = 0.01
#: The loaded book's newest frozen quarter end, or None before it has frozen one.
QUARTER = max((str(d)[:10] for d in Book().quarter_nav_total().index), default=None)


# =====================================================================================
# EACH RENDERER'S HEADLINE BLOCK, AS DATA
# =====================================================================================

@pytest.fixture(scope="module")
def engine():
    return Book()


@pytest.fixture(scope="module")
def desk_figures():
    from portfusion.desk import panels
    return {f["label"]: f for f in panels.get("dashboard").data()["figures"]}


@pytest.fixture(scope="module")
def report_figures():
    return {f["label"]: f for f in summary_figures(QUARTER)}


def _labels(page):
    """The label under each figure the report prints (`class="k"`), read from the page itself."""
    return {html.unescape(m) for m in re.findall(r'class="k">([^<]*)<', page)}


@pytest.fixture(scope="module")
def report_labels():
    return _labels(render(QUARTER))


# =====================================================================================
# GUARD 1 · REGISTRY CLOSURE — no renderer may show a label the engine does not know
# =====================================================================================

@needs("buys")
def test_every_rendered_label_is_in_the_registry(desk_figures, report_labels):
    """A label nobody registered may not be shown. `basis_of()` refuses one when a renderer asks
    for its basis; this names every one a renderer shows, whether it asked or not. The report's
    are read from the page it draws, so a label typed there is seen.
    """
    assert _labels('<div class="k">A &amp; B</div>') == {"A & B"}, "a planted label is read"
    rendered = set(desk_figures) | report_labels
    # NO EXEMPTIONS. The guard is absolute.
    unknown = {label for label in rendered if label not in Book.HEADLINE}
    assert not unknown, (
        f"these labels are rendered but not in Book.HEADLINE: {sorted(unknown)}. "
        f"Register the figure — its basis and its unit — before showing it.")


@needs("buys")
def test_both_renderers_list_the_registry_in_its_order(desk_figures, report_figures):
    """ONE ORDER, THE REGISTRY'S. The Dashboard lists HEADLINE, and the report's Section 1 lists
    the figures `headline(date)` gives, in the same order; a quarter's own is the report's."""
    assert list(desk_figures) == [k for k, v in Book.HEADLINE.items() if not v.get("report_only")]
    assert list(report_figures) == [k for k, v in Book.HEADLINE.items() if v["point_in_time"]]


@needs("buys")
def test_the_registry_is_not_a_graveyard(desk_figures, report_labels):
    """The other direction. A registered label nothing renders is a figure that was retired
    without the registry being told, and the next renderer will resurrect it by accident."""
    rendered = set(desk_figures) | report_labels
    assert not (set(Book.HEADLINE) - rendered), \
        f"registered but rendered nowhere: {sorted(set(Book.HEADLINE) - rendered)}"


# =====================================================================================
# GUARD 2 · VALUE AGREEMENT — every renderer's number is the engine's number
# =====================================================================================

@needs("buys")
def test_the_desk_renders_the_engines_figures(engine, desk_figures):
    live = engine.headline()
    for label, fig in desk_figures.items():
        if label not in live:
            continue
        tol = 1e-6 if Book.HEADLINE[label]["unit"] == "pct" else PENNY
        assert abs(live[label] - fig["value"]) < tol, (
            f"desk {label!r}: engine {live[label]:,.6f} vs desk {fig['value']:,.6f}")


@needs("buys")
def test_the_report_renders_the_engines_figures(engine, report_figures):
    """THE DATED VIEW IS THE STORE'S: a quarter's inputs are FROZEN, and a reconstruction from
    the ledger is not a frozen input.
    """
    at_quarter = engine.headline(QUARTER)
    for label, fig in report_figures.items():
        assert label in at_quarter, f"report shows {label!r}, which headline({QUARTER}) does not"
        # A BLANK IS A BLANK: the record's first quarter end has no return, on either side.
        assert fig["value"] == pytest.approx(at_quarter[label], abs=PENNY, nan_ok=True), (
            f"report {label!r}: engine {at_quarter[label]:,.2f} vs report {fig['value']:,.2f}")


@needs("buys")
def test_the_report_quotes_the_quarters_own_totals(engine, report_figures):
    """The report's exposure and net asset value are the quarter end's, not today's."""
    assert report_figures["Total market exposure"]["value"] == \
        pytest.approx(engine.quarter_exposure_total()[QUARTER], abs=PENNY)
    assert report_figures["Net asset value"]["value"] == \
        pytest.approx(engine.quarter_nav_total()[QUARTER], abs=PENNY)


@needs("buys")
def test_a_dated_page_cannot_quote_a_year_to_date_figure(engine):
    """"YTD return (MWR)" and "YTD income" have no value AT A DATE — they are year-to-date by
    construction. headline(date) does not return them, so a Q2 page cannot show one by
    reaching for a label that happens to exist."""
    at_quarter = engine.headline(QUARTER)
    for label, spec in Book.HEADLINE.items():
        assert (label in at_quarter) == spec["point_in_time"], (
            f"{label!r} is point_in_time={spec['point_in_time']} but "
            f"{'is' if label in at_quarter else 'is not'} in headline({QUARTER})")


@needs("buys")
def test_the_parts_add_up_to_the_whole_at_a_quarter_end(engine):
    """"— of which" has to mean it. Both components and the total come from ONE call to
    quarter_nav_rows(), split by is_spread_bet(), so they cannot be sourced differently."""
    f = engine.headline(QUARTER)
    assert f["— of which securities owned"] + f["— of which spread-bet notional"] == \
        pytest.approx(f["Total market exposure"], abs=PENNY)
    assert f["Total market exposure"] - f["Net asset value"] == \
        pytest.approx(f["Exposure above net asset value"], abs=PENNY)


# =====================================================================================
# GUARD 3 · LABEL / BASIS INTEGRITY — the word beside a number is the registry's
# =====================================================================================

def test_the_desk_states_the_registrys_basis(desk_figures):
    for label, fig in desk_figures.items():
        assert fig["basis"] == Book.basis_of(label), \
            f"desk {label!r} is labelled {fig['basis']!r}, the registry says {Book.basis_of(label)!r}"
        assert fig["notional_basis"] == (fig["basis"] in Book.NOTIONAL_BASES)


def test_a_basis_is_the_registrys_or_nothing():
    """NO SECOND OPINION ON A BASIS. A label nobody registered is refused, and every notional
    basis is one a figure carries."""
    with pytest.raises(KeyError, match="not in Book.HEADLINE"):
        Book.basis_of("A figure nobody registered")
    assert Book.NOTIONAL_BASES <= {spec["basis"] for spec in Book.HEADLINE.values()}


@needs("buys")
def test_the_report_states_the_registrys_basis(report_figures):
    for label, fig in report_figures.items():
        assert fig["basis"] == Book.basis_of(label)
        assert fig["unit"] == Book.HEADLINE[label]["unit"]


def test_a_net_asset_value_column_shows_only_a_nav_basis(engine):
    """Where a renderer shows a value and a basis in the same row, the basis must be one the
    column's heading permits.
    """
    for row in engine.quarter_nav_rows(QUARTER, "nav").itertuples():
        assert row.contribution in engine.NAV_BASES, \
            f"{row.account}: basis {row.contribution!r} is not a NAV basis"
    for row in engine.quarter_nav_rows(QUARTER, "exposure").itertuples():
        assert row.contribution in engine.EXPOSURE_BASES, \
            f"{row.account}: basis {row.contribution!r} is not an exposure basis"


# =====================================================================================
# GUARD 4 · NO ARITHMETIC IN A RENDERER
# =====================================================================================

#: Aggregations that mean a figure is being DERIVED rather than shown.
AGGREGATIONS = {"sum", "mean", "groupby", "pivot_table", "cumsum", "prod", "agg", "median"}

#: Lines a person had to write on purpose, each still doing arithmetic, each allowed by name.
#: Adding to this list is the decision; the point is that it cannot happen silently. Empty: the
#: report's Holdings total is the engine's (`Book.quarter_lines_total()`).
ALLOWED: set[tuple[str, str]] = set()


def _renderer_files():
    for path in sorted((SRC / "desk" / "panels").glob("*.py")):
        yield f"desk/panels/{path.name}", path
    for path in sorted((SRC / "report").glob("*.py")):
        yield f"report/{path.name}", path


def test_no_renderer_derives_a_figure_it_was_not_allowed_to():
    """A renderer's job is to show what the engine decided."""
    found = set()
    for name, path in _renderer_files():
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                called = getattr(node.func, "attr", None)
                if called in AGGREGATIONS:
                    found.add((name, called))
    assert found <= ALLOWED, (
        f"a renderer is deriving figures it was not allowed to: {sorted(found - ALLOWED)}. "
        f"Ask the engine, or add the line to ALLOWED with a reason beside it.")


def test_no_renderer_reaches_past_the_engines_methods_into_its_store():
    """`b.store[...]` is the engine's own loaded tables. A renderer reading them is choosing
    its own population: a page that sorts a movements table itself while
    Book.capital_movements() gives something else is two answers to one question."""
    offenders = []
    for name, path in _renderer_files():
        src = path.read_text()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) \
                    and node.value.attr == "store":
                offenders.append(f"{name}:{node.lineno}")
    assert not offenders, (
        f"these renderers read Book.store directly: {offenders}. Add an engine accessor.")


# =====================================================================================
# ONE HEADING PER COLUMN — house/headings.py, read by every renderer
# =====================================================================================
#
# Each renderer is held to the registry here, the way the headline block is above, rather than
# one to the other.

#: Retired headings: none may come back as a column's heading on any renderer. Bare "Gain" is not
#: among them: on Performance it is the quarter's gain, which is neither unrealised nor realised.
RETIRED_HEADINGS = {"GBP", "GBP proceeds", "GBP value", "GBP cost", "Gain %", "Entry",
                    "Exit", "Ref", "Qty", "Period", "Unrealised", "Realised", "Company (issuer)",
                    "Unrealised gain (£)", "Realised gain (£)",
                    # "(local)": the Ccy column names a local price's currency.
                    "Entry price (local)", "Traded price (local)", "Price (local)"}

#: Bold words in glossary §5's heading tables that name something other than a column, each with
#: why. The sterling suffix row states a rule, so it carries code rather than a heading.
GLOSSARY_NOT_HEADINGS: dict[str, str] = {
    # A FIGURE'S WORD, not a column's: Book.HEADLINE's label on the Dashboard, and no table is
    # headed with it.
    "YTD income": "the Dashboard's figure, Book.HEADLINE's word",
    "Spread-bet notional": "the Dashboard's figure, Holdings' strip and What Changed's block",
}


@needs_checkout
def test_the_glossarys_headings_are_the_registrys():
    """GLOSSARY §5 AND house/headings.py SAY THE SAME WORDS, BOTH WAYS. A word renamed in one and
    not the other fails, and so does a heading added without a word agreed in §5.
    """
    import re
    from portfusion.house.headings import BY_TAB, COMMON
    shown = set(COMMON.values()).union(*(m.values() for m in BY_TAB.values()))
    text = (ROOT / "docs" / "glossary.md").read_text()
    section = text[text.index("## 5 ·"):text.index("## 5b ·")]
    agreed = {word for line in section.splitlines() if line.startswith("| ")
              for bold in re.findall(r"\*\*(.+?)\*\*", line.split(" | ")[1] if " | " in line else "")
              if "`" not in bold for word in bold.split(" · ")}
    assert len(agreed) > 20, f"read {len(agreed)} words from §5 — has its table moved?"
    missing = sorted(agreed - shown - set(GLOSSARY_NOT_HEADINGS))
    assert not missing, (
        f"glossary §5 agrees {missing}, which no renderer heads a column with. Rename it in §5 "
        f"or in house/headings.py, so the two say one word.")
    unagreed = sorted(shown - agreed)
    assert not unagreed, f"headed on a page but agreed nowhere in glossary §5: {unagreed}"


def test_every_store_column_is_headed_under_its_own_name():
    """ONE NAME FROM THE STORE TO THE PAGE: a column a reader can meet is headed under the
    name the store gives it, so the store and the desk cannot call one thing two names."""
    from portfusion.house.headings import STORE_ONLY, registered
    from portfusion.record import schema
    pairs = {(n, f.name) for n, t in schema.TABLES.items() for f in t.fields}
    unheaded = sorted(f"{n}.{c}" for n, c in pairs if c not in registered()
                      and c not in STORE_ONLY and f"{n}.{c}" not in STORE_ONLY)
    assert not unheaded, f"store columns with no heading under their own name: {unheaded}"
    gone = set(STORE_ONLY) - {c for _, c in pairs} - {f"{n}.{c}" for n, c in pairs}
    assert not gone, f"store-only, but no longer in the store: {sorted(gone)}"


def test_one_heading_names_one_field():
    """ONE IDEA, ONE NAME: two fields under one heading are one idea under two names, or two
    ideas under one word."""
    from collections import defaultdict
    from portfusion.house.headings import BY_TAB, COMMON
    fields = defaultdict(set)
    for words in (COMMON, *BY_TAB.values()):
        for field, word in words.items():
            fields[word].add(field)
    shared = {w: sorted(f) for w, f in fields.items() if len(f) > 1}
    assert not shared, f"one heading over several fields: {shared}"


def test_every_desk_column_has_a_heading_for_its_tab():
    """Every field a panel shows is named for its tab, and app.js draws a head from nothing else:
    no map of its own, and no typed head."""
    import re
    from portfusion.desk import panels
    unnamed = []
    for mod in panels.all_panels():
        try:
            panels.heads(mod)
        except KeyError as e:
            unnamed.append(f"{mod.NAME}: {e}")
    assert not unnamed, f"name these in house/headings.py: {unnamed}"
    js = desk_script()
    assert not re.search(r"const HEADS\s*=\s*\{", js), "app.js has its own heading map again"
    literal = set(re.findall(r"<th[^>]*>([^<$]+)</th>", js))
    assert not literal, f"app.js types {sorted(literal)} as a table head; draw it with head()"
    # A FIELD head() IS ASKED FOR BY NAME IS REGISTERED: an unregistered one prints its own name.
    from portfusion.house.headings import registered
    asked = set(re.findall(r'\b(?:head|box|pick)\("([a-z_]+)"', js))
    assert not asked - registered(), f"app.js heads {sorted(asked - registered())}, named nowhere"


def test_app_js_draws_a_table_from_the_panels_own_columns():
    """A COLUMN LIST TYPED IN app.js DRIFTS FROM THE PANEL'S. Every table() takes its columns
    from the payload."""
    import re
    js = desk_script()
    typed = re.findall(r"\btable\([^,()]+,\s*\[[^\]]*\]", js)
    assert not typed, f"app.js types a table's columns: {typed}; send the panel's *COLUMNS"


@needs("buys")
def test_the_desks_allocation_is_headed_as_the_reports():
    """WHERE THE EXPOSURE SITS IS DRAWN BY BOTH RENDERERS — the report's section, and Holdings
    under its table — so the axes, their order and their words are one. The desk's tables are
    compared with the report's own head by head, in order."""
    import html
    import re
    from portfusion.desk.panels import holdings
    tables = re.findall(r'<table class="alloc">(.*?)</table>', render(QUARTER), re.S)
    report = [[html.unescape(h) for h in re.findall(r"<th[^>]*>([^<]*)</th>", t)] for t in tables]
    d = holdings.query()
    desk = [[d["allocation_heads"][axis], "", d["allocation_heads"]["share"]] for axis in d["allocation"]]
    assert report and desk == report, f"the desk heads its allocation {desk}; the report {report}"


def test_every_figure_is_printed_to_the_houses_places(repo_root):
    """ONE PRECISION FOR EVERY FIGURE THE PROJECT PRINTS: house/precision.py's. A Python renderer
    and the engine's own words print a percentage with precision.pct(), sterling with money() and
    a date with day() or day_month(); core.js takes the places each panel answer carries and
    types none of its own. A CSS width is not a printed figure; a door's refusal and a reference
    read off a document are not renderers."""
    import re
    from portfusion.desk import app as desk_app
    from portfusion.house import precision
    renderers = [*(SRC / "desk" / "panels").glob("*.py"), *(SRC / "report").glob("*.py"),
                 SRC / "record" / "__main__.py", *engine_files()]
    files = [*(SRC / "desk").rglob("*.py"), *(SRC / "report").glob("*.py"),
             SRC / "record" / "__main__.py", *engine_files()]
    def typed(paths, pattern):
        return [f"{p.relative_to(repo_root)}:{n}" for p in paths
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                if re.search(pattern, line) and "width:" not in line]
    own = typed(files, r"\.\d+%\}|\.\d+f\}%")
    assert not own, f"these print a percentage at their own places: {own}; use precision.pct()"
    own = typed(renderers, r":\+?,?\.[1-9]f\}|:\+,\.0f\}")
    assert not own, f"these print sterling at their own places: {own}; use precision.money()"
    own = typed(renderers, r"%-d %b")
    assert not own, f"these print a date in their own form: {own}; use precision.day()"
    js = desk_script()
    pct_js = re.search(r"const pct = [\s\S]*?;\n", js).group(0)
    assert not re.search(r"FractionDigits:\s*\d", pct_js), "core.js types a percentage's places"
    assert "toLocaleString(\"en-GB\", {" not in js, "core.js rounds a figure outside fixed()"
    sent = desk_app.panel("holdings")["precision"]
    assert (sent["pct_dp"], sent["money_dp"], sent["rate_dp"]) == \
        (precision.PCT_DP, precision.MONEY_DP, precision.RATE_DP)


@needs("buys")
def test_every_report_heading_is_the_registrys():
    """The report's heads are the registry's words, or an income category, which is data."""
    import re
    from portfusion.record import rules as D
    from portfusion.house.headings import BY_TAB, COMMON
    words = set(COMMON.values()).union(*(m.values() for m in BY_TAB.values()))
    allowed = words | set(D.POSITION_INCOME) | set(D.ACCOUNT_INCOME) | {""}
    heads = set(re.findall(r"<th[^>]*>([^<]*)</th>", render(QUARTER)))
    assert heads <= allowed, f"the report types {sorted(heads - allowed)}; use _head()"


def test_no_renderer_heads_a_column_with_a_retired_word():
    """The registry holds none of them, and every renderer draws its heads from the registry."""
    from portfusion.house.headings import BY_TAB, COMMON
    words = set(COMMON.values()).union(*(m.values() for m in BY_TAB.values()))
    assert not words & RETIRED_HEADINGS, sorted(words & RETIRED_HEADINGS)


def test_a_table_with_a_local_price_marks_its_sterling():
    """A LOCAL PRICE IS IN ITS LINE'S OWN CURRENCY, which the Ccy column beside it names:
    house/precision.py's LOCAL_PRICE_FIELDS say which fields are one. On a table that shows one,
    every sterling column (house/precision.py's MONEY_FIELDS) is headed "… (GBP)" —
    glossary §5's suffix rule — and no local price is drawn as money."""
    from portfusion.desk import panels
    from portfusion.house.headings import headings
    from portfusion.house.precision import LOCAL_PRICE_FIELDS, MONEY_FIELDS
    money = set(MONEY_FIELDS)
    tables, unmarked, as_money = 0, [], []
    for mod in panels.all_panels():
        for const in [n for n in dir(mod) if n.endswith("COLUMNS")]:
            cols = getattr(mod, const)
            if not set(LOCAL_PRICE_FIELDS) & set(cols):
                continue
            tables += 1
            unmarked += [f"{mod.NAME}.{const} {f}: {h!r}" for f, h in headings(mod.TITLE, cols).items()
                         if f in money and "(GBP)" not in h]
            as_money += [f"{mod.NAME}.{f}" for f in cols if f in LOCAL_PRICE_FIELDS and f in money]
    assert tables, "no desk table shows a local price — has LOCAL_PRICE_FIELDS lost them?"
    assert not unmarked, f"sterling beside a local price without (GBP): {unmarked}"
    assert not as_money, f"a local price is drawn as sterling: {sorted(as_money)}"


def test_the_valuation_date_is_the_engines(desk_figures):
    """WHERE THE BOOK STANDS, AND WHEN. Every live figure rests on the current marks, and one answer
    says when those were taken — Book.valued_at(), the newest mark — so no page can hold its own
    opinion of what "now" means. ISO, as the store and every date column."""
    from portfusion.desk import panels
    assert panels.get("dashboard").data()["valued_at"] == Book().valued_at()


@needs("buys")
def test_net_asset_value_leads_wherever_the_figures_are_listed(desk_figures):
    """NAV FIRST, then exposure and its parts: the book's own capital, and what the return is
    measured on. The registry's order is the order every list reads in — the Dashboard,
    `portfusion record`, the glossary's index — so it is held there."""
    nav = "Net asset value"
    assert next(iter(Book.HEADLINE)) == nav
    assert next(iter(Book().headline())) == nav and next(iter(Book().headline(QUARTER))) == nav
    assert next(iter(desk_figures)) == nav and desk_figures[nav].get("lead")
    page = render(QUARTER)
    assert page.index('class="k">Net asset value') < page.index('class="k">Total market exposure')


@needs("buys")
def test_the_open_quarter_reaches_the_desk():
    """A row one renderer shows and another lacks is the many-renderers problem.
    The report is deliberately NOT in this: a quarterly report is a document about a closed
    quarter and a frozen quarter's inputs are fixed, so an open row valued at today's marks would
    change every time the page was generated."""
    from portfusion.desk import panels
    from portfusion.record import rules as D
    b = Book()
    engine = [r["quarter"] for r in b.quarter_returns(include_open=True).to_dict("records")]
    desk = [r["quarter"] for r in panels.get("performance").data()["firm"]]
    assert desk == engine, "the desk's firm block is not the engine's open-quarter series"
    # THERE IS AN OPEN QUARTER ONLY ONCE A LIVE MARK IS DATED AFTER THE LAST FROZEN END — between
    # a freeze and the next refresh the book holds nothing inside the new quarter to show.
    open_rows = [q for q in engine if q.endswith("to date")]
    expected = b.valued_at() > max(D.QSNAP_FROZEN)
    assert bool(open_rows) == expected, (
        f"valued at {b.valued_at()}, last frozen {max(D.QSNAP_FROZEN)}: open rows {open_rows}")
    assert not open_rows or open_rows == engine[-1:], "the open quarter must be the last row"

    closed = [r["quarter"] for r in b.quarter_returns().to_dict("records")]
    assert not any(q.endswith("to date") for q in closed), (
        "the default must stay closed-quarters-only — the report depends on it")


# =====================================================================================
# ONE PALETTE — house/palette.py, read by every renderer
# =====================================================================================

def test_no_renderer_types_a_colour(project_files):
    """EVERY COLOUR IS house/palette.py's, in either scheme. A colour written in a renderer is a
    copy waiting to drift, so none may be: hex with a `#`, or bare six digits."""
    import re
    colour = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b|[\"'][0-9A-Fa-f]{6}[\"']")
    # THE RENDERERS BY THEIR PLACE IN THE PACKAGE, never by a path from the checkout's root.
    renderers = [p for p in project_files(".py", ".css", ".js")
                 if p.is_relative_to(SRC) and p.relative_to(SRC).parts[0] in ("desk", "report")]
    assert len(renderers) > 20, f"the guard reads {len(renderers)} renderer file(s)"
    found = [f"{p.relative_to(SRC)}: {m}" for p in renderers
             for m in colour.findall(p.read_text(encoding="utf-8"))]
    assert not found, f"a renderer types a colour; name it in house/palette.py: {found}"


# =====================================================================================
# GUARD 5 · THE HEADINGS REGISTRY IS NOT A GRAVEYARD EITHER
# =====================================================================================

#: A heading registered for a field a page sends and nothing yet draws, kept by name while its
#: home is decided. Adding here is the decision; the point is that it cannot happen silently.
HEADINGS_AWAITING_A_HOME: set[str] = set()


def _headings_used(monkeypatch) -> set[tuple[str, str]]:
    """Every (tab, field) a renderer heads: the desk's declared columns, and every heading the
    panels and the report ask for while they render — Holdings' allocation heads, the report's
    tables — caught at `heading()` itself, so a column headed outside a `*COLUMNS` constant
    still counts."""
    import portfusion.house.headings as H
    import portfusion.report.page as RP
    from portfusion.desk import panels
    used, real = set(), H.heading

    def record(tab, field):
        used.add((tab, field))
        return real(tab, field)
    monkeypatch.setattr(H, "heading", record)
    monkeypatch.setattr(RP, "heading", record)
    for mod in panels.all_panels():
        used.update((mod.TITLE, f) for f in panels.heads(mod))
        mod.data()
    render(QUARTER)
    return used


def test_every_desk_page_is_a_tab_the_headings_know():
    """EVERY PAGE IS A TAB THE HEADINGS NAME, and a tab that is not one is refused."""
    from portfusion.desk import panels
    from portfusion.house import headings as H
    assert set(H.BY_TAB) == {m.TITLE for m in panels.all_panels()}, (
        "house/headings.py's BY_TAB and the desk's page titles differ")
    with pytest.raises(KeyError, match="not a desk page"):
        H.heading("Holding", "ticker")


@needs("buys")
def test_the_headings_registry_is_not_a_graveyard(monkeypatch):
    """A heading nothing heads is a column that was retired without the registry being told, and
    the next renderer will resurrect it by accident, as test_the_registry_is_not_a_graveyard says
    of a figure."""
    from portfusion.house import headings as H
    used = _headings_used(monkeypatch)
    fields = {f for _, f in used}
    unused = set(H.COMMON) - fields - HEADINGS_AWAITING_A_HOME
    assert not unused, f"registered in COMMON and headed nowhere: {sorted(unused)}"
    for tab, words in H.BY_TAB.items():
        gone = set(words) - {f for t, f in used if t == tab}
        assert not gone, f"registered for {tab!r} and headed nowhere on it: {sorted(gone)}"
    assert HEADINGS_AWAITING_A_HOME <= set(H.COMMON), \
        "a field waiting for a home has left the registry: take it off the list"

