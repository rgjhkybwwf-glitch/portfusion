# PortFusion

A book's own record — holdings, trades, capital — kept as CSV facts, with every figure derived
from them by one engine and shown by the desk and the quarterly report. [`README.md`](README.md)
is the way in and the folder map; **[`CONTRIBUTING.md`](CONTRIBUTING.md) is how a change is
worked — read it before changing anything.** Every commit's diff goes through the `code-review` skill
before it is pushed, at the level its tier takes (CONTRIBUTING, Commits and pull requests).

```bash
source .venv/bin/activate                 # once per terminal (docs/environment.md)
export PORTFUSION_BOOK=demo               # once per terminal: a checkout holds no book
python3 -m pytest                         # the guard: green unless the code broke
portfusion record                         # the audit: what the record needs
python3 tools/clean_room.py               # the app on its own: a copy, a new book and a wheel
portfusion desk --port 8769               # the desk, in a browser, beside any book's
```

Every command but `init`, and the suite, read the book `PORTFUSION_BOOK` names, or the one in the
folder they are typed in ([`docs/environment.md`](docs/environment.md), Which book).

## Pointers

| Where | What it holds |
|---|---|
| [`docs/store.md`](docs/store.md) | which table a fact goes in, and what each column may hold |
| `record/rules.py` | the record's rules; the desk's Method page (`desk/panels/method.py`) shows them |
| `engine/` | every derived figure, once; `Book.HEADLINE`, in `engine/book.py`, registers the headline ones |
| [`docs/testing.md`](docs/testing.md) | what each layer of the guard proves, and what to do when a test fails |
| [`docs/content-map.md`](docs/content-map.md) | which page and report section answers each job; a page's work is designed against it |
| [`docs/`](docs) | the component guides; [`docs/glossary.md`](docs/glossary.md) is the agreed nomenclature |

## Open work

The Queue (issue #206) orders what is built next, the milestones say what each release is for, and
[`docs/direction.md`](docs/direction.md) says who it is for and where it is going. `gh issue list`
shows the rest; in a cloud session, where `gh`'s GraphQL is refused, the GitHub tools'
`list_issues`.
