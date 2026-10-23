"""THE DESK AS A PROCESS — restarting it, and knowing whether it runs the code on disk."""
from __future__ import annotations

import pathlib
import pytest
from portfusion import engine as _engine
from portfusion.desk import panels, engine
from desk_support import _static
from harness import SRC, needs


# =====================================================================================
# THE RESTART BUTTON
# =====================================================================================

def test_the_restart_is_declared_and_writes_nothing():
    """A running desk serves what it IMPORTED at startup, and a browser refresh cannot fix
    that. The Dock launcher replaces a stale server but only one IT started — a desk run from a
    terminal, which is how it is run while being worked on, never meets that check.

    `writes=None` is literal here: it replaces a PROCESS and touches no file.
    """
    from portfusion.desk import actions
    a = actions.get("restart-desk")
    assert a.writes is None
    assert a.reaches is None, "restarting reaches nothing; it does not leave this machine"
    assert a.gate, "a button that kills a server names the human step that presses it"


def test_the_restart_module_touches_no_file(repo_root):
    """It is not another writer to the record, and it is not a writer at all. Checked on the
    syntax tree rather than by reading the docstring — prose is not behaviour, which is the
    lesson bench.py's own guard records."""
    import ast
    from harness import write_call
    tree = ast.parse((SRC / "desk" / "restart.py").read_text())
    # THE SUITE'S ONE LIST OF WHAT WRITES (`harness.write_call`): this one kept its own, and missed
    # a replace and an `open(…, "w")`.
    found = {write_call(n) for n in ast.walk(tree)} - {None}
    assert not found, f"desk/restart.py writes something: {sorted(found)}"


def test_the_restart_will_not_default_to_a_port_it_was_not_given():
    """THE BUG THIS EXISTS FOR, caught before it shipped. The action first read
    `port=8765` as a default — so a desk started on any other port would have restarted the one
    on 8765 instead: a different server, quite possibly someone else's work.

    The PAGE knows which server it is talking to and says so; the action requires it.
    """
    import inspect
    from portfusion.desk import actions
    sig = inspect.signature(actions.get("restart-desk").run)
    port = sig.parameters.get("port")
    assert port is not None, "the action must take a port"
    assert port.default is inspect.Parameter.empty, (
        "the restart must not default its port — a default restarts whichever desk is on it")


def _restart_spawns(monkeypatch, *, env: str | None, launchd_pid: int | None) -> list[str]:
    """What restart() would spawn, given XPC_SERVICE_NAME and the pid launchd reports for it.
    Nothing is spawned and nothing exits: Popen and the exit timer are both stood in for."""
    import subprocess
    import types
    from portfusion.desk import restart
    if env is None:
        monkeypatch.delenv("XPC_SERVICE_NAME", raising=False)
    else:
        monkeypatch.setenv("XPC_SERVICE_NAME", env)
    printed = f"\tstate = running\n\tpid = {launchd_pid}\n" if launchd_pid else "\tstate = not running\n"
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, printed, ""))
    spawned = []

    def popen(argv, **kw):
        assert kw.get("start_new_session"), "the child must outlive this process's group"
        spawned.append(argv)
        return types.SimpleNamespace(pid=0)
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(restart.threading, "Timer",
                        lambda *a, **k: types.SimpleNamespace(start=lambda: None))
    assert restart.restart(8769)["ok"]
    assert len(spawned) == 1
    return spawned[0]


def test_under_its_agent_the_restart_is_launchds(monkeypatch):
    """THE ORPHAN, 19 Oct 2026. A replacement the desk spawned itself had ppid 1: the agent no
    longer owned the desk, a kickstart after a merge could not stop it, and the agent's own copy
    found the ports taken while the orphan served the old code. Under the agent, launchd does
    the restart, so its plist's arguments and PORTFUSION_BOOK come back with it."""
    import os
    argv = _restart_spawns(monkeypatch, env="some.agent", launchd_pid=os.getpid())
    assert argv[-1] == f"gui/{os.getuid()}/some.agent"
    assert "kickstart" in argv[2] and "portfusion.desk" not in argv[2]


