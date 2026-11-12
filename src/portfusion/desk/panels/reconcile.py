"""RECONCILE — what the book says, beside what the broker says.

Reconciliation as a screen. A share account is checked on units: its holdings export, filed on the
Bench only if every holding's units were the book's, is counted again here. An IG account's
equity, struck in one pass with the marks, is held to `rules.RECON_LIVE_TOLERANCE_PCT`; struck
apart, it is NOT JUDGED and reported as a gap, never as a pass or a failure.

The rule is not implemented here, and neither are its words. `Book.account_checks()` decides and
says, and the audit and the Dashboard ask the same function — the three of them disagreeing about
whether an account reconciles would be worse than any one of them being wrong.

REPORT ONLY WHAT DISAGREES is a REPORTING rule rather than a data one. The panel hands over every
row with its verdict; the screen leads with the ones that need attention.
"""
from __future__ import annotations


from portfusion.desk import engine
from portfusion.desk.doors import observations
from portfusion.desk.panels import _shape
from portfusion.house import precision as P

#: RECONCILE, NOT ACCOUNTS: the register, capital and income are the Accounts page's, and this
#: page is the reconciliation alone. Its file, URL and title are one name, as every panel's are.
NAME = "reconcile"
TITLE = "Reconcile"
ORDER = 28

#: The table under "Every account". The rest of each row is the verdict's working, read in the
#: row's own sentence rather than given a column.
#:
#: WHAT THE BROKER'S SIDE RESTS ON, LAST: the report's two columns, in its words and its layout —
#: the document and its day, then whether it is on file or was read from IG — from the same
#: engine answer, `Book.quarter_evidence()`, asked for the newest check rather than a quarter's.
COLUMNS = ("account", "book", "broker", "difference", "verdict", "last_check", "document")

#: EVERY VERDICT HAS A TAG, the colour its row's tag wears. One that fell through to `note` would
#: wear the colour of a row inside its band, for a row that has not been judged at all.
VERDICT_TAG = {"units-agree": "ok", "within-band": "note", "differs": "problem",
               "no-statement": "gap", "no-holdings": "gap", "struck-apart": "gap",
               "no-reading": "gap"}


def data() -> dict:
    b = engine.book()
    # The engine itself once the record has loaded, not with the module (`price_refresh.data`).
    checks = b.account_checks(observations.counted()).set_index("account")
    rows = []
    for r in b.reconciliation().itertuples(index=False):
        c = checks.loc[r.account]
        rows.append({
            "account": r.account,
            "book": _num(r.book),
            "broker": _num(r.statement),
            "difference": _num(r.difference),
            # A SPREAD-BET READING'S FIGURES, IG's own under IG's names, drawn under the
            # broker's figure: the ones the reading holds, and none on a share row.
            "ig_figures": [{"label": label, "value": _num(v)} for label, v in (
                ("funds", r.funds), ("running P/L", r.running_pl), ("deposit", r.deposit),
                ("available", r.available)) if v is not None and v == v],
            "verdict": c["verdict"],
            "tag": VERDICT_TAG[c["verdict"]],
            "checkable": c["checkable"],
            # QUOTED, NEVER COMPOSED: `Book.account_checks()` words every page's account alike.
            "compared": c["compared"],
            "state": c["state"],
            "next": c["next"],
            "reads": c["page"],
            "sentence": c["sentence"],
            **_rests_on(c),
        })
    return {
        "rows": rows,
        "columns": list(COLUMNS),
        "disagreements": [r for r in rows if r["verdict"] == "differs"],
        "gaps": [r for r in rows if not r["checkable"]],
    }


def _num(x):
    return _shape.money(x)


def _rests_on(c) -> dict:
    """The report's two cells for one account, as `report/page.py` lays them out."""
    if c["on"] is None:
        return {"last_check": "no broker check", "document": None}
    held = {"read from IG": f"read from IG on {P.day(c['on'])}",
            "retrieved another way": "n/a — retrieved another way"}.get(c["held"], c["held"])
    return {"last_check": _shape.reading(c["against"], c["on"]), "document": held}
