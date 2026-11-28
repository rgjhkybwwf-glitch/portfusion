"""THE BENCH'S GATES — whether an item may be approved, and if not, everything that holds it.

The evidence, the rows, the document that retrieves it, every line read, nothing already in the
book, each sign as its category's, and the why a decision owes. Nothing here writes either; the
item is `bench.py`'s.
"""
from __future__ import annotations

import datetime as _dt
import os

from portfusion.desk.engine import RecordUnavailable, _guarded
from portfusion.desk.intake import filing, recorded
from portfusion.desk.intake.bench_form import REGISTER, validate_row
from portfusion.house.headings import COMMON
from portfusion.record import schema


#: The two judgement fields, and they are the RECORD's names — `store/reasoning.csv` has these
#: columns. Naming them anything else here would be a second vocabulary for one idea.
WHY_FIELDS = ("why_entered", "why_exited")


#: A SPLIT OR CONSOLIDATION is a `trades` row that carries its ratio, `{"from": 20, "to": 1}`:
#: 20 shares become 1. The owner gives the account, the ticker, the date and the ratio; the rest
#: of the row is the record's (`adjustment_cells()`), and the Trades page calls it an Adjustment.
ADJUSTMENT_LABEL = "Split or consolidation"


def is_adjustment(row: dict) -> bool:
    return row.get("table") == "buys" and isinstance(row.get("adjustment"), dict)


def adjustment_cells(item: dict, row: dict) -> tuple[dict, list[str]]:
    """THE ROW A SPLIT OR CONSOLIDATION WRITES, derived and never typed: what the holding was the
    day before the date, what the ratio makes it, and the difference as a quantity of nil cost.
    Returns the cells and what stops them, which the rows gate reports.

    THE HOLDING IS THE RECORD'S, from its buys and sales dated before the event (an undated
    pre-baseline buy counts as before). THE RATIO IS THE DOCUMENT'S. A holding the ratio does not
    divide keeps the whole shares, and the note names the remainder, which the broker settles in
    its own way, usually as cash: that is a sale, entered beside this row from the same document.
    """
    values, ratio = row.get("values") or {}, row.get("adjustment") or {}
    account = str(values.get("account") or "").strip()
    ticker = str(values.get("ticker") or "").strip()
    date = str(values.get("date") or "").strip()
    try:
        old, new = int(str(ratio.get("from", "")).strip()), int(str(ratio.get("to", "")).strip())
    except ValueError:
        old = new = 0
    problems = []
    if old <= 0 or new <= 0 or old == new:
        problems.append("ratio: two whole numbers, different, each above nought — "
                        "20 to 1 for a consolidation, 1 to 2 for a split")
    try:
        day = _dt.date.fromisoformat(date)
    except ValueError:
        day = None
        problems.append("date: the day the split or consolidation took effect")
    if not (account and ticker) or problems:
        return {}, problems + ([] if account and ticker else ["account and ticker: whose holding"])

    def _held():
        from portfusion.record import rules as D
        def before(d):                              # ISO, so text compares as dates do
            return not d or str(d) < day.isoformat()
        bought = sum(t.qty or 0 for t in D.buys
                     if (t.acct, t.ticker) == (account, ticker) and before(t.date))
        sold = sum(e.qty or 0 for e in D.sales
                   if (e.acct, e.ticker) == (account, ticker) and before(e.date))
        cur = next((t.cur for t in reversed(D.buys) if (t.acct, t.ticker) == (account, ticker)), "")
        kind = D.KIND_OF_CODE.get(ticker)
        source = (D.trade_source(item.get("evidence_class") or "",
                                 str((item.get("evidence") or {}).get("dated") or "").strip())
                  if item.get("evidence_class") else "")
        return bought - sold, cur, kind, source
    try:
        held, cur, kind, document = _guarded(_held)
    except RecordUnavailable:
        return {}, ["the record cannot be read, so the holding cannot be"]
    if kind != "shares":
        return {}, [f"ticker: {ticker} is not a share, and only shares split or consolidate here"]
    if held <= 0:
        return {}, [f"{account} held no {ticker} before {day:%d %b %Y}"]
    after, left = divmod(held * new, old)
    what = "consolidation" if new < old else "split"
    note = f"{old}-to-{new} share {what}: {held:,} shares became {after:,}."
    if left:
        note += f" The remainder, {left}/{old} of a share, is not in this row."
    cells = {"qty": str(after - held), "cost": "0", "level_points": "", "cur": cur, "note": note,
             "traded_price": "", "rate": "", "stake": "", "broker_ref": ""}
    if document:
        cells["source"] = (f"Derived: {old}-to-{new} {what} of {ticker}, effective "
                           f"{day:%d %b %Y}, per {document}")
    else:
        cells["source"] = ""
    return cells, []


