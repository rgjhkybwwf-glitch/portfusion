"""
LIMB 3 — "a named reference that retrieves it", checked rather than asserted.

Kept apart from test_record.py, whose tests import no build and touch no file: these open
`_archive/statements/` and read the PDFs inside it — the only tests in the suite that look at
the evidence rather than reasoning about it.

WHY THAT MATTERS HERE MORE THAN ANYWHERE. The first version of this check reasoned, and was
wrong: it took the DATE out of a row's basis prose, matched it against archive FILENAMES, and
produced a confident list of eleven rows whose documents were supposedly missing. Every one of
those rows stored the dealId that retrieves it, and every dealId was already in an archived
statement. A guard that sends you looking for documents that were filed months ago is worse
than no guard, because you believe it.

So the strongest test here opens the files.
"""
import re

import pytest

# =====================================================================================
# LIMB 3, CHECKED RATHER THAN ASSERTED
#
# "A named reference that retrieves it" was the one limb of statement-grade nothing could
# test. EVIDENCE_CLASSES said what retrieves each class in PROSE — "the contract note
# number", "the dealId the row stores" — so no code could ask whether a reference actually
# led anywhere. rules.Evidence.retrieval turns that into structure, and these tests are what
# it buys.
#
# EVERY ROW, WHATEVER ITS DATE. A row whose document the archive does not hold says so in its
# own class, `not-on-file`, so no row may cite a document that is missing.
# =====================================================================================

#: Rows citing a broker document `_archive/statements/` does not hold. EMPTY, and it stays so: a
#: row read from a document that was never filed is labelled `not-on-file`, honestly.
_EXPECTED_EVIDENCE_GAPS = set()

#: A provenance line that DECLARES ITSELF A DERIVATION is not citing a document, and no class
#: should be invented to make it look like one: a figure worked out from recorded rows says
#: "Derived", an account with nothing in it says so, and a quarter end before an account's
#: record begins says where it begins.
_DERIVATION_PREFIXES = ("Derived", "Account not yet funded", "Record begins at")


def _is_derivation(line) -> bool:
    return str(line or "").strip().startswith(_DERIVATION_PREFIXES)

#: Source lines no evidence class composed. NONE: every governed row is in its class's own words,
#: `not-on-file` included.
_UNCLASSIFIED_HIGH_WATER = 0


#: Tables carrying a `source` column that the EVIDENCE VOCABULARY DOES NOT GOVERN, each
#: with the reason it is out. Statement-grade is a rule about BROKER DOCUMENTS behind the book's
#: events and balances; it is not a rule about every cell that happens to cite something.
_NOT_BROKER_DOCUMENTS = {
    "current-prices": "a feed mark. TradingView and IG levels are not broker documents",
    "fx":             "a feed rate, same reason",
    "quarter-snapshots": "a derived freeze of a composition the ledger already holds",
    "quarter-nav":    "its source says how the figure was ARRIVED AT; `quality` says what it "
                      "rests on, and test_quarter_nav.py guards that",
    "cash-readings": "carries an explicit `evidence` COLUMN, so its class is structural "
                         "rather than parsed — guarded by test_record.py",
}


