"""METHOD — how the numbers are made, what enters the record, and the entry protocol.

It is the reader's statement of the method, so it is reference content, not chrome: the ratchet
on the desk's own prose does not count it.

THE RULES ARE RENDERED FROM THE RECORD, never retyped: `rules.SPREAD_BET`, `STATEMENT_GRADE`,
`SOURCE_HIERARCHY` and its note, the tolerance band, the income categories, the price
limits and the reasoning cut-off are interpolated from the constants, through the engine's pinned
record. tests/test_record.py refuses a file that writes the hierarchy out in its own words.

The Mac's desk only, for now: adding it to the hosted desk is the owner's decision.
"""
from __future__ import annotations

from portfusion.desk import engine
from portfusion.house.precision import pct

NAME = "method"
TITLE = "Method"
#: After Reports, and apart from the thread of the work: how the numbers are made is not work
#: on the book (13 Oct 2026).
ORDER = 80
APART = True


def data() -> dict:
    b = engine.book()
    D = b.D
    since = f"{b.baseline:%-d %b %Y}"
    return {"sections": [
        {"heading": "How the numbers are made", "rows": [
            {"topic": "What a spread bet is", "text": (
                f"{D.SPREAD_BET} Total market exposure = securities owned at market value plus "
                f"spread-bet notional. Net asset value = securities owned at market value plus "
                f"spread-bet equity. The gap between them is leverage. Retired terms, do not "
                f"reintroduce: economic interest · contract value · portfolio value · positions "
                f"basis · economic basis · economic value.")},
            {"topic": "Return — the headline figure", "text": (
                f"On net asset value against capital deployed into positions. A flow is money "
                f"buying a position, less the proceeds of one sold, for a share account; and "
                f"funds for a spread-bet account, never its notional. In a share account a "
                f"deposit, a withdrawal or a cash transfer moves nothing: its net asset value is "
                f"positions at market and holds no cash, so a cash movement counted against it "
                f"would read as a gain or a loss that never happened. The numerator takes "
                f"position income only — {' and '.join(D.POSITION_INCOME)}, which are what the "
                f"capital earns and costs; {' and '.join(D.ACCOUNT_INCOME)} belong to the "
                f"account and stay out. YTD income on the Dashboard is still the whole figure, "
                f"because only the return filters. The formula is modified Dietz in GBP, "
                f"day-weighted: (end value − start value − capital deployed + position income) "
                f"÷ (start value + each flow × the share of the period after its date). A flow "
                f"is weighted by the days from its date to the period's end, so money put in on "
                f"a period's last day moves nothing, and a sale late in one takes little off the "
                f"denominator. The figure is money-weighted and is not comparable to an "
                f"index.")},
            {"topic": "The year, and since the start", "text": (
                f"The year-to-date figures run from the previous 31 December and roll at a new "
                f"year's first price or first row, whichever comes sooner. The year opens at "
                f"that 31 December's frozen net asset value: until that quarter end is frozen, "
                f"the opening and what is built on it are blank, never zero, and so is the "
                f"return since {since}. A spread-bet account's net asset value does not roll: it "
                f"is built from {since}, and built from a later opening it would count that "
                f"year's gains twice. The return since {since} links each full year's return "
                f"with the year to date: (1 + one year) × (1 + the next) − 1, so each year's "
                f"flows weigh only on that year.")},
            {"topic": "A company's life — Round Trips by company life", "text": (
                "First purchase, in any account or instrument, to the day nothing is held. "
                "Life gain = realised + gain to date + dividends + daily funding. Net cost per "
                "share = (cost of what is held − realised − dividends − funding) ÷ held, open "
                "bets as share-equivalents: the break-even price. A percentage only for a life "
                "of shares alone.")},
            {"topic": "Quarterly returns — one series", "text": (
                "One series, on net asset value (Performance), by the same day-weighted formula "
                "as the headline YTD return. Each quarter end's value says what it rests on: sourced "
                "or derived. A quarter whose opening net asset value does not exist gets no "
                "return — never zero, which would be a claim. The open quarter is shown to "
                "date, ends at the newest price mark, and moves with every refresh until it is "
                "frozen.")},
            {"topic": "Reconciling to the brokers", "text": (
                f"Two checks, one per kind of account, on Reconcile. A spread-bet account: the "
                f"book's figure is its derived equity — capital in, plus realised, plus "
                f"unrealised, plus income, never its notional — against IG's own reading, which "
                f"nothing in the book can influence. The pair is judged only when it was struck "
                f"in one pass with the marks; a judged pair is held to a band of "
                f"{pct(D.RECON_LIVE_TOLERANCE_PCT)} of the broker's figure — FX, rounding, bid "
                f"against last, never the market. A share account is checked on its units "
                f"against the broker's holdings export, at the door that takes it: what that "
                f"catches is what no contract note carries — a reinvested dividend, a corporate "
                f"action, a wrong quantity. A reading that lists no units, or an IG reading not "
                f"struck in one pass, is not judged: a gap under Needs attention, never a pass "
                f"and never a failure.")},
            {"topic": "Spread-bet valuation", "text": (
                "Marked at IG contract levels, at both ends — entry and mark — never at the "
                "underlying share price: marking the entry at the contract level and the mark at "
                "spot was a real defect, a subtraction across two bases. Different legs of one "
                "underlying can sit on different IG contracts at different prices, so marks are "
                "keyed by contract, not by ticker. A sweep reads a contract's level live, and a past "
                "day's close can be dated too: IG's hour bar ending 22:00 UK for a near contract, and "
                "for a far one the level its filed IG statement prints. Between refreshes a mark ages "
                "like any other.")},
            {"topic": "Cash", "text": (
                "Recorded like a price: a balance, the date it was true, a named source. Cash is "
                "never in net asset value: a share account's is its positions at market, and a "
                "spread-bet account's equity already contains its funds. It is recorded because "
                "a broker's total is positions plus cash and the reconciliation needs it "
                "(Accounts, Cash / Funds). It does not reach the return.")},
            {"topic": "Partial disposals from a pooled holding", "text": (
                "S.104 pool average, per account and ticker. Cost released = quantity sold × "
                "(pool cost ÷ pool quantity) at the sale, and the sale that empties a pool "
                "releases what remains. A sale is one Exits row and nothing else is written. "
                "Realised = proceeds less cost released, net of dealing commission.")},
            {"topic": "Unrealised gain and position size", "text": (
                "Unrealised gain is in sterling: (value − cost) ÷ cost, matching the broker app "
                "and including FX. Position size (weight) is a share of current total market "
                "exposure, not of entry cost and not of 'portfolio value', a retired term: a "
                "spread bet contributes its exposure, so a weight is a share of what the book is "
                "exposed to, not of what it is worth.")},
            {"topic": "Prices, and how fresh they must be", "text": (
                f"Each line's mark is sourced and dated on its own; Holdings opens to every mark "
                f"behind a line. Two limits, and they catch different things: a problem when the "
                f"oldest mark passes {D.PRICE_AGE_LIMIT} days — nobody has refreshed lately — and "
                f"another when the oldest lags the newest by more than {D.PRICE_SPREAD_LIMIT} "
                f"days — a sweep missed a line, which the age limit cannot see. A deal's local "
                f"price is its document's; one priced in sterling on a foreign share takes its "
                f"day's close. The GBP cost is always real, so a rate never moves a total.")},
        ]},
        {"heading": "What enters the record", "rows": [
            {"topic": "The door", "text": (
                f"Everything enters through the door — an authenticated feed read, or a broker "
                f"document filed in the archive — and a row that cites a document has it there. "
                f"No figure on file changes: a correction is a new row that supersedes the old "
                f"one, and a mark read again the same day replaces that day's. "
                f"{D.STATEMENT_GRADE}")},
            {"topic": "Source hierarchy", "text": (
                f"When two sources disagree: {D.SOURCE_HIERARCHY}. {D.SOURCE_HIERARCHY_NOTE} A "
                f"recollection ranks last and cannot enter the record by itself: only a feed "
                f"read or a filed broker document can.")},
            {"topic": "Entering a trade", "text": (
                "A trade is not accepted without seven fields, and if one is "
                "missing it waits for the document. 1 · the real trade date, not settlement. "
                "2 · direction: Buy or Sell. 3 · the account exactly as the "
                "register names it. 4 · the real ticker from the securities register; a "
                "part-sold parcel is a Realisation ID, never an invented code. 5 · quantity, "
                "or the stake per point for a spread bet. 6 · the executed price; for a buy "
                "the GBP cost must be right, for a sell the net proceeds. 7 · a named document "
                "and its broker reference — not 'statement' or 'app'.")},
            {"topic": "Entering a new position", "text": (
                f"The seven fields, then the eighth: the thesis, written the same day. It shows "
                f"under 'why' on Holdings while the position is open and on Round Trips once it "
                f"closes, beside the research note if one stands behind it, with the reason for "
                f"closing. Each half is owed from {D.REVIEW_FROM:%-d %b %Y} — the thesis if the "
                f"position opened on or after it, the exit reason if it closed on or after it — "
                f"and is marked owed while blank. One dated before then is blank on purpose, "
                f"and is not owed.")},
            {"topic": "If a field is missing", "text": (
                "Do not put a figure of your own into the ledger to fill the gap. Wait for the "
                "document: a guess sitting in the ledger is indistinguishable from a fact — the "
                "failure this whole system exists to prevent.")},
        ]},
    ]}
