"""THE FREEZE — a quarter end written into the store from the engine, once.

    python3 -m portfusion.desk.doors.freeze 2026-09-30             what would be written, and what is not ready
    python3 -m portfusion.desk.doors.freeze 2026-09-30 --write     write it

Until 25 Sep 2026 the close checklist had a person copy HOLDINGS into `quarter-snapshots.csv`
and each account's contribution into `quarter-nav.csv` — the one place a close typed figures,
and only while HOLDINGS happened to show that day's prices. `Book.freeze_rows()` derives both
from the price and FX histories, each line at its mark nearest the quarter end within
`rules.CLOSE_CHECK_WINDOW_DAYS` either side, so the freeze can run on the day or days after it: a
quarter end needs only to be close.

A STORE DOOR, the fourth under desk/ (`tests/desk/test_boundaries.py`), and it only APPENDS.

WHAT IT WILL NOT DO:

  · FREEZE ANY DAY BUT THE ONE DUE. `Book.quarter_to_close()` names it; a quarter frozen out of
    order, or twice, would leave the returns reading from the wrong pair of ends.
  · FREEZE A DAY STILL TO COME, or with a line the close window does not reach —
    `Book.freeze_rows()["off_date"]` lists any, and the fix is a Price Refresh inside the window.
  · LEAVE HALF A FREEZE. Every table and the journal are held by `commit.atomic()`.

THE RESULTS GO IN LAST. Once the inputs are on file the engine computes the closed quarter, and
`Book.quarter_results()` appends its six figures per account to `quarter-results.csv`: what the
quarter is held to from then on.

A RESTATEMENT IS NOT A SECOND FREEZE. `restate()` strikes named accounts at frozen quarter ends
again from the record as it now stands, superseding their rows rather than editing them, and
appends a results row, saying why, for each quarter whose figures moved. It is
called from Python with the dates, the accounts and the reason, and is a decision each time.
"""
from __future__ import annotations

import csv
import datetime as _dt
import sys

from portfusion.record import rules as D
from portfusion.record import schema
from portfusion.desk.doors import commit
from portfusion.log import log

TABLES = ("quarter-snapshots", "quarter-nav", "quarter-results")


class Refused(Exception):
    """Nothing was written. Carries why."""


def plan(as_of: str) -> dict:
    """What a freeze of `as_of` would write, and every reason it may not. Writes nothing."""
    from portfusion.engine import Book
    due = Book.quarter_to_close().date().isoformat()
    why = []
    if as_of != due:
        why.append(f"{as_of} is not the quarter due to close; that is {due}")
    if _dt.date.fromisoformat(as_of) > _dt.date.today():
        why.append(f"{as_of} has not come yet")
    on_file = [t for t in TABLES if any(str(r[0]) == as_of for r in schema.load(t))]
    if on_file:
        why.append(f"{', '.join(on_file)} already hold rows dated {as_of}: a quarter is frozen once")
    rows = {"quarter_snapshots": [], "quarter_nav": [], "off_date": [], "off_keys": []}
    if not why:
        try:
            rows = Book().freeze_rows(as_of)
        except KeyError as e:
            why.append(_unvalued(as_of, e))
    if rows["off_date"]:
        why.append(f"{len(rows['off_date'])} line(s) have no mark within "
                   f"{D.CLOSE_CHECK_WINDOW_DAYS} days of {as_of} — {_way_in(rows['off_keys'], as_of)}")
    return {"as_of": as_of, "due": due, "ready": not why, "why": why, **rows}


@commit.held
def write(as_of: str) -> dict:
    """Append the quarter end's inputs, then its results, and journal all three. Raises
    `Refused`, writing nothing."""
    p = plan(as_of)
    if not p["ready"]:
        raise Refused("; ".join(p["why"]))
    by_table = {"quarter-snapshots": p["quarter_snapshots"], "quarter-nav": p["quarter_nav"]}
    at = schema.record_instant()
    paths = [schema.TABLES[t].path for t in TABLES] + [schema.TABLES["journal"].path]
    try:
        with commit.atomic(*paths):
            for table, rows in by_table.items():
                _append(table, [{**r, "status": D.LIVE_MARK} for r in rows])
            # THE QUARTER IS COMPUTED FROM WHAT WAS JUST FROZEN, so the record is reloaded first.
            D.reload_store()
            from portfusion.engine import Book
            by_table["quarter-results"] = [{**r, "note": ""} for r in Book().quarter_results(as_of)]
            _append("quarter-results", by_table["quarter-results"])
            commit.journal([("freeze", "append", table, len(rows), as_of,
                             f"{len(rows)} row(s) freezing {as_of}, from the engine")
                            for table, rows in by_table.items()], at=at)
    finally:
        D.reload_store()
    return {"as_of": as_of, "quarter_snapshots": len(p["quarter_snapshots"]),
            "quarter_nav": len(p["quarter_nav"]),
            "quarter_results": len(by_table["quarter-results"])}


