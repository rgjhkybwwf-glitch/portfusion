"""`portfusion` — the app's one command, and its seven actions.

    portfusion init       a new book: empty, or a practice book  (init/__main__.py)
    portfusion desk       the desk, in a browser               (desk/__main__.py)
    portfusion check      the guard: the code, and the book opening (check/__main__.py)
    portfusion record     the audit: is the record in good order (record/__main__.py)
    portfusion report     whether a quarter is ready to report  (report/__main__.py)
    portfusion freeze     a quarter end written to the record  (desk/doors/freeze.py)
    portfusion migrate    a book moved to this release's names  (migrate/__main__.py)

    portfusion -q <action>     warnings and errors only
    portfusion -v <action>     and the debug lines too
    portfusion --version       which release this is

Every command reads the book in the folder it is typed in. To read another:

    portfusion <action> --book <folder>     the action on that book's folder, for this run: the
                                            same as PORTFUSION_BOOK, a path from where you are;
                                            `demo` is the demo book the app ships

Each action is its module's own command line, reached by name: `python3 -m portfusion.desk`
is the same thing, `--book` and all. The other commands are reached that way alone:

    python3 -m portfusion.feeds.refresh               the price sweep, printed: Price Refresh's
    python3 -m portfusion.feeds.ig                    IG: find an epic, check levels, sweep events
    python3 -m portfusion.feeds.tv                    TradingView: sign in, find a symbol
    python3 -m portfusion.history.prices              the price history: show, check, bank
    python3 -m portfusion.history.fx                  the FX history: show, check, bank
    python3 -m portfusion.history.accounts            the account history: show, check, bank
    python3 -m portfusion.desk.intake.read_document   a document on the workbench, as text
    python3 -m portfusion.desk.intake.propose         a Claude session's reading of one, checked
"""
import importlib
import logging
import sys

import portfusion
from portfusion.log import log, setup

#: The actions, each a module's `main(argv)`.
ACTIONS = {"init": "portfusion.init.__main__", "desk": "portfusion.desk.__main__",
           "check": "portfusion.check.__main__", "record": "portfusion.record.__main__",
           "report": "portfusion.report.__main__", "freeze": "portfusion.desk.doors.freeze",
           "migrate": "portfusion.migrate.__main__"}


#: How much an action says, set before it starts (`log.py`).
LEVELS = {"-q": logging.WARNING, "--quiet": logging.WARNING,
          "-v": logging.DEBUG, "--verbose": logging.DEBUG}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    argv, folder = portfusion.book(list(argv))
    if folder is not None and not portfusion.name_book(folder):
        return 2
    while argv and argv[0] in LEVELS:
        setup(LEVELS[argv[0]])
        argv = argv[1:]
    if argv and argv[0] == "--version":
        from portfusion import about
        log.info(about.release())
        return 0
    if not argv or argv[0] in ("-h", "--help"):
        log.info(__doc__)
        return 0
    action, rest = argv[0], argv[1:]
    if action not in ACTIONS:
        log.error(f"no action {action!r}. {__doc__}")
        return 2
    return importlib.import_module(ACTIONS[action]).main(rest)


if __name__ == "__main__":
    sys.exit(main())