def _provenance_rows(D):
    """(id, date, source line, stored reference, account) for every row the vocabulary governs.

    THE TABLE LIST IS DERIVED FROM THE SCHEMA, never typed. A typed list covered trades and
    exits — two of the ten tables carrying provenance — and `feeds/ig.py` wrote thirty
    unclassified lines into income, cash-readings and account-statements without it
    noticing. A guard that watches two of ten doors is not a guard, it is a sample.

    A new table with a `source` column joins by EXISTING. Opting one out means adding a
    line to `_NOT_BROKER_DOCUMENTS` with a reason, which is a diff a reviewer sees.

    THE STORED REFERENCE IS CARRIED because it is the thing that retrieves the row —
    record/schema.py: "`source` says what KIND of document; this says WHICH ONE." Leaving it out
    is what made eleven rows look unretrievable when their dealIds were in the archive already.
    THE ACCOUNT IS CARRIED for the same reason: a trade's source names its document's kind and
    date only (`rules.trade_source()`), and a date is not a document until the account narrows it.

    """
    from portfusion.record import schema

    rows = []
    for name, table in sorted(schema.TABLES.items()):
        if name in _NOT_BROKER_DOCUMENTS:
            continue
        fields = [f.name for f in table.fields]
        src = "source" if "source" in fields else None
        if src is None:
            continue
        when = "date" if "date" in fields else "as_of" if "as_of" in fields else None
        for row in schema.load(name):
            r = dict(zip(fields, row))
            rows.append((f"{name}:{r.get('id') or r.get('eid') or r.get(when) or '?'}",
                         r.get(when) or "", r.get(src) or "", r.get("broker_ref") or "",
                         r.get("account") or ""))

    # account-statements is NOT in schema.TABLES — one of the three files outside it — and it
    # is squarely a broker document table, so it is named here rather than silently missed.
    import csv
    import pathlib
    path = pathlib.Path(schema.STORE) / "account-statements.csv"
    if path.is_file():
        for r in csv.DictReader(path.open()):
            rows.append((f"account-statements:{r['account']} {r['as_of']}",
                         r.get("as_of") or "", r.get("source") or "", "", r.get("account") or ""))
    return rows


def _archive_names():
    """The loaded book's filed documents: the folder the doors file into. A dot-file (the Mac's
    `.DS_Store`) is the machine's, not a document."""
    from portfusion.record import schema
    folder = schema.STATEMENTS
    return [p.name for p in folder.iterdir() if not p.name.startswith(".")] if folder.is_dir() else []


@pytest.mark.audit
def test_every_filed_document_is_named_as_the_record_reads_it(D):
    """Every document in the archive leads with its date, may carry its own instant, then an
    authority the record declares (`rules.ARCHIVE_CONVENTION`). A name that does not was filed
    by hand under a name the record cannot read: rename the file, never the rule.

    THE MATCHER IS DERIVED FROM THE RECORD, not from a second statement of the shape. Those are
    the convention's first three parts, and the only ones a filename can be held to: `(what it
    covers)` is judgement, and a REF is absent from any class retrieved by its date."""
    authorities = tuple({e.authority.lower() for e in D.EVIDENCE_CLASSES})
    shape = re.compile(r"^\d{2} [A-Z][a-z]{2} \d{4}(?: \d{2}\.\d{2})? (.+)$")
    misnamed = [name for name in _archive_names()
                if not ((m := shape.match(name.rsplit(".", 1)[0]))
                        and m.group(1).lower().startswith(authorities))]
    assert not misnamed, f"filed under a name the record cannot read: {misnamed}"


@pytest.mark.audit
def test_the_evidence_chain_census_has_not_moved(D):
    """Which rows cite a document the archive does not hold — counted, not assumed.

    If this fires, a row's evidence stopped resolving. Investigate before editing the set:
    either a document left `_archive/statements/` (which breaks limb 3 for every row that
    names it) or a new row cites something nobody filed.
    """
    names = _archive_names()
    gaps = {rid for rid, _, src, ref, acct in _provenance_rows(D)
            if D.reference_resolves(src, names, ref, acct) is False}
    assert gaps == _EXPECTED_EVIDENCE_GAPS, (
        f"rows citing a document the archive does not hold: {sorted(gaps)}, expected "
        f"{sorted(_EXPECTED_EVIDENCE_GAPS)}. A document that LEFT the archive breaks limb 3 "
        f"for every row naming it — check that before changing this set.")


#: EVERY TABLE WHOSE ROWS NAME THEIR DOCUMENT. A trade's line is its document's kind and date; every
#: other table's is its evidence class's own template, slots filled.
SOURCED = ("buys", "sales", "income", "capital-movements", "account-statements")


