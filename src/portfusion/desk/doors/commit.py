"""THE COMMIT — the ONLY place in `desk/` that writes an event to `store/`.

NOT AN `Action`, AND NOT A LOOPHOLE IN THE MARKS RULE. A feed may never write an event because its
only authority is an endpoint. A row committed here has the operator's: the three evidence
limbs, the reasoning and the approval, entered on the bench. This is the bench's other end.

What keeps that honest is structural:

  - ONE ENTRY POINT, AND IT TAKES AN ITEM ID. You cannot hand this module a row. It re-runs
    `bench.gates()` from scratch and refuses unless every gate is green; the stored `state` is
    never taken as evidence of approval.
  - EVERY ROW GOES THROUGH `schema`, the loader's own door. A row that would not load is not
    written.
  - THE WRITE IS VERIFIED AND ROLLED BACK. Every target's bytes are held, the rows placed and
    the table reloaded. A failed reload, a row count that moved by anything but the rows added,
    or a row that does not read back identically restores EVERY touched file and refuses.
  - THE BOOK MUST STILL LOAD, or nothing is written: `_the_book_loads()`, last in the envelope.
  - NOTHING RESTS IN `written`. The record would hold the row while its evidence sat in the
    inbox, so writing and archiving are one operation and `written` exists only in memory
    between them. `tests/test_inbox.py` fails on any item left on disk in that state.

It never deletes a row, and edits one only to move its id when an earlier-dated row takes its
place (`record/order.py`). A mistake is corrected by a further row, or by a hand edit with a
commit message saying why; `git revert` is the undo, which is why the store is tracked.
"""
from __future__ import annotations

from collections import Counter
import json
import shutil

from portfusion.desk.doors import envelope
from portfusion.desk.intake import bench, filing
from portfusion.record import order, schema

#: Where a committed item's note goes. `_archive/` is tracked, and it is the audit trail
#: behind the row: what evidence was held, what the reasoning was, and when it landed.
ARCHIVE = schema.BOOK / "_archive" / "bench"

#: States a committed item may already be in. Committing twice is refused, not ignored — an
#: event happened once, and writing it again would be a duplicate the schema cannot see.
TERMINAL = ("written", "archived")


def renumbering(rows: list[dict]) -> list[str]:
    """The ids these Bench rows would move, in words, nothing written: what the Bench's review
    shows before the press."""
    new = {}
    for row in rows:
        if row.get("table") in order.NUMBERED and (row.get("values") or {}).get("date"):
            new.setdefault(row["table"], []).append(
                envelope.rendered(row["table"], row.get("values") or {}))
    if not new:
        return []
    return order.said(_renumbered_only(new, envelope.placed(new)[1]))


def _renumbered_only(new: dict, moves: dict) -> dict:
    """`moves` without the new rows' own ids: a new row is added, and only a row already on file
    is renumbered."""
    proposed = {c[schema.TABLES[t].header.index(order.NUMBERED[t][0])]
                for t, cells in new.items() if t in order.NUMBERED for c in cells}
    return {t: kept for t, pairs in moves.items()
            if (kept := [p for p in pairs if p[0] not in proposed])}


class Refused(Exception):
    """The commit did not happen, and the store is exactly as it was."""


def _the_book_loads() -> None:
    """Build the engine from the store as it now stands, or refuse in the engine's own words.

    THE SCHEMA JUDGES A CELL; ONLY THE ENGINE KNOWS WHETHER A ROW JOINS THE REST. A sale in no
    realisation, a leg nothing closes, a share with no price: each passes `schema` and stops
    `Book()` — and with it every panel but the bench. Called inside `atomic()`, so a refusal puts
    every file back; `envelope.record_follows_the_files()` then puts the record in memory back too.
    """
    from portfusion import engine
    from portfusion.record import rules
    try:
        rules.reload_store()
        engine.Book()
    except (Exception, SystemExit) as e:
        raise Refused(f"the book would not load with this written, so nothing was — "
                      f"{type(e).__name__}: {e}") from e


def _title(item: dict) -> str:
    """The item's title as a journal `detail`, on one line. The id in `ref` retrieves the rest."""
    return " ".join(str(item.get("title") or item.get("id") or "").split())


