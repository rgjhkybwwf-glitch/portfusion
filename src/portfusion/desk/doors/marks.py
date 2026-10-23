"""THE MARKS DOOR — the one place in `desk/` that REPLACES a mark, or RETIRES one nothing holds.

`commit.py` APPENDS AN EVENT; this REPLACES A MARK, and the two are different operations on
purpose. An event happened once and is history, so its table is append-only. A price is replaced
by design at every refresh — which is safe only because the outgoing value is BANKED first, and
that is the ordering this module refuses to skip.

THE MARKS RULE IS WHAT MAKES THIS LEGAL, and it was written for exactly this: *a feed may write a
MARK on the owner's tick; it may never write an EVENT.* This is the door `Action(writes="marks")`
declares.

THE ORDERING IS ENFORCED BY THE FLOW, NOT REMEMBERED. `feeds/refresh.py` exists because two
commands meant two chances to forget one. Here the bank runs first and the replace does not
happen if it fails — the same guarantee, arriving on a screen.

WHAT IT WILL NOT DO:

  · WRITE A MARK WITHOUT A SOURCE AND A DATE TOGETHER. Rule 1 of `docs/prices.md` — *"a stale
    price wearing today's date is worse than a stale price, because the freshness indicator then
    agrees everything is fine."* This is where that rule is enforced.
  · WRITE A PRICE THAT DOES NOT SAY WHICH INSTANT IT DESCRIBES. `struck` is the feed's — a close
    or a live read — and a live read carries the UTC instant, on the mark's own date. A price
    typed by hand says neither, which is the point: nothing is typed.
  · TOUCH A CARRIED LINE. `rules.STATEMENT_PRICED` for shares, `rules.RATE_CARRIED` for rates.
    Those are decisions about what the book stops watching and a refresh must not quietly undo one.
  · TOUCH A ROW IT WAS NOT GIVEN. Every line this module does not replace comes through
    BYTE-IDENTICAL, because it is passed through as the bytes it was read as rather than
    re-rendered.
  · LEAVE A HALF-WRITTEN STORE. `commit.atomic()` holds every target's bytes and restores all of
    them if anything raises. Same envelope as the other doors, deliberately.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import pathlib as _pathlib
import re

from portfusion.record import rules as D
from portfusion.record import schema
from portfusion.desk.doors import commit

#: The two tables a refresh replaces, and which column identifies a row in each: a line's price
#: by its ticker, a currency's rate by the currency. Every row of both is live.
KEYED_BY = {"current-prices": "mark_key", "fx": "currency"}


class Refused(Exception):
    """The write did not happen, and nothing was touched. Carries why, in full."""


def paths() -> list:
    """Every file a write here can touch: the two mark tables, the two histories they are
    banked into, and the journal.

    NAMED SO A CALLER DOES NOT KEEP A SECOND LIST. `write()` already holds these under
    `commit.atomic()`; a caller combining this door with another has to hold the union of both,
    and a hand-copied list is the drift this project keeps deleting things for. The Reconcile
    write is that caller — its levels and its equity are ONE observation and must land or fail
    together, which is the whole reason the reading takes them in one pass.
    """
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH
    # `_FILE.path` is the one actually written, and the one a test redirects — a list of paths
    # that is not the list being written is not an envelope.
    return [schema.TABLES["current-prices"].path, schema.TABLES["fx"].path,
            _pathlib.Path(PH._FILE.path), _pathlib.Path(FX._FILE.path),
            schema.TABLES["journal"].path]


def carried() -> dict:
    """Every line the book deliberately does not refresh, with its reason.

    TWO DICTS, TWO DIFFERENT TESTS, one outcome. `STATEMENT_PRICED` is "no feed AND immaterial";
    `RATE_CARRIED` is "nothing the book values is denominated in it". They are kept apart in
    `record/rules.py` so the first exemption stays as narrow as its own comment insists.

    A CARRIED LINE IS NOT AN UNPRICED ONE. Unpriced is a gap somebody is chasing; carried is a
    decision with its reason on the row, and the bay shows them differently for that reason.
    """
    out = {t: {"kind": "price", "why": why} for t, why in D.STATEMENT_PRICED.items()}
    out.update({k: {"kind": "rate", "why": why} for k, why in D.RATE_CARRIED.items()})
    return out


def banked() -> dict:
    """Are the OUTGOING marks on file? The bay's step 1, and this door's precondition.

    Asks the history modules rather than re-deriving it: `check()` returns the live marks that
    are NOT yet banked, on both halves. Empty both times means a refresh is safe to run.

    THE DESK MAY IMPORT `history/`, and only the BUILD may not — a report build that can fail
    because a CSV moved is a worse book, which is why that rule exists and why it does not reach
    here. Imported inside the function so the desk still starts if the histories are unavailable.
    """
    from portfusion.history import accounts as AH
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH
    prices, rates, accounts = PH.check(), FX.check(), AH.check()
    # ACCOUNTS ARE REPORTED BUT NOT FOLDED INTO `ok`. `ok` is the PRICE REFRESH's
    # precondition — may these prices and rates be replaced — and an unbanked account
    # observation is no reason to refuse a price refresh. They are separate doors and one
    # vendor's problem is not the other's, which is the rule the bay already keeps between IG
    # and TradingView. The door that REPLACES an observation gates on `accounts_ok`.
    return {"prices_unbanked": prices, "rates_unbanked": rates,
            "accounts_unbanked": accounts,
            "ok": not (prices or rates),
            "accounts_ok": not accounts}


def _require(row: dict, fields: tuple, what: str) -> None:
    """Every field present and non-blank, or the whole write is refused.

    RULE 1 OF `docs/prices.md`, ENFORCED. A price without its date, or without a source that can
    be asked again, is the failure that makes the book claim to be fresher than it is. Refusing
    the WHOLE write rather than skipping the row is deliberate: a partial refresh is how a book
    ends up with eleven lines on one date and one on another.
    """
    missing = [f for f in fields if not str(row.get(f) or "").strip()]
    if missing:
        raise Refused(
            f"{what}: no {', '.join(missing)}. A mark needs its price, its date and a source "
            f"that retrieves it again — update a price and its date together, or the freshness "
            f"indicator agrees everything is fine when it is not.")


def _replace_lines(table: str, new_rows: dict) -> str:
    """The table's text with `new_rows` swapped in by key, everything else UNTOUCHED.

    LINE BY LINE, NOT THROUGH A CSV WRITER, and that is the whole point. Re-rendering the file
    would requote every row to this writer's taste — `fx.csv`'s historical rows would change
    bytes without changing meaning, and a diff nobody can read is a diff nobody checks. Only the
    lines being replaced are rendered; every other line is passed through exactly as read.

    The header is line one and is never a data row. A key is read with `csv.reader` rather than
    `split(",")` because a quoted field may contain one.
    """
    path = schema.TABLES[table].path
    key_col = schema.TABLES[table].header.index(KEYED_BY[table])
    out, seen = [], set()
    lines, eol = commit.lines_and_eol(path)         # returned in the file's own ending
    for i, line in enumerate(lines):
        if i == 0 or not line.strip():
            out.append(line)
            continue
        key = next(csv.reader([line]))[key_col]
        if key in new_rows:
            buf = io.StringIO()
            csv.writer(buf, lineterminator="").writerow(new_rows[key])
            out.append(buf.getvalue())
            seen.add(key)
        else:
            out.append(line)
    unknown = set(new_rows) - seen
    if unknown:
        raise Refused(
            f"{table}.csv has no row for {sorted(unknown)}. This door REPLACES a mark; it does "
            f"not add a line. A new instrument is an event and goes to the bench.")
    return eol.join(out) + eol


def _asof(table: str, prices: list[dict], rates: list[dict]) -> str:
    """The date the replaced marks are dated, as the journal's `ref`.

    ONE DATE OR SEVERAL, STATED EITHER WAY. A refresh normally dates every line in a table on
    one day, and then that date is what retrieves the write — `price-history.csv` holds what
    each of those rows displaced, keyed by it. It does NOT have to — `feeds/tv.py` says why
    lines are struck apart — and nothing stops a partial refresh dating two lines
    differently. So the distinct dates are joined rather than the first one
    taken, because a `ref` naming one of two days retrieves half the write.
    """
    rows = prices if table == "current-prices" else rates
    return " ".join(sorted({str(r.get("as_of") or "").strip() for r in rows if r.get("as_of")}))


_UTC_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _require_instant(row: dict, what: str) -> None:
    """`struck` is a known kind, and `at` agrees with it — or the whole write is refused.

    A LIVE READ IS AN INSTANT, so it carries one, in UTC, on the mark's own date: an `at` on
    another day is a stale level wearing a fresh date, the failure `docs/prices.md`'s rule 1 exists
    for. A CLOSE IS A DATE, so it carries none — an instant on a close would claim a precision a
    daily figure does not have.
    """
    struck, at = str(row.get("struck") or ""), str(row.get("at") or "")
    if struck not in schema.STRUCK_KINDS:
        raise Refused(f"{what}: `struck` is {struck!r}; a mark says whether it is one of "
                      f"{schema.STRUCK_KINDS}, and only the feed that fetched it can.")
    if struck == "close" and at:
        raise Refused(f"{what}: a close is a date and carries no instant, but `at` is {at!r}.")
    if struck == "live":
        if not _UTC_INSTANT.match(at):
            raise Refused(f"{what}: a live read carries its UTC instant as YYYY-MM-DDTHH:MM:SSZ; "
                          f"`at` is {at!r}.")
        if D.uk_date(at) != str(row.get("as_of") or "")[:10]:
            raise Refused(f"{what}: struck at {at} but dated {row.get('as_of')} — a live read is "
                          f"dated the UK day it describes.")


@commit.held
def write(prices: list[dict] | None = None, rates: list[dict] | None = None) -> dict:
    """Bank the outgoing marks, then replace them. ONE operation, or none of it.

    `prices` are `{mark_key, price, currency, as_of, source, struck, at}`; `rates` are
    `{currency, rate, as_of, source, struck}` — each table's own columns, so nothing here has to
    know a shape the schema does not already hold.

    Raises `Refused`, leaving every file byte-identical, if a row is incomplete, names a line the
    book carries, names a row that is not there, or if the outgoing marks could not be banked.

    THE BANKING IS INSIDE THE ENVELOPE, both halves of it: `paths()` holds the two histories with
    the tables, so a refusal after the outgoing marks were banked takes the banking back too.
    Until 21 Oct 2026 the first half ran before `atomic()`, which held the tables and the journal
    alone.
    """
    prices, rates = list(prices or []), list(rates or [])
    if not (prices or rates):
        raise Refused("nothing to write — no prices and no rates were ticked.")

    held = carried()
    for row in prices:
        _require(row, ("mark_key", "price", "as_of", "source"), f"price {row.get('mark_key')!r}")
        _require_instant(row, f"price {row.get('mark_key')!r}")
        if row["mark_key"] in held:
            raise Refused(f"{row['mark_key']} is carried, not refreshed: {held[row['mark_key']]['why']}")
    for row in rates:
        _require(row, ("currency", "rate", "as_of", "source"), f"rate {row.get('currency')!r}")
        if row["currency"] in held:
            raise Refused(f"{row['currency']} is carried, not refreshed: "
                          f"{held[row['currency']]['why']}")

    from portfusion.history import fx as FX
    from portfusion.history import prices as PH

    by_table = {}
    if prices:
        by_table["current-prices"] = {r["mark_key"]: [r["mark_key"], r["price"], r["currency"],
                                                    r["as_of"], r["source"], r["struck"],
                                                    r.get("at") or ""] for r in prices}
    if rates:
        by_table["fx"] = {r["currency"]: [r["currency"], r["rate"], r["as_of"], r["source"],
                                          r.get("struck") or ""]
                          for r in rates}

    # RECORD TIME, DECIDED ONCE. Both tables of one refresh carry the same instant, because
    # they are one write — a reader asking "what did this refresh do" must not have to notice
    # that the prices and the rates are a second apart.
    at = schema.record_instant()

    with commit._record_follows_the_files(), commit.atomic(*paths()):
        # STEP 1, AND IT IS NOT OPTIONAL. Whatever is on file now is banked BEFORE it is
        # replaced, because a refresh done without this is a data point that cannot be recovered.
        try:
            archived = {"prices": len(PH.archive(verbose=False)),
                        "rates": len(FX.archive(verbose=False))}
        except Exception as e:                      # noqa: BLE001 — reported, never swallowed
            raise Refused(f"the outgoing marks could not be banked, so nothing was replaced: {e}")

        still = banked()
        if not still["ok"]:
            raise Refused(
                f"{len(still['prices_unbanked'])} mark(s) and {len(still['rates_unbanked'])} "
                f"rate(s) are still unbanked after archiving. Refusing to replace a mark whose "
                f"outgoing value is not on file.")

        before = {t: len(schema.load(t)) for t in by_table}
        for table, rows in by_table.items():
            schema.TABLES[table].path.write_text(_replace_lines(table, rows), encoding="utf-8",
                                                 newline="")
        # VERIFY BY READING IT BACK, through the loader the build uses — the same check the
        # other door makes. A REPLACE MUST NOT MOVE THE ROW COUNT: if it did, this wrote a line
        # rather than replacing one, which is the failure worth catching here.
        for table, rows in by_table.items():
            loaded = schema.load(table)
            if len(loaded) != before[table]:
                raise Refused(f"{table}.csv went from {before[table]} to {len(loaded)} rows. A "
                              f"replace must not change the count.")
            fields = schema.TABLES[table].fields
            for key, cells in rows.items():
                expect = tuple(schema._parse(f, c, table, 0) for f, c in zip(fields, cells))
                back = next(r for r in loaded if r[0] == key)
                if tuple(back) != expect:
                    raise Refused(f"{table}.csv row {key} did not read back as written:\n"
                                  f"  wrote {expect}\n  read  {tuple(back)}")

        # RECORD TIME, INSIDE THE SAME ENVELOPE — a mark cannot be replaced without the
        # journal saying so, because a rollback takes both.
        #
        # `op` IS `replace` AND THAT IS LOAD-BEARING, not a label. This door replaces rows and
        # adds none, so the check must not count these against the table's opening figure:
        # counted as arrivals, every refresh would read as a batch of unaccounted rows and the
        # line would stop being read. The two columns exist for exactly this case.
        #
        # THE REF IS THE MARK DATE, which is what retrieves the write — every replaced row
        # carries that `as_of`, and `store/price-history.csv` holds the value it displaced.
        commit.journal(
            [("marks", "replace", table, len(rows), _asof(table, prices, rates),
              f"{len(rows)} {'mark' if table == 'current-prices' else 'rate'}"
              f"{'' if len(rows) == 1 else 's'} replaced")
             for table, rows in sorted(by_table.items())],
            at=at)

        # THE RECORD IN MEMORY IS RE-READ, AND WITHOUT THIS THE WRITE IS INVISIBLE.
        # `CURRENT_PRICES` and `fx_rows` are module-level in record/rules.py and read once at
        # import; `engine.load_store()` takes prices and FX from those attributes rather than
        # from the files. A long-lived desk would therefore go on serving the mark it just
        # replaced, however many times the engine was rebuilt. record/rules.py owns the reload
        # because it owns every table; a refusal after it reloads again, from the files restored.
        D.reload_store()

        # STEP 4'S SECOND HALF. The marks just written are themselves banked, so a refresh ends
        # with the record and its history agreeing — `python3 -m portfusion.feeds.refresh
        # --bank`, without the second command.
        banked_after = {"prices": len(PH.archive(verbose=False)),
                        "rates": len(FX.archive(verbose=False))}

    return {"prices": len(prices), "rates": len(rates),
            "banked_before": archived, "banked_after": banked_after,
            "tables": sorted(by_table)}


def first_paths() -> list:
    """The files `first()` writes: the live prices and the journal. The caller holds them."""
    return [schema.TABLES["current-prices"].path, schema.TABLES["journal"].path]


def first(prices: list[dict], route: str, ref: str, at: str) -> list[str]:
    """A NEW CONTRACT'S FIRST MARK, appended inside the caller's envelope with the bet it prices.
    There is no price on file to bank or replace; the next refresh banks this one as it replaces
    it. Complete as `write()` requires: price, date, source and instant. Returns the lines marked."""
    for row in prices:
        _require(row, ("mark_key", "price", "as_of", "source"), f"price {row.get('mark_key')!r}")
        _require_instant(row, f"price {row.get('mark_key')!r}")
    named = [r["mark_key"] for r in prices]
    priced = sorted(set(named) & {r[0] for r in schema.load("current-prices")})
    if priced:
        raise Refused(f"{', '.join(priced)} has a mark already: the Price Refresh replaces it")
    path = schema.TABLES["current-prices"].path
    was = len(schema.load("current-prices"))
    commit._append(path, path.read_bytes(), [commit._csv_line(
        [r["mark_key"], r["price"], r["currency"], r["as_of"], r["source"], r["struck"],
         r.get("at") or ""]) for r in prices])
    if len(schema.load("current-prices")) != was + len(prices):
        raise Refused("current-prices.csv did not gain exactly the new marks")
    commit.journal([(route, "append", "current-prices", len(prices), ref,
                     f"{', '.join(named)}: first mark")], at=at)
    return named


def retire_paths() -> list:
    """The files `retire()` writes: the live prices, the contracts, the price history the
    outgoing price is banked into, and the journal. The caller holds them in its envelope."""
    from portfusion.history import prices as PH
    return [schema.TABLES["current-prices"].path, schema.TABLES["contracts"].path,
            _pathlib.Path(PH._FILE.path), schema.TABLES["journal"].path]


def retire(lines: list[str], route: str, ref: str, at: str) -> list[str]:
    """RETIRE A LINE NOTHING HOLDS: bank its live price and take it out of current-prices.csv.
    An IG contract also has its epic blanked in contracts.csv — the record's own definition of a
    closed contract (`schema.CONTRACTS`: "nothing reads its level again"). A share has no epic:
    the price going is the whole of it. Returns the lines retired, sorted.

    A MARK NOBODY NEEDS, which every refresh would go on fetching and the guard refuses. The sale
    that closes a contract's last leg, or sells a share out of every account, retires it in the
    same write (`commit.commit()`), so the book never stands with a line priced that nothing
    holds.

    RUNS INSIDE THE CALLER'S ENVELOPE, holding `retire_paths()`, and opens none of its own: a
    refusal here raises, and the caller's `atomic()` restores every file. The outgoing price is
    banked first, as every replaced mark is; one that will not bank is not retired.
    """
    lines = sorted(set(lines))
    if not lines:
        return []
    known = {r[0] for r in schema.load("contracts")}
    contracts = [x for x in lines if x in known]
    shares = [x for x in lines if x not in known]
    from portfusion.history import prices as PH
    try:
        PH.archive(verbose=False)
    except Exception as e:                          # noqa: BLE001 — reported, never swallowed
        raise Refused(f"the outgoing price could not be banked, so nothing was retired: {e}")
    unbanked = sorted({m["mark_key"] for m in PH.check()} & set(lines))
    if unbanked:
        raise Refused(f"{', '.join(unbanked)}: the live price is not in the history, so it is "
                      f"not retired")

    prices = schema.TABLES["current-prices"].path
    was = len(schema.load("current-prices"))
    rows, eol = commit.lines_and_eol(prices)
    kept = [line for i, line in enumerate(rows)
            if i == 0 or not line.strip() or next(csv.reader([line]))[0] not in lines]
    gone = len(rows) - len(kept)
    prices.write_text(eol.join(kept) + eol, encoding="utf-8", newline="")

    if contracts:
        path = schema.TABLES["contracts"].path
        out = []
        rows, eol = commit.lines_and_eol(path)
        for i, line in enumerate(rows):
            cells = next(csv.reader([line])) if line.strip() else []
            out.append(",".join([cells[0], "", *cells[2:]])
                       if i and cells and cells[0] in contracts else line)
        path.write_text(eol.join(out) + eol, encoding="utf-8", newline="")

    # VERIFY BY READING IT BACK, as every door does.
    loaded = schema.load("current-prices")
    if len(loaded) != was - gone or any(r[0] in lines for r in loaded):
        raise Refused(f"current-prices.csv did not lose exactly {', '.join(lines)}")
    epics = {r[0]: r[1] for r in schema.load("contracts")}
    if any(epics.get(c) for c in contracts) or not all(c in epics for c in contracts):
        raise Refused(f"contracts.csv did not close exactly {', '.join(contracts)}")

    entries = []
    if gone:
        said = [f"{', '.join(contracts)}: no leg on it stays open"] if contracts else []
        said += [f"{', '.join(shares)}: no account holds it"] if shares else []
        entries.append((route, "remove", "current-prices", gone, ref,
                        "live price retired — " + "; ".join(said)))
    if contracts:
        entries.append((route, "replace", "contracts", len(contracts), ref,
                        f"{', '.join(contracts)}: epic blanked, a contract with no epic is closed"))
    commit.journal(entries, at=at)
    return lines


@commit.held
def bank_closes(day: str, prices: list[dict] | None = None,
                rates: list[dict] | None = None) -> dict:
    """File PAST CLOSES into the price and FX histories, and leave the live marks alone: one
    day's, or the rates the record lacks on several days (`Book.rate_gaps()`), each no later
    than `day`.

    THE QUARTER END FETCHED AFTER THE DAY: a close should not hang on one
    evening. The engine values any date from these histories — `Book._marks_at()` takes the
    newest mark on or before it — so closes dated the quarter end are all a freeze needs,
    whatever the live marks have moved on to since. `current-prices.csv` and `fx.csv` are not
    touched, which is why this door has no ordering against a refresh.

    A CLOSE OUTRANKS A LIVE READ OF ITS OWN DAY. A
    (line, date) already on file at the same figure is skipped; held by a live read of that day,
    the read is REPLACED — it leaves the file, the close lands, and a line says so (a live read
    is that day seen earlier, never a wrong figure: `history/prices.py`); held by a statement's
    price or a reconstruction, that is SUPERSEDED and kept, a correction; held by a DIFFERENT
    close, the whole write is refused, because one of the two is wrong and a door cannot say
    which. `history/prices.py` keeps the next archive step
    from striking the live read back over the close. Refused too, writing nothing: a line without its figure, date and source,
    a carried line, a line dated after `day`, and anything that is not a close — a live read
    describes an instant, and a quarter is valued at closes.

    No journal row: `journal.csv` counts the record's tables, and the histories are banked by
    `write()` unjournalled in the same way.
    """
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH

    prices, rates = list(prices or []), list(rates or [])
    if not (prices or rates):
        raise Refused("nothing to bank — no closes were ticked.")
    try:
        when = _dt.date.fromisoformat(str(day))
    except ValueError:
        raise Refused(f"{day!r} is not a date.")
    if when >= _dt.date.today():
        raise Refused(f"{day} is not a past day. Today's marks are written by the ordinary "
                      f"refresh, which replaces them.")
    day = when.isoformat()
    held = carried()

    def _settle(what, key, date, value, on_file, struck_of):
        """None to append, "same" to skip, the live read the close supersedes — or Refused."""
        if date > day:
            raise Refused(f"{what} is dated {date}, after {day}: a later day's close is not "
                          f"that day's.")
        was = on_file.get((key, date))
        if was is None:
            return None
        if float(was[value[0]]) == float(value[1]):
            return "same"
        if struck_of(was) == "close":
            raise Refused(f"{what} already has a close of {was[value[0]]} for {date}; this one "
                          f"says {value[1]}. One of them is wrong, and this door does not choose.")
        return was

    def _supersede(was, field, figure, said):
        """A live read leaves the file; anything else is superseded, its status moving and its
        provenance staying — `AppendOnlyCSV.restruck()`'s rule, both histories'."""
        if was.get("struck") == "live":
            dropped.append(id(was))
            superseded.append(f"{said} {was['date']}: the live read {was[field]} is replaced by "
                              f"that day's close {figure}")
            return
        superseded.append(f"{said} {was['date']}: {was[field]} is superseded by that day's "
                          f"close {figure}")
        was["status"] = "superseded"

    rows_p, rows_f = PH.load(), FX.load()
    on_file_p = {(r["mark_key"], r["date"]): r for r in rows_p if r["status"] == PH.LIVE}
    new_p, superseded, same, dropped = [], [], 0, []
    for row in prices:
        _require(row, ("mark_key", "price", "currency", "as_of", "source"),
                 f"close {row.get('mark_key')!r}")
        if row["mark_key"] in held:
            raise Refused(f"{row['mark_key']} is carried, not refreshed: "
                          f"{held[row['mark_key']]['why']}")
        if row.get("struck") != "close":
            raise Refused(f"{row['mark_key']}: struck {row.get('struck')!r}, not a session close. "
                          f"A live read is an instant, and a quarter is valued at closes.")
        date, price = str(row["as_of"])[:10], float(row["price"])
        said = _settle(row["mark_key"], row["mark_key"], date, ("price", price), on_file_p,
                       lambda r: r.get("struck"))
        if said == "same":
            same += 1
        else:
            if said:
                _supersede(said, "price", price, row["mark_key"])
            new_p.append({"mark_key": row["mark_key"], "date": date, "price": price,
                          "currency": row["currency"], "quality": "sourced", "struck": "close",
                          "status": PH.LIVE, "source": row["source"]})
            # A LINE TWICE IN ONE WRITE: its twin is then "same", and another figure refused.
            on_file_p[(row["mark_key"], date)] = new_p[-1]

    on_file_f = {(r["currency"], r["date"]): r for r in rows_f
                 if r["status"] == FX.LIVE and r["kind"] == "spot"}
    new_f = []
    for row in rates:
        _require(row, ("currency", "rate", "as_of", "source"), f"rate {row.get('currency')!r}")
        what = f"{row['currency']} rate"
        if row["currency"] in held:
            raise Refused(f"{row['currency']} is carried, not refreshed: "
                          f"{held[row['currency']]['why']}")
        if row.get("struck") != "close":
            raise Refused(f"{what}: struck {row.get('struck')!r}, not a session close. A dated "
                          f"rate is that day's close.")
        date, rate = str(row["as_of"])[:10], float(row["rate"])
        said = _settle(what, row["currency"], date, ("rate", rate), on_file_f,
                       lambda r: r.get("struck"))
        if said == "same":
            same += 1
        else:
            if said:
                _supersede(said, "rate", rate, what)
            new_f.append({"currency": row["currency"], "date": date,
                          "rate": rate, "kind": "spot", "quality": "sourced", "struck": "close",
                          "status": FX.LIVE, "source": row["source"]})
            on_file_f[(row["currency"], date)] = new_f[-1]

    if new_p or new_f:
        gone = set(dropped)
        with commit.atomic(*paths()):
            if new_p:
                PH.save([r for r in rows_p if id(r) not in gone] + new_p)
            if new_f:
                FX.save([r for r in rows_f if id(r) not in gone] + new_f)
        D.reload_store()
    return {"day": day, "days": sorted({r["date"] for r in new_p + new_f}),
            "banked": {"prices": len(new_p), "rates": len(new_f)},
            "already": same, "superseded": superseded}