@pytest.mark.parametrize("env", [None, "0", "some.app"])
def test_a_desk_launchd_does_not_name_relaunches_itself(monkeypatch, env):
    """XPC_SERVICE_NAME is inherited — a desk started from a terminal or an app carries that
    app's label — so it is believed only when launchd reports THIS pid for it. Anything else
    restarts as a desk started by hand, never by kickstarting somebody else's job."""
    import os
    argv = _restart_spawns(monkeypatch, env=env, launchd_pid=os.getpid() + 1)
    assert "portfusion.desk" in argv[2] and "kickstart" not in argv[2]


def test_the_page_sends_the_port_it_is_connected_to(repo_root):
    """The other half: a required argument nothing supplies is a button that always fails."""
    js = (SRC / "desk" / "static" / "app.js").read_text()
    assert "restart-desk" in js
    assert "location.port" in js, "app.js does not tell the action which server to restart"


def test_the_restart_waits_for_the_new_process_rather_than_guessing(repo_root):
    """Reloading on a timer lands on either the dying server or a refused connection, and both
    look like a crash. /api/health carries `started`, so the page polls until it MOVES."""
    js = (SRC / "desk" / "static" / "app.js").read_text()
    block = js[js.index("async function wireRestart()"):js.index("function drawFreshness")]
    assert "/api/health" in block
    assert "!== was" in block, "it must compare `started` against what it saw before"
    assert "location.reload" in block


def test_every_font_size_comes_from_the_scale(repo_root):
    """THE SCALE EXISTED IN NAME ONLY (the owner: "scan the desk font for sizing and uniformity").

    app.css declared three steps and then set SEVENTEEN font sizes as hard-coded rem literals,
    so changing the small text meant finding eight separate `0.8125rem` and hoping. And
    `--step-2` had been declared since the file began and used nowhere — a size the design does
    not have, pretending to be one it does.

    Five steps then, one per job, and nothing may state a size outside :root. That is the same
    rule this file already opens with for colour and spacing — "nothing outside it sets a
    colour, a size or a spacing" — applied to the file itself. The display steps added two (the owner,
    6 Oct 2026): a page's title in the design system's display size, and the figures on the Dashboard's band.
    """
    import re
    css = (SRC / "desk" / "static" / "app.css").read_text()

    literals = re.findall(r"font-size:\s*([0-9.]+(?:rem|px|em))", css)
    assert not literals, (
        f"these font sizes are literals rather than steps: {sorted(set(literals))}. "
        f"Add a step to :root, or use the one that already means this.")

    scale = {"--text-lead", "--text-body", "--text-note", "--text-label", "--text-micro",
             "--text-display", "--text-numeral"}
    used = set(re.findall(r"font-size:\s*var\((--text-[a-z]+)\)", css))
    assert used <= scale, f"unknown step(s): {sorted(used - scale)}"
    declared = set(re.findall(r"(--text-[a-z]+):", css))
    assert declared == scale, f"declared {sorted(declared)}, expected {sorted(scale)}"
    assert declared == used, (
        f"declared but never used: {sorted(declared - used)} — a step nothing renders is the "
        f"defect --step-2 was")


def test_nothing_in_a_data_row_is_bold(repo_root):
    """Bold is for a headline figure and an item's label, never a cell (the owner, 30 Sep 2026:
    Price Refresh and Recent Trades had bold tickers and dates that no other table had). Trades
    is a table since 12 Oct 2026, so the cell check holds it with the rest."""
    import re
    js = (SRC / "desk" / "static" / "app.js").read_text()
    assert not re.findall(r"<td[^>]*>\s*<strong", js), "a table cell is bold"


