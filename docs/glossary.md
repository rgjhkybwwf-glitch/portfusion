# Glossary

The words the record, the desk and the report use, and where each is defined. **Where a term has
a home in code, this points at it and stops**: a second telling is the one that goes stale, and
`test_record.py` refuses one for the rules the record states once. If this file and the code
disagree, the code is right.

---

## 1 · The words that live once

| Term | Defined in | A reader meets it in |
|---|---|---|
| Statement-grade | `rules.STATEMENT_GRADE` | the Method page |
| The source hierarchy | `rules.SOURCE_HIERARCHY`, `rules.SOURCE_HIERARCHY_NOTE` | the Method page |
| What a spread bet is | `rules.SPREAD_BET` | the Method page |
| What a document is | `rules.EVIDENCE_CLASSES`, `rules.RETRIEVAL_KINDS` | §9 |

## 2 · `basis`, and the words that took its other senses

| The question | Word | Values | Where |
|---|---|---|---|
| What kind of number is this? | **`basis`** | `capital` · `notional` · `mixed` · `count` | `Book.HEADLINE`, `MEASURE_BASIS` |
| What document is this row's evidence? | **`source`** | free text | every table |
| How does this account contribute to net asset value? | **`contribution`** | `positions at market` · `account equity` · `notional` | `quarter-nav.csv` |
| Do we own it, or have exposure to it? | **`kind`**, shown as **Held as** | `shares` · `spread bet` | `schema.KINDS`; `held_as` on every frame |
| Which set of measures? | **`measure=`** | `nav` · `exposure` | `quarter_nav_rows()` |
| What unit is this price quoted in? | **Price unit** | points · GBP | the column heading |
| The accounting sense | **cost basis** | — | — |

`basis` pairs with *measure*, a column you can total, in `MEASURE_BASIS` and `roll_up()`.

## 2b · `movement` and `reading`

**`movement` is never used bare**; the qualifier keeps its senses apart.

| Sense | Spelling |
|---|---|
| Capital crossing the book's boundary | **capital movement** — `capital-movements.csv`, `Book.capital_movements()` |
| A broker's document | the broker's own name for it |
| The up and down colour on the desk | **movement colour** — `house/palette.py`, `MOVEMENTCOL` in `app.js` |
| Ordinary prose | *price movement*, wherever no named figure is at stake |

| Sense | Spelling |
|---|---|
| A broker-side figure for an account, at an instant | **reading** — a row of `account-observations.csv` |
| A document retrieved by asking again, for a new instant | **`reading`**, one of `rules.RETRIEVAL_KINDS` |
| What a Claude session hands the Bench after transcribing a document | **proposal** — `desk/intake/propose.py` |

## 3 · Provenance

| Value | Means |
|---|---|
| `sourced` | from a named authority, retrievable again |
| `derived` | anything else: computed or reconstructed by the book, or a figure nothing on file retrieves |

A `derived` figure becomes `sourced` only when the evidence itself changes. The vocabulary is
`schema.QUALITIES`, and each history declares its subset. `superseded` is not provenance but a
lifecycle: the `status` column.

## 4 · Time

| Layer | Word |
|---|---|
| What a reader reads | **As at** — the date a value was measured, when it is not a quarter boundary |
| A column or a Python name | **`as_of`** |
| The instant a figure was read | **`at`**, ISO and UTC, on `current-prices.csv` and `account-observations.csv`; the journal's `at` is local time |
| What instant a mark describes | **`struck`** — `close`, a session close that can be fetched again, or `live`, a read that cannot |

**"As at" is a label; `as_of` is a name.** A name need not be what a reader sees, but it must
not mean two things.

A **Quarter** always carries its year (`Book.quarter_label()`), bounded by **Quarter start** and
**Quarter end**. **Entry date**, **Exit date** and **Date** are when an event happened. **The
freeze** writes a quarter end's rows (`Book.freeze_rows()`), and the quarter is then closed and
held to its **Results** (`quarter-results.csv`); **a restatement** is a later row that moves
them, with its reason. **The close** is the work around a freeze.

### The store's own names

One idea, one column name, in every table.

