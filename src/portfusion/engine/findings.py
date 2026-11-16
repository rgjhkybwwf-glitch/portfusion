"""The Book's record time, and what the record needs today."""

from __future__ import annotations

import pandas as pd

from portfusion.engine.store import utc_of
from portfusion.engine.core import Core
from portfusion.house import precision as P
from portfusion.house import words as W

#: A finding's kinds: WORK the record is owed, and the STATE a check found.
KINDS = ("work", "state")


class Finding(str):
    """A finding's sentence, which says what is so, and its kind (`KINDS`).

    A work finding names `page`, the panel its work is done on, and `action`, the words of the step
    taken there; or neither, where no desk page does the work. A state finding names neither. The
    step is never in the sentence: the desk draws it as the link's words, and the command prints
    it after the sentence."""
    page: str | None
    action: str | None
    kind: str

    def __new__(cls, text: str, page: str | None = None, action: str | None = None,
                kind: str = "work"):
        if kind not in KINDS:
            raise ValueError(f"a finding's kind is one of {KINDS}, not {kind!r}")
        if (page is None) != (action is None):
            raise ValueError(f"a finding names its page and its action together: {text!r}")
        if kind == "state" and page is not None:
            raise ValueError(f"a state finding leads nowhere: {text!r}")
        self = super().__new__(cls, text)
        self.page, self.action, self.kind = page, action, kind
        return self