def test_every_detail_is_in_the_one_order(repo_root):
    """The owner, 12 Oct 2026: "the toggle is one across the book and is detail, inside the fold are
    the sub headings and they are always listed in the same order."

    app.js's DETAIL is the order; a panel names which parts its rows' detail draws, in
    DETAIL_COLUMNS. A part DETAIL does not know would never be drawn, and a panel listing its
    parts in another order would read as though the order were its own."""
    import re
    from portfusion.desk import panels
    js = (SRC / "desk" / "static" / "app.js").read_text()
    order = re.findall(r'"([a-z_]+)"', re.search(r"const DETAIL = \[(.*?)\];", js, re.S).group(1))
    assert len(order) == len(set(order)) >= 8, f"read DETAIL as {order} — has it moved?"
    named = {m.NAME: m.DETAIL_COLUMNS for m in panels.all_panels() if hasattr(m, "DETAIL_COLUMNS")}
    assert {"holdings", "round-trips", "trades"} <= set(named), named
    for name, parts in named.items():
        assert set(parts) <= set(order), f"{name}'s detail names {set(parts) - set(order)}, which DETAIL never draws"
        assert list(parts) == [c for c in order if c in parts], f"{name}'s detail is not in DETAIL's order"
    assert js.count('class="link detail-toggle"') == 1 and "why-toggle" not in js, (
        "a row opens by a second kind of link")


def test_every_filter_row_has_the_same_shape(repo_root):
    """The owner: "the same form, order and layout across holdings, round trips and recent
    trades — I like the grey filter boxes."

    They had three shapes. Trades used labelled `.f` boxes in a grid; Holdings and Round
    Trips used inline controls in a paragraph with the label to the LEFT of the select, so the
    same Account dropdown was a different object on each tab.

    ONE ORDER, applying only the fields a panel has (S8, 14 Oct 2026: "arrange them for the best
    synergy across the desk pages"): account · company · ticker · dates, then the page's own
    control. Account is the first box on every page that has one, so a box two pages share sits
    in one place.
    No filter reads "all" on every page; a date is bounded to what is on file; and the grey boxes
    are only ever a filter row, never a form.
    """
    js = (SRC / "desk" / "static" / "app.js").read_text()
    assert "const filterField" in js and "const filters" in js
    assert 'class="controls"' not in js, (
        "a panel is still using the retired inline filter row")

    order = ["account", "company", "ticker", "from", "to", "direction", "group by", "view"]
    # A row is drawn by `filters([...])`, or handed to the page template as
    # `filters: { fields: [...] }`, which calls the same helper.
    blocks = [_upto(js, m.end(), "]")
              for m in re.finditer(r"filters(?:\(\[|: \{[^\[]*fields: \[)", js)]
    assert len(blocks) == 4, f"expected four filter rows, found {len(blocks)}"
    for block in blocks:
        got = re.findall(r'filterField\("([a-z ]+)"', block) + (
            ["view"] if "viewField(d)" in block else [])
        assert got, f"a filters([...]) block declares no fields: {block[:80]}"
        # A COMPANY LIFE SPANS ACCOUNTS, so Round Trips' life view alone offers none.
        assert got[0] == "account" or ("view" in got and "account" not in got), \
            f"account is not the first box: {got}"
        if "ticker" in got:
            assert "company" in got, f"a row offers a ticker but no company to choose it by: {got}"
        ranks = [order.index(g.replace("closed ", "")) for g in got]
        assert ranks == sorted(ranks), f"filters are out of order: {got}"
        assert len(ranks) == len(set(ranks)), f"a field appears twice: {got}"
        for date in re.findall(r'<input[^>]*type="date"[^>]*>', block, re.S):
            assert re.search(r'\smin="', date) and re.search(r'\smax="', date), \
                f"a date is not bounded to what is on file: {date}"
    assert '<option value="">any</option>' not in js, "a filter reads \"any\" where the others read \"all\""
    assert js.count('class="grid filters"') == 1, "the filter row's boxes are drawn outside filters()"
    from portfusion.desk.panels import holdings
    assert set(holdings.GROUPING_WORDS) == set(holdings.GROUPINGS) and "d.grouping_words[g]" in js
    assert holdings.GROUPING_WORDS["issuer"] == "company", "the group by speaks the engine's word"
    assert "d.company_tickers[co]" in js and 'co.addEventListener("change", () => { if (tk) tk.value = ""' in js, \
        "a Ticker box does not follow the company chosen beside it"


