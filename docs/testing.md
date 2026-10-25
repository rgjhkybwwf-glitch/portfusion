# Testing

What each layer of the guard proves, how to write a test, and what to do when one fails.
[`CONTRIBUTING.md`](../CONTRIBUTING.md) has the commands that set up and run it.

```bash
portfusion check               # the code on the demo, then the loaded book opening with its checks/
portfusion record              # the audit: what the record needs today
portfusion migrate             # a book carried to this release's store; --write moves it
python3 -m pytest -m audit     # the audit set alone
```

**One suite, any book.** `python3 -m pytest` runs on whichever book is loaded, and its last line
names that book. A check of one book's own facts lives in **that book's `checks/` folder**,
collected when that book is loaded (`tests/harness.py`). Everything in `tests/` must pass on any
book, which the demo run proves. A check another book could pass or fail belongs in `tests/` or
the audit, never in a book's `checks/`.

**Read a test's docstring before changing it.** It says why the check exists.

## What each layer proves

| Layer | Proves | Does not prove |
|---|---|---|
| `python3 -m pytest` | the code, on the loaded book's rows | that the record is in good order |
| the suite on the demo | the code runs on a book that is not yours | that the demo's figures are right |
| `portfusion check` | the code passes on the demo, and the loaded book opens: figures, findings, every page | that the code is right on your book's rows |
| `portfusion record` | whether the record is in good order: the findings, then the audit tests | anything about the code |
| `tools/clean_room.py` | the tracked files install fresh and pass on the demo and on a new, empty book, and the wheel built from them passes `portfusion check` | that nothing of a book is named in what leaves |
| `tools/advisories.py` | no package `requirements.lock` pins has an advisory OSV knows of | that the floors' older versions have none |
| `test_engine_ties`, `desk/test_ties.py` | the engine's figures agree seen from more than one side, and each page shows what the engine computed | that the engine is right |
| `test_engine_invariants` | the engine's arithmetic agrees with itself, assuming nothing | that a figure is the right answer |
| `test_demo` | `tools/make_demo.py` writes the demo exactly | that the demo's invented figures agree beyond the suite |
| `test_what_leaves` | nothing of the loaded book is named in the checkout, the commits not yet on `main` or the branch's name | anything, on the demo or a practice book: there is nothing to check |
| `test_code` | the code carries nothing only a test reads, and a function its comments name exists | that the code is right |
| the brokers' statements | the book against a figure nothing here can influence | an account that is not judged; the audit names those |
| eyes on the desk | whether a heading sits over its column | that the figure under it is right |

## Writing a test

- **Find a figure by its field or its label, never by position.** A column added in front
  breaks a positional read silently.
- **Assert a relationship or a shape, never an expected figure.** A real trade moves a number.
- **Say which rows a test is built from.** `needs("buys", …)` skips it on a book with none
  yet, saying so; never assume a row is there. A book lists the skips it expects in its
  `checks/skips.txt`, and any other skip there fails the run.
- **Hold any book, not the demo's shape.** A test picks its rows from the loaded book, or stubs
  them, so it passes on a book with two IG accounts as on the demo with one. A test of the
  demo's own documents skips elsewhere with `DEMO_ONLY`, which no book lists.
- **Write to a copy, never the loaded book.** `store_copy`, `item`, `workbench` and `inbox` give
  one. A run that moves the loaded book's `store/`, `_archive/` or `_inbox/` fails, every test
  green or not.

## A failing test

**On a deliberate change it is not a blocker**: update the expectation and say why in the commit
message. **On an accidental change it is the whole point.** Know which you have before you touch
it; if you are not sure, that is the finding.

**Never weaken a check to make it pass.** A fixture that fires means something real changed. A
warning that fires on a successful build is furniture, not a check. The feeds' allowlist tests
(`test_ig.py`, `test_tv.py`) are meant to stop you.
