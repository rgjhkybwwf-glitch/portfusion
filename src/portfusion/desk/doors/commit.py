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
  - THE WRITE IS VERIFIED AND ROLLED BACK. Every target's bytes are held, the rows appended and
    the table reloaded. A failed reload, a row count that moved by anything but the rows added,
    or a row that does not read back identically restores EVERY touched file and refuses.
  - THE BOOK MUST STILL LOAD, or nothing is written: `_the_book_loads()`, last in the envelope.
  - NOTHING RESTS IN `written`. The record would hold the row while its evidence sat in the
    inbox, so writing and archiving are one operation and `written` exists only in memory
    between them. `tests/test_inbox.py` fails on any item left on disk in that state.

It never edits or deletes a row. A mistake is corrected by a further row, or by a hand edit
with a commit message saying why; `git revert` is the undo, which is why the store is tracked.
"""
from __future__ import annotations

import contextlib
import csv
import datetime as _dt
import functools
import io
import json
import pathlib
import re
import shutil

from portfusion.desk.intake import bench
from portfusion.record import schema

#: The book this door writes to (`schema.BOOK`): its inbox, its archive.
BOOK = schema.BOOK

#: Where a committed item's note goes. `_archive/` is tracked, and it is the audit trail
#: behind the row: what evidence was held, what the reasoning was, and when it landed.
ARCHIVE = BOOK / "_archive" / "bench"

#: States a committed item may already be in. Committing twice is refused, not ignored — an
#: event happened once, and writing it again would be a duplicate the schema cannot see.
TERMINAL = ("written", "archived")


@contextlib.contextmanager
def atomic(*paths: pathlib.Path):
    """Hold these files' bytes, and restore EVERY one of them if the block raises.

    Both store doors use it: `commit()` for an append, `marks.py` for a replace.

    IT LIVES HERE, NOT IN A MODULE OF ITS OWN, FOR THE GUARD'S SAKE. The scan in
    `tests/desk/test_boundaries.py` finds store writes by resolving each write's target back to
    its assignment, and a path passed in as a parameter cannot be resolved. Moved elsewhere,
    this would still write store files and no longer be seen to.

    A file that did not exist when held is REMOVED on rollback. A file whose bytes did not
    change is NOT rewritten: restoring identical bytes still moves the mtime, and the desk's
    freshness line would then report a store change that never happened.

    THE BYTES ARE HELD UNDER `schema.LOCK`, for the whole block. A restore puts back what was read
    on entry, so a second write landing in between would have been erased by the first one's
    refusal.
    """
    with schema.LOCK:
        held = [(p, p.read_bytes() if p.is_file() else None) for p in paths]
        try:
            yield
        except Exception:
            for path, original in held:
                if original is None:
                    path.unlink(missing_ok=True)
                elif not path.is_file() or path.read_bytes() != original:
                    path.write_bytes(original)
            raise


def held(door):
    """A door's entry point, run under `schema.LOCK` from its first read to its last write.

    `atomic()` alone holds the files, not the reads that decided what to write: a check that an
    item is not already committed, or that the outgoing marks are banked, would otherwise be
    answered before another request's write and acted on after it.
    """
    @functools.wraps(door)
    def under_the_lock(*args, **kwargs):
        with schema.LOCK:
            return door(*args, **kwargs)
    return under_the_lock


def journal(rows: list[tuple], at: str | None = None) -> int:
    """Append these writes to `store/journal.csv`. Returns how many rows were added.

    Each `rows` entry is `(route, op, table, count, ref, detail)`: who wrote, what it did to the
    row count, which table, how much moved, what retrieves it, and what happened in a sentence.
    The caller states `route` and `op`, because only the caller knows them.

    It lives here for the reason `atomic()` does. It is not wrapped in its own `atomic()`:
    every caller is already inside one that holds this file, and a second envelope would
    disagree with the first about which bytes were the original.
    """
    from portfusion.record import schema
    at = at or schema.record_instant()
    path = schema.TABLES["journal"].path
    lines = [_csv_line([at, route, op, table, str(count), ref or "", detail or ""])
             for route, op, table, count, ref, detail in rows]
    _append(path, path.read_bytes() if path.is_file() else b"", lines)
    schema.load("journal")        # it must still load, like everything else written here
    return len(lines)


def _eol(original: bytes) -> bytes:
    """The line ending most of a file's lines already use. The store is LF; a write that changed a
    file's ending would show as every line changed."""
    crlf = original.count(b"\r\n")
    return b"\r\n" if crlf > original.count(b"\n") - crlf else b"\n"