| Idea | Column |
|---|---|
| An account | `account` |
| A deal's price, as its document states it | `price` |
| The broker's rate, where its document states one | `rate` — units of the other currency per £1 |
| An instrument's currency | `currency` |
| The currency a deal's price is stated in | `cur` — not always the instrument's |
| The provenance line | `source` |
| An evidence-class key | `evidence`, on the two observation tables only |
| Owned, or exposure | `kind` |
| A sterling amount on an event | `amount` |
| A trade leg's own figure | `val` — cost on a share leg, entry level on a spread bet |
| A frozen line's value | `gbp_value` |
| A lifecycle | `status` — `live` · `superseded` |
| An instant | `at` |

### The three clocks

| Clock | Answers | Lives in |
|---|---|---|
| **Market time** | when a price moved | the price and FX histories |
| **Event time** | when the thing happened | every `date` and `as_of` column |
| **Record time** | when the book learned it | `journal.csv`, forward from the day it opened |

A page showing two clocks names the clock on every block, as What Changed does. The engine also
carries `priced_at`, the oldest mark across a position's open legs, and `priced_from`, the mark
a `changes_since()` window opened at.

## 5 · What a reader is shown

Every heading comes from `house/headings.py`, on the desk and the report alike, and
`test_figures.py` holds this section's bold words to that list. Spelling is British: *realised*,
not *realized*.

| Concept | Canonical |
|---|---|
| Gain on an open position | **Unrealised gain (GBP) · Unrealised gain (%)** |
| Gain on a closed position | **Realised gain (GBP) · Realised gain (%)** |
| A line's gain over a quarter | **Quarter gain (GBP)** |
| A round trip's prices, in the share's own currency | **Entry price · Exit price**, beside **Ccy** |
| Issuer name | **Company** |
| Instrument code | **Ticker** |
| Trade direction | **Direction** — Buy · Sell · Adjustment (a split or consolidation) |
| Net asset value at a quarter's bounds | **Opening NAV · Closing NAV** |
| Money into positions | **Capital deployed** |
| Sterling | `… (GBP)` on every sterling column of a table that also shows a local figure; elsewhere each cell prints its £ |
| How many are held | **Quantity** |
| The key of a realisation | **Realisation ID** |
| When a position was entered | **Entry date** |
| Weighted entry price | **Entry price**, in the line's own currency |
| A line's mark, and its date | **Price · Price as at** |
| The price of one fill | **Traded price** |
| The ledger's figure | **Book** |
| The broker's figure | **Broker** |
| The firm an account is held with | **Broker firm** |
| A cell naming several accounts | **Accounts** |
| A total row | **Total** |
| Net asset value, as a column | **Net asset value** |
| Spread-bet notional, as a column | **Spread-bet notional** |
| The year's income, fees and cash interest included | **YTD income** |
| An income row's kind | **Category** |
| Reasoning headings | **Why we entered · Why we exited** |
| A Bench field | **Sale ID · Closes trade · Rate (per £1) · IG contract · Document kind** |
| What a row opens to | **Detail** — one link, in one order (`DETAIL` in `app.js`) |

**Entry price and Traded price are different quantities**: the first is the weighted mean of the
legs still held, the second what one fill paid.

### The three effects of a change in value

| Concept | Canonical | Note |
|---|---|---|
| What the price alone did to a line's value | **From price (GBP)** | never a share price |
| What the exchange rate alone did | **From FX (GBP)** | measured to the live rate; zero on a spread bet |
| What buying or selling did, at what was transacted | **From dealing (GBP)** | |

The three sum exactly to **Change (GBP)**; the order they are taken in is
`Book.changes_since()`'s.

### What a position row says about its last mark

| Concept | Canonical | Note |
|---|---|---|
| How far a line's mark moved, against its own previous mark | **Mark move (%)** | not the change in value |
| Every banked mark behind one line | **Mark history** | the end of a Holdings row's detail |

### What a sale closes

| Concept | Canonical | Note |
|---|---|---|
| One buy row in the ledger | **Leg** | a spread-bet sale names the leg it closes |
| One account's shares in one ticker, at their average cost | **Pool** | an emptied pool bought again is a new one |
| What a sale took off the cost held | **Cost released** | a pool's average for a share; the leg's cost for a spread bet |
| Everything sold out of one holding, keyed `R-…` | **Realisation** | headed **Realisation ID** |
| A realisation seen whole, entry to exit | **Round trip** | the Round Trips page |
| Every buy and sale on file | **Trades** | the Trades page |

### Running a refresh

