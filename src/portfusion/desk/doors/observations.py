"""THE OBSERVATIONS DOOR — the one place in `desk/` that REPLACES an account reading.

The third store door, beside `commit.py` (appends an event) and `marks.py` (replaces a mark).
`store/account-readings.csv` is what `Book.reconciliation()` compares the book to.

THE MARKS RULE COVERS THIS. *A feed may write a MARK — "a price, an FX rate, live equity" — on
the owner's per-line tick.* Live equity is named in that sentence. This door is not a new
permission; the marks rule grants it. The journal route is `marks` for the same reason: this is a
marks-class door, not a fourth kind of write.

WHAT IT REPLACES, AND WHAT IT LEAVES ALONE
------------------------------------------
A reading from IG's `/accounts` is IG's five figures under IG's names: funds, running P/L,
equity, deposit, available. It cannot supply NOTIONAL — that needs the open-positions endpoint,
which `feeds/ig.py` refuses because the same endpoint family places trades — and the record
keeps none on a spread-bet reading: the notional is derived. A spread-bet account reconciles on
its EQUITY.

WHAT IT WILL NOT DO
-------------------
  · WRITE A READING WITHOUT ITS EVIDENCE AND REFERENCE. Limbs 2 and 3 of statement-grade. A
    figure that cannot say what would retrieve it is the failure `rules.STATEMENT_GRADE` is
    written to prevent, and this is the door where that becomes enforceable rather than hoped
    for.
  · REPLACE A READING WHOSE OUTGOING VALUE IS NOT BANKED. `history/accounts.py:archive()` runs
    FIRST and the replace does not happen if it fails. Same ordering as `marks.py`, and the same
    reason: the outgoing reading is a data point that cannot be recovered.
  · ADD A ROW. One row per account, replaced. A new account is a decision, not a reading.
  · LEAVE A HALF-WRITTEN STORE. `envelope.atomic()` holds every target's bytes and restores all of
    them if anything raises.
"""
from __future__ import annotations

import csv
import pathlib as _pathlib

from portfusion.record import rules as D
from portfusion.record import schema
from portfusion.desk.doors import envelope

TABLE = "account-readings"

#: One row per ACCOUNT. Unlike `current-prices.csv` there is no history mixed into this table
#: and no carried line to protect — every row is a live reading and every one is replaceable.
KEYED_BY = "account"

#: What a reading may set. `positions` is a SHARE account's: the stock off a filed document. The
#: five after it are a SPREAD-BET account's, IG's own, and `_check()` holds each kind to its own.
SETTABLE = ("as_of", "at", "positions",
            "funds", "running_pl", "equity", "deposit", "available", "evidence", "reference")

#: A spread-bet reading's own figures: what IG prints on a statement, and the feed returns.
#: `available` is the feed's alone (a statement prints none), so it is not required.
SB_REQUIRED = ("funds", "running_pl", "equity", "deposit")
SB_NEVER = ("positions", "cash", "total")

#: What a SHARE account's reading must carry beyond REQUIRED: the stock its broker document states.
#: NOT the time it was pulled: the check is on units, which a close does
#: not move.
SHARE_REQUIRED = ("positions",)

#: ...and the cash and the total they make, where the document states the cash
#: (`rules.states_cash()`) — and NEVER where it does not. ii's holdings export states none, so a
#: cash figure on a reading off it would be another document's, filed under this one's evidence
#: and left to age there. THE CASH IS WRITTEN AS A CASH READING of the reading's day, the record's
#: one place for it (`_cash_rows()`); the total is checked and not kept, being the two together.
SHARE_CASH = ("cash", "total")

#: Without these a reading is not one. `as_of` because a figure with no date lets the freshness
#: indicator agree everything is fine; `evidence` and `reference` because limb 3 of
#: statement-grade asks what retrieves it a second time, and prose cannot be checked.
REQUIRED = ("as_of", "evidence", "reference")


class Refused(Exception):
    """The write did not happen and nothing was changed. Carries the reason."""


def paths() -> list:
    """Every file a write here can touch: the readings, the history they are banked into, and
    the journal. See `marks.paths()` for why a caller is given this rather than a list to copy.
    """
    from portfusion.history import accounts as AH
    return [schema.TABLES[TABLE].path, schema.TABLES["cash-readings"].path,
            _pathlib.Path(AH._FILE.path), schema.TABLES["journal"].path]


def banked() -> dict:
    """Is every outgoing reading on file? This door's precondition, asked of the account
    history alone: an unbanked reading refuses THIS write, and a price or rate history, the marks
    door's, neither refuses it nor is refused by it (`marks.banked()`).
    """
    from portfusion.history import accounts as AH
    unbanked = AH.check()
    return {"ok": not unbanked, "unbanked": unbanked}