def _documented(D, table):
    """(row id, row) for each row of `table` citing a document something retrieves: not a row
    not on file, nor a derivation, which say what they are instead."""
    if table == "account-statements":
        from portfusion.history import accounts as A
        rows = [(f"{r['account']} {r['as_of']}", r) for r in A.load()]
    else:
        hdr = D.schema.TABLES[table].header
        rows = [(f"{table} row {n}", dict(zip(hdr, r)))
                for n, r in enumerate(D.schema.load(table), 2)]
    return [(rid, r, ev) for rid, r in rows
            if (ev := D.evidence_from_source(r["source"])) and ev.retrieval != "none"]


@pytest.mark.parametrize("table, audit", [
    *(pytest.param(t, False, id=t) for t in SOURCED),
    # THE SAME, OF THE LOADED BOOK'S OWN ROWS, which `portfusion record` asks (a table with no such
    # row has nothing to put right there).
    *(pytest.param(t, True, id=f"{t}, the book", marks=pytest.mark.audit) for t in SOURCED)])
def test_every_row_names_its_document_in_its_class_format(D, table, audit):
    """The owner, 12 Oct 2026: "I want one format going forward for all accounts."

    A trade or sale's `source` is its document's kind, in its class's own words, and the
    document's date — "ii contract note 03 Feb 2022", "HL security movements 23 Jul 2026"; an API
    read names its endpoint before the day. Nothing else: the deal's reference is `broker_ref`
    (an ii contract note's number above all, since the archive finds the note by it), and the
    account and security are the row's own columns. Every other row naming a document is its
    class's template, slots filled, so one kind of document reads one way in every table. A row
    that cites no document (not on file, a derivation) says what it is instead."""
    import re
    documented = _documented(D, table)
    if not documented and not audit:
        pytest.skip(f"no {table} row on file names a document — this would assert nothing")
    wrong, unnumbered = [], []
    for rid, row, ev in documented:
        if table in ("buys", "sales"):
            prefix = ev.source.split("{")[0].strip()
            fits = re.fullmatch(rf"{re.escape(prefix)}( /\S+)? \d{{2}} [A-Z][a-z]{{2}} \d{{4}}",
                                row["source"])
            if ev.key in D.REFERENCE_IS_THE_DEAL and not (row["broker_ref"] or "").strip():
                unnumbered.append(rid)
        else:
            fits = D.template_pattern(ev).fullmatch(row["source"])
        if not fits:
            wrong.append(f"{rid}: {row['source']!r}")
    assert not wrong, f"not in its class's one format: {wrong}"
    assert not unnumbered, f"an ii contract note with no number in broker_ref: {unnumbered}"


def test_a_date_alone_does_not_put_a_document_on_file():
    """On a quarter end every broker's documents share the date, so a date is not a document.
    An HL valuation must not count as filed because an IG statement of that day is, nor one
    account's valuation because another account's is."""
    from portfusion.record import rules_evidence as E
    filed = ["30 Sep 2026 IG statement (Voss IG Spread bet).pdf",
             "30 Sep 2026 22.40 ii valuation download (Voss ii Trading).csv"]
    assert E.reference_resolves("HL valuation 30 Sep 2026 22:35 (Rowe HL ISA)", filed) is False
    assert E.reference_resolves("ii valuation 30 Sep 2026 22:40 (Voss ii ISA)", filed) is False
    assert E.reference_resolves("ii valuation 30 Sep 2026 22:40 (Voss ii Trading)", filed) is True
    assert E.reference_resolves("IG statement 30 Sep 2026", filed) is True


def test_every_source_line_was_composed_by_a_class_the_record_knows(D):
    """A provenance line no class composed has no stated authority and no reference shape.

    The vocabulary is `EVIDENCE_CLASSES`, and a line outside it cannot be checked by
    anything — which is the state limb 3 was in for every row before the vocabulary existed.
    The count can only grow if somebody types a provenance line instead of letting
    evidence_source() compose one.
    """
    unknown = {rid for rid, _, src, ref, _acct in _provenance_rows(D)
               if "S.104" not in str(src) and not _is_derivation(src)
               and D.evidence_from_source(src) is None}
    assert len(unknown) <= _UNCLASSIFIED_HIGH_WATER, (
        f"{len(unknown)} source lines were composed by no evidence class, above the "
        f"{_UNCLASSIFIED_HIGH_WATER} on file. A new one means a provenance line was typed "
        f"rather than composed, or names a document kind the vocabulary is missing.")


