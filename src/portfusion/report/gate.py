"""THE COMPLETENESS GATE, and the point of the package.

A report from a half-arrived quarter looks finished and is wrong, so the page is not rendered
until every input it reads exists at the quarter-end date, and the gate says exactly what is
missing. The desk's Reports page and `portfusion report --check` both ask it.
"""
from __future__ import annotations

from portfusion.record import rules as D


def completeness(quarter_end: str) -> list[str]:
    """What is still missing before this quarter can be reported. Empty means ready.

    IT CHECKS WHAT THE PAGE READS (14 Oct 2026): every account's quarter-nav row at the
    date and at the quarter's opening, the previous quarter end its return runs from, and the
    composition frozen at the date. Both are checked against the DATE ITSELF, not "on or
    before": a figure from six weeks earlier does not describe the quarter that just closed. THE
    MARKS ARE NOT ASKED FOR: the page reads none, and the freeze that froze the quarter checked
    them, which is where a missing one is named (`desk/doors/freeze.py`). THE BROKER CHECKS DO
    NOT GATE IT EITHER: they confirm the figures rather than make them, and section 9 prints each
    account's last check, or that there is none.
    """
    missing = []
    accounts = set(D.ACCOUNT_ORDER)

    opening = _opening(quarter_end)
    if opening is None:
        return [f"{quarter_end} is not a quarter end"]
    for day, what in ((quarter_end, "NAV row"), (opening, "opening NAV row")):
        nav = {q.account for q in D.QUARTER_NAV if q.as_of == day}
        if nav != accounts:
            missing.append(f"quarter-nav: no {what} at {day} for "
                           f"{', '.join(sorted(accounts - nav))}")
    if quarter_end not in D.QSNAP_FROZEN:
        missing.append(f"quarter-snapshots: no frozen composition at {quarter_end}. A quarter end "
                       f"is frozen by the freeze door: python3 -m portfusion.desk.doors.freeze {quarter_end}")
    return missing


def _opening(quarter_end: str) -> str | None:
    """The quarter end before `quarter_end`, which its quarter opens from; None for a date that is
    not a quarter end."""
    year = int(quarter_end[:4])
    return {"03-31": f"{year - 1}-12-31", "06-30": f"{year}-03-31", "09-30": f"{year}-06-30",
            "12-31": f"{year}-09-30"}.get(quarter_end[5:])
