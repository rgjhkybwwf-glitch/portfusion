"""THE PAGE LOOK — how every tab is drawn: its colours, its own prose, its template and its names."""
from __future__ import annotations

from portfusion import engine as _engine
from portfusion.desk import panels
from harness import SRC, desk_script, desk_style


# =====================================================================================
# MOVEMENT COLOUR
#
# `house/palette.py` heads UP and DOWN "movement, which is not provenance". That is
# the rule these two tests hold: a THIRD channel, beside font-colour-as-origin and
# fill-as-state, which must borrow from neither and must say only what a figure's SIGN is.
# =====================================================================================


def test_movement_colour_is_used_and_scoped():
    """`--up` and `--down` are worn, or a loss renders in the ink of a gain. A token nobody
    consumes is a palette entry pretending to be a treatment.

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
      unrealised unrealised_pct realised realised_pct annualised_pct life_gain life_pct
                  a holding's, a round trip's and a company life's gains: results, as `gain` is.
      transacted  NOT a result, and never to be added. Buying shares is not a
                  gain and selling them is not a loss. Same exclusion as
                  `difference`: money, often negative, carrying no judgement. Colouring it
                  would turn every purchase green and every sale red.
    """
    css, js = desk_style(), desk_script()

    assert "var(--up)" in css and "var(--down)" in css, \
        "the stylesheet does not consume the movement tokens — they are generated and unused again"

    from portfusion.house.palette import MOVEMENT_FIELDS
    assert "PRECISION.movement_fields.includes(c)" in js, "the desk no longer colours house's list"
    cols = set(MOVEMENT_FIELDS)
    assert cols == {"gain", "unrealised", "unrealised_pct", "realised_pct", "return",
                    "change", "price_effect", "fx_effect", "price_move_pct",
                    "realised", "life_gain", "life_pct", "annualised_pct"}, \
        f"MOVEMENT_FIELDS is {sorted(cols)}"

    for excluded, why in (("difference", "a reconciliation gap is not a loss"),
                          ("weight", "a share of exposure is never negative"),
                          ("transacted", "a purchase is not a gain and a sale is not a loss")):
        assert excluded not in cols, f"{excluded} must not wear movement colour — {why}"

    # ZERO WEARS NEITHER. A flat quarter is not a gain and must not read as one.
    assert "v === 0" in js, "movement() no longer leaves an exact zero uncoloured"


