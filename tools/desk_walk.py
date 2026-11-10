"""THE DEMO DESK, SERVED FOR `desk_walk.spec.mjs`: a copy of the demo's tracked files as the book,
and the clock held at `DAY`, so a page drawn tomorrow is the page drawn today. Playwright starts
and stops it (`playwright.config.mjs`).

    npm ci --prefix tools && npm --prefix tools run browser      # once: Playwright, its Chromium
    npm --prefix tools run walk
"""
from __future__ import annotations

import datetime
import importlib
import os
import pathlib
import pkgutil
import shutil
import subprocess
import sys
import tempfile
import types

HERE = pathlib.Path(__file__).resolve().parent.parent     # the checkout; this file is in tools/
DEMO = "src/portfusion/demo"
#: The day every page is drawn on, `playwright.config.mjs`'s: the demo's rows are dated, and an
#: age or a day count moves.
DAY = datetime.datetime.fromisoformat(sys.argv[2])


def copy_demo(into: pathlib.Path) -> None:
    """The demo as git tracks it, each file last changed on `DAY`: a workbench left in the
    checkout's `_inbox/` stays behind, and so does the hour the checkout was made."""
    listed = subprocess.run(["git", "ls-files", "-z", DEMO], cwd=HERE, capture_output=True,
                            text=True, check=True).stdout.split("\0")
    for path in filter(None, listed):
        to = into / pathlib.Path(path).relative_to(DEMO)
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / path, to)
        os.utime(to, (DAY.timestamp(), DAY.timestamp()))


def hold_the_clock() -> None:
    """Every `today` and `now` the app reads answers `DAY`: pandas', and each module's `_dt`,
    every module imported first, since one that loads at its first request would keep the real."""
    import pandas as pd

    import portfusion
    for m in pkgutil.walk_packages(portfusion.__path__, "portfusion."):
        if ".tests" not in m.name and not m.name.endswith("__main__"):
            importlib.import_module(m.name)

    class Date(datetime.date):
        @classmethod
        def today(cls):
            return DAY.date()

    class DateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return DAY.replace(tzinfo=tz)
    held = types.SimpleNamespace(**{**vars(datetime), "date": Date, "datetime": DateTime})
    pd.Timestamp.today = pd.Timestamp.now = classmethod(lambda cls, tz=None: pd.Timestamp(DAY, tz=tz))
    for name, module in list(sys.modules.items()):
        if name.startswith("portfusion") and getattr(module, "_dt", None) is datetime:
            module._dt = held


def main(port: str) -> None:
    with tempfile.TemporaryDirectory() as book:
        copy_demo(pathlib.Path(book))
        os.environ["PORTFUSION_BOOK"] = book
        import uvicorn

        from portfusion.desk import app
        hold_the_clock()
        uvicorn.run(app.app, host="127.0.0.1", port=int(port), log_level="warning")


if __name__ == "__main__":
    main(sys.argv[1])
