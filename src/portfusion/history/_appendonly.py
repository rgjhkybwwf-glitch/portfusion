"""
ONE HISTORY CSV, shared by the three histories.

Three copies of a parse rule are three parse rules.

`archive()` and `check()` are NOT shared. Each asks the record for its live set in the record's
own vocabulary (`D.CURRENT_PRICES`, `D.fx_rows`), and the printing differs by what is printed;
neither is worth an indirection. WHAT A SAME-DAY READ DOES IS SHARED (`restruck()`): a price, a
rate and a statement are all read again.

The build must not import this, and each history keeps a test saying so. The engine reads the
same files with pandas for a different job — frames for analysis, not rows for appending.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import os
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Sequence

from portfusion.record import rules as D
from portfusion.record import schema


class AppendOnlyCSV:
    """One history file: read it, sort it, write it, and say what is already in.

    `numeric` names the columns to coerce to float. `nullable` says whether a blank in one of
    them is a legitimate absence (None) or an error worth raising — accounts carry blanks by
    design, a price or a rate does not.

    `sort_key` is the file's canonical order, applied on every save. Sorting on write is what
    lets a row appended by hand at the foot of the file land in the right place.

    `identity` names the columns that make a row unique, so `known()` can answer whether a
    mark is already banked. A history with no natural identity leaves it None.

    `places` says how each numeric column is written, as the schema's `MONEY` or `QUOTE` says it
    for the record's own tables: every save writes them so (`schema.figure()`).

    `series` names the columns that make one line's marks — a price's `mark_key` — for a
    history that keeps only the marks a figure can take (`kept()`). None keeps every row: an
    account's history is its value series, and What Changed may take a rate of any day.
    """

    def __init__(self, name: str, fields: list[str], numeric: tuple, sort_key,
                 identity: tuple | None = None, nullable: bool = False,
                 figure: str | tuple | None = None, places: dict | None = None,
                 series: tuple | None = None) -> None:
        # A FILENAME, never a folder: the folder is whichever store `schema.STORE` points at
        # when the file is used, so the histories follow the record when a test moves it.
        self._name = str(name)
        self.fields = fields
        self.numeric = numeric
        self.sort_key = sort_key
        self.identity = identity
        self.nullable = nullable
        # THE FIGURE A ROW STATES — `price`, `rate`, or an account's several — which a same-day
        # read compares. None for a history that holds none (`restruck()` is then never asked).
        self.figure = (figure,) if isinstance(figure, str) else figure
        self.places = places or {}
        self.series = series
        # The fields their figures are held to on reading, built once.
        self._held = {k: schema.Field(k, "float", **how) for k, how in self.places.items()}

    @property
    def path(self) -> str:
        """This history's file, in whatever store the record is currently reading.

        Side effects: none.
        """
        return str(D.store_dir() / self._name)

    def load(self) -> list[dict]:
        """Every row on file, in file order, with the numeric columns coerced.

        Returns [] when the file does not exist — a history that has not started yet is not
        an error. Side effects: none.
        """
        if not os.path.exists(self.path):
            return []
        with open(self.path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        # A ROW THAT DOES NOT FIT THE HEADER IS REFUSED HERE, where nothing has been written yet.
        # Read through, an extra cell arrives under the key None and a missing one as the value
        # None, and either would only surface at `save()` — after the file had been opened.
        if list(reader.fieldnames or []) != list(self.fields):
            raise ValueError(f"{self._name}: the header is {reader.fieldnames}, "
                             f"not {list(self.fields)}")
        for i, r in enumerate(rows, 2):
            if None in r or None in r.values():
                raise ValueError(f"{self._name} line {i}: {len(self.fields)} cells expected, "
                                 f"the row does not have them")
        for i, r in enumerate(rows, 2):
            for k in self.numeric:
                if self.nullable and r[k] in ("", None):
                    r[k] = None
                    continue
                if k in self._held:
                    try:
                        schema._held_to_places(self._held[k], r[k])
                    except ValueError as e:
                        raise ValueError(f"{self._name} line {i}, {k}: {e}") from None
                r[k] = float(r[k])
        return rows

    def save(self, rows: list[dict]) -> list[dict]:
        """Write every row, in canonical order. Returns the rows as written.

        Side effects: REPLACES the file. Callers append to what load() gave them; nothing
        here edits or drops a row. The one caller that drops one is `bank()`, for a row a later
        read of its own day replaces (`restruck()`) and a live read no figure can take (`kept()`).

        THE FILE ON DISK IS EITHER THE OLD ONE OR THE NEW ONE, never a truncated one. The rows
        are rendered whole first — a row the writer refuses raises before anything is touched —
        then land in a file beside this one, which `os.replace` swaps in. The new file keeps the
        old one's line ending and permissions.
        """
        rows = sorted(rows, key=self.sort_key)
        eol = "\n"
        if os.path.exists(self.path):
            with open(self.path, "rb") as fh:
                eol = "\r\n" if b"\r\n" in fh.readline() else "\n"
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=self.fields, lineterminator=eol)
        w.writeheader()
        w.writerows({**r, **{c: schema.figure(r[c], **how) for c, how in self.places.items()
                             if r.get(c) is not None and r[c] != ""}} for r in rows)
        folder = os.path.dirname(self.path)
        fd, tmp = tempfile.mkstemp(prefix=f".{self._name}.", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
                fh.write(buf.getvalue())
            if os.path.exists(self.path):
                os.chmod(tmp, os.stat(self.path).st_mode & 0o7777)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return rows

    def key(self, row: dict) -> tuple:
        """One row's identity tuple."""
        return tuple(row[c] for c in self.identity)  # pyright: ignore[reportOptionalIterable]

    def known(self, rows: Iterable[dict]) -> set:
        """The identities already banked. Side effects: none."""
        return {self.key(r) for r in rows}

    def unbanked(self, live_marks: list[dict], rows: list[dict] | None = None) -> list[dict]:
        """Which of `live_marks` are NOT yet on file. Silent when there are none — a warning
        that fires on a healthy run is furniture, not a check."""
        have = self.known(self.load() if rows is None else rows)
        return [m for m in live_marks if self.key(m) not in have]

    # ---- A SAME-DAY READ: the marks' one rule, for a price and a rate alike --------------------
    #
    # A FIGURE ON FILE IS REPLACED, NEVER KEPT BESIDE ITS REPLACEMENT. A later read of the same
    # day — another live read, that day's close, a statement put right — takes the row's place,
    # and git keeps what the row said.

    @staticmethod
    def outranked(was: dict, mark: dict) -> bool:
        """Does the row on file outrank this mark for their shared day? A close outranks a live
        read taken during that day, so once `desk/doors/marks.py:bank_closes()` has filed one,
        the live read still sitting in the live table must not strike back over it."""
        return was.get("struck") == "close" and mark.get("struck") == "live"

    def _same(self, was: dict, mark: dict) -> bool:
        """Do the row on file and this mark say the same of their day? Compared on every figure
        BOTH state: an account's row on file can carry what no reading does — a statement's
        notional — and that is not a second reading of the day."""
        return all(was[c] == mark[c] for c in self.figure  # pyright: ignore[reportOptionalIterable]
                   if was[c] is not None and mark[c] is not None)

    @staticmethod
    def promoted(was: dict, mark: dict) -> bool:
        """Is this mark its day's close, where the row on file is that day's live read? Then it
        replaces the live read AT ANY FIGURE, even a close equal to the last live read, or the day
        goes on reading as a live read, owed its close."""
        return was.get("struck") == "live" and mark.get("struck") == "close"

    def _restrikes(self, was: dict, mark: dict) -> bool:
        """Does this mark take the place of the row on file for its day? At another figure, or as
        the close of a day held by a live read — and never a live read over its day's close. A
        re-read at the SAME figure is not a re-strike, or every read of a closed market would
        replace itself."""
        return (not self._same(was, mark) or self.promoted(was, mark)) and not self.outranked(was, mark)

    def restruck(self, rows: list[dict], live: list[dict]) -> list[dict]:
        """The rows on file a SAME-DAY re-strike replaces, so the history agrees with the live
        table about a day read twice. Side effects: none; the caller drops them and saves."""
        on_file = {self.key(r): r for r in rows}
        return [was for m in live
                if (was := on_file.get(self.key(m))) is not None and self._restrikes(was, m)]

    def unstruck(self, live: list[dict], rows: list[dict] | None = None) -> list[dict]:
        """The live marks NOT on file at their own figure: a mark of an unbanked day, or a
        re-struck one whose day is on file at another figure. A live read its day's close
        outranks needs no banking: the close is that day's mark. Side effects: none."""
        on_file = {self.key(r): r for r in (self.load() if rows is None else rows)}
        return [m for m in live
                if (was := on_file.get(self.key(m))) is None or self._restrikes(was, m)]

    def bank(self, live: list[dict]) -> tuple[list[dict], list[dict]]:
        """Append the live marks: (new, replaced). Idempotent at the SAME figure — safe to run
        twice, and safe to run late, so long as the live table has not moved on.

        A same-day mark at a DIFFERENT figure takes the place of the row on file (`restruck()`);
        a live read of a day whose close is on file is not banked at all (`outranked()`). Side
        effects: REPLACES the file when anything changed.
        """
        rows = self.load()
        replaced = self.restruck(rows, live)
        rows = [r for r in rows if not any(r is d for d in replaced)]
        new = self.unbanked(live, rows)
        if new or replaced:
            self.save(self.kept(rows + new, live))
        return new, replaced

    # ---- WHAT A HISTORY KEEPS: the marks a figure can take -------------------------------------
    #
    # A live read between the days the book is valued on drives no figure, and every refresh adds
    # one per line. Kept, per series: every row not struck live; the mark each valued day takes —
    # the newest on or before it (`Book._marks_at()`) and the nearest within
    # `rules.CLOSE_CHECK_WINDOW_DAYS`, the earlier on a tie (a freeze's window); the live table's
    # own and the one before it, which What Changed sets it against; and the two newest. Git keeps
    # the rest.

    def kept(self, rows: list[dict], live: Sequence[dict] = ()) -> list[dict]:
        """`rows` less the live reads no figure can take. Side effects: none."""
        if self.series is None or not rows:
            return rows
        held = self.known(live)
        live_on = {tuple(m[c] for c in self.series): m["date"] for m in live}
        days = [_dt.date.fromisoformat(d)
                for d in valued_days(min(r["date"] for r in rows), max(r["date"] for r in rows))]
        lines = defaultdict(list)
        for r in rows:
            lines[tuple(r[c] for c in self.series)].append(r)
        keep = set()
        for series, line in lines.items():
            line.sort(key=lambda r: r["date"])
            upto = [r for r in line if r["date"] <= live_on.get(series, line[-1]["date"])]
            keep |= {id(r) for r in line[-2:] + upto[-2:]}
            on = [(_dt.date.fromisoformat(r["date"]), r) for r in line]
            for day in days:
                before = [r for d, r in on if d <= day]
                if before:
                    keep.add(id(before[-1]))
                near = [(abs((d - day).days), d, id(r)) for d, r in on
                        if abs((d - day).days) <= D.CLOSE_CHECK_WINDOW_DAYS]
                if near:
                    keep.add(min(near)[2])
        return [r for r in rows
                if r.get("struck") != "live" or id(r) in keep or self.key(r) in held]


def valued_days(first: str, last: str) -> list[str]:
    """The days the book is valued on, for marks from `first` to `last`: every quarter end from the
    year before `first`, whose last a freeze's window reaches past; each opening — the record's and
    each account's — with the day before it, where an opening is valued; and each account's current
    reading, which the reconciliation values at its own day."""
    ends = [f"{y}-{md}" for y in range(int(first[:4]) - 1, int(last[:4]) + 1)
            for md in ("03-31", "06-30", "09-30", "12-31")]
    opens = [str(o)[:10] for o in (D.RECORD_BEGINS, *D.ACCOUNT_BEGINS.values()) if o]
    eve = [(_dt.date.fromisoformat(o) - _dt.timedelta(days=1)).isoformat() for o in opens]
    read = [str(r.as_of)[:10] for r in D.ac_rows if r.as_of]
    return sorted(set(ends) | set(opens) | set(eve) | set(read))