# The three limbs of `rules.STATEMENT_GRADE`, as fields rather than as a paragraph someone has
# to remember.
LIMBS = (
    ("dated", "Dated",
     "The date on the document, not the day it was filed."),
    ("authority", "Authority that can be asked again",
     "Who issued it, in the document kind's own words."),
    # Help text answers "what do I type here". Why the rule exists belongs where the rule is
    # explained, which is `rules.STATEMENT_GRADE`.
    ("reference", "Named reference that retrieves it",
     "Its number or name: a contract note number, 'ii statement Q2', an IG deal id."),
)


class _Filled(dict):
    """A format's values, with any placeholder not given left empty."""
    def __missing__(self, key):
        return ""


def _filed_already(item: dict, reference: str, names: list[str]) -> list[str]:
    """The archived names this item's document matches, by the archive's own rule
    (`rules.filed_as`): a statement by its date, authority and account, a contract note by its
    number. A substring match never fires for a dated statement, whose reference is never how its
    file is named."""
    from portfusion.record import rules as D
    ev = D.EVIDENCE_BY_KEY.get(item.get("evidence_class") or "")
    if ev is None:
        return [n for n in names if reference.lower() in n.lower()]
    account = next((str(r["values"].get("account") or "") for r in item.get("rows") or []
                    if str(r.get("values", {}).get("account") or "").strip()), "")
    # THE CLASS'S OWN LINE, its other placeholders (an API's endpoint) left empty.
    line = ev.source.format_map(_Filled(reference=reference, date=reference, account=account))
    return D.filed_as(line, names, reference, account) or []


def _repeated_ids(rows: list[dict]) -> list[str]:
    """An id this item's rows share, or one the store already holds: each is a second row of one
    name, which the record refuses on load (`rules`). Said here, by row, before the commit."""
    from portfusion.record import rules as D
    on_file = {"buys": {t.trade_id for t in D.buys}, "sales": {e.sale_id for e in D.sales}}
    first, out = {}, []
    for i, row in enumerate(rows, 1):
        key = {"buys": "trade_id", "sales": "sale_id"}.get(row["table"])
        rid = str(row["values"].get(key) or "").strip() if key else ""
        if not rid:
            continue
        if rid in on_file[row["table"]]:
            out.append(f"row {i} ({row['table']}) — {key} {rid} is already in the store")
        elif (row["table"], rid) in first:
            out.append(f"row {i} ({row['table']}) — {key} {rid} is row "
                       f"{first[(row['table'], rid)]}'s too")
        else:
            first[(row["table"], rid)] = i
    return out


def _register_problems(rows: list[dict]) -> list[str]:
    """A new line, company or contract is new, agrees with the rows beside it, and stands with
    the trade that first needs it."""
    new = {t: [r["values"] for r in rows if r["table"] == t] for t in REGISTER}
    if not any(new.values()):
        return []

    def _load():
        from portfusion.record import rules as D
        return ({r[0] for r in D.SECURITIES}, {r[0] for r in D.COMPANIES}, set(D.CONTRACTS))
    codes, companies, contracts = _guarded(_load)
    trades = [r["values"] for r in rows if r["table"] == "buys"]

    def v(row, k):
        return str(row.get(k) or "").strip()
    new_codes = {v(r, "ticker") for r in new["securities"]}
    new_companies = {v(r, "company") for r in new["companies"]}
    out = []
    for code in sorted(new_codes & codes):
        out.append(f"{code} is a line already")
    for code in sorted(new_codes - {v(t, "ticker") for t in trades}):
        out.append(f"{code}: a new line needs its trade")
    for company in sorted(new_companies & companies):
        out.append(f"{company} is a company already")
    for company in sorted(new_companies - {v(r, "company") for r in new["securities"]}):
        out.append(f"{company}: a new company needs its line")
    for r in new["securities"]:
        if v(r, "company") not in companies | new_companies:
            out.append(f"{v(r, 'ticker')}: {v(r, 'company')} has no company row")
    for r in new["contracts"]:
        name = v(r, "contract")
        if name in contracts:
            out.append(f"{name} is a contract already")
        if v(r, "ticker") not in codes | new_codes:
            out.append(f"{name}: {v(r, 'ticker')} is not a line")
        if not any(v(t, "contract") == name and v(t, "ticker") == v(r, "ticker") for t in trades):
            out.append(f"{name}: a new contract needs its trade, on its line")
    return out


