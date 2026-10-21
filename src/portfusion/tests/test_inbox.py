"""The intake workbench, and the step that gets skipped.

_inbox/ exists because ii and HL have no retail API: a contract note or portfolio summary
from either reaches this book as a file. IG needs none — `--ig-events` reads the account
directly.

A document is DROPPED, WORKED, then ARCHIVED. The third step is the one that gets skipped,
and skipping it is not untidiness -- it removes the third limb of statement-grade. The rule
requires A NAMED REFERENCE THAT RETRIEVES THE FIGURE A SECOND TIME. The reference lives in
the row; _archive/statements/ is where it leads. A row whose evidence was left on the
workbench, or deleted from it, points at nothing.

THIS IS THE SAME SHAPE AS feeds/refresh.py, deliberately. That orchestrator exists because the
archive was the step that got skipped, so it archives BEFORE it prints the block inviting you
to overwrite. Here the archive comes last and cannot be enforced by ordering, so it is
enforced by the suite instead.
"""
import os
import pytest


@pytest.mark.audit
def test_the_workbench_is_clear():
    """A document resting in _inbox/ is UNFINISHED WORK.

    Either it has not been entered, or -- the dangerous one -- it has been entered and not
    archived, in which case the book looks complete while a row's evidence sits outside the
    audit trail and outside git.

    If this fails, FINISH THE INTAKE on the bench or take the document back out. Do not delete
    the guard, and do not delete the document: it leaves by being archived, or it goes back
    where it came from.
    """
    # THE LOADED BOOK'S WORKBENCH, not the checkout's: on the demo this watched this book's.
    from portfusion.record import schema
    inbox = schema.INBOX
    if not inbox.is_dir():
        return          # the workbench is optional; its discipline is not

    resting = sorted(f.name for f in inbox.iterdir()
                     if f.is_file() and not f.name.startswith("."))
    assert not resting, (
        "documents are still on the intake workbench:\n"
        + "".join(f"    _inbox/{n}\n" for n in resting)
        + "  Each is unentered, or entered and unarchived. Finish it on the bench, or move it\n"
          "  back out. Archiving is what gives a row's broker_ref something to retrieve.")


def test_the_inbox_is_not_a_second_home_for_the_audit_trail(repo_root):
    """_archive/statements/ is TRACKED; _inbox/ is not. Nothing may be committed to both.

    Defends against a document being archived by copying rather than moving, which would leave
    the same evidence under two paths -- one of them ignored, and therefore one of them liable
    to be edited or lost without the other noticing. `git mv`, never `cp`.
    """
    import subprocess
    tracked = subprocess.run(["git", "ls-files", "_inbox"], cwd=repo_root,
                             capture_output=True, text=True).stdout.split()
    unexpected = [t for t in tracked
                  if os.path.basename(t) != ".gitkeep"]
    assert not unexpected, (
        "these are committed under _inbox/, which is a workbench and not a record:\n"
        + "".join(f"    {t}\n" for t in unexpected)
        + "  A document belongs in _archive/statements/. Move it with `git mv`, not `cp`.")


