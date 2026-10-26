# Glossary

The words the record, the desk and the report use, and where each is defined.

**Where a term has a home in code, this points at it and stops**: a second telling is the one
that goes stale, and `test_record.py` refuses one for the rules the record states once. If this
file and the code disagree, the code is right.

---

## 1 · The words that live once

| Term | Defined in | A reader meets it in |
|---|---|---|
| Statement-grade | `rules.STATEMENT_GRADE` | the Method page |
| The source hierarchy | `rules.SOURCE_HIERARCHY`, `rules.SOURCE_HIERARCHY_NOTE` | the Method page |
| What a spread bet is | `rules.SPREAD_BET` | the Method page |
| What a document is | `rules.EVIDENCE_CLASSES`, `rules.RETRIEVAL_KINDS` | §9 |

## 2 · `basis`, and the words used instead of it

| The question | Word | Values | Where |
|---|---|---|---|
| What kind of number is this? | **`basis`** | `capital` · `notional` · `count` | `Book.HEADLINE`, `MEASURE_BASIS` |
| What document is this row's evidence? | **`source`** | [the store](store.md) | the event, mark and quarter-end tables; a reading's is `evidence` · `reference` |
| How does this account contribute to net asset value? | **`contribution`** | §9 | `schema.CONTRIBUTIONS` |
| Do we own it, or have exposure to it? | **`held_as`**, shown as **Held as** | §9; `mixed` on a company row holding both | `schema.KINDS`, and every frame |
| Which set of measures? | **`measure=`** | `nav` · `exposure` | `quarter_nav_rows()` |
| What unit is a listing quoted in? | **`quote_unit`**, shown as **Quote unit** | [the store](store.md) | `securities.csv` |
| The accounting sense | **cost basis** | — | — |

`basis` pairs with *measure*, a column you can total, in `MEASURE_BASIS` and `roll_up()`.

## 2b · `movement` and `reading`

**`movement` is never used bare**; the qualifier keeps its senses apart.

| Sense | Spelling |
|---|---|
| Capital crossing the book's boundary | **capital movement** — `capital-movements.csv`, `Book.capital_movements()` |
| A broker's document | the broker's own name for it |
| The up and down colour on the desk | **movement colour** — `house/palette.py`, `MOVEMENTCOL` in `kit.js` |
| Ordinary prose | *price movement*, wherever no named figure is at stake |

| Sense | Spelling |
|---|---|
| A broker-side figure for an account, at an instant | **reading** — a row of `account-readings.csv`, or of `cash-readings.csv` (a cash reading) |
| A document retrieved by asking again, for a new instant | **`reading`**, one of `rules.RETRIEVAL_KINDS` |
| What a Claude session hands the Bench after transcribing a document | **proposal** — `desk/intake/propose.py` |

## 3 · Provenance

| Value | Means |
|---|---|
| `sourced` | from a named authority, retrievable again |
| `derived` | anything else: computed or reconstructed by the book, or a figure nothing on file retrieves |

A `derived` figure becomes `sourced` only when the evidence itself changes. The vocabulary is
`schema.QUALITIES`, and each history declares its subset.

## 4 · Time

| Layer | Word |
|---|---|
| What a reader reads | **As at** — the date a value was measured, when it is not a quarter boundary |
| A column or a Python name | **`as_of`** |
| The instant a figure was read or written | **`at`**, ISO and UTC, marked `Z`, on `current-prices.csv`, `account-readings.csv` and `journal.csv` |
| What instant a mark describes | **`struck`** — `close`, a session close that can be fetched again, or `live`, a read that cannot |

**"As at" is a label; `as_of` is a name.** A name need not be what a reader sees, but it must
not mean two things.

A **Quarter** always carries its year (`Book.quarter_label()`), bounded by **Quarter start** and
**Quarter end**. **Entry date**, **Exit date** and **Date** are when an event happened. **The
freeze** writes a quarter end's rows (`Book.freeze_rows()`), and the quarter is then closed and
held to its **Results** (`quarter-results.csv`); **a restatement** replaces those rows, with its
reason. **The close** is the work around a freeze.