def _unmarked(item: dict) -> list[str]:
    """The new contracts on an item, with an epic, that carry no first mark: the book will not
    load an open bet on a contract it cannot value."""
    marked = {str(m.get("mark_key") or "") for m in item.get("marks") or []}
    return sorted(str(r["values"].get("contract") or "") for r in item.get("rows") or []
                  if r["table"] == "contracts" and str(r["values"].get("epic") or "").strip()
                  and str(r["values"].get("contract") or "") not in marked)


def _source_shape(item: dict, row: dict) -> list[str]:
    """A trade or sale's `source` in its document kind's one format, or why not — with the line
    the kind composes, so the fix is to copy it rather than to guess at a shape."""
    source = str((row.get("values") or {}).get("source") or "").strip()
    key = item.get("evidence_class") or ""
    if row.get("table") not in ("buys", "sales") or not source or not key:
        return []

    def _load():
        from portfusion.record import rules as D
        if D.in_trade_source_format(source, key):
            return []
        want = D.trade_source(key, (item.get("evidence") or {}).get("dated") or "")
        return [f"source: {source!r} is not its document's kind and date"
                + (f" — {want!r}" if want else "")]
    try:
        return _guarded(_load)
    except RecordUnavailable:
        return []


# =================================================================================================
# IS THIS ALREADY IN THE BOOK?
# =================================================================================================
class Found(str):
    """A finding that this item is already in the book, and its `kind`: "document", whose
    reference the record already cites, or "event", a row the record holds or could not be
    checked against. Still a string, in a set, in `json.dumps` and in an item read back from disk,
    so an acknowledgement matches it by its words."""
    kind: str

    def __new__(cls, text: str, kind: str = "event"):
        self = super().__new__(cls, text)
        self.kind = kind
        return self


def already_in_the_record(item: dict) -> list[Found]:
    """Findings that this evidence, or this event, is already in the book, each of its kind.

    Without this, a document worked twice writes its event twice — a sale on the record at double
    its size, with nothing to say so. `commit.py`'s own docstring warns of exactly this: "a
    duplicate the schema cannot see".

    TWO QUESTIONS, because they fail independently. **Is this DOCUMENT already in the book?**
    — its reference is the thing that identifies it, in a row's source and on a file in
    `_archive/statements/`. **Is this EVENT already in the book?** — same date, account,
    holding, size and money.

    IT IS A WARNING AND NOT A REFUSAL, because a genuine duplicate exists: two
    legs of one spread bet closed the same day at the same size and the same price, and both are
    real. So the gate reports and the owner acknowledges. What it must never do is stay silent.
    """
    out = []
    reference = str((item.get("evidence") or {}).get("reference", "") or "").strip()

    def _load():
        found = []

        if len(reference) >= 4:
            for table in recorded.reference_tables(reference):
                found.append(Found(f"{reference} already appears in {table}.csv — this "
                                   f"document's evidence is in the book already", "document"))
            archived = _filed_already(item, reference, schema.filed_statements())
            if archived:
                found.append(Found(f"{reference} is already filed in _archive/statements/ as "
                                   f"{archived[0]!r} — this document has been worked before",
                                   "document"))

        for i, row in enumerate(item.get("rows") or [], 1):
            table = row.get("table")
            cols = recorded.SIGNATURE.get(table)
            if not cols:
                continue
            match = recorded.matching_row(table, row.get("values") or {})
            if match == "unreadable":
                # NOT SKIPPED SILENTLY. A row the parser cannot read is a row the duplicate check
                # cannot see: a proceeds cell carrying a "£" makes float() raise, and a check that
                # quietly moved on would let an already-recorded sale through.
                found.append(Found(f"row {i} ({table}) could not be checked against the record "
                                   f"— its cells do not parse yet, so it may be a duplicate"))
            elif match:
                found.append(Found(f"row {i} ({table}) is already in the record as {match} — "
                                   "same " + ", ".join(cols)))
        return found

    try:
        out = _guarded(_load)
    except RecordUnavailable as e:
        out = [Found(f"could not check the record for duplicates: {e}")]
    return out


