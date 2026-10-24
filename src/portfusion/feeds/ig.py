"""
IG PRICE SWEEP — READ-ONLY. Spread-bet contract levels, account equity and the account's event
history, from IG's REST API; `feeds/tv.py` is its sibling for shares and FX, and `feeds/refresh.py`
reads both in one sweep.

It never writes the record: the API supplies the number and a precise source string, and the
judgement between them and the record stays yours.

WHY THE CONTRACT LEVEL AND NOT SPOT. Cost sits at the IG entry level, so the mark must be on the
same basis; marking a spread bet at spot subtracts across two bases in every unrealised figure.
The contract level is what IG's API returns.

A WRONG EPIC IS CAUGHT BY NOTHING HERE. Never guess one: `--ig-search` first, and `docs/prices.md`
before touching a mark.

NOT PART OF THE BUILD. The report must not import this: a build that reaches the network can fail
because a broker is down.

READ-ONLY, ENFORCED. IG's REST API can open and close real positions. `_assert_readonly()` refuses
anything outside `_ALLOWED` before a request is built, so there is no code path here that deals,
and adding one trips the guard rather than quietly working.

CREDENTIALS live in credentials.json in the book's folder (`schema.BOOK`, the folder
PORTFUSION_BOOK names), gitignored by `credentials.*`. Run any
command without it for the template. Nothing here logs, prints or transmits a credential.
"""
import sys
import os
import json
import time
import datetime as _dt
import urllib.request
import urllib.error
import urllib.parse

from portfusion.record import schema as _schema   # the book folder, whose keys these are
from portfusion.log import log
CREDENTIALS_FILE = os.path.join(_schema.BOOK, "credentials.json")

# IG's demo gateway has the same API surface: prove the login and the epic map there before
# touching a live account.
GATEWAYS = {
    "demo": "https://demo-api.ig.com/gateway/deal",
    "live": "https://api.ig.com/gateway/deal",
}

# =================================================================================================
# THE READ-ONLY GUARD
#
# THE ALLOWLIST EXPRESSES ONE RULE — READ-ONLY, NEVER DEALING — and is not a list of the endpoints
# this module happens to use. Every entry is a read with no side effect, and none trips a
# forbidden marker below. GET /positions is deliberately absent: it trips the "position" marker
# by name, and making the marker check method-aware would weaken a guard that is blunt on purpose.
# =================================================================================================
_ALLOWED = (
    "GET /markets/",          # a single instrument snapshot
    "GET /markets?",          # epic discovery by search term, and every mapped epic's snapshot
    "GET /accounts",          # whose account is this key on
    "GET /history/activity",  # what happened on the account: deal discovery
    "GET /history/transactions",   # closed trades and cash ledger, with IG's own P&L
    "GET /prices/",           # historical levels for an epic — a contract CAN be dated
    "POST /session",          # log in
    "DELETE /session",        # log out
)
_FORBIDDEN_MARKERS = ("position", "workingorder", "deal", "otc", "confirm")


