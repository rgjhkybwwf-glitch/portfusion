# Intake

How a broker document enters the book and where it rests after. Working it on the Bench, row by
row, is [reconciling.md](reconciling.md).

## The three steps

1. **Dropped**: a PDF, CSV, TSV or text file lands in `_inbox/`, from the Bench's drop-off or from
   Finder.
2. **Worked**: read on the Bench, rows proposed, approved, written to `store/`.
3. **Archived**: moved to `_archive/statements/`, named by `rules.ARCHIVE_CONVENTION`, so no
   name is typed.

**Step 3 is not tidying.** The third part of `rules.STATEMENT_GRADE` needs the file: a row whose
document is still in the inbox, or was deleted, has lost what made it statement-grade. The Bench
does all three and will not skip the last.

**A document not used is withdrawn**, not archived: it is not evidence. One read in full with
nothing new is filed, since it proves the record.

**A PDF is read by a Claude session**, starting from `python3 -m portfusion.desk.intake.propose`,
which prints everything the session needs and checks every quote it returns against the file.
`python3 -m portfusion.desk.intake.read_document "<document>"` prints its text as the Bench reads
it.

## What rests where

| Folder | Holds |
|---|---|
| `_inbox/` | nothing, once the work is done. `test_inbox.py` fails while a document rests there. Its contents are never committed |
| `_inbox/.bench/` | one note per item being worked: about a document, not evidence |
| `_archive/statements/` | the documents behind every row. A row's reference leads here |
| `_archive/bench/` | one note per item written or withdrawn: what was proposed, what was written. `test_journal.py` ties each write to the journal |

**Evidence is never edited and never deleted.** A new document is filed beside the old one,
never over it. Nothing else is kept in `_archive/`, and no headline figure is read from it.

## Never

- **Enter a figure from a document you have not read in full.**
- **Delete a document from the inbox.** It leaves by being archived, or goes back where it came
  from. An overwrite counts as a deletion, and the drop-off refuses one.
- **Let a document land under a name starting with a dot.** Nothing would list it.
- **Enter a figure nothing retrieves again.** It is not statement-grade, and the Bench refuses it.
