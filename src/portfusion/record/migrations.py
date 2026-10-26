"""record/migrations.py — A RELEASE'S STORE CHANGES, AS DATA, and how a book is moved by them.

The loader refuses a table whose columns are not the schema's, and names it. A release that
renames a table or a column declares the move here, and `portfusion migrate` carries a book across:
shown first, written on `--write`, and put back whole if the book then will not open or audit.

A STEP APPLIES WHERE THE BOOK STILL HAS ITS OLD SHAPE: an old file name, an old column. Nothing is
recorded in the book, so a second run finds nothing to do and no version number can drift.

NAMES, NOT FACTS. Beside the tables, the journal's `table` and the Bench's items (archived and
open) carry table and column names, and move with them. A book's own `checks/` is its code: the
lines that name an old one are listed, never edited.

Imports nothing of the record: a book in the old shape will not load, which is why it is here.
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import re
from typing import Callable, NamedTuple


class Migration(NamedTuple):
    issue: str                    # where the change was agreed
    tables: dict[str, str]        # old file stem -> new
    columns: dict[str, dict]      # table (new stem) -> {old column: new}
    #: A COLUMN THAT SPLITS BY ITS LINE'S `held_as`: table -> (old, {held_as: new}, ticker column).
    #: The new columns take the old one's place, in the order given; the other one is blank.
    splits: dict[str, tuple]
    #: A Bench item's first marks: {old key: new}.
    marks: dict[str, str]
    #: How a book's own `checks/` code may read an old name, beyond quoting it: patterns, listed.
    code: tuple[str, ...]
    #: A MOVE OF ROWS, NOT NAMES: the store folder -> the changes it makes there.
    rows: Callable[[pathlib.Path], list] | None = None


#: A RELEASE THAT CHANGES THE STORE DECLARES THE MOVE HERE, as data, in the order it applies.
MIGRATIONS: tuple[Migration, ...] = ()


class Change(NamedTuple):
    """One file's move: where it was, where it goes, its new text (None removes it), and what
    moved, in words."""
    was: pathlib.Path
    to: pathlib.Path
    text: str | None
    said: list[str]


def _rows(text: str) -> tuple[list[str], list[list[str]], str]:
    """The file's raw lines, its parsed rows and its line ending. A cell that spans lines would
    part the two, so it is refused: such a table is moved by hand."""
    lines = [x for x in re.split(r"(?<=\n)", text) if x]   # "\n" alone, as csv reads a row
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) != len(lines):
        raise ValueError("a cell spans lines")
    return lines, rows, ("\r\n" if "\r\n" in text else "\n")


def _line(row: list[str], eol: str) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator=eol).writerow(row)
    return out.getvalue()


def _held_as(store: pathlib.Path) -> dict[str, str]:
    """ticker -> held_as, from securities.csv."""
    _lines, rows, _ = _rows((store / "securities.csv").read_text(encoding="utf-8"))
    tk, kind = rows[0].index("ticker"), rows[0].index("held_as")
    return {r[tk]: r[kind] for r in rows[1:]}


def _table(m: Migration, path: pathlib.Path, stem: str, held_as: dict) -> Change | None:
    """A table's move under `m`: its name, its header, a split column, and the journal's names.
    Every line it does not change passes through as the bytes it read."""
    text = path.read_text(encoding="utf-8")
    lines, rows, eol = _rows(text)
    head, said = rows[0], []
    to = path.with_name(f"{m.tables.get(stem, stem)}.csv")
    table = to.stem
    if to != path:
        if to.exists():
            raise ValueError(f"{path.name} and {to.name} are both in the store: move it by hand")
        said.append(f"rename  {path.name} -> {to.name}")
    renames = {o: n for o, n in m.columns.get(table, {}).items() if o in head}
    new_head = [renames.get(c, c) for c in head]
    split = m.splits.get(table)
    if split and split[0] in head:
        old, into, by = split
        at, tk = head.index(old), new_head.index(by)
        new_head[at:at + 1] = list(into.values())
        for i, r in enumerate(rows[1:], 1):
            kind = held_as.get(r[tk])
            if kind not in into:
                raise ValueError(f"{path.name} row {i}: {r[tk]!r} has no held_as on securities.csv")
            r[at:at + 1] = [r[at] if c == into[kind] else "" for c in into.values()]
            lines[i] = _line(r, eol)
            said.append(f"  {r[0]} {r[tk]} ({kind}): {old} {r[at + list(into).index(kind)]} "
                        f"-> {into[kind]}")
        renames[old] = " and ".join(into.values())
    if renames:
        said.insert(1 if to != path else 0, f"columns {to.name}: " + ", ".join(
            f"{o} -> {n}" for o, n in renames.items()))
        lines[0] = _line(new_head, eol)
    if stem == "journal" and "table" in head:
        at, n = head.index("table"), 0
        for i, r in enumerate(rows[1:], 1):
            if r[at] in m.tables:
                r[at], n = m.tables[r[at]], n + 1
                lines[i] = _line(r, eol)
        if n:
            said.append(f"journal.csv: {n} row(s) name a renamed table")
    new = "".join(lines)
    return Change(path, to, new, said) if new != text or to != path else None


def _item(m: Migration, path: pathlib.Path, held_as: dict) -> Change | None:
    """A Bench item's move: its rows' tables, their columns and split, `written_to` and marks.
    Written back in the format it was written in, so only the names move."""
    raw = path.read_text(encoding="utf-8")
    try:
        item = json.loads(raw)
    except ValueError as e:
        raise ValueError(f"{path.name} will not read: {e}") from None
    fmt = next(((a, nl) for a in (True, False) for nl in ("", "\n")
                if json.dumps(item, indent=2, ensure_ascii=a) + nl == raw), (True, ""))
    if item.get("written_to"):
        item["written_to"] = {m.tables.get(t, t): n for t, n in item["written_to"].items()}
    if item.get("marks"):
        item["marks"] = [{m.marks.get(k, k): v for k, v in mark.items()} for mark in item["marks"]]
    new_lines = {r["values"].get("ticker"): r["values"].get("held_as")
                 for r in item.get("rows") or [] if r.get("table") == "securities"}
    for r in item.get("rows") or []:
        table = r["table"] = m.tables.get(r.get("table"), r.get("table"))  # pyright: ignore[reportCallIssue, reportArgumentType]
        cols = dict(m.columns.get(table, {}))  # pyright: ignore[reportCallIssue, reportArgumentType]
        values = r.get("values") or {}
        old, into, by = m.splits.get(table) or (None, {}, None)  # pyright: ignore[reportArgumentType]
        if old in values:
            kind = held_as.get(values.get(by)) or new_lines.get(values.get(by))
            if kind not in into:
                raise ValueError(f"{path.name}: {values.get(by)!r} has no held_as on securities.csv")
            cols[old] = into[kind]
        if isinstance(r.get("values"), dict):
            # THE SPLIT TAKES THE OLD COLUMN'S PLACE, the other new column blank beside it.
            r["values"] = dict(kv for c, v in values.items() for kv in (
                [(n, v if n == cols[c] else "") for n in into.values()] if c == old
                else [(cols.get(c, c), v)]))
        if isinstance(r.get("sources"), dict):
            r["sources"] = {cols.get(c, c): v for c, v in r["sources"].items()}
        for k in ("derived", "drafted"):
            if isinstance(r.get(k), list):
                r[k] = sorted(cols.get(c, c) for c in r[k])
    new = json.dumps(item, indent=2, ensure_ascii=fmt[0]) + fmt[1]
    return Change(path, path, new, [f"bench item {path.name}"]) if new != raw else None


def plan(book: pathlib.Path) -> tuple[Migration | None, list[Change]]:
    """The first declared migration `book` still needs, and every change it makes, nothing
    written; (None, []) when the book is in the shape this release reads. ONE AT A TIME: a later
    migration is planned from the shape the one before it leaves, so a run moves one."""
    store = book / "store"
    for m in MIGRATIONS:
        held_as = _held_as(store)
        out = [c for path in sorted(store.glob("*.csv"))
               if (c := _table(m, path, path.stem, held_as))]
        for folder in (book / "_archive" / "bench", book / "_inbox" / ".bench"):
            out += [c for path in (sorted(folder.glob("*.json")) if folder.is_dir() else [])
                    if (c := _item(m, path, held_as))]
        out += m.rows(store) if m.rows else []
        if out:
            return m, out
    return None, []


def carry(book: pathlib.Path) -> tuple[list[Migration], dict[pathlib.Path, bytes | None]]:
    """Write every migration `book` still needs, each planned from the shape the one before left,
    and return them and what was there before, for `put_back()`. ALL OF THEM BEFORE THE BOOK IS
    OPENED: a book two releases behind may not load between them. A plan that fails part-way puts
    the book back itself."""
    done: list[Migration] = []
    before: dict[pathlib.Path, bytes | None] = {}
    try:
        for _ in MIGRATIONS:
            m, changes = plan(book)
            if m is None:
                break
            for path, data in write(changes).items():
                before.setdefault(path, data)
            done.append(m)
    except BaseException:
        put_back(before)
        raise
    return done, before


def write(changes: list[Change]) -> dict[pathlib.Path, bytes | None]:
    """Write `changes`. Returns what was there before each path, None where nothing was, so
    `put_back()` can restore the book exactly; a write that fails part-way puts it back itself."""
    before: dict[pathlib.Path, bytes | None] = {}
    for c in changes:
        for p in (c.was, c.to):
            before.setdefault(p, p.read_bytes() if p.exists() else None)
    try:
        for c in changes:
            if c.text is None:
                c.was.unlink()
                continue
            c.to.write_text(c.text, encoding="utf-8", newline="")
            if c.to != c.was:
                c.was.unlink()
    except BaseException:
        put_back(before)
        raise
    return before


def put_back(before: dict[pathlib.Path, bytes | None]) -> None:
    """Every path as it was before `write()`."""
    for p, data in before.items():
        if data is None:
            p.unlink(missing_ok=True)
        else:
            p.write_bytes(data)


def named_in_checks(book: pathlib.Path) -> list[str]:
    """The lines of the book's own `checks/` that name an old table or column: the book's code,
    listed for its owner to move by hand. Nothing declared, nothing listed."""
    old = {t for m in MIGRATIONS for t in m.tables} | {
        c for m in MIGRATIONS for cols in m.columns.values() for c in cols} | {
        s[0] for m in MIGRATIONS for s in m.splits.values()}
    alternatives = [c for m in MIGRATIONS for c in m.code]
    if old:
        alternatives.insert(0, r"""(["'])(%s)(\.csv)?\1""" % "|".join(
            re.escape(n) for n in sorted(old, key=len, reverse=True)))
    if not alternatives:
        return []
    pattern = re.compile("|".join(alternatives))
    out = []
    for path in sorted((book / "checks").glob("*.py")) if (book / "checks").is_dir() else []:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                out.append(f"{path.name}:{n}: {line.strip()}")
    return out
