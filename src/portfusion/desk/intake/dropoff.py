"""THE DROP-OFF — a document, from the browser onto the intake workbench.

WHY IT EXISTS. **ii and HL have no retail API**, so their documents reach this book as files
(IG needs none — `python3 -m portfusion.feeds.ig --ig-events` reads the account directly). The
document is already beside the browser; switching to Finder to drop it into `_inbox/` is pure
ceremony.

IT WRITES, AND THAT IS A STRUCTURAL DECISION, NOT A CONVENIENCE. `DESK_WRITERS` in
`tests/desk/test_boundaries.py` names it, as it names every module under desk/ that writes.

THE SYMMETRY IS WITH commit.py. That is the door by which an event enters `store/`; this is the
one door INTO `_inbox/`. Both exist in order to be the only one, and both are narrower than they
look:

    commit.py   may append a validated row to the record, and archives in the same breath.
    dropoff.py  may land bytes in ONE directory under a name it has checked. Nothing else.

WHAT IT CANNOT DO IS THE POINT. It never overwrites, never deletes, never renames, never moves
a document out, never reads the record and never touches `store/`. `docs/intake.md` says a
document leaves that folder by being archived or by going back where it came from — this module
has no way to make one leave, so the rule holds for this route too.
"""
from __future__ import annotations

import datetime as _dt
import os

from portfusion.record import schema

INBOX = schema.INBOX

#: WHAT MAY LAND, and the list is not arbitrary: it is what `desk/intake/
#: read_document.py` can actually extract. A file the bench cannot read is a file whose figures
#: would have to be typed from a recollection of it, which is the transcription error the bench
#: exists to remove. `.txt` is here because that extractor's fallback branch reads one.
#:
#: THESE TWO LISTS MUST AGREE. If the extractor learns a new kind, this is the second place to
#: say so — the only duplication in the module, and it is one line rather than a parser.
ACCEPTED = (".pdf", ".csv", ".tsv", ".txt")

#: Generous for a contract note, which runs to tens of kilobytes; small enough that a mis-drop
#: of a video or a disk image is refused rather than copied. Nothing about the workbench wants
#: a large file: every document here is a page or two of a broker's text.
MAX_BYTES = 25 * 1024 * 1024

#: macOS allows 255 bytes in a filename. A name near that is a paste accident, not a document.
MAX_NAME = 200


class Refused(Exception):
    """The drop was not accepted. The message names the rule that refused it.

    Every refusal here is a rule of `_inbox/`, not a preference of the desk's, so the message
    says which one — a drop that just fails teaches nobody why the workbench has the shape
    it has.
    """


def safe_name(raw: str) -> str:
    """The filename this drop may use, or a refusal.

    THE NAME ARRIVES FROM THE BROWSER AND IS THEREFORE UNTRUSTED. Not because anything sinister
    is expected on localhost — because a name is data, and the one thing that must never be
    possible here is a write outside `_inbox/`.
    """
    # SPLIT TWICE RATHER THAN `str.replace`, and that is not an idiom preference. The guard in
    # `test_the_drop_off_has_no_way_to_make_a_document_LEAVE` walks this file's syntax tree for
    # the names that could move or remove a document, and a tree cannot tell `str.replace` from
    # `os.replace`. Forbidding the name outright is worth more here than the shorter line.
    name = str(raw or "").strip()
    for sep in ("\\", "/"):
        name = name.rsplit(sep, 1)[-1]
    name = name.strip()

    if not name:
        raise Refused("the drop carried no filename")
    if len(name) > MAX_NAME:
        raise Refused(f"that filename is {len(name)} characters — the workbench takes "
                      f"{MAX_NAME} or fewer")
    if any(ord(c) < 32 for c in name):
        raise Refused("that filename contains control characters")

    # A LEADING DOT IS THE DANGEROUS ONE, and it is worth being explicit about why. Both
    # guards over this folder skip dotfiles: `read_document.waiting()` would not list it, and
    # `test_inbox.py`'s "the workbench is clear" would not fail on it. A document landing as
    # `.note.pdf` would therefore rest here invisibly and forever — the precise failure both
    # guards were written to prevent, arriving through the one route that bypasses them.
    if name.startswith("."):
        raise Refused(f"{name!r} starts with a dot, so nothing would ever list it: neither the "
                      f"bench's own document list nor the test that fails when a document is "
                      f"left resting here. Rename it and drop it again")

    ext = name[name.rfind("."):].lower() if "." in name else ""
    if ext not in ACCEPTED:
        got = ext or "a file with no extension"
        raise Refused(f"the workbench takes {', '.join(ACCEPTED)} — a document has to be one "
                      f"the intake extractor can read in full, and {got} is not")
    return name


