"""THE WITHDRAWAL — a document that was not needed, back out of the workbench.

WHY IT IS ITS OWN MODULE. `dropoff.py` is the door IN, and
`test_the_drop_off_has_no_way_to_make_a_document_LEAVE` proves on its syntax tree that it can
never become the door out — its one write is `write_bytes`, and nothing that moves or removes.
Putting the exit there would have meant opening that test to a move, which is gutting a guard
to do the exact thing the guard forbids. So the exit is a separate door with its own rules, and
`tests/desk/test_boundaries.py:WRITERS` names it.

THE GAP IT CLOSES. `bench.discard()` removes the working NOTE and its docstring promises it never
touches a document; the drop-off cannot make one leave. Without this, a document dropped on the
bench and then not needed had two exits, both wrong: archive it as evidence, which is false when
it was never used, or leave it stranded and fail `test_inbox.py::test_the_workbench_is_clear`
for ever. Or it goes somewhere temporary that gets cleaned, which is `docs/intake.md`'s "never
delete a document from here" by a slower route.

THE SYMMETRY IS WITH commit.py, which is the other terminal route: both move the document and
close the note in one breath, and both copy the note to `_archive/bench/` so the tracked record
says what became of it. The difference is only which of the two endings it was.

    commit.py    the document produced rows. It goes to _archive/statements/ as evidence.
    withdraw.py  the document produced nothing. It goes back out of the repo.

WHERE IT GOES IS OUT OF THE REPO, and that is the whole of the destination rule.
`docs/intake.md` already sanctions it — a document leaves by being archived, or it goes back
where it came from. A withdrawn document is not evidence, so it must not come to rest anywhere
the record keeps evidence, and this refuses any path inside the repo for that reason.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from portfusion.record import schema
from portfusion.desk.intake.dropoff import Refused, safe_name


#: Where a withdrawn document goes when the operator names nowhere. "Back where it came from"
#: for a file that reached the workbench from a browser download, which is how every ii and HL
#: document arrives.
DEFAULT_DESTINATION = Path.home() / "Downloads"


def _archive_dir():
    """`_archive/bench/`, asked rather than restated — commit.py owns it."""
    from portfusion.desk.doors import commit
    return commit.archive()


def destination_for(raw: str | None) -> Path:
    """The directory a withdrawn document may land in, or a refusal.

    Refuses anywhere inside the repo, which is the rule this module exists to keep. A withdrawn
    document is not evidence; `_archive/statements/` is where evidence lives and a file resting
    there is citable by a row. Nor may it go back into `_inbox/`, which would be a no-op wearing
    the name of an exit.

    Side effects: none — it only resolves and checks.
    """
    where = Path(raw).expanduser() if raw else DEFAULT_DESTINATION
    where = where.resolve()

    if not where.is_dir():
        raise Refused(f"{where} is not a directory that exists. Name one that does — a "
                      f"withdrawal moves a document, it does not create a place to put it")

    # The book, the app's own folder, and the checkout when it runs from one.
    for inside in {p.resolve() for p in (schema.BOOK, schema.APP, schema.ROOT) if p}:
        if where != inside and inside not in where.parents:
            continue
        raise Refused(f"{where} is inside the repository or the book. A withdrawn document is "
                      f"NOT evidence "
                      f"and must not rest where the record keeps evidence — it goes back where "
                      f"it came from, outside the book")
    return where


def withdraw(name: str, destination: str | None = None, why: str = "") -> dict:
    """Send a document that was not needed out of `_inbox/`, and close its bench note.

    The document is moved, never deleted. `docs/intake.md` is absolute about that and this is
    the route that makes the rule keepable rather than merely stated.

    `why` is recorded on the archived note. A withdrawal without a reason is the state that
    reads, six months later, as a document somebody lost.

    Returns what happened. Raises `Refused` with the rule that stopped it, having moved nothing.
    """
    from portfusion.desk.intake import bench

    document = safe_name(name)
    inbox = schema.inbox()
    source = inbox / document
    if source.resolve().parent != inbox.resolve():
        raise Refused(f"{document!r} does not resolve inside _inbox/")
    if not source.is_file():
        raise Refused(f"{document!r} is not on the workbench")

    where = destination_for(destination)
    target = where / document

    # The common case is that it is already there, and that is not a clash. `dropoff.accept()`
    # writes BYTES into `_inbox/` — it copies, it does not move — so the original never left
    # the folder it was downloaded to. Withdrawing is then removing a working COPY.
    #
    # BYTE-IDENTICAL IS THE WHOLE OF THE TEST, and it is what makes this legal rather than a
    # judgement. `docs/intake.md` forbids deleting a document because deleting it destroys
    # the evidence a row points at; when the same bytes are provably sitting at the
    # destination, nothing is destroyed. Anything less than identical is a different document
    # wearing the same name, and that is refused exactly as an overwrite is.
    returning = False
    if target.exists():
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            raise Refused(f"{document!r} already exists in {where} and is NOT the same file. "
                          f"Nothing here overwrites a document — move or rename the one "
                          f"already there")
        returning = True

    item = next((i for i in bench.all_items()
                 if (i.get("document") or {}).get("name") == document), None)

    # THE NOTE IS ARCHIVED BEFORE THE DOCUMENT MOVES: a note that cannot be archived moves nothing.
    archived_to = None
    if item is not None:
        item["state"] = "withdrawn"
        # `~`-RELATIVE: the note is archived in the book's git, which carries no Mac's user name.
        home = Path.home().resolve()
        item["withdrawn_to"] = (f"~/{target.relative_to(home)}" if home in target.parents
                                else str(target))
        item["withdrawn_why"] = why
        item["withdrawn_how"] = ("returned — an identical copy was already there, so the "
                                 "workbench copy was removed" if returning else "moved")
        arch = _archive_dir()
        arch.mkdir(parents=True, exist_ok=True)
        path = arch / f"{item['id']}.json"
        path.write_text(json.dumps(item, indent=2), encoding="utf-8")
        archived_to = str(path)

    if returning:
        source.unlink()
    else:
        shutil.move(str(source), str(target))
    if item is not None:
        bench.discard(item["id"])

    return {"document": document, "moved_to": str(target), "returned": returning,
            "item": (item or {}).get("id"), "archived_to": archived_to, "why": why}
