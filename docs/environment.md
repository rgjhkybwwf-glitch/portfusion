# The environment

Python 3.13 or newer, and one venv per checkout. `pyproject.toml` names the packages and
`requirements.lock` the exact set the suite was proved on.

```bash
python3 -m venv .venv && .venv/bin/python3 -m pip install -e '.[dev]' -c requirements.lock
source .venv/bin/activate          # once per terminal: `python3` is then the venv's
```

**The tests refuse any other interpreter** and print the fix; **the audit only reports it**, on
its `python:` line, so a report can still be built the day a venv breaks.

**A venv does not survive its folder being moved.** It records its own absolute path, so after a
move `python3` falls back to the system's, and the first sign is a desk test failing with
`No module named 'fastapi'`. Rebuild it with the first line above, after `rm -rf .venv`; do the
same after changing Python.

**A second checkout needs a venv of its own**: the tests refuse unless the app comes from their
own `src/`.

**A running desk keeps what it imported.** Rebuilding the venv or changing Python reaches it only
when it restarts (`docs/desk-app.md`).

## Which book

Every command reads the book in the folder it is typed in, and refuses in a folder that holds
none. `PORTFUSION_BOOK` names another, absolute or relative; `--book` does the same for one run
of any `portfusion` action; `demo` is the invented book the app ships:

```bash
portfusion desk --book demo --port 8769
```

Every test run and every audit names the book it read on a `book:` line. Read it before trusting
a green.