def _rows_on_file() -> dict[str, list[str]]:
    """Every row of the table as its raw cells, by account."""
    path = schema.TABLES[TABLE].path
    out = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if i == 0 or not line.strip():
            continue
        cells = next(csv.reader([line]))
        out[cells[schema.TABLES[TABLE].header.index(KEYED_BY)]] = cells
    return out


def _merged(existing: list[str], reading: dict) -> list[str]:
    """The row on file with every SETTABLE cell taken from the reading; the rest stands.

    EVERY SETTABLE CELL IS THE NEW READING'S, and a field it does not carry is BLANK: the old
    value would be a figure filed under evidence that never stated it. Only what is not a
    reading's (the account) stays from the row on file.
    """
    fields = schema.TABLES[TABLE].fields
    cells = list(existing)
    for i, f in enumerate(fields):
        if f.name in SETTABLE:
            cells[i] = schema.cell(f, reading.get(f.name))
    return cells


def _check(reading: dict, filed: list | None = None, document=None) -> None:
    """Every limb present, or the whole write is refused. `filed` and `document` stand in for
    `_archive/statements/` when a document about to be filed is checked (`preflight()`)."""
    account = str(reading.get("account") or "").strip()
    if not account:
        raise Refused("a reading with no account names nothing")
    missing = [f for f in REQUIRED if not str(reading.get(f) or "").strip()]
    if missing:
        raise Refused(
            f"{account}: no {', '.join(missing)}. A reading needs its date and something that "
            f"retrieves it again — an account figure that cannot be asked for a second time is "
            f"not evidence, it is a recollection with a number attached.")
    key = str(reading["evidence"]).strip()
    ev = D.EVIDENCE_BY_KEY.get(key)
    if ev is None:
        raise Refused(
            f"{account}: {key!r} is not a class in EVIDENCE_CLASSES, so nothing states what "
            f"authority stands behind this figure or what would retrieve it.")
    if ev.retrieval == "none":
        raise Refused(
            f"{account}: {key} is a class NOTHING retrieves ({ev.authority}). The "
            f"reconciliation baseline is the figure the whole check is judged against; it may "
            f"not rest on something that cannot be asked for again.")
    if D.ACCOUNT_KIND.get(account) != "spread bet":
        _check_share(account, reading, ev, filed, document)
    else:
        _check_spread_bet(account, reading)


def _check_spread_bet(account: str, reading: dict) -> None:
    """A spread-bet account's reading is IG's figures under IG's names, once each, agreeing as
    IG's own arithmetic says: funds + running P/L = equity, equity − deposit = available. The
    notional is never set — no allowlisted IG endpoint returns it, and the record derives it —
    and the share columns stay blank."""
    def blank(f):
        return reading.get(f) is None or str(reading[f]).strip() == ""

    set_wrongly = [f for f in SB_NEVER if not blank(f)]
    if set_wrongly:
        raise Refused(f"{account}: a spread-bet reading is IG's figures, not "
                      f"{', '.join(set_wrongly)}: its NOTIONAL is derived, never read, and its cash "
                      f"is its funds.")
    missing = [f for f in SB_REQUIRED if blank(f)]
    if missing:
        raise Refused(f"{account}: no {', '.join(missing)}. A spread-bet reading carries IG's own "
                      f"figures, each once.")
    try:
        funds, pl, equity, deposit = (float(reading[f]) for f in SB_REQUIRED)
        available = None if blank("available") else float(reading["available"])
    except (TypeError, ValueError):
        raise Refused(f"{account}: {', '.join(SB_REQUIRED)} must be numbers.")
    if abs(funds + pl - equity) >= 0.005:
        raise Refused(f"{account}: funds {funds:,.2f} plus running P/L {pl:,.2f} is "
                      f"{funds + pl:,.2f}, not the equity {equity:,.2f}. One of the three is not IG's.")
    if available is not None and abs(equity - deposit - available) >= 0.005:
        raise Refused(f"{account}: equity {equity:,.2f} less deposit {deposit:,.2f} is "
                      f"{equity - deposit:,.2f}, not the available {available:,.2f}.")


