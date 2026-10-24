"""THE PAGE — the quarterly report's nine sections, every figure the engine's.

Nothing is computed here. Where the page needs something engine.py does not offer, the fix is an
engine method.
"""
from __future__ import annotations

import datetime as _dt
import html

from portfusion import about, brand
from portfusion.engine import Book
from portfusion.house.headings import heading
from portfusion.house.precision import day, local_price, pct, points
from portfusion.record import rules as D
from portfusion.report.style import CSS

def _money(x):
    return f"{x:,.0f}"


def _rows(items):
    return "\n".join(items)


def _head(tab: str, *cols) -> str:
    """A table head in house/headings.py's words for `tab`. Each column is a field, or a
    (field, attributes) pair; None is a column with no heading."""
    cells = []
    for c in cols:
        field, attrs = (c, "") if not isinstance(c, tuple) else c
        cells.append(f"<th{attrs}>{'' if field is None else html.escape(heading(tab, field))}</th>")
    return f"<thead><tr>{''.join(cells)}</tr></thead>"


#: The first period the book reports on. Q1 and Q2 2026 are computed for the record and as the
#: series' starting point.
def first_reported() -> str:
    """The first quarter end the report is built for: settings.csv `first_report`."""
    return D.SETTINGS["first_report"]


def notice(quarter_end: str) -> str:
    """The note at the head of every report, plus the narrower one where it applies.

    Every page says the positions are the book's own and not a recommendation, whatever the
    quarter. Only Q3 2026 onward is a period the book reports on; an earlier quarter's page
    also says it is computed, not reported.

    Its own function so both branches can be tested without a reportable quarter behind them.
    """
    text = "The book's own positions; not a recommendation."
    if quarter_end < first_reported():
        text += ' Computed for the record, not a reported period.'
    return '<div class="notice">' + text + '</div>'


def summary_figures(quarter_end: str, b: Book | None = None) -> list[dict]:
    """The page's headline figures AS DATA: label, value, basis and unit.

    The values are the engine's, selected and labelled here, never computed. Returned as data so
    tests/test_figures.py can hold this page and the desk to one registry,
    Book.HEADLINE. The page passes its own engine; asked alone, it builds one.
    """
    b = b if b is not None else Book()
    figures = b.headline(quarter_end)
    return [{"label": label, "value": value,
             "basis": b.basis_of(label), "unit": b.HEADLINE[label]["unit"]}
            for label, value in figures.items()]


def _pct(x) -> str:
    """A return, or a dash where there is none — never 0.00%, which would claim one."""
    return "&mdash;" if x != x else pct(x)


def _sign(x) -> str:
    return "pos" if x >= 0 else "neg"


esc = html.escape

#: A note in muted type beneath a table.
_NOTE = 'class="note"'

#: What stands between two sections, and between the header and the first.
_RULE = '\n\n<div class="rule"></div>\n\n'