def _reasoning_targets(item: dict) -> dict:
    """Which ticker gets which why, and the date it is filed under, from the rows themselves:
    {ticker: {"date", "why_entered"?, "why_exited"?}}.

    An item buying supplies that ticker's `why_entered`; one selling supplies its `why_exited`.
    An item doing both supplies both, and an item doing neither — a dividend, a transfer —
    supplies nothing. THE DATE IS THE TRADE'S, the latest of the rows the why is written for,
    so the why sits beside the event it explains.
    """
    said = bench.why(item)
    out: dict[str, dict] = {}
    for row in item.get("rows") or []:
        values = row.get("values") or {}
        ticker = str(values.get("ticker", "") or "").strip()
        if not ticker:
            continue
        half = {"buys": "why_entered", "sales": "why_exited"}.get(row["table"])
        if half and said.get(half, "").strip():
            target = out.setdefault(ticker, {"date": ""})
            target[half] = said[half].strip()
            target["date"] = max(target["date"], str(values.get("date", "") or "").strip())
    return out


def _write_reasoning(targets: dict) -> list[str]:
    """Append one `store/reasoning.csv` row per ticker in `targets`, and return the tickers.

    ADDED, NEVER REPLACED, as every event table is, where its date puts it. A second why on a name
    is a row of its own beside the first, so the thesis a position was opened on is still there when it is added
    to or trimmed, and the desk shows both.
    """
    envelope.place({"reasoning": [envelope.rendered("reasoning", {"ticker": ticker, **values})
                                  for ticker, values in sorted(targets.items())]})
    return sorted(targets)


def retired_by(rows: list[dict]) -> list[str]:
    """The lines these rows leave held by nothing, each with a live price to retire, sorted:
      · an IG contract, still mapped to an epic, when every leg on it is closed — already, or by
        these rows' sales naming their legs
      · a share these rows' sales leave in no account: a holding is per account, but a price is
        per ticker, so a ticker still held anywhere keeps it
    These rows' own buys count, so a line reopened in the same item stays. Read from the files,
    so it answers before a write (the Bench's review) and inside one (`commit()`) alike."""
    sales = [r.get("values") or {} for r in rows if r.get("table") == "sales"]
    buys = [r.get("values") or {} for r in rows if r.get("table") == "buys"]
    th, eh = schema.TABLES["buys"].header, schema.TABLES["sales"].header
    out = []

    named = {str(v.get("closes") or "").strip() for v in sales} - {""}
    if named:
        closed = {r[eh.index("closes")] for r in schema.load("sales")
                  if r[eh.index("closes")]} | named
        contract_of = {r[th.index("trade_id")]: r[th.index("contract")] for r in schema.load("buys")}
        contract_of.update({str(v.get("trade_id") or "").strip(): str(v.get("contract") or "").strip()
                            for v in buys if str(v.get("trade_id") or "").strip()})
        epics = {r[0]: r[1] for r in schema.load("contracts")}
        touched = {contract_of.get(leg) for leg in named} - {None, ""}
        out += [c for c in touched if epics.get(c)
                and all(leg in closed for leg, on in contract_of.items() if on == c)]

    sold = {str(v.get("ticker") or "").strip() for v in sales} - {""}
    if sold:
        sh = schema.TABLES["securities"].header
        sold &= ({r[sh.index("ticker")] for r in schema.load("securities")
                  if r[sh.index("held_as")] == "shares"}
                 & {r[0] for r in schema.load("current-prices")})
        held = dict.fromkeys(sold, 0)
        # A CORPORATE ACTION IS A BUY OF NIL COST, its quantity signed, so buys less sales is the
        # quantity held whatever the holding went through.
        for table, h, sign, mine in (("buys", th, 1, buys), ("sales", eh, -1, sales)):
            ticker, qty = h.index("ticker"), h.index("qty")
            for r in schema.load(table):
                if r[ticker] in held:
                    held[r[ticker]] += sign * (r[qty] or 0)
            for v in mine:
                t = str(v.get("ticker") or "").strip()
                if t in held:
                    held[t] += sign * int(float(str(v.get("qty") or 0).strip() or 0))
        out += [t for t, q in held.items() if q <= 0]
    return sorted(out)


