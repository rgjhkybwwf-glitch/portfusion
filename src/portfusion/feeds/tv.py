"""
TRADINGVIEW PRICE FEED — READ-ONLY. The share marks and the FX rates, beside `feeds/ig.py`'s
contract levels and shaped the same way: every row is a whole mark — its date, its source, whether
it is a session close or a live read (`struck`), and for a live read the UTC instant (`at`).

EACH LINE IS STRUCK AT ITS OWN INSTANT. A venue still trading gives a LIVE
read from the quote screen, at the moment it describes: the time it was read, less the delay the
vendor declares for that line. A venue not trading gives its latest session's close from the daily
bars, dated by that session — today's, once its venue has shut: a sweep is the price at the moment
it is taken, at any hour.

A LIVE READ IS THE QUOTE SCREEN'S, AND NOTHING ELSE. A day bar for a session still in progress is
not a price: a line quoting 50.0p can have a part-formed day bar reading 49.7p. Nor is a minute
bar: the bars can run on a delayed feed while the quote streams live, so one standing in for a
quote is a stale price looking current. Completed bars are exact. So when the quote screen,
TradingView's scanner, refuses, cannot be reached, or leaves a line out, a line still trading is
REPORTED UNPRICED with the screen's reason, and the next sweep asks again.

A REFUSAL ARRIVES AS A NORMAL REPLY — `success: false` inside HTTP 200, or `isError` with a reason
in plain text. It is raised as a refusal and named, never read as data. A reply that is only
PARTIAL — some markets failed — says so in `partial` and `warnings`, and names each symbol it left
out in `missing`; the sweep reports all three.

NOT PART OF THE BUILD, AND IT NEVER WRITES THE RECORD. It prints; `desk/doors/marks.py` is the door. The
only file it writes is its own sign-in, `.tv_session.json`, gitignored and mode 0600.

THE ALLOWLIST GUARDS THE OWNER'S TRADINGVIEW ACCOUNT. The server that quotes a price also creates
alerts and edits watchlists, so every tool that changes anything is refused by name, before a
request is built — as `feeds/ig.py` refuses dealing.

SIGN-IN is TradingView's OAuth: one browser sign-in (`--tv-sign-in`), after which a refresh token
renews the fifteen-minute access token on every run. Nothing here prints or logs a token.
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import http.client
import http.server
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor

from portfusion.record import schema as _schema   # the book folder, whose session this is
from portfusion.log import log

MCP_URL = "https://mcp.tradingview.com/mcp"
AUTH_BASE = "https://www.tradingview.com/mcp/oauth"
SCOPE = "mcp:read mcp:tools"
REDIRECT_PORT = 8767
SESSION_FILE = os.path.join(_schema.BOOK, ".tv_session.json")
PROTOCOL = "2025-06-18"

#: A REQUEST THAT NEVER GOT AN ANSWER IS SENT AGAIN — a failed handshake, a dropped or stalled
#: connection, a gateway with nothing behind it — after a pause that doubles. An answer is never
#: retried, a refusal included, with ONE exception below. Safe because every tool on the allowlist
#: only reads. The sign-in's renewal is not retried: a refresh token may already have been spent
#: by the try that was lost.
TRIES = 3
PAUSE_SECONDS = 1.0
_GATEWAY = (502, 503, 504)

#: THE ONE REFUSAL ASKED AGAIN: TradingView's server has not yet opened its own data connection.
#: A fresh session's first bar requests are refused with this, then answered — within seconds.
#: Every sweep opens a fresh session, so its first line meets it.
_NOT_YET_CONNECTED = "websocket: bad handshake"

#: Request ids are numbered under this lock: a sweep has several requests in flight at once.
_IDS = threading.Lock()


# =================================================================================================
# THE ALLOWLIST — three reads, and every writing tool refused by name
# =================================================================================================
_ALLOWED = (
    "mcp-tv-get-symbol-data-batch",   # the quote screen: every live line in one call
    "mcp-tv-get-ohlcv",               # daily bars: a completed session, and which day it was
    "mcp-tv-search-symbols",          # symbol discovery — a symbol is looked up, never guessed
)

_WRITES_TO_THE_ACCOUNT = ("changes the owner's TradingView account. This feed reads prices; "
                          "nothing here may create, edit or delete anything there.")
_REFUSED = {name: _WRITES_TO_THE_ACCOUNT for name in (
    "mcp-tv-create-alert", "mcp-tv-update-alert", "mcp-tv-delete-alert",
    "mcp-tv-restart-alerts", "mcp-tv-stop-alerts",
    "mcp-watchlist-create-watchlist", "mcp-watchlist-update-watchlist",
    "mcp-watchlist-delete-watchlist", "mcp-watchlist-add-to-watchlist",
    "mcp-watchlist-remove-from-watchlist",
)}


class TVError(Exception):
    """Something TradingView said, or refused to say, or a sign-in that is missing."""


class TVRefused(TVError):
    """TradingView answered and declined — `success: false` or `isError` in a normal reply."""


def _assert_allowed(tool: str) -> None:
    if tool in _REFUSED:
        raise TVError(f"REFUSED: {tool} — {_REFUSED[tool]}")
    if tool not in _ALLOWED:
        raise TVError(f"REFUSED: {tool} is not on feeds/tv.py's allowlist ({', '.join(_ALLOWED)}). "
                      f"A new tool is a decision, not a detail — say why here.")


# =================================================================================================
# SIGN-IN — OAuth with PKCE, the client registered once, the session in a gitignored file
# =================================================================================================
def _post(url: str, body: dict, form: bool = False) -> dict:
    data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
    ctype = "application/x-www-form-urlencoded" if form else "application/json"
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": ctype, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise TVError(f"TradingView sign-in: HTTP {e.code} from {url.rsplit('/', 1)[-1]}")
    except urllib.error.URLError as e:
        raise TVError(f"could not reach TradingView — {e.reason}")


def _save_session(session: dict) -> None:
    with open(SESSION_FILE, "w") as fh:
        json.dump(session, fh)
    os.chmod(SESSION_FILE, 0o600)


def sign_in(open_browser=webbrowser.open) -> dict:
    """ONE BROWSER SIGN-IN, by the owner, in their own browser. Registers this client, waits for
    TradingView to hand back a code on a local port, and keeps the tokens. Run once; the refresh
    token does the rest."""
    redirect = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
    client = _post(f"{AUTH_BASE}/register", {
        "client_name": "PortFusion (read-only price feed)",
        "redirect_uris": [redirect], "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"], "token_endpoint_auth_method": "none", "scope": SCOPE})
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = f"{AUTH_BASE}/authorize?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client["client_id"], "redirect_uri": redirect,
        "code_challenge": challenge, "code_challenge_method": "S256", "scope": SCOPE,
        "state": state, "resource": MCP_URL})
    got = {}

    class _Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            got.update({k: v[0] for k, v in
                        urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<p>Signed in to TradingView. You can close this tab.</p>")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), _Callback)
    server.timeout = 5
    log.info(f"Opening TradingView sign-in. If no page opens, visit:\n{url}")
    open_browser(url)
    deadline = time.time() + 900
    while not ({"code", "error"} & set(got)) and time.time() < deadline:
        server.handle_request()
    server.server_close()
    if got.get("state") != state or "code" not in got:
        raise TVError(f"sign-in did not complete: {got.get('error') or 'no code came back'}")
    tokens = _post(f"{AUTH_BASE}/token", {
        "grant_type": "authorization_code", "code": got["code"], "redirect_uri": redirect,
        "client_id": client["client_id"], "code_verifier": verifier, "resource": MCP_URL},
        form=True)
    session = {**tokens, "client_id": client["client_id"], "saved": time.time()}
    _save_session(session)
    return session


def _access_token() -> str:
    """The current access token, renewed from the refresh token when it is within a minute of
    expiring. A rotated refresh token is kept, or the next run would sign in again."""
    try:
        with open(SESSION_FILE) as fh:
            session = json.load(fh)
    except (OSError, ValueError):
        raise TVError("not signed in to TradingView — run: python3 -m portfusion.feeds.tv --tv-sign-in")
    if time.time() - session.get("saved", 0) > session.get("expires_in", 900) - 60:
        fresh = _post(f"{AUTH_BASE}/token", {
            "grant_type": "refresh_token", "refresh_token": session.get("refresh_token", ""),
            "client_id": session.get("client_id", ""), "resource": MCP_URL}, form=True)
        if not fresh.get("access_token"):
            raise TVError("TradingView would not renew the sign-in — run --tv-sign-in again")
        session = {**session, **fresh, "saved": time.time()}
        _save_session(session)
    return session["access_token"]


# =================================================================================================
# THE CONNECTION — MCP over HTTP: one handshake, then tool calls
# =================================================================================================
class _Connection:
    def __init__(self, token: str):
        self.token, self.session_id, self.n = token, None, 0
        self._rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                 "clientInfo": {"name": "portfusion", "version": "1"}})
        self._rpc("notifications/initialized", notify=True)

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False):
        body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notify:
            with _IDS:
                self.n += 1
                body["id"] = self.n
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": PROTOCOL}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(MCP_URL, data=json.dumps(body).encode(), headers=headers,
                                     method="POST")
        for attempt in range(1, TRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    self.session_id = r.headers.get("Mcp-Session-Id") or self.session_id
                    raw, ctype = r.read().decode(), r.headers.get("Content-Type", "")
                break
            except urllib.error.HTTPError as e:
                if e.code not in _GATEWAY:
                    raise TVError(f"TradingView {method}: HTTP {e.code}")
                lost = f"HTTP {e.code}"
            except urllib.error.URLError as e:          # before OSError, which it is
                lost = f"could not reach TradingView — {e.reason}"
            except (OSError, http.client.HTTPException) as e:   # a stall or a reset mid-read
                lost = f"{type(e).__name__}: {e}"
            if attempt == TRIES:
                raise TVError(f"TradingView {method}, {TRIES} tries: {lost}")
            time.sleep(PAUSE_SECONDS * 2 ** (attempt - 1))
        if notify:
            return None
        if "event-stream" in ctype:
            messages = [json.loads(line[5:]) for line in raw.splitlines()
                        if line.startswith("data:") and line[5:].strip()]
            reply = next((m for m in messages if m.get("id") == body["id"]), {})
        else:
            reply = json.loads(raw) if raw.strip() else {}
        if "error" in reply:
            raise TVError(f"TradingView {method}: {reply['error'].get('message', reply['error'])}")
        if "result" not in reply:
            raise TVError(f"TradingView {method}: no answer to request {body['id']}")
        return reply["result"]

    def call(self, tool: str, **arguments) -> dict:
        """One tool call, allowlisted BEFORE the request is built. A reply that says no is raised —
        unless it says TradingView has not yet reached its own data (`_NOT_YET_CONNECTED`)."""
        _assert_allowed(tool)
        for attempt in range(1, TRIES + 1):
            try:
                return self._read(tool, self._rpc("tools/call", {"name": tool,
                                                                 "arguments": arguments}))
            except TVRefused as e:
                if _NOT_YET_CONNECTED not in str(e):
                    raise
                if attempt == TRIES:
                    raise TVRefused(f"{e}, {TRIES} tries") from None
                time.sleep(PAUSE_SECONDS * 2 ** (attempt - 1))

    @staticmethod
    def _read(tool: str, result: dict) -> dict:
        """A tool's reply as data, or raised: TVRefused if it says no, TVError if it is unreadable."""
        payload = result.get("structuredContent")
        text = (((result.get("content") or [{}])[0]).get("text") or "").strip()
        if payload is None:
            try:
                payload = json.loads(text or "{}")
            except ValueError:
                payload = None
        if not isinstance(payload, dict):
            if result.get("isError"):
                raise TVRefused(f"{tool}: {text or 'refused, no reason given'}")
            raise TVError(f"{tool}: a reply this feed cannot read — {text[:200]!r}")
        if result.get("isError") or payload.get("success") is False:
            raise TVRefused(f"{tool}: {payload.get('error') or 'refused, no reason given'}")
        if not payload:
            raise TVError(f"{tool}: an empty reply")
        return payload


