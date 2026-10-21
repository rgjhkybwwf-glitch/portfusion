"""REPORTS — every quarterly report, and each year's, from the desk.

The report is its own renderer (`report/`), a page that stands on its own; this panel lists the
quarters it can be shown for and opens each one. It decides nothing: whether a quarter is ready
is `report.gate.completeness()`'s answer, through `engine.reports()`, the same check
`portfusion report --check` makes.

LAST ON THE THREAD, for the reason the registry's docstring gives.

THE YEAR-END REPORT IS NOT BUILT YET. Each year is listed so the place for it exists; the engine
gives a year-to-quarter row already, and a year's contributors, round trips and income would each
need an engine method of their own.
"""
from __future__ import annotations

from portfusion.desk import engine

NAME = "reports"
TITLE = "Reports"
ORDER = 70


def data() -> dict:
    return engine.reports()