def lines_and_eol(path: pathlib.Path) -> tuple[list[str], str]:
    """A file's lines and its own line ending, for a door that rewrites the file whole and must
    write it back in the ending it found: `write_text(eol.join(lines) + eol, newline="")`."""
    original = path.read_bytes()
    return original.decode("utf-8").splitlines(), _eol(original).decode()


def _append(path: pathlib.Path, original: bytes, lines: list[str]) -> None:
    """Write `lines` after `original`, in the file's own line ending. BYTES, not text: text mode
    reads CRLF as LF, and the next write would rewrite every line of the file."""
    eol = _eol(original)
    head = original if not original or original.endswith(b"\n") else original + eol
    path.write_bytes(head + b"".join(line.encode("utf-8") + eol for line in lines))


class Refused(Exception):
    """The commit did not happen, and the store is exactly as it was."""


def _the_book_loads() -> None:
    """Build the engine from the store as it now stands, or refuse in the engine's own words.

    THE SCHEMA JUDGES A CELL; ONLY THE ENGINE KNOWS WHETHER A ROW JOINS THE REST. A sale in no
    realisation, a leg nothing closes, a share with no price: each passes `schema` and stops
    `Book()` — and with it every panel but the bench. Called inside `atomic()`, so a refusal puts
    every file back; `_record_follows_the_files()` then puts the record in memory back too.
    """
    from portfusion import engine
    from portfusion.record import rules
    try:
        rules.reload_store()
        engine.Book()
    except (Exception, SystemExit) as e:
        raise Refused(f"the book would not load with this written, so nothing was — "
                      f"{type(e).__name__}: {e}") from e


@contextlib.contextmanager
def _record_follows_the_files():
    """Outside `atomic()`: once it has restored the files after a refusal or a fault, reload the
    record in memory from them, since a reload inside the envelope left it reading the rows just
    taken back out. Every door that reloads inside its envelope wears this.

    A reload that fails here means the store did not load BEFORE this write either — the desk
    reports that on its own, and the refusal is still the answer to this write.
    """
    try:
        yield
    except Exception:
        from portfusion.record import rules
        with contextlib.suppress(Exception):
            rules.reload_store()
        raise


def _shown(path) -> str:
    """A path relative to the project when it is inside it — the tests point ARCHIVE
    elsewhere, where an unconditional relative_to() would raise."""
    try:
        return str(path.relative_to(BOOK))
    except ValueError:
        return str(path)


def _rendered(table: str, values: dict) -> list[str]:
    """One row as cells, in schema field order. Blank for a null, which is what the loader
    reads back as None — a missing number is a GAP and never zero.

    A KEY THE TABLE HAS NO COLUMN FOR IS REFUSED, never dropped. Dropped, a column renamed in the
    schema but not in a writer is written blank with nothing said: a test row keyed `basis` wrote
    an empty `evidence` for three weeks after the 7 Sep 2026 rename. Raises ValueError."""
    from portfusion.record import schema
    stray = set(values) - {f.name for f in schema.TABLES[table].fields}
    if stray:
        raise ValueError(f"{table} has no column {sorted(stray)}: a writer is using a name the "
                         f"schema does not")
    out = []
    for f in schema.TABLES[table].fields:
        v = values.get(f.name)
        out.append("" if v is None else str(v))
    return out


def _csv_line(cells: list[str]) -> str:
    """Quoted the way `csv` itself would, so a note containing a comma cannot split a row."""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(cells)
    return buf.getvalue()


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
        half = {"trades": "why_entered", "exits": "why_exited"}.get(row["table"])
        if half and said.get(half, "").strip():
            target = out.setdefault(ticker, {"date": ""})
            target[half] = said[half].strip()
            target["date"] = max(target["date"], str(values.get("date", "") or "").strip())
    return out


def _write_reasoning(targets: dict) -> list[str]:
    """Append one `store/reasoning.csv` row per ticker in `targets`, and return the tickers.

    APPENDED, NEVER REPLACED, as every event table is. A second why on a name is a row of its
    own beside the first, so the thesis a position was opened on is still there when it is added
    to or trimmed, and the desk shows both.
    """
    from portfusion.record import schema
    path = schema.TABLES["reasoning"].path
    original = path.read_bytes()
    _append(path, original, [_csv_line(_rendered("reasoning", {"ticker": ticker, **values}))
                             for ticker, values in sorted(targets.items())])
    return sorted(targets)


