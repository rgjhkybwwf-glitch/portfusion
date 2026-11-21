"""THE BENCH — an event, from evidence to an approved row.

WHAT THIS IS FOR. Something happened in the market and the record has to catch up. A dropped
document, an IG read and "I made a spread bet" are three inputs to ONE pipeline, not three
procedures.

    open  ->  evidence  ->  reasoning  ->  proposed rows  ->  approved  ->  written  ->  archived
              3 limbs      the why         validated live     all gates    commit.py   _archive/

THE REASONING IS THE ONLY INPUT WITH NO OTHER SOURCE. A price can be re-fetched, a contract note
re-downloaded; why a position was taken exists nowhere but in the owner's head, and without this it
gets typed into a CSV cell in the middle of a chat. That is what this screen is really for.

IT PROPOSES NOTHING BY ITSELF, ON PURPOSE. A screen cannot parse an arbitrary ii contract note
deterministically, and a parser that guessed would be fabricating figures, and every figure must
trace to a named source. So the bench is a FORM, not a parser: it shows the document beside fields
whose values come from the store's own vocabulary, and it validates through `record/schema.py`,
which is the same door the CSV loader uses. The judgement stays human; what goes away is
transcription error and invented
spellings. (`desk/intake/propose.py` and `desk/intake/read_rows.py` fill the form; neither parses a guess.)

NOTHING HERE WRITES TO store/. This module keeps the item, its preview and the documents it reads;
`bench_form.py` holds the form and `bench_gates.py` the gates, and every name of theirs is asked
of this module too. `desk/doors/commit.py` writes an approved item's rows, through a declared
action.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import uuid

from portfusion.desk.engine import RecordUnavailable, _guarded
from portfusion.desk.intake import recorded
from portfusion.desk.intake.bench_form import (CLOSED, LONG, OPEN, REGISTER, TABLES,
                                               TABLE_LABELS, _blank_refused, _id_clash,
                                               _parcel_clash, _size_clash, closed_for,
                                               evidence_classes, form_for, next_ids,
                                               validate_row, vocabulary)
from portfusion.desk.intake.bench_gates import (ADJUSTMENT_LABEL, LIMBS, WHY_FIELDS, _Filled,
                                                _filed_already, _reading_gate, _register_problems,
                                                _repeated_ids, _source_shape, _unmarked,
                                                _why_needed, adjustment_cells,
                                                already_in_the_record, approved, gates,
                                                is_adjustment, reading_of, unusual_signs, why)
from portfusion.record import schema

#: WHAT THIS MODULE OFFERS: the item's own names, then the form's and the gates', each of those
#: answered here as well as where it is defined.
__all__ = ["bench_dir", "item_for_event", "sweep_status", "new_item", "for_document", "read_here",
           "for_event", "to_bench", "Stale", "save", "get", "all_items", "discard", "paste_block",
           "recognise", "waiting_documents", "document_text",
           "TABLES", "TABLE_LABELS", "REGISTER", "CLOSED", "OPEN", "LONG", "closed_for",
           "evidence_classes", "vocabulary", "next_ids", "_blank_refused", "form_for",
           "validate_row", "_size_clash", "_parcel_clash", "_id_clash",
           "WHY_FIELDS", "ADJUSTMENT_LABEL", "LIMBS", "is_adjustment", "adjustment_cells",
           "_Filled", "_filed_already", "already_in_the_record", "unusual_signs", "_repeated_ids",
           "_register_problems", "_unmarked", "_source_shape", "gates", "reading_of",
           "_reading_gate", "why", "_why_needed", "approved"]


def bench_dir():
    """Where the items in work are kept: beside the workbench they belong to, and gitignored
    with it — a half-worked intake is not a record. The dot keeps it clear of `test_inbox.py`'s
    "the workbench is clear" check, which is about DOCUMENTS resting unfinished; an item mid-work
    is legitimate transient state. The state that IS dangerous — written but not archived — is
    asserted separately."""
    return schema.inbox() / ".bench"


def item_for_event(ref: str) -> dict | None:
    """The open bench item carrying this deal reference, if there is one.

    The lookup for_event() does before it creates anything, named so the sweep can ask it
    without creating anything.
    """
    ref = str(ref or "").strip()
    if not ref:
        return None
    for existing in all_items():
        if (existing.get("event_ref") == ref
                and existing.get("state") not in ("written", "archived")):
            return existing
    return None


def sweep_status(refs: list[str]) -> dict:
    """For each deal reference: is it already in the record, or already on the bench?

    THE SWEEP IS A SNAPSHOT AND THE WORLD MOVES UNDER IT. Its result is held client-side so that
    returning to the Bench does not mean another 30-day call to the broker — but a snapshot alone
    would go on offering "work it" for a row already carried across, or already committed.

    So the snapshot supplies the EVENTS and this supplies their STATE, asked fresh every time
    the sweep is drawn. Neither is guessed from the other.
    """
    out = {}
    for ref in refs or []:
        ref = str(ref or "").strip()
        if not ref:
            continue

        def _look(ref=ref):
            tables = recorded.reference_tables(ref)
            item = item_for_event(ref)
            return {
                "in_record": bool(tables),
                "tables": tables,
                "item": None if item is None else {
                    "id": item["id"], "state": item.get("state", "open"),
                    "blocked": [g["label"] for g in gates(item) if not g["ok"]],
                },
            }

        try:
            out[ref] = _guarded(_look)
        except RecordUnavailable as e:
            out[ref] = {"error": str(e)}
    return out


# =================================================================================================
# STORAGE. One JSON per open item, beside the workbench.
# =================================================================================================
def _path(item_id: str):
    if not re.fullmatch(r"[A-Za-z0-9-]+", item_id):
        raise ValueError(f"bad item id: {item_id!r}")
    return bench_dir() / f"{item_id}.json"


def new_item(origin: str = "manual", title: str = "", document: dict | None = None) -> dict:
    bench_dir().mkdir(parents=True, exist_ok=True)
    item = {
        "id": f"B-{_dt.date.today():%Y%m%d}-{uuid.uuid4().hex[:6]}",
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "state": "open",
        "origin": origin,
        "title": title or "untitled",
        "document": document,
        # WHICH KIND OF DOCUMENT THIS IS. Picking one fills the authority, says what its
        # reference looks like, and composes `source` in the shape the record already uses.
        "evidence_class": "",
        "evidence": {k: "" for k, _, _ in LIMBS},
        "why": {f: "" for f in WHY_FIELDS},
        "rows": [],
    }
    save(item)
    return item


def for_document(name: str, origin: str = "document") -> dict:
    """The bench item for this document — the existing one if there is one, else a new one.

    WHY THIS IS NOT JUST `new_item()`. A fresh item on every click leaves two identical empty
    items on the bench and no way to tell which one is being filled.

    OPENING A DOCUMENT IS IDEMPOTENT, which is the honest shape: one document is one piece of
    evidence and one item works it, however many rows that item ends up proposing. A committed
    or archived item does NOT block a new one — the same document legitimately comes back if a
    correction is needed, and by then the old item has left the bench anyway.
    """
    # A DOCUMENT IS ONE ON THE WORKBENCH, by its bare name. The name arrives from the browser,
    # and an item's document is what the reader opens: a path would be read wherever it points,
    # so the name is found in the workbench's own listing and never joined to a path.
    inbox = schema.inbox()
    if not name or not inbox.is_dir() \
            or name not in {p.name for p in inbox.iterdir() if p.is_file()}:
        raise FileNotFoundError(f"no document {name!r} on the workbench")
    for existing in all_items():
        doc = existing.get("document") or {}
        if doc.get("name") == name and existing.get("state") not in ("written", "archived"):
            return existing
    item = new_item(origin=origin, title=name, document={"name": name})

    # WHAT THE DOCUMENT SAYS ABOUT ITSELF, filled in. This is DERIVATION and not a proposal:
    # every value here is read out of the document's own text, the way `propose._derived()`
    # works — fill a blank from something checkable, never overwrite, and say where it came
    # from. The item carries `recognised` so the screen can show what was matched and on what.
    #
    # ONE MATCH ONLY. Two is ambiguous, and a class decides which columns mean what — guessing
    # between them would be worse than leaving both blank, because a pre-filled wrong answer is
    # the one nobody re-reads.
    from portfusion.record import rules as D
    seen = recognise(name)
    item["recognised"] = seen
    if len(seen["classes"]) == 1:
        key = seen["classes"][0]
        item["evidence_class"] = key
        item["evidence"]["authority"] = D.EVIDENCE_BY_KEY[key].authority
        if seen["instant"]:
            item["evidence"]["dated"] = seen["instant"][:10]
        if seen.get("reference"):
            item["evidence"]["reference"] = seen["reference"]
    save(item)
    # A KIND THIS MACHINE READS IS READ AT ONCE — no reader, no cost, nothing to press.
    from portfusion.desk.intake import read_rows
    if len(seen["classes"]) == 1 and seen["classes"][0] in read_rows.LOCAL:
        return read_here(item)
    return item


def read_here(item: dict) -> dict:
    """Read the item's document ON THIS MACHINE, if it is a kind `read_rows.LOCAL` reads. Returns
    the item, saved. Nothing leaves the machine and nothing is verified, because the value IS
    the cell (`desk/intake/read_rows.py`).

    A RE-READ REPLACES WHAT THE LAST READ PROPOSED AND NOTHING ELSE, as `propose.py` does: rows
    added by hand survive. The limbs are filled only where blank — a value typed is the owner's.
    """
    from portfusion.record import rules as D
    from portfusion.desk.intake import read_rows
    name = (item.get("document") or {}).get("name")
    if not name:
        raise ValueError("this item has no document to read")
    got = read_rows.read(name)
    if got["class"] not in read_rows.LOCAL:
        raise ValueError(f"{name} is not a kind of document this machine reads; a Claude "
                         f"session can: python3 -m portfusion.desk.intake.propose")
    kept = [r for r in (item.get("rows") or []) if not r.get("machine")]
    item["rows"] = kept + got["rows"]
    item["examined"] = ([s["line"] for s in got["seen"]]
                        + [next(iter(r["sources"].values()), r["table"]) for r in got["rows"]])
    item["unrecognised"] = got["unrecognised"]
    if not item.get("evidence_class"):
        item["evidence_class"] = got["class"]
    ev = D.EVIDENCE_BY_KEY[got["class"]]
    filled = {"dated": (got["instant"] or "")[:10], "authority": ev.authority,
              "reference": got["reference"]}
    for key, value in filled.items():
        if value and not str(item["evidence"].get(key, "")).strip():
            item["evidence"][key] = value
    if got["account"] and not item.get("account"):
        item["account"] = got["account"]
    # A HOLDINGS EXPORT FILES THE ACCOUNT'S READING: its units against the
    # book, and the figures `commit.py` writes through `observations.py` when it is filed.
    if "reading" in got:
        item["reading"], item["units"] = got["reading"], got.get("units") or []
    item["proposed"] = {"at": _dt.datetime.now().isoformat(timespec="seconds"), "local": True,
                        "document": name, "kind": ev.label, "seen": got["seen"],
                        "not_found": [], "dropped": [], "directives": []}
    return save(item)


def for_event(event: dict, origin: str = "ig-events", marks: list[dict] | None = None) -> dict:
    """The bench item for one IG event — the existing one if there is one, else a new one.

    ONE EVENT, ONE ITEM. The alternative was one item per sweep carrying every missing row, and
    it does not survive contact with the evidence rule: `ig-api` defines its reference as "the
    dealId the row stores", and an item has ONE reference. A sweep that found six events would
    have had to pick one dealId for all six, and one reason would have covered six unrelated
    trades — where a reason belongs to a decision.

    IDEMPOTENT ON THE DEAL ID, the same shape as for_document(). Pressing the button twice
    returns the item already open rather than a second empty copy.

    WHAT IT FILLS: the evidence, which the API genuinely supplies — the class is `ig-api`, the
    authority is the endpoint, the reference is the dealId, the date is the event's own. And
    the row, as the sweep built it.

    WHAT IT NEVER FILLS: the WHY. No API supplies it, and bench.gates() will not let the item be
    approved without one where one is owed. That is the whole reason an event goes to the bench rather
    than into the record.
    """
    ref = str(event.get("ref") or "").strip()
    if not ref:
        raise ValueError("an IG event with no deal reference cannot go to the bench — "
                         "the reference IS the evidence for an `ig-api` row")

    # THE EVENT ARRIVES FROM THE BROWSER, so it is checked rather than trusted. The sweep's
    # result is held client-side and posted back, which is the only way to avoid a second
    # broker call — and it means the shape reaching the bench is whatever was sent. A table
    # this store does not have, or a row that does not fill exactly that table's columns, is
    # refused here rather than staged and discovered at commit.
    def _shape(row, tables):
        table = row.get("table")
        if table not in tables:
            raise ValueError(f"{table!r} is not a table in this store")
        want = tuple(f.name for f in schema.TABLES[table].fields)
        got = tuple((row.get("values") or {}))
        if got != want:
            raise ValueError(f"an {table} row must fill exactly {want}, and this one has {got}")
        return True

    _guarded(lambda: _shape(event, schema.TABLES))
    # A SET-UP carries the new line, company and contract its trade stands on (`REGISTER`).
    setup = list(event.get("with") or [])
    for row in setup:
        _guarded(lambda row=row: _shape(row, REGISTER))

    existing = item_for_event(ref)
    if existing:
        return existing

    row = {"table": event["table"], "values": dict(event["values"])}
    # THE EVENT'S OWN WORDS ARE ITS TITLE, as the Trades page says it; the deal id is the
    # evidence's reference, shown with it.
    item = new_item(origin=origin, title=event.get("what") or ref)
    item["event_ref"] = ref
    item["evidence_class"] = "ig-api"
    item["evidence"] = {
        "dated": str(row["values"].get("date", "") or ""),
        # A DEAL IS IG's ACTIVITY; MONEY IS ITS LEDGER, where the sweep read each.
        "authority": "IG REST /history/" + (
            "activity" if row["table"] in ("buys", "sales") else "transactions"),
        "reference": ref,
    }
    item["rows"] = [{"table": r["table"], "values": dict(r["values"])} for r in setup] + [row]
    # A NEW CONTRACT'S FIRST MARK, read from IG on the owner's press and written with the bet.
    if marks:
        item["marks"] = [dict(m) for m in marks]
    return save(item)


def to_bench(event: dict, marks: list[dict] | None = None) -> dict:
    """Carry one swept event onto the bench (`for_event()`). Returns the item, or a refusal."""
    try:
        item = for_event(event, marks=marks)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except RecordUnavailable as e:
        return {"ok": False, "error": f"record unavailable: {e}"}
    return {"ok": True, "id": item["id"], "title": item["title"],
            "blocked": [g["label"] for g in gates(item) if not g["ok"]]}


class Stale(Exception):
    """A save made from a copy of the item older than the one on disk."""


def save(item: dict, drawn: int | None = None) -> dict:
    """Write the item, raising its `revision` by one.

    A PAGE SAYS WHICH REVISION IT DREW (`drawn`), and a save from an older one is refused with
    `Stale`. The page sends the whole item, so a page drawn before another save would write its
    old rows back over it. Every saver comes through here, so every save moves the revision. An
    item from before revisions reads as revision 0."""
    bench_dir().mkdir(parents=True, exist_ok=True)
    path = _path(item["id"])
    current = (json.loads(path.read_text(encoding="utf-8")).get("revision", 0) if path.is_file()
               else item.get("revision", 0))
    if drawn is not None and drawn != current:
        raise Stale(current)
    item["revision"] = current + 1
    # A TERMINAL STATE IS NOT RECOMPUTED. Deriving state from "does it have rows" is right
    # while an item is being worked and WRONG the moment it is committed: a written item has
    # rows, so the derivation would quietly demote it to "proposed" and offer it for writing a
    # second time. desk/doors/commit.py sets those two states deliberately, and they stand.
    if item.get("state") not in ("written", "archived"):
        item["state"] = "proposed" if item.get("rows") else "open"
    _path(item["id"]).write_text(json.dumps(item, indent=2), encoding="utf-8")
    return item


def get(item_id: str) -> dict:
    p = _path(item_id)
    if not p.is_file():
        raise KeyError(item_id)
    return json.loads(p.read_text(encoding="utf-8"))


def all_items() -> list[dict]:
    if not bench_dir().is_dir():
        return []
    items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(bench_dir().glob("*.json"))]
    return sorted(items, key=lambda i: i["created"], reverse=True)


def discard(item_id: str) -> None:
    """Remove an item from the bench. It has written nothing, so nothing is lost.

    NOT the same as deleting a document — `docs/intake.md` forbids that, and this never
    touches one. An item is a work-in-progress note about a document, not the evidence.
    """
    _path(item_id).unlink(missing_ok=True)


def paste_block(item: dict) -> list[dict]:
    """The rows as they would land in each CSV — a PREVIEW.

    `desk/doors/commit.py` writes them; this shows each line before it lands, and can be pasted by
    hand if a commit is refused.
    """
    out = []
    for row in item.get("rows") or []:
        table = row["table"]
        fields = schema.TABLES[table].fields
        cells = []
        for f in fields:
            raw = row["values"].get(f.name, "")
            try:
                v = schema.cell(f, raw)
            except ValueError:               # the gate names it; the line still shows it
                v = str(raw)
            cells.append(f'"{v}"' if ("," in v or '"' in v) else v)
        out.append({"table": table, "target": f"store/{table}.csv", "line": ",".join(cells)})
    return out


# =================================================================================================
# DOCUMENTS. ii and HL have no retail API, so their evidence arrives as a file.
# =================================================================================================
def _reader():
    """The one document extractor, `desk/intake/read_document.py`.

    ONE EXTRACTOR, and that is the point: copying twenty lines of pypdf into a second place
    would be the actual mistake, because two extractors disagree the first time one learns a new
    document kind. It also runs standalone — `python3 -m portfusion.desk.intake.read_document` — which is worth
    keeping for a document that will not parse.
    """
    from portfusion.desk.intake import read_document
    return read_document


#: Recognised in the LISTING for these only. `extract()` reads a whole file, and the bench
#: panel renders on every visit — walking every PDF in the workbench each time would be felt.
#: A PDF is still recognised when its item is created, where the cost is paid once.
_CHEAP_TO_READ = (".csv", ".tsv", ".txt")


def recognise(name: str) -> dict:
    """What this document says it IS, read from its own text.

    NEVER FROM THE FILENAME. HL exports three different reports all titled "Portfolio Summary",
    and the `-2` and `-3` that appear on disk are macOS disambiguating a download in the order
    the downloads happened. Believing them would pick the wrong column map for a whole document
    and every cell after it.

    `classes` IS A LIST AND MAY HOLD MORE THAN ONE. Two matches is an honest answer and the
    caller must ask rather than take the first — deciding what a document is decides which
    columns mean what.

    Never raises. A document that cannot be read reports `why` and is still workable by hand.
    """
    from portfusion.record import rules as D
    out = {"name": name, "classes": [], "instant": None, "instant_from": "", "reference": "",
           "encoding": None, "scanned": False, "why": ""}
    try:
        doc = _reader().extract(name)
    except Exception as e:                       # noqa: BLE001 — reported on the row, never raised
        out["why"] = str(e)
        return out
    text = doc.get("text") or ""
    # THE DOCUMENT'S OWN INSTANT, ELSE WHEN IT WAS DOWNLOADED. ii's exports state no date, and
    # the file's time is when ii produced it. `instant_from` says which.
    inst, source = D.document_instant(text), "document"
    if inst is None:
        inst, source = _reader().modified(name), "download"
    out.update(classes=D.identify(text), reference=D.document_reference(text),
               encoding=doc.get("encoding"),
               scanned=bool(doc.get("scanned")),
               instant=inst.isoformat(sep=" ", timespec="minutes") if inst else None,
               instant_from=source if inst else "")
    return out


def waiting_documents() -> list[dict]:
    """What is sitting on the intake workbench, unfinished — and what each one says it is."""
    try:
        docs = _reader().waiting()
    except Exception as e:      # noqa: BLE001 — an unreadable _inbox/ must not blank the panel
        return [{"name": f"could not read _inbox/: {e}", "bytes": 0, "error": True}]
    for d in docs:
        if str(d.get("name", "")).lower().endswith(_CHEAP_TO_READ):
            d["recognised"] = recognise(d["name"])
    return docs


def document_text(name: str) -> dict:
    """A document's text, for reading BESIDE the form rather than in another window.

    A scan comes back with `scanned` true and an empty body. That is reported, never smoothed
    over: `docs/intake.md` is explicit that a figure must not be entered from a document that
    has not been read in full, and nothing can be read from an image here.
    """
    return _reader().extract(name)

