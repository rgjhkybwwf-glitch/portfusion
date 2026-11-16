"""THE PICTURES A PULL REQUEST MAY RETAKE: the pages its description names on its `Pictures:` line,
and no other. `baselines.yml` walks the desk, retakes every page's picture, then asks this which may
be kept; a page whose picture changed and is not named fails the retake, by name, and nothing is
pushed. The line is the plan's list of the pages the change means to move, copied into the pull
request (CONTRIBUTING.md, Building).

    PR_BODY="$body" python3 tools/pictures.py tools/desk_walk/<page>-linux.png …

Exits 0 when every changed picture is named, 1 when another changed, 2 when the pull request names
no pages or a name that is no page's. The one line it says is the comment the workflow posts, so
nothing of the description but a page's name is repeated in it.

It judges a mistake, not an intent: a branch could edit this file and pass itself.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

from portfusion.log import log

LINE = re.compile(r"^[\s*_]*pictures[\s*_]*:(.*)$", re.IGNORECASE | re.MULTILINE)
PAGE = re.compile(r"[a-z][a-z-]*")
PICTURES = pathlib.Path(__file__).resolve().parent / "desk_walk"


def named(body: str) -> set[str] | None:
    """The pages the description's first `Pictures:` line names; empty for `none`; None when it has
    no such line. A name that is not a page's (words joined by hyphens) is kept, so it is refused
    by name rather than dropped."""
    found = LINE.search(body or "")
    if found is None:
        return None
    words = [w.strip(" `*_.").lower() for w in found.group(1).split(",")]
    return {w for w in words if w and w != "none"}


def page(path: str) -> str:
    """`tools/desk_walk/what-changed-linux.png` → `what-changed`."""
    return pathlib.Path(path).name.removesuffix(".png").removesuffix("-linux")


def judge(pages: set[str], changed: list[str]) -> tuple[list[str], list[str]]:
    """The changed pictures' pages split into those the pull request named and those it did not."""
    moved = sorted({page(p) for p in changed})
    return [p for p in moved if p in pages], [p for p in moved if p not in pages]


def main(changed: list[str]) -> int:
    pages = named(os.environ.get("PR_BODY", ""))
    if pages is None:
        log.info("the pull request names no pages to retake: add a line to its description, "
                 "`Pictures: <page>, <page>` from its plan, or `Pictures: none`, and label it again.")
        return 2
    if any(not PAGE.fullmatch(p) for p in pages):
        log.info("`Pictures:` names something not shaped as a page. Name each page as its picture "
                 "is, `tools/desk_walk/<page>-linux.png`, and label it again.")
        return 2
    unknown = sorted(pages - {page(p.name) for p in PICTURES.glob("*-linux.png")}
                     - {page(p) for p in changed})
    if unknown:
        log.info(f"`Pictures:` names no page the walk draws: {', '.join(unknown)}. Name each page "
                 "as its picture is, `tools/desk_walk/<page>-linux.png`, and label it again.")
        return 2
    kept, other = judge(pages, changed)
    if other:
        log.info(f"pictures changed for pages the pull request does not name: {', '.join(other)}. "
                 "Nothing was pushed. If the change means to move them, add them to its `Pictures:` "
                 "line and label it again; if not, the change moved a page it should not have.")
        return 1
    log.info(", ".join(kept) if kept else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
