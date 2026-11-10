# The desk, walked cold

Where a person new to the desk stalls, and which pages are slow. Evidence only: no row is a
decision. Taken on 10 Nov 2026 at `1c61c41`, on a practice copy of the demo book, at 1440 × 900.

| | |
|---|---|
| The walker | one fresh agent given the twelve jobs and the desk's address; no code, no docs |
| Not pressed | "Fetch everything", "Sweep IG events", "Set up this bet": they leave the machine |
| Not completed | any write: the browser pane cancels the desk's "Write this to the record?" dialog |
| Timing | three runs each, in the browser, the desk on the same Mac |

## The jobs

| Job | In the owner's words | How often |
|---|---|---|
| 1 | My prices are stale. Bring them up to date. | weekly |
| 2 | One of my holdings paid a dividend. Record it. | monthly |
| 3 | A broker document is waiting. Get it onto the record. | monthly |
| 4 | What does the record need from me today? | every sitting |
| 5 | Does one account agree with its broker's statement? Reconcile it. | monthly |
| 6 | The book's value moved last quarter. Why? | quarterly |
| 7 | Show me one holding's history: bought, sold, received, worth now. | weekly |
| 8 | How has the book done since it began? | weekly |
| 9 | Which closed positions made and lost the most? | quarterly |
| 10 | What did I pay for one company, and when? | monthly |
| 11 | Get the latest quarter's report, ready to send. | quarterly |
| 12 | A figure on the dashboard looks wrong. Find how it is made. | occasional |

## Findings

| Class | Means |
|---|---|
| wording | the words on screen misled or were not understood |
| missing state | the page did not show something true that the job needed |
| layout | it was there, and not where it was looked for |
| speed | a wait |
| missing function | the page has no way to do it |

| Severity | Means |
|---|---|
| 3 | the job was abandoned |
| 2 | a wrong turn or a guess, then recovered |
| 1 | a pause |
| 0 | checked, and not a fault of the desk |

A screenshot is named for the first row it shows.

