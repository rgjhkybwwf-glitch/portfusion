# Direction

Who PortFusion is for, what it never does, and what each milestone is for. The agents read it
before they plan ([`CONTRIBUTING.md`](../CONTRIBUTING.md), The loop). It holds only what
changes slowly, and changes only by the maintainer's answer: at a milestone's gate, or to a
question that asks which release builds a feature.

## For whom

- **The owner of a book**, at the desk on their Mac: the maintainer's own book, and no one else's
  needs shape it (decided 13 Nov 2026). Their twelve jobs are [`ux-audit.md`](ux-audit.md)'s,
  under "The jobs":

  | Comes round | Jobs |
  |---|---|
  | every sitting | 4 what the record needs |
  | weekly | 1 prices · 7 one holding's history · 8 how the book has done |
  | monthly | 2 a dividend · 3 a broker document · 5 reconcile an account · 10 what a company cost |
  | quarterly | 6 why the value moved · 9 the best and worst closed positions · 11 the report to send |
  | occasional | 12 how a figure is made |

**1.0** is the twelve jobs passing a cold walk on an empty book.

## Never

- **A feed that writes.** An event reaches the record only through the Bench, and a price only by
  a person's tick on Price Refresh.
- **A database.** The record is CSV files you can read and diff.
- **Anything else the stability rules hold** ([`CONTRIBUTING.md`](../CONTRIBUTING.md), The
  stability rules).

## The arc

| Milestone | What it is for | Where you first see something new |
|---|---|---|
| 0.4.1 Words and names | One name per figure, and findings in plain words. No figure or store change. | "price" for "mark"; "Trading gain, excl. income" |
| 0.4.2 The Bench guides | A newcomer records a fact without leaving the Bench. Closes with the empty-book walk (#41). | a Bench item's standing line |
| 0.4.3 The new frame | The desk opens in a new frame, in PortFusion's own design system (#9): a side menu, an address for each object, and new Home, Companies and company pages (#347), then Trades, Round Trips and What Changed redrawn in it, each record opening in its row (#413). One store move: a company keyed by a code of its own, with its migration (#349). First the engine is cleaned up (#366, #367, #368), under a figure check widened to every round trip, company life and holding (#375), so the clean-up moves no figure. Then the first way to change a fact already on the record: correcting a row from the desk (#134). | the side menu, and a company's own page (#347); the first edit of a row on the record (#134) |
| 0.5.0 What each page is for | Each page answers its job, decided by the content map (#3). One piece of structural engine work, in this order: an account keyed by its code, a store move with its migration (#225); one instrument that a share and a bet each answer for, and a bet's margin through it, its rate a second store move (#145); then one new figure (#146). Charts of progress (#241). | a quarter's row on Performance that opens to what made its gain (#153), a headline figure you can click (#154), a send control (#155), a bet's return on the money put up for it (#145), a holding's return column (#146), charts (#241) |
| 0.6.0 The record takes more | New ways for a fact to reach the record. The other store changes and migrations live here. | opening positions (#74) |

The desk runs on the Mac only through 0.6.0. The AI reading session on the Bench is a feature to
grow, not plumbing.

## Later and Declined

Later is parked with its date and reason. Declined is not raised again unless something material
has changed; nothing is declined yet.

| Later | Since | Why it waits |
|---|---|---|
| The year-end report | 13 Nov 2026 | decided on the content map's card (#3): later |
| A time-weighted return beside the money-weighted | 13 Nov 2026 | an open bet: the figures cannot be set against an index today |
| Tax reporting from the section 104 pools | 13 Nov 2026 | decided: later |
| Platforms other than the Mac | 13 Nov 2026 | decided: Mac only through 0.6.0 |