def render(quarter_end: str) -> str:
    """The page. Every figure comes from the engine; nothing is computed here.

    THE NINE SECTIONS ARE LISTED HERE, IN ORDER, and numbered by their place in the list, so
    moving one renumbers the rest. Each is its own function and takes what it shows; what two
    sections share is looked up once, here.
    """
    b = Book()
    label = _dt.date.fromisoformat(quarter_end).strftime("%d %B %Y")
    q = {"03-31": "Q1", "06-30": "Q2", "09-30": "Q3", "12-31": "Q4"}[quarter_end[5:]]
    year = quarter_end[:4]

    # One call, so an amount and the basis printed beside it cannot come from different rows.
    navs = b.quarter_nav_rows(quarter_end)
    figures = {f["label"]: f["value"] for f in summary_figures(quarter_end, b)}
    nav_total = figures["Net asset value"]
    # THE FROZEN COMPOSITION, so the holdings add to the exposure Section 1 publishes. It was a
    # revaluation of the same day once, and the page had to explain a gap between the two.
    lines = b.quarter_lines(quarter_end)

    qr = b.quarter_returns()
    this_q = qr.set_index("quarter_end").loc[quarter_end]
    # AN ACCOUNT IS NAMED BY ITS CODE, ALWAYS: the report is the document
    # that leaves the book, so it never carries a holder. A row that is not an account, the
    # income table's total, keeps its own word.
    codes = b.account_codes()
    names = dict(zip(codes["account"], codes["label"]))

    sections = [
        ("Portfolio summary",
         _summary(nav_total, figures["Total market exposure"], this_q, figures["Open positions"],
                  len(D.accounts_open(quarter_end)))),
        ("Performance", _performance(b, qr, quarter_end)),
        ("Where the exposure sits", _allocation(b, quarter_end)),
        ("Holdings", _holdings(lines, b.quarter_lines_total(quarter_end),
                               figures["Total market exposure"])),
        ("Contributors and detractors", _movers(b, quarter_end)),
        ("Investment activity", _activity(b, quarter_end, names)),
        # THE QUARTER'S WINDOW for money and income: after the previous quarter end, up to this
        # one, as the return itself bounds them.
        ("Cash movements and income",
         _cash_and_income(b, this_q["opens"], quarter_end, names)),
        ("By account", _by_account(b, navs, this_q, nav_total, quarter_end, names)),
        ("What these figures rest on", _evidence(b, quarter_end, names)),
    ]
    body = _RULE.join(
        f'<section>\n  <div class="snum">{n:02d}</div><h2>{title}</h2>\n{inner}\n</section>'
        for n, (title, inner) in enumerate(sections, 1))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{q} {year} — {html.escape(brand.NAME)}</title>
<style>{CSS}</style></head><body>
<div class="wrap">

<header>
  {brand.lockup()}
  <div class="eyebrow">Quarterly report</div>
  <h1>{q} {year}</h1>
  <p class="lede">As at {label}. All figures GBP.</p>
  {notice(quarter_end)}
</header>{_RULE}{body}

<footer>{_colophon()}</footer>

</div></body></html>"""


def _colophon() -> str:
    """The footer: the brand's ownership line, if any, then `about.stamp()`."""
    whose = brand.ownership(_dt.date.today().year)
    return " &middot; ".join([*([html.escape(whose)] if whose else []),
                              about.stamp(store=D.store_dir())])


def _summary(nav_total, exposure, this_q, positions, accounts) -> str:
    """The headline figures."""
    return f"""  <div class="stats">
    <div><div class="v">&pound;{_money(nav_total)}</div><div class="k">Net asset value</div>
      <div class="sub">Shares at market plus spread-bet equity.</div></div>
    <div><div class="v">&pound;{_money(exposure)}</div><div class="k">Total market exposure</div>
      <div class="sub">Includes spread-bet notional.</div></div>
    <div><div class="v">{_pct(this_q["return"])}</div><div class="k">Return this quarter</div>
      <div class="sub">Modified Dietz, day-weighted.</div></div>
    <div><div class="v">{accounts} / {positions:,.0f}</div><div class="k">Accounts / positions</div>
      <div class="sub">Frozen at the quarter end.</div></div>
  </div>"""


def _performance(b, qr, quarter_end) -> str:
    """Every quarter to this one, and the year to it."""
    def perf_row(r, cls=""):
        return (f'<tr{cls}><td style="white-space:nowrap">{esc(str(r["quarter"]))}</td>'
                f'<td class="n">{_money(r["opening_nav"])}</td>'
                f'<td class="n">{r["capital_deployed"]:+,.0f}</td>'
                f'<td class="n">{r["return_income"]:+,.0f}</td>'
                f'<td class="n">{_money(r["closing_nav"])}</td>'
                f'<td class="n {_sign(r["gain"])}">{r["gain"]:+,.0f}</td>'
                f'<td class="n">{_pct(r["return"])}</td></tr>')
    perf = (_rows(perf_row(r) for r in qr.to_dict("records") if r["quarter_end"] <= quarter_end)
            + perf_row(b.year_to_quarter(quarter_end), ' class="total"'))
    return f"""  <div class="scroll"><table>
    {_head("Performance", "quarter", *((f, ' class="n"') for f in (
        "opening_nav", "capital_deployed", "return_income", "closing_nav", "gain", "return")))}
    <tbody>{perf}</tbody></table></div>
  <p {_NOTE}>Income: share-account dividends. A spread bet&rsquo;s is inside its equity.</p>"""