@envelope.held
def commit(item_id: str) -> dict:
    """Write one approved bench item's rows into the store, then archive it.

    Returns a summary. Raises `Refused` — leaving every file untouched — if the item is
    already committed, has no rows, or fails any gate.
    """
    item = bench.get(item_id)

    if item.get("state") in TERMINAL:
        raise Refused(f"{item_id} is already {item['state']}. An event happened once; writing "
                      f"it a second time would be a duplicate the schema cannot see.")

    rows = item.get("rows") or []
    # A DOCUMENT READ IN FULL THAT YIELDS NOTHING IS STILL EVIDENCE: empty `rows` beside a
    # non-empty `examined` means every line was checked and none was new. Empty `rows` alone
    # means nothing was read, and is refused.
    if not rows and not (item.get("examined") or []):
        raise Refused(f"{item_id} proposes no rows and has read no lines — there is nothing to "
                      f"write and nothing to say it was worked.")

    failed = [g for g in bench.gates(item) if not g["ok"]]
    if failed:
        raise Refused(
            f"{item_id} is not approved. " + "; ".join(f"{g['name']}: {g['detail']}" for g in failed))

    by_table: dict[str, list[list[str]]] = {}
    for row in rows:
        by_table.setdefault(row["table"], []).append(envelope.rendered(row["table"], row["values"]))

    # Hold every target's bytes before touching any: a two-table item failing on the second
    # table must not leave the first written.
    before: dict = {}
    for table in by_table:
        path = schema.TABLES[table].path
        before[table] = (path, path.read_bytes(), schema.load(table))

    # The why shares the envelope, so no thesis can outlive a trade that failed to land.
    targets = _reasoning_targets(item)
    reasoning_path = schema.TABLES["reasoning"].path

    # One instant, decided before the write, for the journal, the archived item and the
    # summary: test_journal.py compares them.
    written_at = schema.record_instant()

    # A HOLDINGS EXPORT FILES THE ACCOUNT'S READING, and the reading's table shares the envelope.
    reading = bench.reading_of(item) if item.get("reading") is not None else None
    # A SALE THAT CLOSES A CONTRACT'S LAST LEG, OR SELLS A SHARE OUT OF EVERY ACCOUNT, RETIRES
    # ITS LIVE PRICE in the same write, through the marks door — this door still only appends
    # the event.
    from portfusion.desk.doors import marks
    retiring = retired_by(rows)
    # A NEW CONTRACT'S FIRST MARK, read from IG when its set-up was pressed (`bench.for_event`).
    marking = list(item.get("marks") or [])
    held = list(dict.fromkeys([path for path, _, _ in before.values()]
                              + envelope.paths_placing(by_table)
                              + ([reasoning_path] if targets else [])
                              + (_observations_paths() if reading else [])
                              + (marks.retire_paths() if retiring else [])
                              + (marks.first_paths() if marking else [])
                              + [schema.TABLES["journal"].path]))
    with envelope.record_follows_the_files(), envelope.atomic(*held):
        # EACH ROW IN ITS PLACE (`envelope.place()`).
        try:
            moved, rewritten = envelope.place(by_table)
        except ValueError as e:
            raise Refused(f"nothing was written — {e}") from e
        final = {was: now for pairs in moved.values() for was, now in pairs}
        moved = _renumbered_only(by_table, moved)
        for table, cells in by_table.items():
            cells[:] = [order.followed(table, schema.TABLES[table].header, row, final)
                        for row in cells]

        # VERIFY BY READING IT BACK, through the loader the build uses.
        for table, cells in by_table.items():
            _, _, was = before[table]
            loaded = schema.load(table)
            if len(loaded) != len(was) + len(cells):
                raise Refused(f"{table}.csv went from {len(was)} to {len(loaded)} rows, expected "
                              f"{len(was) + len(cells)}")
            fields = schema.TABLES[table].fields
            # Compared as VALUES: "3197.00" reads back as 3197.0. Still catches a cell in the
            # wrong column, a row split by an unquoted comma, a lost field. WHAT WAS ADDED, row
            # for row, where no id moved; where one did, each row by its id, which is unique.
            expect = Counter(tuple(schema._parse(f, c, table, 0) for f, c in zip(fields, wrote))
                             for wrote in cells)
            got = Counter(loaded) if table in moved or table in rewritten else (
                Counter(loaded) - Counter(was))
            if expect - got:
                raise Refused(f"{table}.csv row did not read back as written:\n"
                              f"  wrote {sorted(expect - got)}")
        # AFTER the events and their read-back, so the why never outlives a refused row.
        reasoned = _write_reasoning(targets) if targets else []
        if targets:
            schema.load("reasoning")        # it must still load, like everything else here

        # The journal shares the envelope, so an item cannot reach the record without
        # reaching the journal. `ref` is the item id, which retrieves its archived evidence.
        entries = ([("bench", "append", table, len(cells), item["id"], _title(item))
                    for table, cells in sorted(by_table.items())]
                   + [("bench", "replace", table, n, item["id"],
                       "; ".join(order.said({table: moved.get(table)})
                                 or ["followed the renumbered rows it names"]))
                      for table, n in sorted(rewritten.items())]
                   + ([("bench", "append", "reasoning", len(reasoned), item["id"],
                        "why for " + ", ".join(reasoned))] if reasoned else []))
        if entries:
            envelope.journal(entries, at=written_at)
        # THE MARKS DOOR'S REFUSAL IS THIS COMMIT'S, so the route answers it with a 409.
        try:
            retired = marks.retire(retiring, "bench", item["id"], written_at) if retiring else []
        except marks.Refused as e:
            raise Refused(f"the live price could not be retired, so nothing was written — {e}") from e
        try:
            marked = marks.first(marking, "bench", item["id"], written_at) if marking else []
        except marks.Refused as e:
            raise Refused(f"the contract could not be marked, so nothing was written — {e}") from e

        # FILED, THEN THE READING, AND BOTH OR NEITHER. The readings door checks the document is in
        # _archive/statements/, so it is moved first; if the reading is refused it goes back to the
        # workbench and every file above is restored. AN ITEM WITH NO READING FILES ITS DOCUMENT
        # HERE TOO, inside the envelope, so rows never land without the document they cite.
        document = _file_with_reading(item, reading) if reading else _archive_document(item)

        # LAST, AND INSIDE THE ENVELOPE: the book must still load with all of this written.
        # `atomic()` puts the CSVs back on a refusal and knows nothing of a moved document.
        try:
            _the_book_loads()
        except Exception:
            _unfile(item, document)
            raise

    # THE ARCHIVED ITEM NAMES ITS ROWS AS THEY WERE WRITTEN, by the ids they took.
    ids = {}
    for row in rows:
        values = row.get("values") or {}
        for k in ("trade_id", "sale_id", "closes"):
            if values.get(k):
                if k != "closes":
                    ids[values[k]] = final.get(values[k], values[k])
                values[k] = final.get(values[k], values[k])
    if moved:
        item["renumbered"] = {t: order.said({t: p}) for t, p in moved.items()}
    item["state"] = "written"
    item["written_at"] = written_at
    item["written_to"] = {t: len(c) for t, c in by_table.items()}
    if retired:
        item["retired"] = retired
    if marked:
        item["marked"] = marked
    if targets:
        item["reasoning_written"] = targets

    # Archive at once: nothing may rest in `written` (the module docstring says why).
    item["state"] = "archived"
    if document:
        item["document_archived_to"] = filing.filed_as(document)

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (ARCHIVE / f"{item['id']}.json").write_text(json.dumps(item, indent=2), encoding="utf-8")
    bench.discard(item["id"])

    return {"id": item["id"], "written": item["written_to"], "written_at": written_at,
            "ids": ids,
            "renumbered": {was: now for pairs in moved.values() for was, now in pairs},
            "document": item.get("document_archived_to"),
            "reading": item.get("reading_written"),
            "reasoning": sorted(targets),
            "retired": retired,
            "marked": marked,
            "archived_to": filing.filed_as(ARCHIVE / f"{item['id']}.json")}