def test_every_screen_colour_is_legible_in_both_schemes():
    """A COLOUR THAT CANNOT BE READ IS WORSE THAN NONE, and nothing else in the project can tell.

    Every text colour is held to 4.5 on the paper and on the band a header or a total row sits on,
    and an input's border to the 3.0 a control boundary needs.

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


def test_no_panel_leaves_a_handler_on_the_frame():
    """#main OUTLIVES EVERY PANEL, so a handler a panel adds to it on each draw stays behind and
    multiplies. A panel's handlers go on its own elements; a delegated one on #main is wired once,
    behind a guard, from a `main` it has looked up."""
    js = desk_script()
    assert '$("#main").addEventListener' not in js


def test_no_call_site_puts_anything_in_a_style_attribute():
    """Every width, colour and spacing lives in the stylesheet, so a call site sets none of them."""
    import re
    used = re.findall(r'style="([^"]*)"', desk_script())
    assert not used, f"app.js sets style={used}; the style layer is the stylesheet"


# =====================================================================================
# THE DESK'S OWN PROSE — a ratchet that rises only with a reason
# =====================================================================================

#: How many words of CHROME the desk shows. A ratchet: it goes down, or up with a reason beside it.
#:
#: The desk is for account management, and chrome above the work pushes it below the fold.
#:
#: Chrome is what the desk says ABOUT ITSELF — a caveat, a note, a button's blurb. It is not the
#: record: a trade's note and a position's reasoning are FACTS and are not counted here, and they
#: are already behind a per-row toggle. Nor is anything inside a `.why-fold`, which is the whole
#: point of the fold — an explanation moved below the work it describes has stopped competing
#: with it, and pricing it the same would punish the fix.
#:
#: A ratchet, in the shape `tests/record/test_evidence.py:_UNCLASSIFIED_HIGH_WATER` uses. Cutting can
#: never fail it; only new prose can.
#:
#: The step line's quiet notes (`<span class="muted small">`, `quiet()`) are counted too.
DESK_CHROME_WORDS = 438


def _chrome_words():
    """Every word the desk says about itself, counted one way. See DESK_CHROME_WORDS."""
    import re

    from portfusion.desk import actions
    from portfusion.desk import panels as _panels

    js = desk_script()
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


def test_the_desks_own_prose_rises_only_with_a_reason():
    """The desk is an operating interface, not a place to record decisions about it.

    Reasons accumulate, and together they push the work below the fold.

    The fix is not deletion, it is placement — `whyFold()` puts the reasons under the work they
    describe — so this counts only what still sits in the reader's way. Raising it needs a reason
    written down beside it; the ordinary way past it is to move prose into the fold or into a
    docstring, where a maintainer wants it and an operator never looks.
    """
    words = _chrome_words()
    assert words <= DESK_CHROME_WORDS, (
        f"the desk now says {words} words about itself, above the {DESK_CHROME_WORDS} on file. "
        f"An explanation belongs below the work it describes — `whyFold()` — or in a docstring. "
        f"Take prose out, or raise this with the reason beside it.")


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


def test_the_dashboards_status_line_draws_what_it_is_sent():
    """THE AGE LEADS THE PRICES STEP, and the year-to-date step names the first day the year
    counts. A payload field the renderer drops is a figure shown nowhere. `year` and `opens` are
    the two not drawn: `first_day` names both, and no page prints the day before it."""
    js = _renderer(desk_script(), "dashboard")
    data = panels.get("dashboard").data()
    assert set(data["prices"]) == {"newest", "oldest", "spread_days", "marks", "age_days"}
    assert set(data["ytd"]) == {"year", "opens", "first_day", "frozen"}
    missing = ([f"p.{k}" for k in data["prices"] if f"p.{k}" not in js]
               + [f"y.{k}" for k in ("first_day", "frozen") if f"y.{k}" not in js])
    assert not missing, f"the Dashboard is sent {missing} and draws none of it"
    assert "y.opens" not in js, "the Dashboard prints the day before the year's first"
    assert panels.get("performance").data()["year_from"] == data["ytd"]["first_day"]


def test_the_dashboard_lists_the_checks_the_audit_prints():
    """WHAT WAS CHECKED, apart from what needs attention: what is captured has a display home.
    The engine's notes, in its words and its order, and none counting what a gap already says.

    AND EACH FINDING LEADS TO ITS PAGE: the engine's, one the desk has, drawn as a link in the
    words of its step; what waits on the Bench is drawn only where the Bench opens. So does the
    round trips count, to the page that lists them."""
    data, found = panels.get("dashboard").data(), _engine.Book().findings()
    js = _renderer(desk_script(), "dashboard")
    assert data["checks"] == found["notes"]
    assert any(c.startswith("evidence:") for c in data["checks"])
    assert "d.checks" in js and "What was checked" in js
    for note, gap in (("reasoning:", "reasoning owed"), ("funding interest:", "funding interest"),
                      ("dated rates:", "rate owed")):
        if any(a["text"].startswith(gap) for a in data["attention"]):
            assert not [c for c in data["checks"] if c.startswith(note)], note
    sent = {a["text"]: (a.get("panel"), a.get("action")) for a in data["attention"] + data["bench"]}
    for f in found["problems"] + found["gaps"]:
        assert sent[f] == (f.page, f.action), f
    assert {p for p, _ in sent.values() if p} <= {p.NAME for p in panels.all_panels()}, sent
    assert "panelLink(a.panel, a.action" in js and 'PANELS.has("bench") ? d.bench' in js
    leads = {f["label"]: f.get("panel") for f in data["figures"] if f.get("panel")}
    assert leads == {"Round trips closed out": "round-trips"}
    assert set(leads.values()) <= {p.NAME for p in panels.all_panels()} and "panelLink(f.panel, " in js
    # AND OPENS IT ON WHAT IT COUNTS: boxes the page draws and asks with.
    held = next(f for f in data["figures"] if f.get("panel"))["held"]
    rt = desk_script()
    assert held == {"rt-view": "holding", "rt-closed": "yes"} and "f.held)" in js
    assert all(f'id="{box}"' in rt for box in held) and "go.dataset.held" in rt


def test_the_footer_says_which_release():
    """Every page's footer says which release the desk is, held once, in portfusion/__init__.py,
    and filled into the shell. Never "Nothing here is typed": the Bench is where rows are typed."""
    from portfusion import about
    from portfusion.desk import bundle
    template = (SRC / "desk" / "static" / "index.html").read_text()
    assert "<!-- footer -->" in template and "Nothing here is typed" not in template
    page = bundle.index().decode()
    assert f"<span>{about.release()}</span>" in page, about.release()


def test_every_page_is_drawn_through_the_template():
    """`page()` draws the bands in one order, so a fix lands on every page; a page that skips it
    drifts."""
    js = desk_script()
    skipped = [p.NAME for p in panels.all_panels() if "page({" not in _renderer(js, p.NAME)]
    assert not skipped, (
        f"these pages are not drawn through page(): {skipped}. A new band belongs in the "
        f"template, where every page gets it, not in one page's renderer.")


def test_the_template_has_no_note_box_and_no_pill():
    """Two treatments add a second voice to a page: the note box between the figures and the
    table (explanations live in the fold), and the basis pill beside a figure whose label already
    says what it is.

    The design system's labels are condensed capitals, set by the stylesheet, so every label is
    WRITTEN in sentence case, which this checks — a heading typed in capitals would hide three
    spellings."""
    import re
    js, css = desk_script(), desk_style()
    assert 'class="caveat"' not in js and ".caveat" not in css, "a note box is back"
    assert 'class="basis"' not in js and ".basis" not in css, "a basis pill is back"
    typed = [h for h in re.findall(r"<(?:h2|th)[^>]*>([^<$]{4,})</", js) if h.isupper()]
    assert not typed, f"a heading is typed in capitals rather than styled so: {typed}"


def test_the_page_head_is_ruled_off_on_every_page():
    """A rule under the title and its scope line, on every page: it belongs to the head, which
    every page draws through `page()`, and the status line draws none beneath it."""
    import re
    css = desk_style()
    head = re.search(r"\.page-head \{([^}]*)\}", css).group(1)
    steps = re.search(r"\.steps \{([^}]*)\}", css).group(1)
    assert "border-bottom" in head, "the page head has lost its rule"
    assert "border-top" not in steps, "the status line draws a second rule under the head"


def test_every_wide_table_scrolls_in_its_own_box():
    """A wide table scrolls in its own box, so the page never does. The two narrow kinds, a page's
    figures and Holdings' bars, are two or three columns and fit a phone as they are."""
    import re
    js = desk_script()
    narrow = ('<table class="figures">', '<table class="alloc">')
    def boxed(at):
        return re.search(r'<div class="scroll"[^>]*>\s*$', js[max(0, at - 80):at])
    loose = [js[m.start():m.start() + 60].split("\n")[0] for m in re.finditer(r"<table", js)
             if not boxed(m.start()) and not js.startswith(narrow, m.start())]
    assert not loose, f"a table outside a scroll box: {loose}"


