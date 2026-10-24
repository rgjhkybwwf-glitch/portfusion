"""record/migrations.py — A RELEASE'S STORE CHANGES, AS DATA, and how a book is moved by them.

The loader refuses a table whose columns are not the schema's, and names it. A release that
renames a table or a column declares the move here, and `portfusion migrate` carries a book across:
shown first, written on `--write`, and put back whole if the book then will not open or audit.

A STEP APPLIES WHERE THE BOOK STILL HAS ITS OLD SHAPE: an old file name, an old column. Nothing is
recorded in the book, so a second run finds nothing to do and no version number can drift.

NAMES, NOT FACTS. Beside the tables, the journal's `table` and the Bench's items (archived and
open) carry table and column names, and move with them. A book's own `checks/` is its code: the
lines that name an old one are listed, never edited.

Imports nothing of the record but its order (`order.py`), its evidence classes
(`rules_evidence.py`), its schema and the histories' files, all pure: a book in the old shape will
not load, which is why it is here.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import pathlib
import re
import zoneinfo
from typing import Callable, NamedTuple

from portfusion.history import files
from portfusion.record import order, rules_evidence, schema


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


MIGRATIONS = (
    Migration(
        issue="#43 one name for one idea, from the store to the desk",
        tables={"trades": "buys", "exits": "sales", "closed-positions": "realisations",
                "issuers": "companies", "account-observations": "account-readings",
                "cash-observations": "cash-readings"},
        columns={
            "securities": {"code": "ticker", "kind": "held_as"},
            "accounts": {"broker": "broker_firm", "kind": "held_as"},
            "contracts": {"code": "ticker"},
            "realisations": {"realisation": "realisation_id", "open_date": "opened"},
            "buys": {"id": "trade_id", "price": "traded_price"},
            "sales": {"eid": "sale_id", "price": "traded_price", "realisation": "realisation_id"},
            "baseline-reconstruction": {"fx": "rate"},
            "quarter-snapshots": {"local_price": "price", "gbp_value": "value",
                                  "gbp_cost": "cost"},
            "current-prices": {"ticker": "mark_key"},
            "price-history": {"ticker": "mark_key"},
        },
        splits={"buys": ("val", {"shares": "cost", "spread bet": "level_points"}, "ticker")},
        marks={"ticker": "mark_key"},
        code=(r"\bD\.(trades|exits|closed|COMPANY_MASTER|cash_observations)\b",
              r"\b(CashObservation|ClosedPosition|Trade|Exit)\b",
              r"\.(eid|val|realisation|open_date|price|id)\b"),
    ),
    Migration(
        issue="the record reads as it happened: every event table in date order, ids its place",
        tables={}, columns={}, splits={}, marks={}, code=(),
        rows=lambda store: _in_date_order(store),
    ),
    Migration(
        issue="two tables retired, each saying nothing its events do not",
        tables={}, columns={}, splits={}, marks={},
        code=(r"\bD\.(realisations|dec_rows)\b", r"\bRealisationRow\b"),
        rows=lambda store: _retired(store),
    ),
    Migration(
        issue="a correction replaces its row, and the lifecycle column retires",
        tables={}, columns={}, splits={}, marks={},
        code=(r"\b(LIVE_MARK|MARK_STATUSES|live_rows)\b",),
        rows=lambda store: _lifecycle(store),
    ),
    Migration(
        issue="a share account's cash in one place, its cash readings",
        tables={}, columns={}, splits={}, marks={},
        code=(r"\.(recon_cash|stmt_value|cash_retired)\b",),
        rows=lambda store: _cash_in_one_place(store),
    ),
    Migration(
        issue="every sum of money written to the penny",
        tables={}, columns={}, splits={}, marks={}, code=(),
        rows=lambda store: _to_the_penny(store),
    ),
    Migration(
        issue="the journal on one clock: every instant in UTC",
        tables={}, columns={}, splits={}, marks={}, code=(),
        rows=lambda store: _on_one_clock(store),
    ),
    Migration(
        issue="an account opened after the book says when: the register's `record_begins`",
        tables={}, columns={}, splits={}, marks={}, code=(),
        rows=lambda store: _record_begins_column(store),
    ),
)

#: THE TABLES A RELEASE HAS RETIRED, and why: their files go, and the journal rows that name them
#: with them, since the journal names only tables the record holds.
RETIRED = {
    "realisations": "a round trip's entry date and note come from its own buys and sales",
    "baseline-reconstruction": "the working behind quarter ends since restated, read by nothing",
}


#: THE TABLES THAT CARRIED A LIFECYCLE, `status`: a row live, or superseded and kept beside the one
#: that replaced it. A correction now replaces its row, so the column goes, and any superseded row
#: with it. True where the journal counts the table's rows.
LIFECYCLE = {"price-history": False, "fx-history": False, "account-statements": False,
             "quarter-nav": True, "quarter-snapshots": True}


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
    """ticker -> held_as, from securities.csv in either shape."""
    _lines, rows, _ = _rows((store / "securities.csv").read_text(encoding="utf-8"))
    head = rows[0]
    tk = head.index("ticker" if "ticker" in head else "code")
    kind = head.index("held_as" if "held_as" in head else "kind")
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
    new_lines = {r["values"].get("code", r["values"].get("ticker")):
                 r["values"].get("kind", r["values"].get("held_as"))
                 for r in item.get("rows") or [] if r.get("table") == "securities"}
    for r in item.get("rows") or []:
        table = r["table"] = m.tables.get(r.get("table"), r.get("table"))
        cols = dict(m.columns.get(table, {}))
        values = r.get("values") or {}
        old, into, by = m.splits.get(table) or (None, {}, None)
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


def _in_date_order(store: pathlib.Path) -> list[Change]:
    """Every event table into its date order and the buys and sales numbered by it
    (`order.py`), and settings.csv's retired `trade_id_floor` gone. Untouched lines keep their
    bytes."""
    def read(name):
        path = store / f"{name}.csv"
        text = path.read_text(encoding="utf-8")
        lines, rows, eol = _rows(text)
        return path, text, rows[0], list(zip(rows[1:], lines[1:])), lines[0], eol

    _p, _t, head, accounts, _h, _e = read("accounts")
    accounts = [r[head.index("account")] for r, _ in accounts]
    tables = {n: read(n) for n in order.DATED if (store / f"{n}.csv").is_file()}
    rows = {n: order.placed(n, t[2], [r for r, _ in t[3]], [], accounts)
            for n, t in tables.items()}
    moves = {}
    if "buys" in rows and "sales" in rows:
        rows["buys"], rows["sales"], moves = order.renumbered(
            (tables["buys"][2], rows["buys"]), (tables["sales"][2], rows["sales"]))
    out, journal = [], []
    for name, (path, text, _head, pairs, header, eol) in tables.items():
        line_of = {id(r): line for r, line in pairs}
        new = header + "".join(line_of.get(id(r)) or _line(r, eol) for r in rows[name])
        if new != text:
            moved = sum(1 for (r, _), s in zip(pairs, rows[name]) if r is not s)
            said = order.said({name: moves.get(name)})
            out.append(Change(path, path, new, [f"{path.name}: into date order"]
                              + [f"  {s}" for s in said]))
            journal.append(("replace", name, moved, "; ".join(
                [f"{moved} row(s) into date order"] + said)))
    settings = store / "settings.csv"
    if settings.is_file():
        text = settings.read_text(encoding="utf-8")
        lines = [ln for ln in re.split(r"(?<=\n)", text) if ln]
        kept = [ln for ln in lines if not ln.startswith("trade_id_floor,")]
        if len(kept) != len(lines):
            out.append(Change(settings, settings, "".join(kept),
                              ["settings.csv: trade_id_floor retired, an id being its place"]))
            journal.append(("remove", "settings", len(lines) - len(kept),
                            "trade_id_floor retired, an id being its place"))
    return out + _journalled(store, journal)


def _journalled(store: pathlib.Path, journal: list[tuple]) -> list[Change]:
    """THE JOURNAL SAYS SO, or the rows a migration moved or removed are rows no route accounts
    for: `journal` as (op, table, rows, detail), appended to journal.csv."""
    path = store / "journal.csv"
    if not (journal and path.is_file()):
        return []
    text = path.read_text(encoding="utf-8")
    at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    eol = "\r\n" if "\r\n" in text else "\n"
    text += "" if not text or text.endswith("\n") else eol
    return [Change(path, path, text + "".join(
        _line([at, "migrate", op, table, str(n), "portfusion migrate", detail], eol)
        for op, table, n, detail in journal), [f"journal.csv: {len(journal)} row(s) say so"])]


def _lifecycle(store: pathlib.Path) -> list[Change]:
    """Each `LIFECYCLE` table without its `status` column and its superseded rows. Every line the
    column leaves is written again, without that one cell."""
    out, journal = [], []
    for name, counted in LIFECYCLE.items():
        path = store / f"{name}.csv"
        if not path.is_file():
            continue
        _lines, rows, eol = _rows(path.read_text(encoding="utf-8"))
        if "status" not in rows[0]:
            continue
        at = rows[0].index("status")
        kept = [r[:at] + r[at + 1:] for r in rows if r is rows[0] or r[at] != "superseded"]
        gone = len(rows) - len(kept)
        out.append(Change(path, path, "".join(_line(r, eol) for r in kept), [
            f"{path.name}: `status` retired"
            + (f", {gone} superseded row(s) with it" if gone else "")]))
        if gone and counted:
            journal.append(("remove", name, gone, "superseded rows, retired with the lifecycle"))
    # A RESTATED QUARTER WAS A SECOND ROW, the newest in force: it now replaces the one before.
    path = store / "quarter-results.csv"
    if path.is_file():
        lines, rows, _eol = _rows(path.read_text(encoding="utf-8"))
        last = {tuple(r[:2]): i for i, r in enumerate(rows[1:], 1)}
        kept = lines[:1] + [ln for i, ln in enumerate(lines[1:], 1) if last[tuple(rows[i][:2])] == i]
        if gone := len(lines) - len(kept):
            out.append(Change(path, path, "".join(kept), [
                f"quarter-results.csv: {gone} row(s) give way to their restatement"]))
            journal.append(("remove", "quarter-results", gone,
                            "rows a restatement replaced, retired with the lifecycle"))
    return out + _journalled(store, journal)


def _retired(store: pathlib.Path) -> list[Change]:
    """Each `RETIRED` table's file removed, and the journal's rows naming one."""
    out = [Change(path, path, None, [f"{path.name}: retired, {why}"])
           for name, why in RETIRED.items() if (path := store / f"{name}.csv").is_file()]
    journal = store / "journal.csv"
    if journal.is_file():
        lines, rows, _eol = _rows(journal.read_text(encoding="utf-8"))
        at = rows[0].index("table")
        kept = lines[:1] + [ln for ln, r in zip(lines[1:], rows[1:]) if r[at] not in RETIRED]
        if len(kept) != len(lines):
            out.append(Change(journal, journal, "".join(kept), [
                f"journal.csv: {len(lines) - len(kept)} row(s) naming a retired table removed"]))
    return out


def _evidence_of(source: str, account: str) -> tuple[str, str] | None:
    """The evidence class and reference a `source` line was made from: the class that composed it
    (`rules_evidence.evidence_from_source()`), and the reference its template holds, where the
    two make the line again exactly. None otherwise."""
    ev = rules_evidence.evidence_from_source(source)
    if ev is None:
        return None
    m = rules_evidence.template_pattern(ev).fullmatch(source)
    ref = (m.group("reference") or "").strip() if m and "reference" in m.groupdict() else ""
    made = rules_evidence.evidence_source(ev.key, reference=ref, account=account)
    return (ev.key, ref) if ref and made == source else None


def _cash_in_one_place(store: pathlib.Path) -> list[Change]:
    """A share reading's cash and total, and a statement's cash, out of their own columns: each
    figure a cash reading of its day, unless one is on file at it. A figure on file at another, or
    a statement's cash whose source names no class, is moved by hand, and so is a reading whose
    stock and cash are not its total. A statement's cash of zero whose source names none is an
    account not yet funded, and goes; a spread bet's is its funds, on the same row, and goes; and
    so does one whose document states no cash (ii's holdings export), being another document's.
    Untouched lines keep their bytes."""
    path = store / "cash-readings.csv"
    if not path.is_file():
        return []
    lines, rows, eol = _rows(path.read_text(encoding="utf-8"))
    on_file = {(r[0], r[1]): r[2] for r in rows[1:]}
    new, out = [], []

    def owe(account, day, cash, evidence, reference, where):
        ev = rules_evidence.EVIDENCE_BY_KEY.get(evidence)
        if ev is not None and ev.covers and not rules_evidence.states_cash(ev):
            said.append(f"  {where}: cash {cash} its {ev.label} does not state, dropped")
            return
        was = on_file.get((account, day))
        if was is not None and abs(float(was) - float(cash)) >= 0.005:
            raise ValueError(f"{where}: cash {cash} for {account} on {day}, but cash-readings.csv "
                             f"says {was}: move it by hand")
        if was is None:
            on_file[(account, day)] = cash
            new.append([account, day, cash, evidence, reference])

    _p, register, _e = _rows((store / "accounts.csv").read_text(encoding="utf-8"))
    kind = register[0].index("held_as" if "held_as" in register[0] else "kind")
    named = register[0].index("account")
    accounts = [r[named] for r in register[1:]]
    spread_bets = {r[named] for r in register[1:] if r[kind] == "spread bet"}
    for name, drop in (("account-readings", ("recon_cash", "stmt_value")),
                       ("account-statements", ("cash",))):
        table = store / f"{name}.csv"
        if not table.is_file():
            continue
        _l, trows, teol = _rows(table.read_text(encoding="utf-8"))
        at = {c: i for i, c in enumerate(trows[0])}
        if drop[0] not in at:
            continue
        said = [f"{table.name}: {', '.join(c for c in drop if c in at)} retired, its cash a "
                f"cash reading"]
        for i, r in enumerate(trows[1:], 2):
            cash, where = r[at[drop[0]]], f"{table.name} row {i}"
            if cash == "":
                continue
            if name == "account-readings":
                total, stock = r[at["stmt_value"]], r[at["positions"]]
                if total and stock and abs(float(stock) + float(cash) - float(total)) >= 0.005:
                    raise ValueError(f"{where}: stock {stock} plus cash {cash} is not its total "
                                     f"{total}: move it by hand")
                owe(r[at["account"]], r[at["as_of"]], cash, r[at["evidence"]],
                    r[at["reference"]], where)
            elif r[at["account"]] in spread_bets:
                said.append(f"  {where}: a spread bet's cash, its funds on the same row, dropped")
            elif (r[at["account"]], r[at["as_of"]]) in on_file:
                owe(r[at["account"]], r[at["as_of"]], cash, "", "", where)   # compared, not added
            elif found := _evidence_of(r[at["source"]], r[at["account"]]):
                owe(r[at["account"]], r[at["as_of"]], cash, *found, where)
            elif float(cash) == 0:
                said.append(f"  {where}: cash 0 of an account no document names, dropped")
            else:
                raise ValueError(f"{where}: its cash {cash} names no evidence class in its "
                                 f"source, so it cannot be a cash reading: move it by hand")
        keep = [j for j, c in enumerate(trows[0]) if c not in drop]
        out.append(Change(table, table, "".join(_line([r[j] for j in keep], teol) for r in trows),
                          said))
    if not new:
        return out
    line_of = {id(r): line for r, line in zip(rows[1:], lines[1:])}
    placed = order.placed("cash-readings", rows[0], rows[1:], new, accounts)
    out.append(Change(path, path, lines[0] + "".join(line_of.get(id(r)) or _line(r, eol)
                                                     for r in placed),
                      [f"cash-readings.csv: {len(new)} cash reading(s) from the readings and "
                       f"statements"]))
    return out + _journalled(store, [("append", "cash-readings", len(new),
                                      "cash moved here from account readings and statements")])


def _to_the_penny(store: pathlib.Path) -> list[Change]:
    """Every sum of money written to exactly two places (`schema.MONEY`), in the record's tables
    and the account history. No value moves; a sum with more places than pennies is moved by
    hand. Untouched lines keep their bytes."""
    money = {t.name: [f.name for f in t.fields if f.exact] for t in schema.TABLES.values()}
    money |= {pathlib.Path(name).stem: [c for c, how in places.items() if how.get("exact")]
              for name, places in files.PLACES.items()}
    out, journal = [], []
    for name, cols in money.items():
        path = store / f"{name}.csv"
        if not cols or not path.is_file():
            continue
        lines, rows, eol = _rows(path.read_text(encoding="utf-8"))
        at = [rows[0].index(c) for c in cols if c in rows[0]]
        n = 0
        for i, r in enumerate(rows[1:], 1):
            new = list(r)
            for j in at:
                try:
                    new[j] = schema.figure(r[j], 2, exact=True) if r[j] != "" else ""
                except ValueError:
                    raise ValueError(f"{path.name} row {i + 1}: {r[j]!r} is not a sum to the "
                                     f"penny: move it by hand") from None
            if new != r:
                lines[i], n = _line(new, eol), n + 1
        if n:
            out.append(Change(path, path, "".join(lines),
                              [f"{path.name}: {n} row(s) with money written to the penny"]))
            if name in schema.TABLES:
                journal.append(("replace", name, n, "money written to the penny; no value moved"))
    return out + _journalled(store, journal)


def _utc(at: str) -> str:
    """An instant on the record's clock (`schema.record_instant`): one marked `Z` as it is, one
    carrying its own offset moved by it, one with no zone read as UK wall-clock time. An hour the
    clocks going back make twice is read as its first, summer, one."""
    if not at or at.endswith("Z"):
        return at
    t = _dt.datetime.fromisoformat(at)
    t = t if t.tzinfo else t.replace(tzinfo=zoneinfo.ZoneInfo("Europe/London"))
    return t.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _on_one_clock(store: pathlib.Path) -> list[Change]:
    """Every journal instant written before the record kept UTC, and the bench items it ties to
    (`written_at`), on the one clock. No row moves; untouched lines keep their bytes."""
    out, path = [], store / "journal.csv"
    if path.is_file():
        lines, rows, eol = _rows(path.read_text(encoding="utf-8"))
        moved = [i for i, r in enumerate(rows[1:], 1) if r and _utc(r[0]) != r[0]]
        for i in moved:
            lines[i] = _line([_utc(rows[i][0]), *rows[i][1:]], eol)
        if moved:
            out.append(Change(path, path, "".join(lines),
                              [f"journal.csv: {len(moved)} instant(s) written in UTC"]))
    for item in sorted((store.parent / "_archive" / "bench").glob("*.json")):
        raw = item.read_text(encoding="utf-8")
        at = json.loads(raw).get("written_at") or ""
        new = re.sub(rf'("written_at"\s*:\s*"){re.escape(at)}"', rf'\g<1>{_utc(at)}"', raw, count=1)
        if new != raw:
            out.append(Change(item, item, new, [f"bench item {item.name}: written_at in UTC"]))
    return out


def _record_begins_column(store: pathlib.Path) -> list[Change]:
    """The register given its `record_begins` column, blank on every row: each account held from the
    book's opening. One opened later is dated by hand, with the 0.00 rows that stood in for its
    quarter ends before it, since only their prose says which they were."""
    path = store / "accounts.csv"
    lines, rows, eol = _rows(path.read_text(encoding="utf-8"))
    if "record_begins" in rows[0]:
        return []
    return [Change(path, path, "".join(_line([*r, "" if i else "record_begins"], eol)
                                       for i, r in enumerate(rows)),
                   ["accounts.csv: a `record_begins` column, blank: date an account opened later by hand"])]


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
    """The lines of the book's own `checks/` that name an old or retired table or column: the
    book's code, listed for its owner to move by hand."""
    old = {t for m in MIGRATIONS for t in m.tables} | set(RETIRED) | {
        c for m in MIGRATIONS for cols in m.columns.values() for c in cols} | {
        s[0] for m in MIGRATIONS for s in m.splits.values()}
    pattern = re.compile("|".join([r"""(["'])(%s)(\.csv)?\1""" % "|".join(
        re.escape(n) for n in sorted(old, key=len, reverse=True)),
        *(c for m in MIGRATIONS for c in m.code)]))
    out = []
    for path in sorted((book / "checks").glob("*.py")) if (book / "checks").is_dir() else []:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                out.append(f"{path.name}:{n}: {line.strip()}")
    return out