def connect() -> _Connection:
    return _Connection(_access_token())


# =================================================================================================
# THE MAP — book ticker to TradingView symbol, with the unit TradingView quotes
# =================================================================================================
#: THE RECORD NAMES A LISTING AS ITS MARKET DOES: the market's ISO code (MIC) and the ticker as
#: that market spells it (securities.csv's `symbol`). TradingView names some markets otherwise,
#: and joins a ticker's words with an underscore; this is the one place that knows.
MARKETS = {"XLON": "LSE", "XNYS": "NYSE", "XNAS": "NASDAQ", "XETR": "XETR", "XCSE": "OMXCOP",
           "XSTO": "OMXSTO", "XPAR": "EURONEXT", "XAMS": "EURONEXT"}


def tv_symbol(symbol: str) -> str:
    """A listing as the record names it (XCSE:HALD B), as TradingView names it (OMXCOP:HALD_B).
    Refuses a market not in MARKETS, naming it, rather than asking for a symbol that is not."""
    market, _, ticker = symbol.partition(":")
    if market not in MARKETS or not ticker:
        raise ValueError(f"{symbol!r}: not a market TradingView is mapped for ({', '.join(MARKETS)}),"
                         f" or no ticker after the colon")
    return f"{MARKETS[market]}:{ticker.replace(' ', '_')}"


