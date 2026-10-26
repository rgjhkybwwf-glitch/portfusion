"""
portfusion init — A NEW BOOK, in a folder that is empty or does not exist yet.

    portfusion init <folder>                 an empty book; its record begins this 1 January
    portfusion init <folder> --begins 2027   an empty book whose record begins on 1 January 2027
    portfusion init <folder> --begins 2027-05-15
                                             an empty book whose record begins on 15 May 2027
    portfusion init <folder> --practice      a practice book: a copy of the demo, marked as one,
                                             to try the desk on. Its figures are invented
    portfusion init <folder> --no-git        without starting its git history
    portfusion init <folder> --no-venv       without making its venv
    portfusion init <folder> --push-on-commit
                                             with a hook that pushes each commit to origin
                                             as it lands, once you add one

Each has its own venv, `.venv`, running the portfusion that made it, and is a git repository from
its first commit, unless --no-git: kept on this machine, and pushed anywhere only if you add a
remote — a private one.

Then work in it: every command typed in the book's folder reads that book.
"""
import argparse
import os
import sys

from portfusion.log import log


def _begins(value: str) -> int | str:
    """A year, or a day as YYYY-MM-DD: anything else is refused as the command line's own error."""
    import datetime as _dt
    if value.isdigit():
        return int(value)
    try:
        return _dt.date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is neither a year nor a day (YYYY-MM-DD)")


def main(argv=None):
    # IT READS NO BOOK, and the record refuses to load in a folder that holds none: the demo
    # stands in while the new one is written.
    os.environ.setdefault("PORTFUSION_BOOK", "demo")
    from portfusion.init import Refused, create, make_venv, start_history
    p = argparse.ArgumentParser(prog="portfusion init", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder")
    kind = p.add_mutually_exclusive_group()
    kind.add_argument("--practice", action="store_true",
                      help="a practice book: a copy of the demo, marked as one")
    kind.add_argument("--begins", type=_begins, metavar="YEAR|DATE",
                      help="the year, or the day (YYYY-MM-DD), the record begins")
    p.add_argument("--no-git", action="store_true", help="do not start its git history")
    p.add_argument("--no-venv", action="store_true", help="do not make its venv")
    p.add_argument("--push-on-commit", action="store_true",
                   help="a hook that pushes each commit to origin as it lands")
    args = p.parse_args(argv)
    try:
        folder = create(args.folder, practice=args.practice, begins=args.begins,
                        push_on_commit=args.push_on_commit)
    except Refused as e:
        log.error(str(e))
        return 2
    log.info(f"a new {'practice' if args.practice else 'empty'} book at {folder}")
    made = "" if args.no_venv else make_venv(folder)
    if made:
        log.info(f"  {made}")
    elif not args.no_venv:
        log.error("  its venv could not be made. In the book's folder:\n"
                  "    python3 -m venv .venv && .venv/bin/python3 -m pip install -r requirements.txt")
    if not args.no_git:
        log.info(f"  {start_history(folder)}")
    log.info(f"  cd {folder}{' && source .venv/bin/activate' if made else ''}    every command "
             f"typed there reads it")
    return 0 if made or args.no_venv else 1


if __name__ == "__main__":
    sys.exit(main())
