# Prices

How the book's marks are fetched, when, and the three rules that stop a bad one entering. What
the sweep does, step by step, is `feeds/refresh.py`'s docstring.

```bash
portfusion desk                              # Price Refresh: fetch, tick, write
python3 -m portfusion.feeds.refresh          # the same sweep, printed; --on D for a past day's closes
python3 -m portfusion.feeds.refresh --check  # are both histories current?
```

The terminal sweep writes nothing. On the desk, the write banks the outgoing marks first, then
lands the ticked marks and IG readings together.

## When to run it

**Refresh the whole book or none of it**, when every venue it holds is trading, so every line
comes back live. Outside that window the sweep still runs: a venue not yet open gives its last
close, and one that has shut gives that day's close. The audit flags a book whose oldest mark is
older than `PRICE_AGE_LIMIT`.

**A quarter end needs no sweep of its own.** The freeze takes each line's nearest mark within
`CLOSE_CHECK_WINDOW_DAYS`. For that day's closes instead, use Price Refresh's *closes of* date,
from the next day on. A close outranks a live read of its own day.

**A rate on a date is that day's close.** The rates the record still owes are listed under
*Rates the record lacks* on Price Refresh, and fetched in one press.

## The three rules

A person sits between the fetch and the record because of these. Rule 1 is enforced at the
door; rule 2 only on the past-day route; rule 3 is judgement.

1. **Update a price and its date together.** A stale price wearing today's date is worse than a
   stale price, because the freshness indicator then agrees everything is fine.
2. **Never back-date a live level onto a close it was not struck at.** A level struck mid-session
   is a different instant, and re-dating it invents a mark.
3. **A broker statement is read for transactions, not for live marks.** Taking levels off it the
   day it lands puts the contracts ahead of the shares: one price date is worth more than two
   fresh contracts. A past day's close, banked under the statement's own date, is the exception.

## TradingView

Every share and the exchange rates. Sign in once in your own browser; the session file rotates,
so it is never copied.

```bash
python3 -m portfusion.feeds.tv --tv-sign-in       # once
python3 -m portfusion.feeds.tv --tv-search NAME   # find a symbol; never guess one
```

## IG

The spread-bet contract levels, and each account's equity.

```bash
python3 -m portfusion.feeds.ig --ig-search "NAME"   # find an epic, first
python3 -m portfusion.feeds.ig --ig-verify          # live levels against the record
python3 -m portfusion.feeds.ig --ig-events          # trades, closes, costs and cash against the book
```

- **Never guess an epic.** A wrong one returns a plausible price for the wrong contract and
  passes the audit. Find it with `--ig-search`, check it with `--ig-verify`, then add its row to
  `store/contracts.csv`.
- **Credentials are three per account**: identifier, password and API key, in
  `credentials.json` in the book's folder. Git ignores it.
- **A reading moves the book.** It writes the equity and re-marks the contracts, because the two
  compare only when struck together. **Its funds are not spendable cash**, and are never added to
  the equity.
- **A far contract's past close is its statement's level.** IG prints no evening bars for it, so
  file that day's statement on the bench first.

**Each feed's allowlist refuses anything that is not a read**, before a request is built. IG's
API deals, and TradingView's edits alerts and watchlists. The tests stop a change to either, and
they are meant to.
