# PortFusion

A book's own record — holdings, trades, capital and what they are worth — kept as CSV files you
can read and diff, with every figure derived from them by one engine and shown two ways: a desk
in the browser, and a quarterly report. It records your own positions; it gives no advice.

## Try it

PortFusion needs Python 3.13 or newer.

```bash
python3 -m venv ~/.portfusion && ~/.portfusion/bin/python3 -m pip install "portfusion @ git+https://github.com/rgjhkybwwf-glitch/portfusion@v0.3.2" -c https://raw.githubusercontent.com/rgjhkybwwf-glitch/portfusion/v0.3.2/requirements.lock
~/.portfusion/bin/portfusion desk --book demo     # the invented demo book, in a browser
~/.portfusion/bin/portfusion init ~/my-book       # a new, empty book: its venv and git history
cd ~/my-book && source .venv/bin/activate
portfusion desk                                   # reads the book in the folder it is typed in
```

| `portfusion init` with | Makes |
|---|---|
| `--practice` | a copy of the demo, to try things on |
| `--begins 2026-05-18` | a book whose record begins that day |
| `--push-on-commit` | a book whose every commit is pushed to its remote as it lands |

On a Mac, `portfusion desk --install-agent` starts the desk at login for the book it is typed in.
`portfusion --help` lists every command: the seven actions, and the rest.

| A book's folder | Holds |
|---|---|
| `store/` | the facts: one CSV per kind of event |
| `_inbox/` | documents waiting to be read onto the record |
| `_archive/` | the documents behind the rows |
| `brand/` | its name and look (optional) |
| `checks/` | its own tests (optional) |
| `.githooks/` | its guards |
| `requirements.txt` | the PortFusion release it runs, and the lock it installs against |
| `.venv/` | that release, installed by `portfusion init` |

## Taking a new release

A book names the release it runs in its own `requirements.txt`, and moves only when its owner
changes that line. Read the release's entry in [`CHANGELOG.md`](CHANGELOG.md), change the line,
then in the book's folder:

```bash
.venv/bin/python3 -m pip install --force-reinstall --no-deps -r requirements.txt   # the pinned code
.venv/bin/python3 -m pip install -r requirements.txt                               # what it needs
portfusion migrate                   # what the release moves in the store; --write moves it
portfusion check                     # the guard, on this book
portfusion record                    # the audit
```

| Step | Why |
|---|---|
| the first install is forced | two commits can carry one version number, and a plain install keeps the old code |
| `migrate --write` | until the release's store moves are made the book will not load, and the loader names the table; it opens and audits the book, and puts every file back if either fails |
| moves the entry gives as by hand, and the lines of `checks/` it lists | made first, and committed as the book's own change |
| a hook or `.gitignore` the audit names | copied from a book `portfusion init` makes in a scratch folder |
| restart the desk | it does not notice an upgraded package ([`docs/desk-app.md`](docs/desk-app.md)) |

## Where everything is

| `src/portfusion/` | Holds |
|---|---|
| `record/` | the schema, which types every column on load, and the record's rules |
| `engine/` | every derived figure, once |
| `desk/` | the browser, and its doors to the record |
| `report/` | the quarterly report |
| `house/` | what both renderers share: headings, precision, PortFusion's palette |
| `feeds/` | the market feeds (IG, TradingView), read-only |
| `history/` | the histories: prices, FX rates and account values over time |
| `tests/` | the guard, shipped with the app: `portfusion check` runs it; a folder per package it tests |
| `demo/` | the invented book; `tools/make_demo.py` writes it |

A document becomes a row only on the desk's Bench, by a person's approval
([`docs/intake.md`](docs/intake.md)). The engine derives every figure from the record; the desk and
the report show it and compute none.

A book holds no code, so a change to PortFusion is made here: [`CONTRIBUTING.md`](CONTRIBUTING.md)
sets up a checkout and says where each kind of change goes, [`docs/`](docs) holds the component
guides, and [`docs/glossary.md`](docs/glossary.md) what each word means here.

PortFusion is open source under the Apache License 2.0 ([`LICENSE`](LICENSE)). A security fault
is reported privately, as [`SECURITY.md`](SECURITY.md) says.
