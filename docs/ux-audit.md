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