import re  # noqa: E402 — used by the tests around it


def _upto(js, i, closer):
    """The text from `i` to the `closer` that ends the bracket opened just before it. A bracket
    inside a string or a template literal does not count; a `${...}` inside a template is code."""
    closers = {"(": ")", "[": "]", "{": "}"}
    stack, start = [closer], i
    while stack:
        c, top = js[i], stack[-1]
        if top in "'\"`" and c == "\\":
            i += 2
            continue
        if top in "'\"":
            if c == top:
                stack.pop()
        elif top == "`":
            if c == "`":
                stack.pop()
            elif js.startswith("${", i):
                stack.append("}")
                i += 1
        elif c in "'\"`":
            stack.append(c)
        elif c in closers:
            stack.append(closers[c])
        elif c == top:
            stack.pop()
        i += 1
    return js[start:i - 1]


def _table_calls(js):
    """The argument text of every `table(...)` call in app.js, comments aside."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return [_upto(js, m.end(), ")") for m in re.finditer(r"(?<![\w.])table\(", js)]


def _own(call):
    """A call's text without the tables drawn inside it (a detail row's own table)."""
    for inner in _table_calls(call):
        call = call.replace(f"table({inner})", "")
    return call


def test_every_sorting_table_names_itself_and_holds_its_own_sort(repo_root):
    """S8, the map's point A (14 Oct 2026): a sort was held under the page and the table's
    columns, so What Changed's Shares and Spread bets held one sort between them, as did its record
    time and the fold beneath it, and the account tables on Accounts. A sorting table names itself
    and its sort is held under that name; one with no name would share again, so it is refused."""
    js = _static("app.js")
    assert "const sortKey = (name) =>" in js and "sortKey(name)" in js, \
        "a sort is not held under its table's name"
    calls = [_own(c) for c in _table_calls(js)]
    assert len(calls) >= 17, f"found {len(calls)} table() calls — has the scan stopped matching?"
    unnamed = [c[:60] for c in calls if "sort: false" not in c and "name:" not in c]
    assert not unnamed, f"a table sorts with no name of its own: {unnamed}"
    names = [n for c in calls for n in re.findall(r'name: "([^"]+)"', c)]
    assert len(names) == len(set(names)), f"two tables share a name: {sorted(names)}"


def test_a_table_whose_order_is_its_layout_keeps_it(repo_root):
    """S8, the map's point B (14 Oct 2026): Performance's year table, drawn as one grid with the
    quarters, sorted where the quarters did not, and YTD return pressed put The book third among
    its accounts; Accounts' Income and costs did the same. A table naming the book first and then
    each account once keeps that order, as a detail's mark history keeps its own."""
    kept = {c.split(",")[0].strip() for c in map(_own, _table_calls(_static("app.js")))
            if "sort: false" in c}
    assert kept == {"x.marks", "quarters", "d.year", "d.income"}, kept


