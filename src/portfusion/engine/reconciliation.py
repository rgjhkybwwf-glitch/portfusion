"""The Book against the brokers' statements."""

from __future__ import annotations

import pandas as pd

from portfusion.record import rules as D
from portfusion.engine.store import utc_of
from portfusion.engine.core import Core
from portfusion.house import precision as P


class Reconciliation(Core):

    # ---- RECONCILIATION  —  the book against the brokers' statements -----------------

    def statements(self) -> pd.DataFrame:
        """Every broker statement reading, as loaded: one row per account per as_of date. Callers
        ask here rather than reading the file, so the file has one parser, not three."""
        return self.store["statements"].copy()

    def reconciliation(self) -> pd.DataFrame:
        """Each account against its statement: what the book says, what the broker said.

        THE DIFFERENCE COLUMN IS THE POINT: near zero means the book's own figures explain the
        account's movement; anything else is a question. `cash_at_recon` is the cash on or
        before the reading's date, which a share reading's total rests on; an account's newest
        cash is `newest_cash()`, a different fact.
        """
        # THE BOOK'S OWN NUMBER FOR A SPREAD-BET ACCOUNT IS THE DERIVED ONE — capital in, plus
        # realised, unrealised and income — because that is the figure with something to prove.
        # Using the broker's equity here compares the statement with itself: a reconciliation that
        # cannot fail is a decoration.
        #
        # PINNED TO THE READING, NOT TO NOW: valued at the marks of the reading's own instant, so a
        # later sweep cannot move a verdict already struck. A difference that appears only at later
        # marks is the market, not the book.
        _nav_cache: dict[str, dict] = {}

        def _nav_at(day: str | None) -> dict:
            key = str(day)[:10] if day else ""
            if key not in _nav_cache:
                _nav_cache[key] = (self.by_account(key) if key else self.by_account()) \
                    .set_index("account")["nav"].to_dict()
            return _nav_cache[key]
        rows = []
        for a in self.D.ACCOUNT_ORDER:
            r = next((x for x in self.D.ac_rows if x.acct == a), None)
            if r is None:
                continue
            # TWO CHECKS, ONE PER KIND OF ACCOUNT. A SPREAD-BET ACCOUNT'S BOOK SIDE IS ITS
            # DERIVED EQUITY — never cells typed off the statement it is compared against, which
            # can only ever agree with it — valued at the reading's own instant and compared by
            # value. A SHARE ACCOUNT IS CHECKED ON UNITS at the door that
            # took its holdings document, so nothing is valued here: its verdict follows from the
            # evidence class, in `reconciliation_verdict()`.
            sb = self.is_spread_bet(a)
            if sb:
                comparable, why = self.comparability(a, r.as_of, r.evidence, r.at)
                book_total = _nav_at(r.as_of).get(a)
            else:
                comparable, why, book_total = None, "", None
            struck_on = str(r.as_of)[:10] if r.as_of else ""
            # A SPREAD-BET READING IS IG'S FIVE FIGURES: its cash is the funds, its total the
            # equity. A SHARE READING HOLDS ITS STOCK ALONE: its cash is the account's newest cash
            # reading on or before the reading's date — the one its own document wrote, where it
            # states cash — and its total the two together.
            if sb:
                cash, cash_on, total = r.funds, struck_on if r.funds is not None else None, r.equity
            else:
                held = self._cash_at_reading.get(a)
                cash = held.cash if held else None
                cash_on = held.as_of.isoformat() if held else None
                total = (round(r.positions + held.cash, 2)
                         if held and r.positions is not None else None)
            rows.append({
                "account": a,
                "positions": r.positions,
                "cash_at_recon": cash,
                "cash_at_recon_at": cash_on,
                "equity": r.equity,
                # IG'S OWN FIGURES on a spread-bet reading, under IG's names; None on a share.
                "funds": r.funds, "running_pl": r.running_pl, "deposit": r.deposit,
                "available": r.available,
                "book": book_total,
                "statement": total,
                "difference": (book_total - total)
                              if (total is not None and book_total is not None) else None,
                "as_of": r.asof,
                # The typed date the book's side is pinned to, beside the display string, so a
                # reader of this frame never parses the sentence back.
                "struck_on": struck_on,
                "at": r.at,
                # FOR AN IG READING: do the two sides describe the same market state, and why.
                # Measured here; CLASSIFIED by reconciliation_verdict().
                "comparable": comparable,
                "comparability": why,
                # THE EVIDENCE CLASS, so a reader of this frame can ask what KIND of figure the
                # broker side is without parsing `as_of`. `reconciliation_verdict()` takes this.
                "evidence": r.evidence,
            })
        return pd.DataFrame(rows, columns=[
            "account", "positions", "cash_at_recon", "cash_at_recon_at", "equity", "funds",
            "running_pl", "deposit", "available", "book", "statement", "difference", "as_of",
            "struck_on", "at", "comparable", "comparability", "evidence"])

    def newest_cash(self) -> pd.DataFrame:
        """Each account's newest cash on file and what it was read from: one row per account in
        ACCOUNT_ORDER — account, cash, as_of (ISO), and document, the evidence class's label —
        None throughout where the record holds none.

        ONE PLACE PER KIND: a share account's cash readings (`cash_latest()`), and a spread-bet
        account's FUNDS, under IG's own name on its reading.
        """
        rows = []
        for a in self.D.ACCOUNT_ORDER:
            if self.is_spread_bet(a):
                r = next((x for x in self.D.ac_rows if x.acct == a), None)
                best = ((r.as_of, r.funds, r.evidence)
                        if r is not None and r.funds is not None and r.as_of else None)
            else:
                o = self._cash_latest.get(a)
                best = (o.as_of, o.cash, o.evidence) if o else None
            ev = self.D.EVIDENCE_BY_KEY.get(best[2]) if best else None
            rows.append({"account": a, "cash": best[1] if best else None,
                         "as_of": best[0].isoformat() if best else None,
                         "document": ev.label if ev else None})
        # OBJECT, so None stays None (quarter_evidence() says why).
        return pd.DataFrame(rows, columns=["account", "cash", "as_of", "document"], dtype=object)

    def units_check(self, account: str, as_of: str,
                    broker_units: dict[str, float]) -> pd.DataFrame:
        """THE SHARE-ACCOUNT CHECK: each holding's units in the book at
        `as_of` against a broker's holdings export. Units are COUNTED, not valued, so the check
        is exact — no mark, no band, no time of day. A holding one side has and the other does
        not is a row with 0 on the empty side.

        Columns: ticker, book, broker, agrees. Side effects: none.
        """
        held = self.as_of(as_of, account)
        book = {str(t): float(q) for t, q in zip(held["ticker"], held["qty"]) if float(q)}
        rows = [{"ticker": t, "book": book.get(t, 0.0), "broker": float(broker_units.get(t, 0.0))}
                for t in sorted(set(book) | set(broker_units))]
        out = pd.DataFrame(rows, columns=["ticker", "book", "broker"])
        out["agrees"] = (out["book"] - out["broker"]).abs() < 1e-9
        return out

    def comparability(self, account: str, as_of, evidence, at=None) -> tuple[bool, str]:
        """Does a SPREAD-BET account's broker reading describe the SAME STATE OF THE MARKET as the
        book's side?

        An IG reading is an instant on the broker's server that cannot be fetched again, so it
        compares only against marks struck LIVE in the same pass — which `feeds/refresh.py`
        produces by fetching the levels and the equity in one visit. A band wide enough to absorb
        a session is wider than the errors a reconciliation exists to catch, so the test is
        comparability, not tolerance. A SHARE ACCOUNT IS NOT ASKED THIS: it
        is checked on units at the door, which a close does not move.

        A MARK THAT DOES NOT SAY WHICH INSTANT IT DESCRIBES COMPARES WITH NOTHING. One pass is the
        reading's day, and no mark of it struck after the reading's own instant `at`: a later read
        of that day takes the earlier one's place, so the reading would meet levels it never saw.

        Returns `(comparable, why)`, `why` in a reader's words, so a renderer never composes it.

        Side effects: none.
        """
        ev = self.D.EVIDENCE_BY_KEY.get(str(evidence or ""))
        if ev is None or ev.retrieval != "reading":
            return False, f"{evidence!r} is not a live reading, and only a reading is compared"
        day = str(as_of)[:10]
        try:
            held = self.holdings_at(day, account)
        except (KeyError, ValueError) as exc:
            return False, f"the book cannot be valued at {day} — {exc}"
        if held.empty:
            return False, f"the book holds nothing in this account at {day}"

        # BY MARK KEY, NOT BY HOLDING TICKER. A spread bet holds "HALV SB" and is priced from
        # "HALV-DEC26" and "HALV-MAR27"; looking the holding's own name up in the price history
        # finds nothing and reports every IG account as unable to say what it was struck at.
        struck = self._struck_at(day)
        keys = {k for (_tk, k) in self._held_by_mark_key(day, account)}
        kinds = {struck.get(k, "") for k in keys} or {""}
        newest = max(str(d)[:10] for d in held["priced_at"])
        stalest = min(str(d)[:10] for d in held["priced_at"])
        if "" in kinds:
            return False, "a mark on this account does not say which instant it describes"
        if kinds != {"live"}:
            return False, "a live read compares only with live marks, and these are closes"
        if not (stalest == newest == day):
            return False, (f"the equity was read on {day} and the marks are from "
                           f"{stalest if stalest == newest else stalest + ' to ' + newest}"
                           f" — not one pass")
        if at:
            live = self.store["prices"]
            live = live[live["mark_key"].isin(keys) & (live["as_of"].astype(str).str[:10] == day)
                        & (live["at"].fillna("").astype(str) != "")]
            read = pd.Timestamp(utc_of(at))
            later = sorted(k for k, t in zip(live["mark_key"], live["at"])
                           if pd.Timestamp(utc_of(t)) > read)
            if later:
                return False, (f"{', '.join(later)} struck after the equity was read at "
                               f"{utc_of(at)} — not one pass")
        return True, "read in one pass"

    def _struck_at(self, as_of: str) -> dict:
        """What instant each mark on or before a date was struck at — `close` or `live`.

        Beside `_marks_at()`, not inside it: four callers unpack that one's (date, price) tuples
        positionally.

        Side effects: none.
        """
        ph = self.store["history.prices"]
        out: dict[str, tuple] = {}
        for row in ph[ph["date"] <= as_of].itertuples():
            cur = out.get(row.mark_key)
            if cur is None or row.date >= cur[0]:
                out[row.mark_key] = (row.date, str(getattr(row, "struck", "") or ""))
        return {k: v[1] for k, v in out.items()}

    #
    # A VERDICT IS A CLASSIFICATION, and a renderer may not classify, so it sits here beside the
    # frame it judges. Sharing a constant stops a band drifting between readers; sharing the
    # function stops the LOGIC drifting, and the logic is the part with branches.
    @staticmethod
    def reconciliation_verdict(statement: float | None, difference: float | None,
                               evidence: str | None, comparable: bool | None = None,
                               why: str = "") -> dict:
        """Whether one reconciliation row ties, and on which of the rules.

        TWO CHECKS, ONE PER KIND OF ACCOUNT, told apart by the evidence class
        (`rules.EVIDENCE_BY_KEY`):

          a READING (an IG account)  its equity against the book's, struck in one pass, held to
                                     `rules.RECON_LIVE_TOLERANCE_PCT` — the DERIVATION band: FX,
                                     rounding, bid against last. Not struck in one pass, it is
                                     not judged but reported as a gap.
          a HOLDINGS EXPORT          a share account, checked on UNITS at the door that took it.
                                     A reading on file means they agreed,
                                     and the audit re-reads the document. No value is compared.
          anything else              lists no units, so a gap, owed an export.

        AN ACCOUNT WITH NO STATEMENT IS NEITHER A PASS NOR A FAILURE; "ties" would be the worst
        answer available.

        Returns {checkable, live, band, ties, verdict, rule}. `verdict` is one of:
          "no-statement"  nothing to check against — a GAP
          "no-holdings"   a share account whose reading lists no units — a GAP
          "units-agree"   a share account whose holdings export agreed on units
          "struck-apart"  an IG reading not struck in one pass with the marks — a GAP
          "within-band"   an IG pair inside the derivation band
          "differs"       past the band. A difference is a defect until explained.

        `rule` is the verdict in a reader's words, here so every renderer says it the same way.
        It carries no date: agreement is of the reading's day, and a page heads that day itself,
        with the document behind it (`quarter_evidence()`).

        Side effects: none.
        """
        missing = statement is None or (isinstance(statement, float) and statement != statement)
        if missing:
            return {"checkable": False, "live": False, "band": None, "ties": None,
                    "verdict": "no-statement", "rule": "nothing to check against"}
        ev = D.EVIDENCE_BY_KEY.get(str(evidence or ""))
        if ev is None or ev.retrieval != "reading":
            if ev is not None and ev.key in D.HOLDINGS_COLUMNS:
                return {"checkable": True, "live": False, "band": None, "ties": True,
                        "verdict": "units-agree",
                        "rule": "units agree with the broker's holdings"}
            return {"checkable": False, "live": False, "band": None, "ties": None,
                    "verdict": "no-holdings",
                    "rule": f"{ev.label if ev else evidence} lists no units — a holdings export "
                            f"is owed"}
        if comparable is False:
            return {"checkable": False, "live": True, "band": None, "ties": None,
                    "verdict": "struck-apart",
                    "rule": why or "the equity and the marks were not read in one pass"}
        band = abs(statement) * D.RECON_LIVE_TOLERANCE_PCT
        ties = abs(difference or 0) < band
        return {"checkable": True, "live": True, "band": band, "ties": ties,
                "verdict": "within-band" if ties else "differs",
                "rule": f"{why or 'live read'} — band {P.money(band)}"}

    def quarter_readings(self, quarter_end: str | None, latest: bool = False,
                         checks: bool = False) -> pd.DataFrame:
        """Each account's broker reading that checks a quarter end: its FIRST dated from the
        quarter end to `rules.CLOSE_CHECK_WINDOW_DAYS` after it. One row per account that has
        one, in `statements()`'s shape.

        The quarter is valued at its own closes whenever they were banked; this is the broker's
        side, which may follow. A reading before the quarter end describes a different book and
        does not count.

        `latest=True` asks a different question: each account's NEWEST reading up to the end of
        that window, whenever it fell — the last check a report can cite. A share account is
        checked on units at any hour, so a check before the quarter end
        still stands. Bounded by the window, so the page regenerates the same once it has passed.
        With no `quarter_end`, it is each account's newest reading, unbounded: what the desk's
        Reconcile compares.

        `checks=True` keeps A BROKER'S CHECKS ALONE: a reading whose source names an evidence
        class. The history also copies the record's own figures where no freeze wrote them — the
        engine's derivation, an account not yet funded — and those check nothing.
        """
        st = self.statements()
        if checks:
            st = st[st["source"].map(lambda s: self.D.evidence_from_source(str(s)) is not None)]
        if quarter_end is None:
            return (st.sort_values("as_of").groupby("account", sort=False).tail(1)
                    .reset_index(drop=True))
        end = pd.Timestamp(quarter_end)
        day = pd.to_datetime(st["as_of"])
        until = end + pd.Timedelta(days=self.D.CLOSE_CHECK_WINDOW_DAYS)
        if latest:
            return (st[day <= until].sort_values("as_of").groupby("account", sort=False).tail(1)
                    .reset_index(drop=True))
        inside = st[(day >= end) & (day <= until)]
        return inside.sort_values("as_of").groupby("account", sort=False).head(1) \
                     .reset_index(drop=True)

    def quarter_evidence(self, quarter_end: str | None,
                         filed: list[str] | None = None) -> pd.DataFrame:
        """What each account's figure at a quarter end rests on: its last check, the kind of
        document behind it, and whether that document can be found again. One row per account,
        in ACCOUNT_ORDER — the three limbs of statement-grade, as a reader outside the repo meets
        them.

        The check is `quarter_readings(latest=True)`'s, and AT A QUARTER END ONLY A BROKER'S
        (`checks=True`): the newest reading whose source names an evidence class, so a page never
        cites the record's own figure as its check. `as_of` is None where there is none.
        `document` is its evidence class's label, None where the source names no class — which
        only the undated answer can give, since Reconcile shows the reading its row compares. `held`:

          "on file"                the cited document sits in `_archive/statements/`
          "NOT on file"            it cites one, and the archive does not hold it — whether
                                   the row says so (`not-on-file`) or not
          "read live"              A LIVE READ KEEPS NO DOCUMENT: nothing can be asked what the
                                   account was worth at that instant, and the row is the only
                                   copy
          "retrieved another way"  a classified source that cites no file
          None                     no classified source, or no check

        `filed` is the archive's names, so a test can say what is filed; None lists the folder.
        With no `quarter_end`, each account's newest reading: the reconciliation the desk shows.
        """
        if filed is None:
            filed = self.D.schema.filed_statements()
        at = self.quarter_readings(quarter_end, latest=True,
                                   checks=quarter_end is not None).set_index("account")
        rows = []
        for account in self.D.ACCOUNT_ORDER:
            if account not in at.index:
                rows.append({"account": account, "as_of": None, "document": None, "held": None})
                continue
            src = str(at.loc[account, "source"])
            ev = self.D.evidence_from_source(src)
            # THE ACCOUNT TOO: a line citing a dated statement and naming no account would
            # otherwise be "on file" on the strength of another account's statement.
            resolves = self.D.reference_resolves(src, filed, account=account)
            if ev and ev.retrieval == "none":
                ev, held = self.D.document_not_on_file(src) or ev, "NOT on file"
            elif resolves is not None:
                held = "on file" if resolves else "NOT on file"
            elif ev and ev.retrieval == "reading":
                held = "read live"
            else:
                held = "retrieved another way" if ev else None
            rows.append({"account": account, "as_of": str(at.loc[account, "as_of"]),
                         "document": ev.label if ev else None, "held": held})
        # OBJECT, so None stays None. pandas 3 infers its str dtype for a column of text and
        # None, and stores the None as NaN — which is truthy, so `document or ...` gives "nan".
        return pd.DataFrame(rows, columns=["account", "as_of", "document", "held"], dtype=object)
