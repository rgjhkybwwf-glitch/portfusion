"""`portfusion` — the app's one command, and its five actions.

    portfusion init       a new book: empty, or a practice book  (init/__main__.py)
    portfusion desk       the desk, in a browser               (desk/__main__.py)
    portfusion check      the guard: the code, and the book opening (check/__main__.py)
    portfusion record     the audit: is the record in good order (record/__main__.py)
    portfusion report     whether a quarter is ready to report  (report/__main__.py)

    portfusion -q <action>     warnings and errors only
    portfusion -v <action>     and the debug lines too
    portfusion --version       which release this is

Every action reads the book in the folder it is typed in. To read another:

    portfusion <action> --book <folder>     the action on that book's folder, for this run: the
                                            same as PORTFUSION_BOOK, a path from where you are;
                                            `demo` is the demo book the app ships

Each action is its package's own command line, reached by name: `python3 -m portfusion.desk`
is the same thing.
"""
import importlib
import logging
import os
import pathlib
import sys

from portfusion.log import log, setup

#: The five actions, each its package's `__main__.main(argv)`.
ACTIONS = ("init", "desk", "check", "record", "report")


#: How much an action says, set before it starts (`log.py`).
LEVELS = {"-q": logging.WARNING, "--quiet": logging.WARNING,
          "-v": logging.DEBUG, "--verbose": logging.DEBUG}


def book(argv: list[str]) -> tuple[list[str], str | None]:
    """`--book <folder>` or `--book=<folder>`, wherever it sits, taken out of the arguments.

    ONE FLAG FOR EVERY ACTION, read here and not by each action, because the book is chosen when
    `record/schema.py` is first imported, before any action parses its arguments. It sets
    `PORTFUSION_BOOK` for this process and whatever it starts — a desk's restart included — resolved
    from where the command was typed, as a path on a command line is."""
    out, folder = [], None
    it = iter(argv)
    for arg in it:
        if arg == "--book":
            folder = next(it, "")
        elif arg.startswith("--book="):
            folder = arg.split("=", 1)[1]
        else:
            out.append(arg)
    return out, folder


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    argv, folder = book(list(argv))
    if folder == "demo":                  # the demo the app ships (record/schema.py:DEMO)
        os.environ["PORTFUSION_BOOK"] = folder
    elif folder is not None:
        path = pathlib.Path(folder).expanduser().resolve()
        if not (path / "store").is_dir():
            log.error(f"no book at {path}: a book's folder holds its store/")
            return 2
        os.environ["PORTFUSION_BOOK"] = str(path)
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
    return importlib.import_module(f"portfusion.{action}.__main__").main(rest)


if __name__ == "__main__":
    sys.exit(main())
