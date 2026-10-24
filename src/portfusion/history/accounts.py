"""
ACCOUNT STATEMENTS — what the broker said an account was worth, and when.

    python3 -m portfusion.history.accounts --show                  every row
    python3 -m portfusion.history.accounts --show "<account>"      one account
    python3 -m portfusion.history.accounts --check                 are the live observations banked?
    python3 -m portfusion.history.accounts --archive               bank them

Run it as `-m`, not as a path: by path, history/ goes on sys.path instead of the project root
and the imports fail before any work starts.

APPEND-ONLY: a new statement adds a row, which is what gives each account a value series at all.
A statement of a day already on file at other figures replaces that row (`restruck()`).

A share row holds positions_value; a spread-bet row holds IG's own figures — funds, running_pl,
equity, deposit — and the statement's Position (net), the notional, under positions_value. NAV per
account is positions_value for a share account and equity for a spread-bet one.

CASH IS NOT HERE AND NEVER IN NAV. A share account's cash is its cash readings
(cash-readings.csv), the record's one place for it; the return counts flows into positions, so
NAV does not. `Book.by_account()` agrees, and tests/test_quarter_nav.py cross-checks the two.
"""
from __future__ import annotations


from portfusion.history import files
from portfusion.history._appendonly import AppendOnlyCSV
from portfusion.record import rules as D
import sys
from collections import defaultdict

from portfusion.log import log

# The file and its columns are `history/files.py`'s, where the demo's generator reads them.
CSV_NAME, FIELDS = files.ACCOUNTS, files.ACCOUNT_FIELDS
NUMERIC = ("positions_value", "funds", "running_pl", "equity", "deposit")
#: The subset this table permits, from `schema.QUALITIES`.
QUALITIES = ("sourced", "derived")

def _is_spread_bet(account: str) -> bool:
    """The register's kind for the account (`accounts.csv`), never its name."""
    return D.ACCOUNT_KIND.get(account) == "spread bet"


# --- the file itself ------------------------------------------------------------------------
# ITS FIGURES ARE ALL OF NUMERIC: a re-reading of one day that moves any figure both rows state
# is a new statement of that day, and `bank()` replaces the earlier one (`restruck()`).
_FILE = AppendOnlyCSV(CSV_NAME, FIELDS, numeric=tuple(NUMERIC), sort_key=lambda r: (r["as_of"], r["account"]),
                      identity=("as_of", "account"), nullable=True, figure=tuple(NUMERIC))

load = _FILE.load
save = _FILE.save
known = _FILE.known

def live_observations() -> list[dict]:
    """The record's CURRENT account observations, in this history's row shape.

    `quality` is DERIVED from the evidence class, never stored beside it. It keys on
    `retrieval` — can anything get the figure back a second time? — not on `official`, which
    asks a different question and would call a broker's own partial ledger unsourced.
    """
    out = []
    for r in D.ac_rows:
        ev = D.EVIDENCE_BY_KEY.get(r.evidence)
        if ev is None or not str(r.reference or "").strip():
            continue                      # unbankable() reports these; see the note there
        out.append({
            "account": r.acct,
            "as_of": r.as_of.isoformat(),
            "positions_value": r.positions,
            "funds": r.funds,
            "running_pl": r.running_pl,
            "equity": r.equity,
            "deposit": r.deposit,
            # THE ACCOUNT TOO, where the class's line carries one: two ii valuations filed on
            # one day are told apart by nothing else (rules.reference_resolves).
            "source": D.evidence_source(r.evidence, reference=r.reference, account=r.acct),
            "quality": "sourced" if ev.retrieval != "none" else "derived",
        })
    return out


def unbankable() -> list[dict]:
    """Observations that CANNOT be filed — no evidence class, or no reference.

    live_observations() must skip a row it cannot describe; this makes the skip loud rather
    than silent, the same as `history/fx.py`'s `unbankable()`.
    """
    return [{"account": r.acct, "as_of": r.as_of.isoformat(), "equity": r.equity,
             "why": (f"evidence {r.evidence!r} is not a class in EVIDENCE_CLASSES"
                     if D.EVIDENCE_BY_KEY.get(r.evidence) is None
                     else "no reference — nothing retrieves this reading a second time")}
            for r in D.ac_rows
            if D.EVIDENCE_BY_KEY.get(r.evidence) is None
            or not str(r.reference or "").strip()]