@commit.held
def restate(changes: dict[str, list[str]], why: str, lines_only: bool = False) -> dict:
    """RESTATE frozen quarter ends: at each date in `changes`, its accounts struck again by the
    engine at the marks nearest it (`Book.freeze_rows()`), and every closed quarter a restated
    date ends or opens held to its new figures.

    NO FIGURE ON FILE CHANGES; A CORRECTION SUPERSEDES. Each account's live rows at the date are
    SUPERSEDED, kept with their own provenance, and the new ones appended beside them, live. Then
    `quarter-results.csv` gains a row, noted "Restated: <why>", for the book and each account whose
    six figures moved from the newest held, which the rows before it stay under.

    A date with no frozen composition — the opening, 31 Dec 2025, never had one — has its net
    asset value restated alone, unless `lines_only` asks for its LINES ALONE: the named accounts'
    composition, struck as a freeze strikes it and APPENDED, with nothing superseded and the
    date's net asset value and results left as they stand (the first quarter's contributors
    need an opening composition). A date with lines on file is refused
    then: they are restated with its net asset value. An account whose struck rows match its live
    ones to the figure is left as it is. The statements history copies quarter-nav at the quarter ends the freeze did
    not write; restating one of those is mirrored there by hand (`test_quarter_nav.py` ties them).

    Raises `Refused`, writing nothing: no reason given, a date to come, an account with no live
    row at the date, a line the close window does not reach, nothing that would move, or lines
    asked for where lines are on file.
    """
    from portfusion.engine import Book
    if not str(why).strip():
        raise Refused("a restatement says why: its reason is the results rows' note")
    today = _dt.date.today()
    nav_hdr, snap_hdr = schema.TABLES["quarter-nav"].header, schema.TABLES["quarter-snapshots"].header
    live = D.LIVE_MARK
    on_nav = [dict(zip(nav_hdr, r)) for r in schema.load("quarter-nav")]
    on_snap = [dict(zip(snap_hdr, r)) for r in schema.load("quarter-snapshots")]
    b = Book()
    new_nav, new_snap, struck = [], [], {}
    for as_of, accounts in sorted(changes.items()):
        if _dt.date.fromisoformat(as_of) > today:
            raise Refused(f"{as_of} has not come yet")
        was_nav = [r for r in on_nav if str(r["as_of"]) == as_of and r["status"] == live]
        missing = sorted(set(accounts) - {r["account"] for r in was_nav})
        if missing:
            raise Refused(f"{', '.join(missing)}: no frozen row at {as_of} to restate. A quarter "
                          f"end is frozen first, by write().")
        try:
            rows = b.freeze_rows(as_of, accounts=accounts, restated=today.isoformat())
        except KeyError as e:
            raise Refused(_unvalued(as_of, e))
        except ValueError as e:
            raise Refused(f"the book cannot strike {as_of} again: {e}")
        if rows["off_date"]:
            raise Refused(f"{len(rows['off_date'])} line(s) have no mark within "
                          f"{D.CLOSE_CHECK_WINDOW_DAYS} days of {as_of}: "
                          + "; ".join(rows["off_date"]) + f". {_way_in(rows['off_keys'], as_of)}")
        was_snap = [r for r in on_snap if str(r["as_of"]) == as_of and r["status"] == live]
        composed = bool(was_snap)
        if lines_only:
            if composed:
                raise Refused(f"{as_of} has a composition on file: lines frozen there are "
                              f"restated with its net asset value, not appended")
            new_snap += [r for r in rows["quarter_snapshots"] if r["account"] in accounts]
            struck.update({(as_of, a): False for a in accounts})
            continue
        for account in accounts:
            n_new = [r for r in rows["quarter_nav"] if r["account"] == account]
            s_new = [r for r in rows["quarter_snapshots"] if r["account"] == account] if composed else []
            n_was = [r for r in was_nav if r["account"] == account]
            s_was = [r for r in was_snap if r["account"] == account]
            if (_figures(n_new, ("contribution", "amount")) == _figures(n_was, ("contribution", "amount"))
                    and _figures(s_new, _LINE) == _figures(s_was, _LINE)):
                continue
            struck[(as_of, account)] = composed
            new_nav += n_new
            new_snap += s_new
    if not struck:
        raise Refused("nothing would move: every account named strikes at its figures on file")
    if lines_only:
        return _append_lines(new_snap, sorted(struck))

    at = schema.record_instant()
    paths = [schema.TABLES[t].path for t in TABLES] + [schema.TABLES["journal"].path]
    journal, results = [], []
    try:
        with commit.atomic(*paths):
            for table, new in (("quarter-nav", new_nav), ("quarter-snapshots", new_snap)):
                keys = {k for k, composed in struck.items() if table == "quarter-nav" or composed}
                gone = _supersede(table, keys)
                _append(table, [{**r, "status": live} for r in new])
                for as_of in sorted({d for d, _ in keys}):
                    names = ", ".join(a for d, a in sorted(keys) if d == as_of)
                    n_gone = sum(1 for d, _ in gone if d == as_of)
                    n_new = sum(1 for r in new if r["as_of"] == as_of)
                    journal += [("freeze", "replace", table, n_gone, f"restated {as_of}",
                                 f"{names}: {n_gone} row(s) at {as_of} superseded, kept"),
                                ("freeze", "append", table, n_new, f"restated {as_of}",
                                 f"{names}: {n_new} row(s) restating {as_of}, from the engine")]
            D.reload_store()
            b = Book()
            closed = {str(q)[:10] for q in b.quarter_returns()["quarter_end"]}
            # A RESTATED DATE ENDS ONE QUARTER AND OPENS THE NEXT; both are held again.
            touched = {d for d, _ in struck} | {_next_quarter_end(d) for d, _ in struck}
            held = {(str(r[0]), r[1] or ""): r for r in D.QUARTER_RESULTS}
            hdr = schema.TABLES["quarter-results"].header
            for q in sorted(touched & closed):
                moved = [r for r in b.quarter_results(q)
                         if _moved(r, held.get((q, r["account"])), hdr)]
                results += [{**r, "note": f"Restated: {why}"} for r in moved]
                if moved:
                    journal.append(("freeze", "append", "quarter-results", len(moved),
                                    f"restated {q}",
                                    f"{len(moved)} restatement row(s) of {Book.quarter_label(q)}"))
            _append("quarter-results", results)
            commit.journal([j for j in journal if j[3]], at=at)
    finally:
        D.reload_store()
    return {"struck": sorted(struck), "quarter_nav": len(new_nav),
            "quarter_snapshots": len(new_snap), "quarter_results": len(results)}


