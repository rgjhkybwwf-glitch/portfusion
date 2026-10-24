"""
portfusion init — A NEW BOOK, in a folder that is empty or does not exist yet.

    portfusion init <folder>                 an empty book; its record begins this 1 January
    portfusion init <folder> --begins 2027   an empty book whose record begins on 1 January 2027
    portfusion init <folder> --practice      a practice book: a copy of the demo, marked as one,
                                             to try the desk on. Its figures are invented
    portfusion init <folder> --no-git        without starting its git history
    portfusion init <folder> --push-on-commit
                                             with a hook that pushes each commit to origin
                                             as it lands, once you add one

Each is a git repository from its first commit, unless --no-git: kept on this machine, and
pushed anywhere only if you add a remote — a private one.

Then work in it: every command typed in the book's folder reads that book.
"""
import argparse
import os
import sys

from portfusion.log import log


def main(argv=None):
    # IT READS NO BOOK, and the record refuses to load in a folder that holds none: the demo
    # stands in while the new one is written.
    os.environ.setdefault("PORTFUSION_BOOK", "demo")
    from portfusion.init import Refused, create, start_history
    p = argparse.ArgumentParser(prog="portfusion init", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder")
    kind = p.add_mutually_exclusive_group()
    kind.add_argument("--practice", action="store_true",
                      help="a practice book: a copy of the demo, marked as one")
    kind.add_argument("--begins", type=int, metavar="YEAR", help="the year the record begins")
    p.add_argument("--no-git", action="store_true", help="do not start its git history")
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
    if not args.no_git:
        log.info(f"  {start_history(folder)}")
    log.info(f"  cd {folder}    every command typed there reads it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
