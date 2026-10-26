"""THE RESEARCH NOTES DOOR — a published note's rows, appended on one press from the Bench.

    owed()        each published note the book has no row for yet, with the codes it covers
    write(ref)    append one note's rows to research-notes.csv, journalled, or refuse

A STORE DOOR, the fifth under desk/ (`tests/desk/test_boundaries.py`), and it only APPENDS. Without
it nothing writes the table, and no note reaches a page.

WHAT A NOTE COVERS IS THE BOOK'S RULE, kept here once: every code of its company the book has
held since the record began (`Book.codes_held()`), matched as the research reader matches
(`research.for_ticker()`). A company held both as shares and as a spread bet has both codes
covered; a share line closed before the record began has none. A note on a company the book has
never held is owed nothing until it is held.

THE REF, ITS DATE AND ITS ADDRESS ARE THE RESEARCH REPO'S, read by `desk/intake/research.py`, and
never typed. A row on file is never rewritten here: a note withdrawn or redated is the research
repo's question, and `tests/record/test_record.py`'s ties name it.

THE BOOK DOES NOT NEED THE RESEARCH REPO. Without it `owed()` is empty and the Bench shows nothing.
"""
from __future__ import annotations

from portfusion.record import rules as D
from portfusion.record import schema
from portfusion.desk.doors import envelope
from portfusion.desk.intake import research

TABLE = "research-notes"


class Refused(Exception):
    """Nothing was written. Carries why."""


def owed(held: list[str] | None = None) -> list[dict]:
    """Each published note with a code it covers and no row for that code, newest first:
    {ref, date, url, title, company, kind, codes}. Empty when the research repo is absent.
    `held` is `Book.codes_held()`, passed by a caller that has a book already built."""
    if not research.available():
        return []
    if held is None:
        from portfusion import engine
        held = engine.Book().codes_held()
    on_file = {(t, ref) for t, entries in D.RESEARCH_NOTES.items() for ref, _, _ in entries}
    found: dict[str, dict] = {}
    for code in held:
        for n in research.for_ticker(code):
            if (code, n["ref"]) in on_file:
                continue
            note = found.setdefault(n["ref"], {
                "ref": n["ref"], "date": n["date"], "url": n["url"], "title": n["title"],
                "company": n["company"], "kind": n["kind"], "codes": []})
            note["codes"].append(code)
    return sorted(found.values(), key=lambda n: (n["date"], n["ref"]), reverse=True)


@envelope.held
def write(ref: str) -> dict:
    """Append `ref`'s owed rows, one per code it covers, and journal them. Raises `Refused`,
    writing nothing, if the note is owed no row: not in the research repo, or on file already."""
    note = next((n for n in owed() if n["ref"] == ref), None)
    if note is None:
        raise Refused(f"{ref} is owed no row: it is not a published note on a company the book "
                      f"has held, or its rows are on file already.")
    rows = [{"ticker": code, "ref": note["ref"], "published": note["date"], "url": note["url"]}
            for code in note["codes"]]
    path = schema.TABLES[TABLE].path
    before = len(schema.load(TABLE))
    with envelope.atomic(path, schema.TABLES["journal"].path):
        path.write_bytes(envelope.placed({TABLE: [envelope.rendered(TABLE, r) for r in rows]})[0][path])
        if len(schema.load(TABLE)) != before + len(rows):
            raise Refused(f"{TABLE}.csv did not read back {len(rows)} new row(s)")
        envelope.journal([("bench", "append", TABLE, len(rows), ref,
                           f"{ref} for {', '.join(note['codes'])}, from the research repo")])
    D.reload_store()
    return {"ref": ref, "codes": note["codes"], "written": len(rows)}
