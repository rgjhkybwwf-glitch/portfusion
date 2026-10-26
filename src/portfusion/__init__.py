"""PortFusion — the app, and no book. What it holds is README.md's folder map; the
folder of facts it reads is whichever `PORTFUSION_BOOK` names (`record/schema.py:BOOK`).
"""
import sys as _sys

#: THE RELEASE, PEP 440, in its one home: `pyproject.toml` reads it, `portfusion --version` prints
#: it, and the desk's footer and the report's stamp carry it (`about.release()`). Raised by
#: decision, never by every merge. Between releases it is the next one's `.devN`, and the commit
#: says which code it is; a release is tagged `v<version>` when this says it.
__version__ = "0.4.1.dev0"
#: What a release in this series is called beside its number. A label, not part of the number.
LABEL = "beta"


def book(argv: list[str]) -> tuple[list[str], str | None]:
    """`--book <folder>` or `--book=<folder>`, wherever it sits, taken out of the arguments.

    ONE FLAG FOR EVERY COMMAND, read before the command and not by each one, because the book is
    chosen when `record/schema.py` is first imported, before a command parses its arguments."""
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


def name_book(folder: str) -> bool:
    """`folder` as PORTFUSION_BOOK, for this process and whatever it starts — a desk's restart
    included: the word `demo` (record/schema.py:DEMO), or a path from where the command was typed.
    False, and nothing set, for a folder that holds no store/."""
    import os
    import pathlib
    if folder != "demo":
        path = pathlib.Path(folder).expanduser().resolve()
        if not (path / "store").is_dir():
            from portfusion.log import log
            log.error(f"no book at {path}: a book's folder holds its store/")
            return False
        folder = str(path)
    os.environ["PORTFUSION_BOOK"] = folder
    return True


# `python3 -m portfusion.<command>` imports this package first, with `-m` still first on the line:
# the command's --book is taken here, before any command reads a book. Another package's run is
# left alone.
_ran = _sys.orig_argv[_sys.orig_argv.index("-m") + 1:][:1] if "-m" in _sys.orig_argv else []
if _sys.argv[:1] == ["-m"] and _ran and _ran[0].split(".")[0] == "portfusion":
    _sys.argv[1:], _folder = book(_sys.argv[1:])
    if _folder is not None and not name_book(_folder):
        raise SystemExit(2)
