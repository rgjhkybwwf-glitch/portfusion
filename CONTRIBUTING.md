# Contributing to PortFusion

For anyone changing PortFusion, a collaborator or a Claude session arriving cold. `README.md`
says what PortFusion is; this says how a change is worked.

## Setting up

```bash
git config core.hooksPath .githooks       # the gate that keeps credentials out of git
python3 -m venv .venv && .venv/bin/python3 -m pip install -e '.[dev]' -c requirements.lock
python3 -m pytest                          # the guard, on the book in this folder
PORTFUSION_BOOK=demo python3 -m pytest     # on the demo
python3 tools/clean_room.py                # the app on its own: a copy, a new book and a wheel
```

`docs/testing.md` says what each layer of the guard proves, and what to do when a test fails.

## Agree first, and stop when a decision appears

- **Propose before changing**, in an issue or the conversation, and wait for the maintainer's
  yes. An approval covers exactly what it names.
- **A decision that appears mid-task is a stop**, and so is a test or guide that would bend one
  already agreed. A test that only needs its expectation moved to the agreed outcome is not.
- **Options carry their cost** (files, tests, figures that move), with a recommendation. A
  declined one is not raised again.

## Where a change goes

| To add | Write it in | Held by |
|---|---|---|
| a table, or a value in a vocabulary | `record/schema.py` | `tests/test_schema.py` |
| a headline figure | a `Book` method and its entry in `Book.HEADLINE` | `tests/test_figures.py` |
| a column heading | `house/headings.py` | `tests/test_figures.py` |
| a desk panel | `desk/panels/<name>.py` | `tests/desk/test_panels.py` |
| anything that writes a file, or opens a CSV | its door, named in `DESK_WRITERS` or `CSV_FILE_READERS` | `tests/desk/test_boundaries.py`, `tests/test_store_doors.py` |
| a kind of document | an `Evidence` in `record/rules_evidence.py` | `tests/test_evidence.py` |
| a feed endpoint | the allowlist in `feeds/ig.py` or `feeds/tv.py` | `tests/test_ig.py`, `tests/test_tv.py` — meant to stop you |

Search for what already does the job before adding anything; give a function a parameter rather
than a second version.

## Commits and pull requests

- **One logical change per commit**, its message written for a reader who was not there.
- **Run the guard unpiped before committing**: a pipe returns the last command's status.
- **Never bypass a hook.** A branch reaches `main` as a pull request, merged once CI is green.

## The desk and the report

- **Check a change on the demo**: `portfusion desk --book demo --port 8769`, never on a desk a
  book is using.
- **The renderers move together**: what changes on the desk changes on the report.
- **The desk carries as little prose as it can**; `DESK_CHROME_WORDS` is cut, never raised.