@pytest.mark.audit
def test_every_stored_deal_reference_is_findable_in_an_archived_statement(D):
    """LIMB 3 PROVED END TO END, by opening the documents.

    A dealId is treated as self-retrieving — `rules.SOURCE_HIERARCHY_NOTE` puts an
    authenticated API read on the top rung when the row stores the reference that retrieves it.
    That is a RULE, and a rule is what the eleven-row false alarm was built on. So this stops
    asserting and looks: every stored dealId must appear verbatim in a statement in
    `_archive/statements/`.

    It reads every PDF in the archive and costs about a third of a second, which is worth
    paying for the only check in the suite that opens the evidence rather than reasoning
    about it.

    Whitespace is stripped before matching because IG's PDFs come out of extraction with a
    space between almost every character.
    """
    pypdf = pytest.importorskip("pypdf", reason="pypdf reads the archived statements")
    # THE LOADED BOOK'S archive — the same derivation the doors use. The repo's own path
    # would open this book's statements whatever book the deal references belong to.
    folder = D.schema.STATEMENTS
    if not folder.is_dir():
        pytest.skip("no _archive/statements/ on this checkout")

    blob = ""
    for path in sorted(folder.glob("*.pdf")):
        try:
            pages = pypdf.PdfReader(str(path)).pages
            blob += re.sub(r"\s+", "", "".join(p.extract_text() or "" for p in pages))
        except Exception:
            continue                       # an unreadable document is test_inbox's problem
    if not blob:
        pytest.skip("no readable PDF in the archive")

    # A ROW WHOSE CLASS RETRIEVES BY API OWES NO PDF (`rules_evidence.py`, retrieval `api`):
    # its stored dealId IS the retrieval, and an IG event swept from the Bench files no document
    # (30 Sep 2026). Every other dealId must be in a filed statement.
    missing = [f"{rid} ({when})  {ref}" for rid, when, src, ref, _acct in _deal_rows(D)
               if D.is_deal_reference(ref) and ref not in blob
               and getattr(D.evidence_from_source(src), "retrieval", None) != "api"]
    assert not missing, (
        "these rows store a deal reference that appears in NO archived statement, so nothing "
        "retrieves them a second time:\n  " + "\n  ".join(missing))


def _deal_rows(D):
    """Every row of every table: a stored dealId retrieves its row whatever the row's date."""
    return _provenance_rows(D)


def test_every_class_says_how_its_reference_is_answered(D):
    """`retrieval` is a SECOND AXIS beside `official`, and every class declares it.

    official answers "is this the document a quarter reconciles against"; retrieval answers
    "what would I go and look at". A download is not official and is perfectly retrievable.
    """
    for e in D.EVIDENCE_CLASSES:
        assert e.retrieval in D.RETRIEVAL_KINDS, \
            f"{e.key} declares retrieval={e.retrieval!r}, not one of {D.RETRIEVAL_KINDS}"
    # The two axes are genuinely independent, which is why this is not a flag on `official`.
    pairs = {(e.official, e.retrieval) for e in D.EVIDENCE_CLASSES}
    assert (False, "document") in pairs and (True, "document") in pairs, \
        "official and retrieval have collapsed into one another"


# =====================================================================================
# RECOGNISING A DOCUMENT FROM ITS OWN TEXT
# =====================================================================================
#
# HL exports THREE different reports all titled "Portfolio Summary" — a valuation, a
# transaction list and a totals line. The `-2` and `-3` that appear on disk are macOS
# disambiguating a download in the order the downloads happened, and say nothing about what is
# inside. These fixtures are each export's head with invented figures, and they are the fingerprint's
# contract: if HL changes a column header, this fails and the fingerprint is what needs looking
# at, not the caller.

