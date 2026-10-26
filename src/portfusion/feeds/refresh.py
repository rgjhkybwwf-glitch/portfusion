"""
THE PRICE SWEEP — every mark the book is valued at, in ONE PASS, as data. The desk's Price Refresh
fills its form from `sweep()`, and the terminal prints the same thing.

    python3 -m portfusion.feeds.refresh               bank the current marks, then print the sweep
    python3 -m portfusion.feeds.refresh --on D        bank, then print one past day's closes (a quarter end)
    python3 -m portfusion.feeds.refresh --bank        bank only
    python3 -m portfusion.feeds.refresh --check       are both histories current? changes nothing

ONE PASS, FOUR PARTS, each reporting its own failure, so one vendor being down costs the others
nothing:

    ig_levels   every IG contract's level (`feeds/ig.py`), and straight after it
    ig_equity   each IG account's equity. THE TWO ARE ONE OBSERVATION: the book derives a
                spread-bet account's equity from the levels and reconciles it against the
                broker's, so read apart they describe different markets (`Book.comparability`).
    tv          TradingView's shares and FX rates, each line struck at its own instant
    watchlist   the Live, Exit and Entry lists against the book: reported, never acted on

A PAST DAY (`on`) IS CLOSES ONLY: TradingView's day bars, IG's close bars, and for a contract IG
does not quote through the evening, the level on that day's filed statement. The caller reads the
statement, because the reader lives in the desk and this module may not import it
(the import contracts in `pyproject.toml`). A past day has no equity: a reading is an instant.

IT WRITES THE HISTORIES ONLY: the command banks the marks on file to the price and FX histories,
and never writes `store/`. The desk's Price Refresh is the door: it banks the outgoing marks,
writes the ticked lines and banks those, in one operation. Nothing printed here is for pasting
into `store/`.
"""

import datetime as _dt
import sys

from portfusion.log import log


def _part(fn) -> dict:
    """One part of the sweep: its answer, or its failure in the vendor's own words."""
    try:
        return {"ok": True, **fn()}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"no credentials: {e}"}
    except Exception as e:                          # noqa: BLE001 — the vendor, named
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _reading(row: dict, read_at: str, at: str) -> dict:
    """An account's equity as `desk/doors/observations.py` takes it. `ig-accounts` is retrieved again
    as a `reading`: the endpoint answers a second time, with a different figure, because the value
    is an instant."""
    return {"account": row["account"], "as_of": read_at[:10], "at": at,
            "funds": row["funds"], "running_pl": row["running_pl"], "equity": row["equity"],
            "deposit": row["deposit"], "available": row["available"],
            "evidence": "ig-accounts", "reference": f"{row['account_id']}, read {read_at}"}


def _ig_now() -> tuple[dict, dict]:
    """The levels, then the equity, back to back, and the seconds between them: a reading whose
    halves are a minute apart is a worse reading and should say so. The equity is read even when
    the levels fail, since a balance is worth having when a market is untradeable."""
    try:
        from portfusion.feeds import ig
    except Exception as e:                          # noqa: BLE001
        failed = {"ok": False, "error": f"feeds/ig.py could not be imported: {e}"}
        return failed, {**failed, "gap_seconds": None}
    levels = _part(ig.contract_levels)
    landed = _dt.datetime.now()
    equity = _part(ig.account_state)
    done = _dt.datetime.now()
    if equity["ok"]:
        equity["read_at"] = f"{done:%Y-%m-%d at %H:%M}"
        at = done.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        equity["readings"] = [_reading(r, equity["read_at"], at) for r in equity["rows"]]
    equity["gap_seconds"] = round((done - landed).total_seconds(), 1)
    return levels, equity


def _ig_closes(on: str, filed=None) -> dict:
    """IG's half for ONE PAST DAY: each contract's close bar (`ig.contract_closes()`), and for a
    contract the bar left unpriced, the level `filed(on)` read off that day's filed statement. A
    statement that cannot be read costs the bar closes nothing."""
    try:
        from portfusion.feeds import ig
    except Exception as e:                          # noqa: BLE001
        return {"ok": False, "error": f"feeds/ig.py could not be imported: {e}"}
    r = _part(lambda: ig.contract_closes(on))
    if not r["ok"] or filed is None:
        return r
    try:
        got = filed(on)
    except Exception as e:                          # noqa: BLE001 — reported, never swallowed
        got = {"rows": {}, "read": None, "problems": [f"the filed IG statements: {e}"]}
    rows = []
    for row in r["rows"]:
        if not row["priced"] and row["contract"] in got["rows"]:
            row = {**row, **got["rows"][row["contract"]]}
        elif not row["priced"] and got["read"] is not None:
            row = {**row, "status": row["status"] + (
                f"; not on the IG statements filed for {on}" if got["read"]
                else f"; none is filed for {on} yet")}
        rows.append(row)
    return {**r, "rows": rows, "statements": got["read"] or [], "problems": got["problems"]}


def sweep(on: str | None = None, filed=None) -> dict:
    """ONE PASS, as the module docstring sets out. Prints nothing; writes nothing.

    `filed(on)` reads the far contracts' levels off that day's filed IG statements; the desk
    passes `desk/intake/statement_closes.closes`. Without it they stay unpriced, each saying where its
    level is printed.
    """
    out = {"on": on}
    if on:
        out["ig_levels"] = _ig_closes(on, filed)
    else:
        out["ig_levels"], out["ig_equity"] = _ig_now()
    try:
        from portfusion.feeds import tv
        conn = tv.connect()
    except Exception as e:                          # noqa: BLE001 — the vendor, named
        failed = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        out["tv"] = failed
        if not on:
            out["watchlist"] = failed
        return out
    out["tv"] = _part(lambda: tv.closes(on, conn=conn) if on else tv.sweep(conn=conn))
    if not on:
        out["watchlist"] = _part(lambda: tv.watchlist(conn))
    return out