#: `unit` is what TradingView says the line is quoted in — checked against the reply, so the pence
#: trap is caught by the vendor's own word rather than a divisor typed here. The map itself is
#: securities.csv's `symbol` and `quote_unit`; `tests/test_tv.py` holds it against the prices.
def symbols(D=None) -> dict:
    """book code -> {"symbol", "unit"}, for every security the book prices from TradingView: the
    ones securities.csv gives a unit, each symbol in TradingView's form."""
    D = D or _rules()
    h = D.schema.TABLES["securities"].header
    code, sym, unit = h.index("ticker"), h.index("symbol"), h.index("quote_unit")
    return {r[code]: {"symbol": tv_symbol(r[sym]), "unit": r[unit]}
            for r in D.SECURITIES if r[sym] and r[unit]}


def _rules():
    from portfusion.record import rules as D
    return D


#: A quoted unit, as the record holds it: (currency, divisor). Only pence differs.
UNITS = {"GBX": ("GBP", 100)}

def rate_symbol(currency: str) -> str:
    """The TradingView pair a rate is read from: sterling against the currency, units of it per
    £1, as the record holds a rate. SPELT FROM THE CURRENCY, so a currency the record holds is a
    currency this can read without a list beside it to keep in step."""
    return f"FX_IDC:GBP{currency}"