def contracts_closed_by(rows: list[dict]) -> list[str]:
    """The IG contracts these rows leave with no open leg: each sale's leg's contract, still
    mapped to an epic, when every leg on it is closed — already, or by these rows. Read from the
    files, so it answers before a write (the Bench's review) and inside one (`commit()`) alike."""
    from portfusion.record import schema
    th, eh = schema.TABLES["trades"].header, schema.TABLES["exits"].header
    named = {str((r.get("values") or {}).get("closes") or "").strip()
             for r in rows if r.get("table") == "exits"} - {""}
    if not named:
        return []
    closed = {r[eh.index("closes")] for r in schema.load("exits") if r[eh.index("closes")]} | named
    contract_of = {r[th.index("id")]: r[th.index("contract")] for r in schema.load("trades")}
    # THESE ROWS' OWN LEGS COUNT: a close and a reopen on one contract in one item left the new
    # leg out, so the contract was retired under it and the book would not load with the item
    # written (the review of 21 Oct 2026).
    contract_of.update({str(v.get("id") or "").strip(): str(v.get("contract") or "").strip()
                        for r in rows if r.get("table") == "trades"
                        for v in [r.get("values") or {}] if str(v.get("id") or "").strip()})
    epics = {r[0]: r[1] for r in schema.load("contracts")}
    touched = {contract_of.get(leg) for leg in named} - {None, ""}
    return sorted(c for c in touched if epics.get(c)
                  and all(leg in closed for leg, on in contract_of.items() if on == c))


@held
def commit(item_id: str) -> dict:
    """Write one approved bench item's rows into the store, then archive it.

    Returns a summary. Raises `Refused` — leaving every file untouched — if the item is
    already committed, has no rows, or fails any gate.
    """
    from portfusion.record import schema

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
        by_table.setdefault(row["table"], []).append(_rendered(row["table"], row["values"]))

    # Hold every target's bytes before touching any: a two-table item failing on the second
    # table must not leave the first written.
    before: dict = {}
    for table in by_table:
        path = schema.TABLES[table].path
        before[table] = (path, path.read_bytes(), len(schema.load(table)))

    # The why shares the envelope, so no thesis can outlive a trade that failed to land.
    targets = _reasoning_targets(item)
    reasoning_path = schema.TABLES["reasoning"].path

    # One instant, decided before the write, for the journal, the archived item and the
    # summary: test_journal.py compares them.
    written_at = schema.record_instant()

    # A HOLDINGS EXPORT FILES THE ACCOUNT'S READING, and the reading's table shares the envelope.
    reading = bench.reading_of(item) if item.get("reading") is not None else None
    # A SALE THAT CLOSES A CONTRACT'S LAST LEG RETIRES ITS LIVE PRICE in the same write, through
    # the marks door — this door still only appends the event.
    from portfusion.desk.doors import marks
    retiring = contracts_closed_by(rows)
    held = list(dict.fromkeys([path for path, _, _ in before.values()]
                              + ([reasoning_path] if targets else [])
                              + (_observations_paths() if reading else [])
                              + (marks.retire_paths() if retiring else [])
                              + [schema.TABLES["journal"].path]))
    with _record_follows_the_files(), atomic(*held):
        for table, cells in by_table.items():
            path, original, _ = before[table]
            _append(path, original, [_csv_line(c) for c in cells])

        # VERIFY BY READING IT BACK, through the loader the build uses.
        for table, cells in by_table.items():
            _, _, was = before[table]
            loaded = schema.load(table)
            if len(loaded) != was + len(cells):
                raise Refused(f"{table}.csv went from {was} to {len(loaded)} rows, expected "
                              f"{was + len(cells)}")
            fields = schema.TABLES[table].fields
            for wrote, back in zip(cells, loaded[-len(cells):]):
                # Compared as VALUES: "3197.00" reads back as 3197.0. Still catches a cell in
                # the wrong column, a row split by an unquoted comma, a lost field.
                expect = tuple(schema._parse(f, c, table, 0) for f, c in zip(fields, wrote))
                if tuple(back) != expect:
                    raise Refused(f"{table}.csv row did not read back as written:\n"
                                  f"  wrote {expect}\n  read  {tuple(back)}")
        # AFTER the events and their read-back, so the why never outlives a refused row.
        reasoned = _write_reasoning(targets) if targets else []
        if targets:
            schema.load("reasoning")        # it must still load, like everything else here

        # The journal shares the envelope, so an item cannot reach the record without
        # reaching the journal. `ref` is the item id, which retrieves its archived evidence.
        entries = ([("bench", "append", table, len(cells), item["id"], _title(item))
                    for table, cells in sorted(by_table.items())]
                   + ([("bench", "append", "reasoning", len(reasoned), item["id"],
                        "why for " + ", ".join(reasoned))] if reasoned else []))
        if entries:
            journal(entries, at=written_at)
        # THE MARKS DOOR'S REFUSAL IS THIS COMMIT'S: raised as its own class, it went past the
        # route's 409 and answered a bare 500, the envelope having put every file back.
        try:
            retired = marks.retire(retiring, "bench", item["id"], written_at) if retiring else []
        except marks.Refused as e:
            raise Refused(f"the contract could not be retired, so nothing was written — {e}") from e

        # FILED, THEN THE READING, AND BOTH OR NEITHER. The readings door checks the document is
        # in _archive/statements/, so it is moved first; if the reading is refused it goes back
        # to the workbench and every file above is restored. AN ITEM WITH NO READING FILES ITS
        # DOCUMENT HERE TOO, inside the envelope, so rows never land without the document they
        # cite: until 14 Oct 2026 it was filed after the write, and a missing file was skipped.
        document = _file_with_reading(item, reading) if reading else _archive_document(item)

        # LAST, AND INSIDE THE ENVELOPE: the book must still load with all of this written.
        # `atomic()` puts the CSVs back on a refusal and knows nothing of a moved document.
        try:
            _the_book_loads()
        except Exception:
            _unfile(item, document)
            raise

    item["state"] = "written"
    item["written_at"] = written_at
    item["written_to"] = {t: len(c) for t, c in by_table.items()}
    if retired:
        item["retired"] = retired
    if targets:
        item["reasoning_written"] = targets

    # Archive at once: nothing may rest in `written` (the module docstring says why).
    item["state"] = "archived"
    if document:
        item["document_archived_to"] = _shown(document)

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (ARCHIVE / f"{item['id']}.json").write_text(json.dumps(item, indent=2), encoding="utf-8")
    bench.discard(item["id"])

    return {"id": item["id"], "written": item["written_to"], "written_at": written_at,
            "document": item.get("document_archived_to"),
            "reading": item.get("reading_written"),
            "reasoning": sorted(targets),
            "retired": retired,
            "archived_to": _shown(ARCHIVE / f"{item['id']}.json")}