#: THE WAY OUT OF EACH KIND OF FINDING, as the page offers it (`_exits()`): an event the book
#: already holds may be a second event, and is acknowledged as one; a document already filed is
#: withdrawn, since a second copy is evidence of nothing new; and on an item with no document,
#: there is none to withdraw, so the finding is a further row from that evidence, acknowledged.
EXITS = {"event": ("this is a separate event", "acknowledge"),
         "document": ("withdraw this document", "withdraw"),
         "no document": ("a further row from this evidence", "acknowledge")}


def _exits(item: dict, unacknowledged: list[Found]) -> list[dict]:
    """Each kind of finding still to answer, with its exit's words, its act and its findings."""
    named = bool((item.get("document") or {}).get("name"))
    out = []
    for kind in ("document", "event"):
        covered = [f for f in unacknowledged if f.kind == kind]
        if covered:
            label, act = EXITS["no document" if kind == "document" and not named else kind]
            out.append({"kind": kind, "label": label, "act": act, "findings": covered})
    return out


def unusual_signs(item: dict) -> list[str]:
    """Each income row whose amount's sign is not the one its category usually carries
    (`schema.USUAL_SIGN`). A blank or unreadable amount is the rows gate's to report."""
    out = []
    for i, row in enumerate(item.get("rows") or [], 1):
        values = row.get("values") or {}
        usual = row.get("table") == "income" and schema.USUAL_SIGN.get(values.get("category"))
        try:
            amount = float(str(values.get("amount") or "").replace(",", ""))
        except ValueError:
            continue
        if usual and amount and (amount > 0) != (usual > 0):
            out.append(f"row {i} (income): a {values['category']} of {amount:,.2f}, where one "
                       f"is usually money {'in' if usual > 0 else 'out'}")
    return out


