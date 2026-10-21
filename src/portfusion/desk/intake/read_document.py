#!/usr/bin/env python3
"""Read what is on the intake workbench, and extract a document's text.

ii and HL have no retail API, so a contract note or portfolio summary reaches this book as a
file. This prints what is waiting and, given a filename, the full text of it -- so the figures
can be read off the document itself rather than off a recollection of it.

It EXTRACTS. It does not enter anything, does not guess a field, and does not write to store/.
Nothing here invents a number, on the same contract as every other tool in this repo.

    python3 -m portfusion.desk.intake.read_document   # what is waiting
    python3 -m portfusion.desk.intake.read_document "<filename>" # its full text

It is the ONE extractor: the bench imports it. It still runs standalone, which is worth keeping
for a document that will not parse.
"""
import csv
import io
import os
import sys

from portfusion.record import schema
from portfusion.log import log

INBOX = str(schema.INBOX)


def listing():
    if not os.path.isdir(INBOX):
        log.info(f"no {INBOX}/ — nothing to intake")
        return
    files = sorted(f for f in os.listdir(INBOX)
                   if not f.startswith("."))
    if not files:
        log.info("The workbench is clear. Nothing waiting.")
        return
    log.info(f"{len(files)} document(s) waiting in {INBOX}/:\n")
    for f in files:
        size = os.path.getsize(os.path.join(INBOX, f))
        log.info(f"  {f}   ({size:,} bytes)")
    log.info("\nRead one with:  python3 -m portfusion.desk.intake.read_document \"<filename>\"")
    log.info("Every one of these is UNFINISHED WORK until it is entered AND archived.")


#: What a broker export is actually encoded as, in the order to try.
#:
#: UTF-8 FIRST because it is what anything modern writes, and `-sig` because a BOM is common on
#: a Windows export and would otherwise arrive as a stray character at the head of the first
#: cell. CP1252 SECOND because that is what a UK broker's spreadsheet export is — HL's downloads
#: carry the pound sign as the single byte 0xA3, which is not valid UTF-8 at all.
#:
#: NEVER `errors="replace"`. It is the tempting one-word fix and the worst available, because
#: 0xA3 sits IMMEDIATELY BEFORE A FIGURE in these files — replacing it hands the reader
#: "?10,000.00" to quote and verify against. A document that cannot be decoded must SAY SO, not
#: arrive corrupted in the one place a number is read from.
ENCODINGS = ("utf-8-sig", "cp1252")


def _decode(path) -> tuple[str, str]:
    """The file's text, and the encoding that read it. Raises rather than guessing."""
    raw = open(path, "rb").read()
    # A UTF-16 EXPORT SAYS SO IN ITS FIRST TWO BYTES, and is read so. Without this cp1252, which
    # takes any byte, read one as letters and NULs: a document of garbage that loaded cleanly.
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16"), "utf-16"
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise ValueError(
        f"{os.path.basename(path)} is not readable as any of {', '.join(ENCODINGS)}. "
        f"Re-export it rather than guessing at the bytes — a figure read through the wrong "
        f"encoding loads cleanly and is wrong.")


def _located(name):
    """The file a name means: an ABSOLUTE path as given — the doors' own, into the archive — or a
    bare name ON THE WORKBENCH, and nowhere else.

    A NAME IS NOT TRIED AGAINST THE FOLDER THE PROCESS RUNS IN. It was, first, so a name the desk
    was handed by a browser — `credentials.json` — was read from the book's own folder and served
    back (the review of 21 Oct 2026). The containment is the `/raw` route's: the name resolves
    inside `_inbox/` or it is not found.
    """
    if os.path.isabs(name):
        return name
    inbox = os.path.realpath(INBOX)
    path = os.path.realpath(os.path.join(inbox, name))
    if os.path.dirname(path) != inbox:
        raise FileNotFoundError(name)
    return path


