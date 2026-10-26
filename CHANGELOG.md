# Changelog

Each release, newest first. The version is `portfusion/__init__.py`'s, and `portfusion --version`
prints it.

## Unreleased

- **The FX history keeps every rate.** A bank dropped the live rates read between the days the
  book is valued on, but What Changed sets a share line against the rate of the day before its
  mark, which may be one of them: a refresh could move a line's FX effect. 0.2.1's "No figure
  moves" held for the price history only. The file now grows by a row per currency for each day
  a refresh reads; a rate a bank already dropped stays in git, not in the file.
- **Every desk read is the desk's one Book.** The Price Refresh's "Was" column is read from it,
  so the first load after a hand edit, a pull or a checkout no longer shows the marks the store
  held before. A quarter's report is drawn from it under the record's lock, so a record that
  refuses to reload refuses the report too, rather than serving the tables it refused. The
  Bench's reasons and the IG event sweep read the same Book.
- **A failed write puts the files back, however it fails.** The write envelope, and the reload of
  the record after it, caught every exception but `SystemExit`, which the record raises when a
  store goes incomplete; a write that ended that way left its files half-written. The Price
  Refresh's write reloads the record after its envelope too, as each door's does.
- **The record's seven load checks hold under `python -O`.** They were `assert`s, which `-O`
  strips: a settings key named twice, a spread-bet leg with no contract or on another line, an id
  used twice, a price in a third currency, an income category in neither half, an account code
  repeated or malformed. Each is now refused with a `ValueError`.
- **Publish keeps to its own clone.** It refuses a `deploy_repo` that is, holds or lies inside the
  book, the app or the checkout, or is or holds the home folder, and a clone that tracks files
  but has no version manifest: a publish deletes what it did not write.
- **The audit tells the truth.** `portfusion record` typed in a checkout reported the checkout's
  backup under the book's name; it now reads the book's own git. An evidence chain or journal that
  could not be checked read as good order; each is now a problem, as the conversions' was. The
  three opening dates in settings (`record_begins`, `reasoning_owed_from`, `first_report`) are
  refused on load unless each is a date, and the first is read once; `engine.BASELINE` and
  `BASELINE_ASOF` are gone, a Book's `baseline` answers.
- **Each Book names its own "Return since" date.** The label was fixed when the app started, so a
  desk running when `record_begins` changed showed the old date until restarted, and a Book of
  another store showed the loaded book's. A Book now reads it from its own record, as the registry
  of headline figures does.
- **The PDF reader is pypdf 6.21.2**, locked and floored: 6.16.2 had 19 advisories, each a crafted
  PDF that could hang the desk. The guard on GitHub now asks OSV about every locked pin
  (`tools/advisories.py`) and fails on any advisory.
- **The floors are versions the suite runs on**: pytest 8.4 (8.0–8.3 cannot load the harness),
  fastapi 0.133 (an older one brings a Starlette whose test client needs `httpx`), pandas 2.2.3
  (2.2.0–2.2.2 do not install on Python 3.13).
- **The guard on GitHub checks the desk's script parses** (`node --check`). A syntax error in
  `app.js` blanks the desk, and every test that reads the file passed over one.
- **A checkout names the demo.** CONTRIBUTING's setup, CLAUDE.md and the testing guide start with
  `export PORTFUSION_BOOK=demo`, so their commands work first time in a checkout, which holds no
  book. Run without one, the suite says so in one line rather than a page of `INTERNALERROR`.
- **The stability rules are in CONTRIBUTING**: 22 rules under six headings, each beside the test
  or hook that holds it, and eight parts not yet held marked "being made to fire". The conventions
  follow, one line each; "run the guard unpiped" is a tip in docs/testing.md.
- **The import contracts are checked by a tool**, import-linter (`lint-imports`), in CI and in a
  checkout's pre-commit: seven contracts in `pyproject.toml` say which part of the app may import
  which. The build's independence of the desk, the feeds and the histories (rule 21) is now held
  for the record too, where a planted import passed every test; CI plants one to prove it is
  refused. Ten hand-written import tests and two fixtures retire, and three tests lose their
  import half. A dev tool only: a book installs none of it.