def test_the_dashboards_glance_stacks_on_a_phone():
    """The Dashboard's figures stand beside Needs attention. Beside them on a phone the list would
    be one letter wide, so at the phone's width, the 48rem the gutter narrows at, the list goes
    below them."""
    import re
    css = desk_style()

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


def test_every_filter_row_can_be_cleared():
    """The filters band is one shape on every page, and "clear filters" is part of it."""
    import re
    js = desk_script()
    rows = re.findall(r"filters: \{([^\[]*)fields:", js)
    assert rows and all("clear:" in r for r in rows), \
        "a page's filters band has no \"clear filters\""


#: THE BENCH'S OWN SCRIPTS, whose controls are still the underlined link.
BENCH_SCRIPTS = ("bench.js", "bench-form.js", "bench-review.js", "sweep.js")


def test_a_control_is_drawn_in_the_shape_of_what_it_does():
    """GO, ACT AND OPEN, each written once in kit.js: a way to another page is `goButton()`, an
    action `actButton()`, and a row's detail `detailToggle()`. No script but the Bench's draws
    the underlined link, so a reader can tell what a word does before pressing it."""
    import re
    from portfusion.desk import bundle
    def shape(name):
        """The class, alone or first among others."""
        return re.compile(rf'class="{name}[\s"]')
    for name in bundle.SCRIPTS:
        assert name in BENCH_SCRIPTS or not shape("link").search(desk_script(name)), (
            f"{name} draws a control as an underlined link: draw it through goButton() or "
            "actButton() in kit.js")
    js, kit = desk_script(), desk_script("kit.js")
    for name in ("go", "act"):
        assert len(shape(name).findall(js)) == 1 and shape(name).search(kit), (
            f"the {name} shape is written somewhere other than kit.js, or twice")


