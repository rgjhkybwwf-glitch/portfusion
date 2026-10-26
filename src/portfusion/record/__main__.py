"""`portfusion record` — THE AUDIT: is the record in good order?

Two halves, in this order. First the FINDINGS — `Book.findings()`, read from the record: the book
against the brokers' statements, price age, conversions, the evidence chain, the journal, any
reasoning owed — with the headline figures, the backup and a quarter left to close. Then the tests
marked `audit`, the same set as `python3 -m pytest -m audit`, outside the default run
(`docs/testing.md`). A finding here is a thing the record needs, not a code defect.

Exits non-zero on a PROBLEM or a failed audit test. A gap is work owed and does not fail it.
"""
import datetime as _dt
import sys

from portfusion.log import log

RULE = "=" * 66


def close_reminder(today: _dt.date | None = None) -> str | None:
    """The quarter-close procedure, when a quarter has ended and has not been frozen; else None.

    Closing a quarter happens once every three months — the interval at which a procedure stops
    being remembered. The book knows the date and whether the quarter is frozen, so it says so.
    """
    from portfusion.engine import Book
    from portfusion.record import rules as D
    today = today or _dt.date.today()
    end = Book.quarter_to_close().date()            # the same quarter the Dashboard names
    if end > today:
        return None
    w = _dt.timedelta(days=D.CLOSE_CHECK_WINDOW_DAYS)
    return f"""{RULE}
  QUARTER-END: {end:%-d %b %Y} has not been frozen yet.
{RULE}
  Each line is valued at its mark nearest {end:%-d %b}, taken from
  {end - w:%-d %b} to {end + w:%-d %b %Y}.

  1. EVENTS. The freeze takes the quantities held on {end:%-d %b}, once, so every
     event to that day goes in first: each contract note through the drop-off, then
     "Sweep IG events" on the Bench.
  2. PRICES. Any Price Refresh in that window. For that day's closes instead:
     Price Refresh → "closes of" {end} → fetch everything →
     tick → write.
  3. FREEZE. The first lists every line and the mark it takes; the second writes:
       portfusion freeze {end}
       portfusion freeze {end} --write
  4. REPORT. The page is on the desk's Reports page once the gate says READY; each
     account's last broker check prints beside it, and none is waited for:
       portfusion report --check {end}
  Then commit the four store files the freeze wrote."""


def _figure(value, unit: str) -> str:
    if value is None or value != value:
        return "blank"                              # the year's opening is not frozen yet
    if unit == "gbp":
        return f"£{value:,.2f}"
    if unit == "pct":
        from portfusion.house.precision import pct
        return pct(value)
    return f"{value:,.0f}"


def findings() -> int:
    """Print the findings. Returns how many PROBLEMS there are. COMPUTES NOTHING: every line is
    the engine's or about.py's, so this and the desk's Dashboard cannot disagree."""
    from portfusion import about
    from portfusion.engine import Book
    b = Book()
    f = b.findings()
    log.info(f"  python: {about.interpreter()['line']}")
    log.info(f"  book:   {about.book_line()}")
    log.info("-" * 66)
    head = b.headline()
    w = max(len(k) for k in head)
    for label, value in head.items():
        log.info(f"  {label:<{w}}  {_figure(value, Book.HEADLINE[label]['unit'])}")  # pyright: ignore[reportIndexIssue]
    log.info(f"  {'Prices':<{w}}  {f['prices'][0]}")
    log.info(f"  {'Price age':<{w}}  {f['prices'][1]}")
    log.info("-" * 66)
    for n in f["notes"] + [about.backup_state()]:
        log.info(f"  {n}")
    for g in f["gaps"]:
        log.info(f"  ○ {g}")
    for p in f["problems"]:
        log.info(f"  ✗ {p}")
    reminder = close_reminder()
    if reminder:
        log.info(reminder)
    return len(f["problems"])


def main(argv=None):
    import argparse
    argparse.ArgumentParser(prog="portfusion record",
                            description="THE AUDIT: is the record in good order? The findings, "
                                        "then the tests marked audit.",
                            epilog="It takes nothing: it audits the book PORTFUSION_BOOK names.").parse_args(argv)
    log.info(RULE)
    from portfusion import brand
    log.info(" · ".join(["PORTFUSION", "record audit",
                         *([brand.NAME] if brand.NAME != brand.APP else [])]))
    log.info("  Is the RECORD in good order? For the code, run portfusion check.")
    log.info(RULE)
    problems = findings()
    log.info(RULE)                         # AHEAD of the subprocess, or it lands under it
    from portfusion.check import run              # the suite the app ships, with the book's checks
    code = run(["-m", "audit", "-q", "--no-header", "--tb=line"])
    log.info("-" * 66)
    if problems:
        log.info(f"  {problems} PROBLEM(S) in the findings above")
    log.info("  the record is in good order" if code == 0 and not problems else
          "  FINDINGS ABOVE — each is a thing the record needs, not a code defect")
    log.info(RULE)
    return code or (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main())