def _allocation(b, quarter_end) -> str:
    """A bar per slice, by currency, region and sector, from the same valuation. The shares are
    the engine's."""
    def alloc(dim):
        return _rows(
            f'<tr><td>{esc(str(r[dim]))}</td>'
            f'<td><div class="bar">'
            f'<i style="width:{r["share_of_largest"] * 100:.1f}%"></i></div></td>'
            f'<td class="n">{pct(r["share"])}</td></tr>'
            for _, r in b.allocation(by=dim, as_of=quarter_end).iterrows())
    share = ("share", ' class="n"')
    return "\n".join(
        f'  <div class="scroll"><table class="alloc">{_head("Dashboard", dim, None, share)}\n'
        f'    <tbody>{alloc(dim)}</tbody></table></div>'
        for dim in ("currency", "region", "sector"))


def _holdings(lines, total, exposure) -> str:
    """The frozen composition, line by line, with the engine's total row, and both figures where
    that total and Section 1's exposure differ."""
    hold = _rows(
        f'<tr><td>{esc(str(r.ticker))}</td><td>{esc(str(r.company))}</td><td class="dim">{r.held_as}</td>'
        f'<td class="dim">{esc(str(r.sector)) if r.sector == r.sector else ""}</td>'
        f'<td class="dim">{r.currency}</td><td class="n">{pct(r.weight)}</td>'
        f'<td class="n">{_money(r.cost)}</td><td class="n">{_money(r.value)}</td>'
        f'<td class="n {_sign(r.unrealised)}">{r.unrealised:+,.0f}</td></tr>'
        for r in lines.itertuples())
    return f"""  <div class="scroll"><table>
    {_head("Holdings", "ticker", "company", "held_as", "sector", "currency",
           *((f, ' class="n"') for f in ("weight", "cost", "value", "unrealised")))}
    <tbody>{hold}
      <tr class="total"><td>Total</td><td></td><td></td><td></td><td></td><td class="n">{pct(1)}</td>
        <td class="n">{_money(total["cost"])}</td><td class="n">{_money(total["value"])}</td>
        <td class="n">{total["unrealised"]:+,.0f}</td></tr></tbody></table></div>
  <p {_NOTE}>Spread bets at notional.{"" if round(total["gap"]) == 0 else
    f" These lines total &pound;{_money(total['value'])}; Section 1&rsquo;s exposure is &pound;{_money(exposure)}."}</p>"""