class IGError(Exception):
    """An error IG returned. Carries the HTTP status and IG's own errorCode."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code


class CredentialsError(Exception):
    """credentials.json is missing, malformed, or half-filled.

    Its own class, not IGError — nothing has been sent to the broker when it fires. And raised,
    never sys.exit(): SystemExit walks through a server's `except Exception` and surfaces as a
    bare 500. A library must not decide for its caller that there is no recovering.
    """


def _assert_readonly(method, path):
    """Refuse anything that is not an allowed read, before the request is constructed.

    The second test is belt-and-braces against a future edit adding a path that happens to start
    with an allowed prefix.
    """
    call = f"{method} {path}"
    if not any(call.startswith(a) for a in _ALLOWED):
        raise RuntimeError(
            f"REFUSED: {call}\n"
            "feeds/ig.py is read-only. It may make only the calls _ALLOWED lists. If you are\n"
            "trying to add a dealing call, this is the guard telling you that this is the wrong\n"
            "file for it.")
    low = path.lower().split("?")[0]
    if any(m in low for m in _FORBIDDEN_MARKERS):
        raise RuntimeError(f"REFUSED: {call} — path looks like a dealing endpoint.")


# =================================================================================================
# CREDENTIALS
#
# IG's REST auth is NOT an API key alone: POST /session takes identifier + password + API key and
# returns a CST and an X-SECURITY-TOKEN. Three secrets per account.
# =================================================================================================
CREDENTIALS_TEMPLATE = """{
  "<the account's feed_key in store/accounts.csv>": {
    "identifier": "<the account's IG username>",
    "password":   "<its IG password>",
    "api_key":    "<the API key from My IG > Settings > API keys>",
    "account_id": "<e.g. ABC12>",
    "env":        "demo"
  }
}
One block per IG account."""


def load_credentials(path=CREDENTIALS_FILE):
    """Read credentials.json, or explain exactly what to create.

    The only place a credential is read; it returns them rather than keeping them at module level.
    """
    if not os.path.exists(path):
        raise CredentialsError(
            f"NO CREDENTIALS FILE — expected {path}\n\n"
            "Create it yourself; do not paste these values into a chat with Claude, and do not\n"
            "commit the file (.gitignore already excludes credentials.* — verify with:\n"
            "    git check-ignore -v credentials.json\n"
            ").\n\nThe shape:\n\n" + CREDENTIALS_TEMPLATE + "\n\n"
            "Set env to \"demo\" until the epic map is proved, then switch to \"live\".")
    with open(path) as fh:
        raw = json.load(fh)

    SECRETS = ("identifier", "password", "api_key")
    creds, skipped = {}, []
    for name, c in raw.items():
        # NOT EVERY ENTRY IS AN IG ACCOUNT: another service's API key may sit here too. The test
        # is for the KEYS — a block with no `identifier` and no `env` is someone else's and is
        # skipped; one that has them and leaves them empty is a half-configured IG account, and
        # is reported below.
        if not isinstance(c, dict) or ("identifier" not in c and "env" not in c):
            continue
        # An account still exactly as the template is not configured yet — normal, since accounts
        # are set up one at a time — and is skipped with a note.
        unfilled = [k for k, v in c.items()
                    if isinstance(v, str) and v.startswith("<") and v.endswith(">")]
        if all(k in unfilled for k in SECRETS):
            skipped.append(name)
            continue
        # A PARTLY filled account is a mistake, caught here rather than four calls later as a 401
        # that says nothing about which field was left alone.
        if unfilled:
            raise CredentialsError(
                f"credentials.json: {name} still has the template placeholder in "
                f"{', '.join(unfilled)} — fill it in or delete that account block")
        missing = [k for k in SECRETS + ("env",) if not c.get(k)]
        if missing:
            raise CredentialsError(f"credentials.json: {name} is missing {', '.join(missing)}")
        if c["env"] not in GATEWAYS:
            raise CredentialsError(
                f"credentials.json: {name} has env={c['env']!r}, expected 'demo' or 'live'")
        creds[name] = c

    if skipped:
        log.info(f"(not configured yet, skipping: {', '.join(skipped)})")
    if not creds:
        raise CredentialsError("credentials.json: no IG account is configured yet — fill one in")
    return creds


# =================================================================================================
# THE SESSION, AND ITS CACHE
#
# IG's tokens are valid six hours, extended up to 72 while in use, and IG asks for a session to
# be created once and reused. Logging in on every invocation gets the API key rate-limited, and a
# retry makes it worse. So the tokens are cached: the two tokens, their account, and when they
# were saved. They are bearer credentials the FULL API accepts, dealing included, so the file is
# 0600, gitignored, and kept beside credentials.json.
# =================================================================================================
SESSION_CACHE = os.path.join(_schema.BOOK, ".ig_session.json")
SESSION_MAX_AGE_HOURS = 5      # tokens last 6; refresh before the edge rather than at it


def _load_session_cache():
    try:
        with open(SESSION_CACHE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}               # absent or corrupt is not an error — just log in again


def _save_session_cache(cache):
    with open(SESSION_CACHE, "w") as fh:
        json.dump(cache, fh, indent=2)
    os.chmod(SESSION_CACHE, 0o600)


def clear_session_cache(label=None):
    cache = _load_session_cache()
    if label is None:
        cache = {}
    else:
        cache.pop(label, None)
    _save_session_cache(cache)


class IGSession:
    """An IG REST session, reusing cached tokens where they are still good."""

    def __init__(self, cred, label="?"):
        self.base = GATEWAYS[cred["env"]]
        self.env = cred["env"]
        self.label = label
        self.api_key = cred["api_key"]
        self._cred = cred
        self.cst = None
        self.token = None
        self.account_id = None
        self._from_cache = False
        self._relogged = False

    def _request(self, method, path, version, body=None):
        _assert_readonly(method, path)
        url = self.base + path
        headers = {
            "X-IG-API-KEY": self.api_key,
            "Version": str(version),
            "Accept": "application/json; charset=UTF-8",
            "Content-Type": "application/json; charset=UTF-8",
        }
        if self.cst:
            headers["CST"] = self.cst
            headers["X-SECURITY-TOKEN"] = self.token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode() or "{}")
                return payload, dict(resp.headers)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            # IG returns a machine-readable errorCode. Raised rather than exited so a caller can
            # act on the code — one of them is transient and worth a retry, see __enter__.
            try:
                code = json.loads(detail).get("errorCode", "")
            except ValueError:
                code = ""
            # A cached token IG has since expired looks exactly like a broken tool: drop the cache,
            # authenticate once, replay. Guarded, so a genuine auth failure cannot become a login
            # loop — the thing that gets the key rate-limited.
            stale = (self._from_cache and not self._relogged
                     and path != "/session" and code.startswith("error.security"))
            if stale:
                self._relogged = True
                clear_session_cache(self.label)
                self._from_cache = False
                self.cst = self.token = None
                self._login()
                return self._request(method, path, version, body)
            raise IGError(e.code, code, f"IG API {e.code} on {method} {path} "
                                        f"({self.label}, {self.env})\n  {detail}")

    def _login(self):
        """POST /session. The ONLY place this module authenticates."""
        payload, headers = self._request(
            "POST", "/session", 2,
            {"identifier": self._cred["identifier"],
             "password": self._cred["password"],
             "encryptedPassword": False})
        self.cst = headers.get("CST")
        self.token = headers.get("X-SECURITY-TOKEN")
        if not self.cst or not self.token:
            raise IGError(0, "", f"{self.label}: login returned no session tokens")
        self.account_id = payload.get("currentAccountId")
        self._from_cache = False
        cache = _load_session_cache()
        cache[self.label] = {"env": self.env, "cst": self.cst, "token": self.token,
                             "account_id": self.account_id,
                             "saved": _dt.datetime.now().isoformat(timespec="seconds")}
        _save_session_cache(cache)

    def __enter__(self):
        entry = _load_session_cache().get(self.label)
        if entry and entry.get("env") == self.env:
            try:
                age_h = (_dt.datetime.now()
                         - _dt.datetime.fromisoformat(entry["saved"])).total_seconds() / 3600
            except (KeyError, ValueError):
                age_h = 1e9
            if age_h < SESSION_MAX_AGE_HOURS:
                self.cst, self.token = entry.get("cst"), entry.get("token")
                self.account_id = entry.get("account_id")
                self._from_cache = True
                return self
        self._login()
        return self

    def __exit__(self, *exc):
        # NO LOGOUT, deliberately: logging out forces the next command to authenticate again.
        # The tokens expire on their own; --ig-logout ends one early.
        return False

    def markets(self, epics):
        """EVERY EPIC'S SNAPSHOT IN ONE CALL, so the levels describe one instant.

        Keyed by epic, and an epic IG does not answer for is ABSENT, never a zero. `update_time`
        is IG's `updateTime`, which is UTC and carries no date; `delay` is IG's own `delayTime`,
        in minutes. NOT `filter=SNAPSHOT_ONLY`: that returns the instrument's name, expiry and
        currency as nulls.
        """
        query = urllib.parse.urlencode({"epics": ",".join(epics)})
        payload, _ = self._request("GET", f"/markets?{query}", 2)
        out = {}
        for d in payload.get("marketDetails") or []:
            inst, snap = d.get("instrument") or {}, d.get("snapshot") or {}
            out[inst.get("epic")] = {
                "epic": inst.get("epic"),
                "name": inst.get("name", ""),
                "expiry": inst.get("expiry", ""),
                "currency": (inst.get("currencies") or [{}])[0].get("code", ""),
                "bid": snap.get("bid"),
                "offer": snap.get("offer"),
                "status": snap.get("marketStatus", ""),
                "update_time": snap.get("updateTime", ""),
                "delay": snap.get("delayTime") or 0,
            }
        return out

    def bars(self, epic, resolution, start, end):
        """IG's own bars for one epic between two instants, as IG returns them."""
        query = urllib.parse.urlencode({"resolution": resolution, "from": start, "to": end})
        payload, _ = self._request("GET", f"/prices/{urllib.parse.quote(epic)}?{query}", 3)
        return payload.get("prices") or []

    def close_bar(self, epic, on):
        """IG's HOUR bar opening at `CLOSE_BAR_UK` on `on`, or None unless IG QUOTED THE CONTRACT
        THROUGH THE EVENING: every hour bar from `QUOTED_FROM_UK` to it carries a close.

        Matched on IG's UTC stamps against those UK times, so the clock change needs no case of
        its own. The window holds the evening whichever clock IG reads `from` and `to` in.
        """
        from zoneinfo import ZoneInfo

        def utc(hour):
            return (_dt.datetime.fromisoformat(f"{on}T{hour:02d}:00:00")
                    .replace(tzinfo=ZoneInfo("Europe/London")).astimezone(_dt.timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%S"))
        got = {b.get("snapshotTimeUTC"): b
               for b in self.bars(epic, "HOUR", f"{on}T16:00:00", f"{on}T23:59:59")}
        evening = [got.get(utc(h))
                   for h in range(int(QUOTED_FROM_UK[:2]), int(CLOSE_BAR_UK[:2]) + 1)]
        if all(((b or {}).get("closePrice") or {}).get(PRICE_SIDE) is not None for b in evening):
            return evening[-1]
        return None

    def search(self, term):
        """Epic discovery. The map below cannot be guessed — it is read off this."""
        payload, _ = self._request(
            "GET", "/markets?searchTerm=" + urllib.parse.quote(term), 1)
        return payload.get("markets", [])


# =================================================================================================
# THE EPIC MAP — store/contracts.csv, filled from --ig-search and verified against a statement,
# never guessed.
#
# An epic is an opaque code, and a WRONG one is the worst failure available: a plausible price for
# the wrong contract, a clean build, a clean audit. So:
#
#   * MATCH ON THE INSTRUMENT NAME AS WELL AS THE EXPIRY. A search returns leveraged ETPs on the
#     same company with the same expiries.
#   * TAKE THE LINE THAT QUOTES IN THE RECORD'S CURRENCY. Other venues' lines of the same names are
#     the trap, and currency alone rules them out.
#   * A level is instrument data, not account data: either session may read any epic.
# =================================================================================================
def epics(D=None) -> dict:
    """contract -> (the feed label of the account whose legs are on it, epic), for every contract
    contracts.csv gives an epic. A closed contract has none, and nothing reads its level again."""
    D = D or _record()
    label_of = {v: k for k, v in account_names(D).items()}
    acct_of = {t.contract: t.acct for t in D.buys if t.contract}
    return {c: (label_of.get(acct_of.get(c)), epic) for c, epic in sorted(D.CONTRACTS.items()) if epic}

# IG quotes spread bets in POINTS and the record keeps the level as IG states it (10000.5 stays
# 10000.5): the unit every bet leg, sale, mark and frozen line is in, the stake being £ per point.

# WHICH SIDE OF THE SPREAD: THE BID. IG values an open LONG at the bid; a short is valued at the offer,
# and the record holds longs only. Levels and /accounts read together reproduce IG's own running P/L
# exactly; a wrong side would sit a spread out, in one direction, on every leg.
# Every print still shows bid, offer and mid, so the next check stays cheap.
PRICE_SIDE = "bid"

# A PAST DAY'S CLOSE IS THE HOUR BAR OPENING AT 21:00 UK: it ends at 22:00, when an IG statement
# values every position. Its close is the printed level on the near contracts; the DAY bar's close
# is not.
# ONLY WHERE IG QUOTES THE CONTRACT THROUGH THE EVENING. A near contract has a priced bar each
# hour from 18:00; a far one has none, or empty bars, and its statement level matches no bar.
# A far contract's close is that day's statement level.
CLOSE_BAR_UK = "21:00"
QUOTED_FROM_UK = "18:00"


def _level(snap, side=PRICE_SIDE):
    raw = snap[side]
    return None if raw is None else float(raw)


# =================================================================================================
# COMMANDS
# =================================================================================================
def cmd_search(terms):
    """Find the epics for one or more underlyings, in a SINGLE session.

    IG refuses a login too soon after the last session closed, so one login per term makes a
    multi-name search fail about half the time.
    """
    with _instrument_session() as s:
        log.info(f"\nSearching IG ({s.env}) as {s.label}: {', '.join(terms)}\n")
        for i, term in enumerate(terms):
            if i:
                time.sleep(1.0)          # IG rate-limits; be polite between searches
            markets = s.search(term)
            log.info(f"=== {term} " + "=" * (58 - len(term)))
            if not markets:
                log.info("  no markets returned\n")
                continue
            log.info(f"  {'EPIC':<38} {'EXPIRY':<10} {'TYPE':<14} NAME")
            log.info(f"  {'-'*38} {'-'*10} {'-'*14} {'-'*40}")
            for m in markets:
                log.info(f"  {m.get('epic',''):<38} {m.get('expiry',''):<10} "
                      f"{m.get('instrumentType',''):<14} {m.get('instrumentName','')}")
            log.info("")
    log.info("  Add each contract and its epic to store/contracts.csv. Match the EXPIRY to the")
    log.info("  contract key: DEC-26 -> *-DEC26, MAR-27 -> *-MAR27, '-' or 'DFB' -> *-DFB.")
    log.info("  READ THE NAME, not just the expiry — a search for one company returns leveraged")
    log.info("  ETPs on it too, and those carry the same expiries and quote plausible prices.\n")


def _utc_now() -> str:
    """This instant in UTC, as a mark's `at` is written."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _less(at, minutes):
    """A UTC instant, `minutes` earlier."""
    t = _dt.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ") - _dt.timedelta(minutes=minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _instrument_session():
    """THE ONE SESSION EVERY INSTRUMENT READ GOES THROUGH, levels and bars alike.

    Either account reads any epic to the point (the note on `epics()`), so one login serves every
    contract whichever account holds the leg, and each row names the session that read it
    (`read_via`). Where the account itself is the answer, `account_state()` still asks
    each account for its own.
    """
    creds = load_credentials()
    label = next(iter(creds))
    return IGSession(creds[label], label)


def _each_epic(fetch):
    """`fetch(session, epic)` for every mapped contract, through the one session, by contract.

    For IG's PER-EPIC reads, its bars; a level has a batch call and never comes here. The reads
    are spaced because IG caps requests per minute.
    """
    out = {}
    with _instrument_session() as s:
        for i, (key, (holder, epic)) in enumerate(epics().items()):
            if i:
                time.sleep(1.0)
            out[key] = {**fetch(s, epic), "account": holder, "read_via": s.label, "env": s.env}
    return out


def contract_levels(mapped=None):
    """THE IG CONTRACT SWEEP, AS DATA. What `feeds/refresh.py` prints and the desk ticks.
    `mapped` ({contract: (holder, epic)}) reads only those: a new contract's first mark.

    ONE CALL FOR EVERY CONTRACT, through one session, so the levels describe one instant and the
    equity `account_state()` reads beside them meets them there. `priced` is False when IG
    returned no bid, and the unpriced row is KEPT: a shorter list gives a caller no way to know a
    contract failed.

    EACH ROW IS A WHOLE MARK — `as_of`, `source`, `struck` and `at` — so no caller composes one.
    `at` is the instant IG was ASKED, less any delay IG declares, because IG values the account on
    the level it quotes then. `updateTime` says when the level last moved, and stays in the source
    as evidence. A level whose currency is not the record's is kept, unpriced, as `feeds/tv.py`
    keeps a line whose unit is wrong.
    """
    from portfusion.record import rules as D
    held_in = {t: c for t, _p, c, *_ in D.CURRENT_PRICES}
    with _instrument_session() as s:
        mapped = mapped or epics(D)
        snaps = s.markets([epic for _holder, epic in mapped.values()])
        read_at, via, env = _utc_now(), s.label, s.env
    rows = []
    for key in sorted(mapped):
        holder, epic = mapped[key]
        snap = snaps.get(epic) or {
            "name": "", "expiry": "", "currency": "", "bid": None, "offer": None,
            "status": "IG returned no snapshot", "update_time": "", "delay": 0}
        wrong_unit = not snap["currency"] or snap["currency"] != held_in.get(key, snap["currency"])
        if snap["bid"] is not None and wrong_unit:
            # A mark in the wrong currency is a wrong mark, however right the number.
            snap = {**snap, "bid": None, "offer": None,
                    "status": f"IG quotes it in {snap['currency'] or 'no currency'}, "
                              f"the record in {held_in.get(key)}"}
        bid, offer = _level(snap, "bid"), _level(snap, "offer")
        priced = bid is not None and offer is not None
        at = _less(read_at, snap["delay"])
        rows.append({
            "as_of": D.uk_date(at), "struck": "live", "at": at,
            "source": (f"IG REST {env} {epic}, {PRICE_SIDE} {snap[PRICE_SIDE]}, "
                       f"IG updateTime {snap['update_time']} UTC"
                       + (f", IG delayTime {snap['delay']} min" if snap["delay"] else "")
                       + f", market {snap['status']}") if bid is not None else "",
            "contract": key, "epic": epic, "name": snap["name"], "expiry": snap["expiry"],
            "currency": snap["currency"], "account": holder, "read_via": via, "env": env,
            "status": snap["status"], "update_time": snap["update_time"],
            "bid": bid, "offer": offer,
            "mid": round((bid + offer) / 2, 3) if priced else None,
            "spread": round(offer - bid, 3) if priced else None,
            "level": _level(snap), "raw": snap[PRICE_SIDE], "priced": bid is not None,
        })
    return {"today": _dt.date.today().isoformat(), "side": PRICE_SIDE, "rows": rows}


def contract_closes(on):
    """EVERY CONTRACT'S LEVEL AT ONE DAY'S CLOSE, AS DATA — a quarter end fetched after the day.

    The close of `IGSession.close_bar()`, on the side a live level uses, in points, so the book
    values that day at the level IG's own statement prints. A CLOSE, not a live read: the row
    says `struck="close"` and its source names the bar. A contract IG did not quote through the
    evening comes back unpriced and is KEPT, as in `contract_levels()`, and its status says where
    the level is.
    """
    bars = _each_epic(lambda session, epic: {"epic": epic, "bar": session.close_bar(epic, on)})
    rows = []
    for key in sorted(bars):
        b = bars[key]
        close = (b.get("bar") or {}).get("closePrice") or {}
        raw = close.get(PRICE_SIDE)
        priced = raw is not None
        rows.append({
            "contract": key, "epic": b["epic"], "account": b["account"],
            "read_via": b["read_via"], "env": b["env"],
            "as_of": on, "raw": raw, "bid": close.get("bid"), "offer": close.get("ask"),
            "level": float(raw) if priced else None, "priced": priced,
            "struck": "close", "at": "",
            "status": "CLOSE" if priced else (f"not quoted through the evening of {on}; "
                                              f"that day's IG statement prints its level"),
            "source": (f"IG REST {b['env']} /prices/{b['epic']} HOUR bar {on} {CLOSE_BAR_UK} "
                       f"UK, close {PRICE_SIDE} {raw}") if priced else "",
        })
    return {"today": _dt.date.today().isoformat(), "on": on, "side": PRICE_SIDE, "rows": rows}


def verify_levels():
    """LIVE LEVELS AGAINST THE RECORD, AS DATA. The comparison, without the table.

    `state` is the branch a reader has to handle, named rather than inferred:
      "ok"        both figures exist and `pct` is the move
      "new"       IG has a level for a contract the record does not carry
      "no-price"  the record has a mark and IG returned no bid

    A caller that treats a missing `pct` as zero would report a contract that failed to price
    as unchanged, which is the worst available answer. Hence the explicit state.
    """
    D = _record()
    stored = {t: (p, c, d) for t, p, c, d, *_ in D.CURRENT_PRICES}
    rows = []
    for level in contract_levels()["rows"]:
        key, live, status = level["contract"], level["level"], level["status"]
        if key not in stored:
            rows.append({"contract": key, "state": "new", "stored": None, "as_of": None,
                         "live": live, "pct": None, "status": status})
            continue
        old, _cur, asat = stored[key]
        if live is None:
            rows.append({"contract": key, "state": "no-price", "stored": old, "as_of": asat,
                         "live": None, "pct": None, "status": status})
            continue
        rows.append({"contract": key, "state": "ok", "stored": old, "as_of": asat, "live": live,
                     "pct": (live - old) / old * 100 if old else 0.0, "status": status})
    return {"side": PRICE_SIDE, "rows": rows}


def cmd_verify():
    """Compare live levels against what the record holds — the test the sweep must pass before it
    is trusted. Run it on a day you also have an IG statement: a fetched bid matching the
    statement's valuation level proves the epic map and the side of the spread at once.
    """
    r = verify_levels()
    log.info(f"\n{'CONTRACT':<14} {'STORED':>10} {'AS AT':<12} {'IG '+r['side'].upper():>10} "
          f"{'DIFF':>9}  STATUS")
    log.info("-" * 74)
    for row in r["rows"]:
        key, live, old, asat = row["contract"], row["live"], row["stored"], row["as_of"]
        if row["state"] == "new":
            # NO LEVEL IS A DASH: a wrong epic answers none, and None does not format.
            shown = "—" if live is None else live
            log.info(f"{key:<14} {'—':>10} {'not in record':<12} {shown:>10}   NEW")
            continue
        if row["state"] == "no-price":
            log.info(f"{key:<14} {old:>10.3f} {asat:<12} {'—':>10} {'':>9}  NO PRICE ({row['status']})")
            continue
        log.info(f"{key:<14} {old:>10.3f} {asat:<12} {live:>10.3f} {row['pct']:>8.2f}%  {row['status']}")
    log.info("\nA large diff is not automatically wrong — these are dated marks and the book's are")
    log.info("often a fortnight old. What you are checking is that each contract is PLAUSIBLE for its")
    log.info("expiry, and that longer-dated sits above nearer-dated, the term-structure sanity "
             "check.\n")


# The book's name for each IG account, keyed by the credential label. Stated, never derived from
# account_id: mapping one namespace to the other by guessing is how a figure lands on the wrong
# account.
def account_names(D=None) -> dict:
    """credentials.json label -> the book's account: the register's `feed_key` column."""
    D = D or _record()
    i = D.schema.TABLES["accounts"].header
    return {r[i.index("feed_key")]: r[0] for r in D.register if r[i.index("feed_key")]}


def account_state():
    """LIVE IG ACCOUNT STATE, AS DATA. Equity per account, and every reason one was refused.

    Returns {today, entries, rows, refusals}. `entries` is the ORDERED sequence the printer walks,
    each `{"kind": "row"|"refusal", ...}`; `rows` and `refusals` are the same items split out.

    THE REFUSALS ARE THE POINT. An account is refused when IG's own identity does not hold
    (`balance - deposit + profitLoss != available`), when it returns no balance figures, or when
    its label is no account's feed_key — each a way for a plausible number to reach the
    record on the wrong account or from a mis-parsed field. Dropping them removes the guard.
    """
    # The record, for evidence_source(). Deferred like _record()'s, so importing this
    # module still costs nothing and still reaches no store until something asks.
    from portfusion.record import rules as D
    creds = load_credentials()
    today = _dt.date.today().isoformat()
    entries = []

    def refuse(text):
        entries.append({"kind": "refusal", "text": text})

    for label in sorted(creds):
        with IGSession(creds[label], label) as sess:
            payload, _ = sess._request("GET", "/accounts", 1)
        for a in payload.get("accounts", []):
            if a.get("accountType") != "SPREADBET":
                continue
            bal = a.get("balance") or {}
            funds = bal.get("balance")
            pl = bal.get("profitLoss")
            deposit = bal.get("deposit")
            available = bal.get("available")
            if funds is None or pl is None:
                refuse(f"{label}: /accounts returned no balance figures — nothing written")
                continue
            equity = round(funds + pl, 2)
            name = account_names(D).get(label)
            if name is None:
                refuse(f"{label}: no account's feed_key in accounts.csv — add it rather than guessing "
                       f"which account in the record this is")
                continue
            # IG's own identity, checked rather than trusted: a mis-parsed field would other-
            # wise reach the record as a plausible balance.
            if available is not None and abs((funds - deposit + pl) - available) > 0.005:
                refuse(f"{label}: balance - deposit + profitLoss != available "
                       f"({funds} - {deposit} + {pl} != {available}) — REFUSING to print a row")
                continue
            # The provenance line is COMPOSED by rules.evidence_source(), so the record's vocabulary
            # decides its shape; the figures are this entry's own fields.
            source = D.evidence_source("ig-accounts", f"{a.get('accountId')}, read {today}")
            entries.append({
                "kind": "row", "label": label, "account": name, "as_of": today,
                "account_id": a.get("accountId"), "env": creds[label]["env"],
                "funds": funds, "running_pl": pl, "equity": equity, "deposit": deposit,
                "available": available, "positions_value": None, "quality": "sourced",
                "source": source,
            })
    return {"today": today, "entries": entries,
            "rows": [e for e in entries if e["kind"] == "row"],
            "refusals": [e for e in entries if e["kind"] == "refusal"]}


def _record():
    """The book, imported late: this module must stay importable without the record, and the
    build must never import this."""
    from portfusion.record import rules as D
    return D


def _epic_to_ticker(D):
    """epic -> the book's ticker: the code of the line its contract is on (contracts.csv). An
    epic no contract carries resolves to nothing, never to a guess: a wrong ticker would file a
    real trade against the wrong position."""
    return {epic: D.CONTRACT_CODE[c] for c, epic in D.CONTRACTS.items() if epic}


#: THE COLUMNS EACH GENERATED ROW FILLS, in the store's own order, BY NAME. tests/test_ig.py
#: asserts these against schema.TABLES.
ROW_COLUMNS = {
    "buys": ("trade_id", "date", "source", "account", "ticker", "cur", "qty", "stake", "cost",
             "level_points", "broker_ref", "note", "contract", "traded_price", "rate"),
    "sales": ("sale_id", "date", "account", "ticker", "qty", "stake", "traded_price", "cur",
              "rate", "proceeds", "source", "broker_ref", "realisation_id", "closes", "note"),
    # IG bills funding interest in the account currency, so a swept row leaves `currency`,
    # `local_amount` and `rate` blank, and `ticker`, since funding is no one line's — named
    # explicitly, or the paste misaligns.
    "income": ("date", "account", "category", "detail", "amount", "source", "note",
               "currency", "local_amount", "rate", "ticker"),
    "capital-movements": ("date", "account", "amount", "source", "detail"),
}


_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def contract_suffix(epic: str, day: str) -> dict:
    """A new contract's name after its line's root, and its funding, read off its epic: the
    month and the year it next falls on or after `day` (`-JUN27`), or `-DFB` for a daily-funded
    bet. The owner confirms both; a month the epic does not carry suggests nothing."""
    part = (epic.split(".") + ["", "", "", ""])[3]
    if part in ("DAILY", "CASH"):
        return {"suffix": "-DFB", "funding": "daily"}
    if part not in _MONTHS:
        return {"suffix": "", "funding": "dated"}
    on = _dt.date.fromisoformat(day)
    year = on.year + (_MONTHS.index(part) + 1 < on.month)
    return {"suffix": f"-{part}{year % 100:02d}", "funding": "dated"}


def _said(ticker, direction, stake, level=None, day=""):
    """AN EVENT IN THE TRADES PAGE'S WORDS: ticker, direction, stake per point, and the level in
    points or the day — "VELD SB · Sell · £1/pt · 10,000.5 pts"."""
    return " · ".join([ticker, direction, f"£{stake:g}/pt"]
                      + ([f"{level:,.10g} pts"] if level is not None else [])
                      + ([day] if day else []))


def _event(table, ref, kind, account, what, values):
    """One proposed row, as DATA: the table, the values by column name, and enough about the event
    for a reader or the bench to know what it is.

    `values` is a dict, not **kwargs: the store's `account` column would collide with this
    function's own `account` parameter.

    `line` is the CSV rendering the sweep prints, kept here so the printed block and anything
    carrying the row onward cannot disagree about what the row is.
    """
    missing = set(ROW_COLUMNS[table]) - set(values)
    if missing:
        # ValueError, not IGError: IG did not do anything wrong. A row built without every
        # column is a mistake in this file, and it must not survive long enough to be rendered.
        raise ValueError(f"{table} row for {ref} is missing {sorted(missing)} — "
                         f"every column is filled explicitly or the paste misaligns")
    ordered = {c: values[c] for c in ROW_COLUMNS[table]}
    return {"table": table, "values": ordered, "ref": ref, "kind": kind,
            "account": account, "what": what,
            # AS IT WILL BE WRITTEN: each figure to its places (`schema.cell()`).
            "line": _csv_row([_schema.cell(_field(table, c), v) for c, v in ordered.items()])}


def _field(table: str, column: str):
    """The schema's field for a column of a row this feed proposes."""
    return next(f for f in _schema.TABLES[table].fields if f.name == column)


def _csv_row(values):
    """One CSV line, quoted the way the store's own writer would quote it."""
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    _csv.writer(buf, lineterminator="").writerow(values)
    return buf.getvalue()


#: The page size the sweep asks for: IG's most for /history/activity (its reference: 10 to 500).
PAGE = 500

#: How many pages one sweep will follow before it stops and says so, so a paging link that never
#: ends cannot spin the allowance away.
MAX_PAGES = 50

#: A `WITH` line that is a FUNDING COST, by the words IG prints on it ("Long Interest for US/Can
#: shares 10/08/26"). Every other `WITH` is money leaving the account, proposed as capital.
FUNDING_WORDS = ("interest", "funding")


def _every_page(s, path, version, key):
    """Every row of one history endpoint across its pages, or a refusal: NEVER THE FIRST PAGE
    PASSED OFF AS THE WHOLE.

    /history/activity (v3) links its next page in `metadata.paging.next`; /history/transactions
    (v2) numbers them, `metadata.pageData.totalPages` (IG's API reference). A full page that says
    nothing about paging is refused, since what lies beyond it is unknown.
    """
    rows, page, number = [], None, 1
    for _ in range(MAX_PAGES):
        page, _ = s._request("GET", path, version)
        got = page.get(key) or []
        rows += got
        meta = page.get("metadata") or {}
        if "paging" in meta:
            nxt = (meta["paging"] or {}).get("next")
            if not nxt:
                return rows
            if not str(nxt).startswith("/history/"):
                raise IGError(None, "", f"IG's next page is {nxt!r}, not a history path")
            path = str(nxt)
        elif "pageData" in meta:
            if number >= int((meta["pageData"] or {}).get("totalPages") or 1):
                return rows
            number += 1
            path = f"{path.split('&pageNumber=')[0]}&pageNumber={number}"
        elif len(got) >= PAGE:
            raise IGError(None, "", f"{path.split('?')[0]} returned a full page of {len(got)} "
                                    f"and no paging: what follows it is unknown. Sweep a "
                                    f"shorter window (--since).")
        else:
            return rows
    raise IGError(None, "", f"{path.split('?')[0]} ran past {MAX_PAGES} pages; sweep a shorter "
                            f"window (--since).")


def ig_events(since=None):
    """Every IG event in a window, matched against the book, with paste-ready rows for whatever is
    missing. PRINTS, NEVER WRITES.

    Everything a spread-bet statement's deal and ledger sections carry, with the deal reference
    attached and no transcription step.

    WHAT IT WILL NOT DO:

      * Write. You paste, and the human read between a fetched number and the record stays.
      * Invent a ticker. An epic no contract carries is offered for set-up, never guessed.
      * Write the WHY. Every generated row carries a marker where the judgement belongs.

    THE WINDOW DEFAULTS TO 30 DAYS. Activity from before the record begins is not reconstructed
    backwards; use --since only when you mean to.
    """
    # The record, for evidence_source(), deferred through _record(), so importing this
    # module still costs nothing and still reaches no store until something asks.
    D = _record()
    creds = load_credentials()
    today = _dt.date.today()
    frm = since or (today - _dt.timedelta(days=30)).isoformat()
    to = today.isoformat()
    tick_of = _epic_to_ticker(D)

    known_open = {t.broker_ref for t in D.buys if t.broker_ref}
    # A CLOSE IS KNOWN BY ITS broker_ref, the closing deal IG gave it.
    known_close = {str(e.broker_ref).strip() for e in D.sales if str(e.broker_ref or "").strip()}
    # WHAT AN EVENT ALREADY IN THE BOOK IS, said from the book's own row.
    buy_of = {t.broker_ref: t for t in D.buys if t.broker_ref}
    sale_of = {str(e.broker_ref).strip(): e for e in D.sales if str(e.broker_ref or "").strip()}
    # WHAT A CLOSE BELONGS TO, from IG's own ids: the leg is the one whose broker_ref is the deal
    # the close names. The parcel is its ACCOUNT's holding's, `Book.parcel()`, the answer a
    # share sale on the bench gets: two accounts may bet on the same ticker, and a parcel named
    # by ticker alone would put one account's close into the other account's round trip. Asked
    # once per holding, so a second close in the same sweep joins the first.
    leg_of = {t.broker_ref: t.trade_id for t in D.buys if t.broker_ref}
    parcel_of, engine = {}, []

    def _parcel(acct, tk):
        if (acct, tk) not in parcel_of:
            if not engine:
                from portfusion.engine import Book
                engine.append(Book())
            parcel_of[(acct, tk)] = engine[0].parcel(acct, tk)
        return parcel_of[(acct, tk)]
    known_cash = {(c.date, round(c.amount, 2)) for c in D.ci_rows}
    known_moves = {(m[0], round(m[2], 2)) for m in D.movements}

    free = D.next_free_ids()
    nt, ne = int(free["buys"][2:]) - 1, int(free["sales"][2:]) - 1
    contract_of = {epic: c for c, (_holder, epic) in epics(D).items()}

    matched, rows_t, rows_e, rows_i, rows_m, skipped, setups = [], [], [], [], [], [], []
    seen_api_cash, swept = set(), set()
    for label in sorted(creds):
        acct = account_names(D).get(label, label)
        swept.add(acct)
        with IGSession(creds[label], label) as s:
            activities = _every_page(
                s, f"/history/activity?from={frm}T00:00:00&to={to}T23:59:59"
                   f"&detailed=true&pageSize={PAGE}", 3, "activities")
            transactions = _every_page(
                s, f"/history/transactions?from={frm}T00:00:00&to={to}T23:59:59"
                   f"&pageSize={PAGE}", 2, "transactions")

        for a in sorted(activities, key=lambda x: x["date"]):
            d = a.get("details") or {}
            for action in d.get("actions") or []:
                kind = action["actionType"]
                if kind not in ("POSITION_OPENED", "POSITION_CLOSED"):
                    continue
                ref, day = a["dealId"], a["date"][:10]
                closed_id = action.get("affectedDealId")
                # MATCH BEFORE RESOLVING THE TICKER. The closed contracts with no epic are
                # already in the book; an event already recorded needs no ticker, and reporting it
                # as unresolvable trains the reader to ignore the section that matters.
                if kind == "POSITION_OPENED" and ref in known_open:
                    t = buy_of[ref]
                    matched.append(_said(t.ticker, "Buy", t.stake, day=day) + " · in the book")
                    continue
                if kind == "POSITION_CLOSED" and (closed_id in known_close or ref in known_close):
                    e = sale_of.get(ref) or sale_of[closed_id]
                    matched.append(_said(e.ticker, "Sell", e.stake, day=day) + " · in the book")
                    continue
                tk = tick_of.get(a["epic"])
                market = d.get("marketName", "")
                if tk is None and kind == "POSITION_CLOSED":
                    skipped.append(f"{day} {ref} {a['epic']} {market} ({acct}) — not in the book")
                    continue
                size, level = d.get("size"), d.get("level")
                if kind == "POSITION_OPENED":
                    nt += 1
                    leg_of[ref] = f"T-{nt:03d}"        # a close later in this sweep can name it
                    # AN EPIC NO CONTRACT CARRIES is the first bet on a contract: offered for
                    # set-up with its line and contract, never filed against a guessed ticker.
                    (rows_t if tk else setups).append(_event(
                        "buys", ref, "open", acct,
                        _said(tk or market, "Buy", size, level), {
                            "trade_id": f"T-{nt:03d}", "date": day,
                            # ONE FORMAT FOR A TRADE: the read and its day; the dealId is broker_ref.
                            "source": D.trade_source("ig-api", to, endpoint="/history/activity"),
                            "account": acct, "ticker": tk or "",
                            # A BET IS STERLING: IG prints "Curr £" on every bet, the stake's
                            # currency; the market's own currency is the code's, on securities.csv.
                            "cur": "GBP", "qty": "",
                            "stake": size,
                            "cost": "", "level_points": level,
                            "broker_ref": ref, "note": "",
                            "contract": contract_of.get(a["epic"], ""),
                            "traded_price": "", "rate": ""}))
                    if not tk:
                        setups[-1].update(epic=a["epic"], market=market,
                                          **contract_suffix(a["epic"], day))
                else:
                    closed = closed_id
                    ne += 1
                    # The deal id goes in broker_ref, which is what the column is for: a close
                    # whose note omitted it would otherwise be proposed a second time.
                    rows_e.append(_event(
                        "sales", ref, "close", acct,
                        _said(tk, "Sell", size, level), {
                            "sale_id": f"E-{ne:03d}", "date": day, "account": acct, "ticker": tk,
                            "qty": "", "stake": size, "traded_price": level, "cur": "GBP", "rate": "",
                            "proceeds": round(size * level, 2),
                            "source": D.trade_source("ig-api", to, endpoint="/history/activity"),
                            "broker_ref": ref,
                            "realisation_id": _parcel(acct, tk),
                            "closes": leg_of.get(closed, ""),
                            "note": ""}))

        for r in sorted(transactions, key=lambda x: x["dateUtc"]):
            amt = float(r["profitAndLoss"].replace("£", "").replace(",", ""))
            day = r["dateUtc"][:10]
            # A `WITH` IS MONEY OUT, and only some of it is a cost: IG files its funding charges
            # and a withdrawal under the one type.
            funding = r["transactionType"] == "WITH" and any(
                w in str(r.get("instrumentName") or "").lower() for w in FUNDING_WORDS)
            if funding:
                seen_api_cash.add((acct, day, round(amt, 2)))
                if (day, round(amt, 2)) in known_cash:
                    matched.append(f"{r['instrumentName']} · £{amt:,.2f} · {day} · in the book")
                    continue
                rows_i.append(_event(
                    "income", r["reference"], "cost", acct,
                    f"{r['instrumentName']} · £{amt:,.2f}", {
                        "date": day, "account": acct, "category": "Funding interest",
                        "detail": r["instrumentName"], "amount": amt,
                        "source": D.evidence_source("ig-api", r["reference"],
                                                   endpoint="/history/transactions"),
                        "note": "", "currency": "", "local_amount": "", "rate": "",
                        "ticker": ""}))
            elif r["transactionType"] in ("DEPO", "WITH"):
                if (day, round(amt, 2)) in known_moves:
                    matched.append(f"{r['instrumentName']} · £{amt:,.2f} · {day} · in the book")
                    continue
                rows_m.append(_event(
                    "capital-movements", r["reference"], "capital", acct,
                    f"{r['instrumentName']} · £{amt:,.2f}", {
                        "date": day, "account": acct, "amount": amt,
                        "source": D.evidence_source("ig-api", r["reference"],
                                                   endpoint="/history/transactions"),
                        "detail": f"{r['instrumentName']} — EXTERNAL CAPITAL, money crossing "
                                  f"the book's boundary. Confirm it is not an internal "
                                  f"transfer"}))

    # THE REVERSE DIRECTION, AND IT STOPS A DOUBLE COUNT. A book row in the window that IG's ledger
    # lacks is either a figure of the book's own that the swept rows supersede, or one that should
    # not be there. A sweep that reports only what is MISSING would let a pasted set of real charges
    # sit beside the figure they replace.
    #
    # ONLY THE ACCOUNTS SWEPT, and each against its own ledger: an account with no credentials
    # here was read by nothing, so its rows are not missing from IG — they were never asked about.
    orphans = [{"date": c.date, "amount": c.amount, "detail": c.detail, "account": c.account}
               for c in D.ci_rows
               if c.account in swept and D.ACCOUNT_KIND.get(c.account) == "spread bet"
               and frm <= c.date <= to
               and (c.account, c.date, round(c.amount, 2)) not in seen_api_cash]

    return {"frm": frm, "to": to, "matched": matched,
            "opens": rows_t, "closes": rows_e, "costs": rows_i, "capital": rows_m,
            "orphans": orphans, "skipped": skipped, "setups": setups}


def cmd_events(since=None):
    """Print the sweep. COMPUTES NOTHING — every row comes from `ig_events()`."""
    r = ig_events(since)
    matched, skipped, orphans = r["matched"], r["skipped"], r["orphans"]
    log.info(f"\n# IG EVENT SWEEP — {r['frm']} to {r['to']}, every configured account")
    log.info("# Matched against the book by DEAL REFERENCE. Paste what you accept; nothing is written.")

    def block(title, rows, target):
        log.info(f"\n  --- {title}: {len(rows)} row(s) ---")
        if not rows:
            log.info("      nothing missing")
            return
        log.info(f"      paste into {target}")
        for row in rows:
            log.info(f"    {row['line']}")

    log.info(f"\n  --- ALREADY IN THE BOOK: {len(matched)} event(s) ---")
    for m in matched:
        log.info(f"    {m}")
    block("MISSING opens", r["opens"], "store/buys.csv")
    block("MISSING closes", r["closes"], "store/sales.csv")
    block("MISSING costs", r["costs"], "store/income.csv")
    block("MISSING capital", r["capital"], "store/capital-movements.csv")

    if orphans:
        log.info(f"\n  --- IN THE BOOK BUT NOT IN IG'S LEDGER: {len(orphans)} row(s) ---")
        for c in orphans:
            log.info(f"    {c['date']}  {c['amount']:>8,.2f}  {c['detail'][:56]}")
        log.info("      A FIGURE IG DID NOT GIVE, which the rows above supersede, or one that should not be there.")
        log.info("      REMOVE IT BEFORE PASTING, or the money is counted twice.")

    if r["setups"]:
        log.info(f"\n  --- FIRST BET ON A CONTRACT THE BOOK DOES NOT HAVE: {len(r['setups'])} ---")
        for x in r["setups"]:
            log.info(f"    {x['what']} · {x['account']} · {x['ref']} · {x['epic']}")
        log.info("      Set each up on the Bench: its line, company and contract go with the trade.")
    if skipped:
        log.info(f"\n  --- SKIPPED: {len(skipped)} ---")
        for x in skipped:
            log.info(f"    {x}")
    log.info("\n  Every generated row marks the WHY as owed. Fill it before pasting — it is the one")
    log.info("  field no API supplies, and a rationale written after the outcome is worth little.")
    log.info("  A close carries IG's own realised figure: CHECK IT against the book's before")
    log.info("  accepting. That instruction lives here rather than inside every row.\n")


def cmd_logout():
    """End the cached session early and delete the cache — to get credential material off this
    disk now, or to clear a cache gone bad in a way the automatic recovery cannot see."""
    cache = _load_session_cache()
    if not cache:
        log.info("no cached session")
        return
    # THE CACHE IS CLEARED HOWEVER THE GOODBYE GOES. A missing credentials file or a dropped
    # connection must not leave the tokens on this disk.
    try:
        creds = load_credentials()
        for label, entry in list(cache.items()):
            if label in creds:
                s = IGSession(creds[label], label)
                s.cst, s.token = entry.get("cst"), entry.get("token")
                try:
                    s._request("DELETE", "/session", 1)
                    log.info(f"  {label}: session closed at IG")
                except IGError as e:
                    log.info(f"  {label}: IG would not close it ({e.code or e.status}) — "
                          "clearing locally anyway; it expires on its own")
    finally:
        clear_session_cache()
        log.info("session cache cleared")


USAGE = """
IG price sweep — read-only. Fetches spread-bet CONTRACT levels from IG's REST API.

    python3 -m portfusion.feeds.ig --ig-search "Zephyr" "Morane" ...    find epics (do this first)
    python3 -m portfusion.feeds.ig --ig-verify            compare live levels against the record
    python3 -m portfusion.feeds.ig --ig-events            trades, closes, costs and cash vs the book
    python3 -m portfusion.feeds.ig --ig-events 2026-08-01     ...over a window you choose
    python3 -m portfusion.feeds.ig --ig-logout            end the cached session and delete the cache

The sweep, `python3 -m portfusion.feeds.refresh [--on D]`, prints levels, equity and past closes.

Tokens from one login are cached in .ig_session.json (0600, gitignored) and reused for up to
five hours, because IG rate-limits an app that authenticates on every call.

Credentials go in credentials.json in the book's folder, the one PORTFUSION_BOOK names
(gitignored). Run any command without it to see the template. This module never writes to the record and cannot place a trade.
"""

def dispatch(args):
    """Which command a set of arguments SELECTS, without running it. None means none.

    Returns a zero-argument callable, so a test can ask what `--ig-events` is wired to without
    opening a session. SELECTING RUNS NOTHING: every branch returns a lambda.
    """
    if "--ig-search" in args:
        i = args.index("--ig-search")
        terms = [a for a in args[i + 1:] if not a.startswith("--")]
        if not terms:
            sys.exit('--ig-search needs at least one term, e.g. --ig-search "Zephyr" "Morane"')
        return lambda: cmd_search(terms)
    if "--ig-verify" in args:
        return cmd_verify
    if "--ig-events" in args:
        i = args.index("--ig-events")
        rest = [a for a in args[i + 1:] if not a.startswith("--")]
        return lambda: cmd_events(rest[0] if rest else None)
    if "--ig-logout" in args:
        return cmd_logout
    return None


if __name__ == "__main__":
    try:
        command = dispatch(sys.argv[1:])
        if command is None:
            log.info(USAGE)
        else:
            command()
    except (IGError, CredentialsError) as e:
        sys.exit(f"\n{e}\n")