def test_every_account_dropdown_offers_individual_accounts_in_the_books_order():
    """TWO DEFECTS, both found by the owner using the Holdings filter.

    NOT INDIVIDUAL. A holdings row names EVERY account its ticker sits in, joined with " · " so
    no sub-rows double-count. The panel split that column on a COMMA, which never appears in it,
    so nothing ever split and each COMBINATION became its own entry: "Rowe HL ISA · Voss ii
    ISA · Voss ii Trading" was offered as though it were an account. Selecting it returned ZERO
    rows, because no account is called that.

    AND OUT OF ORDER. All three dropdowns were alphabetical, which puts "Voss IG Spread bet"
    between "Voss ii ISA" and "Voss ii Trading" — a spread-bet account in the middle of the
    share ones, with the break between the two valuation bases gone. ACCOUNT_ORDER is an ORDER
    rather than a sort for exactly that reason.

    EVERY OPTION MUST ALSO WORK. A dropdown entry that returns nothing is worse than one that is
    missing: it reads as "this account holds nothing" when the truth is "that is not an account".
    """
    from portfusion.desk.panels import holdings, round_trips, trades
    canonical = _engine.Book().account_order()

    for name, panel in (("holdings", holdings), ("round-trips", round_trips),
                        ("trades", trades)):
        offered = panel.data()["accounts"]

        assert set(offered) <= set(canonical), (
            f"{name} offers something that is not an account: "
            f"{sorted(set(offered) - set(canonical))}")

        ranks = [canonical.index(a) for a in offered]
        assert ranks == sorted(ranks), (
            f"{name} is not in the book's order: {offered}")

        for account in offered:
            assert panel.query(account=account)["rows"], (
                f"{name}: selecting {account!r} returns nothing — a dead option")


@needs("buys")
def test_the_canonical_order_is_the_records_own():
    """The engine holds it so a panel cannot re-derive it and get a different answer."""
    from portfusion.record import rules as D
    order = _engine.Book().account_order()
    assert order == list(D.ACCOUNT_ORDER)
    kinds = [D.ACCOUNT_KIND[a] for a in order]
    assert set(kinds) == {"shares", "spread bet"}, (
        "one basis is missing from the register, so the break below asserts nothing")
    assert kinds == sorted(kinds, key=lambda k: k == "spread bet"), (
        "the break separates the two valuation bases; shares first, then spread bets")


# =====================================================================================
# IS THIS DESK RUNNING THE CODE THAT IS ON DISK?
# =====================================================================================

@pytest.fixture
def source_baseline():
    """Restore record._source_seen, which is process-wide state these tests move."""
    saved = dict(engine._source_seen)
    yield engine._source_seen
    engine._source_seen.clear()
    engine._source_seen.update(saved)


def test_the_scan_covers_this_projects_source_and_nothing_else():
    """The scan reads the package and nothing beside it. The venv sat inside the repository
    while the scan's root was the repository, and the first version walked 592 modules and would
    have named
    `.venv/lib/python3.13/site-packages/pandas/core/frame.py` in the page header the day
    anything was reinstalled. A dependency changing is a real event and it is not this one.

    THE TWO EXCLUSIONS THAT ARE NOT ABOUT NOISE. `store/*.csv` is absent because the engine is
    cached on the store's own mtime, so a changed CSV is picked up live; `desk/static/*` is
    absent because it is read from disk per request. Flagging either would send the owner to the
    restart button when a refresh — or nothing at all — is what is needed.
    """
    from portfusion.desk import panels as _panels
    for name in ("holdings", "dashboard"):
        _panels.get(name)                       # the panels import lazily, as a request does

    names = {str(pathlib.Path(p).relative_to(engine.ROOT))
             for p in engine._repo_modules()}
    assert names, "the scan found nothing at all"

    for expected in ("engine.py", "record/rules.py", "desk/engine.py", "desk/panels/holdings.py"):
        assert expected in names, f"{expected} is imported by the desk and is not scanned"

    for name in names:
        parts = pathlib.Path(name).parts
        assert ".venv" not in parts, f"{name} is a dependency, not this project's source"
        assert "site-packages" not in parts, f"{name} is a dependency"
        assert not name.endswith(".csv"), \
            f"{name} is store data — the engine is cached on its mtime and needs no restart"
        assert "static" not in parts, \
            f"{name} is served from disk per request and needs no restart"


