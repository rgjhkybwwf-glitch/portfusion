# Content map

Which page of the desk, and which section of the report, answers each of the owner's twelve jobs
([`direction.md`](direction.md), For whom), what each shows, and where the other renderer shows
the same figure. It is the reference a page's work is designed against: a design card cites it,
and a change that adds a page or a section, removes one, or moves a job between them changes this
page in the same pull request.

Decided on the content map's design card (#3, the maintainer, 13 Nov 2026: "All as
recommended"):

- **Thirteen pages, one job each.** No page is removed. Accounts and Access answer no job of their
  own and stay: Accounts holds the register and the money in and out, Access who may read.
- **"Why the value moved" is answered on Performance**: a quarter's row opens to what made its
  gain (#153, slices #251 and #252). What Changed stays, after Price Refresh, as what the last
  refresh moved and what was recorded, and points to Performance. No period chooser.
- **Charts of progress are a feature of their own** (#241), in 0.5.0. The year-end report stays
  Later.
- Asked on their own cards: how a figure leads to its working (#154, slices #256 to #258), the
  report's format and how it is sent (#155), and which pages the hosted desk carries (#6). Until
  then the working stays on Method, the report stays one page the desk renders, and the hosted
  desk keeps the pages it has.

## The desk's pages

In tab order (each panel's `ORDER`, `desk/panels/`). Hosted: the page is in `REMOTE_PANELS`
(`desk/remote.py`), so a signed-in reader may open it ([`access-levels.md`](access-levels.md)).

| Page | Jobs | What it shows | Hosted |
|---|---|---|---|
| Dashboard | 4, part of 8 | net asset value, exposure and its two parts, the year's return, and the other headline figures; "Needs attention", what the record needs, each leading to its page; "What was checked" | yes |
| Bench | 2, 3 | documents waiting, and an item's evidence, proposed rows, reasoning and gates | no |
| Price Refresh | 1 | bank, fetch, review, write | no |
| What Changed | part of 6 | what the prices did, for shares and for spread bets, each line against its own previous price; every write to the record since | yes |
| Reconcile | 5 | what disagrees; every account against its broker | yes |
| Performance | 8, part of 6 | each quarter, for the book and for each account; the year so far | yes |
| Holdings | 7, part of 10 | every line; a row's reasoning, research notes, company life, income and price history; where the exposure sits | yes |
| Round Trips | 9, parts of 7 and 10 | closed positions, by holding or by company life | yes |
| Trades | 10, part of 7 | every buy and sale, with no totals | yes |
| Accounts | part of 5 | the register, external capital, income and costs for the year | no |
| Reports | 11 | each quarter's report and whether it is ready; the year end, not built | yes |
| Method | 12 | how the numbers are made, in eighteen topics; no figure leads to it yet (#154) | no |
| Access | none | levels, readers, devices, sign-ins | no |

## The report's sections

In the order `report/page.py` lists them; the number is the place in that list.

| Section | The same on the desk |
|---|---|
| 01 Portfolio summary | Dashboard (live); Performance (the quarter's return) |
| 02 Performance | Performance |
| 03 Where the exposure sits | Holdings, under the same heading, live |
| 04 Holdings | Holdings (the desk has no total row) |
| 05 Contributors and detractors | **nowhere yet**: `Book.quarter_contributions()` and `quarter_attribution()` have no reader on the desk until #153 |
| 06 Investment activity | Trades, and Round Trips for the realised gain |
| 07 Cash movements and income | Accounts |
| 08 By account | Performance's account rows |
| 09 What these figures rest on | Reconcile's last two columns |

The report prints whole on A4 landscape (`report/style.py`, #195).

## The jobs and their homes

| Job | Where it is answered today | Homes | Work that changes it |
|---|---|---|---|
| 1 prices | Price Refresh | one | |
| 2 a dividend, 3 a broker document | Bench | one | the Bench lines of 0.4.2 |
| 4 what the record needs | Dashboard, each line leading to its page | one | |
| 5 reconcile an account | Reconcile reads; the work is on Price Refresh or the Bench; cash is on Accounts | three pages | |
| 6 why the value moved | What Changed, a quarter's row on Performance, the report's section 05 | **three places, none whole** | #153: Performance becomes its home |
| 7 one holding's history | a Holdings row's detail, then Trades, then Round Trips by company life | two or three pages | #199 brings the trades into the detail |
| 8 how the book has done | Dashboard and Performance | two pages, one figure | |
| 9 the best and worst closed | Round Trips | one | |
| 10 what a company cost | Trades by company, Holdings' cost, Round Trips by company life | two or three pages | |
| 11 the report to send | Reports | one, with no send control | #155 |
| 12 how a figure is made | Method | one, not reached from a figure | #154 |

## One figure under more than one name

Each name is in `house/headings.py`; Method's topic "How the gains, incomes and capitals differ"
sets the gains side by side.

| Figure | Its names |
|---|---|
| The year's return | "YTD return" and "Return since … (MWR)", the record's first day filled in, both on the Dashboard and again on Performance; "MWR on NAV" under the Dashboard's figure |
| Net asset value | "Net asset value" on the Dashboard and in the report; "Closing NAV" on Performance and in the report's tables |
| Exposure | "Total market exposure" on the Dashboard; "Market exposure" on Performance |
| The gains | "Trading gain, excl. income" on the Dashboard; "Capital growth" and "Gain with income" on Performance; "The quarter's gain" in the report's section 05 |

## Not on the map yet

- **New pages or figures decided for 0.5.0**: a holding's return column (#146) and charts of
  progress (#241). Each joins the tables above in the pull request that turns it on.
- **The year-end report**: Later ([`direction.md`](direction.md), Later and Declined).
