"""THE RESEARCH REPO, READ ONLY — what notes exist, and what ref each one has.

    from portfusion.desk.intake import research
    research.notes()              # every published note, newest first
    research.for_ticker("HALV")    # the ones naming that ticker

WHY THIS EXISTS. A note's ref has to come from somewhere, and the research repo's frontmatter is
the source of truth for it, as for a note's date and disclosed position. If a note's position
contradicts the book, stop and ask: nothing in either build can check it. So the research notes door (`desk/doors/research_notes.py`) reads
refs here rather than anyone inventing one.

THE RULES ON A REF ARE NOT THIS MODULE'S, and it must never act as though they were: never
reused, never computed, gaps are legitimate. They belong to the research repository, which
is the authority. THIS MODULE ONLY REPORTS
WHAT IS ON DISK. If a ref looks wrong, the answer is to look at the note, not to correct it here.

READ-ONLY, AND THAT IS STRUCTURAL. There is no write path in this file, and it is not in
`WRITERS` (tests/desk/test_boundaries.py), so adding one fails the suite. The research repo
is a different project with its own git history; this one has no business editing it.

THE BOOK MUST BUILD WITHOUT IT. A book's research repo is optional, a setting it may leave
empty. Every function here returns empty rather than raising when the
repo is absent, so a checkout on another machine builds a correct book and simply cannot
offer you a ref to pick.
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import re

from portfusion.record import rules

# WHERE THE NOTES LIVE: the book's `research_repo` (a leading `~` is the home folder), or None
# when the book names none, and then there are no notes to offer. A module attribute, so the
# tests can point it at a fixture rather than at the owner's actual research repo — a test that
# reads the real one would pass or fail on whatever was published that week, which is not a test.
REPO: pathlib.Path | None = (pathlib.Path(rules.SETTINGS["research_repo"]).expanduser()
                             if rules.SETTINGS.get("research_repo") else None)
INSIGHTS = "src/content/insights"
#: Where a published note is read, the book's `insights_url`, the note's slug appended.
INSIGHTS_URL: str = rules.SETTINGS.get("insights_url") or ""

# The frontmatter keys this book cares about. The notes carry more — deck, scope, stat, dcf —
# and none of it belongs here: this is an index of what exists, not a copy of the research.
_WANTED = ("ref", "date", "ticker", "companyTicker", "company", "title", "position", "kind")

_SCALAR = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$')


def _frontmatter(text: str) -> dict:
    """The leading `---` block, as flat strings. Deliberately NOT a YAML parser.

    The notes' frontmatter is flat except for `stat:`, which is a nested map this book does not
    want — so indented lines are skipped rather than parsed. Pulling in a YAML dependency to
    read six keys would put a third-party package in the path of the record for no gain, and
    record/schema.py's "imports nothing third-party" habit is the house style for a reason.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out = {}
    for line in text[3:end].splitlines():
        if not line or line[0].isspace():        # nested (stat:) or blank — not wanted
            continue
        m = _SCALAR.match(line)
        if m and m.group(1) in _WANTED:
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[m.group(1)] = v
    return out


def _slug_url(path: pathlib.Path) -> str:
    """The note's page, or blank when the book names no `insights_url`."""
    return f"{INSIGHTS_URL.rstrip('/')}/{path.stem}/" if INSIGHTS_URL else ""


def notes() -> list[dict]:
    """Every published note, newest first. Empty if the repo is not on this machine.

    `_example.mdx` is skipped: it is a template carrying a specimen ref, and offering it as a
    real note is exactly the kind of thing that ends up in a record.
    """
    if REPO is None or not (folder := REPO / INSIGHTS).is_dir():
        return []
    out = []
    for path in sorted(folder.glob("*.mdx")):
        if path.name.startswith("_"):
            continue
        try:
            fm = _frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if not fm.get("ref"):
            continue                              # not a note this book can cite
        try:
            date = _dt.date.fromisoformat(fm.get("date", ""))
        except ValueError:
            date = None
        out.append({
            "ref": fm["ref"],
            "date": date.isoformat() if date else "",
            "ticker": fm.get("companyTicker") or "",
            "exchange_ticker": fm.get("ticker") or "",
            "company": fm.get("company") or "",
            "title": fm.get("title") or "",
            "position": fm.get("position") or "",
            "kind": fm.get("kind") or "",
            "url": _slug_url(path),
            "file": str(path),
        })
    return sorted(out, key=lambda n: (n["date"], n["ref"]), reverse=True)


def for_ticker(ticker: str) -> list[dict]:
    """Notes naming this ticker. The book's codes carry a mode suffix — ORLA and ORLA SB are
    one company — so the suffix is stripped before matching."""
    base = (ticker or "").split()[0].upper()
    return [n for n in notes() if n["ticker"].upper() == base]


def by_ref() -> dict[str, dict]:
    return {n["ref"]: n for n in notes()}


def available() -> bool:
    """Whether the research repo is on this machine at all. The bench asks before offering."""
    return REPO is not None and (REPO / INSIGHTS).is_dir()
