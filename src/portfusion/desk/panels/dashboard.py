"""THE SNAPSHOT — where are we, and what needs attention.

It is not the report. The report is frozen and quarterly and answers *how did we do*; the
snapshot is live and answers *where are we now*. The views are largely the same. What only the
snapshot carries is the OPERATIONAL layer — what is stale, what is missing, what is owed —
which the report must never carry.

EVERY FIGURE HERE IS DERIVED AT RENDER TIME from `engine/`. Nothing is typed, nothing is cached
beyond the store's own mtime, and there is no second calculation: the arithmetic all happens in
the engine and this module only decides what to show and how to label it.
"""
from __future__ import annotations

from portfusion.desk import engine
from portfusion.desk.panels import _shape

NAME = "dashboard"
TITLE = "Dashboard"
ORDER = 10

#: THE DASHBOARD'S OWN WORD on the registry's figures: which lead a group, and which sit under the
#: one before. Every label, its order and its unit are `Book.HEADLINE`'s.
LEAD = frozenset({"Net asset value", "Total market exposure", "YTD return (MWR)"})
INDENT = frozenset({"— of which securities owned", "— of which spread-bet notional"})


def data() -> dict:
    b = engine.book()
    ageing = b.price_ageing()
    found = b.findings()

    # EVERY FIGURE AND ITS LABEL COME FROM THE ENGINE — `Book.headline()`, the route the report
    # takes too. Two routes to one number is one route too many. Every registered figure is
    # shown here or on the report (tests/test_figures.py).
    f = b.headline()

    def fig(label):
        basis = b.basis_of(label)
        value = f[label]
        # A STERLING FIGURE IS "money" to the browser, which formats by this word.
        kind = {"gbp": "money"}.get(b.HEADLINE[label]["unit"], b.HEADLINE[label]["unit"])
        return {"label": label,
                "value": _shape.plain(value) if kind in ("pct", "count") else _shape.money(value),
                "kind": kind, "basis": basis,
                "notional_basis": basis in b.NOTIONAL_BASES,
                **({"lead": True} if label in LEAD else {}),
                **({"indent": True} if label in INDENT else {})}

    # THE REGISTRY'S FIGURES IN THE REGISTRY'S ORDER: net asset value leads, as on the report, and
    # exposure follows with the two parts that make it up. A quarter's own is the report's.
    figures = [fig(label) for label, spec in b.HEADLINE.items() if not spec.get("report_only")]

    return {
        # WHERE THE BOOK STANDS, AND WHEN. The same Book.valued_at() the report and every page
        # read, so no two of them can disagree about what "now" means.
        "valued_at": b.valued_at(),
        "figures": figures,
        "prices": ageing,
        # WHICH YEAR "YTD" IS OF, and the 31 December it opens at: frozen, or the reason every
        # year-to-date figure is blank.
        "ytd": b.ytd_window(),
        "attention": _attention(found),
        # THE CHECKS BEHIND IT, in the engine's words: the lines `portfusion record` prints under
        # the figures, so a clean list shows what was checked as well as that nothing failed.
        "checks": found["notes"],
        # THE LATEST REPORT THE GATE ALLOWS, for the step line: the Reports page has the rest.
        "report": next((q for q in engine.reports()["quarters"] if q["closed"] and not q["gaps"]),
                       None),
    }


def _attention(f: dict) -> list[dict]:
    """What is stale, missing or owed. The half the report must never carry.

    `Book.findings()`'s, the same list `portfusion record` prints, so the desk and the command
    line cannot disagree about whether something is a problem.
    """
    items = ([{"level": "problem", "text": p} for p in f["problems"]]
             + [{"level": "gap", "text": g} for g in f["gaps"]])

    fresh = engine.freshness()
    # A PROBLEM RATHER THAN A NOTE: a stale SERVER answers with an older engine while serving
    # the current page, so figures can be missing or wrong with nothing on screen admitting it.
    if fresh["source_stale"]:
        more = fresh["source_count"] - len(fresh["source_files"])
        named = ", ".join(fresh["source_files"]) + (f" and {more} more" if more > 0 else "")
        items.append({"level": "problem",
                      "text": (f"this desk is running code it imported before "
                               f"{fresh['source_changed']} — {named} changed since. The page "
                               f"is served from disk and is current; the engine behind it is "
                               f"not, so restart the desk before trusting these figures")})
    if not items:
        items.append({"level": "clear", "text": "nothing outstanding — the record's findings are clean"})
    return items