@pytest.mark.audit
def test_no_bench_item_has_been_written_and_not_archived():
    """THE SHARPER VERSION OF THE GUARD ABOVE, for the bench.

    `_inbox/.bench/` holds one JSON note per event being worked. The dot keeps it clear of
    "the workbench is clear" above, and that is deliberate rather than a dodge: an item
    MID-WORK is legitimate transient state — evidence half-gathered, reasoning not yet
    written — and failing the suite for it would make the bench unusable for anything that
    takes more than one sitting.

    WHAT IS NOT LEGITIMATE IS THE SAME DANGEROUS STATE THE DOCUMENT RULE GUARDS: written and
    not archived. At that point the record has the row, the book looks complete, and the
    evidence has not been moved to where the row's reference can retrieve it. That is the
    failure this suite exists to catch, and it is worth catching one state earlier than a
    document resting in the folder — by then the row is already in.
    """
    import json

    from portfusion.record import schema
    bench = schema.INBOX / ".bench"             # the loaded book's
    if not bench.is_dir():
        return

    stranded = []
    for path in sorted(bench.glob("*.json")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            stranded.append(f"{path.name}: unreadable ({e})")
            continue
        if item.get("state") == "written":
            stranded.append(f"{path.name}: {item.get('title', '?')} — rows are IN THE RECORD, "
                            f"document not archived")

    assert not stranded, (
        "bench items are written but not archived:\n"
        + "".join(f"    {s}\n" for s in stranded)
        + "  The row is in the store and its evidence is not in _archive/statements/, so the\n"
          "  broker_ref points at nothing. Archive the document, or reverse the row.")


def test_a_broker_export_that_is_not_utf8_still_reads(tmp_path):
    """HL'S EXPORTS COULD NOT BE OPENED AT ALL.

    The CSV branch decoded as strict `utf-8-sig` with no fallback, and a UK broker's
    spreadsheet export is CP1252: HL writes the pound sign as the single byte 0xA3, which is
    not valid UTF-8. HL's downloads raised `UnicodeDecodeError` before anything
    could read them.

    AND THE ONE-WORD FIX WOULD HAVE BEEN WORSE. `errors="replace"` opens the file and corrupts
    it in the one place it matters — 0xA3 sits IMMEDIATELY BEFORE A FIGURE in these documents,
    so the reader would be handed "?12,345.67" to quote and verify against. This asserts the
    figure survives intact, not merely that the file opens.
    """
    from portfusion.desk.intake import read_document as R

    p = tmp_path / "hl-export.csv"
    p.write_bytes('Account,Total value\n"Stocks & Shares ISA","£12,345.67"\n'
                  .encode("cp1252"))
    doc = R.extract_file(p)
    assert doc["encoding"] == "cp1252", f"read as {doc['encoding']!r}"
    assert "£12,345.67" in doc["text"], \
        f"the figure did not survive the decode: {doc['text']!r}"


def test_a_document_in_no_known_encoding_says_so_rather_than_guessing(tmp_path):
    """A figure read through the wrong encoding loads cleanly and is wrong, which is the worst
    failure available here. Refusing names the file and says what to do about it.

    0x81 and 0x8D are undefined in CP1252 and invalid in UTF-8, so neither codec can claim it."""
    import pytest
    from portfusion.desk.intake import read_document as R
    assert R.ENCODINGS[0].startswith("utf-8"), "UTF-8 must be tried before anything lossy"

    p = tmp_path / "mystery.csv"
    p.write_bytes(b"Account,Value\n\x81\x8d,123\n")
    with pytest.raises(ValueError) as e:
        R._decode(str(p))
    assert "mystery.csv" in str(e.value), "the refusal does not name the file"
    assert "re-export" in str(e.value).lower(), "the refusal does not say what to do"


@pytest.mark.audit
def test_a_working_note_and_its_document_are_never_separated():
    """The two silent states, and both had happened before this was written.

    A bench note in `_inbox/.bench/` and the document it is about are one piece of work. Either
    half without the other is debris that no guard above catches, because both of those look at
    only one side:

      * a note without its document — the document was archived or moved by some route that did
        not close the note. Four sat like this after the ii SIPP rehearsal was worked by hand,
        every one reading `open`, so the bench showed four jobs outstanding and the desk looked
        as though nothing had been done. `test_no_bench_item_has_been_written_and_not_archived`
        misses it: these never reached `written`.

      * a document without its note — what `bench.discard()` leaves behind, since it removes the
        note and its docstring promises it never touches a document. The document then rests on
        the workbench with nothing tracking it. "The workbench is clear" above does fire on it,
        eventually, but says only that something is resting there and not that its note is gone.

    An item need not have a document and that is not a gap — a spread bet is evidenced by IG's
    deal reference, which the row itself carries. Only items naming one are checked.

    The exit this guard assumes is `desk/intake/withdraw.py`. Without it a document that turned out
    not to be needed has no route out, and the honest half of this check is unsatisfiable.
    """
    import json

    from portfusion.record import schema
    inbox = schema.INBOX                        # the loaded book's
    bench = inbox / ".bench"

    documents = {p.name for p in inbox.glob("*") if p.is_file() and not p.name.startswith(".")}

    noted, orphaned = set(), []
    if bench.is_dir():
        for path in sorted(bench.glob("*.json")):
            item = json.loads(path.read_text(encoding="utf-8"))
            name = (item.get("document") or {}).get("name")
            if not name:
                continue
            noted.add(name)
            if name not in documents:
                orphaned.append(f"{path.name}: {item.get('state', '?')} — its document "
                                f"{name!r} is not on the workbench")

    unnoted = sorted(documents - noted)

    assert not orphaned, (
        "these bench notes have lost their document:\n"
        + "".join(f"    {s}\n" for s in orphaned)
        + "  The work finished by a route that did not close the note. Discard it if the\n"
          "  document was archived, or withdraw the pair together.")
    assert not unnoted, (
        f"these documents are on the workbench with no bench note: {unnoted}. Something\n"
        "  removed the note and left the document — bench.discard() does exactly that. Open\n"
        "  an item on it, or withdraw it with desk/intake/withdraw.py.")