def _movers(b, quarter_end) -> str:
    """The largest contributors and detractors, and what every line adds up to."""
    # Both ends must be frozen compositions; the first quarter of the record has no opening one.
    try:
        contrib = b.quarter_contributions(quarter_end)
        attrib = b.quarter_attribution(quarter_end)
    except KeyError:
        return '  <p style="color:var(--muted)">Not available for this quarter.</p>'

    def contrib_rows(frame):
        return _rows(
            f'<tr><td>{esc(str(r.ticker))}</td><td>{esc(str(r.company))}</td><td class="dim">{r.held_as}</td>'
            f'<td class="n">{"" if not r.realised else f"{r.realised:+,.0f}"}</td>'
            f'<td class="n {_sign(r.contribution)}">{r.contribution:+,.0f}</td></tr>'
            for r in frame.itertuples()) or '<tr><td colspan="5" class="dim">None.</td></tr>'

    # FIXED WIDTHS, so the two tables and the sum beneath them read as one column set.
    head = _head("Holdings", ("ticker", ' style="width:12%"'), ("company", ' style="width:34%"'),
                 ("held_as", ' style="width:18%"'), ("realised", ' class="n" style="width:16%"'),
                 ("quarter_gain", ' class="n" style="width:20%"'))
    gains = contrib[contrib["contribution"] > 0].iloc[::-1].head(5)
    losses = contrib[contrib["contribution"] < 0].head(5)
    return f"""  <h3 style="font-size:.95rem;margin:18px 0 0">Largest contributors</h3>
  <div class="scroll"><table>{head}<tbody>{contrib_rows(gains)}</tbody></table></div>
  <h3 style="font-size:.95rem;margin:18px 0 0">Largest detractors</h3>
  <div class="scroll"><table>{head}<tbody>{contrib_rows(losses)}</tbody></table></div>
  <div class="scroll"><table><tbody>
    <tr><td>Every line together</td><td class="n">{attrib["lines"]:+,.0f}</td></tr>
    <tr><td>Position income</td><td class="n">{attrib["position_income"]:+,.0f}</td></tr>
    <tr><td>Not attributed to a line</td><td class="n">{attrib["unattributed"]:+,.0f}</td></tr>
    <tr class="total"><td>The quarter&rsquo;s gain</td><td class="n">{attrib["gain"]:+,.0f}</td></tr>
  </tbody></table></div>
  <p {_NOTE}>{heading("Holdings", "quarter_gain")}:
    change in unrealised gain, plus realised.</p>"""


def _bet(r) -> bool:
    """A spread bet's leg reads in its own terms: the engine's level column says which."""
    return r.level_points == r.level_points


def _size(r) -> str:
    """A trade's size in its own unit, as the desk prints it: a share's count, or a spread bet's
    stake per point."""
    return f"&pound;{r.stake:g}/pt" if _bet(r) else f"{r.qty:,.0f}"


def _activity(b, quarter_end, names) -> str:
    """Every trade in the quarter, in the desk's Trades columns and order, a bet
    in IG's own units with no currency of its own; then the realised gain, which the desk leaves
    to Round Trips and the report has no page for."""
    act = b.activity(start=b.quarter_start(quarter_end), end=quarter_end)
    activity = _rows(
        f'<tr><td>{esc(str(r.ticker))}</td><td>{r.direction}</td>'
        f'<td class="dim">{esc(names[r.account])}</td>'
        f'<td class="dim">{"&mdash;" if _bet(r) else r.currency}</td>'
        f'<td class="n">{_size(r)}</td>'
        f'<td class="n">{points(r.level_points) if _bet(r) else local_price(r.traded_price, r.currency)}</td>'
        f'<td class="n">{_money(r.value)}</td><td class="dim">{day(r.date)}</td>'
        f'<td class="n{"" if r.realised != r.realised else " " + _sign(r.realised)}">'
        f'{"" if r.realised != r.realised else f"{r.realised:+,.0f}"}</td></tr>'
        for r in act.itertuples()) or '<tr><td colspan="9" class="dim">No trades this quarter.</td></tr>'
    return f"""  <div class="scroll"><table>
    {_head("Trades", "ticker", "direction", "account", "currency",
           *((f, ' class="n"') for f in ("qty", "traded_price", "value")), "date",
           ("realised", ' class="n"'))}
    <tbody>{activity}</tbody></table></div>"""