| # | Page | Job | What happened | Class | Severity | Cost to fix |
|---|---|---|---|---|---|---|
| 1 | Dashboard | 1 | "run a refresh" sits beside the prices' age. The walker could not tell whether it starts a fetch or opens a page, and did not press it. [shot](ux-audit/01.png) | wording | 1 | `reading.js` (the link, twice); no test |
| 2 | Dashboard | 2 | Nothing on the page or in the tabs says where a fact is added. "Bench" was a guess. [shot](ux-audit/01.png) | wording | 2 | a tab's title is its panel's one name: a rename is the panel file, its `DRAW`, two tests and the docs |
| 3 | Dashboard | 3, 4 | A document waiting in the inbox, and an item left Ready on the Bench, appear nowhere under "Needs attention". [shot](ux-audit/03.png) | missing state | 2 | `panels/dashboard.py`, `reading.js`; `test_panels.py` extended |
| 4 | Dashboard | 4 | The lines under "Needs attention" are not links. "reasoning owed … why we exited" names no page to write it on. [shot](ux-audit/03.png) | missing function | 2 | a finding is a sentence, shared with `portfusion record`: `engine/findings.py` gives each a page, then `panels/dashboard.py`, `reading.js`; two tests extended |
| 5 | Dashboard | 4 | Four lines carry a tag and seven do not. The walker could not tell whether the seven need anything; three restate a tagged line. [shot](ux-audit/03.png) | layout | 1 | `reading.js`, `app.css`; no test |
| 6 | Dashboard | 4 | Not understood: "(typed)", "band £40.70", "a LIVE read" of 41 days ago, "7 not on file", `_archive/statements/`. [shot](ux-audit/03.png) | wording | 1 | `engine/findings.py`, the same sentences the command line prints; the tests that pin them |
| 7 | Dashboard | 12 | A figure and its label do nothing when clicked or hovered. No figure leads to how it is made. [shot](ux-audit/01.png) | missing function | 2 | `reading.js`, `panels/method.py` and an anchor per figure; `test_panels.py` extended |
| 8 | Dashboard | 8 | "YTD return (MWR)" and "Return since 1 Jan 2026 (MWR)" show the same 36.54%; the year runs "from 31 Dec 2025" in one place and "since 1 Jan 2026" in the other; MWR is not spelled out. [shot](ux-audit/01.png) | wording | 1 | the same figure whenever the record began this year: `engine/book.py`, `test_figures.py`; the report moves with it |
| 9 | Dashboard | 9 | "Closed round trips 1", and Round Trips lists four rows under "Realisations 4 / Closed out 1". [shot](ux-audit/01.png) | wording | 1 | the label in `Book.HEADLINE`; `test_figures.py`; the report moves with it |
| 10 | Dashboard | 11 | "Total gain £3,292.53" here, "Capital growth £3,291.33" on Performance, "Gain +3,334" on the report. They agree: £1.20 of funding interest lowers net asset value and sits in income. Nothing says so. [shot](ux-audit/01.png) | wording | 2 | a line of the Method (`record/rules.py`), or a label and `test_figures.py` |
| 11 | Dashboard | all | The slowest page, at 0.22 s. Its findings are derived again on every request, and the first load asks for the shell before it asks for the page. Not slow on the demo's 189 rows; not measured on a larger book. | speed | 1 | `desk/engine.py` holds the findings for a store's mtime; one test |
| 12 | Dashboard | 1, 2 | The walker saw the last page stay up for 2 to 4 s after a tab was pressed, with no sign of loading. Not reproduced: every page paints in 5 to 230 ms. The browser pane runs the page as a hidden one. [shot](ux-audit/12.jpg) | speed | 0 | none |
| 13 | Bench | 2 | The item's own labels had to be decoded: "Evidence — statement-grade", "Authority that can be asked again", "Named reference that retrieves it". [shot](ux-audit/13.png) | wording | 2 | `bench.js`; no test |
| 14 | Bench | 2 | A dividend the owner knows of, with no file, cannot be recorded: "Blocked the reference retrieves it a ii-statement is retrieved by its FILE and none is on the bench." The kinds offered are broker documents only. The job was abandoned. [shot](ux-audit/14.jpg) | missing function | 3 | the rule is the record's (`docs/intake.md`, Never), so a decision before a file; saying it before the form is filled is `bench.js` |
| 15 | Bench | 2, 3 | No date field says its form. "30 Sep 2026" passes in "Dated" and an income "Date", and fails in a cash reading's "As at": "cash-readings.csv row 0, column 'as_of': Invalid isoformat string". "2026-09-30" was a guess. [shot](ux-audit/15.jpg) | wording | 2 | `desk/intake/bench.py` reads every row's date as `filing.py` reads the item's, `bench.js`; `test_bench.py` extended |
| 16 | Bench | 2 | An income row has two fields called "Amount", and "Ticker", which says what paid, comes last, after Notes. | layout | 1 | the form follows the table's column order: `bench.js`; no test |
| 17 | Bench | 2 | After tabbing from Account to Category, the Account list stayed open beside the Category list. | layout | 1 | `app.js` (`wireCombos`); no test |
| 18 | Bench | 2, 3 | "Gates", the only place a fault is said, is a screen below the fields, and nothing marks the field at fault. [shot](ux-audit/14.jpg) | layout | 2 | `bench.js`, `app.css`; no test |
| 19 | Bench | 2 | While a gate is blocked the item shows no button to approve or write, and nothing says where one will appear. | missing state | 2 | `bench.js`; no test |
| 20 | Bench | 2 | A garbled reference ("15 Oct 202615 Oct15 Oct 2026 2026") still read "Ok statement-grade". | missing state | 1 | the gate asks that a reference is there, not its form: `desk/intake/bench.py`; `test_bench.py` extended |
| 21 | Bench | 3 | The Bench tab reopened inside the unfinished item, not on the list where the waiting document is. "back to the Bench" had to be found. | layout | 1 | `bench.js`; no test |
| 22 | Bench | 3 | Under a PDF: "a Claude session reads it: python3 -m portfusion.desk.intake.propose". The walker did not know what was being asked of them. [shot](ux-audit/13.png) | wording | 2 | `bench.js`; no test |
| 23 | Bench | 3 | Nothing says which rows a statement becomes. Of nine "+" buttons the walker chose "+ cash reading" and left the holdings; "+ new line" and "+ new contract" meant nothing. [shot](ux-audit/13.png) | wording | 2 | `bench.js`; `docs/reconciling.md` has the answer |
| 24 | Bench | 3 | A row asks again for the document kind and reference just entered on the item, and lists kinds as codes ("ii-statement") where the item lists names ("ii statement"). [shot](ux-audit/13.png) | layout | 1 | `bench.js`, `desk/intake/bench.py`; `test_bench.py` extended |
| 25 | Bench | 3 | "not already in the record": the one way on was "I know — this is a separate event", which was not true. Withdraw, discard or that: the walker could not tell. The test caused the gate: its document was a copy of one already filed. [shot](ux-audit/15.jpg) | wording | 1 | `bench.js`; no test |
| 26 | Bench | 3 | With every gate Ok the only button was "next item: untitled". A blocked item elsewhere held this one's write, and only the folded help says so. | missing state | 2 | `bench.js`; no test |
| 27 | Bench | 3 | "discard item" removed the item at once: no question, no undo, no word after. | missing function | 1 | `bench.js`; no test |
| 28 | Bench | 3 | A worked document is listed twice, "Ready" on the bench and still "Waiting", and the header still counts it in the inbox. [shot](ux-audit/28.png) | missing state | 1 | `panels/bench.py`, `bench.js`; `test_bench.py` extended |
| 29 | Bench | 2, 3 | "write to the record" did nothing: the browser pane cancels the desk's confirming dialog. No write was tested. | missing function | 0 | none |
| 30 | Price Refresh | 1 | "6 marks", "Mark key", "the marks stand at": taken to mean prices, by a guess. [shot](ux-audit/30.png) | wording | 1 | the word is the glossary's: `house/headings.py`, `price-refresh.js` |
| 31 | Price Refresh | 1 | "2 rate(s) the record lacks" sits beside "fetch everything" and "or closes of" a date. The walker could not tell what either would do, and pressed neither. [shot](ux-audit/30.png) | wording | 1 | decided 10 Nov: stays as it is |
| 32 | Price Refresh | 1 | A "New" cell takes the outline of a box to type in and takes no typing; "Take" will not tick. Nothing says why. [shot](ux-audit/30.png) | missing state | 2 | decided 10 Nov: stays as it is |
| 33 | Price Refresh | 1 | "fetch everything" was not pressed, so ticking and writing the marks were not walked or timed. | missing function | 0 | none |
| 34 | What Changed | 6 | The page never names net asset value. Its two blocks cannot be added to the book's move, and the spread bets' "Value now £24,122.00" is notional. The answer is one row of Performance and section 05 of the report; nothing points to either. [shot](ux-audit/34.png) | missing state | 2 | `reading.js`, `panels/what_changed.py`; `test_panels.py` extended |
| 35 | What Changed | 6 | "Compared new line → 30 Sep 2026 3 lines · 30 Jun 2026 → 30 Sep 2026 3 lines" was not understood. It is not a control, and no other period can be chosen. [shot](ux-audit/34.png) | wording | 2 | the words: `reading.js`. A choice of period: the panel, its route and a test |
| 36 | What Changed | 6 | "Market time — what the marks did" and "Record time — every write since": the second table reads as a system log (route, did, table), and one detail is cut off with "…". | wording | 1 | `house/headings.py`, `reading.js`, `app.css` |
| 37 | What Changed | 6 | "3 earlier, since the journal opened 30 Sep 2026" sits under rows dated June and August. | wording | 1 | `reading.js`; no test |
| 38 | Reconcile | 5 | "Every account" lists one of three. The two share accounts are absent and nothing says why. [shot](ux-audit/38.png) | missing state | 2 | the engine hands the page one row: `engine/reconciliation.py`, `panels/reconcile.py`, `reading.js`; `test_panels.py` extended |
| 39 | Reconcile | 5 | The page has nothing to press. "Reading IG equity Price Refresh · a holdings export Bench" was read as: fetch, or find a file. The job stopped. [shot](ux-audit/38.png) | missing function | 2 | the page reads and the work is elsewhere, by design: the words are `reading.js` |
| 40 | Reconcile | 5 | "read live" beside a date 41 days old; the Dashboard's "reconcile to statement" for an account with no statement; "read in one pass — band £40.70"; "running P/L — · deposit — · available —". [shot](ux-audit/38.png) | wording | 1 | `reading.js`, `engine/findings.py`; the tests that pin the sentences |
| 41 | Reconcile | 5 | The help says a share account's units are counted when its reading is written. No page shows the count. | missing state | 1 | follows row 38 |
| 42 | Performance | 8 | No figure is named as since the book began. The first row is Q1 2026, opening at £2,000.00, and Trades holds a buy of 10 Nov 2025: the walker could not tell whether 2025 is in any figure. [shot](ux-audit/42.png) | missing state | 2 | `panels/performance.py`, `reading.js`; `test_panels.py` extended |
| 43 | Performance | 8 | "modified Dietz (day-weighted)"; and under "detail", "Positions at market frozen from the engine at the marks nearest 2026-09-30 / Quality derived". | wording | 1 | `reading.js`; the source sentence is the store's |
| 44 | Performance | 8 | "The book" rows have no "detail"; each account's rows do. [shot](ux-audit/42.png) | missing state | 1 | `reading.js`; no test |
| 45 | Performance | 11 | Three incomes under one heading. "Income" here is £12.50 for Q3 and £42.50 for the year; the Dashboard's "YTD income" is £42.40; the report has "+13", "Position income +11" and a total of 12.40. They are the income the return counts, the positions' income and all income. [shot](ux-audit/42.png) | wording | 2 | `return_income` is headed "Income": `house/headings.py`, `test_figures.py`; the report moves with it |
| 46 | Holdings | 7 | At 1440 wide the table runs off the page. Unrealised gain, weight, entry date, days held and the only ways into a row, "trades" and "detail", are out of sight; a black bar is the one sign. [shot](ux-audit/46.png) | layout | 2 | `app.css`, `kit.js`; no test |
| 47 | Holdings | 7 | Clicking a row highlights it and does nothing else. | missing function | 1 | `kit.js`; no test |
| 48 | Holdings | 7 | Scrolled right, "detail" opened a tall empty gap: its content is drawn at the table's left, out of sight. It looked broken. | layout | 2 | `app.css`, `kit.js`; no test |
| 49 | Holdings | 7 | "detail" is the mark history alone. Bought and sold are on Trades, received is on Accounts, by account, in free text. No one place holds a holding's history; Round Trips' "company life" view holds much of it, and nothing points there. | missing function | 2 | `panels/holdings.py`, `reading.js`; `test_panels.py` extended |
| 50 | Holdings | 7 | The Method says the thesis "shows under 'why' on Holdings". None was seen on the holding opened; whether it has one was not traced. | wording | 1 | not traced |
| 51 | Round Trips | 9 | The tab's name did not say closed positions, and "Realisations 4 / Closed out 1" were not told apart. [shot](ux-audit/51.png) | wording | 1 | `reading.js`, `house/headings.py` |
| 52 | Round Trips | 9 | The table runs off the page as on Holdings: "Entry date" is cut to "Entr", and exit date, days held, closed out, "trades" and "detail" are out of sight. [shot](ux-audit/51.png) | layout | 2 | as row 46 |
| 53 | Round Trips | 9 | A heading sorts when pressed, and nothing shows that until one is. | layout | 1 | `app.css`; no test |
| 54 | Round Trips | 4, 9 | An "Owed" tag sits unlabelled at the row's far right. Its detail reads "Why we exited Owed" with nowhere to write it. It is written on a Bench item, and neither page says so. | missing function | 2 | `reading.js` (a link to the Bench); with row 4 |
| 55 | Round Trips | 9 | A row's entry date is 26 Jun 2026 and its "Why we entered" is dated 6 Jul 2026. | wording | 1 | the second is the reasoning's own date: `reading.js` |
| 56 | Round Trips | 9 | "View: holding / company life": the walker did not know what the second would change. | wording | 1 | `reading.js` |
| 57 | Trades | 10 | Opened from its tab, the page was still filtered to the company looked at before: "2 trades" under "every buy and sale on file" read as the whole book. The company's name is cut off in its box. | missing state | 2 | `kit.js` (`HELD_FILTERS`), `app.css`; no test |
| 58 | Trades | 10 | There is no total for a company bought in lots. A spread bet's "Trade value (GBP)" is notional, not money paid, and nothing says so. [shot](ux-audit/57.png) | missing state | 1 | `panels/trades.py`, `reading.js`; `test_panels.py` extended |

## Timing

Load is a tab pressed to the page painted, three runs. The first load of the desk, address to
Dashboard painted: 353, 240, 231 ms.

| Page | Load, ms | Slowest action |
|---|---|---|
| Dashboard | 218, 228, 230 | open the Q3 report: 131, 137, 139 |
| Bench | 14, 12, 15 | |
| Price Refresh | 36, 33, 36 | |
| What Changed | 27, 31, 26 | |
| Reconcile | 47, 37, 38 | |
| Performance | 176, 122, 122 | |
| Holdings | 81, 67, 78 | |
| Round Trips | 67, 52, 59 | |
| Trades | 26, 21, 21 | |
| Accounts | 17, 17, 21 | |
| Reports | 7, 12, 7 | |
| Method | 5, 5, 5 | |
| Access | 11, 12, 12 | |
