# Changelog

Each release, newest first. The version is `portfusion/__init__.py`'s, and `portfusion --version`
prints it.

## Unreleased

- **A new book passes its own audit**: the change-totals audit asks only of the kinds a book
  holds, and the price-feed audit waits for a book's first prices.
- **The journal's opening boundary is tested on any book**: a book with no rows written before
  its journal opened, a new one included, no longer fails the audit.
- **`portfusion migrate` carries a book to this release's store** (#12): it shows every move,
  and on `--write` makes it, opens the book and audits it, and puts every file back if either
  fails. Moves are declared in `record/migrations.py`. It never commits. The README's *Taking a
  new release* now forces the install, since two commits can share a version, and migrates before
  the guard; a new book's requirements.txt points there.
- **One name for one idea, from the store to the desk** (#43). The store's names are the desk's,
  and the suite refuses a heading the glossary has not agreed or a column with no heading.
  `portfusion migrate` moves a book's store:
  - tables: `trades` → `buys`, `exits` → `sales`, `closed-positions` → `realisations`, `issuers`
    → `companies`, `account-observations` → `account-readings`, `cash-observations` →
    `cash-readings`; the journal's `table` and the Bench archive's keys follow;
  - columns: `securities.code` and `contracts.code` → `ticker`; `kind` → `held_as`;
    `accounts.broker` → `broker_firm`; `buys.id` → `trade_id`; `sales.eid` → `sale_id`;
    `realisation` → `realisation_id`; `price` on buys and sales → `traded_price`;
    `realisations.open_date` → `opened`; `baseline-reconstruction.fx` → `rate`;
    quarter-snapshots' `local_price`, `gbp_value`, `gbp_cost` → `price`, `value`, `cost`;
    `ticker` on current-prices and price-history → `mark_key`, a share's ticker or a bet's
    contract; an archived Bench item's `marks` follow;
  - `buys.val` splits by the line's `held_as` into `cost` (a share) and `level_points` (a bet).

  On the desk: Unrealised gain, Funding interest, Quantity and Life cost per share replace Gain to
  date, Funding, Held and Net cost per share on Round Trips by company life; a deal's `cur` is
  headed Deal ccy; What Changed and Price Refresh head a mark's key Mark key, not Line. The
  report's figures do not change.
- **Round Trips reads by company life**: a company's shares and bets from first purchase to the
  day nothing is held, with dividends, daily funding, a net cost per share and a gain % over
  exposure at entry. The quarterly report does not change.
- **`income.csv` gains `ticker`.** A book's rows move by hand: add `,ticker` to the header and
  each row, and give each dividend its line's code.
- **A company held both ways reads as one position.** Grouped by company, Holdings gives each row
  its quantity in shares, a spread bet counted as share-equivalents (stake per point × points per
  unit × its currency's rate per pound on the deal date × shares per unit), its entry price as the
  mean over shares and share-equivalents in the share listing's currency, the listing's current
  price, and that currency, stated. A company held only as bets is priced from the bets' own marks.
  The audit names a held bet line with no points per unit, and each bet deal date owed a close.
- **`securities.csv`: `tv_symbol` and `tv_unit` become `symbol` and `quote_unit`, and it gains
  `points_per_unit` and `shares_per_unit`.** A symbol is the market's ISO code and the ticker as
  that market spells it (`XLON:BRYC`, `XNYS:VELD`, `XCSE:HALD B`); the price feed translates.
  **A book's rows move by hand:** rename the two headers and add the two new ones at the end;
  rewrite each symbol's market (`LSE`→`XLON`, `NYSE`→`XNYS`, `NASDAQ`→`XNAS`, `XETR` stays,
  `OMXCOP`→`XCSE`, `OMXSTO`→`XSTO`) and an underscore in a ticker as the market's space; give
  every spread-bet line its points per unit, and a shares per unit only where its listing is a
  receipt for other than one share.
- **A share sold out of every account stops being priced.** The sale that empties it banks its
  live price and takes it out of `current-prices.csv` in the same write, and the Bench's review
  says so before the press. The audit names any live price on a line nothing holds.
- **A document is read from the workbench by its bare name only.** `read_document.extract()` no
  longer reads an absolute path, which every route a browser reaches had to refuse for it; code
  that holds a path, such as a book's own check reading its archive, calls
  `read_document.extract_file(path)`.
- **A refused passkey is not described to the caller.** The door says the passkey was not
  accepted; the passkey library's reason goes to the sign-in log only.
- **A practice book's journal accounts for its practice setting**, so a new practice book passes
  its own audit.
- **The guard holds what leaves to a book's holdings**, not only its people and accounts:
  `tests/test_what_leaves.py` reads the loaded book and checks the checkout's files, the commits
  not yet on `main` and the branch's name. A push from a checkout runs it on the book
  `PORTFUSION_BOOK` names, and refuses one that names it.
- **A first bet on a new contract is set up from the IG sweep.** The sweep offers it with its
  epic; the Bench takes its line, company and contract with the trade, reads the contract's first
  mark from IG, and writes all of them together. Any item can add a new line, company or
  contract, and the Bench suggests every code in the register.
- **`contracts.csv` gains `code`**, the line each contract is on, and the sweep reads a bet's
  ticker from it. **A book's rows move by hand:** add `,code` to the header, and to each row the
  ticker its legs carry in `trades.csv`. Every leg on a contract must be on that contract's line.
- **The report's footer names the commit an installed build came from**, as `release()` does.

## 0.2.0 — beta, 21 Oct 2026

The first public release: the app and the demo book, apart from any book that uses them.

- **The record**: a book's facts as CSV files, typed on load by one schema, held to the record's
  rules, and written only through the desk's doors, each write journalled.
- **The engine**: every figure derived once, from the record alone.
- **The desk**: the browser app, with the Bench, where a document is read onto the record and a
  person approves each row, and the Price Refresh, where marks are fetched and reviewed.
- **The report**: the quarterly report, from the same engine.
- **The feeds**: IG and TradingView, read-only.
- **`portfusion init`**: a new book's folder, its git history, its secret gate, the guard on its
  `main` and the release it runs; `--practice` copies the demo.
- **`portfusion check`**: the guard, shipped with the app and run on any book.

### Known limits

What 0.2 does not do yet, or does one way only. Each is open to an issue.

- **A PDF is read by a Claude session, not by the desk.** A session reads the document and
  hands its figures to `python3 -m portfusion.desk.intake.propose`, which checks every figure
  against the document's own text before the Bench shows it. Without Claude Code, a contract
  note or statement in PDF cannot be put on the Bench. A broker's CSV export is read on the
  machine.
- **Three brokers.** The record knows the documents of interactive investor, Hargreaves
  Lansdown and IG. Another broker needs its kinds of document added
  (`record/rules_evidence.py`) and, for a CSV, a reader.
- **Spread bets are IG's.** A bet is held as IG states it: a stake per point, levels in points,
  each leg on an IG contract, funded daily or dated, and an account's five figures under IG's
  names. A second spread-bet broker would need that model widened.
- **Prices come from TradingView and IG.** TradingView needs an account
  (`python3 -m portfusion.feeds.tv --tv-sign-in`), and which lines are live, exiting or entering
  is read from three of its watchlists, named in the book's settings.
- **Sterling, and UK hours.** Every total is in pounds. A line in another currency is converted,
  and venue closes are kept in UK time for the currencies the code knows, with a default for
  the rest.
- **The record begins on 1 January.** The year's return is measured from the 31 December
  before it, so a book that begins mid-year is not yet supported.
- **Cash sits outside a share account's net asset value,** and there is no cash
  reconciliation: cash is a snapshot from the broker's documents, never a figure the book
  derives.
- **One return, money-weighted.** Each period's return is day-weighted Modified Dietz on net
  asset value. There is no time-weighted return and no benchmark.
- **No migration tool.** A release that changes a table's columns says how to move a book's rows,
  and the loader refuses the table, by name, until they are.
- **A quarter end is valued within seven days either side.** Each line takes its mark nearest
  the date (`rules.CLOSE_CHECK_WINDOW_DAYS`).
- **The report is quarterly,** and its format is not final. The year-end report is not built.
- **The desk runs on a Mac,** at desktop width, started at login by a LaunchAgent. The hosted
  desk needs a Tailscale Funnel, a Netlify site with its signed proxy, and passkeys. It has two
  reader levels, owner and principal.
- **The guard is strict about prose.** Comments and docstrings may not repeat an eight-word
  run beyond a count on file, and the desk's on-screen words have a cap. Both are ratchets, so
  cutting always passes and adding can fail.