_HL_SHAPES = {
    "hl-valuation": (
        "HL Stocks & Shares ISA, , , ,\n"
        "Client Number:, 7421958, , ,\n"
        "Spreadsheet created at,03-03-2025 14:05, , ,\n"
        "Stock value:,50000.00, , ,\n"
        "Amount available to invest:,120.00, , ,\n"
        "Code,Stock,Units held,Price (pence),Value (£),Cost (£),Gain/loss (£),Gain/loss (%),\n"
    ),
    "hl-income": (
        "Income transactions for my HL Stocks & Shares ISA during 2025\n"
        "Client Number:,7421958\n"
        "Valuation as at,03-03-2025 14:07\n"
        "Date,Type,Description,Amount\n"
    ),
    "hl-transactions": (
        "Portfolio Summary\n"
        "Client Number:,7421958\n"
        "Valuation as at,03-03-2025 14:08\n"
        "Trade date,Settle date,Reference,Description,Unit cost (p),Quantity,Value (£)\n"
    ),
    "hl-account-totals": (
        "Portfolio Summary, , , ,\n"
        "Client Number:,7421958, , ,\n"
        "Valuation as at,03-03-2025 14:10, , ,\n"
        "Account,Stock value,Total cash,Total value,Available to invest,\n"
    ),
}


def test_each_hl_download_is_recognised_from_its_own_text():
    """ON CONTENT, NEVER ON THE FILENAME. Believing the filename would pick the wrong column
    map for a whole document, and every cell after it."""
    from portfusion.record import rules as D
    for expected, text in _HL_SHAPES.items():
        got = D.identify(text)
        assert got == [expected], f"{expected}: identify() said {got}"


def test_a_fingerprint_never_matches_two_classes():
    """A classification is a judgement about what a document IS, and it decides which columns
    mean what. Two matches is an honest answer for `identify()` to give and a bad property for
    the vocabulary to have — three of these share a title and two share a column header, so the
    fingerprints are carrying the whole distinction."""
    from portfusion.record import rules as D
    for name, text in _HL_SHAPES.items():
        hits = D.identify(text)
        assert len(hits) == 1, f"{name} matches {hits} — the fingerprints do not separate them"


def test_an_ii_contract_note_is_recognised_and_nothing_else_is_taken_for_one():
    """THE ARCHIVE IS THE SAMPLE. Every filed ii contract note must be recognised from its own
    text, and must give back the date, time and number its filed name was built from. No other
    filed document may be taken for one: an ii statement is the near miss, from the same broker
    in the same register. DERIVED from the folder, so a new document joins by being filed.

    Found 1 Oct 2026, reading a real note through the bench: the class came back blank, and the
    date came from the file's download time rather than from the dealing line."""
    import datetime as dt
    from portfusion.record import rules as D
    from portfusion.desk.intake import read_document
    folder = D.schema.STATEMENTS
    if not folder.is_dir():
        pytest.skip("this book has filed no documents")
    notes = 0
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in (".pdf", ".csv", ".tsv", ".txt"):
            continue
        text = read_document.extract_file(path).get("text") or ""
        named = re.search(r"^(\d{2} \w{3} \d{4})(?: \d{2}\.\d{2})? ii contract note ([A-Z0-9]{5,})",
                          path.name)
        if not named:
            assert "ii-contract-note" not in D.identify(text), f"{path.name} taken for a note"
            continue
        notes += 1
        assert D.identify(text) == ["ii-contract-note"], f"{path.name}: {D.identify(text)}"
        assert D.document_reference(text) == named.group(2), path.name
        when = D.document_instant(text)
        assert when and when.date() == dt.datetime.strptime(named.group(1), "%d %b %Y").date(), \
            f"{path.name}: the note states {when}"
    if not notes:
        pytest.skip("this book has filed no ii contract notes")


def test_a_document_with_no_fingerprint_is_not_guessed_at():
    """Most classes carry none, because no sample has been seen. Empty is the honest answer."""
    from portfusion.record import rules as D
    assert D.identify("some unrelated csv\na,b,c\n") == []
    assert D.identify("") == []


