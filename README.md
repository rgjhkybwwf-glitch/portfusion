# PortFusion

A book's own record — holdings, trades, capital and what they are worth — kept as CSV files you
can read and diff, with every figure derived from them by one engine and shown two ways: a desk
in the browser, and a quarterly report. It records your own positions; it gives no advice.

## Try it

PortFusion needs Python 3.13. From a clone:

```bash
python3 -m venv .venv && .venv/bin/python3 -m pip install -e . -c requirements.lock
source .venv/bin/activate
portfusion desk --book demo          # the invented demo book, in a browser
portfusion init ~/my-book            # a new, empty book: its own folder and git history
cd ~/my-book && portfusion desk      # every command reads the book in the folder it is typed in
```

`portfusion init --practice` makes a copy of the demo to try things on. On a Mac,
`portfusion desk --install-agent` starts the desk at login for the book it is typed in.

A book is a folder:

```
store/      the facts: one CSV per kind of event          brand/    its name and look (optional)
_inbox/     documents waiting to be read onto the record   checks/   its own tests (optional)
_archive/   the documents behind the rows                  .githooks/  the secret gate
requirements.txt   the PortFusion release the book runs
```

## Taking a new release

A book names the release it runs in its own requirements.txt, and moves only when its owner changes
that line. Read the release's entry in `CHANGELOG.md`, change the line, then in the book's folder:

```bash
.venv/bin/python3 -m pip install -r requirements.txt
portfusion check                     # the guard, on this book
portfusion record                    # the audit
```

A release that changes a table's columns says in its changelog entry how to move a book's rows;
until they are moved, the record names the table and will not load. Restart the desk afterwards:
it does not notice an upgraded package (`docs/desk-app.md`). A book holds no code, so a change to
PortFusion is made in PortFusion, as `CONTRIBUTING.md` says.

## Where everything is

```
src/portfusion/
  record/     the schema, which types every column on load, and the record's rules
  engine.py   every derived figure, once
  desk/       the browser, and its doors — the only code that writes to a book
  report/     the quarterly report
  house/      what both renderers share: headings, precision, PortFusion's palette
  feeds/      the market feeds (IG, TradingView), read-only; history/  their append-only reads
  tests/      the guard, shipped with the app: `portfusion check` runs it
  demo/       the invented book; tools/make_demo.py writes it
```

A document becomes a row on the desk's Bench: it is read, each figure quoted back with the line
it came from, a person approves, and `desk/doors/commit.py` appends the row, files the document
and journals the write in one step. The engine derives from the record and the two renderers
show it; neither computes a figure of its own.

To change PortFusion, `CONTRIBUTING.md` sets up a checkout and says where each kind of change
goes; `docs/` holds the component guides, and `docs/glossary.md` what each word means here.

PortFusion is open source under the Apache License 2.0 (`LICENSE`). A security fault is
reported privately, as `SECURITY.md` says.