def rate_currencies(D=None) -> list[str]:
    """The currencies a refresh reads a live rate for: fx.csv's, less any the book carries."""
    D = D or _rules()
    return [r[0] for r in D.fx_rows if r[0] not in D.RATE_CARRIED]


def _record_unit(unit: str) -> tuple[str, int]:
    return UNITS.get(unit, (unit, 1))


def _delay_minutes(update_mode: str | None) -> int | None:
    """`streaming` is real time; `delayed_streaming_900` is fifteen minutes behind. Anything else
    is a mode nobody has seen, and a live read whose delay is unknown has no instant."""
    mode = str(update_mode or "")
    if mode == "streaming":
        return 0
    if mode.startswith("delayed_streaming_") and mode.rsplit("_", 1)[-1].isdigit():
        return int(mode.rsplit("_", 1)[-1]) // 60
    return None


# =================================================================================================
# DATING A BAR — which session it describes
# =================================================================================================
def session_date(t: int) -> str:
    """The date of the session a daily bar describes.

    A share's bar is stamped at its session's open, on its own day (US 13:30Z, Europe 07:00Z). An
    FX bar is stamped at 22:00 UTC THE EVENING BEFORE: "Sun 27 Sep 22:00Z" is Monday's rate. Dated
    by its stamp it would be a day early — a rate for the wrong date, the conversion error
    `rules.FX_RATE_AGE_LIMIT_DAYS` describes. So a bar stamped in the evening opens the next day's
    session.
    """
    stamp = _dt.datetime.fromtimestamp(int(t), _dt.timezone.utc)
    if stamp.hour >= 18:
        stamp += _dt.timedelta(days=1)
    return stamp.date().isoformat()


def _complete_bar(bars: list[dict], on: str) -> tuple[str, float]:
    """The newest bar whose session is ON OR BEFORE `on`: (session date, close)."""
    dated = [(session_date(b["t"]), b.get("c")) for b in bars]
    held = [(d, c) for d, c in dated if d <= on]
    if not held:
        oldest = min((d for d, _ in dated), default="none")
        raise TVError(f"no session on or before {on} in the bars returned (oldest {oldest})")
    day, close = max(held)
    if close is None:
        raise TVError(f"the session dated {day} carries no close")
    return day, float(close)