**One idea, one column name, in every table**: [the store](store.md) lists them.

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
| A buy's trade ID or a sale's sale ID, on the engine's ledger | `event_id`, never shown |
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
| Spread-bet notional, on Holdings' strip | **Spread-bet notional** |
| The year's income, fees and cash interest included | **YTD income** |
| An income row's kind | **Category** |
| Reasoning headings | **Why we entered · Why we exited** |
| A Bench field | **Sale ID · Closes trade · Rate (per £1) · IG contract · Document kind · Reference · Also retires · Renumbers · Symbol · Quote unit · Points per unit · Shares per unit · Epic · Cash (GBP) · Amount** |
| An account, as the register holds it | **Account · Account no. · Holder · Code · Feed · Record begins** — the day its record began, blank for one held from the book's opening |
| What a line is | **Sector · Region · Held as · Funding** — how IG funds a contract, daily or dated |
| A deal's own terms | **Trade ID · Broker ref · Deal ccy · Stake (£/pt) · Level (points) · Entry level (points) · Exit level (points) · Trade value (GBP)** |
| When | **Date · As at · Exit date · Days held · Age (days) · Quarter** |
| Money and measures | **Cost (GBP) · Value (GBP) · Proceeds (GBP) · Amount (GBP) · Weight · % of book · Market exposure · Capital employed · Capital growth · Income · Return · YTD return · Gain · Contribution** |
| A round trip, and a company life | **Closed out · State · Dividends (GBP) · Funding interest (GBP) · Life gain (GBP) · Life gain (%) · Life cost per share · Round trips · Lines** |
| Against the broker | **Difference · Verdict · Last broker check · Document · Cash / Funds (GBP) · Read from · FX rate as at** |
| A mark, and a window from one to the next | **Mark key** — a share's ticker, or a bet's contract · **Quality · Stale · Priced · Was priced · Value now (GBP) · Change (GBP)** |
| The refresh grid | **Was · Was as at · New · New as at · From · Take** |
| The journal | **Recorded · Route · Did · Table · Rows · Retrieves** |
| Where a figure came from | **Source · FX at trade · FX from · Notes** |
| The judgement | **Why · Research notes** |
| Who opens the hosted desk | **Reader · Level · Since · Devices · Last signed in · Now · Device · Enrolled · Last used · At · Result · Address · Named as** |
| A currency as a category, on the Dashboard | **Currency** |
| What happened, on a capital movement, an income row, a write or a sign-in | **Detail**; a row's detail link opens in `DETAIL`'s order (`kit.js`) |

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

## 5b · The book's concepts

Words for what the record holds, which a reader meets in prose and page names rather than as
column headings.

### What a sale closes

| Concept | Canonical | Note |
|---|---|---|
| One buy row in the ledger | **Leg** | [the store](store.md) |
| One account's shares in one ticker, at their average cost | **Pool** | an emptied pool bought again is a new one |
| A spread bet counted in the company's shares: stake × points per unit × rate per pound on the deal date × shares per unit | **Share-equivalent** | how a company row adds a bet to shares |
| What a sale took off the cost held | **Cost released** | a pool's average for a share; the leg's cost for a spread bet |
| Everything sold out of one holding | **Realisation** | headed **Realisation ID**; [the store](store.md) |
| A realisation seen whole, entry to exit | **Round trip** | the Round Trips page |
| A company's shares and bets, first purchase to the day nothing is held | **Company life** | Round Trips, by company life |
| A life's realised gain, unrealised gain, dividends and funding interest together | **Life gain** | |
| (cost of what is held − realised − dividends − funding interest) ÷ quantity, bets as share-equivalents | **Life cost per share** | the break-even price; not the pool's cost |
| Shares at cost, spread bets at notional (stake × level) when entered | **Exposure at entry** | every gain %'s denominator |
| Every buy and sale on file | **Trades** | the Trades page |

### Running a refresh