def _way_in(keys, as_of: str) -> str:
    """WHERE A MISSING MARK COMES FROM, line by line (14 Oct 2026). The
    Price Refresh's closes of a past day read only the lines priced now (`current-prices.csv`), so
    a line closed since is out of its reach: its close is read in a session and banked through the
    marks door's `bank_closes()`. A rate, or no key, is the Price
    Refresh's."""
    priced = {str(r[0]) for r in schema.load("current-prices")}
    now = sorted(k for k in set(keys) if k in priced)
    gone = sorted(k for k in set(keys) if k not in priced)
    ways = [f"{', '.join(now)}: the Price Refresh, closes of {as_of}"] if now else []
    if gone:
        ways.append(f"{', '.join(gone)}: not priced now, so out of the Price Refresh's reach — read "
                    f"each close in a session and bank it through "
                    f"desk.doors.marks.bank_closes('{as_of}', prices=[...])")
    return "; ".join(ways) or "the Price Refresh"


def _unvalued(as_of: str, e: KeyError) -> str:
    """Why the book cannot be valued at `as_of`: EVERY gap at once, each with its way in, as
    `Book.valuation_gaps()` lists them; the engine's own refusal where it names none."""
    from portfusion.engine import Book
    gaps = Book().valuation_gaps(as_of)
    said = []
    if gaps["prices"]:
        said.append(f"no mark on or before {as_of} for {_way_in(gaps['prices'], as_of)}")
    if gaps["rates"]:
        said.append(f"no {', '.join(gaps['rates'])} rate on or before {as_of}: the Price Refresh")
    said += gaps["other"]
    return f"the book cannot be valued at {as_of}: " + ("; ".join(said) or str(e))


