"""A PULL REQUEST'S RISK TIER, BY THE PATHS IT CHANGES: the tiers CONTRIBUTING.md's Merging names,
and here the paths each holds, and whether `tiers.yml` holds the pull request for the maintainer's
yes. It reads only the standard library and `portfusion.log`, so the workflow runs the base's copy
of it, never the branch's, without installing anything.

    python3 tools/tiers.py <changed path> …       says the tier, then the path that set it
    python3 tools/tiers.py --hold <comments file>  what to do with auto-merge, from the environment
                                                   TIER, WHY, MOVED, AUTO_ON, HEAD and OWNER

A pull request takes the highest tier of its paths; one that changes nothing is tier 0. The
stability rules' tests are read from CONTRIBUTING.md's tables, where each rule names what holds it.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from portfusion.log import log

ROOT = Path(__file__).resolve().parents[1]
PKG = "src/portfusion/"

WORDS = ("docs/", "README.md", "CHANGELOG.md")
ENGINE = tuple(PKG + p for p in ("engine/", "house/", "record/rules", "feeds/", "history/",
                                 "demo/")) + ("tools/make_demo.py",)
OWN = (".github/", ".githooks/", ".claude/", PKG + "hooks/", "pyproject.toml", "requirements.lock",
       "tools/clean_room.py", "tools/package.json", "tools/package-lock.json", "tools/tiers.py",
       "tools/figures.py", "tools/pictures.py", "CONTRIBUTING.md", PKG + "__init__.py",
       PKG + "record/schema.py", PKG + "record/migrations.py", PKG + "migrate/",
       PKG + "tests/pytest.ini", PKG + "tests/test_tiers.py", PKG + "tests/test_pictures.py")


def stability_tests(contributing: str) -> set[str]:
    """The file names of the tests that hold a stability rule: each `test_*.py` or `harness.py`
    named in the tables under "The stability rules", up to the next section."""
    section = contributing.partition("## The stability rules")[2].partition("\n## ")[0]
    return set(re.findall(r"`((?:test_\w+|harness)\.py)(?:::\w+)?`", section))


def tier(path: str, held: set[str]) -> int:
    if path.startswith(OWN) or (path.startswith(PKG + "tests/") and Path(path).name in held):
        return 3
    if path.startswith(ENGINE):
        return 2
    if path.startswith(WORDS):
        return 0
    return 1


def sort(paths: list[str], held: set[str]) -> tuple[int, str | None]:
    """The pull request's tier and the first path that set it; None when nothing changed."""
    tiers = sorted(((tier(p, held), p) for p in paths), key=lambda t: -t[0])
    return tiers[0] if tiers else (0, None)


def hold(tier: int, why: str, moved: str, auto_on: bool, said: str, head: str,
         owner: str) -> tuple[str, str]:
    """What `tiers.yml` does with auto-merge, and the comment it posts: ("off", text) turns it off,
    ("say", text) says once that the pull request does not merge itself, ("none", why) does
    nothing. Tier 3, and tier 2 with a figure moved, are held. Auto-merge found on is turned off
    ONCE A COMMIT, marked in the bot's comments `said`: turned on again on that commit, it is the
    maintainer's yes, and stands. A new commit is asked again."""
    if tier == 3:
        reason = f"it is tier 3, the store or the guard's own (`{why}`): it waits for the maintainer's yes."
    elif tier == 2 and moved.strip():
        lines = "\n".join(f"- {m}" for m in moved.replace("<!--", "").strip().splitlines())
        reason = f"it moves the demo's headline figures, so it waits for the maintainer's yes:\n\n{lines}"
    else:
        return "none", f"tier {tier}: nothing to hold"
    off, told = f"<!-- tiers:off:{head} -->", f"<!-- tiers:said:{head} -->"
    if off in said:
        return "none", f"auto-merge was turned off once on {head}: turned on again, it is the yes"
    if auto_on:
        return "off", (f"🤖 **PortFusion agent** · @{owner}, auto-merge is turned off: {reason}\n\n"
                       f"Pressing Enable auto-merge again on this commit is the yes; a new commit, "
                       f"a merge of `main` included, is asked again.\n{off}")
    if told in said:
        return "none", f"already said on {head}"
    return "say", f"🤖 **PortFusion agent** · this does not merge itself: {reason}\n{told}"


def main(args: list[str]) -> int:
    if args[:1] == ["--hold"]:
        e = os.environ
        action, text = hold(int(e["TIER"]), e.get("WHY", ""), e.get("MOVED", ""),
                            e.get("AUTO_ON") == "true", Path(args[1]).read_text(encoding="utf-8"),
                            e["HEAD"], e["OWNER"])
        log.info(action)
        log.info(text)
        return 0
    held = stability_tests((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))
    n, why = sort(args, held)
    log.info(str(n))
    log.info(why or "no file changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