- **Six guards that passed on the code they forbid now fail on it**, each beside a planted case:
  no credential is logged, in either feed, as well as printed; a panel's copy of a shaping helper
  is found by the names `_shape.py` defines; a negative quantity with a value is read from `qty`
  (it read `stake`); a name taken from the record's rules, or a path the schema rebinds, is
  refused; the engine's case of the lock test waits on `book()`'s own lock; and **a skip a book
  lists that ran fails the run**. When a book's pin moves, delete any such line from its
  `checks/skips.txt`; the demo's one is gone.
- **Every label the report prints is registered.** "Return this quarter" and "Accounts / positions"
  join `Book.HEADLINE`, marked as the report's only (`report_only`), and the engine gives both, so
  the report no longer counts the accounts itself. The registry's test reads the labels from the
  drawn page, where it read the data and missed both. Nothing on the desk or the report moves.
- **One census of every writer in the package.** The scan that names each module allowed to
  write now walks the whole package, not `desk/` alone, and counts a removal, a copy and a rename
  as writes. Six writers outside `desk/` are named: the two feeds' sign-in files, the histories'
  bank, `init`, the migrations and the schema's unused `dump()`. The store's doors are counted
  by what each opens, so the Bench's commit, research notes, `init`, the stamp and the demo
  generator are listed. Eight hand scans share one helper; four tests that only repeated the
  census are gone. `Naming.rename()` is `Naming.apply()`, so a path's `rename()` counts.
- **The guard on GitHub draws every desk page.** `tools/desk_smoke.py` asks the demo desk for its
  page, script and panels with no server; `tools/desk_smoke.mjs` loads them into jsdom and opens
  each tab, failing on any error, rejected promise, error box or unanswered fetch, at start-up and
  on each page. A misspelt name crashes a page yet passes `node --check` and every test that reads
  the script; CI plants one at start-up to prove it is refused. jsdom is pinned in
  `tools/package-lock.json`, which the advisory check and Dependabot now read too. A dev tool
  only: a book installs none of it.
- **The record is built, then taken.** `record/rules.py` read each table into the module as it
  went, so a reload the record refused — a store caught mid-edit, a bad cell — left the refused
  tables beside the old ones, a record no store ever held, until a reload passed. It now reads
  and checks every table into names of its own and the module takes them only when the whole
  build has passed, so a refused reload leaves the record exactly as it was. A Book's pin holds
  for the record's functions too: a leg's kind and the accounts open on a day answer from the
  record the Book was built from. No figure, page or store moves.
- **A price or rate history that cannot be read no longer blocks an account reading.** The
  readings door asked the marks door whether its outgoing readings were banked, and the marks door
  read all three histories to answer, so a broken price or FX history refused a reading it had no
  part in. Each door now asks its own history: an account reading, from the Price Refresh or filed
  with a holdings export, waits only on the account history. The desk's two panels that acted now
  only shape: the Price Refresh's write is the marks door's `refresh()`, and the sweeps the desk
  asks of the feeds are `desk/intake/sweep.py`'s. No figure, page or store moves.
- **The quarter close is an action: `portfusion freeze <quarter end>`**, and `--write` writes it.
  The audit's close procedure and the report gate's refusal name it. `--book` reaches every
  command run as `python3 -m portfusion.<command>`: `python3 -m portfusion.record --book demo` was
  refused as an unrecognised argument. `portfusion --help` lists all fifteen commands: the seven actions, and
  the eight reached by `python3 -m` alone. `python3 -m portfusion.desk.doors.freeze` still works.
- **The engine is a package.** `engine.py` is `engine/`, a file per topic: the store, the two
  bases, the ledger and valuation, then `Book`, built from seven classes, each a group of its
  methods, over the construction they share (`engine/core.py`). `portfusion.engine` offers every
  name it did, `Book.HEADLINE` stays the one registry, and an import contract keeps the topics
  from importing one another. pyright now checks the store, the bases, the ledger and valuation.
  No figure, page or store moves.
