"""
portfusion report — WHETHER A QUARTER IS READY TO REPORT, and nothing else.

    portfusion report --check 2026-09-30      # READY, or what is missing

The page itself is rendered for the request on the desk's Reports page (`desk/engine.py`'s
`report_page()`); nothing writes it to a file.
"""
import sys

from portfusion.report.gate import completeness
from portfusion.log import log


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        log.info(__doc__)
        return 0
    # --CHECK IS READ WHEREVER IT STANDS. Without it a bare date is answered with the usage.
    dates = [a for a in argv if a != "--check"]
    if "--check" not in argv or len(dates) != 1:
        log.error(__doc__)
        return 2
    date = dates[0]
    gaps = completeness(date)
    if not gaps:
        log.info(f"{date}: READY — every input is on file. The page is on the desk's Reports page.")
        return 0
    log.info(f"{date}: NOT READY")
    for g in gaps:
        log.info(f"  · {g}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
