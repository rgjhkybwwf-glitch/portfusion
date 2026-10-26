"""THE BENCH — an event, from evidence to an approved row.

WHAT THIS IS FOR. Something happened in the market and the record has to catch up. A dropped
document, an IG read and "I made a spread bet" are three inputs to ONE pipeline, not three
procedures.

    open  ->  evidence  ->  reasoning  ->  proposed rows  ->  approved  ->  written  ->  archived
              3 limbs      the why         validated live     all gates    commit.py   _archive/

THE REASONING IS THE ONLY INPUT WITH NO OTHER SOURCE. A price can be re-fetched, a contract note
re-downloaded; why a position was taken exists nowhere but in the owner's head, and without this it
gets typed into a CSV cell in the middle of a chat. That is what this screen is really for.

IT PROPOSES NOTHING BY ITSELF, ON PURPOSE. A screen cannot parse an arbitrary ii contract note
deterministically, and a parser that guessed would be fabricating figures, and every figure must
trace to a named source. So the bench is a FORM, not a parser: it shows the document beside fields
whose values come from the store's own vocabulary, and it validates through `record/schema.py`,
which is the same door the CSV loader uses. The judgement stays human; what goes away is
transcription error and invented
spellings. (`desk/intake/propose.py` and `desk/intake/read_rows.py` fill the form; neither parses a guess.)

NOTHING HERE WRITES TO store/. This module holds the item, its gates and its preview;
`desk/doors/commit.py` writes an approved item's rows, through a declared action.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import uuid

from portfusion.desk.engine import RecordUnavailable, _guarded
from portfusion.desk.intake import filing, recorded
from portfusion.house.headings import COMMON
from portfusion.record import schema


def bench_dir():
    """Where the items in work are kept: beside the workbench they belong to, and gitignored
    with it — a half-worked intake is not a record. The dot keeps it clear of `test_inbox.py`'s
    "the workbench is clear" check, which is about DOCUMENTS resting unfinished; an item mid-work
    is legitimate transient state. The state that IS dangerous — written but not archived — is
    asserted separately."""
    return schema.inbox() / ".bench"


#: The two judgement fields, and they are the RECORD's names — `store/reasoning.csv` has these
#: columns. Naming them anything else here would be a second vocabulary for one idea.
WHY_FIELDS = ("why_entered", "why_exited")

# The tables a bench item can produce. Everything else in the store is either derived or is a
# mark, and a mark does not come through here — the marks rule put marks on the refresh path.
# A CASH OBSERVATION IS NOT AN EVENT, and it is on this list anyway. The other four are things
# that HAPPENED ONCE — a purchase, a sale, a dividend, a transfer — and are history the moment
# they are entered. A cash reading is a MEASUREMENT of a balance at a date, and the same account
# gets another one next month. It belongs here because it arrives the same way: on a document
# the owner is already working through, needing the same three evidence limbs and the same approval.
# An ii transactions download carries a Running Balance whose top row is dated and sourced, so
# cash maintains itself as a by-product of an intake being done anyway.
TABLES = ("buys", "sales", "income", "capital-movements", "cash-readings")

#: WHAT A ROW OF EACH TABLE IS, in the desk's words: a buy, a sale (the Trades page's Direction),
#: income — a cost is negative income — money into or out of an account, and a cash reading.
TABLE_LABELS = {"buys": "Buy", "sales": "Sale", "income": "Income",
                "capital-movements": "Money in or out", "cash-readings": "Cash reading",
                "securities": "New line", "companies": "New company", "contracts": "New contract"}

#: THE REGISTER: a line, its company and an IG contract. One rides on an item with the trade that
#: first needs it and is written with it, so the register holds nothing no trade stands on.
REGISTER = ("securities", "companies", "contracts")

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


# =================================================================================================
# THE VOCABULARY — derived from the record, never typed here.
# =================================================================================================
# WHICH VOCABULARIES ARE CLOSED, AND WHICH ARE MERELY KNOWN.
#
# THE DISTINCTION MATTERS. Enforce every derived list and a FIRST-EVER PURCHASE OF A NEW COMPANY
# is rejected — its ticker is by definition not in the record yet — so the gate blocks exactly
# the event the bench exists for.
#
# CLOSED sets are genuinely finite and adding to one is a structural decision: the accounts, the
# instrument types, the currencies, the income categories. A value outside them is a typo,
# every time. Most are declared to the loader too (`record/schema.py`).
#
# OPEN sets grow in the ordinary course of business. A new holding is not an error, so these are
# SUGGESTED — offered, and typing past them is allowed.
CLOSED = ("account", "cur", "category", "evidence")
OPEN = ("ticker",)



def closed_for(table: str) -> tuple:
    """Which of `table`'s columns are a CLOSED vocabulary, as opposed to merely known.

    One flat list, because a column name means one thing on every table.
    """
    return CLOSED

#: PROSE, and it does not fit on one line. `note` runs to a sentence or three, and a one-line
#: input means scrolling a short box sideways to read what the machine drafted — the one thing
#: the owner most needs to read in full before approving it. `detail` is the same shape on income
#: rows.
LONG = ("note", "detail")


def evidence_classes() -> list[dict]:
    """What kinds of evidence the record knows, from `rules.EVIDENCE_CLASSES`.

    NOT DECLARED HERE. It is a fact about the record's provenance — the same shelf as
    SOURCE_HIERARCHY and STATEMENT_GRADE — and a Claude session needs it as much as the
    desk does. A second list here would be a second answer to what a document is.
    """
    def _load():
        from portfusion.record import rules as D
        return [{"key": e.key, "label": e.label, "authority": e.authority,
                 "reference_is": e.reference_is, "official": e.official,
                 # Still listed, so an item already citing one can name it; never offered.
                 "closed": e.key in D.CLOSED_TO_NEW_ENTRIES}
                for e in D.EVIDENCE_CLASSES]
    return _guarded(_load)


def vocabulary() -> dict:
    """What each controlled column may hold, read off the store.

    Derived rather than written down, because a second statement of what the record already
    contains drifts the moment a new account or currency appears. `ACCOUNT_ORDER` is canonical
    and ordered (shares first, then spread bets — the break separates the two valuation bases); a
    vocabulary the schema declares to the loader is offered as declared; the rest are the values
    actually in use.

    These dropdowns are convenience on top of a real guard: `schema.check_references()` runs at
    import and refuses any account name that is not in store/accounts.csv, whatever route the
    row came in by.
    """
    def _load():
        from portfusion.record import rules as D
        return {
            "account": list(D.ACCOUNT_ORDER),
            # STERLING, EVERY CURRENCY WITH A RATE, AND ANY TRADED. A currency is a closed set the
            # record decides by holding its rate (`fx.csv`); the traded ones alone would refuse a
            # first trade in a new currency, and offer a new book nothing.
            "cur": sorted({"GBP"} | {r[0] for r in D.fx_rows} | {t.cur for t in D.buys}),
            "category": list(D.schema.INCOME_CATEGORIES),
            # THE REGISTER'S CODES, so a line set up and not yet traded is offered too.
            "ticker": sorted({r[0] for r in D.SECURITIES} | {t.ticker for t in D.buys}),
            "company": sorted({r[0] for r in D.COMPANIES}),
            "sector": sorted({r[1] for r in D.COMPANIES}),
            "region": sorted({r[2] for r in D.COMPANIES}),
            "held_as": list(D.schema.KINDS),
            "funding": list(D.schema.FUNDINGS),
            "realisation_id": sorted({e.realisation_id for e in D.sales}),
            # CLOSED, and the one vocabulary that is a fact about PROVENANCE rather than about
            # the book's contents. A reading citing a class the record does not know has no
            # stated authority and no reference shape — limbs 2 and 3 of statement-grade — and
            # a test in test_record.py refuses one, so offering a free text box here would let
            # the bench build a row the suite then rejects.
            "evidence": [e.key for e in D.EVIDENCE_CLASSES],
        }
    return _guarded(_load)


def next_ids() -> dict:
    """The next free row id per table: the name a proposed row goes by until the door writes it
    at its place in date order, which may be another.

    IT READS THE STORE, WHICH DOES NOT MOVE BETWEEN ROWS. A statement carrying two sales would
    have both allocated one id, and committing would write one over the other — the second sale
    silently absent from a book that looked complete. A caller holding several rows must
    allocate for all of them from one read and advance the number itself; asking twice gets the
    same answer twice.
    """
    def _load():
        from portfusion.record import rules as D
        return D.next_free_ids()
    return _guarded(_load)


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


def _blank_refused(field, table: str) -> bool:
    """Would the STORE reject this column left empty?

    ASK schema, DO NOT RE-DERIVE IT. `not field.null` is stricter than the store: `_parse`
    returns "" for a blank str column whatever `null` says, and only a blank NUMBER raises.
    Re-derived here, it would demand an `income.note` — blank on most income rows, "and that is a
    real value" in the schema's own words — on a row already described in full.

    validate_row's docstring says the bench "cannot accept something the store would then
    reject". Refusing something the store ACCEPTS is the same defect pointing the other way, and
    it is the one a person actually meets.
    """
    try:
        schema._parse(field, "", table, 0)
        return False
    except ValueError:
        return True


def form_for(table: str) -> list[dict]:
    """The form for one table: every column, its type, and its allowed values if it has any.

    GENERATED FROM schema.TABLES, so a new column appears on the screen by existing. A form
    written out by hand would be a third statement of the store's shape, after the schema and
    the CSV header.
    """
    if table not in TABLES + REGISTER:
        raise KeyError(f"{table!r} is not a table the bench produces: {TABLES + REGISTER}")
    vocab = vocabulary()
    closed = closed_for(table)
    ids = next_ids()
    out = []
    for f in schema.TABLES[table].fields:
        spec = {"name": f.name, "kind": f.kind, "required": _blank_refused(f, table),
                "choices": vocab.get(f.name),
                "closed": f.name in closed,
                "long": f.name in LONG}
        if f.name in ("trade_id", "sale_id"):
            spec["suggested"] = ids.get(table)
            spec["help"] = "given when written: its place in date order"
        out.append(spec)
    return out


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


def validate_row(table: str, values: dict) -> list[str]:
    """Complaints about one proposed row. Empty means it would load.

    VALIDATES THROUGH record/schema.py ITSELF — `_parse` is the very function the CSV loader runs
    on every cell, so the bench cannot accept something the store would then reject. It is
    private, and using it is deliberate: a second copy of the parsing rules is exactly the
    duplication this project keeps paying for. `tests/desk/test_bench.py` asserts it still exists
    under that name.
    """
    problems = []
    fields = {f.name: f for f in schema.TABLES[table].fields}
    for name, f in fields.items():
        raw = values.get(name, "")
        raw = "" if raw is None else str(raw).strip()
        if not raw:
            if _blank_refused(f, table):
                problems.append(f"{name}: required, and empty")
            continue
        # AS IT WILL BE WRITTEN (`schema.cell()`): a figure typed "0" is written "0.00".
        try:
            schema._parse(f, schema.cell(f, raw), table, 0)
        except ValueError as e:
            problems.append(f"{name}: {e}")
    vocab = vocabulary()
    for name in closed_for(table):
        allowed = vocab.get(name)
        got = str(values.get(name, "") or "").strip()
        if allowed and name in fields and got and got not in allowed:
            problems.append(f"{name}: {got!r} is not one of {allowed} — match the record's "
                            f"spelling rather than inventing one")
    for name in ("trade_id", "sale_id"):
        if name in fields and values.get(name):
            problems.extend(_id_clash(table, name, str(values[name]).strip()))
    if table == "sales" and str(values.get("realisation_id") or "").strip():
        problems.extend(_parcel_clash(values))
    if table in ("buys", "sales"):
        problems.extend(_size_clash(values))
    return problems


def _size_clash(values: dict) -> list[str]:
    """A row sized in the other kind's column: a share has a quantity and no stake, a spread bet
    a stake and no quantity, by its code's kind. The record refuses either on load
    (`record/rules.py`); this says so before anything is written."""
    ticker = str(values.get("ticker") or "").strip()
    qty = str(values.get("qty") or "").strip()
    stake = str(values.get("stake") or "").strip()

    def _load():
        from portfusion.record import rules as D
        kind = D.KIND_OF_CODE.get(ticker)
        if kind == "spread bet" and (not stake or qty):
            return ["stake: a spread-bet row has a stake per point and no quantity"]
        if kind == "shares" and (not qty or stake):
            return ["qty: a share row has a quantity and no stake"]
        return []
    try:
        return _guarded(_load)
    except RecordUnavailable:
        return []


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


def _parcel_clash(values: dict) -> list[str]:
    """A realisation in another form, or one another holding already has, which would file this
    sale into that holding's round trip. The record refuses both on load (`record/rules.py`; a
    share's in `engine.share_pools()`); this says so before anything is written."""
    want = str(values.get("realisation_id") or "").strip()
    mine = (str(values.get("account") or "").strip(), str(values.get("ticker") or "").strip())

    def _load():
        from portfusion.record import rules as D
        if not D.REALISATION_FORM.fullmatch(want):
            return [f"realisation: {want} is not in the record's form — R-, the holding's root, "
                    f"and -2, -3 when the name is taken"]
        other = sorted({(e.acct, e.ticker) for e in D.sales if e.realisation_id == want} - {mine})
        return ([f"realisation: {want} is {other[0][0]}'s {other[0][1]} — a sale files under "
                 f"its own holding's"] if other else [])
    try:
        return _guarded(_load)
    except RecordUnavailable:
        return []