def _download_time(modified_ms) -> float | None:
    """The browser's `File.lastModified` as a timestamp, or None if it is not a plausible one.

    A download is written to disk when it is pulled, so this is when the broker produced the
    file. It dates a document that states no date of its own — ii's holdings export and ledger
    carry none. Nothing later than a minute from now and nothing before
    2000: a value outside that is a browser's placeholder, not a download.
    """
    try:
        seconds = float(modified_ms) / 1000
    except (TypeError, ValueError):
        return None
    now = _dt.datetime.now().timestamp()
    return seconds if 946_684_800 <= seconds <= now + 60 else None


def accept(raw_name: str, data: bytes, modified_ms=None) -> dict:
    """Land a dropped document on the workbench. THE ONLY WRITE IN THIS MODULE.

    Returns what landed. Raises `Refused` with the rule that stopped it, and writes nothing
    at all in that case — a half-written document is a document whose figures cannot be
    trusted, and it would look exactly like a whole one in a listing.
    """
    name = safe_name(raw_name)

    if not data:
        raise Refused(f"{name!r} arrived empty — a nought-byte file is a failed drop, not a "
                      f"document")
    if len(data) > MAX_BYTES:
        raise Refused(f"{name!r} is {len(data):,} bytes; the workbench takes up to "
                      f"{MAX_BYTES:,}. A broker document is a page or two of text")

    INBOX.mkdir(parents=True, exist_ok=True)
    path = INBOX / name

    # BELT AND BRACES OVER safe_name(). That function is the guard; this asserts its result
    # rather than trusting it, because the cost of being wrong is a write outside the one
    # directory this module is allowed to touch.
    if path.resolve().parent != INBOX.resolve():
        raise Refused(f"{name!r} does not resolve inside _inbox/")

    # NEVER OVERWRITE. `docs/intake.md`: "Never delete a document from here. It leaves by
    # being archived, or it goes back where it came from. Deleting it destroys the evidence
    # the row points at." An overwrite is a deletion with the name left behind, and it is the
    # quieter of the two — the listing would be unchanged.
    #
    # There is a moment between this check and the write. It is not closed with an exclusive
    # open, deliberately: `tests/desk/test_boundaries.py` finds the writing modules by walking
    # the syntax tree for write_bytes/write_text/move/copy2/unlink, so a write hidden behind
    # `open(..., "xb")` would slip past the guard that pins the set. On a single-user localhost
    # desk, being visible to that guard is worth more than the race.
    if path.exists():
        raise Refused(f"{name!r} is already on the workbench. Nothing here overwrites a "
                      f"document — a document leaves _inbox/ by being archived. Rename the "
                      f"new one, or finish the intake that left the old one")

    path.write_bytes(data)
    # THE FILE KEEPS THE TIME IT WAS DOWNLOADED, as it would dragged in through Finder.
    when = _download_time(modified_ms)
    if when is not None:
        os.utime(path, (when, when))
    return {"name": name, "bytes": len(data), "kind": name[name.rfind("."):].lower()}


def accepts() -> dict:
    """What a drop may be, as data — so the browser does not hold a second copy of the rules.

    Same discipline as the bench's forms coming from `schema.TABLES`: the screen can grey out
    a file it knows will be refused, and it learns the list from here rather than restating it.
    The refusal still happens on this side; the browser's copy is a courtesy, never the gate.
    """
    return {"extensions": list(ACCEPTED), "max_bytes": MAX_BYTES,
            "where": "_inbox/",
            "note": "A dropped document is unfinished work until it is entered and archived."}
