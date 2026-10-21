"""
portfusion check — THE GUARD: the code on the demo the app carries, then the loaded book
opening, with its own checks/. Green unless the code broke or the book will not open. Whatever
follows is passed to pytest, on both runs.

    portfusion check                    the code, then the book
    portfusion check -q -k ledger       pytest's own options, as given

Whether the RECORD is in good order is `portfusion record`.
"""
import sys

from portfusion.check import check
from portfusion.log import log


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] in (["-h"], ["--help"]):
        log.info(__doc__)
        return 0
    return check(argv)


if __name__ == "__main__":
    sys.exit(main())