def _cash_and_income(b, start, quarter_end, names) -> str:
    """Capital in and out, then income and costs, both over the quarter's window."""
    moved = _rows(
        f'<tr><td class="dim">{day(r.date)}</td><td>{esc(names[r.account])}</td>'
        f'<td class="n {_sign(r.amount)}">{r.amount:+,.2f}</td></tr>'
        for r in b.capital_movements(start=start, end=quarter_end).itertuples()) \
        or '<tr><td colspan="3" class="dim">No capital moved this quarter.</td></tr>'
    cats = list(D.POSITION_INCOME) + list(D.ACCOUNT_INCOME)
    inc = b.income_summary(start=start, end=quarter_end).to_dict("records")
    income = _rows(
        f'<tr{" class=\"total\"" if i == len(inc) - 1 else ""}>'
        f'<td>{esc(names.get(r["account"], r["account"]))}</td>'
        + "".join(f'<td class="n">{r[c]:,.2f}</td>' for c in cats)
        + f'<td class="n">{r["total"]:,.2f}</td></tr>'
        for i, r in enumerate(inc))
    return f"""  <h3 style="font-size:.95rem;margin:18px 0 0">Capital in and out</h3>
  <div class="scroll"><table>
    {_head("Accounts", "date", "account", ("amount", ' class="n"'))}
    <tbody>{moved}</tbody></table></div>
  <h3 style="font-size:.95rem;margin:18px 0 0">Income and costs</h3>
  <div class="scroll"><table>
    <thead><tr><th>{heading("Accounts", "account")}</th>{"".join(f'<th class="n">{esc(c)}</th>' for c in cats)}<th class="n">{heading("Accounts", "total")}</th></tr></thead>
    <tbody>{income}</tbody></table></div>"""


def _by_account(b, navs, this_q, nav_total, quarter_end, names) -> str:
    """Each account's quarter, and the book's beneath them."""
    per = b.account_quarter_returns()
    per = per[per["quarter_end"] == quarter_end].set_index("account")
    opened = [a for a in per.index if per.loc[a, "opened_in_period"]]
    accounts = _rows(
        f'<tr><td>{esc(names[r.account])}</td>'
        f'<td class="n">{_money(per.loc[r.account, "opening_nav"])}</td>'
        f'<td class="n">{per.loc[r.account, "capital_deployed"]:+,.0f}</td>'
        f'<td class="n">{_money(r.amount)}</td>'
        f'<td class="n">{_pct(per.loc[r.account, "return"])}'
        f'{" &dagger;" if r.account in opened else ""}</td>'
        f'<td class="dim">{esc(r.contribution)}</td></tr>'
        for r in navs.itertuples())
    opened_note = (f'<p {_NOTE}>&dagger; {esc(Book.OPENED_IN_PERIOD)}</p>') if opened else ""
    return f"""  <div class="scroll"><table>
    {_head("Performance", "account", *((f, ' class="n"') for f in (
        "opening_nav", "capital_deployed", "closing_nav", "return")), "contribution")}
    <tbody>{accounts}
      <tr class="total"><td>Total</td><td class="n">{_money(this_q["opening_nav"])}</td>
        <td class="n">{this_q["capital_deployed"]:+,.0f}</td><td class="n">{_money(nav_total)}</td>
        <td class="n">{_pct(this_q["return"])}</td><td></td></tr></tbody></table></div>
  {opened_note}"""


def _evidence(b, quarter_end, names) -> str:
    """What each account's figure rests on, as `Book.quarter_evidence()` decides it."""
    def cells(r):
        if r["as_of"] is None:
            return ("no broker check", "&mdash;")
        on = day(r["as_of"])
        held = {"read live": f"read live, {on}",
                "retrieved another way": "n/a &mdash; retrieved another way",
                None: "&mdash;"}.get(r["held"], r["held"])
        return (esc(f"{r['document']}, {on}"), held)

    evidence = _rows(
        f'<tr><td>{esc(names[r["account"]])}</td><td class="dim">{k}</td>'
        f'<td class="dim">{held}</td></tr>'
        for r in b.quarter_evidence(quarter_end).to_dict("records") for k, held in [cells(r)])
    return f"""  <p {_NOTE}>Share accounts are checked on units, spread bets on equity.</p>
  <div class="scroll"><table>
    {_head("Accounts", "account", "last_check", "document")}
    <tbody>{evidence}</tbody></table></div>"""