def _check_share(account: str, reading: dict, ev, filed=None, document=None) -> None:
    """A share account's reading: the figures off one FILED holdings export, adding up, and its
    UNITS AGREEING WITH THE BOOK at the document's date.

    Nothing enters but through the door. The document must already sit in `_archive/statements/` —
    the Bench files it when it is worked — because a baseline citing a document nobody filed is a
    figure nothing retrieves. The figures must be the document's own: where it states the cash,
    stock
    plus cash is the total, to the penny, or one of the three was mistyped; where it states none,
    the stock is the reading. And every holding's units must be the book's:
    a contract note brings every trade, and what a units check catches is
    what none carries — a reinvested dividend, a corporate action, a wrong quantity. So a share
    reading on file MEANS its units agreed; `Book.reconciliation_verdict()` says so.
    """
    def blank(f):
        return reading.get(f) is None or str(reading[f]).strip() == ""

    states = D.states_cash(ev)
    missing = [f for f in SHARE_REQUIRED + (SHARE_CASH if states else ()) if blank(f)]
    if missing:
        raise Refused(f"{account}: no {', '.join(missing)}. A share account's reading is the "
                      f"figures one broker document states: the stock, and the cash and the "
                      f"total where it states them.")
    unstated = [f for f in SHARE_CASH if not states and not blank(f)]
    if unstated:
        raise Refused(f"{account}: {ev.label} states no cash, so a reading off it has no "
                      f"{', '.join(unstated)}. The account's cash reading is added when a total "
                      f"is shown.")
    if str(reading.get("equity") or "").strip():
        raise Refused(f"{account}: a share account has no equity figure; its total is stock "
                      f"plus cash.")
    if not _baseline_class(ev):
        raise Refused(f"{account}: {ev.key} is not the broker's own statement of the account's "
                      f"holdings, so a baseline cannot rest on it. It may be: "
                      f"{', '.join(c['key'] for c in share_classes())}.")
    figures = ("positions",) + (SHARE_CASH if states else ())
    try:
        stock, *rest = (float(reading[f]) for f in figures)
    except (TypeError, ValueError):
        raise Refused(f"{account}: {', '.join(figures)} must be numbers.")
    if rest and abs(stock + rest[0] - rest[1]) >= 0.005:
        cash, total = rest
        raise Refused(f"{account}: stock {stock:,.2f} plus cash {cash:,.2f} is "
                      f"{stock + cash:,.2f}, not the total {total:,.2f}. One of the three was "
                      f"not read off the document.")
    source = D.evidence_source(ev.key, reference=str(reading["reference"]), account=account)
    names = D.filed_as(source, schema.filed_statements() if filed is None else filed) or []
    if not names:
        raise Refused(f"{account}: \"{source}\" names no document in _archive/statements/. "
                      f"A holdings export is filed on the Bench, which writes its reading.")
    if len(names) > 1:
        raise Refused(f"{account}: \"{source}\" matches {len(names)} filed documents "
                      f"({'; '.join(names)}); its reference must name one.")
    _check_units(account, str(reading["as_of"])[:10], names[0], ev.key, document)


def preflight(reading: dict, filed_as: str, document) -> None:
    """Refuse now what `write()` would refuse once the document is filed as `filed_as` — read
    from `document`, where it still is. The Bench asks this at its gate, so a holdings export is
    never filed with a reading this door would then turn away."""
    _check(reading, filed=[filed_as], document=document)
    _cash_rows([reading])
    if reading["account"] not in _rows_on_file():
        raise Refused(f"{TABLE}.csv has no row for {reading['account']}. This door REPLACES a "
                      f"reading; it does not add one.")


def _check_units(account: str, as_of: str, name: str, key: str, document=None) -> None:
    """Refuse unless every holding's units in `name` are the book's at `as_of`, naming each one
    that is not. The comparison is `Book.units_check()`'s; this only reads the document."""
    from portfusion.engine import Book
    from portfusion.desk.intake import read_document, read_rows
    path = document or schema.statements() / name
    units = read_rows.holdings(read_document.extract_file(path)["text"], key)
    if not units:
        raise Refused(f"{account}: {name} lists no units this door can read.")
    check = Book().units_check(account, as_of, units)
    differ = check[~check["agrees"]]
    if not differ.empty:
        raise Refused(
            f"{account}: the units in {name} are not the book's at {as_of} — "
            + "; ".join(f"{r.ticker} book {r.book:,.0f}, broker {r.broker:,.0f}"
                        for r in differ.itertuples(index=False))
            + ". Enter what the book is missing on the Bench first — a reinvested dividend, a "
              "corporate action — then write the reading.")


def _baseline_class(ev) -> bool:
    """May a share account's baseline rest on this kind of document? The broker's OWN statement
    of the holdings (`official`, covering positions), filed, open to new entries, and one whose
    units this door can read (`rules.HOLDINGS_COLUMNS`). Not `hl-account-totals`, which restates
    the valuation rather than being it."""
    return (ev.official and "positions" in ev.covers and ev.retrieval == "document"
            and ev.key not in D.CLOSED_TO_NEW_ENTRIES and ev.key in D.HOLDINGS_COLUMNS)


def share_classes() -> list[dict]:
    """The document kinds a share account's baseline may rest on, from the classes themselves."""
    return [{"key": e.key, "label": e.label, "reference_is": e.reference_is}
            for e in D.EVIDENCE_CLASSES if _baseline_class(e)]


