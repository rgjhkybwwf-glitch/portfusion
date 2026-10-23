"""order.py — THE RECORD'S ONE ORDER, and the ids that follow it.

An event table reads as it happened: by its date, then its account's place in the register, then
its ticker. A row entered late goes where its date puts it. A buy's or a sale's id is its place in
that order, numbered from one under a `T-` or an `E-`, so a backdated entry renumbers every one
after it, and a sale's `closes` and an id a note quotes follow.

Pure: cells in, cells out, holding no state and touching no file. The loader asks it whether a
table is in order (`rules`), the doors where a row goes (`desk/doors/commit.py`), and a migration
how to put a book in order (`migrations.py`), which is why it imports nothing of the record.
"""
from __future__ import annotations

import re

#: Each event table's date column. A register (`accounts`, `current-prices`, `account-readings`)
#: holds one row per key, replaced in place, and has no order of its own; the journal is in the
#: order it was written by construction.
DATED = {"buys": "date", "sales": "date", "income": "date", "capital-movements": "date",
         "cash-readings": "as_of", "reasoning": "date", "research-notes": "published",
         "quarter-nav": "as_of", "quarter-snapshots": "as_of", "quarter-results": "as_of"}

#: The tables whose id is their place: (id column, prefix).
NUMBERED = {"buys": ("trade_id", "T"), "sales": ("sale_id", "E")}

_ID = re.compile(r"\b([TE])-(\d{3,})\b")


def _cell(v) -> str:
    return "" if v is None else str(v)


def key(table: str, header: list[str], accounts: list[str]):
    """A row's place: its date, its account's place in the register (the book's own row, with no
    account, first), its ticker. Cells may be raw text or loaded values."""
    at = header.index(DATED[table])
    acct = header.index("account") if "account" in header else None
    tick = header.index("ticker") if "ticker" in header else None
    place = {a: i for i, a in enumerate(accounts)}

    def of(row) -> tuple:
        a = _cell(row[acct]) if acct is not None else ""
        return (_cell(row[at]), place.get(a, -1 if not a else len(place)),
                _cell(row[tick]) if tick is not None else "")
    return of


def placed(table: str, header: list[str], rows: list, new: list, accounts: list[str]) -> list:
    """`rows` with `new` among them, every one in its place. A new row goes after any it ties
    with, as the later entry; rows already on file keep their order among themselves."""
    return sorted(rows + new, key=key(table, header, accounts))


def out_of_order(table: str, header: list[str], rows: list, accounts: list[str]) -> int | None:
    """The first row (1-based, after the header) placed before one it should follow, or None."""
    of = key(table, header, accounts)
    keys = [of(r) for r in rows]
    return next((i + 2 for i in range(len(keys) - 1) if keys[i + 1] < keys[i]), None)


def misnumbered(table: str, header: list[str], rows: list) -> int | None:
    """The first row (1-based, after the header) whose id is not its place, or None."""
    column, prefix = NUMBERED[table]
    at = header.index(column)
    return next((i + 1 for i, r in enumerate(rows)
                 if _cell(r[at]) != f"{prefix}-{i + 1:03d}"), None)


def renumbered(buys: tuple[list[str], list], sales: tuple[list[str], list]):
    """Buys and sales, each `(header, rows)` in its place, numbered by it, every reference
    following (`followed()`). Returns the two row lists and the ids that moved,
    `{table: [(was, now)]}`. A row that does not change is returned as the same object.
    Raises ValueError where two rows hold one id, since a reference to it could follow either.

    An id no row holds is left as it was: a note quoting one names nothing on file."""
    moves: dict[str, list] = {}
    ids: dict[str, str] = {}
    for table, (header, rows) in (("buys", buys), ("sales", sales)):
        column, prefix = NUMBERED[table]
        at = header.index(column)
        now = {_cell(r[at]): f"{prefix}-{i + 1:03d}" for i, r in enumerate(rows)}
        if len(now) != len(rows):
            seen = [_cell(r[at]) for r in rows]
            raise ValueError(f"{table}: {sorted({i for i in seen if seen.count(i) > 1})} name more "
                             f"than one row, so what names them cannot be followed")
        moves[table] = [(was, n) for was, n in now.items() if was != n]
        ids.update(now)
    out = []
    for table, (header, rows) in (("buys", buys), ("sales", sales)):
        new = []
        for r in rows:
            cells = followed(table, header, r, ids)
            new.append(cells if cells != list(r) else r)
        out.append(new)
    return out[0], out[1], moves


def followed(table: str, header: list[str], row, ids: dict[str, str]) -> list:
    """`row` with every id it holds moved by `ids` ({was: now}): its own, a sale's `closes`, and
    any a note quotes."""
    if table not in NUMBERED:
        return list(row)
    at = {header.index(c) for c in (NUMBERED[table][0], "closes", "note") if c in header}
    return [_ID.sub(lambda m: ids.get(m.group(0), m.group(0)), _cell(c)) if i in at else c
            for i, c in enumerate(row)]


def said(moves: dict[str, list]) -> list[str]:
    """The ids that move, in words, a run of them as one: "<first> to <last> become <first> to
    <last>", each id moved up or down by the same step."""
    out = []
    for table in ("buys", "sales"):
        pairs = sorted(moves.get(table) or [], key=lambda p: _n(p[0]))
        run: list = []
        for pair in pairs + [None]:
            if run and (pair is None or _n(pair[0]) != _n(run[-1][0]) + 1
                        or _n(pair[1]) != _n(run[-1][1]) + 1):
                (a, b), (c, d) = run[0], run[-1]
                out.append(f"{a} becomes {b}" if len(run) == 1 else
                           f"{a} to {c} become {b} to {d}")
                run = []
            if pair is not None:
                run.append(pair)
    return out


def _n(rid: str) -> int:
    m = _ID.fullmatch(rid)
    return int(m.group(2)) if m else -1