- **A hosted reader sees a fixed sentence, not a 500, when the record will not load.** The remote
  door answered 500 at every level, or handed an owner the record's own words, which name the
  Mac's folders; it now tells every reader "the record on the Mac will not load: see the Mac's
  desk". A refusal's words are renamed for a level that reads no names, as its answers are. A
  desk with a hosted door now starts when a cell will not load: the door reads its two settings
  alone.
- **A revoke that races a sign-in holds.** The sign-in wrote back the passkeys it had read, so a
  device revoked part-way through came back, signed in. The passkeys, the readers and the sessions
  in memory now change under one lock, and a session opens only while its passkey is on file. A
  restart's exit waits for a write in progress to finish, as every door's write does.
- **A document is never filed over another.** A commit files a document under its convention's
  name, or that name with the item's id when the first is taken; when both are, the commit is now
  refused and nothing is written, where the document on file was replaced. A TradingView reply
  that answers nothing now fails only its own line, where it stopped the whole sweep.
  `python3 -m portfusion.history.fx --rate` without a currency and a date says how it is used,
  where it crashed.
- **A desk request that fails says so.** A Bench button whose answer was not the desk's JSON
  (opening a new item, saving, reading, writing, withdrawing) left an empty box, or no item; each
  now shows the server's words. An action the desk refused (a write not yet enabled, say) no
  longer reads as done. The page last asked for is the one drawn: a slow page no longer draws
  over a quicker one opened after it. The page open in the rail is marked as the current page
  for a screen reader, each result box is read out as it fills, and a read-only figure shows its
  focus ring. Trades' filters redraw the page, as Holdings' and Round Trips' do.

## 0.3.2 — beta, 24 Oct 2026

The whole suite runs clean on a book of its own, not only on the demo. Nothing in the app moves.

- **The IG reading check strikes a contract the reading's account holds.** On a book with two
  IG accounts, it had struck the other account's.
- **The ii ledger's test reads against a register of its own**, as it stubs the rest of the
  record, so a dividend's ticker is the same whichever book is loaded.
- **A test of the demo's own documents skips on another book without failing its run**: like a
  test that reads the checkout, no book lists it (`tests/harness.py`, `DEMO_ONLY`).

## 0.3.1 — beta, 24 Oct 2026

The restructure's last loose ends. A 0.3.0 book takes it with nothing to move, unless a
quarter's results name an account its register no longer holds: the load names the row.

- **A quarter's results name an account the register holds, or none.** `quarter-results.account`
  is checked against `accounts.csv` as every other account column is; a blank, the book's own
  row, is the one value outside the register that loads.
- **The audit asks that every source line was composed by an evidence class.** `portfusion
  record` holds a book to it, as the suite holds the demo.
- **The FX history is saved in date order**, then currency, as the price history is saved by
  date, then line. A book's file takes the order at its next bank; no row or figure changes.
- **The test guard says when the app is not installed**, rather than failing before it can
  refuse.

## 0.3.0 — beta, 24 Oct 2026

The clean break. This release carries no 0.2.0 book: one takes 0.2.1 first and runs
`portfusion migrate --write` there, then takes this.

- **The moves that carried a 0.2.0 book are retired**, with their tests. `portfusion migrate`
  stays, for the next release that changes the store, held by tests on moves of their own; with
  nothing declared it finds nothing to move.
- **A refusal states its rule alone.** A journal instant without its `Z`, a table out of date
  order and a sum of money not written to the penny no longer send a book to `portfusion migrate`.
- **A holdings item's reading is read by its own names**, `cash` and `total`.

## 0.2.1 — beta, 24 Oct 2026

The stepping stone. A 0.2.0 book takes this release and runs `portfusion migrate --write` before
it takes 0.3.0, which will not carry a 0.2.0 book's store.

- **An IG reading is one pass with its marks only until they are struck again.** A level struck
  later on the reading's own day takes the place of the one it was read with, so the reading reads
  `struck-apart` rather than a difference that was never there.
