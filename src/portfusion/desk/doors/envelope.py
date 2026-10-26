"""THE ENVELOPE — what every store door writes through: the held bytes put back when a write fails
(`atomic()`), the lock (`held()`), the journal, a row placed where its date puts it (`place()`), a
table rewritten row by row (`rewrite()`), and a row's cells as the schema writes them.

A DOOR OF ITS OWN, declared as one in `tests/desk/test_boundaries.py`: `atomic()` writes back what
a door held, a path the scan cannot resolve, so the declaration is what says so.
"""
from __future__ import annotations

import contextlib
import csv
import functools
import io
import pathlib
import re

from portfusion.record import order, schema


@contextlib.contextmanager
def atomic(*paths: pathlib.Path):
    """Hold these files' bytes, and restore EVERY one of them if the block raises. Every store
    door writes inside it.

    A file that did not exist when held is REMOVED on rollback. A file whose bytes did not
    change is NOT rewritten: restoring identical bytes still moves the mtime, and the desk's
    freshness line would then report a store change that never happened.

    THE BYTES ARE HELD UNDER `schema.LOCK`, for the whole block. A restore puts back what was read
    on entry, so a second write landing in between would have been erased by the first one's
    refusal.

    WHATEVER ENDS THE BLOCK, `SystemExit` included, which the record raises when a store goes
    incomplete and which `except Exception` lets past.
    """
    with schema.LOCK:
        held = [(p, p.read_bytes() if p.is_file() else None) for p in paths]
        try:
            yield
        except BaseException:
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

    It is not wrapped in its own `atomic()`: every caller is already inside one that holds this
    file, and a second envelope would disagree with the first about which bytes were the original.
    """
    at = at or schema.record_instant()
    path = schema.TABLES["journal"].path
    lines = [csv_line([at, route, op, table, str(count), ref or "", detail or ""])
             for route, op, table, count, ref, detail in rows]
    append_lines(path, path.read_bytes() if path.is_file() else b"", lines)
    schema.load("journal")        # it must still load, like everything else written here
    return len(lines)


def line_ending(original: bytes) -> bytes:
    """The line ending most of a file's lines already use. The store is LF; a write that changed a
    file's ending would show as every line changed."""
    crlf = original.count(b"\r\n")
    return b"\r\n" if crlf > original.count(b"\n") - crlf else b"\n"


def append_lines(path: pathlib.Path, original: bytes, lines: list[str]) -> None:
    """Write `lines` after `original`, in the file's own line ending. BYTES, not text: text mode
    reads CRLF as LF, and the next write would rewrite every line of the file."""
    eol = line_ending(original)
    head = original if not original or original.endswith(b"\n") else original + eol
    path.write_bytes(head + b"".join(line.encode("utf-8") + eol for line in lines))


def rewrite(path: pathlib.Path, row_fn) -> None:
    """A table rewritten row by row: `row_fn(cells)` returns `cells` itself to keep the row,
    other cells to replace it, or None to take it out. A row kept, the header and a blank line
    pass through as the bytes they were read as, each line in its own ending; a replaced row is
    written by the CSV writer, so a cell holding a comma cannot split it."""
    out = []
    for i, line in enumerate(re.findall(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+$",
                                        path.read_bytes().decode("utf-8"))):
        body = line.rstrip("\r\n")
        if i == 0 or not body.strip():
            out.append(line)
            continue
        cells = next(csv.reader([body]))
        new = row_fn(cells)
        if new is not None:
            out.append(line if new is cells else csv_line(new) + line[len(body):])
    path.write_bytes("".join(out).encode("utf-8"))


def paths_placing(tables) -> list[pathlib.Path]:
    """What `place()` may write for these tables: them, and both of the buys and sales when
    either is among them, since a new buy renumbers what follows it in both."""
    names = set(tables)
    if names & set(order.NUMBERED):
        names |= set(order.NUMBERED)
    return [schema.TABLES[t].path for t in sorted(names)]