# =================================================================================================
# THE GATES — every one of them must be green before a row may be approved.
# =================================================================================================
def gates(item: dict) -> list[dict]:
    """Why this item may or may not be approved yet. Reported in full, never just the first.

    A form that stops at the first problem makes the reader discover them one at a time. All of
    them, always — that is also how the audit reports.
    """
    out = []

    # THE DOCUMENT'S KIND IS OWED FIRST. It composes the row's `source` in the one format every
    # account's trades share and fills the authority in its own words; without it, three typed
    # boxes would pass this gate with a source no class composes.
    missing = (["what kind of document"] if not item.get("evidence_class") else []) + [
        label for key, label, _ in LIMBS if not str(item["evidence"].get(key, "")).strip()]
    out.append({
        "name": "statement-grade",
        "ok": not missing,
        "detail": ("dated · re-askable authority · named retrieving reference"
                   if not missing else "missing: " + ", ".join(missing)),
    })

    rows = item.get("rows") or []
    row_problems = []
    for i, row in enumerate(rows, 1):
        for p in validate_row(row["table"], row["values"]):
            row_problems.append(f"row {i} ({row['table']}) — {p}")
        for p in ([] if is_adjustment(row) else _source_shape(item, row)):
            row_problems.append(f"row {i} ({row['table']}) — {p}")
        if is_adjustment(row):
            for p in adjustment_cells(item, row)[1]:
                row_problems.append(f"row {i} (split or consolidation) — {p}")
    row_problems += _repeated_ids(rows) + _register_problems(rows) + [
        f"{c}: a new contract needs its first price" for c in _unmarked(item)]
    # NONE PROPOSED AND NONE LEFT ARE NOT THE SAME STATE. A document can be read in full and
    # yield nothing to enter: HL's Capital-side transaction list is every dealing line on the
    # account, and when every one is already in the record that document is not unfinished work
    # — it is the PROOF that the dealing side reconciles, which is the question it was pulled to
    # answer, and it has to be archivable.
    #
    # `examined` is what separates the two. It is set by a reader that looked at every line and
    # reported each one, so an empty `rows` beside a non-empty `examined` means "nothing is
    # new", while an empty `rows` on its own still means "nothing has been read yet".
    examined = item.get("examined") or []
    nothing_left = not rows and bool(examined)
    out.append({
        "name": "rows",
        "ok": (bool(rows) or nothing_left) and not row_problems,
        "detail": (f"{len(examined)} line(s) examined, none of them new" if nothing_left
                   else "no rows proposed yet" if not rows
                   else f"{len(rows)} row(s), every cell valid" if not row_problems
                   else "; ".join(row_problems)),
    })

    # DOES THE REFERENCE ACTUALLY RETRIEVE IT?
    #
    # STATEMENT-GRADE IS CHECKED AT THE DOOR, and this is the half the limbs cannot show. The
    # statement-grade gate above asks whether the three limbs are FILLED IN; it cannot ask
    # whether the third one leads anywhere, so a plausible reference typed against a document
    # nobody has passed it. The audit's evidence chain finds those AFTERWARDS, which is a row
    # in the record and an errand; this is a refusal and no row.
    #
    # IT ASKS FOR THE DOCUMENT ON THE BENCH, NOT IN THE ARCHIVE. `commit.py` files the document
    # as PART of the write — bench to archive in one operation — so at gate time it is still on
    # the workbench by definition, and a gate that looked in `_archive/statements/` could never
    # pass.
    #
    # THE CLASS DECIDES WHAT IS OWED. A `document` owes a file. An `api` or a `reading` owes
    # nothing on disk — an authenticated endpoint and a stored dealId ARE the retrieval, which
    # is why RETRIEVAL_KINDS exists as structure. `none` is `not-on-file`, refused here: it says
    # in its own definition that nothing retrieves it.
    #
    # A NAME IS NOT A FILE: a document taken off the workbench after its item was opened stops
    # the rows committing.
    from portfusion.record import rules as _D
    ev = _D.EVIDENCE_BY_KEY.get(item.get("evidence_class") or "")
    on_bench = filing.document_on_the_bench(item)
    if ev is None:
        ok, detail = True, "no class chosen yet — the statement-grade gate above says so"
    elif ev.retrieval == "none":
        ok, detail = False, (f"{ev.key} says nothing retrieves it a second time. An entry is "
                             f"statement-grade at the point of entry.")
    elif ev.retrieval != "document":
        ok, detail = True, f"{ev.key} — {ev.reference_is}"
    elif on_bench is not None:
        ok = on_bench.is_file()
        detail = (f"{on_bench.name}, filed on commit" if ok
                  else f"{on_bench.name} is not on the workbench. Drop it in again, or the row "
                       f"cites a document nobody can open.")
    elif item.get("document_archived_to"):
        ok, detail = True, f"{item['document_archived_to']}, filed"
    else:
        ok, detail = False, (f"a {ev.key} is retrieved by its FILE and none is on the bench. "
                             f"Drop the document in, or the row cites one nobody can open.")
    out.append({"name": "the reference retrieves it", "ok": ok, "detail": detail})

    # EVERY LINE OF A READ DOCUMENT IS ACCOUNTED FOR. A line the reader could not place is
    # entered by hand or confirmed as not an event, then acknowledged — the same deliberate
    # click a duplicate takes — so a document is never filed with a line nobody looked at.
    unread = [u for u in (item.get("unrecognised") or [])
              if u not in set(item.get("acknowledged") or [])]
    out.append({"name": "every line read", "ok": not unread,
                "detail": (f"{len(unread)} line(s) not read: " + "; ".join(unread)) if unread
                          else "every line is a row, in the record already, or acknowledged",
                "findings": unread, "ack": "I have entered these by hand, or they are not events"})

    # A HOLDINGS EXPORT'S READING, checked by the door that will write it, against the name the
    # document will be filed under — so it is never filed with a reading that door turns away.
    if item.get("reading") is not None:
        out.append(_reading_gate(item))

    # IS IT ALREADY IN THE BOOK? Reported like every other gate, and ACKNOWLEDGEABLE rather
    # than fatal — two identical legs closed on one day are legitimate and exist in this record.
    # The acknowledgement is per finding, so a row added afterwards raises it again. Each kind
    # of finding still standing is offered its own way out (`EXITS`).
    findings = already_in_the_record(item)
    acknowledged = set(item.get("acknowledged") or [])
    unacknowledged = [f for f in findings if f not in acknowledged]
    out.append({
        "name": "not already in the record",
        "ok": not unacknowledged,
        "detail": ("nothing here is in the book already" if not findings
                   else "acknowledged: " + "; ".join(findings) if not unacknowledged
                   else "; ".join(unacknowledged)),
        "findings": findings,
        "exits": _exits(item, unacknowledged),
    })

    # A SIGN ITS CATEGORY DOES NOT USUALLY CARRY. The quote check cannot see a sign (`verify`),
    # and it is the one figure the reader composes; acknowledgeable, as the duplicates are.
    signs = unusual_signs(item)
    unconfirmed = [f for f in signs if f not in acknowledged]
    out.append({"name": "signs as the category's", "ok": not unconfirmed,
                "detail": "; ".join(unconfirmed) if unconfirmed
                          else "every income row's sign is its category's, or confirmed",
                "findings": signs, "ack": "I have checked these signs"})

    # TWO WHY FIELDS, because the record has two. Each is appended to `store/reasoning.csv`
    # under the trade's date, and Holdings and Round Trips show both. One field could only ever
    # fill one of them.
    said = why(item)
    for field in WHY_FIELDS:
        text = said.get(field, "").strip()
        needed = _why_needed(item, field)
        out.append({
            "name": field,
            "ok": bool(text) or not needed,
            "detail": (f"{len(text.split())} words" if text
                       else "required — this is the one field no document supplies" if needed
                       else "not required for this item"),
            "required": needed,
        })
    # EACH GATE'S LABEL, what the screen calls it: a why by the words every page heads it with,
    # the rest by their own names. `name` stays the key the code and the tests use.
    for g in out:
        g["label"] = COMMON.get(g["name"], g["name"])
    return out