# =====================================================================================
# RETIRED TAB TITLES AND BUTTON LABELS — a rename leaves nothing calling the old name
# =====================================================================================

#: TAB TITLES THAT NO LONGER EXIST, and what replaced each. A renamed tab leaves its old name
#: scattered through docstrings, comments and guides that a reader then cannot find on screen —
#: prose drifting from behaviour, which is the defect this project is built to catch. This is
#: what makes that checkable instead of careful.
RETIRED_TAB_TITLES = {
    # The keys are spelled out here rather than assembled, because a blanket rename over this
    # file would rewrite them into their own replacements — the list that polices a rename
    # cannot itself be a casualty of one. (tab-name-ok: this is the retired list)
    "Last Refresh": "What Changed",
    "Refresh Bay": "Price Refresh",
    "What changed": "What Changed",     # title case, matching its neighbours
}


#: Action labels that no longer exist, policed by the same test for the same reason. A button
#: is a thing an operator is TOLD to press — by docs/reconciling.md, by the close checklist the
#: build prints — so a renamed one strands an instruction that cannot be followed.
RETIRED_ACTION_LABELS = {
    "Take a reading": "Price Refresh",             # renamed for its scope
    "Read IG live valuations": "Price Refresh",    # IG equity is read with the
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
                # use; matching exactly would miss a heading. Not in lower case:
                # "since the last refresh" is English, not a tab. A rename of case alone
                # has no capital form of its own, so it stays exact (tab-name-ok).
                forms = (old,) if old.lower() == new.lower() else (old, old.upper())
                if any(f in line for f in forms) and new not in line and new.upper() not in line:
                    stale.append(f"{rel}:{n} names {old!r} (now {new!r}): {line.strip()[:70]}")
    assert not stale, (
        "these name a tab that no longer exists:\n  " + "\n  ".join(stale[:12]))


def test_every_live_tab_title_is_one_a_panel_declares():
    """The other half: the retired list must not name something still in use. A rename that
    was reverted, or never finished, would otherwise be policed against the wrong answer."""
    live = {m.TITLE for m in panels.all_panels()}
    wrongly_retired = live & set(RETIRED_TAB_TITLES)
    assert not wrongly_retired, (
        f"{sorted(wrongly_retired)} are listed as retired but a panel still declares them")
    for new in RETIRED_TAB_TITLES.values():
        assert new in live, f"{new!r} is named as a replacement but no panel declares it"
