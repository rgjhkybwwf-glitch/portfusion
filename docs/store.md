# The store

A book's `store/` folder is its record: every sourced fact, one row per event, in a file for each
table `record/schema.py` registers, and the three append-only histories.

**A trade goes in `trades.csv`, a sale in `exits.csv`, a dividend in `income.csv`**, never in a
Python literal. **A new column or table is a `record/schema.py` change**, not a CSV one: the
schema checks every row on load, and a bad cell fails naming its table, row and column.

**`journal.csv` is about the record, not part of it**: one row per write, never an input to a
figure. A hand edit is allowed, and carries a `hand` journal row saying what it was.

**A row names its source** in the column its table provides. A `note` or `detail` says what
happened, never an instruction or how a figure was reached; those go in the commit message.

## What a column may hold

| Column | Values |
|---|---|
| `account` | one of the register's, `accounts.csv`; the loader refuses any other |
| `kind` · `category` · `funding` | closed lists in `record/schema.py`, printed in the glossary's §9. A line's kind sits once, on its code's `securities.csv` row |
| `cur` | on trades and exits, the currency the document states `price` in: `GBP` or the share's own |
| `id` | `T-NNN`; a fill in several legs takes letter suffixes, `T-NNNA`, `T-NNNB` |
| evidence class | `rules.EVIDENCE_CLASSES`, printed in the glossary's §9 |
| `broker_ref` | the deal's own reference (a contract number, a deal id), never a SEDOL; blank where no document prints one. The `source` then names only the document's kind and date (`trade_source()`) |

## What bites

- **A deal's `price` is its document's**, and `rate` only the broker's where it states one:
  never sterling ÷ quantity, which carries the dealing charge.
- **A share sale is one `exits.csv` row.** `share_pools()` derives what it released and what stays
  held.
- **The Realisation ID is the join key, not the ticker.** A code can be an open holding and a
  realised one at once. A spread-bet sale names the leg it closes in `closes`; a share sale names
  none. A realisation is one holding's (one account, one ticker), in the form
  `rules.REALISATION_FORM`.
- **A prose-dated leg takes its date from `closed-positions.csv` by ticker; a round trip joins it
  by Realisation ID.** Different keys on purpose.
- **A spread bet's stake is the bet**: `stake` in £ per point, the level in points, no `qty`; its
  cost is stake × level. It is priced by contract: its row names the contract, and
  `contracts.csv` gives the contract its epic. The write that closes a contract's last leg
  retires it.
- **A mark has three axes**: `quality` (provenance), `status` (lifecycle) and `struck` (`close`
  or `live`). A blank `struck` compares with nothing.
- **A frozen quarter end is restated, never edited.** `restate()` supersedes the rows and appends
  new ones, and `quarter-results.csv` records why.
- **Every file is LF.** Another line ending turns a two-row append into a whole-file diff.

**After any change here, check that the headline figures moved only in ways you can explain.**
