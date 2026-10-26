"""The Book's record time, and what the record needs today."""

from __future__ import annotations

import pandas as pd

from portfusion.engine.store import utc_of
from portfusion.engine.core import Core
from portfusion.house import precision as P


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

    def findings(self, today: str | None = None) -> dict:
        """The record's state as data: {problems, gaps, notes, prices}.

        A PROBLEM is a defect until explained: an account past its reconciliation band, prices
        past their age or spread limit, a conversion at a stale rate, a row entered since the line
        whose document is not on file. A GAP is work owed: an account with no statement, a
        judgement owed. A NOTE is the state, stated, so a working check is visible as working.

        No expected figure is written in: every finding is a relationship in today's record. Each
        part that reads machinery outside the ledger — the journal, the conversions, the archive —
        reports that it could not look rather than raising.

        `today` is an ISO date for the price-age test; today's date if omitted.
        """
        problems, gaps, notes = [], [], []

        # ---- the book against the BROKERS' STATEMENTS -------------------------------------
        checked, ungrounded, apart = 0, [], []
        for r in self.reconciliation().to_dict("records"):
            statement = r["statement"]
            if statement is None or statement != statement:
                ungrounded.append(r["account"])
                continue
            difference = r["difference"]
            difference = None if difference is None or difference != difference else difference
            comparable = r["comparable"]
            v = self.reconciliation_verdict(statement, difference, r["evidence"] or "",
                                            comparable if comparable is not None else None,
                                            "" if comparable else str(r["comparability"] or ""))
            if not v["checkable"]:
                apart.append(f"{r['account']} — {v['rule']}")
                continue
            checked += 1
            if v["verdict"] == "units-agree":
                continue
            if difference is None or not v["ties"]:
                shown = "an unknown amount" if difference is None else P.money(difference)
                problems.append(f"reconciliation failed — {r['account']}: book and broker differ "
                                f"by {shown}" + (f", past the {P.money(v['band'])} live band"
                                                 if v["live"] else ""))
            elif v["live"]:
                # A difference that rounds to nothing is £0.00, never -£0.00 or +£0.00.
                agree = P.money(difference, signed=True)
                if agree[1:] == P.money(0):
                    agree = P.money(0)
                notes.append(f"{r['account']}: book and broker agree to {agree} "
                             f"({P.pct(abs(difference) / abs(statement))}) on a LIVE read, "
                             f"band {P.money(v['band'])}")
        notes.append(f"{checked} account(s) reconcile to statement")
        if ungrounded:
            gaps.append("NO STATEMENT to reconcile against: " + ", ".join(ungrounded))
        if apart:
            notes.append("GAPS, so not judged:")
            notes.extend(f"  {a}" for a in apart)

        # ---- PRICE FRESHNESS ------------------------------------------------------------
        p = self.price_ageing(today)
        newest, oldest = pd.Timestamp(p["newest"]), pd.Timestamp(p["oldest"])
        age, spread = p["age_days"], p["spread_days"]
        prices = ([f"newest {P.day(newest)}, oldest {P.day(oldest)}",
                   f"{age} days (oldest of {p['marks']} marks) · spread {spread}d"]
                  if p["marks"] else ["no marks yet", "nothing to age"])
        if age > self.D.PRICE_AGE_LIMIT:
            problems.append(f"prices are {age} days old — past the {self.D.PRICE_AGE_LIMIT}-day "
                            f"limit, refresh before relying on them")
        if spread > self.D.PRICE_SPREAD_LIMIT:
            problems.append(f"price marks span {spread} days ({P.day(oldest)} to {P.day(newest)}) "
                            f"— past the {self.D.PRICE_SPREAD_LIMIT}-day spread limit. A ticker "
                            f"was probably missed in the last sweep; the newest mark being fresh "
                            f"hides it")
        unheld = self.priced_unheld()
        if unheld:
            problems.append(f"a live price nothing holds — {', '.join(unheld)}: every refresh "
                            f"fetches it, and its age counts against the prices' freshness")

        # ---- JUDGEMENTS OWED ------------------------------------------------------------
        owed = self.theses_owed()
        notes.append(f"reasoning: {len(owed)} owed (from "
                     f"{P.day(self.D.REVIEW_FROM)}, on entry and on exit)")
        gaps.extend(f"reasoning owed — {o['ticker']}"
                    + (f" in {o['account']}" if o["account"] else "")
                    + f": {o['half']}, since {P.day(o['since'])}" for o in owed)

        # ---- FUNDING: every night a daily funded leg was held has its row -----------------
        unfunded = self.funding_gaps()
        notes.append(f"funding: {len(self.D.DAILY_FUNDED_LEGS)} daily funded leg(s), "
                     f"{len(unfunded)} night(s) with no funding-interest row")
        gaps.extend(f"funding interest missing — {a}: {leg} held overnight {night} with no row"
                    for a, leg, night in unfunded)

        # ---- DATED RATES: every date a figure converts at has that day's close ----------
        owed = self.rate_gaps(today)
        notes.append(f"dated rates: {len(owed)} owed a TradingView close")
        gaps.extend(f"rate owed — {g['currency']} {P.day(g['date'])} ({g['why']}): no TradingView "
                    f"close on file for it" for g in owed)

        # ---- A DIVIDEND'S LINE: what lets a company's life count it ---------------------
        gaps.extend(f"dividend not assigned to a line — {r.date} {r.account}: {r.detail}"
                    for r in self.D.ci_rows if r.category == "Dividend" and not r.ticker
                    and pd.Timestamp(r.date) >= self.baseline)

        # ---- A BET LINE'S POINT: what turns a held bet into share-equivalents -----------
        L = self.ledger
        held_bets = sorted(set(L.loc[L["open_leg"] & L["held_as"].eq("spread bet"), "ticker"]))
        ident = self._identity().set_index("ticker")
        gaps.extend(f"points per unit owed — {code}: held, and securities.csv does not say how "
                    f"many points make one unit of its price"
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

    def _conversion_state(self) -> tuple[str, list[str]]:
        """Foreign-currency income, and how far its rate sat from the event: (note, problems).
        A PROBLEM past `rules.FX_RATE_AGE_LIMIT_DAYS`: the book would add a figure computed at a
        rate nobody fetched for the day, and the fix is to fetch one."""
        try:
            conv = self.conversions()
            if conv.empty:
                return "", []
            limit = self.D.FX_RATE_AGE_LIMIT_DAYS
            # THE ROWS WITH A RATE, for the furthest: a row with none has no distance, and the max
            # over it would raise, putting "could not be checked" in place of every problem below.
            apart = [int(d) for d in conv["days_apart"] if d is not None and pd.notna(d)]
            note = (f"conversions: {len(conv)} foreign-currency income row(s) · "
                    + (f"rate up to {max(apart)}d before the event, limit {limit}d" if apart
                       else "none with a rate on file"))
            return note, [
                (f"{r.account} {str(r.date)[:10]}: {r.currency} {r.local_amount} converted at "
                 f"the close of {r.rate_date} — {r.days_apart} days before the event, past the "
                 f"{limit}-day limit. Fetch the rate for the day.") if pd.notna(r.days_apart)
                else (f"{r.account} {str(r.date)[:10]}: {r.currency} {r.local_amount} has no "
                      f"close on file on or before its date. Fetch the rate for the day.")
                for r in conv[conv["stale"]].itertuples()]
        except Exception as e:                       # noqa: BLE001 — never fail over this check
            # NOT CHECKED IS A PROBLEM, not a note: a check that cannot run must not read as good
            # order.
            return (f"conversions: unknown ({type(e).__name__})",
                    [f"conversions could not be checked: {type(e).__name__}: {e}"])

    def _evidence_chain(self) -> tuple[str, str | None]:
        """How many rows citing a broker document can reach it, in one line, and a problem if any
        cannot, whatever its date. A row that cites no document is not counted and is not a gap:
        an IG read is retrieved by the dealId it stores. The rows labelled `not-on-file` are
        counted beside it, so the line says how much of the record no document holds."""
        try:
            names = self.D.schema.filed_statements()
            if not names:
                return "evidence: _archive/statements/ is empty or absent — limb 3 unverifiable", None
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
            line = (f"evidence: {cites - len(gaps)} of {cites} rows citing a document reach it "
                    f"in _archive/statements/ · {absent} not on file")
            if not gaps:
                return line, None
            return (f"{line} · {len(gaps)} cannot",
                    f"{len(gaps)} row(s) cite a document that is in no archived filename: "
                    f"{', '.join(sorted(gaps))} — file it, or correct the row's source")
        except Exception as e:                       # noqa: BLE001 — never fail over provenance
            # NOT CHECKED IS A PROBLEM, as the conversions' is.
            return (f"evidence: unknown ({type(e).__name__})",
                    f"the evidence chain could not be checked: {type(e).__name__}: {e}")

    def _journal_state(self) -> tuple[str, str | None]:
        """What the journal accounts for, in one line, and a problem if it could not be read. A
        difference is a FINDING, not a problem: a hand edit with a commit message is a correction
        the store allows."""
        try:
            opened = self.journal_opened()
            if opened is None:
                return "journal: no opening count — nothing to reconcile against", None
            off = self.journal_unaccounted()
            wrote = self.journal(since=opened)
            if off.empty:
                return (f"journal: every row accounted for since {P.day(pd.Timestamp(opened))} · "
                        f"{len(wrote)} write(s) recorded"), None
            parts = "; ".join(f"{r['table']} {r['unaccounted']:+d}"
                              for r in off.to_dict("records"))
            return (f"journal: {len(off)} table(s) hold rows no route accounts for — {parts}. "
                    f"That is a hand edit; git log will say which."), None
        except Exception as e:                       # noqa: BLE001 — never fail over the journal
            return (f"journal: unknown ({type(e).__name__})",
                    f"the journal could not be checked: {type(e).__name__}: {e}")