| Concept | Canonical | Note |
|---|---|---|
| The screen a refresh is run from | **Price Refresh** | |
| One pass over the feeds for every mark, written nowhere | **Sweep** | `feeds/refresh.py` |
| A mark kept in its history before it is replaced | **Banked** | |
| A mark left at its last level by decision, with the reason on the row | **Carried** | not *unpriced*; the stored key is `held` |
| A figure a feed returned | **Fetched** | |
| A figure read off a filed broker document | **Filed** | |
| A line the sweep could not price | **Unpriced** | the reason on hover |
| A rate entered by hand | **Typed** | the only thing still typed |

### What the book learned, and when

| Concept | Canonical | Note |
|---|---|---|
| The table of every write to the record | **The journal** | one row per write |
| Who made a write | **Route** | §9 |
| What it did to the row count | **Op** — `open` · `append` · `replace` · `remove` | |
| The row a table's journal opens with | **The opening count** | `route=baseline, op=open` |
| A row that arrived by no journalled route | **Unaccounted** | `portfusion record` counts them: a finding, not a failure |

Opening count + appends − removes = rows on file, table by table; a replace adds none.

## 6 · Where the book's words meet standard practice

| The book says | Practice says | Note |
|---|---|---|
| **YTD return (MWR)** | money-weighted return | Modified Dietz, day-weighted; **not comparable to an index**, which is time-weighted |
| **Return since … (MWR)**, from the record's first day | linked return | each full year's return, linked with the year to date; not comparable to an index either |
| **Total market exposure** | gross exposure | no netting: the book holds no short positions |
| **Capital deployed** | contributions | money into positions, not across the book's boundary |
| **Capital employed** | invested capital | opening NAV plus capital deployed |
| **Pool** | section 104 holding | |

**Capital movements** cross the book's boundary; **capital deployed** is committed to
positions. `roll_up()` and `MEASURE_BASIS` keep them apart.

## 8 · Other closed lists, and where each is declared

| List | Declared in |
|---|---|
| The accounts, in order, and the code each is shown by to anyone but the owner | `rules.ACCOUNT_ORDER`, the register's `code` |
| What retrieves a document | `rules.RETRIEVAL_KINDS` |
| How a document is recognised | `rules.Evidence.fingerprint` |
| How an archived document is named | `rules.ARCHIVE_CONVENTION` |
| Which desk columns wear movement colour | `MOVEMENTCOL` in `app.js` |
| Currency, region, sector, ticker | open: a new one is not refused, and the Bench offers those in use |

---

<!-- BEGIN DERIVED — generated by glossary.py; do not edit between the markers -->

## 9 · The record's own words, generated

**Everything below this line is DERIVED from the `record/` modules and
`Book.HEADLINE` by `glossary.py`, and `tests/test_record.py` asserts that the
checked-in file matches what those constants produce.** It cannot drift, which is
the complaint that started this document. It is an INDEX — names, values and where
they live. What a word MEANS stays where it is defined, and `test_record.py`
refuses this block if it starts to define one.

### Every registered headline figure

| Figure | Basis | Unit | A dated page may quote it |
|---|---|---|---|
| Net asset value | `capital` | gbp | yes |
| Total market exposure | `notional` | gbp | yes |
| — of which securities owned | `capital` | gbp | yes |
| — of which spread-bet notional | `notional` | gbp | yes |
| Exposure above net asset value | `notional` | gbp | yes |
| Cost of securities owned | `capital` | gbp | **no — live only** |
| Spread-bet notional at entry | `notional` | gbp | **no — live only** |
| Unrealised gain / loss | `capital` | gbp | **no — live only** |
| Realised gain / loss to date | `capital` | gbp | **no — live only** |
| Total gain | `capital` | gbp | **no — live only** |
| YTD income | `capital` | gbp | **no — live only** |
| Capital employed (opening + deployed) | `capital` | gbp | **no — live only** |
| YTD return (MWR) | `capital` | pct | **no — live only** |
| Return since 1 Jan 2026 (MWR) | `capital` | pct | **no — live only** |
| Open positions | `count` | count | yes |
| Closed round trips | `count` | count | **no — live only** |

### Vocabularies declared to the LOADER

A value outside these fails **on load**, naming the table, the row and the column.