| Concept | Canonical | Note |
|---|---|---|
| The screen a refresh is run from | **Price Refresh** | |
| One pass over the feeds for every mark, written nowhere | **Sweep** | `feeds/refresh.py` |
| A mark kept in its history before it is replaced | **Banked** | |
| A mark left at its last level by decision, with the reason on the row | **Carried** | not *unpriced*; `rules.STATEMENT_PRICED`, and for a rate `rate_carried` |
| A figure a feed returned | **Fetched** | |
| A figure read off a filed broker document | **Filed** | |
| A line the sweep could not price | **Unpriced** | the reason on hover |
| A rate entered by hand | **Typed** | the only thing typed |

### What the book learned, and when

| Concept | Canonical | Note |
|---|---|---|
| The table of every write to the record | **The journal** | [the store](store.md) |
| Who made a write | **Route** | §9 |
| What it did to the row count | **Op** — `open` · `append` · `replace` · `remove` | |
| The row a table's journal opens with | **The opening count** | `route=baseline, op=open` |
| A row that arrived by no journalled route | **Unaccounted** | `portfusion record` counts them: a finding, not a failure |

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
| Which desk columns wear movement colour | `MOVEMENTCOL` in `kit.js` |
| Currency, region, sector, ticker | open: a new one is not refused, and the Bench offers those in use |

---

<!-- BEGIN DERIVED — generated by glossary.py; do not edit between the markers -->

## 9 · The record's own words, generated

**Everything below this line is DERIVED from the `record/` modules,
`house/headings.py` and `Book.HEADLINE` by `tools/glossary.py`, and
`tests/record/test_record.py` asserts that the checked-in file matches what those constants
produce.** It cannot drift. It is an INDEX — names, values and where they live. What a
word MEANS stays where it is defined, and `test_record.py` refuses this block if it
starts to define one.

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
| Return since the day the record begins (MWR) | `capital` | pct | **no — live only** |
| Return this quarter | `capital` | pct | **yes — the report only** |
| Open positions | `count` | count | yes |
| Accounts / positions | `count` | count | **yes — the report only** |
| Closed round trips | `count` | count | **no — live only** |

### Vocabularies declared to the LOADER

A value outside these fails **on load**, naming the table, the row and the column.

| Column | Values | Tables |
|---|---|---|
| `held_as` | `shares` · `spread bet` | `securities` · `accounts` |
| `category` | `Dividend` · `Funding interest` · `Cash interest` · `Fee` | `income` |
| `contribution` | `positions at market` · `account equity` · `notional` | `quarter-nav` |
| `quality` | `sourced` · `derived` | `quarter-nav` · `quarter-snapshots` |
| `struck` | `close` · `live` | `fx` · `current-prices` |
| `key` | `record_begins` · `reasoning_owed_from` · `first_report` · `rate_carried` · `hosted_origin` · `passkey_domain` · `deploy_repo` · `research_repo` · `insights_url` · `practice` | `settings` |
| `funding` | `daily` · `dated` | `contracts` |
| `route` | `baseline` · `bench` · `marks` · `freeze` · `hand` · `migrate` | `journal` |
| `op` | `open` · `append` · `replace` · `remove` | `journal` |
| `table` | the 18 record tables | `journal` |

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

