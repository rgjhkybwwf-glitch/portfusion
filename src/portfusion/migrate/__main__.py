"""
portfusion migrate — A BOOK CARRIED TO THIS RELEASE'S STORE, by the moves `record/migrations.py`
declares: tables and columns renamed, a column split by its line, and the names the journal and
the Bench's items carry.

    portfusion migrate            what would move, every row a figure moves in; nothing written
    portfusion migrate --write    move it, then open the book and audit it; put back if either fails

It never touches git: the move is committed as the book's own change. The book's `checks/` are its
code, and the lines that name an old table or column are listed to move by hand.
"""
import argparse
import sys

from portfusion.log import log


def main(argv=None):
    p = argparse.ArgumentParser(prog="portfusion migrate", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--write", action="store_true", help="move the book, then open and audit it")
    args = p.parse_args(argv)
    from portfusion.record import migrations as M, schema
    book = schema.BOOK
    try:
        m, changes = M.plan(book)
    except (ValueError, OSError) as e:
        log.error(f"migrate: {e}. Nothing was written.")
        return 1
    if m is None:
        log.info(f"{book}: already in this release's shape. Nothing to move.")
        return 0
    log.info(f"{book}\n{m.issue}")
    for c in changes:
        for line in c.said:
            log.info(f"  {line}")
    by_hand = M.named_in_checks(book)
    if by_hand:
        log.info("checks/ lines that may name an old table or column — the book's code, to move by hand:")
        for line in by_hand:
            log.info(f"  {line}")
    if not args.write:
        log.info("Nothing written. --write moves it, then opens and audits the book.")
        return 0
    if book == schema.DEMO:
        log.error("migrate: the demo ships with the app and is moved by tools/make_demo.py.")
        return 2
    before = M.write(changes)
    from portfusion.check import migrated
    try:
        failed = migrated(str(book))
    except BaseException:                    # Ctrl-C in the guard leaves no half-moved book
        M.put_back(before)
        raise
    if failed:
        M.put_back(before)
        log.error("migrate: the moved book did not open or audit, so every file is put back.")
        return 1
    log.info(f"Moved: {len(changes)} file(s). Commit it as the book's own change"
             + (", with checks/ moved." if by_hand else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