- **An ii dividend arrives knowing its line (#39).** The ii reader reads a line's description before
  its Symbol, so a dividend, which names its security as a deal does, is proposed rather than
  reported as a dealing line, with the book's ticker for its Symbol; blank where the book
  registers none.
- **A history keeps only the marks a figure can take.** The price and FX histories keep every
  close, each line's mark at every quarter end, opening and account reading, and its two newest;
  a live read between them leaves at the next bank, and git keeps what it said. No figure moves.
- **A quarter's net asset value is tied to its own day's statement** where its row says it was
  copied from one, not to the latest before it where the journal says the freeze did not write it.
- **A book can begin on any day (#7).** `portfusion init --begins` takes a day as well as a year.
  The year to date, the year to each quarter and the return since the start measure from the
  record's opening in the year it began, and its first quarter from that opening, named for it:
  "Q2 2026, from 17 May" on the desk and the report, whose gate asks for that opening. A record
  that begins on another day than 1 January is no longer refused.
- **An account can open after the book does.** The register's `record_begins` is the day an
  account's record began, blank for one held from the book's opening. Before it the account holds
  nothing, whatever deal dates the statement it opened at carries, and the freeze writes no row
  for it. A quarter end before it holds no row for it (the loader refuses one) and needs no
  statement of it, so the 0.00 rows and statements that stood in for it go; a quarter's income
  table lists only the accounts open by its end. `portfusion migrate` adds the column, blank; an
  account opened later is dated by hand, with those rows removed, since only their prose says
  which they were.
- **A spread bet is priced by its contract, and the journal keeps one clock.** A mark under a
  bet's ticker is refused, and the engine's fall-back to one, from before each contract had a
  key, is retired. A journal instant without its `Z` is refused; `portfusion migrate` writes a
  book's older ones, and the Bench items they tie to, in UTC.
- **A book's folder and its research notes are held by PortFusion.** The audit asks that a book
  holds every file `portfusion init` writes, with the release's hooks and ignore list, that every
  filed document is named as the record reads it, and that its research-notes rows agree with
  the research repo it names, every published note on a held company on file.
  `portfusion init --push-on-commit` writes a hook that pushes each commit as it lands.
- **Every row naming a document is held to its class's one format**, in buys, sales, income,
  capital movements and the statement history: a trade's line its document's kind and date, every
  other its class's template.
- **Money is written to the penny, a quote to at most six places.** Every figure column declares
  its places in the schema, every writer writes figures one way, and the loader refuses a sum of
  money not written to exactly two places or a price, rate or level written to more than six. A
  typed figure is written as it will read back: "0" becomes "0.00". `portfusion migrate` rewrites
  a book's money to the penny; no value moves.
- **A share account's cash is in one place, its cash readings.** An account reading's `recon_cash`
  and `stmt_value` and a statement's `cash` are retired: a reading off a document that states the
  cash writes it as a cash reading of its day, in the same write, and the reading's total is its
  stock plus that cash. The Accounts page's cash now reads one place. `portfusion migrate` moves
  each figure across, reading a statement's class and reference back out of its source.
- **A correction replaces its row.** A mark, a rate or a statement read again on its own day takes
  its row's place, and a restated quarter end replaces its rows and results, the journal saying
  why; git keeps what each row said. The `status` column five tables carried to keep a corrected
  row beside its replacement is retired, with the Holdings mark history's struck-through marks,
  and the loader refuses a quarter end written twice. `portfusion migrate` drops the column and
  any row it marked superseded.
- **Two tables retire: `closed-positions` and `baseline-reconstruction`.** A round trip's entry
  date and note come from its own buys and sales, which already said what the first table did, and
  nothing read the second. `portfusion migrate` removes both files and the journal rows that name
  them.
- **On Trades, a sale's ID is headed Sale ID.** A row's detail read a sale's ID as its Trade ID;
  a buy's keeps Trade ID. Inside the engine, the ledger takes the store's names (#44): `event_id`
  for either side's ID, a buy's `cost` or `level_points`, a sale's `proceeds` and each side's
  `traded_price`. No figure moves.
- **The record reads as it happened, and a buy's or a sale's id is its place.** Every event table
  is in date order, then the account's place in the register, then ticker. A row entered late goes
  where its date puts it, and the buys or sales after it are renumbered, a sale's `closes` and an
  id a note quotes following; the Bench's review names the ids that move before the press. The
  loader refuses a table out of order or an id not its place, and `portfusion migrate` sorts and
  renumbers a book, journalling what it moved under a new `migrate` route. `settings.csv`'s
  `trade_id_floor` and the letter suffixes of a fill in several legs are retired.
- **A new book passes its own audit**: the change-totals audit asks only of the kinds a book
  holds, and the price-feed audit waits for a book's first prices.
- **The journal's opening boundary is tested on any book**: a book with no rows written before
  its journal opened, a new one included, no longer fails the audit.
- **`portfusion migrate` carries a book to this release's store** (#12): it shows the first move
  a book needs, and on `--write` makes every one, then opens the book and audits it, and puts
  every file back if either fails. Moves are declared in `record/migrations.py`. It never commits.
  **Make this section's by-hand moves first**: `--write` puts back a book that will not open. The
  README's [*Taking a new release*](README.md#taking-a-new-release) now forces the install, since
  two commits can share a version, and migrates before the guard; a new book's requirements.txt
  points there.
- **One name for one idea, from the store to the desk** (#43). The store's names are the desk's,
  and the suite refuses a heading the [glossary](docs/glossary.md) has not agreed or a column with
  no heading. `portfusion migrate` moves a book's store:
  - tables: `trades` → `buys`, `exits` → `sales`, `issuers` → `companies`, `account-observations`
    → `account-readings`, `cash-observations` → `cash-readings`; the journal's `table` and the
    Bench archive's keys follow;
  - columns: `securities.code` → `ticker`; `kind` → `held_as`; `accounts.broker` →
    `broker_firm`; `buys.id` → `trade_id`; `sales.eid` → `sale_id`; `sales.realisation` →
    `realisation_id`; `price` on buys and sales → `traded_price`; quarter-snapshots'
    `local_price`, `gbp_value`, `gbp_cost` → `price`, `value`, `cost`; `ticker` on current-prices
    and price-history → `mark_key`, a share's ticker or a bet's contract; an archived Bench
    item's `marks` follow;
  - `buys.val` splits by the line's `held_as` into `cost` (a share) and `level_points` (a bet).

  On the desk: a deal's `cur` is headed Deal ccy, and What Changed and Price Refresh head a mark's
  key Mark key, not Line. The report's figures do not change.
- **Round Trips reads by company life**: a company's shares and bets from first purchase to the
  day nothing is held, with dividends, funding interest, a life cost per share and a life gain %
  over exposure at entry. The quarterly report does not change.
- **`income.csv` gains `ticker`.** **A book's rows move by hand:** add `,ticker` to the header and
  each row, and give each dividend its line's ticker.
- **A company held both ways reads as one position.** Grouped by company, Holdings gives each row
  its quantity in shares, a spread bet counted as share-equivalents (stake per point × points per
  unit × its currency's rate per pound on the deal date × shares per unit), its entry price as the
  mean over shares and share-equivalents in the share listing's currency, the listing's current
  price, and that currency, stated. A company held only as bets is priced from the bets' own marks.
  The audit names a held bet line with no points per unit, and each bet deal date owed a close.
- **`securities.csv`: `tv_symbol` and `tv_unit` become `symbol` and `quote_unit`, and it gains
  `points_per_unit` and `shares_per_unit`.** A symbol is the market's ISO code and the ticker as
  that market spells it (`XLON:BRYC`, `XNYS:VELD`); the price feed translates.
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
  contract, and the Bench suggests every ticker in the register.
- **`contracts.csv` gains `ticker`**, the line each contract is on, and the sweep reads a bet's
  ticker from it. **A book's rows move by hand:** add `,ticker` to the header, and to each row the
  ticker its legs carry in `buys.csv` (`trades.csv` before migrating). Every leg on a contract
  must be on that contract's line.
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