# =================================================================================================
# THE SWEEP
# =================================================================================================
#: LINES PRICED AT ONCE. Five is nearly as fast as ten, and asks half as hard of a vendor rationing
#: its quote screen.
AT_ONCE = 5


def _utc(now: _dt.datetime) -> str:
    return now.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _still_trading(currency: str | None, now: _dt.datetime, delay: int, today_has_bar: bool) -> bool:
    """Is this line's venue in its session now? A share's venue closes at `rules.VENUE_CLOSE_UK`,
    and a delayed quote reaches the close `delay` minutes later; FX trades round the weekday clock.
    No bar for today means the session has not begun — pre-open, a weekend or a holiday."""
    if not today_has_bar:
        return False
    if currency is None:
        return True
    from portfusion.record import rules as D
    from zoneinfo import ZoneInfo
    h, m = (int(x) for x in D.VENUE_CLOSE_UK.get(currency, D.VENUE_CLOSE_UK_DEFAULT).split(":"))
    uk = now.astimezone(ZoneInfo("Europe/London"))
    return uk.hour * 60 + uk.minute < h * 60 + m + delay


def _words(said) -> str:
    """Something the vendor said, as it said it."""
    return said if isinstance(said, str) else json.dumps(said, ensure_ascii=False)


def _quote_screen(conn, symbols: list[str]) -> tuple[dict, str, dict]:
    """EVERY LIVE LINE IN ONE CALL: (each symbol's quote, what the screen answered, and why each
    symbol it did not quote has none). Whatever goes wrong — a refusal, no answer, a partial reply
    — costs only the lines still trading, and is told in the vendor's words. An entry in `missing`
    is the one that names the symbol, quoted whole: its shape is the vendor's, not pinned here."""
    try:
        reply = conn.call("mcp-tv-get-symbol-data-batch", symbols=symbols,
                          columns=["close", "currency", "update_mode"])
    except TVRefused as e:
        return {}, f"refused: {e}", {s: f"it refused — {e}" for s in symbols}
    except TVError as e:
        return {}, f"no answer: {e}", {s: f"it did not answer — {e}" for s in symbols}
    quotes, missing = reply.get("data") or {}, reply.get("missing") or []
    screen = ("partial: " + ("; ".join(map(_words, reply.get("warnings") or []))
                             or "no warning given")) if reply.get("partial") else "ok"
    absent = {}
    for s in (s for s in symbols if quotes.get(s) is None):
        said = (missing.get(s) if isinstance(missing, dict)
                else next((m for m in missing if s in _words(m)), None))
        absent[s] = ("its reply left this symbol out"
                     + (f" — {_words(said)}" if said is not None
                        else f" ({screen})" if screen != "ok" else ", and gave no reason"))
    return quotes, screen, absent


def _one_line(conn, key, symbol, unit, quote, absent, now, record_currency=None):
    """Price one line: its quote if its venue is trading, else its latest session's close from the
    bars. `absent` is why there is no quote, when there is none. Returns the row, or raises TVError
    with the reason it is unpriced."""
    from portfusion.record import rules as D
    today = D.uk_date(_utc(now))
    bars = conn.call("mcp-tv-get-ohlcv", symbol=symbol, interval="1D", count=5)["bars"]
    last_day, last_close = _complete_bar(bars, today)
    currency, divisor = _record_unit(unit)
    delay = _delay_minutes((quote or {}).get("update_mode"))
    trading = _still_trading(record_currency, now, delay or 0, last_day == today)

    if trading:
        if quote is not None and quote.get("currency") != unit:
            raise TVError(f"{symbol} quoted in {quote.get('currency')!r}, expected {unit!r} — "
                          f"the unit is wrong and the price would be too")
        if quote is None or delay is None or quote.get("close") is None:
            why = absent if quote is None else (f"its quote has no price or an unknown delay "
                                                f"({quote.get('update_mode')!r})")
            raise TVError(f"{symbol} is trading, and the quote screen gave no price: {why}")
        raw, struck = float(quote["close"]), "live"
        at = _utc(now - _dt.timedelta(minutes=delay))
        source = (f"TradingView quote {symbol} {raw} {unit}"
                  + (f" / {divisor}" if divisor != 1 else "")
                  + (f", live at {at}, {delay} min delayed" if delay else f", live at {at}"))
        as_of = D.uk_date(at)
    else:
        raw, struck, at, as_of = last_close, "close", "", last_day
        source = (f"TradingView 1D {symbol}, session {last_day} close {raw} {unit}"
                  + (f" / {divisor}" if divisor != 1 else ""))
    return {"key": key, "symbol": symbol, "currency": currency, "price": round(raw / divisor, 6),
            "raw": raw, "as_of": as_of, "struck": struck, "at": at, "source": source}


