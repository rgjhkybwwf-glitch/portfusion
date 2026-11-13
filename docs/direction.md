# Direction

Who PortFusion is for, what it never does, and what each milestone is for. The agents read it
before they plan ([`CONTRIBUTING.md`](../CONTRIBUTING.md), The nightly agent). It holds only what
changes slowly, and changes only at a milestone's gate, by the maintainer's answer.

## For whom

- **The owner of a book**, at the desk on their Mac. Their twelve jobs are
  [`ux-audit.md`](ux-audit.md)'s, under "The jobs":

  | Comes round | Jobs |
  |---|---|
  | every sitting | 4 what the record needs |
  | weekly | 1 prices · 7 one holding's history · 8 how the book has done |
  | monthly | 2 a dividend · 3 a broker document · 5 reconcile an account · 10 what a company cost |
  | quarterly | 6 why the value moved · 9 the best and worst closed positions · 11 the report to send |
  | occasional | 12 how a figure is made |

- **Signed-in readers of the hosted desk**, an owner or a principal, who only read
  ([`access-levels.md`](access-levels.md)).
- **Later, a report's recipients**, by a dated link (#6).

## Never

- **Advice.** PortFusion records your own positions and reports on them.
- **A feed that writes.** A fact reaches the record only by a person's approval on the Bench.
- **A database.** The record is CSV files you can read and diff.
- **Anything else the stability rules hold** ([`CONTRIBUTING.md`](../CONTRIBUTING.md), The
  stability rules).

## The arc

| Milestone | What it is for | Where you first see something new |
|---|---|---|
| 0.4.1 Words and names | One name per figure, and findings in plain words. No figure or store change. | "price" for "mark"; "Trading gain, excl. income" |
| 0.4.2 The Bench guides | A newcomer records a fact without leaving the Bench. Closes with the empty-book walk (#41). | a Bench item's standing line |
| 0.5.0 What each page is for | Each page answers its job, decided by the content map (#3). One new figure (#146). | a headline figure you can click (#154), a period chooser (#153), a send control (#155), a holding's return column (#146) |
| 0.6.0 The record takes more | New ways for a fact to reach the record. Store changes and migrations live here. | the first edit of a row on the record (#134); opening positions (#74) |
| 0.7.0 Look and reach | A design system, the phone, new reader levels, hosting. | dated links for recipients (#6) |

## Later and Declined

Later is parked with its date and reason. Declined is not raised again unless something material
has changed. Nothing is declined yet.

| Later | Since | Why it waits |
|---|---|---|
| Charts of progress, and the year-end report | 13 Nov 2026 | the content map (#3) names both; question 4 |
| A time-weighted return beside the money-weighted | 13 Nov 2026 | an open bet: the figures cannot be set against an index today |
| Tax: section 104 pools | 13 Nov 2026 | question 7 |
| Platforms other than the Mac | 13 Nov 2026 | question 5 |

## Open questions for the maintainer

Answered once; each answer is folded into the sections above and its line removed.

1. Who is it for beyond you? **a** your book only · **b** any UK private investor · **c** owners who report to principals
2. What does 1.0 mean? **a** the twelve jobs pass cold on an empty book · **b** plus a second real user · **c** no 1.0 planned
3. Is "no advice" also "no analysis"? **a** record and reporting only · **b** analysis of your own record is fine · **c** case by case
4. Charts? **a** in 0.5.0 · **b** with the design system in 0.7.0 · **c** never
5. Mac only through 0.7.0? **a** yes · **b** Linux or hosted earlier
6. The AI reading session on the Bench: **a** a product feature to grow · **b** plumbing
7. Tax (section 104 pools): **a** in scope · **b** later · **c** never