| Column | Values | Tables |
|---|---|---|
| `kind` | `shares` · `spread bet` | `securities` · `accounts` |
| `category` | `Dividend` · `Funding interest` · `Cash interest` · `Fee` | `income` |
| `quality` | `sourced` · `derived` | `quarter-nav` · `quarter-snapshots` · `baseline-reconstruction` |
| `status` | `live` · `superseded` | `quarter-nav` · `quarter-snapshots` |
| `struck` | `close` · `live` | `fx` · `current-prices` |
| `key` | `record_begins` · `reasoning_owed_from` · `first_report` · `tv_list_live` · `tv_list_exit` · `tv_list_entry` · `rate_carried` · `trade_id_floor` · `hosted_origin` · `passkey_domain` · `deploy_repo` · `research_repo` · `insights_url` · `practice` | `settings` |
| `funding` | `daily` · `dated` | `contracts` |
| `route` | `baseline` · `bench` · `marks` · `freeze` · `hand` | `journal` |
| `op` | `open` · `append` · `replace` · `remove` | `journal` |
| `table` | the 20 record tables | `journal` |

### Vocabularies the record's rules hold

Closed sets `record/rules.py` keeps beside the loader's. An account name is refused
on load by the join to the register (`schema.REFERENCES`) and the income split is
asserted on import; the rest are held by the suite.

| Vocabulary | Values | Declared in |
|---|---|---|
| Evidence classes | `ii-contract-note` · `ii-statement` · `ii-valuation` · `ii-transactions` · `hl-statement` · `hl-valuation` · `hl-income` · `hl-transactions` · `hl-account-totals` · `hl-movements` · `ig-statement` · `ig-api` · `ig-accounts` · `not-on-file` | `rules.EVIDENCE_CLASSES` |
| Income that reaches the RETURN | `Dividend` · `Funding interest` | `rules.POSITION_INCOME` |
| Income that does NOT | `Cash interest` · `Fee` | `rules.ACCOUNT_INCOME` |

### The store, table by table

| Table | Columns | What it holds |
|---|---|---|
| `account-observations.csv` | 13 | What the book holds each account to be worth RIGHT NOW, and the observation it rests on |
| `accounts.csv` | 7 | The account register |
| `baseline-reconstruction.csv` | 7 | Reconstructed holdings, line by line: the working behind an account's quarter-nav rows as FIRST FILED |
| `capital-movements.csv` | 5 | External capital in and out, one row per event |
| `cash-observations.csv` | 5 | HOW MUCH CASH AN ACCOUNT HELD, AND WHEN |
| `closed-positions.csv` | 4 | What a realisation's events cannot say about it: the entry date where a leg carries prose, and the note written when it was realised |
| `contracts.csv` | 4 | One row per IG contract a spread-bet leg names, with the epic that prices it, how IG funds it, and the code of the line it is on |
| `current-prices.csv` | 7 | What things are worth NOW — never what was paid, which is the ledger |
| `exits.csv` | 15 | One row per sale |
| `fx.csv` | 5 | The rate each currency is converted at NOW, one row per currency, as current-prices |
| `income.csv` | 10 | Dividends, interest and fees |
| `issuers.csv` | 3 | One row per ISSUER — the company, not the holding |
| `journal.csv` | 7 | RECORD TIME — when the book LEARNED a thing, as against when the thing HAPPENED |
| `quarter-nav.csv` | 7 | Each account's CONTRIBUTION to net asset value at each quarter end |
| `quarter-results.csv` | 9 | Each closed quarter's six figures, for the book and for each account, as the engine gave them — what a closed quarter is HELD TO, never what a renderer shows |
| `quarter-snapshots.csv` | 11 | Every account's HOLDINGS, line by line, at each quarter end — the working behind quarter-nav |
| `reasoning.csv` | 4 | WHY a position was taken and why it was closed — one row per DECISION: the ticker, the date of the trade or sale it explains, and the why |
| `research-notes.csv` | 4 | WHICH RESEARCH NOTES COVER WHICH INSTRUMENT |
| `securities.csv` | 6 | One row per CODE held, reserved or closed |
| `settings.csv` | 2 | The book's own settings: one row per key in SETTING_KEYS |
| `trades.csv` | 14 | THE LEDGER — one row per buy leg |

<!-- END DERIVED -->

---

## Changing a word

A word changes here and in its declaration in the same commit. `python3 tools/glossary.py
--write` regenerates §9.