def _append_lines(rows: list[dict], struck: list[tuple]) -> dict:
    """`restate(lines_only=True)`'s write: the composition appended and journalled, in one
    envelope, and nothing else touched."""
    at = schema.record_instant()
    paths = [schema.TABLES["quarter-snapshots"].path, schema.TABLES["journal"].path]
    try:
        with commit.atomic(*paths):
            _append("quarter-snapshots", [{**r, "status": D.LIVE_MARK} for r in rows])
            journal = []
            for as_of in sorted({d for d, _ in struck}):
                names = ", ".join(a for d, a in struck if d == as_of)
                n = sum(1 for r in rows if r["as_of"] == as_of)
                journal.append(("freeze", "append", "quarter-snapshots", n, f"composed {as_of}",
                                f"{names}: {n} line row(s) composing {as_of}, from the engine; "
                                f"its net asset value stands"))
            commit.journal(journal, at=at)
    finally:
        D.reload_store()
    return {"struck": struck, "quarter_nav": 0, "quarter_snapshots": len(rows),
            "quarter_results": 0}


#: A frozen line's figures, which a restatement compares; its source may differ and move nothing.
_LINE = ("ticker", "qty", "price", "value", "cost")


def _figures(rows: list[dict], fields: tuple) -> list[tuple]:
    """Rows as their figures alone, sorted, so two sets compare whatever their order."""
    def cell(v):
        return None if v in (None, "") else round(float(v), 6) if isinstance(v, (int, float)) else v
    return sorted(tuple(str(cell(r.get(f))) for f in fields) for r in rows)


def _next_quarter_end(day: str) -> str:
    """The quarter end after `day`'s."""
    import pandas as pd
    return (pd.Timestamp(day) + pd.offsets.QuarterEnd(1)).date().isoformat()


def _moved(new: dict, was, hdr: list[str]) -> bool:
    """Does a quarter's freshly computed row differ from the newest held for it, on any figure?"""
    if was is None:
        return True
    was = dict(zip(hdr, was))
    for f in ("opening_nav", "capital_deployed", "return_income", "closing_nav", "gain", "return"):
        a, b = new[f], was[f]
        if (a is None) != (b in (None, "")) or (a is not None and round(float(a), 6) != round(float(b), 6)):
            return True
    return False


def _supersede(table: str, keys: set) -> list[tuple]:
    """Mark the live rows of these (as_of, account) keys superseded, in place: every other line
    keeps its bytes, and the count does not move. Returns the keys of the rows marked."""
    path = schema.TABLES[table].path
    hdr = schema.TABLES[table].header
    at, live = hdr.index("status"), D.LIVE_MARK
    original = path.read_bytes()
    eol = commit._eol(original)
    lines = original.decode("utf-8").split(eol.decode())
    gone, out = [], []
    for i, line in enumerate(lines):
        cells = next(csv.reader([line])) if i and line else None
        if cells and (cells[0], cells[1]) in keys and cells[at] == live:
            cells[at] = "superseded"
            gone.append((cells[0], cells[1]))
            line = commit._csv_line(cells)
        out.append(line)
    before = len(schema.load(table))
    path.write_bytes(eol.join(line.encode("utf-8") for line in out))
    if len(schema.load(table)) != before:
        raise Refused(f"{table}.csv changed its row count superseding rows")
    return gone


def _append(table: str, rows: list[dict]) -> None:
    """Rows onto one table, read back. IN THE FILE'S OWN LINE ENDING, through the Bench's helper:
    a text round trip would turn a CRLF file's lines into LF."""
    path = schema.TABLES[table].path
    before = len(schema.load(table))
    commit._append(path, path.read_bytes(),
                   [commit._csv_line(commit._rendered(table, r)) for r in rows])
    if len(schema.load(table)) != before + len(rows):
        raise Refused(f"{table}.csv did not read back {len(rows)} new row(s)")


def main(argv: list[str]) -> int:
    days = [a for a in argv if not a.startswith("--")]
    if len(days) != 1:
        log.info(__doc__)
        return 2
    p = plan(days[0])
    for table in ("quarter_snapshots", "quarter_nav"):
        log.info(f"\n  {table.replace('_', '-')}.csv — {len(p[table])} row(s)")
        for r in p[table]:
            log.info("    " + ", ".join(f"{v}" for v in r.values()))
    if not p["ready"]:
        log.info("\n  NOT READY:\n    " + "\n    ".join(p["why"] + p["off_date"]))
        return 1
    if "--write" not in argv:
        log.info(f"\n  Ready. Nothing written — add --write to freeze {p['as_of']}.")
        return 0
    try:
        done = write(p["as_of"])
    except Refused as e:
        log.info(f"\n  REFUSED — nothing written: {e}")
        return 1
    log.info(f"\n  Frozen {done['as_of']}: {done['quarter_snapshots']} snapshot row(s), "
          f"{done['quarter_nav']} net-asset-value row(s), {done['quarter_results']} result "
          f"row(s), journalled.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
