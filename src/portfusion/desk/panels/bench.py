"""THE BENCH — the panel. Shapes what `desk/intake/bench.py` holds; decides nothing itself."""
from __future__ import annotations

from portfusion.desk import engine
from portfusion.desk.doors import research_notes
from portfusion.desk.intake import bench, dropoff, read_rows, sweep
from portfusion.desk.actions import Action, register
from portfusion.desk.engine import _guarded
from portfusion.record import schema as _schema

NAME = "bench"
TITLE = "Bench"
ORDER = 20

#: EVERY FIELD THE FORMS SHOW, from the tables the bench writes, so each is headed in
#: house/headings.py's words for this tab and never by its store name. The schema's column
#: definitions only: importing it reads no table.
FORM_COLUMNS = tuple(dict.fromkeys(f.name for t in bench.TABLES + bench.REGISTER
                                   for f in _schema.TABLES[t].fields))

#: WHAT THE REVIEW SAYS BESIDE AN ITEM'S ROWS: an IG contract its sale leaves with no open leg,
#: whose live price the same write retires, and the ids a backdated row moves.
REVIEW_COLUMNS = ("retires", "renumbers")


def data() -> dict:
    items = bench.all_items()
    return {
        "items": [_summary(i) for i in items],
        "documents": bench.waiting_documents(),
        # A PUBLISHED RESEARCH NOTE THE BOOK HAS NO ROW FOR, each with the codes it covers: one
        # press records it (`desk/doors/research_notes.py`).
        "notes": _guarded(lambda: research_notes.owed(engine.book().codes_held())),
        "tables": list(bench.TABLES + bench.REGISTER),
        "table_labels": bench.TABLE_LABELS,
        "adjustment_label": bench.ADJUSTMENT_LABEL,
        "forms": {t: bench.form_for(t) for t in bench.TABLES + bench.REGISTER},
        "limbs": [{"key": k, "label": lab, "help": h} for k, lab, h in bench.LIMBS],
        # WHAT KIND OF DOCUMENT THIS IS. ii gives contract notes and quarterly statements —
        # official, referenced, reconciled — and also a recent-transactions download, which is
        # a snapshot between quarters carrying no reference number. They are not the same
        # evidence and the screen should not pretend they are.
        "evidence_classes": bench.evidence_classes(),
        # WHAT A DROPPED FILE MAY BE, from desk/intake/dropoff.py rather than written out here. Same
        # discipline as the forms coming from schema.TABLES: the screen states the rule, the
        # module owns it, and a refusal is never the first time anyone hears it.
        "accepts": dropoff.accepts(),
        # THE KINDS READ ON THIS MACHINE, from their own cells — `read_rows.LOCAL`. Anything
        # else is read by a Claude session through `python3 -m portfusion.desk.intake.propose`.
        "reads_here": sorted(read_rows.LOCAL),
        "why": WHY,
    }


#: HOW THIS PAGE WORKS, in the order the work comes in and in a reader's words (no decision
#: letters, no committing or reverting). The one place the page explains itself; nothing above
#: the fold does.
WHY = [
    ("A dropped document",
     "Drop a contract note, statement or broker download onto the page, or choose one; it "
     "waits under Documents until you work it. Say what kind of document it is, which fills "
     "in who issued it and what its reference looks like, then check each figure read from it "
     "against the page. A download marked as a snapshot comes straight from the broker and can "
     "be pulled again, but it is not the dated statement a quarter is checked against. When "
     "the item is written the document is filed with it; one you don't need can be withdrawn."),
    ("A swept event",
     "Sweep IG events reads the buys, sales, costs and money in or out of each IG account over "
     "the look-back chosen beside it, never before the account's record began, and checks each "
     "against the record by its IG deal number. The sweep "
     "writes nothing. Anything the record doesn't have offers \"work it\", which puts it on "
     "the Bench with its figures and evidence filled in; the reason is yours to write."),
    ("Writing it to the record",
     "Finish one item at a time: once its checks are green it offers the next, and when none "
     "is left, \"review and write\". The review shows each ready item as it will be recorded, "
     "and each is written by its own press. Why we entered and Why we exited are the one thing "
     "no document holds, so the record keeps every one, dated, beside any written before. A "
     "written entry can't be undone from the desk."),
]


def _summary(item: dict) -> dict:
    gates = bench.gates(item)
    return {"id": item["id"], "title": item["title"], "origin": item["origin"],
            "created": item["created"], "state": item["state"],
            # WHICH DOCUMENT this item works, so the list can say so and the screen can tell
            # two items apart without opening them.
            "document": (item.get("document") or {}).get("name"),
            "rows": len(item.get("rows") or []),
            "ready": all(g["ok"] for g in gates),
            "blocked_by": [g["label"] for g in gates if not g["ok"]]}