# =================================================================================================
# THE TERMINAL
# =================================================================================================
def _rule(text):
    log.info("")
    log.info("-" * 86)
    log.info(f"  {text}")
    log.info("-" * 86)
    sys.stdout.flush()


def _print(r: dict) -> None:
    ig = r["ig_levels"]
    _rule(f"IG contract closes of {r['on']}" if r["on"] else "IG contract levels")
    if not ig["ok"]:
        log.info(f"  {ig['error']}")
    for row in ig.get("rows", []):
        figure = f"{row['level']:>12}" if row["priced"] else f"{'—':>12}"
        log.info(f"  {row['contract']:<14}{figure}  {row['source'] if row['priced'] else row['status']}")
    for p in ig.get("problems", []):
        log.info(f"  ! {p}")

    if "ig_equity" in r:
        eq = r["ig_equity"]
        _rule("IG account equity" + (f", read {eq['gap_seconds']}s after the levels"
                                     if eq["gap_seconds"] is not None else ""))
        if not eq["ok"]:
            log.info(f"  {eq['error']}")
        for row in eq.get("rows", []):
            log.info(f"  {row['account']:<24} funds {row['funds']:>12,.2f}   P/L "
                  f"{row['running_pl']:>10,.2f}   equity {row['equity']:>12,.2f}")
        for refusal in eq.get("refusals", []):
            log.info(f"  REFUSED {refusal['text']}")

    tv = r["tv"]
    _rule(f"TradingView closes of {r['on']}" if r["on"] else
          "TradingView shares and rates, each at its own instant")
    if not tv["ok"]:
        log.info(f"  {tv['error']}")
    for row in tv.get("prices", []):
        log.info(f"  {row['mark_key']:<14}{row['price']:>12} {row['currency']}  {row['struck']:<5}  "
              f"{row['source']}")
    for row in tv.get("rates", []):
        # A RATE ROW NAMES ITS CURRENCY: both producers drop `key`.
        log.info(f"  {row['currency']:<14}{row['rate']:>12}      {row['struck']:<5}  {row['source']}")
    for f in tv.get("failed", []):
        log.info(f"  NOT PRICED {f['key']}: {f['why']}")

    if "watchlist" in r:
        wl = r["watchlist"]
        _rule("The flag lists against the book")
        if wl["ok"]:
            from portfusion.feeds import tv as TV
            TV.print_watchlist(wl)
        else:
            log.info(f"  {wl['error']}")


def check():
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH
    missing_p, missing_f = PH.check(), FX.check()
    for name, missing in (("prices", missing_p), ("FX rates", missing_f)):
        if missing:
            log.info(f"  ✗ {len(missing)} live {name} not archived")
        else:
            log.info(f"  ✓ every live {name[:-1] if name.endswith('s') else name} is on file")
    return 1 if (missing_p or missing_f) else 0


def bank():
    """Archive only: the marks on file become history the next write preserves."""
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH
    new_p, new_f = PH.archive(), FX.archive()
    log.info(f"\n  banked {len(new_p)} price mark(s), {len(new_f)} FX rate(s)")
    return 0


KNOWN_FLAGS = {"--on", "--bank", "--check", "--help", "-h"}


def main(argv):
    # --help must never fall through into a live sweep, and an unrecognised flag stops too.
    on = argv[argv.index("--on") + 1] if "--on" in argv[:-1] else None
    unknown = [a for a in argv if a not in KNOWN_FLAGS and a != on]
    try:
        _dt.date.fromisoformat(on) if on else None
    except ValueError:
        unknown.append(f"--on {on}")
    if "--on" in argv and on is None:
        unknown.append("--on needs a date")
    if unknown or "--help" in argv or "-h" in argv:
        log.info(__doc__)
        if unknown:
            log.info(f"  unrecognised: {' '.join(unknown)}\n")
            return 2
        return 0
    if "--check" in argv:
        return check()
    if "--bank" in argv:
        _rule("BANKING the current marks")
        return bank()

    # ---- 1: BANK FIRST. Nothing else runs if this does not. ----------------------------
    _rule("STEP 1 of 3 — banking the current marks")
    from portfusion.history import fx as FX
    from portfusion.history import prices as PH
    try:
        new_p = PH.archive()
        new_f = FX.archive()
    except Exception as exc:                       # noqa: BLE001 — refuse loudly, fetch nothing
        log.info(f"\n  ARCHIVE FAILED: {exc}")
        log.info("  Sweep NOT started. Fix the archive first.")
        return 2
    log.info(f"\n  archived: {len(new_p)} price mark(s), {len(new_f)} FX rate(s)")

    # ---- 2: the sweep ----------------------------------------------------------------
    _rule(f"STEP 2 of 3 — the closes of {on}" if on else
          "STEP 2 of 3 — the sweep: IG levels and equity, TradingView, the flag lists")
    _print(sweep(on))

    # ---- 3: what the human does next -------------------------------------------------
    _rule("STEP 3 of 3 — over to you")
    log.info("""
  Nothing above is written. Take the lines in the desk's Price Refresh (portfusion desk), which
  banks the outgoing marks, writes the ticked ones and banks those in one operation.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