def _id_clash(table: str, field: str, value: str) -> list[str]:
    """A row id already in the store is a silent overwrite waiting to happen."""
    def _load():
        from portfusion.record import rules as D
        taken = ({t.trade_id for t in D.buys} if table == "buys"
                 else {e.sale_id for e in D.sales} if table == "sales" else set())
        return [f"{field}: {value} is already in the store"] if value in taken else []
    try:
        return _guarded(_load)
    except RecordUnavailable:
        return []


# =================================================================================================
# IS THIS ALREADY IN THE BOOK?
# =================================================================================================
def item_for_event(ref: str) -> dict | None:
    """The open bench item carrying this deal reference, if there is one.

    The lookup for_event() does before it creates anything, named so the sweep can ask it
    without creating anything.
    """
    ref = str(ref or "").strip()
    if not ref:
        return None
    for existing in all_items():
        if (existing.get("event_ref") == ref
                and existing.get("state") not in ("written", "archived")):
            return existing
    return None


def sweep_status(refs: list[str]) -> dict:
    """For each deal reference: is it already in the record, or already on the bench?

    THE SWEEP IS A SNAPSHOT AND THE WORLD MOVES UNDER IT. Its result is held client-side so that
    returning to the Bench does not mean another 30-day call to the broker — but a snapshot alone
    would go on offering "work it" for a row already carried across, or already committed.

    So the snapshot supplies the EVENTS and this supplies their STATE, asked fresh every time
    the sweep is drawn. Neither is guessed from the other.
    """
    out = {}
    for ref in refs or []:
        ref = str(ref or "").strip()
        if not ref:
            continue

        def _look(ref=ref):
            tables = recorded.reference_tables(ref)
            item = item_for_event(ref)
            return {
                "in_record": bool(tables),
                "tables": tables,
                "item": None if item is None else {
                    "id": item["id"], "state": item.get("state", "open"),
                    "blocked": [g["label"] for g in gates(item) if not g["ok"]],
                },
            }

        try:
            out[ref] = _guarded(_look)
        except RecordUnavailable as e:
            out[ref] = {"error": str(e)}
    return out