class Findings(Core):

    # ---- RECORD TIME  —  what the book LEARNED, and when -----------------------------

    def journal_opened(self) -> str | None:
        """The instant the journal opened: every table's opening count is taken then.

        Every table's opening count carries it, and they all carry the SAME one, because
        staggered openings would make "since the journal opened" mean a different moment per
        table. Returns None on a journal with no baseline rows, which is a journal that cannot
        be reconciled and is reported as such rather than guessed at.
        """
        opened = self.store["journal"]
        opened = opened[opened["route"] == "baseline"]["at"]
        return None if opened.empty else str(opened.min())

    def journal(self, since: str | None = None, route: str | None = None,
                before: str | None = None) -> pd.DataFrame:
        """The journal, newest first, opening counts excluded — an opening count records what
        was already on file, not a change.

        `since` is an ISO instant or date; a plain date includes the whole of that day.
        `before` is the rest: the same date leaves out the whole of that day.
        """
        frame = self.store["journal"]
        frame = frame[frame["route"] != "baseline"]
        if since:
            frame = frame[frame["at"] >= (utc_of(since) if "T" in str(since) else str(since))]
        if before:
            frame = frame[frame["at"] < (utc_of(before) if "T" in str(before) else str(before))]
        if route:
            frame = frame[frame["route"] == route]
        # ONE SECOND CAN HOLD SEVERAL WRITES, and the later row in the file is the newer: reversed
        # first and sorted stably, they read newest first like everything else.
        return (frame.iloc[::-1].sort_values("at", ascending=False, kind="stable")
                .reset_index(drop=True))

    def journal_reconciliation(self) -> pd.DataFrame:
        """Per table: the opening count, what the journal accounts for, and what is on file.

        THE CLAIM: `opening + appends − removes = rows on file`, table by table. A difference is a
        row that reached the store by a route nobody journalled — the hand edits, which this lists
        rather than fails on. The counts come through the record (`rules.store_rows()`).

        A REPLACE IS NOT COUNTED: a refresh replacing marks leaves the file as long as it was.
        Only rows at or after the opening count are read; the seeded bench rows before it are
        already inside those figures.
        """
        frame = self.store["journal"]
        opened = self.journal_opened()
        on_file = self._rows_on_file
        out = []
        for name in sorted(on_file):
            base = frame[(frame["route"] == "baseline") & (frame["table"] == name)]
            since = frame[(frame["table"] == name) & (frame["route"] != "baseline")]
            if opened is not None:
                since = since[since["at"] >= opened]
            opening = int(base["rows"].sum()) if not base.empty else None
            added = int(since[since["op"] == "append"]["rows"].sum())
            removed = int(since[since["op"] == "remove"]["rows"].sum())
            expected = None if opening is None else opening + added - removed
            out.append({
                "table": name, "opening": opening, "appended": added, "removed": removed,
                "replaced": int(since[since["op"] == "replace"]["rows"].sum()),
                "expected": expected, "on_file": on_file[name],
                "unaccounted": None if expected is None else on_file[name] - expected,
            })
        return pd.DataFrame(out)

    def journal_unaccounted(self) -> pd.DataFrame:
        """Only the tables that do not close. Empty means every row is accounted for."""
        recon = self.journal_reconciliation()
        return recon[recon["unaccounted"].fillna(0) != 0].reset_index(drop=True)

    # ---- WHAT THE RECORD NEEDS TODAY -------------------------------------------------
    #
    # The findings `portfusion record` prints and the Dashboard lists under "Needs attention". Every
    # one is read from the record, never from a rendering.

    def findings(self, today: str | None = None,
                 counted: dict[str, dict[str, float]] | None = None) -> dict:
        """The record's state as data: {problems, gaps, notes, prices}, each finding a `Finding`.

        A PROBLEM is a defect until explained: an account the broker does not agree with, prices
        past their age or spread limit, a conversion at a stale rate, a row entered since the line
        whose document is not on file. A GAP is work owed: an account with nothing checked against
        it, a judgement owed. Both are work. A NOTE is the state, stated, so a working check is
        visible as working; a count note is written only when its check is clean, since the gaps
        say what is owed.

        WORK NO DESK PAGE DOES names no page: reasoning owed on a trade already written, a live
        price nothing holds, a dividend with no line, points per unit owed, and a check that could
        not run.

        No expected figure is written in: every finding is a relationship in today's record. Each
        part that reads machinery outside the ledger — the journal, the conversions, the archive —
        reports that it could not look rather than raising.

        `today` is an ISO date for the price-age test; today's date if omitted. `counted` is
        `account_checks()`'s.
        """
        problems, gaps, notes = [], [], []

        # ---- the book against the BROKERS' STATEMENTS -------------------------------------
        # EACH ACCOUNT IN `account_checks()`'s WORDS, which Reconcile shows. A check with a step
        # is work: a difference a problem, led to Reconcile, which shows what differs; any other a
        # gap, led to where its step is taken. One within its tolerance is the state, stated; one
        # whose units agree is counted, and named in the accounts line.
        checks = self.account_checks(counted).to_dict("records")
        for c in checks:
            said = f"{c['account']}: {c['state']}"
            if c["verdict"] == "differs":
                problems.append(Finding(said, "reconcile", c["next"]))
            elif c["next"]:
                gaps.append(Finding(said, c["page"], c["next"]))
            elif c["verdict"] == "within-band":
                notes.append(Finding(c["sentence"], kind="state"))
        checked = [c["account"] for c in checks if c["checkable"]]
        notes.append(Finding(f"{len(checked)} of {len(checks)} account{'s' * (len(checks) != 1)} "
                             f"checked against the broker"
                             + (f": {', '.join(checked)}" if checked else ""), kind="state"))

        # ---- PRICE FRESHNESS ------------------------------------------------------------
        p = self.price_ageing(today)
        newest, oldest = pd.Timestamp(p["newest"]), pd.Timestamp(p["oldest"])
        age, spread = p["age_days"], p["spread_days"]
        prices = ([f"newest {P.day(newest)}, oldest {P.day(oldest)}",
                   f"{age} days (oldest of {p['marks']} prices) · spread {spread}d"]
                  if p["marks"] else ["no prices yet", "nothing to age"])
        refresh = ("price-refresh", "refresh the prices")
        if age > self.D.PRICE_AGE_LIMIT:
            problems.append(Finding(
                f"prices are {age} days old, past the {self.D.PRICE_AGE_LIMIT}-day limit", *refresh))
        if spread > self.D.PRICE_SPREAD_LIMIT:
            problems.append(Finding(
                f"prices span {spread} days ({P.day(oldest)} to {P.day(newest)}) — past the "
                f"{self.D.PRICE_SPREAD_LIMIT}-day spread limit. A ticker was probably missed in "
                f"the last sweep; the newest price being fresh hides it", *refresh))
        unheld = self.priced_unheld()
        if unheld:
            problems.append(Finding(
                f"a live price nothing holds — {', '.join(unheld)}: every refresh fetches it, and "
                f"its age counts against the prices' freshness"))

        # ---- JUDGEMENTS OWED ------------------------------------------------------------
        owed = self.theses_owed()
        if not owed:
            notes.append(Finding(f"reasoning: none owed since {P.day(self.D.REVIEW_FROM)}, on "
                                 f"entry or on exit", kind="state"))
        gaps.extend(Finding(f"reasoning owed — {o['ticker']}"
                            + (f" in {o['account']}" if o["account"] else "")
                            + f": {o['half']}, since {P.day(o['since'])}") for o in owed)

        # ---- FUNDING: every night a daily funded leg was held has its row -----------------
        unfunded = self.funding_gaps()
        if self.D.DAILY_FUNDED_LEGS and not unfunded:
            notes.append(Finding("funding interest: every night a daily funded bet was held has "
                                 "its row", kind="state"))
        gaps.extend(Finding(f"funding interest missing — {a}: {leg} held overnight {night} with "
                            f"no row", "bench", "enter the funding interest")
                    for a, leg, night in unfunded)

        # ---- DATED RATES: every date a figure converts at has that day's close ----------
        owed = self.rate_gaps(today)
        if not owed:
            notes.append(Finding("dated rates: every date a figure converts at has its close",
                                 kind="state"))
        gaps.extend(Finding(f"rate owed — {g['currency']} on {P.day(g['date'])}, for "
                            f"{W.RATE_OWED_FOR[g['why']]}: no TradingView close on file for it",
                            "price-refresh", "fetch the close") for g in owed)

        # ---- A DIVIDEND'S LINE: what lets a company's life count it ---------------------
        gaps.extend(Finding(f"dividend not assigned to a line — {r.date} {r.account}: {r.detail}")
                    for r in self.D.ci_rows if r.category == "Dividend" and not r.ticker
                    and pd.Timestamp(r.date) >= self.baseline)

        # ---- A BET LINE'S POINT: what turns a held bet into share-equivalents -----------
        L = self.ledger
        held_bets = sorted(set(L.loc[L["open_leg"] & L["held_as"].eq("spread bet"), "ticker"]))
        ident = self._identity().set_index("ticker")
        gaps.extend(Finding(f"points per unit owed — {code}: held, and securities.csv does not "
                            f"say how many points make one unit of its price")
                    for code in held_bets
                    if code not in ident.index or pd.isna(pd.to_numeric(
                        ident.at[code, "points_per_unit"], errors="coerce")))

        # ---- conversions: income in another currency, and its rate's age ---------------
        note, stale = self._conversion_state()
        if note:
            notes.append(note)
        problems.extend(stale)

        # ---- THE EVIDENCE CHAIN ---------------------------------------------------------
        note, problem = self._evidence_chain()
        notes.append(note)
        if problem:
            problems.append(problem)

        # ---- RECORD TIME ----------------------------------------------------------------
        note, problem = self._journal_state()
        notes.append(note)
        if problem:
            problems.append(problem)

        return {"problems": problems, "gaps": gaps, "notes": notes, "prices": prices}

    def funding_gaps(self) -> list[tuple[str, str, str]]:
        """Nights a daily funded leg was held with no funding-interest row charging for them:
        (account, leg, night), from the later of the leg's opening and the account's first
        capital movement, to the night before it closed or last night while it is held. The load
        holds every row to such a leg; this asks the other way round, work the record is owed.
        PER ACCOUNT AND NIGHT: IG's row charges the account's daily legs for a night together,
        so a night one row names is charged for every such leg the account held.

        Side effects: none.
        """
        charged: dict[str, set] = {}
        for r in self.D.ci_rows:
            if r.category == "Funding interest":
                charged.setdefault(r.account, set()).update(
                    pd.Timestamp(n) for n in self.D.funding_nights(r.detail, r.date))
        moved = self.store["movements"]
        begins = pd.to_datetime(moved["date"]).groupby(moved["account"]).min().to_dict()
        today = pd.Timestamp.today().normalize()
        out = []
        for account, leg, opened, closed in self.D.DAILY_FUNDED_LEGS:
            night = max(pd.Timestamp(opened), begins.get(account, pd.Timestamp(opened)))
            end = pd.Timestamp(closed) if closed else today
            while night < end:
                if night not in charged.get(account, set()):
                    out.append((account, leg, night.date().isoformat()))
                night += pd.Timedelta(days=1)
        return out

    def _conversion_state(self) -> tuple[Finding | None, list[Finding]]:
        """Foreign-currency income, and how far its rate sat from the event: (note, problems).
        A PROBLEM past `rules.FX_RATE_AGE_LIMIT_DAYS`: the book would add a figure computed at a
        rate nobody fetched for the day, and the fix is to fetch one."""
        try:
            conv = self.conversions()
            if conv.empty:
                return None, []
            limit = self.D.FX_RATE_AGE_LIMIT_DAYS
            # THE ROWS WITH A RATE, for the furthest: a row with none has no distance, and the max
            # over it would raise, putting "could not be checked" in place of every problem below.
            apart = [int(d) for d in conv["days_apart"] if d is not None and pd.notna(d)]
            note = (f"conversions: {len(conv)} foreign-currency income row(s) · "
                    + (f"rate up to {max(apart)}d before the event, limit {limit}d" if apart
                       else "none with a rate on file"))
            return Finding(note, kind="state"), [Finding(
                (f"{r.account} {str(r.date)[:10]}: {r.currency} {r.local_amount} converted at "
                 f"the close of {r.rate_date} — {r.days_apart} days before the event, past the "
                 f"{limit}-day limit") if pd.notna(r.days_apart)
                else (f"{r.account} {str(r.date)[:10]}: {r.currency} {r.local_amount} has no "
                      f"close on file on or before its date"),
                "price-refresh", "fetch the close") for r in conv[conv["stale"]].itertuples()]
        except Exception as e:                       # noqa: BLE001 — never fail over this check
            # NOT CHECKED IS A PROBLEM, not a note: a check that cannot run must not read as good
            # order.
            return (Finding(f"conversions: unknown ({type(e).__name__})", kind="state"),
                    [Finding(f"conversions could not be checked: {type(e).__name__}: {e}")])

    def _evidence_chain(self) -> tuple[Finding, Finding | None]:
        """How many rows citing a broker document have it on file, in one line, and a problem if
        any has not, whatever its date. A row that cites no document is not counted and is not a
        gap: an IG read is retrieved by the dealId it stores. The rows labelled `not-on-file` are
        counted beside it, so the line says how much of the record no document holds."""
        try:
            names = self.D.schema.filed_statements()
            if not names:
                return Finding("evidence: no broker document is on file, so no row's document can "
                               "be checked", kind="state"), None
            # THE ROW'S ACCOUNT TRAVELS WITH IT: a trade's source names the document's kind and
            # date only, and a date is not a document until the account narrows it.
            rows = ([(t.trade_id, t.source, t.broker_ref, t.acct) for t in self.D.buys]
                    + [(e.sale_id, e.source, e.broker_ref, e.acct) for e in self.D.sales])
            cites, gaps, absent = 0, [], 0
            for rid, src, ref, acct in rows:
                ev = self.D.evidence_from_source(src)
                absent += bool(ev and ev.key in self.D.CLOSED_TO_NEW_ENTRIES)
                ok = self.D.reference_resolves(src, names, ref, acct)
                if ok is None:
                    continue
                cites += 1
                if not ok:
                    gaps.append(rid)
            line = (f"evidence: {cites - len(gaps)} of {cites} rows that cite a broker document "
                    f"have it on file · {absent} more row{'s are' if absent != 1 else ' is'} "
                    f"recorded as having none")
            # THE ROWS WITHOUT ONE ARE THE PROBLEM'S TO NAME: the line's count already says how many.
            return Finding(line, kind="state"), (Finding(
                f"{len(gaps)} row(s) cite a document that is not on file: "
                f"{', '.join(sorted(gaps))}", "bench", "file the document") if gaps else None)
        except Exception as e:                       # noqa: BLE001 — never fail over provenance
            # NOT CHECKED IS A PROBLEM, as the conversions' is.
            return (Finding(f"evidence: unknown ({type(e).__name__})", kind="state"),
                    Finding(f"the evidence chain could not be checked: {type(e).__name__}: {e}"))

    def _journal_state(self) -> tuple[Finding, Finding | None]:
        """What the journal accounts for, in one line, and a problem if it could not be read. A
        difference is a FINDING, not a problem: a hand edit with a commit message is a correction
        the store allows."""
        try:
            opened = self.journal_opened()
            if opened is None:
                return Finding("journal: no opening count — nothing to reconcile against",
                               kind="state"), None
            off = self.journal_unaccounted()
            wrote = self.journal(since=opened)
            if off.empty:
                return Finding(f"journal: every row accounted for since "
                               f"{P.day(pd.Timestamp(opened))} · {len(wrote)} write(s) recorded",
                               kind="state"), None
            parts = "; ".join(f"{r['table']} {r['unaccounted']:+d}"
                              for r in off.to_dict("records"))
            return Finding(f"journal: {len(off)} table(s) hold rows no route accounts for — "
                           f"{parts}. That is a hand edit; git log will say which.",
                           kind="state"), None
        except Exception as e:                       # noqa: BLE001 — never fail over the journal
            return (Finding(f"journal: unknown ({type(e).__name__})", kind="state"),
                    Finding(f"the journal could not be checked: {type(e).__name__}: {e}"))