def _existing_why(item: dict) -> dict:
    """What the record ALREADY says about the tickers this item touches: {ticker: [{date,
    why_entered, why_exited}, ...]}, oldest first.

    A new why is added beside these, never in place of one (`commit.py` appends), so they are
    shown as the record so far: the thesis an addition builds on, or the reason a trim departs
    from.
    """
    tickers = sorted({str((r.get("values") or {}).get("ticker", "") or "").strip()
                      for r in item.get("rows") or []} - {""})
    if not tickers:
        return {}

    try:
        why = engine.book().D.REASONING
    except Exception:
        return {}
    return {t: [{"date": r.date.isoformat(), "why_entered": r.why_entered,
                 "why_exited": r.why_exited} for r in why[t]]
            for t in tickers if why.get(t)}


def detail(item_id: str) -> dict:
    """One item in full, with its gates and what approving it would produce."""
    from portfusion.desk.doors import commit
    item = bench.get(item_id)
    return {"item": item, "gates": bench.gates(item),
            "retires": _guarded(lambda: commit.retired_by(item.get("rows") or [])),
            "renumbers": _guarded(lambda: commit.renumbering(item.get("rows") or [])),
            # THE REST OF THE BENCH, in its order, each ready or not — so a finished item can
            # offer the next one still owed, or the review once none is.
            "bench": [{"id": s["id"], "title": s["title"], "ready": s["ready"]}
                      for s in map(_summary, bench.all_items())],
            "approved": bench.approved(item), "paste": bench.paste_block(item),
            "existing_why": _existing_why(item)}


# =================================================================================================
# THE IG EVENT SWEEP.
#
# IT BELONGS WHERE ITS OUTPUT GOES. The bench has three routes in — a dropped document,
# `+ new item`, and a swept IG event — and a sweep run from another tab would have "Work this
# event" carry you across to reach the item it had just created.
#
# THE OTHER HALF OF THE ARGUMENT: a sweep also finds what would make the book incomplete. A
# missing trade makes the book's own figure wrong, and a reconciliation run against it reports a
# difference that is really an unentered event. Reconcile neither re-runs a 30-day broker call
# nor reports a sweep.
# =================================================================================================
register(Action(
    name="ig-events", label="Sweep IG events", panel=NAME, writes=None,
    reaches="network",
    gate=("The owner clicks it, and the window is theirs. Nothing is swept when the panel is "
          "merely opened — a call to the broker is not something to make by arriving."),
    summary=("Reads IG buys, sales, costs and money in or out over the chosen look-back, and "
             "checks each against the record by its deal number. It writes nothing."),
    run=sweep.ig_events,
))


# THE THIRD ROUTE ONTO THE BENCH, after `+ new item` and a document.
#
# ONE EVENT, ONE BUTTON, ONE ITEM. The sweep reports; carrying an event across is a separate
# press, per event. A single button that swept everything onto the bench would be a background
# pass in all but name, and this project has not allowed one.
#
# `writes=None` IS THE TRUTH. It creates a bench ITEM, which is staging and not the record —
# `_inbox/.bench/`, gitignored, and nothing there is a figure until commit.py writes it. An
# action may never declare writes="events"; Action refuses to be constructed. That is the marks rule
# and this action is what it prescribed rather than an exception to it.
#
# THE EVENT ALONE: a mark rides on an item only as IG's own level, read by the set-up below.
register(Action(
    name="ig-event-to-bench", label="Work this event", panel=NAME, writes=None,
    # INLINE: it belongs to one swept event and is rendered on that event's row. Without it the
    # button would stand in the panel's action list with nothing to act on.
    inline=True,
    gate="The owner presses it on one event from a sweep they ran",
    summary=("Opens a bench item for one swept IG event, its evidence and row from the API and "
             "its why left to you. Pressing twice returns the same item."),
    run=lambda event: bench.to_bench(event),
))


# A FIRST BET ON A CONTRACT THE BOOK LACKS: the same item, with its line, company and contract,
# and the contract's first mark read from IG on this press, so the bet and the mark it is valued
# at are written together.
register(Action(
    name="ig-setup-to-bench", label="Set up this bet", panel=NAME, writes=None,
    reaches="network", inline=True,
    gate="The owner presses it on one swept bet",
    summary="Opens a first bet on the bench with its line, contract and live IG level.",
    run=sweep.set_up,
))
