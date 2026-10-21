"""
ONE APPEND-ONLY CSV, shared by the three histories.

They were the same module written three times, and three copies of a parse rule are three
parse rules: one coerced blanks to None while two raised on them.

`archive()` and `check()` are NOT shared. Each asks the record for its live set in the record's
own vocabulary (`D.CURRENT_PRICES`, `D.fx_rows`), and the printing differs by what is printed;
neither is worth an indirection. WHAT A SAME-DAY READ DOES IS SHARED (`restruck()`): a price and a
rate are both marks, and two copies of that rule had already become one rule and none.

The build must not import this, and each history keeps a test saying so. The engine reads the
same files with pandas for a different job — frames for analysis, not rows for appending.
"""
from __future__ import annotations

import csv
import io
import os
import tempfile

from portfusion.record import rules as D


class AppendOnlyCSV:
    """One append-only history file: read it, sort it, write it, and say what is already in.

    `numeric` names the columns to coerce to float. `nullable` says whether a blank in one of
    them is a legitimate absence (None) or an error worth raising — accounts carry blanks by
    design, a price or a rate does not.

    `sort_key` is the file's canonical order, applied on every save. Sorting on write is what
    lets a row appended by hand at the foot of the file land in the right place.

    `identity` names the columns that make a row unique, so `known()` can answer whether a
    mark is already banked. A history with no natural identity leaves it None.
    """

    #: The lifecycle value a lookup or a series should see; a superseded row stays on file and
    #: is not it. Defined once, as `rules.LIVE_MARK`, because the engine needs it and cannot
    #: import this package. A history with no `status` column has no lifecycle: `known()` treats
    #: every row as live.
    LIVE = D.LIVE_MARK

    def __init__(self, name: str, fields: tuple, numeric: tuple, sort_key,
                 identity: tuple | None = None, nullable: bool = False,
                 figure: str | tuple | None = None) -> None:
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
        for r in rows:
            for k in self.numeric:
                if self.nullable and r[k] in ("", None):
                    r[k] = None
                else:
                    r[k] = float(r[k])
        return rows

    def save(self, rows: list[dict]) -> list[dict]:
        """Write every row, in canonical order. Returns the rows as written.

        Side effects: REPLACES the file. Callers append to what load() gave them; nothing
        here edits or drops a row. The callers that drop one are the mark histories', for a
        live read a later read of its own day replaces (`restruck()`).

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
        w.writerows(rows)
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
        return tuple(row[c] for c in self.identity)

    def known(self, rows: list[dict]) -> set:
        """The identities already banked and still live. Side effects: none."""
        return {self.key(r) for r in rows if r.get("status", self.LIVE) == self.LIVE}

    def unbanked(self, live_marks: list[dict], rows: list[dict] | None = None) -> list[dict]:
        """Which of `live_marks` are NOT yet on file. Silent when there are none — a warning
        that fires on a healthy run is furniture, not a check."""
        have = self.known(self.load() if rows is None else rows)
        return [m for m in live_marks if self.key(m) not in have]

    # ---- A SAME-DAY READ: the marks' one rule, for a price and a rate alike --------------------
    #
    # A LIVE READ IS NOT CORRECTED, IT IS REPLACED (12 Oct 2026). A live
    # read is an instant, and a later read of the same day — another live read, or that day's
    # close — is the same day seen later, not a fix of something wrong; nothing reads the earlier
    # one, so it leaves the file. A close, a statement's figure or a typed one that a different
    # figure replaces WAS wrong: a correction, superseded and kept, never edited.

    @staticmethod
    def outranked(was: dict, mark: dict) -> bool:
        """Does the row on file outrank this mark for their shared day? A close outranks a live
        read taken during that day, so once `desk/doors/marks.py:bank_closes()` has filed one,
        the live read still sitting in the live table must not strike back over it."""
        return was.get("struck") == "close" and mark.get("struck") == "live"

    def _same(self, was: dict, mark: dict) -> bool:
        """Do the row on file and this mark say the same of their day? Compared on every figure
        BOTH state: an account's row on file can carry what no reading does — the cash off a
        ledger, a statement's notional — and that is not a second reading of the day."""
        return all(was[c] == mark[c] for c in self.figure
                   if was[c] is not None and mark[c] is not None)

    @staticmethod
    def promoted(was: dict, mark: dict) -> bool:
        """Is this mark its day's close, where the row on file is that day's live read? Then it
        replaces the live read AT ANY FIGURE: a close that happened to equal the last live read
        was skipped as "the same", and the day went on reading as a live read, owed its close."""
        return was.get("struck") == "live" and mark.get("struck") == "close"

    def _on_file(self, rows: list[dict]) -> dict:
        return {self.key(r): r for r in rows if r.get("status", self.LIVE) == self.LIVE}

    def restruck(self, rows: list[dict], live: list[dict]) -> tuple[list[dict], list[dict]]:
        """The on-file rows a SAME-DAY re-strike replaces: (dropped, superseded).

        Without this, a second read of one day found itself already banked and appended nothing,
        leaving the history disagreeing with the live table about that day. A live read on file
        is DROPPED; anything else on file is SUPERSEDED, keeping its date and provenance. Either
        way `known()` stops seeing it, and the new one lands. A re-read at the SAME figure is not
        a re-strike, or every read of a closed market would replace itself.

        Side effects: marks the rows it supersedes, in place. The caller drops the rest and saves.
        """
        on_file = self._on_file(rows)
        dropped, superseded = [], []
        for m in live:
            was = on_file.get(self.key(m))
            if (was is None or (self._same(was, m) and not self.promoted(was, m))
                    or self.outranked(was, m)):
                continue
            if was.get("struck") == "live":
                dropped.append(was)
                continue
            # A correction: the status moves; the provenance does not.
            was["status"] = "superseded"
            superseded.append(was)
        return dropped, superseded

    def outranked_on_file(self, rows: list[dict], mark: dict) -> bool:
        """Is this mark a live read of a day whose close is already on file?"""
        was = self._on_file(rows).get(self.key(mark))
        return was is not None and self.outranked(was, mark)

    def unstruck(self, live: list[dict], rows: list[dict] | None = None) -> list[dict]:
        """The live marks NOT on file at their own figure: a mark of an unbanked day, or a
        re-struck one whose day is on file at another figure. A live read its day's close
        outranks needs no banking: the close is that day's mark. Side effects: none."""
        on_file = self._on_file(self.load() if rows is None else rows)
        return [m for m in live
                if (was := on_file.get(self.key(m))) is None
                or ((not self._same(was, m) or self.promoted(was, m))
                    and not self.outranked(was, m))]

    def bank(self, live: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
        """Append the live marks: (new, dropped, superseded). Idempotent at the SAME figure —
        safe to run twice, and safe to run late, so long as the live table has not moved on.

        A same-day mark at a DIFFERENT figure replaces a live read on file and supersedes
        anything else (`restruck()`). A live read of a day whose close is on file is not banked
        at all (`outranked()`). Side effects: REPLACES the file when anything changed.
        """
        rows = self.load()
        dropped, superseded = self.restruck(rows, live)
        rows = [r for r in rows if not any(r is d for d in dropped)]
        new = [m for m in self.unbanked(live, rows) if not self.outranked_on_file(rows, m)]
        if new or dropped or superseded:
            self.save(rows + new)
        return new, dropped, superseded
