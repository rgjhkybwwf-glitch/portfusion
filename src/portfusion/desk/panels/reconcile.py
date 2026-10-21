"""RECONCILE — what the book says, beside what the broker says.

Reconciliation as a screen. A share account's reading is its holdings export, filed on the Bench
only if every holding's units are the book's. An IG account's equity, struck in one pass with the
marks, is held to `rules.RECON_LIVE_TOLERANCE_PCT`; struck apart, it is NOT JUDGED and reported
as a gap, never as a pass or a failure.

The rule is not implemented here. `Book.reconciliation_verdict()` decides, and the audit and the
Dashboard ask the same function — the three of them disagreeing about whether an account
reconciles would be worse than any one of them being wrong.

REPORT ONLY WHAT DISAGREES is a REPORTING rule rather than a data one. The panel hands over every
row with its verdict; the screen leads with the ones that need attention.
"""
from __future__ import annotations


from portfusion.desk import engine
from portfusion.desk.panels import _shape

#: RECONCILE, NOT ACCOUNTS: the register, capital and income are the Accounts page's, and this
#: page is the reconciliation alone. Its file, URL and title are one name, as every panel's are.
NAME = "reconcile"
TITLE = "Reconcile"
ORDER = 28

#: The table under "Every account". The rest of each row is the verdict's working, read in the
#: row's own sentence rather than given a column.
#:
#: WHAT THE BROKER'S SIDE RESTS ON, LAST: the report's two columns, in its words and its layout —
#: the document and its day, then whether it is on file or was read live — from the same engine
#: answer, `Book.quarter_evidence()`, asked for the newest reading rather than a quarter's.
COLUMNS = ("account", "book", "broker", "difference", "verdict", "last_check", "document")


def data() -> dict:
    b = engine.book()
    # The engine itself once the record has loaded, not with the module (`price_refresh.query`).
    from portfusion.engine import Book
    rests = b.quarter_evidence(None).set_index("account")
    rows = []
    for r in b.reconciliation().itertuples(index=False):
        v = Book.reconciliation_verdict(r.statement, r.difference, getattr(r, "evidence", ""),
                                   getattr(r, "comparable", None),
                                   getattr(r, "comparability", ""))
        rows.append({
            "account": r.account,
            "book": _num(r.book),
            "broker": _num(r.statement),
            "difference": _num(r.difference),
            "band": _num(v["band"]),
            # A SPREAD-BET READING'S FIVE FIGURES, IG's own under IG's names, drawn under the
            # broker's figure; None on a share row.
            "funds": _num(r.funds), "running_pl": _num(r.running_pl), "equity": _num(r.equity),
            "deposit": _num(r.deposit), "available": _num(r.available),
            "verdict": v["verdict"],
            "checkable": v["checkable"],
            # WHY this row is judged the way it is, in the row rather than in a footnote. A
            # reader should not have to know which accounts are spread bets to read the table.
            # A GAP SAYS WHICH GAP: no broker figure at all, a share reading that lists no
            # units, or an IG reading not struck in one pass with the marks.
            # THE WORDS ARE THE ENGINE'S, and this quotes them. Composed here, they would be a
            # classification living in a renderer — and a second renderer needing the same
            # distinction would work out its own, and get it wrong.
            "rule": v["rule"],
            **_rests_on(rests.loc[r.account] if r.account in rests.index else None),
        })
    return {
        "rows": rows,
        "disagreements": [r for r in rows if r["verdict"] == "differs"],
        "gaps": [r for r in rows if not r["checkable"]],
    }


def _num(x):
    return _shape.money(x)


def _rests_on(e) -> dict:
    """The report's two cells for one account: the document and its day, then whether it is on
    file or was read live. `report/page.py` lays out the same answer the same way."""
    if e is None or e["as_of"] is None:
        return {"last_check": "no broker check", "document": None}
    return {"last_check": _shape.reading(e["document"], e["as_of"]), "document": e["held"]}