def archive(verbose: bool = True) -> list[dict]:
    """Append the current observations. Idempotent on (as_of, account) at the SAME figures.

    The outgoing value is banked before a door replaces it, as for prices and rates. A re-reading
    of a day already on file AT OTHER FIGURES replaces that row: until 21 Oct 2026 it found its
    day banked and appended nothing, so the history kept the earlier figures of the day for good.
    """
    new, replaced = _FILE.bank(live_observations())
    if verbose:
        for r in sorted(replaced, key=lambda r: r["account"]):
            log.info(f"    replaced {r['as_of']}  {r['account']:22} — read again the same day")
        if new:
            log.info(f"  archived {len(new)} new observation(s):")
            for m in sorted(new, key=lambda m: (m["as_of"], m["account"])):
                val = m["equity"] if m["equity"] is not None else m["positions_value"]
                log.info(f"    {m['as_of']}  {m['account']:22} {val:>12,.2f}  {m['quality']}")
        else:
            log.info("  nothing to archive — every observation is already on file")
    return new


def check() -> list[dict]:
    """The observations NOT on file — the unbanked, AND the unbankable.

    BOTH, because a caller asks one question: is it safe to replace this reading? It is not,
    whether the outgoing row is merely unarchived or is one that can never be archived.
    """
    return _FILE.unstruck(live_observations()) + unbankable()


def nav_component(row: dict) -> float | None:
    """The account's contribution to NET ASSET VALUE: equity for a spread-bet account,
    positions for a share account — never notional (`rules.SPREAD_BET`)."""
    if _is_spread_bet(row["account"]):
        return row["equity"]
    # POSITIONS ONLY: cash is never in NAV (module docstring).
    return row["positions_value"]


def at(date: str, rows: list[dict] | None = None) -> dict:
    """Every account's latest statement on or before `date`."""
    rows = load() if rows is None else rows
    latest = {}
    for r in rows:
        if r["as_of"] <= date:
            cur = latest.get(r["account"])
            if cur is None or r["as_of"] > cur["as_of"]:
                latest[r["account"]] = r
    return latest


def show(account: str | None = None) -> None:
    """Print the account history, or one account's. Side effects: prints. Reads only."""
    rows = load()
    if not rows:
        log.info("  nothing on file yet")
        return
    by = defaultdict(list)
    for r in rows:
        by[r["account"]].append(r)
    for a in ([account] if account else sorted(by)):
        series = sorted(by.get(a, []), key=lambda r: r["as_of"])
        if not series:
            log.info(f"  {a}: nothing on file")
            continue
        log.info(f"  {a}")
        for r in series:
            nav = nav_component(r)
            bits = [f"positions {r['positions_value']:>12,.2f}" if r["positions_value"] is not None else f"{'positions —':>22}"]
            if r["equity"] is not None:
                bits.append(f"equity {r['equity']:>11,.2f}")
            if r.get("funds") is not None:
                bits.append(f"funds {r['funds']:>10,.2f}")
            flag = "" if r["quality"] == "sourced" else f"  ({r['quality']})"
            log.info(f"     {r['as_of']}  " + "  ".join(bits)
                  + (f"   -> NAV {nav:>12,.2f}" if nav is not None else ""))
            log.info(f"                 {r['source'][:88]}{flag}")
        log.info("")


def main(argv: list[str]) -> int:
    """The command line: --show [account], --check, --archive. Side effects: prints.

    --archive APPENDS to store/account-statements.csv; everything else reports. Repairing the
    record is the bench's job, and REPLACING an observation is desk/doors/observations.py's.
    """
    if "--archive" in argv:
        archive()
    elif "--check" in argv:
        missing = check()
        if missing:
            log.info(f"  ✗ {len(missing)} observation(s) not in the history:")
            for m in missing:
                if m.get("why"):
                    log.info(f"      {m['account']} at {m['as_of']} — {m['why']}")
                else:
                    log.info(f"      {m['account']} at {m['as_of']}")
            if any(not m.get("why") for m in missing):
                log.info("    run: python3 -m portfusion.history.accounts --archive")
            return 1
        log.info("  ✓ every account observation is on file")
    elif "--show" in argv:
        i = argv.index("--show")
        show(argv[i + 1] if len(argv) > i + 1 else None)
    else:
        log.info(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