def _observations_paths() -> list:
    """What writing a reading touches — its table and its banked history — held with the rest."""
    from portfusion.desk.doors import observations
    return [p for p in observations.paths() if p.name != "journal.csv"]


def _file_with_reading(item: dict, reading: dict):
    """File the item's document, then write the account's reading through `observations.py`.
    A refusal puts the document back on the workbench and raises, inside the caller's
    envelope, so nothing is left filed without its reading."""
    from portfusion.desk.doors import observations
    document = _archive_document(item)
    try:
        observations.write([reading])
    except Exception as e:
        _unfile(item, document)
        raise Refused(f"the reading was not written, so the document was not filed — {e}") from e
    item["reading_written"] = reading["account"]
    return document


def _unfile(item: dict, document) -> None:
    """Put a document `_archive_document()` filed back on the workbench, if it filed one."""
    if document:
        shutil.move(str(document), str(filing.document_on_the_bench(item)))


def _archive_document(item: dict):
    """Move the item's document from `_inbox/` into `_archive/statements/`, if it has one.

    An item need not: a spread bet is evidenced by the IG deal reference its row carries.
    `bench.gates()` checks the three limbs either way.

    A DOCUMENT NAMED AND NOT THERE IS REFUSED, never passed over. Called inside the write's
    envelope, so the refusal takes every row back out: rows citing a document that was never
    filed are what the door exists to stop.
    """
    source = filing.document_on_the_bench(item)
    if source is None:
        return None
    if not source.is_file():
        raise Refused(f"{source.name} is not on the workbench, so it cannot be filed, and no row "
                      f"may cite a document that was never filed. Nothing was written.")
    name = source.name
    schema.STATEMENTS.mkdir(parents=True, exist_ok=True)
    target = schema.STATEMENTS / filing.archive_name(item, name)
    if target.exists():
        stem, suffix = target.stem, target.suffix
        target = schema.STATEMENTS / f"{stem}-{item['id']}{suffix}"
    shutil.move(str(source), str(target))
    return target