| Table | What it holds | Columns, as the desk heads them |
|---|---|---|
| `account-readings.csv` | What the book holds each account to be worth RIGHT NOW, and the observation it rests on | `account` Account · `as_of` As at · `at` · `positions` · `funds` · `running_pl` · `equity` · `deposit` · `available` · `evidence` Document kind · `reference` Reference |
| `accounts.csv` | The account register | `account` Account · `holder` Holder · `broker_firm` Broker firm · `number` Account no. · `code` Code · `held_as` Held as · `feed_key` Feed · `record_begins` Record begins |
| `buys.csv` | THE LEDGER — one row per buy leg | `trade_id` Trade ID · `date` Date · `source` Source · `account` Account · `ticker` Ticker · `cur` Deal ccy · `qty` Quantity · `stake` Stake (£/pt) · `cost` Cost (GBP) · `level_points` Level (points) · `broker_ref` Broker ref · `note` Notes · `contract` IG contract · `traded_price` Traded price · `rate` Rate (per £1) |
| `capital-movements.csv` | External capital in and out, one row per event | `date` Date · `account` Account · `amount` Amount (GBP) · `source` Source · `detail` Detail |
| `cash-readings.csv` | HOW MUCH CASH A SHARE ACCOUNT HELD, AND WHEN: THE RECORD'S ONE PLACE FOR CASH | `account` Account · `as_of` As at · `cash` Cash (GBP) · `evidence` Document kind · `reference` Reference |
| `companies.csv` | One row per ISSUER — the company, not the holding | `company` Company · `sector` Sector · `region` Region |
| `contracts.csv` | One row per IG contract a spread-bet leg names, with the epic that prices it, how IG funds it, and the ticker of the line it is on | `contract` IG contract · `epic` Epic · `funding` Funding · `ticker` Ticker |
| `current-prices.csv` | What things are worth NOW — never what was paid, which is the ledger | `mark_key` Mark key · `price` Price · `currency` Ccy · `as_of` As at · `source` Source · `struck` · `at` |
| `fx.csv` | The rate each currency is converted at NOW, one row per currency, as current-prices.csv holds what each line is worth now: replaced at every refresh, banked into fx-history.csv first | `currency` Ccy · `rate` Rate (per £1) · `as_of` As at · `source` Source · `struck` |
| `income.csv` | Dividends, interest and fees | `date` Date · `account` Account · `category` Category · `detail` Detail · `amount` Amount (GBP) · `source` Source · `note` Notes · `currency` Ccy · `local_amount` Amount · `rate` Rate (per £1) · `ticker` Ticker |
| `journal.csv` | RECORD TIME — when the book LEARNED a thing, as against when the thing HAPPENED | `at` Recorded · `route` Route · `op` Did · `table` Table · `rows` Rows · `ref` Retrieves · `detail` Detail |
| `quarter-nav.csv` | Each account's CONTRIBUTION to net asset value at each quarter end | `as_of` As at · `account` Account · `amount` Amount (GBP) · `contribution` Contribution · `quality` Quality · `source` Source |
| `quarter-results.csv` | Each closed quarter's six figures, for the book and for each account, as the engine gave them — what a closed quarter is HELD TO, never what a renderer shows | `as_of` As at · `account` Account · `opening_nav` Opening NAV · `capital_deployed` Capital deployed · `return_income` Income · `closing_nav` Closing NAV · `gain` Gain · `return` Return · `note` Notes |
| `quarter-snapshots.csv` | Every account's HOLDINGS, line by line, at each quarter end — the working behind quarter-nav.csv's per-account totals | `as_of` As at · `account` Account · `ticker` Ticker · `qty` Quantity · `price` Price · `currency` Ccy · `value` Value (GBP) · `cost` Cost (GBP) · `quality` Quality · `source` Source |
| `reasoning.csv` | WHY a position was taken and why it was closed — one row per DECISION: the ticker, the date of the trade or sale it explains, and the why | `ticker` Ticker · `date` Date · `why_entered` Why we entered · `why_exited` Why we exited |
| `research-notes.csv` | WHICH RESEARCH NOTES COVER WHICH INSTRUMENT | `ticker` Ticker · `ref` · `published` · `url` |
| `sales.csv` | One row per sale | `sale_id` Sale ID · `date` Date · `account` Account · `ticker` Ticker · `qty` Quantity · `stake` Stake (£/pt) · `traded_price` Traded price · `cur` Deal ccy · `rate` Rate (per £1) · `proceeds` Proceeds (GBP) · `source` Source · `broker_ref` Broker ref · `realisation_id` Realisation ID · `closes` Closes trade · `note` Notes |
| `securities.csv` | One row per CODE held, reserved or closed | `ticker` Ticker · `company` Company · `held_as` Held as · `currency` Ccy · `symbol` Symbol · `quote_unit` Quote unit · `points_per_unit` Points per unit · `shares_per_unit` Shares per unit |
| `settings.csv` | The book's own settings: one row per key in SETTING_KEYS | `key` · `value` |

<!-- END DERIVED -->

---

## Changing a word

A word changes here and in its declaration in the same commit, and §9 is regenerated:

```bash
python3 tools/glossary.py --write
```