def reading_of(item: dict) -> dict:
    """The account reading a holdings item files: the figures read off the export, dated and
    referenced by its evidence limbs as they stand now.

    THE DATE IS READ AS THE FILING READS IT (`filing.archive_date()`), however it was typed,
    and is blank when it will not read."""
    r = item.get("reading") or {}
    ev = item.get("evidence") or {}
    dated = str(ev.get("dated") or "").strip()
    when = filing.archive_date(dated)
    return {"account": r.get("account") or item.get("account") or "",
            "as_of": when.isoformat() if when else "", "at": r.get("at") or "",
            "positions": r.get("positions"),
            "cash": r.get("cash"), "total": r.get("total"),
            "evidence": item.get("evidence_class") or "",
            "reference": str(ev.get("reference") or "").strip()}


def _reading_gate(item: dict) -> dict:
    from portfusion.desk.doors import observations
    reading = reading_of(item)
    name = (item.get("document") or {}).get("name") or ""
    dated = str((item.get("evidence") or {}).get("dated") or "").strip()
    if dated and not reading["as_of"]:
        return {"name": "the account's reading", "ok": False,
                "detail": f"the document's date, {dated!r}, does not read as a date: type it as "
                          f"2026-09-30 or 30 Sep 2026"}
    try:
        # The document is still on the workbench, where `read_document` reads it.
        observations.preflight(reading, filing.archive_name(item, name),
                               os.path.join(schema.inbox(), name))
    except observations.Refused as e:
        return {"name": "the account's reading", "ok": False, "detail": str(e)}
    except FileNotFoundError:
        # A DOCUMENT GONE FROM THE WORKBENCH is this gate failing, not the Bench.
        return {"name": "the account's reading", "ok": False,
                "detail": f"{name} is no longer on the workbench: drop it there again to read it"}
    agree = sum(1 for u in item.get("units") or [] if u["agrees"])
    # A CASH OF NOTHING IS STILL A CASH: `or ''` would read 0.00 as none.
    cash = ("" if reading["cash"] is None or str(reading["cash"]).strip() == ""
            else f", cash {reading['cash']}, total {reading['total']}")
    return {"name": "the account's reading", "ok": True,
            "detail": (f"{reading['account']}: {agree} of {len(item.get('units') or [])} "
                       f"holdings agree; stock {reading['positions']}{cash}")}


def why(item: dict) -> dict:
    """The item's two why fields, whatever shape they are stored in.

    TOLERATES THE OLD SINGLE STRING. An older item holds `reasoning` as one string, which was
    always the ENTRY reason — that is what its gate keyed on. Read as `why_entered` rather than
    migrated on disk: an item mid-work is transient state and rewriting one behind the owner's back
    is not worth the risk of getting it wrong.
    """
    said = item.get("why")
    if isinstance(said, dict):
        return {f: str(said.get(f, "") or "") for f in WHY_FIELDS}
    legacy = str(item.get("reasoning", "") or "")
    return {"why_entered": legacy, "why_exited": ""}


def _why_needed(item: dict, field: str) -> bool:
    """A PURCHASE needs an entry reason; a SALE needs an exit reason. A dividend or a transfer
    needs neither.

    Keyed on what the item's rows actually do: a reason is owed with the decision, because
    one recorded after the outcome is worth very little. Every trades row is a buy leg, save a
    split or consolidation.
    """
    rows = item.get("rows") or []
    table = "buys" if field == "why_entered" else "sales"
    # A SPLIT OR CONSOLIDATION IS NOBODY'S DECISION, so it owes no reason.
    return any(r["table"] == table and not is_adjustment(r) for r in rows)


def approved(item: dict) -> bool:
    return all(g["ok"] for g in gates(item))