def already_in_the_record(item: dict) -> list[str]:
    """Findings that this evidence, or this event, is already in the book.

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
                found.append(f"{reference} already appears in {table}.csv — this "
                             f"document's evidence is in the book already")
            archived = _filed_already(item, reference, schema.filed_statements())
            if archived:
                found.append(f"{reference} is already filed in _archive/statements/ as "
                             f"{archived[0]!r} — this document has been worked before")

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
                found.append(f"row {i} ({table}) could not be checked against the record — its "
                             f"cells do not parse yet, so it may be a duplicate")
            elif match:
                found.append(f"row {i} ({table}) is already in the record as {match} — same "
                             + ", ".join(cols))
        return found

    try:
        out = _guarded(_load)
    except RecordUnavailable as e:
        out = [f"could not check the record for duplicates: {e}"]
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
        f"{c}: a new contract needs its first mark" for c in _unmarked(item)]
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
    # The acknowledgement is per finding, so a row added afterwards raises it again.
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


# =================================================================================================
# STORAGE. One JSON per open item, beside the workbench.
# =================================================================================================
def _path(item_id: str):
    if not re.fullmatch(r"[A-Za-z0-9-]+", item_id):
        raise ValueError(f"bad item id: {item_id!r}")
    return bench_dir() / f"{item_id}.json"


def new_item(origin: str = "manual", title: str = "", document: dict | None = None) -> dict:
    bench_dir().mkdir(parents=True, exist_ok=True)
    item = {
        "id": f"B-{_dt.date.today():%Y%m%d}-{uuid.uuid4().hex[:6]}",
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "state": "open",
        "origin": origin,
        "title": title or "untitled",
        "document": document,
        # WHICH KIND OF DOCUMENT THIS IS. Picking one fills the authority, says what its
        # reference looks like, and composes `source` in the shape the record already uses.
        "evidence_class": "",
        "evidence": {k: "" for k, _, _ in LIMBS},
        "why": {f: "" for f in WHY_FIELDS},
        "rows": [],
    }
    save(item)
    return item


def for_document(name: str, origin: str = "document") -> dict:
    """The bench item for this document — the existing one if there is one, else a new one.

    WHY THIS IS NOT JUST `new_item()`. A fresh item on every click leaves two identical empty
    items on the bench and no way to tell which one is being filled.

    OPENING A DOCUMENT IS IDEMPOTENT, which is the honest shape: one document is one piece of
    evidence and one item works it, however many rows that item ends up proposing. A committed
    or archived item does NOT block a new one — the same document legitimately comes back if a
    correction is needed, and by then the old item has left the bench anyway.
    """
    # A DOCUMENT IS ONE ON THE WORKBENCH, by its bare name. The name arrives from the browser,
    # and an item's document is what the reader opens: a path would be read wherever it points,
    # so the name is found in the workbench's own listing and never joined to a path.
    inbox = schema.inbox()
    if not name or not inbox.is_dir() \
            or name not in {p.name for p in inbox.iterdir() if p.is_file()}:
        raise FileNotFoundError(f"no document {name!r} on the workbench")
    for existing in all_items():
        doc = existing.get("document") or {}
        if doc.get("name") == name and existing.get("state") not in ("written", "archived"):
            return existing
    item = new_item(origin=origin, title=name, document={"name": name})

    # WHAT THE DOCUMENT SAYS ABOUT ITSELF, filled in. This is DERIVATION and not a proposal:
    # every value here is read out of the document's own text, the way `propose._derived()`
    # works — fill a blank from something checkable, never overwrite, and say where it came
    # from. The item carries `recognised` so the screen can show what was matched and on what.
    #
    # ONE MATCH ONLY. Two is ambiguous, and a class decides which columns mean what — guessing
    # between them would be worse than leaving both blank, because a pre-filled wrong answer is
    # the one nobody re-reads.
    from portfusion.record import rules as D
    seen = recognise(name)
    item["recognised"] = seen
    if len(seen["classes"]) == 1:
        key = seen["classes"][0]
        item["evidence_class"] = key
        item["evidence"]["authority"] = D.EVIDENCE_BY_KEY[key].authority
        if seen["instant"]:
            item["evidence"]["dated"] = seen["instant"][:10]
        if seen.get("reference"):
            item["evidence"]["reference"] = seen["reference"]
    save(item)
    # A KIND THIS MACHINE READS IS READ AT ONCE — no reader, no cost, nothing to press.
    from portfusion.desk.intake import read_rows
    if len(seen["classes"]) == 1 and seen["classes"][0] in read_rows.LOCAL:
        return read_here(item)
    return item


def read_here(item: dict) -> dict:
    """Read the item's document ON THIS MACHINE, if it is a kind `read_rows.LOCAL` reads. Returns
    the item, saved. Nothing leaves the machine and nothing is verified, because the value IS
    the cell (`desk/intake/read_rows.py`).

    A RE-READ REPLACES WHAT THE LAST READ PROPOSED AND NOTHING ELSE, as `propose.py` does: rows
    added by hand survive. The limbs are filled only where blank — a value typed is the owner's.
    """
    from portfusion.record import rules as D
    from portfusion.desk.intake import read_rows
    name = (item.get("document") or {}).get("name")
    if not name:
        raise ValueError("this item has no document to read")
    got = read_rows.read(name)
    if got["class"] not in read_rows.LOCAL:
        raise ValueError(f"{name} is not a kind of document this machine reads; a Claude "
                         f"session can: python3 -m portfusion.desk.intake.propose")
    kept = [r for r in (item.get("rows") or []) if not r.get("machine")]
    item["rows"] = kept + got["rows"]
    item["examined"] = ([s["line"] for s in got["seen"]]
                        + [next(iter(r["sources"].values()), r["table"]) for r in got["rows"]])
    item["unrecognised"] = got["unrecognised"]
    if not item.get("evidence_class"):
        item["evidence_class"] = got["class"]
    ev = D.EVIDENCE_BY_KEY[got["class"]]
    filled = {"dated": (got["instant"] or "")[:10], "authority": ev.authority,
              "reference": got["reference"]}
    for key, value in filled.items():
        if value and not str(item["evidence"].get(key, "")).strip():
            item["evidence"][key] = value
    if got["account"] and not item.get("account"):
        item["account"] = got["account"]
    # A HOLDINGS EXPORT FILES THE ACCOUNT'S READING: its units against the
    # book, and the figures `commit.py` writes through `observations.py` when it is filed.
    if "reading" in got:
        item["reading"], item["units"] = got["reading"], got.get("units") or []
    item["proposed"] = {"at": _dt.datetime.now().isoformat(timespec="seconds"), "local": True,
                        "document": name, "kind": ev.label, "seen": got["seen"],
                        "not_found": [], "dropped": [], "directives": []}
    return save(item)


def for_event(event: dict, origin: str = "ig-events", marks: list[dict] | None = None) -> dict:
    """The bench item for one IG event — the existing one if there is one, else a new one.

    ONE EVENT, ONE ITEM. The alternative was one item per sweep carrying every missing row, and
    it does not survive contact with the evidence rule: `ig-api` defines its reference as "the
    dealId the row stores", and an item has ONE reference. A sweep that found six events would
    have had to pick one dealId for all six, and one reason would have covered six unrelated
    trades — where a reason belongs to a decision.

    IDEMPOTENT ON THE DEAL ID, the same shape as for_document(). Pressing the button twice
    returns the item already open rather than a second empty copy.

    WHAT IT FILLS: the evidence, which the API genuinely supplies — the class is `ig-api`, the
    authority is the endpoint, the reference is the dealId, the date is the event's own. And
    the row, as the sweep built it.

    WHAT IT NEVER FILLS: the WHY. No API supplies it, and bench.gates() will not let the item be
    approved without one where one is owed. That is the whole reason an event goes to the bench rather
    than into the record.
    """
    ref = str(event.get("ref") or "").strip()
    if not ref:
        raise ValueError("an IG event with no deal reference cannot go to the bench — "
                         "the reference IS the evidence for an `ig-api` row")

    # THE EVENT ARRIVES FROM THE BROWSER, so it is checked rather than trusted. The sweep's
    # result is held client-side and posted back, which is the only way to avoid a second
    # broker call — and it means the shape reaching the bench is whatever was sent. A table
    # this store does not have, or a row that does not fill exactly that table's columns, is
    # refused here rather than staged and discovered at commit.
    def _shape(row, tables):
        table = row.get("table")
        if table not in tables:
            raise ValueError(f"{table!r} is not a table in this store")
        want = tuple(f.name for f in schema.TABLES[table].fields)
        got = tuple((row.get("values") or {}))
        if got != want:
            raise ValueError(f"an {table} row must fill exactly {want}, and this one has {got}")
        return True

    _guarded(lambda: _shape(event, schema.TABLES))
    # A SET-UP carries the new line, company and contract its trade stands on (`REGISTER`).
    setup = list(event.get("with") or [])
    for row in setup:
        _guarded(lambda row=row: _shape(row, REGISTER))

    existing = item_for_event(ref)
    if existing:
        return existing

    row = {"table": event["table"], "values": dict(event["values"])}
    # THE EVENT'S OWN WORDS ARE ITS TITLE, as the Trades page says it; the deal id is the
    # evidence's reference, shown with it.
    item = new_item(origin=origin, title=event.get("what") or ref)
    item["event_ref"] = ref
    item["evidence_class"] = "ig-api"
    item["evidence"] = {
        "dated": str(row["values"].get("date", "") or ""),
        "authority": "IG REST /history/activity",
        "reference": ref,
    }
    item["rows"] = [{"table": r["table"], "values": dict(r["values"])} for r in setup] + [row]
    # A NEW CONTRACT'S FIRST MARK, read from IG on the owner's press and written with the bet.
    if marks:
        item["marks"] = [dict(m) for m in marks]
    return save(item)


def to_bench(event: dict, marks: list[dict] | None = None) -> dict:
    """Carry one swept event onto the bench (`for_event()`). Returns the item, or a refusal."""
    try:
        item = for_event(event, marks=marks)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except RecordUnavailable as e:
        return {"ok": False, "error": f"record unavailable: {e}"}
    return {"ok": True, "id": item["id"], "title": item["title"],
            "blocked": [g["label"] for g in gates(item) if not g["ok"]]}


class Stale(Exception):
    """A save made from a copy of the item older than the one on disk."""


def save(item: dict, drawn: int | None = None) -> dict:
    """Write the item, raising its `revision` by one.

    A PAGE SAYS WHICH REVISION IT DREW (`drawn`), and a save from an older one is refused with
    `Stale`. The page sends the whole item, so a page drawn before another save would write its
    old rows back over it. Every saver comes through here, so every save moves the revision. An
    item from before revisions reads as revision 0."""
    bench_dir().mkdir(parents=True, exist_ok=True)
    path = _path(item["id"])
    current = (json.loads(path.read_text(encoding="utf-8")).get("revision", 0) if path.is_file()
               else item.get("revision", 0))
    if drawn is not None and drawn != current:
        raise Stale(current)
    item["revision"] = current + 1
    # A TERMINAL STATE IS NOT RECOMPUTED. Deriving state from "does it have rows" is right
    # while an item is being worked and WRONG the moment it is committed: a written item has
    # rows, so the derivation would quietly demote it to "proposed" and offer it for writing a
    # second time. desk/doors/commit.py sets those two states deliberately, and they stand.
    if item.get("state") not in ("written", "archived"):
        item["state"] = "proposed" if item.get("rows") else "open"
    _path(item["id"]).write_text(json.dumps(item, indent=2), encoding="utf-8")
    return item


def get(item_id: str) -> dict:
    p = _path(item_id)
    if not p.is_file():
        raise KeyError(item_id)
    return json.loads(p.read_text(encoding="utf-8"))


def all_items() -> list[dict]:
    if not bench_dir().is_dir():
        return []
    items = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(bench_dir().glob("*.json"))]
    return sorted(items, key=lambda i: i["created"], reverse=True)


def discard(item_id: str) -> None:
    """Remove an item from the bench. It has written nothing, so nothing is lost.

    NOT the same as deleting a document — `docs/intake.md` forbids that, and this never
    touches one. An item is a work-in-progress note about a document, not the evidence.
    """
    _path(item_id).unlink(missing_ok=True)


def paste_block(item: dict) -> list[dict]:
    """The rows as they would land in each CSV — a PREVIEW.

    `desk/doors/commit.py` writes them; this shows each line before it lands, and can be pasted by
    hand if a commit is refused.
    """
    out = []
    for row in item.get("rows") or []:
        table = row["table"]
        fields = schema.TABLES[table].fields
        cells = []
        for f in fields:
            raw = row["values"].get(f.name, "")
            try:
                v = schema.cell(f, raw)
            except ValueError:               # the gate names it; the line still shows it
                v = str(raw)
            cells.append(f'"{v}"' if ("," in v or '"' in v) else v)
        out.append({"table": table, "target": f"store/{table}.csv", "line": ",".join(cells)})
    return out


# =================================================================================================
# DOCUMENTS. ii and HL have no retail API, so their evidence arrives as a file.
# =================================================================================================
def _reader():
    """The one document extractor, `desk/intake/read_document.py`.

    ONE EXTRACTOR, and that is the point: copying twenty lines of pypdf into a second place
    would be the actual mistake, because two extractors disagree the first time one learns a new
    document kind. It also runs standalone — `python3 -m portfusion.desk.intake.read_document` — which is worth
    keeping for a document that will not parse.
    """
    from portfusion.desk.intake import read_document
    return read_document


#: Recognised in the LISTING for these only. `extract()` reads a whole file, and the bench
#: panel renders on every visit — walking every PDF in the workbench each time would be felt.
#: A PDF is still recognised when its item is created, where the cost is paid once.
_CHEAP_TO_READ = (".csv", ".tsv", ".txt")


def recognise(name: str) -> dict:
    """What this document says it IS, read from its own text.

    NEVER FROM THE FILENAME. HL exports three different reports all titled "Portfolio Summary",
    and the `-2` and `-3` that appear on disk are macOS disambiguating a download in the order
    the downloads happened. Believing them would pick the wrong column map for a whole document
    and every cell after it.

    `classes` IS A LIST AND MAY HOLD MORE THAN ONE. Two matches is an honest answer and the
    caller must ask rather than take the first — deciding what a document is decides which
    columns mean what.

    Never raises. A document that cannot be read reports `why` and is still workable by hand.
    """
    from portfusion.record import rules as D
    out = {"name": name, "classes": [], "instant": None, "instant_from": "", "reference": "",
           "encoding": None, "scanned": False, "why": ""}
    try:
        doc = _reader().extract(name)
    except Exception as e:                       # noqa: BLE001 — reported on the row, never raised
        out["why"] = str(e)
        return out
    text = doc.get("text") or ""
    # THE DOCUMENT'S OWN INSTANT, ELSE WHEN IT WAS DOWNLOADED. ii's exports state no date, and
    # the file's time is when ii produced it. `instant_from` says which.
    inst, source = D.document_instant(text), "document"
    if inst is None:
        inst, source = _reader().modified(name), "download"
    out.update(classes=D.identify(text), reference=D.document_reference(text),
               encoding=doc.get("encoding"),
               scanned=bool(doc.get("scanned")),
               instant=inst.isoformat(sep=" ", timespec="minutes") if inst else None,
               instant_from=source if inst else "")
    return out


def waiting_documents() -> list[dict]:
    """What is sitting on the intake workbench, unfinished — and what each one says it is."""
    try:
        docs = _reader().waiting()
    except Exception as e:      # noqa: BLE001 — an unreadable _inbox/ must not blank the panel
        return [{"name": f"could not read _inbox/: {e}", "bytes": 0, "error": True}]
    for d in docs:
        if str(d.get("name", "")).lower().endswith(_CHEAP_TO_READ):
            d["recognised"] = recognise(d["name"])
    return docs


def document_text(name: str) -> dict:
    """A document's text, for reading BESIDE the form rather than in another window.

    A scan comes back with `scanned` true and an empty body. That is reported, never smoothed
    over: `docs/intake.md` is explicit that a figure must not be entered from a document that
    has not been read in full, and nothing can be read from an image here.
    """
    return _reader().extract(name)