def _cash_rows(readings: list[dict]) -> list[dict]:
    """The cash readings these readings' documents state, each dated its reading's day, less any
    on file at the same figure. Raises `Refused` where one is on file for that day at another:
    two documents of one day disagree, and this door does not choose."""
    on_file = {(c.account, c.as_of.isoformat()): c.cash for c in D.cash_readings}
    out = []
    for r in readings:
        if r.get("cash") is None or str(r["cash"]).strip() == "":
            continue
        account, day, cash = r["account"], str(r["as_of"])[:10], float(r["cash"])
        was = on_file.get((account, day))
        if was is not None and abs(was - cash) < 0.005:
            continue
        if was is not None:
            raise Refused(f"{account} already has a cash reading of {was:,.2f} for {day}; this "
                          f"reading's document says {cash:,.2f}. One of them is wrong, and this "
                          f"door does not choose.")
        out.append({"account": account, "as_of": day, "cash": cash,
                    "evidence": r["evidence"], "reference": r["reference"]})
        on_file[(account, day)] = cash          # a second reading of it in this write is the same
    return out


@envelope.held
def write(readings: list[dict] | None = None) -> dict:
    """Bank the outgoing readings, then replace them. The one writing action on this door.

    THE REFUSAL IS THE FEATURE, as it is on the other two doors: the whole operation is refused
    — leaving the file byte-identical — if any reading lacks its date, its evidence or its
    reference, names an account that is not on file, or rests on a class nothing retrieves.
    """
    readings = list(readings or [])
    if not readings:
        raise Refused("nothing to write")
    for r in readings:
        _check(r)

    from portfusion.history import accounts as AH
    on_file = _rows_on_file()
    unknown = [r["account"] for r in readings if r["account"] not in on_file]
    if unknown:
        raise Refused(
            f"{TABLE}.csv has no row for {sorted(unknown)}. This door REPLACES a reading; it "
            f"does not add one. A new account is a decision, not an observation.")

    new_rows = {r["account"]: _merged(on_file[r["account"]], r) for r in readings}
    cash = _cash_rows(readings)
    path = schema.TABLES[TABLE].path
    at = schema.record_instant()

    # THE BANKING SHARES THE ENVELOPE (`paths()` holds the history), as on the marks door: a
    # refusal after the outgoing readings were banked takes the banking back with the rest.
    with envelope.record_follows_the_files(), envelope.atomic(*paths()):
        # STEP ONE, AND THE REPLACE DOES NOT HAPPEN IF IT FAILS.
        try:
            archived = len(AH.archive(verbose=False))
        except Exception as e:                      # noqa: BLE001 — reported, never swallowed
            raise Refused(f"the outgoing readings could not be banked, so nothing was "
                          f"replaced: {e}")
        still = banked()
        if not still["ok"]:
            raise Refused(
                f"{len(still['unbanked'])} reading(s) are still unbanked after archiving. "
                f"Refusing to replace a reading whose outgoing value is not on file.")

        before = len(schema.load(TABLE))
        key = schema.TABLES[TABLE].header.index(KEYED_BY)
        envelope.rewrite(path, lambda cells: new_rows.get(cells[key], cells))

        # READ IT BACK THROUGH THE LOADER THE BUILD USES. A replace must not move the count.
        loaded = schema.load(TABLE)
        if len(loaded) != before:
            raise Refused(f"{TABLE}.csv went from {before} to {len(loaded)} rows. A replace "
                          f"must not change the count.")

        # `replace`, NOT `append` — this door adds no rows, so the reconciliation arithmetic
        # must not count these against the table's opening figure. The ref is the reading's
        # own date, which is what retrieves it: account-statements.csv holds what it displaced.
        # A READING'S CASH, the same write: a cash reading of its own day, appended in its place.
        if cash:
            envelope.place({"cash-readings": [envelope.rendered("cash-readings", c) for c in cash]})
        ref = " ".join(sorted({str(r["as_of"]) for r in readings}))
        envelope.journal(
            [("marks", "replace", TABLE, len(readings), ref,
              f"{len(readings)} account reading{'' if len(readings) == 1 else 's'} replaced")]
            + ([("marks", "append", "cash-readings", len(cash), ref,
                 f"{len(cash)} cash reading(s), as the readings' documents state them")]
               if cash else []),
            at=at)

        D.reload_store()

        # The readings just written are themselves banked, so this ends with the record and its
        # history agreeing — the same second half `marks.write()` performs.
        banked_after = len(AH.archive(verbose=False))
    return {"written": len(readings), "accounts": sorted(r["account"] for r in readings),
            "cash": len(cash), "banked_before": archived, "banked_after": banked_after}