def modified(name):
    """When the file on the workbench was written — its download time — as a datetime, or None.

    A document that states no instant of its own is dated by this. The drop-off keeps the
    browser's download time on the file, and Finder keeps it on a copy.

    UK WALL-CLOCK TIME, as a document's own instant is (`rules.utc_instant()` reads it so). In the
    Mac's own zone it was off by the Mac's distance from London, on any machine not set to it.
    """
    import datetime as _dt
    from zoneinfo import ZoneInfo
    try:
        path = _located(name)
    except FileNotFoundError:
        return None
    if not os.path.exists(path):
        return None
    return _dt.datetime.fromtimestamp(os.path.getmtime(path), ZoneInfo("Europe/London")) \
        .replace(tzinfo=None, second=0, microsecond=0)


def extract(name):
    """The document's text, RETURNED, so the bench can read it; `text_of()` prints it.

    It EXTRACTS and nothing more — no figure is invented here, and a scan that yields nothing
    says so rather than guessing.

    Returns {name, kind, pages, text, scanned}. `scanned` true means NO TEXT CAME OUT: the
    caller must stop and read it by eye rather than treat an empty string as an empty document.
    """
    path = _located(name)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    ext = os.path.splitext(path)[1].lower()
    base = os.path.basename(path)

    if ext == ".pdf":
        try:
            import pypdf
        except ImportError:
            raise RuntimeError("pypdf is not installed:  "
                               "python3 -m pip install -e '.[dev]' -c requirements.lock")
        reader = pypdf.PdfReader(path)
        pages = [(p.extract_text() or "") for p in reader.pages]
        body = "\n\n".join(f"--- page {i} ---\n{t}" for i, t in enumerate(pages, 1))
        return {"name": base, "kind": "pdf", "pages": len(pages), "text": body,
                "encoding": None, "scanned": not any(t.strip() for t in pages)}

    if ext in (".csv", ".tsv"):
        delim = "\t" if ext == ".tsv" else ","
        body, enc = _decode(path)
        rows = list(csv.reader(io.StringIO(body), delimiter=delim))
        # WRITTEN BACK AS CSV, QUOTED WHERE A CELL NEEDS IT. Joined bare, "12,000" came back as
        # two cells, and HL writes every figure over 999 that way.
        buf = io.StringIO()
        csv.writer(buf, delimiter=delim, lineterminator="\n").writerows(rows)
        return {"name": base, "kind": ext.lstrip("."), "pages": len(rows), "encoding": enc,
                "text": buf.getvalue().rstrip("\n"), "scanned": False}

    body, enc = _decode(path)
    return {"name": base, "kind": "text", "pages": None, "encoding": enc,
            "text": body, "scanned": False}


def waiting():
    """What is on the workbench, as data."""
    if not os.path.isdir(INBOX):
        return []
    return [{"name": f, "bytes": os.path.getsize(os.path.join(INBOX, f))}
            for f in sorted(os.listdir(INBOX))
            if not f.startswith(".")]


def text_of(name):
    """Print a document's text. PRINTS ONLY — extract() does the work."""
    try:
        doc = extract(name)
    except FileNotFoundError as e:
        sys.exit(f"not found: {e}")
    except RuntimeError as e:
        sys.exit(str(e))

    if doc["kind"] == "pdf":
        log.info(f"# {doc['name']} — {doc['pages']} page(s)\n")
        log.info(doc["text"] or "(no extractable text — SCANNED? see below)")
        log.info("")
        if doc["scanned"]:
            log.info("!! NO TEXT EXTRACTED. This may be a scan or an image-only PDF.")
            log.info("!! Do NOT guess at its figures. Read it by eye, or ask for a text copy.")
        return
    if doc["kind"] in ("csv", "tsv"):
        log.info(f"# {doc['name']} — {doc['pages']} row(s)\n")
        log.info(doc["text"])
        return
    log.info(doc["text"])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # TYPED AT A TERMINAL, a path means what it means there: a file in this folder is read by
        # its full path, which `_located()` takes as given. A bare name is the workbench's.
        arg = sys.argv[1]
        text_of(os.path.abspath(arg) if os.path.sep in arg else arg)
    else:
        listing()