def place(new: dict[str, list[list[str]]]) -> tuple[dict, dict]:
    """Write each table's `new` rows (rendered cells) into their places, renumbering as
    `record/order.py` says. A table with no date order takes them at its end. Returns the ids
    that moved, `{table: [(was, now)]}` (a new row's `was` is the id it was proposed with), and
    how many rows already on file each table had rewritten, `{table: n}`.

    Inside the caller's `atomic()`, which holds `paths_placing()`. An untouched line keeps its
    bytes, and the file its own line ending."""
    files, moves, rewritten = placed(new)
    for path, data in files.items():
        if data != path.read_bytes():
            path.write_bytes(data)
    return moves, rewritten


def placed(new: dict[str, list[list[str]]]):
    """`place()`'s answer, nothing written: `({path: bytes}, moves, rewritten)`, each file as it
    would be. A door that writes for itself writes these bytes. Raises ValueError on a file with
    a cell that spans lines, which is moved by hand."""
    from portfusion.record import rules
    accounts = list(rules.ACCOUNT_ORDER) + [c[0] for c in new.get("accounts", [])]
    files = {}
    for path in paths_placing(new):
        table = path.stem
        original = path.read_bytes()
        text = original.decode("utf-8")
        lines = text.splitlines()
        kept = [ln for ln in lines[1:] if ln.strip()]
        rows = list(csv.reader(io.StringIO(text)))[1:]
        rows = [r for r in rows if r]
        if len(rows) != len(kept):
            raise ValueError(f"{path.name} holds a cell that spans lines: move it by hand")
        line_of = {id(r): line for r, line in zip(rows, kept)}
        header = schema.TABLES[table].header
        rows = (order.placed(table, header, rows, new.get(table, []), accounts)
                if table in order.DATED else rows + new.get(table, []))
        files[table] = [path, original, lines[0] if lines else "", rows, line_of]
    moves: dict[str, list] = {}
    if set(order.NUMBERED) <= set(files):
        files["buys"][3], files["sales"][3], moves = order.renumbered(
            (schema.TABLES["buys"].header, files["buys"][3]),
            (schema.TABLES["sales"].header, files["sales"][3]))
    out, rewritten = {}, {}
    for table, (path, original, head, rows, line_of) in files.items():
        eol = line_ending(original).decode()
        out[path] = (eol.join([head] + [line_of.get(id(r)) or csv_line(r) for r in rows])
                     + eol).encode("utf-8")
        # EVERY ROW NOT ITS OLD LINE, less the new ones: rows on file a renumbering rewrote.
        if n := sum(1 for r in rows if id(r) not in line_of) - len(new.get(table, [])):
            rewritten[table] = n
    return out, {t: m for t, m in moves.items() if m}, rewritten


@contextlib.contextmanager
def record_follows_the_files():
    """Outside `atomic()`: once it has restored the files after a refusal or a fault, reload the
    record in memory from them, since a reload inside the envelope left it reading the rows just
    taken back out. Every door that reloads inside its envelope wears this.

    A reload that fails here means the store did not load BEFORE this write either — the desk
    reports that on its own, and the refusal is still the answer to this write: the record's own
    exit, an incomplete store, is suppressed with the rest.
    """
    try:
        yield
    except BaseException:                       # as `atomic()`: an exit too
        from portfusion.record import rules
        with contextlib.suppress(Exception, SystemExit):
            rules.reload_store()
        raise


def rendered(table: str, values: dict) -> list[str]:
    """One row as cells, in schema field order, each as `schema.cell()` writes it: a figure to its
    places. Blank for a null, which is what the loader reads back as None — a missing number is a
    GAP and never zero.

    A KEY THE TABLE HAS NO COLUMN FOR IS REFUSED, never dropped. Dropped, a column renamed in the
    schema but not in a writer is written blank with nothing said. Raises ValueError."""
    stray = set(values) - {f.name for f in schema.TABLES[table].fields}
    if stray:
        raise ValueError(f"{table} has no column {sorted(stray)}: a writer is using a name the "
                         f"schema does not")
    return [schema.cell(f, values.get(f.name)) for f in schema.TABLES[table].fields]


def csv_line(cells: list[str]) -> str:
    """Quoted the way `csv` itself would, so a note containing a comma cannot split a row."""
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(cells)
    return buf.getvalue()
