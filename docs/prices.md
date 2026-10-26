# Prices

How the book's marks are fetched, when, and the three rules that stop a bad one entering.

```bash
portfusion desk                              # Price Refresh: fetch, tick, write
python3 -m portfusion.feeds.refresh          # bank, then sweep; --on D for a past day's closes
python3 -m portfusion.feeds.refresh --check  # are both histories current?
python3 -m portfusion.history.prices --check # is the outgoing set banked? .fx and .accounts alike
```

The terminal sweep banks the current marks, then prints; it replaces no mark. On the desk, the
write banks the outgoing marks first, then lands the ticked marks and IG readings together. A
history keeps every close, each line's mark at every quarter end, opening and account reading,
and its two newest; a live read between them leaves at the next bank, and git keeps it. What the
sweep does, step by step, is `feeds/refresh.py`'s docstring.

**Each feed's allowlist refuses anything that is not a read**, before a request is built. IG's
API deals, and TradingView's edits alerts and watchlists. The tests stop a change to either, and
they are meant to.

## When to run it

**Refresh the whole book or none of it**, when every venue it holds is trading, so every line
comes back live. Outside that window the sweep still runs: a venue not yet open gives its last
close, and one that has shut gives that day's close. The audit flags a book whose oldest mark is
older than `PRICE_AGE_LIMIT`.

**A quarter end needs no sweep of its own.** The freeze takes each line's nearest mark within
`CLOSE_CHECK_WINDOW_DAYS`. For that day's closes instead, use Price Refresh's *closes of* date,
from the next day on. A close outranks a live read of its own day.

```bash
portfusion freeze 2026-09-30          # what the freeze would write, and what is not ready
portfusion freeze 2026-09-30 --write  # write it; `portfusion record` says when one is owed
```

**A rate on a date is that day's close.** The rates the record still owes are listed under
*Rates the record lacks* on Price Refresh, and fetched in one press.

## The three rules

A person sits between the fetch and the record because of these. Rules 1 and 2 are enforced at
the door; rule 3 is judgement.

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

A line comes back as one of three things:

| Venue | Gives |
|---|---|
| trading | the quote screen's live read, struck at the instant it describes |
| shut | the latest session's close, from the daily bars |
| quote screen refused or unreachable | *unpriced*, with the reason, and a plain "TradingView failed" notice |

A day bar for a session in progress and a minute bar are never a live read: either can run behind
the quote. The next sweep asks again.

```bash
python3 -m portfusion.feeds.tv --tv-sign-in       # once
python3 -m portfusion.feeds.tv --tv-search NAME   # find a symbol; never guess one
```

## IG

The spread-bet contract levels, and each account's equity.

```bash
python3 -m portfusion.feeds.ig --ig-search "NAME"   # find an epic, first
python3 -m portfusion.feeds.ig --ig-verify          # live levels against the record
python3 -m portfusion.feeds.ig --ig-events          # buys, sales, costs, capital against the book
```

- **Never guess an epic.** A wrong one returns a plausible price for the wrong contract and
  passes the audit. A first bet on a new contract is set up from *Sweep IG events* on the Bench,
  which takes the epic from the deal and reads the contract's first mark; `--ig-search` and
  `--ig-verify` check one by hand.
- **Credentials are three per account**: identifier, password and API key, with `env` (`demo` or
  `live`), under the account's `feed_key` in the book's `credentials.json`, which git ignores. An
  IG command run without it prints the template.
- **A reading moves the book.** It writes the equity and re-marks the contracts, because the two
  compare only when struck together. **Its funds are not spendable cash**, and are never added to
  the equity.
- **The events' look-back** is chosen on the Bench ([reconciling.md](reconciling.md)).
- **A far contract's past close is its statement's level.** IG prints no evening bars for it, so
  file that day's statement on the Bench first.
