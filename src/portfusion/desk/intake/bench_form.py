"""THE BENCH'S FORM — what a proposed row may hold, and whether the store would take it.

Every column is `record/schema.py`'s, every choice is read off the record, and a row is checked
by the loader's own parse (`validate_row()`). Nothing here writes; `bench.py` keeps the item, and
answers for each name here as for its own.
"""
from __future__ import annotations

from portfusion.desk.engine import RecordUnavailable, _guarded
from portfusion.record import schema


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