def test_the_document_instant_is_read_from_the_document():
    """NOT the day it was filed, and not the day either — the INSTANT. HL values shares at a
    bid delayed fifteen minutes, so two pulls of one account minutes apart can differ on the
    same line."""
    import datetime as dt
    from portfusion.record import rules as D
    for text in _HL_SHAPES.values():
        assert isinstance(D.document_instant(text), dt.datetime)
    assert D.document_instant(_HL_SHAPES["hl-valuation"]) == dt.datetime(2025, 3, 3, 14, 5)
    assert D.document_instant(_HL_SHAPES["hl-account-totals"]) == dt.datetime(2025, 3, 3, 14, 10)
    assert D.document_instant("no instant stated here") is None


def test_every_fingerprinted_class_is_a_retrievable_document():
    """A fingerprint says "this file IS that class", so the class had better be one a file can
    be. Recognising a screenshot or a query by its text would be recognising something that has
    no file to recognise."""
    from portfusion.record import rules as D
    for e in D.EVIDENCE_CLASSES:
        if e.fingerprint:
            assert e.retrieval == "document", \
                f"{e.key} carries a fingerprint but retrieves by {e.retrieval!r}"


def test_the_classes_closed_to_new_entries_are_a_named_set():
    """`not-on-file` is the one closed class: it labels rows whose document the archive does not
    hold, and no new row may cite it. Every door refuses it — `desk/intake/bench.py` at its
    statement-grade gate and `desk/doors/observations.py` outright.

    The set is derived from the classes and pinned here, so a second closed class fails the
    suite until somebody says why in a diff a reviewer sees.
    """
    from portfusion.record import rules as D
    assert D.CLOSED_TO_NEW_ENTRIES == ("not-on-file",), (
        f"the closed classes are now {D.CLOSED_TO_NEW_ENTRIES}. The evidence classes are "
        f"reduced, never added to.")
    for key in D.CLOSED_TO_NEW_ENTRIES:
        ev = D.EVIDENCE_BY_KEY[key]
        assert not ev.official, f"{key} cannot be an official document"
        assert ev.retrieval == "none", key


@pytest.mark.audit
def test_no_reading_entered_from_now_on_rests_on_a_closed_class(D):
    """A row written after the door closed may not cite a closed class.

    THE AUDIT'S QUESTION, not the guard's: no code change can make this true or false, only a
    row can. A reading written on a closed class before the door closed is to be replaced by
    an admissible document, never edited, and the journal row records the move.
    """
    CLOSED_ON = "2026-09-11"
    stragglers = [f"{r.acct} — {r.evidence}, dated {r.as_of}"
                  for r in D.ac_rows
                  if r.evidence in D.CLOSED_TO_NEW_ENTRIES and str(r.as_of)[:10] > CLOSED_ON]
    assert not stragglers, (
        "readings entered after the screenshot classes closed:\n    "
        + "\n    ".join(stragglers))



@pytest.mark.parametrize("key", sorted(__import__("portfusion.record.rules", fromlist=["x"])
                                       .REFERENCE_IS_A_DATE))
def test_a_dated_statement_cited_with_no_date_is_a_gap_not_no_document(key):
    """A STATEMENT IS FOUND BY ITS DATE, so a line that cites one with none — the ii statement's
    own prompt once asked for "Q2 25" — names a document and says nothing that finds it. It read
    as citing no document at all and was never reported missing (the review of 21 Oct 2026)."""
    from portfusion.record import rules as D
    ev = D.EVIDENCE_BY_KEY[key]
    # THE CLASS'S OWN SOURCE LINE, with a quarter where its date belongs.
    line = ev.source.format(reference="Q2 25", date="Q2 25", account="")
    assert D.evidence_from_source(line) is ev and ev.retrieval == "document", line
    assert D.archive_reference(line) == ""
    assert D.reference_resolves(line, [f"30 Jun 2026 {ev.authority} Q2 25.pdf"]) is False