#: How `_archive/statements/` names a document is `rules.ARCHIVE_CONVENTION`, whose parts are
#: the three evidence limbs — so the name is derived from the evidence, never typed, and a
#: document filed by the desk reads like one filed by hand.
_DATE_FORMATS = ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y", "%d %b %y")


def _archive_date(raw: str):
    """The document's date, however it was typed; None if it will not parse, and then the
    document keeps its original filename. Never guessed: this folder's job is retrieval."""
    text = str(raw or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _covers(item: dict) -> str:
    """What the document covers, from the rows: tickers and accounts. Factual, never
    editorial — a hand-filed "(PENR trim 3)" knows which trim it was; nothing here can."""
    rows = item.get("rows") or []
    tickers, accounts = [], []
    for row in rows:
        v = row.get("values") or {}
        for key in ("ticker",):
            if v.get(key) and v[key] not in tickers:
                tickers.append(str(v[key]))
        if v.get("account") and v["account"] not in accounts:
            accounts.append(str(v["account"]))
    # A document that yields no rows still covers an account, and says whose.
    #
    # ACCOUNT FIRST WHEN THE REFERENCE IS ONLY A DATE. A contract note number is unique across
    # every account, so tickers can lead. A date range is not: two accounts' GBP ledgers over
    # the same dates are identical files, and the account is the whole identification.
    from portfusion.record import rules as D
    ev = D.EVIDENCE_BY_KEY.get(item.get("evidence_class") or "")
    account_first = ev is not None and ev.key in D.REFERENCE_IS_A_DATE
    first, second = (accounts, tickers) if account_first else (tickers, accounts)
    parts = first or second or ([item["account"]] if item.get("account") else [])
    return ", ".join(parts)


def _document_stamp(original: str, when) -> str:
    """`HH.MM` from the document's own "as at" line, or "". Never raises: a document that
    cannot be read is still filed, and the time is provenance, not something filing needs."""
    from portfusion.record import rules as D
    from portfusion.desk.intake import read_document
    src = BOOK / "_inbox" / original
    if not src.is_file():
        return ""
    try:
        inst = D.document_instant(read_document.extract(str(src)).get("text") or "")
    except Exception:                     # noqa: BLE001 — a name is worth more than a stamp
        return ""
    return f"{inst:%H.%M}" if inst and inst.date() == when else ""


def _instant_in(reference: str, when) -> tuple[str, str]:
    """(`HH.MM`, the reference without it) where the reference states an instant on `when`'s
    day, else ("", the reference unchanged).

    THE INSTANT IS NAMED ONCE. A download is referenced by the instant it was pulled, and the
    name already leads with the date and the time, so repeating them in the reference wrote
    both twice in two spellings. A period that ENDS on that day keeps its date, because there
    the date is the period's, not the pull's.
    """
    m = re.search(rf"\b0?{when.day} {when:%b} {when.year}[ ,]+([01]\d|2[0-3])[:.\-]([0-5]\d)\b",
                  reference)
    if not m:
        return "", reference
    before, after = reference[:m.start()], reference[m.end():]
    if re.search(r"(\bto|-)\s*$", before):
        before += f"{when.day} {when:%b} {when.year}"
    return f"{m.group(1)}.{m.group(2)}", " ".join(f"{before}{after}".strip(" ,;-").split())


def _archive_name(item: dict, original: str) -> str:
    """The filename this document should be filed under. Falls back to what it arrived as."""
    evidence = item.get("evidence") or {}
    when = _archive_date(evidence.get("dated"))
    authority = " ".join(str(evidence.get("authority") or "").split())
    if not when or not authority:
        return original

    # THE DOCUMENT'S OWN TIME, when it states one: a valuation moves within the day, and
    # several exports can share a date and a title. Only when it falls on the `dated` limb's
    # day — a time from one document spliced onto another's date would invent a third instant.
    stamp = _document_stamp(original, when)
    suffix = pathlib.Path(original).suffix
    reference = " ".join(str(evidence.get("reference") or "").split())
    typed, rest = _instant_in(reference, when)
    if typed and (not stamp or typed == stamp):     # the same instant: name it once
        stamp, reference = typed, rest
    bits = [f"{when:%d %b %Y}"] + ([stamp] if stamp else []) + [authority]
    if reference and reference.lower() not in authority.lower():
        bits.append(reference)
    name = " ".join(b for b in bits if b)
    covers = _covers(item)
    if covers:
        name += f" ({covers})"
    # A filename, so nothing that would make it one path segment too many.
    name = re.sub(r"[/\\:]", "-", name).strip()
    return f"{name}{suffix}"


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
        shutil.move(str(document), str(BOOK / "_inbox" / item["document"]["name"]))


def document_on_the_bench(item: dict) -> pathlib.Path | None:
    """Where the item's document waits to be filed — on the workbench, `_inbox/` — or None if
    it names none. The gate asks here and the filing reads here, so the two cannot disagree."""
    name = (item.get("document") or {}).get("name")
    return BOOK / "_inbox" / name if name else None


def _archive_document(item: dict):
    """Move the item's document from `_inbox/` into `_archive/statements/`, if it has one.

    An item need not: a spread bet is evidenced by the IG deal reference its row carries.
    `bench.gates()` checks the three limbs either way.

    A DOCUMENT NAMED AND NOT THERE IS REFUSED, never passed over. Called inside the write's
    envelope, so the refusal takes every row back out: rows citing a document that was never
    filed are what the door exists to stop.
    """
    source = document_on_the_bench(item)
    if source is None:
        return None
    if not source.is_file():
        raise Refused(f"{source.name} is not on the workbench, so it cannot be filed, and no row "
                      f"may cite a document that was never filed. Nothing was written.")
    name = source.name
    schema.STATEMENTS.mkdir(parents=True, exist_ok=True)
    target = schema.STATEMENTS / _archive_name(item, name)
    if target.exists():
        stem, suffix = target.stem, target.suffix
        target = schema.STATEMENTS / f"{stem}-{item['id']}{suffix}"
    shutil.move(str(source), str(target))
    return target
