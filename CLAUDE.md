# PortFusion

A book's own record — holdings, trades, capital — kept as CSV facts, with every figure derived
from them by one engine and shown by the desk and the quarterly report. [`README.md`](README.md)
is the way in and the folder map; **[`CONTRIBUTING.md`](CONTRIBUTING.md) is how a change is
worked — read it before changing anything.**

```bash
source .venv/bin/activate                 # once per terminal (docs/environment.md)
python3 -m pytest                         # the guard: green unless the code broke
portfusion record                         # the audit: what the record needs
python3 tools/clean_room.py               # the app on its own: a copy, a new book and a wheel
portfusion desk                           # the desk, in a browser
```

Every command reads the book in the folder it is typed in, or the one `PORTFUSION_BOOK` names.

## Pointers

| Where | What it holds |
|---|---|
| [`docs/store.md`](docs/store.md) | which table a fact goes in, and what each column may hold |
| `record/rules.py` | the record's rules; the desk's Method page renders them |
| `engine.py` | every derived figure, once; `Book.HEADLINE` registers the headline ones |
| [`docs/testing.md`](docs/testing.md) | what each layer of the guard proves, and what to do when a test fails |
| [`docs/`](docs) | the component guides; [`docs/glossary.md`](docs/glossary.md) is the agreed nomenclature |

## Open work

The repository's issues (`gh issue list`).