def test_a_file_changed_since_import_reads_stale_and_is_named(source_baseline):
    """The signal that was missing while a server ran a six-day-old engine, asserted.

    NAMED, NOT COUNTED. "1 file changed" sends you looking; "engine.py" tells you what moved.
    """
    # THE ENGINE BY ITS OWN PATH: "ends with engine.py" also takes desk/engine.py, so which file
    # was picked hung on the order the modules came in (the review of 21 Oct 2026).
    target = next(p for p in engine._repo_modules()
                  if pathlib.Path(p).parts[-2:] == ("portfusion", "engine.py"))
    source_baseline[target] = 0.0               # as if imported before the file was written

    f = engine.freshness()
    assert f["source_stale"] is True
    assert "engine.py" in f["source_files"], f"the changed file is not named: {f['source_files']}"
    assert f["source_changed"], "nothing says WHEN the code moved"
    assert f["source_count"] >= 1


def test_a_module_first_seen_now_is_never_stale(source_baseline):
    """THE BASELINE IS PER FILE, not the process start time.

    The panels are imported lazily, on the first request that needs one. Against a process
    clock, a panel edited BEFORE startup and imported AFTER it would report as stale when it
    is the newest thing in the building. A file first seen now is by definition the version
    this process is running.
    """
    source_baseline.clear()
    assert engine.freshness()["source_stale"] is False, \
        "a process that has just seen every file for the first time cannot be behind them"


def test_a_clean_desk_says_nothing_about_its_source(source_baseline):
    """No signal when there is nothing to say. A warning that is always on is furniture."""
    for path, mtime in engine._repo_modules().items():
        source_baseline[path] = mtime
    f = engine.freshness()
    assert f["source_stale"] is False
    assert f["source_files"] == [] and f["source_changed"] is None


def test_the_page_says_the_desk_is_behind_and_points_at_the_restart(repo_root):
    """The button has been on this line since the desk was built; nothing said when to press
    it. That is the whole defect — the freshness line reported the store was fine, because it
    was, while the engine behind the page was six days old."""
    js = _static("app.js")
    assert "source_stale" in js, "the header no longer reads the source-staleness signal"
    assert "restart it" in js, "the warning does not say what to do about it"
    assert "source_files" in js, "the warning does not name what changed"


def test_a_stale_desk_is_a_problem(source_baseline):
    """The LEVEL is the judgement. A stale server answers with an older engine while serving the
    current page, so figures go missing with nothing on screen admitting it."""
    # The engine by its own path, as above.
    target = next(p for p in engine._repo_modules()
                  if pathlib.Path(p).parts[-2:] == ("portfusion", "engine.py"))
    source_baseline[target] = 0.0

    items = panels.get("dashboard").data()["attention"]
    mine = [i for i in items if "restart the desk" in i["text"]]
    assert mine, f"a stale desk raises nothing in Needs attention: {[i['text'] for i in items]}"
    assert mine[0]["level"] == "problem", \
        f"a stale engine is reported as {mine[0]['level']!r} — it produces wrong figures"
    assert "engine.py" in mine[0]["text"], "the item does not name what changed"




def test_every_app_the_desk_hands_uvicorn_imports():
    """uvicorn is given its apps BY NAME, `module:attribute`, and imports them only as the server
    starts. When the app became a package those names still said `desk.app:app`, no test
    started the desk through its command line, and the desk did not come back after the merge
    (18 Oct 2026). Every such name in the app is imported here, as uvicorn would."""
    import ast
    import re
    from uvicorn.importer import import_from_string
    from harness import SRC, TESTS
    names = {n.value for p in SRC.rglob("*.py") if not p.is_relative_to(TESTS) for n in ast.walk(ast.parse(p.read_text()))
             if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and re.fullmatch(r"[A-Za-z_][\w.]*:[A-Za-z_]\w*", n.value) and "." in n.value}
    assert names, "no app named for uvicorn at all — has the desk stopped using it?"
    for name in sorted(names):
        assert import_from_string(name) is not None, name