def sweep(tickers=None, currencies=None, now=None, conn=None) -> dict:
    """THE TRADINGVIEW HALF OF A REFRESH, AS DATA. Prints nothing; writes nothing.

    The book decides what is priced: every share `current-prices.csv` holds that is not a contract
    and not carried, and every live rate that is not carried. A line this feed cannot price comes
    back in `failed` with its reason — never dropped, never zero.
    """
    from portfusion.record import rules as D
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if tickers is None:
        contracts = set(D.LEG_CONTRACT.values())
        tickers = [r[0] for r in D.CURRENT_PRICES
                   if r[0] not in contracts and r[0] not in D.STATEMENT_PRICED]
    if currencies is None:
        currencies = rate_currencies(D)
    SYMBOLS = symbols(D)
    record_ccy = {r[0]: r[2] for r in D.CURRENT_PRICES}
    conn = conn or connect()

    wanted = {t: SYMBOLS[t]["symbol"] for t in tickers if t in SYMBOLS}
    wanted.update({c: rate_symbol(c) for c in currencies})
    quotes, screen, absent = _quote_screen(conn, sorted(set(wanted.values())))

    def priced(job):
        key, symbol, unit, record_currency = job
        try:
            return _one_line(conn, key, symbol, unit, quotes.get(symbol), absent.get(symbol), now,
                             record_currency)
        except TVError as e:
            return {"key": key, "symbol": symbol, "why": str(e)}

    jobs = ([(t, SYMBOLS[t]["symbol"], SYMBOLS[t]["unit"], record_ccy.get(t))
             for t in tickers if t in SYMBOLS]
            + [(c, rate_symbol(c), c, None) for c in currencies])
    with ThreadPoolExecutor(AT_ONCE) as pool:          # AT_ONCE in flight; answers in book order
        done = {job[0]: row for job, row in zip(jobs, pool.map(priced, jobs))}

    prices, rates, failed = [], [], []
    for t in tickers:
        if t not in SYMBOLS:
            failed.append({"key": t, "why": "securities.csv gives it no TradingView symbol"})
        elif "why" in done[t]:
            failed.append(done[t])
        else:
            row = done[t]
            row["mark_key"] = row.pop("key")
            prices.append(row)
    for c in currencies:
        row = done[c]
        if "why" in row:
            failed.append(row)
            continue
        row.pop("key")
        row.update(rate=row.pop("price"))
        rates.append(row)
    return {"now": _utc(now), "prices": prices, "rates": rates, "failed": failed,
            "quote_screen": screen}


def rate_closes(wanted: dict, conn=None, today=None) -> dict:
    """THE CLOSES A RECORD LACKS: for each currency, the close of the newest session on or before
    each wanted date, from ONE read of its daily bars however many dates. A row
    carries the dates it was wanted for beside the session's own: two dates one session serves —
    a Saturday and the Friday before it — come back as one row. Prints nothing; writes nothing.
    """
    today = today or _dt.date.today()
    rates, failed = [], []
    if not wanted:
        return {"rates": rates, "failed": failed}
    conn = conn or connect()
    for currency, dates in sorted(wanted.items()):
        symbol = rate_symbol(currency)
        back = (today - _dt.date.fromisoformat(min(dates))).days
        try:
            bars = conn.call("mcp-tv-get-ohlcv", symbol=symbol, interval="1D",
                             count=max(5, min(5000, back + 10)))["bars"]
        except TVError as e:
            failed += [{"key": currency, "symbol": symbol, "wanted": d, "why": str(e)}
                       for d in sorted(dates)]
            continue
        by_session = {}
        for d in sorted(set(dates)):
            try:
                day, raw = _complete_bar(bars, d)
            except TVError as e:
                failed.append({"key": currency, "symbol": symbol, "wanted": d, "why": str(e)})
                continue
            if day in by_session:
                by_session[day]["wanted"].append(d)
                continue
            by_session[day] = {"currency": currency, "symbol": symbol, "rate": raw, "raw": raw,
                               "as_of": day, "struck": "close", "at": "", "wanted": [d],
                               "source": f"TradingView 1D {symbol}, session {day} close {raw} "
                                         f"{currency}"}
            rates.append(by_session[day])
    return {"rates": rates, "failed": failed}


