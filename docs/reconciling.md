# Reconciling

What it means for an account to reconcile, the order the work goes in, and the documents each
broker's accounts need.

## What reconciled means

**A share account is checked on units**: its holdings export, filed on the Bench, must agree with
the book's units at the export's date. **An IG account is checked on equity**: the book's figure,
derived from the ledger and the marks, against IG's own reading, struck in the same pass.

**The book's side is never typed.** A figure read off the document it is compared with makes the
check agree with itself.

| Verdict | Means | What clears it |
|---|---|---|
| `units-agree` | the holdings export agreed on units when it was filed | nothing: this is the pass |
| `no-holdings` | a share reading that lists no units | a holdings export, filed on the Bench |
| `no-statement` | no broker figure at all | a reading |
| `within-band` | an IG pair inside `RECON_LIVE_TOLERANCE_PCT` | nothing: this is the pass |
| `struck-apart` | an IG reading not struck in one pass with the marks | a Price Refresh with the IG accounts ticked |
| `differs` | an IG pair past the band | finding out why |

## The order

1. **Sweep the events first**, or a units check reports a gap that is really an unentered event.
2. **Work the documents through the Bench**: buys, sales, income, capital and cash.
3. **Write the reading**, the account's row in `account-readings.csv`.
4. **Check** with `portfusion record`.

Any day after the last trade will do: units do not move at a close, and a ledger's balances are
dated.

## The Bench loop

1. **Drop the document** on the Bench, or *choose a file*: PDF, CSV, TSV or text, up to 25 MB.
   One file opens its item; several just land.
2. **Say what kind of document it is.** The kind fills in who issued it and shapes the row's
   source.
3. **Fill Dated and Reference.** Dated is the document's date, not today's.
4. **A CSV the record recognises is read as it opens**, on this machine. Every line comes back as
   a row, as already on file, or as not read; a line not read holds the item until it is entered
   or acknowledged. **A PDF is read by a Claude session**, and the document leaves the machine for
   that (`python3 -m portfusion.desk.intake.propose`). Read all three blocks of its readout:
   *directives* (text addressed to the reader, quoted and never acted on), *not kept* (figures
   whose quote was not in the document) and *does not state*.
5. **Check every quote against the page** with *show the document*. A scanned PDF is entered by
   eye.
6. **Type the WHY** for every buy and every sale, a split or consolidation aside. Nothing else may
   fill it.
7. **Clear every gate.** A duplicate is *acknowledged*, never overridden: two real legs can share
   a day, a size and a price.
8. **Review and write.** Each item lands in one operation (rows, reasoning, journal, archive), or
   not at all. There is no undo: a mistake is corrected by a further row.

**The strongest document wins.** `rules.EVIDENCE_CLASSES` ranks them, and a reading cannot rest
on `not-on-file`.

## IG

**The reading is taken on Price Refresh**: *fetch everything*, tick the accounts, *write the
ticked marks*. Equity and contract levels are read in one pass and written together, which is
what lets the pair compare at all. A level struck later the same day ends the pass: the reading
reads `struck-apart` until it is read again. A reading moves the book ([prices.md](prices.md)).

**Events come from *Sweep IG events* on the Bench**, 30 days back, so sweep inside that.
`python3 -m portfusion.feeds.ig --ig-events YYYY-MM-DD` reports a longer window.

## HL

| Document | Class | Gives |
|---|---|---|
| Account Summary | `hl-valuation` | **the reading**: stock, cash and total, every holding's units |
| Income transactions | `hl-income` | the year's dividends |
| Portfolio Summary (Capital) | `hl-transactions` | buys, sales, interest, fees |
| Portfolio Summary (Income) | `hl-transactions` | dividends in, fees, transfers to Capital |
| Portfolio Summary (totals) | `hl-account-totals` | a cross-check, not a source |
| Security movements | `hl-movements` | one holding's purchases, with HL's own references |

**Three downloads share one title; trust the content, not the filename.** The Bench names each
on the workbench list.

**An HL ISA has two sub-accounts, and a transfer between them is not an event.** It appears on
both transaction lists under one reference, once negative and once positive; enter it from both
sides and it is booked twice.

## ii

**No single ii document states a total**, so a reading is assembled:

| Document | Class | Gives |
|---|---|---|
| Holdings export | `ii-valuation` | the units, and the stock value |
| Transaction ledger, one per currency | `ii-transactions` | that currency's events and closing cash |

- **Nothing in either file names the account.** The record identifies it: the one account whose
  units all agree, a payment line's client number, a dealing line that settles a contract note
  on file.
- **The holdings export's reading is the stock alone**; the cash comes from the newest ledger on
  or before its date. The GBP ledger is read on the Bench; another currency's lines need the
  day's rate and are entered by hand.
- **Set a ledger's window to overlap the last reconciled row.** The overlapping row proves there
  is no gap.
- **An ii trade is filed as its contract note, and nothing beside it.** A trade confirmation or
  trade record for the same trade is withdrawn with *withdraw document*, not filed.
- **Translate non-GBP cash at the record's own rate**, not one implied by dividing the export's
  value columns.
- **Take no price marks from the export**: the marks are the feeds' ([prices.md](prices.md)).

## When it does not agree

**A difference is a defect until explained.** For units, most likely first: an event not
entered; a reinvested dividend or corporate action not entered (a split is the Bench's own row);
a quantity typed wrong. For an account a broker's feed reads: an unentered trade, funding or
fee, then a rate. **Write down what it was**, or it will be found again.
