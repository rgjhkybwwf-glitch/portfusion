# The store

A book's `store/` folder is its record: every sourced fact, one row per event, in a file for each
table `record/schema.py` registers, and the three append-only histories.

**A trade goes in `buys.csv`, a sale in `sales.csv`, a dividend in `income.csv`**, never in a
Python literal. **A new column or table is a `record/schema.py` change**, not a CSV one: the
schema checks every row on load, and a bad cell fails naming its table, row and column.

**Every event table reads as it happened**: by date, then the account's place in the register,
then ticker (`record/order.py`). A door writes a row where its date puts it; the loader refuses a
table out of that order, and `portfusion migrate` puts a book in it.

**`journal.csv` is about the record, not part of it**: one row per write, never an input to a
figure. A hand edit is allowed, and carries a `hand` journal row saying what it was.

**A row names its source** in the column its table provides. A `note` or `detail` says what
happened, never an instruction or how a figure was reached; those go in the commit message.

## What a column may hold

| Column | Values |
|---|---|
| `account` | one of the register's, `accounts.csv`; the loader refuses any other |
| `held_as` · `category` · `funding` | closed lists in `record/schema.py`, printed in the glossary's §9. A line's `held_as` sits once, on its ticker's `securities.csv` row |
| `ticker` on income | the line a dividend was paid on; blank on interest, fees and funding |
| `symbol` · `quote_unit` | a listing as its market names it: the market's ISO code and its ticker (`XLON:BRYC`, `XCSE:HALD B`), and the unit it quotes in (`GBX` is pence). The price feed translates the symbol into its own form |
| `points_per_unit` · `shares_per_unit` | on a spread-bet line: how many points make one unit of its listing's price (100 where IG quotes in cents or pence), and how many shares one unit of the listing stands for (blank is one; a depositary receipt's ratio). With the stake they make a bet's share-equivalents |
| `cur` | on buys and sales, the currency the document states `traded_price` in: `GBP` or the share's own |
| `cost` · `level_points` | on a buy: a share's settled sterling, or a spread bet's entry level in points; the other is blank |
| `trade_id` · `sale_id` | `T-NNN` and `E-NNN`, the row's place in date order: given when the row is written, and moved, with every `closes` and note that names it, when an earlier-dated row is written before it |
| evidence class | `rules.EVIDENCE_CLASSES`, printed in the glossary's §9 |
| `broker_ref` | the deal's own reference (a contract number, a deal id), never a SEDOL; blank where no document prints one. The `source` then names only the document's kind and date (`trade_source()`) |

## What bites

- **A deal's `traded_price` is its document's**, and `rate` only the broker's where it states one:
  never sterling ÷ quantity, which carries the dealing charge.
- **A share sale is one `sales.csv` row.** `share_pools()` derives what it released and what stays
  held.
- **The Realisation ID is the join key, not the ticker.** A code can be an open holding and a
  realised one at once. A spread-bet sale names the leg it closes in `closes`; a share sale names
  none. A realisation is one holding's (one account, one ticker), in the form
  `rules.REALISATION_FORM`.
- **A spread bet's stake is the bet**: `stake` in £ per point, the level in points, no `qty`; its
  cost is stake × level. It is priced by contract: its row names the contract, and
  `contracts.csv` gives the contract its epic and the ticker of its line, which is the leg's.
  The write that closes a contract's last leg retires it.
- **A live price is on a line still held.** The sale that leaves a share in no account banks its
  price and takes it out of `current-prices.csv`, as a contract's last close does; the audit
  names any price nothing holds.
- **A mark has two axes**: `quality` (provenance) and `struck` (`close` or `live`). A blank
  `struck` compares with nothing.
- **A share account's cash is in one place, its cash readings.** A reading off a document that
  states the cash writes it as a cash reading of that day, and the reading's total is its stock
  plus that cash. A spread bet's cash is IG's funds, on its reading.
- **A correction replaces its row.** A mark read again on its own day takes its row's place, and
  `restate()` replaces a frozen quarter end's rows and results, the journal saying why; git keeps
  what each row said. One row per fact, so no reader filters.
- **Every file is LF.** Another line ending turns a two-row append into a whole-file diff.

**After any change here, check that the headline figures moved only in ways you can explain.**