def closes(on: str, tickers=None, currencies=None, conn=None) -> dict:
    """ONE PAST DAY'S CLOSES — a quarter end fetched after the day. Every line from the daily bars:
    the newest session on or before `on`, under that session's own date — a shut day is answered
    by the session before it, never by a figure wearing `on`."""
    from portfusion.record import rules as D
    days_back = (_dt.date.today() - _dt.date.fromisoformat(on)).days
    count = max(5, min(5000, days_back + 10))
    if tickers is None:
        contracts = set(D.LEG_CONTRACT.values())
        tickers = [r[0] for r in D.CURRENT_PRICES
                   if r[0] not in contracts and r[0] not in D.STATEMENT_PRICED]
    if currencies is None:
        currencies = rate_currencies(D)
    SYMBOLS = symbols(D)
    conn = conn or connect()
    prices, rates, failed = [], [], []
    lines = [(t, SYMBOLS[t]["symbol"], SYMBOLS[t]["unit"]) for t in tickers if t in SYMBOLS]
    failed += [{"key": t, "why": "securities.csv gives it no TradingView symbol"}
               for t in tickers if t not in SYMBOLS]
    # THE RATES BY THE ONE ROUTE A DATED RATE TAKES (`rate_closes()`), for the one day.
    got = rate_closes({c: [on] for c in currencies}, conn=conn)
    rates += [{k: v for k, v in r.items() if k != "wanted"} for r in got["rates"]]
    failed += [{k: v for k, v in f.items() if k != "wanted"} for f in got["failed"]]
    for key, symbol, unit in lines:
        try:
            bars = conn.call("mcp-tv-get-ohlcv", symbol=symbol, interval="1D", count=count)["bars"]
            day, raw = _complete_bar(bars, on)
        except TVError as e:
            failed.append({"key": key, "symbol": symbol, "why": str(e)})
            continue
        currency, divisor = _record_unit(unit)
        row = {"symbol": symbol, "currency": currency, "raw": raw, "as_of": day,
               "struck": "close", "at": "",
               "source": (f"TradingView 1D {symbol}, session {day} close {raw} {unit}"
                          + (f" / {divisor}" if divisor != 1 else ""))}
        prices.append({**row, "mark_key": key, "price": round(raw / divisor, 6)})
    return {"on": on, "prices": prices, "rates": rates, "failed": failed}


# =================================================================================================
# THE COMMAND LINE — the prices are printed by the sweep, `python3 -m portfusion.feeds.refresh`
# =================================================================================================
def search(query: str, conn=None) -> list[dict]:
    """TradingView's own hits for a query, in its order: each a dict carrying `symbol`, `type`,
    `exchange` and `description`. The reply nests them under `data.symbols`."""
    conn = conn or connect()
    return list((conn.call("mcp-tv-search-symbols", query=query).get("data") or {}).get("symbols") or [])


def dispatch(args) -> int:
    if "--tv-sign-in" in args:
        sign_in()
        log.info("signed in — the session is kept in .tv_session.json (gitignored, 0600)")
        return 0
    if "--tv-search" in args:
        query = " ".join(a for a in args if a != "--tv-search")
        for hit in search(query)[:15]:
            log.info(f"  {hit.get('symbol', ''):<22} {hit.get('type', ''):<8} {hit.get('description', '')}")
        return 0
    log.info("feeds/tv.py — the TradingView share and FX feed. It prints; it never writes.\n")
    log.info("  python3 -m portfusion.feeds.tv --tv-sign-in            one browser sign-in, kept for later runs")
    log.info("  python3 -m portfusion.feeds.tv --tv-search QUERY       find a symbol — never guess one")
    log.info("  the prices: python3 -m portfusion.feeds.refresh [--on D]")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(dispatch(sys.argv[1:]))
    except TVError as e:
        log.error(f"\n{e}\n")
        sys.exit(1)
