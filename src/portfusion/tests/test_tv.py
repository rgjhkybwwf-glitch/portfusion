"""
THE TRADINGVIEW FEED — the guards. What each guards against is `feeds/tv.py`'s own docstring: a
wrong price entering the book looking right, and this feed changing the owner's account.

NOTHING HERE REACHES THE NETWORK: every test drives the module with replies of its own, so the
suite runs with no sign-in present.
"""
import ast
import datetime as dt
import ssl
import threading
import time

import pytest

from portfusion.feeds import tv

from harness import SRC, holds, needs
UTC = dt.timezone.utc


def _t(stamp: str) -> int:
    return int(dt.datetime.fromisoformat(stamp).replace(tzinfo=UTC).timestamp())


class FakeConnection:
    """Answers tool calls from canned replies, through the real allowlist."""

    def __init__(self, quotes=None, bars=None, refuse_quotes=None, minutes=None, hits=None):
        self.quotes, self.bars, self.refuse = quotes or {}, bars or {}, refuse_quotes
        self.minutes, self.hits = minutes or {}, hits or []
        self.calls = []

    def call(self, tool, **args):
        tv._assert_allowed(tool)
        self.calls.append((tool, args))
        if tool == "mcp-tv-get-symbol-data-batch":
            if self.refuse:
                raise tv.TVRefused(f"{tool}: {self.refuse}")
            return {"success": True, "data": {s: self.quotes[s] for s in args["symbols"]
                                              if s in self.quotes}}
        if tool == "mcp-tv-get-ohlcv" and args["interval"] == "1m":
            if args["symbol"] not in self.minutes:
                raise tv.TVRefused(f"{tool}: no minute bars for {args['symbol']}")
            return {"success": True, "bars": self.minutes[args["symbol"]][-args["count"]:]}
        if tool == "mcp-tv-get-ohlcv":
            if args["symbol"] not in self.bars:
                raise tv.TVRefused(f"{tool}: unknown symbol {args['symbol']}")
            return {"success": True, "bars": self.bars[args["symbol"]]}
        if tool == "mcp-tv-search-symbols":
            return {"success": True, "data": {"count": len(self.hits), "symbols": self.hits}}
        raise AssertionError(tool)


# =====================================================================================
# THE ALLOWLIST — the owner's account is not this feed's to change
# =====================================================================================

def test_every_tool_that_changes_the_account_is_refused_by_name():
    """BY NAME, so the refusal says WHY. The same server that quotes a price creates alerts and
    edits watchlists; a feed that reads prices has no business with either."""
    for tool in ("mcp-tv-create-alert", "mcp-tv-update-alert", "mcp-tv-delete-alert",
                 "mcp-tv-restart-alerts", "mcp-tv-stop-alerts",
                 "mcp-watchlist-create-watchlist", "mcp-watchlist-update-watchlist",
                 "mcp-watchlist-delete-watchlist", "mcp-watchlist-add-to-watchlist",
                 "mcp-watchlist-remove-from-watchlist"):
        with pytest.raises(tv.TVError) as e:
            tv._assert_allowed(tool)
        assert "changes the owner's TradingView account" in str(e.value), tool


def test_a_tool_nobody_has_considered_is_refused_too():
    with pytest.raises(tv.TVError):
        tv._assert_allowed("mcp-tv-get-news")
    for allowed in tv._ALLOWED:
        tv._assert_allowed(allowed)


def test_the_allowlist_is_three_reads_and_a_fourth_is_a_decision():
    """Pinned, so widening it shows up in a diff."""
    assert set(tv._ALLOWED) == {
        "mcp-tv-get-symbol-data-batch", "mcp-tv-get-ohlcv", "mcp-tv-search-symbols"}
    assert not set(tv._ALLOWED) & set(tv._REFUSED)


def test_the_allowlist_is_checked_before_a_request_is_built(monkeypatch):
    """The refusal happens in `call()`, before `_rpc` — nothing leaves the machine."""
    sent = []
    conn = object.__new__(tv._Connection)
    monkeypatch.setattr(conn, "_rpc", lambda *a, **k: sent.append(a), raising=False)
    with pytest.raises(tv.TVError):
        conn.call("mcp-tv-create-alert", symbol="NASDAQ:GRVL")
    assert not sent


# =====================================================================================
# A REFUSAL IN A NORMAL REPLY
# =====================================================================================

@pytest.mark.parametrize("result", [
    {"structuredContent": {"success": False, "error": "tradingview api: …/scan: 429: "}},
    {"isError": True, "content": [{"type": "text", "text": '{"error": "bad symbol"}'}]},
])
def test_a_refusal_inside_a_normal_reply_is_raised_and_not_read(monkeypatch, result):
    """The quote screen can answer HTTP 200 with `success: false`: a parser reading only `data`
    would price nothing and say nothing."""
    conn = object.__new__(tv._Connection)
    monkeypatch.setattr(conn, "_rpc", lambda *a, **k: result, raising=False)
    with pytest.raises(tv.TVRefused):
        conn.call("mcp-tv-get-symbol-data-batch", symbols=["NASDAQ:GRVL"])


def test_a_refusal_in_plain_text_is_a_refusal_in_its_own_words(monkeypatch):
    """`isError` with a sentence, not JSON. It is checked before it is parsed."""
    conn = object.__new__(tv._Connection)
    monkeypatch.setattr(conn, "_rpc", lambda *a, **k: {
        "isError": True, "content": [{"type": "text", "text": "Rate limit exceeded"}]}, raising=False)
    with pytest.raises(tv.TVRefused, match="Rate limit exceeded"):
        conn.call("mcp-tv-get-symbol-data-batch", symbols=["NASDAQ:GRVL"])


def test_a_read_that_stalls_is_the_feeds_error_and_not_a_crash(monkeypatch):
    """A timeout during the read is not a URLError, and is caught as the feed's own error."""
    def stall(*a, **k):
        raise TimeoutError("The read operation timed out")
    monkeypatch.setattr(tv.urllib.request, "urlopen", stall)
    monkeypatch.setattr(tv.time, "sleep", lambda s: None)
    with pytest.raises(tv.TVError, match="timed out"):
        _bare_connection()._rpc("tools/call", {"name": "mcp-tv-get-ohlcv", "arguments": {}})


@pytest.mark.parametrize("body, ctype", [
    ("", "application/json"), ('{"jsonrpc": "2.0", "id": 1}', "application/json"),
    ('event: message\ndata: {"jsonrpc": "2.0", "id": 7, "result": {}}\n\n', "text/event-stream")])
def test_a_reply_that_answers_nothing_is_the_feeds_error(monkeypatch, body, ctype):
    """No body, no result, or a stream with no message for this request: each is no answer, raised
    as the feed's own error so the sweep names the line, and an empty payload is not data."""
    monkeypatch.setattr(tv.urllib.request, "urlopen", lambda *a, **k: _Reply(body, ctype))
    with pytest.raises(tv.TVError, match="no answer to request 1$"):
        _bare_connection()._rpc("tools/call", {"name": "mcp-tv-get-ohlcv"})
    with pytest.raises(tv.TVError, match="an empty reply$"):
        tv._Connection._read("mcp-tv-get-ohlcv", {"structuredContent": {}})


def _bare_connection():
    conn = object.__new__(tv._Connection)
    conn.token, conn.session_id, conn.n = "x", None, 0
    return conn


class _Reply:
    """What urlopen hands back: headers, and a body read once."""
    def __init__(self, body, ctype="application/json"):
        self.body, self.headers = body, {"Content-Type": ctype}

    def read(self):
        return self.body.encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _answers(monkeypatch, *outcomes):
    """urlopen answering with each outcome in turn — an exception is raised, a string is the body.
    Returns the list of pauses taken between tries."""
    queue, pauses = list(outcomes), []

    def urlopen(*a, **k):
        nxt = queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return _Reply(nxt)
    monkeypatch.setattr(tv.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(tv.time, "sleep", pauses.append)
    return queue, pauses


def test_a_handshake_that_fails_is_tried_again(monkeypatch):
    """A request that never reached an answer is sent again, after a pause that doubles; every
    tool on the allowlist only reads, so asking twice changes nothing."""
    handshake = tv.urllib.error.URLError(ssl.SSLError("bad handshake"))
    queue, pauses = _answers(monkeypatch, handshake, handshake,
                             '{"jsonrpc": "2.0", "id": 1, "result": {"ok": true}}')
    assert _bare_connection()._rpc("tools/call", {"name": "mcp-tv-get-ohlcv"}) == {"ok": True}
    assert not queue and pauses == [1.0, 2.0]


def test_a_request_that_never_answers_says_how_often_it_was_tried(monkeypatch):
    handshake = tv.urllib.error.URLError(ssl.SSLError("bad handshake"))
    _, pauses = _answers(monkeypatch, *[handshake] * tv.TRIES)
    with pytest.raises(tv.TVError, match=f"{tv.TRIES} tries: could not reach TradingView — "
                                          f".*bad handshake"):
        _bare_connection()._rpc("tools/call", {"name": "mcp-tv-get-ohlcv"})
    assert len(pauses) == tv.TRIES - 1


@pytest.mark.parametrize("code", [401, 429])
def test_an_answer_is_never_asked_again(monkeypatch, code):
    """A 401 is an answer, and so is a 429: asking again at once would be asking too fast."""
    err = tv.urllib.error.HTTPError(tv.MCP_URL, code, "no", {}, None)
    queue, pauses = _answers(monkeypatch, err, '{"result": {}}')
    with pytest.raises(tv.TVError, match=f"HTTP {code}$"):
        _bare_connection()._rpc("tools/call", {"name": "mcp-tv-get-ohlcv"})
    assert queue and not pauses


_NOT_YET = {"structuredContent": {"success": False,
                                  "error": "failed to fetch bars: tvws: dial: websocket: bad handshake"}}


def _replies(monkeypatch, conn, *results):
    """The tool replies `conn` receives, in turn. Returns what is left and the pauses taken."""
    queue, pauses = list(results), []
    monkeypatch.setattr(conn, "_rpc", lambda *a, **k: queue.pop(0), raising=False)
    monkeypatch.setattr(tv.time, "sleep", pauses.append)
    return queue, pauses


def test_a_bar_refused_before_tradingview_has_its_data_is_asked_again(monkeypatch):
    """A fresh session's first bar requests may be refused with "websocket: bad handshake", and
    every sweep opens a fresh session, so such a refusal is asked again."""
    conn = _bare_connection()
    queue, pauses = _replies(monkeypatch, conn, _NOT_YET, _NOT_YET,
                             {"structuredContent": {"success": True, "bars": []}})
    assert conn.call("mcp-tv-get-ohlcv", symbol="NASDAQ:GRVL", interval="1m", count=1) == \
        {"success": True, "bars": []}
    assert not queue and pauses == [1.0, 2.0]


def test_still_not_connected_after_every_try_says_so(monkeypatch):
    conn = _bare_connection()
    _replies(monkeypatch, conn, *[_NOT_YET] * tv.TRIES)
    with pytest.raises(tv.TVRefused, match=f"bad handshake, {tv.TRIES} tries$"):
        conn.call("mcp-tv-get-ohlcv", symbol="NASDAQ:GRVL", interval="1m", count=1)


def test_any_other_refusal_is_an_answer_and_is_not_asked_again(monkeypatch):
    """A 429 can last hours: asking again would only slow every sweep."""
    conn = _bare_connection()
    queue, pauses = _replies(
        monkeypatch, conn,
        {"structuredContent": {"success": False, "error": "tradingview api: …/uk/scan: 429: "}},
        {"structuredContent": {"success": True}})
    with pytest.raises(tv.TVRefused, match="429"):
        conn.call("mcp-tv-get-symbol-data-batch", symbols=["LSE:PENR"])
    assert queue and not pauses


# =====================================================================================
# DATING A BAR
# =====================================================================================

def test_a_bar_is_dated_by_the_session_it_describes_and_fx_is_stamped_the_evening_before():
    """TradingView's stamps; `session_date()` says why FX differs."""
    assert tv.session_date(_t("2026-09-28T13:30:00")) == "2026-09-28"     # NASDAQ:GRVL
    assert tv.session_date(_t("2026-09-29T07:00:00")) == "2026-09-29"     # LSE, XETR, OMXCOP
    assert tv.session_date(_t("2026-09-27T22:00:00")) == "2026-09-28"     # FX_IDC:GBPUSD
    assert tv.session_date(_t("2026-09-24T22:00:00")) == "2026-09-25"     # ...Friday's


def test_a_named_day_takes_the_newest_session_on_or_before_it_under_its_own_date():
    """`closes()` states the rule; these are its three cases."""
    bars = [{"t": _t(f"2026-09-{d}T07:00:00"), "c": c}
            for d, c in (("28", 30.1), ("29", 30.4), ("30", 30.8), ("01", 31.0))]
    bars[-1]["t"] = _t("2026-10-01T07:00:00")
    assert tv._complete_bar(bars, "2026-09-30") == ("2026-09-30", 30.8)
    shut = [b for b in bars if tv.session_date(b["t"]) != "2026-09-30"]
    assert tv._complete_bar(shut, "2026-09-30") == ("2026-09-29", 30.4)
    with pytest.raises(tv.TVError):
        tv._complete_bar(bars, "2026-09-01")


# =====================================================================================
# THE SWEEP — each line at its own instant
# =====================================================================================

NOW_1400_UK = dt.datetime(2026, 9, 29, 13, 0, tzinfo=UTC)      # 14:00 BST: US shut, Europe open
NOW_1715_UK = dt.datetime(2026, 9, 29, 16, 15, tzinfo=UTC)     # 17:15 BST: Europe shut


# THE SWEEP'S THREE LINES, the loaded book's own: a US-venue line (shut at 14:00 UK, priced
# at its last session), a GBX line (the pence trap's subject), and a third European line.
# The quotes and bars stay CANNED and invented — only the names are the
# book's, so the same claims bite on any book that carries the wiring.
def _three_lines():
    # LINES THE BOOK PRICES: a sold-out share keeps its symbol, and has no price to sweep.
    priced = {r[0] for r in tv._rules().CURRENT_PRICES}
    syms = {t: s for t, s in tv.symbols().items() if t in priced}
    us = next((t for t, s in syms.items() if s["symbol"].split(":")[0] in ("NASDAQ", "NYSE")),
              None)
    pence = next((t for t, s in syms.items() if s["unit"] == "GBX"), None)
    # The third line must be EUROPEAN: shut by 17:15 UK, open at 14:00, like the pence line.
    third = next((t for t, s in syms.items() if t not in (us, pence)
                  and s["symbol"].split(":")[0] not in ("NASDAQ", "NYSE")), None)
    return us, pence, third


US, PENCE, THIRD = _three_lines()
SYM = {t: tv.symbols()[t]["symbol"] for t in (US, PENCE, THIRD) if t}
UNIT = {t: tv.symbols()[t]["unit"] for t in (US, PENCE, THIRD) if t}
HOLDS_LINES = holds(US, PENCE, THIRD, what="a US line, a pence line and a third European line")


def _px(ticker, raw):
    """What the record stores for a raw quote — the GBX/100 rule, restated on purpose so a
    broken divisor in the feed cannot vouch for itself."""
    return round(raw / 100, 6) if UNIT[ticker] == "GBX" else raw


def _bars(symbol_day_close):
    return {s: [{"t": _t(f"{d}T13:30:00" if s == SYM[US] else f"{d}T07:00:00"),
                 "c": c} for d, c in rows] for s, rows in symbol_day_close.items()}


def _conn(**over):
    quotes = {SYM[US]: {"close": 150.25, "currency": UNIT[US],
                        "update_mode": "delayed_streaming_900"},
              SYM[PENCE]: {"close": 50.0, "currency": UNIT[PENCE], "update_mode": "streaming"},
              SYM[THIRD]: {"close": 30.5, "currency": UNIT[THIRD],
                           "update_mode": "delayed_streaming_900"}}
    bars = _bars({SYM[US]: [("2026-09-25", 151.10), ("2026-09-28", 150.25)],
                  SYM[PENCE]: [("2026-09-28", 48.0), ("2026-09-29", 49.7)],
                  SYM[THIRD]: [("2026-09-28", 30.1), ("2026-09-29", 30.4)]})
    return FakeConnection(quotes=over.get("quotes", quotes), bars=bars,
                          refuse_quotes=over.get("refuse"), minutes=over.get("minutes"))


def _sweep(conn, now):
    return tv.sweep(tickers=[US, PENCE, THIRD], currencies=[], now=now, conn=conn)


@HOLDS_LINES
def test_a_trading_line_is_a_live_read_at_its_own_instant_and_a_shut_one_its_last_session():
    """14:00 UK: Europe trading, the US not yet open. Each line says which, and when."""
    r = _sweep(_conn(), NOW_1400_UK)
    by = {p["mark_key"]: p for p in r["prices"]}
    assert (by[US]["struck"], by[US]["as_of"], by[US]["at"]) == ("close", "2026-09-28", "")
    assert by[US]["price"] == _px(US, 150.25)
    assert (by[PENCE]["struck"], by[PENCE]["at"]) == ("live", "2026-09-29T13:00:00Z")
    assert (by[THIRD]["struck"], by[THIRD]["at"]) == ("live", "2026-09-29T12:45:00Z"), \
        "a delayed quote describes the market fifteen minutes before it was read"
    assert not r["failed"]


@HOLDS_LINES
def test_a_live_read_is_the_quote_and_never_a_part_formed_bar():
    """A line quoting 50.0p can have an unfinished day bar reading 49.7p."""
    r = _sweep(_conn(), NOW_1400_UK)
    assert next(p for p in r["prices"] if p["mark_key"] == PENCE)["raw"] == 50.0


@HOLDS_LINES
def test_a_venue_that_shut_today_prices_at_todays_close():
    """17:15 UK: LSE and XETRA have shut. A sweep is the price at the moment it is taken, so each
    takes today's close, dated today — and after midnight the same session still prices the
    same."""
    r = _sweep(_conn(), NOW_1715_UK)
    assert not r["failed"]
    by = {p["mark_key"]: p for p in r["prices"]}
    assert (by[PENCE]["struck"], by[PENCE]["as_of"], by[PENCE]["raw"]) == \
        ("close", "2026-09-29", 49.7)
    assert (by[THIRD]["struck"], by[THIRD]["as_of"], by[THIRD]["price"]) == \
        ("close", "2026-09-29", _px(THIRD, 30.4))

    after_midnight = dt.datetime(2026, 9, 29, 23, 30, tzinfo=UTC)     # 00:30 BST on 30 Sep
    by = {p["mark_key"]: p for p in _sweep(_conn(), after_midnight)["prices"]}
    assert (by[THIRD]["struck"], by[THIRD]["as_of"], by[THIRD]["at"],
            by[THIRD]["price"]) == ("close", "2026-09-29", "", _px(THIRD, 30.4))


@HOLDS_LINES
def test_when_the_quote_screen_refuses_the_trading_lines_are_unpriced_and_named():
    """Shut lines still price from completed bars; a trading line has no honest price without the
    quote, so it is reported — never filled from a bar."""
    r = _sweep(_conn(refuse="tradingview api: …/scan: 429: "), NOW_1400_UK)
    assert [p["mark_key"] for p in r["prices"]] == [US]
    assert {f["key"] for f in r["failed"]} == {PENCE, THIRD}
    assert all("429" in f["why"] for f in r["failed"])
    assert r["quote_screen"].startswith("refused")


@HOLDS_LINES
def test_a_line_the_vendor_does_not_return_is_reported_and_never_zero():
    r = _sweep(_conn(quotes={}), NOW_1400_UK)
    assert all(p["price"] for p in r["prices"])
    assert {f["key"] for f in r["failed"]} == {PENCE, THIRD}
    assert all("left this symbol out, and gave no reason" in f["why"] for f in r["failed"])


def _quote_screen_answers(conn, answer):
    """The connection, with the quote screen's reply replaced by `answer(the real reply)`."""
    real = conn.call

    def call(tool, **args):
        if tool == "mcp-tv-get-symbol-data-batch":
            return answer(real(tool, **args))
        return real(tool, **args)
    conn.call = call
    return conn


@HOLDS_LINES
def test_a_quote_screen_that_does_not_answer_costs_only_the_lines_still_trading():
    """An HTTP error on the quote screen is caught in the sweep: the closes the bars priced stand,
    and only the lines that needed a quote fail."""
    def no_answer(_):
        raise tv.TVError("TradingView tools/call: HTTP 429")
    r = _sweep(_quote_screen_answers(_conn(), no_answer), NOW_1400_UK)
    assert [p["mark_key"] for p in r["prices"]] == [US]
    assert {f["key"] for f in r["failed"]} == {PENCE, THIRD}
    assert all("it did not answer — TradingView tools/call: HTTP 429" in f["why"]
               for f in r["failed"])
    assert r["quote_screen"] == "no answer: TradingView tools/call: HTTP 429"


@HOLDS_LINES
@pytest.mark.parametrize("missing", [
    [{"symbol": None, "reason": "market unavailable"}],
    {None: "market unavailable"},
])
def test_a_partial_reply_is_not_ok_and_a_line_it_left_out_carries_the_vendors_reason(missing):
    """The vendor reports a market that failed in `partial` and `warnings`, and each symbol it left
    out in `missing`. A partial reply is not `ok`; a line left out carries the vendor's reason."""
    # the parametrised shapes name the symbol at run time — the book's own third line
    missing = ([{"symbol": SYM[THIRD], "reason": "market unavailable"}]
               if isinstance(missing, list) else {SYM[THIRD]: "market unavailable"})

    def partial(reply):
        return {"success": True, "partial": True, "warnings": ["germany: 503"],
                "missing": missing,
                "data": {s: q for s, q in reply["data"].items() if s != SYM[THIRD]}}
    r = _sweep(_quote_screen_answers(_conn(), partial), NOW_1400_UK)
    assert {p["mark_key"]: p["struck"] for p in r["prices"]} == {US: "close", PENCE: "live"}
    (f,) = r["failed"]
    assert f["key"] == THIRD and "market unavailable" in f["why"]
    assert r["quote_screen"] == "partial: germany: 503"


@HOLDS_LINES
def test_the_lines_are_asked_five_at_a_time_and_read_in_the_books_order():
    """Never more than AT_ONCE in flight, and the answer reads in the book's order whichever line
    finished first. A Saturday, so every line prices from Friday's session."""
    class Slow(FakeConnection):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.lock, self.now_in, self.most = threading.Lock(), 0, 0

        def call(self, tool, **args):
            with self.lock:
                self.now_in += 1
                self.most = max(self.most, self.now_in)
            try:
                time.sleep(0.02)
                return super().call(tool, **args)
            finally:
                with self.lock:
                    self.now_in -= 1

    symbols = ([s["symbol"] for s in tv.symbols().values()]
               + [tv.rate_symbol(c) for c in tv.rate_currencies()])
    conn = Slow(bars=_bars({s: [("2026-10-02", float(n + 1))] for n, s in enumerate(symbols)}))
    saturday = dt.datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    r = tv.sweep(tickers=list(tv.symbols()), currencies=tv.rate_currencies(), now=saturday,
                 conn=conn)
    assert not r["failed"]
    assert [p["mark_key"] for p in r["prices"]] == list(tv.symbols())
    assert [x["currency"] for x in r["rates"]] == tv.rate_currencies()
    assert 1 < conn.most <= tv.AT_ONCE


def test_no_two_requests_in_flight_share_an_id(monkeypatch):
    """A reply is matched to its request by id, and a sweep has several in flight."""
    seen, lock = [], threading.Lock()

    def urlopen(req, **k):
        body = tv.json.loads(req.data)
        with lock:
            seen.append(body["id"])
        return _Reply(tv.json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": {}}))
    monkeypatch.setattr(tv.urllib.request, "urlopen", urlopen)
    conn = _bare_connection()
    threads = [threading.Thread(target=lambda: [conn._rpc("tools/call") for _ in range(50)])
               for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(seen) == 400 and len(set(seen)) == 400


def _minute(stamp, last):
    return {"t": _t(stamp), "o": last, "h": last, "l": last, "c": last, "v": 100}


@HOLDS_LINES
def test_when_the_quote_screen_refuses_a_trading_line_takes_its_last_minute_bar():
    """When the quote screen refuses, a trading line takes its last minute bar. The price is that
    minute's last trade, struck live at the minute's end — fifteen minutes behind the read for a
    delayed venue — and a line between sessions still prices from its session."""
    minutes = {SYM[PENCE]: [_minute("2026-09-29T12:44:00", 50.05), _minute("2026-09-29T12:45:00", 50.1)],
               SYM[THIRD]: [_minute("2026-09-29T12:44:00", 30.6)]}
    r = _sweep(_conn(refuse="tradingview api: …/uk/scan: 429: ", minutes=minutes), NOW_1400_UK)
    assert not r["failed"]
    by = {p["mark_key"]: p for p in r["prices"]}
    assert (by[PENCE]["struck"], by[PENCE]["at"], by[PENCE]["price"]) == \
        ("live", "2026-09-29T12:46:00Z", 0.501)
    assert by[PENCE]["source"] == (f"TradingView 1m bar {SYM[PENCE]} 50.1 GBX / 100, "
                                   "last trade in the minute to 2026-09-29T12:46:00Z")
    assert (by[THIRD]["struck"], by[THIRD]["at"]) == ("live", "2026-09-29T12:45:00Z")
    assert by[US]["struck"] == "close"
    assert r["quote_screen"].startswith("refused")


@HOLDS_LINES
def test_a_minute_bar_from_before_the_session_opened_is_not_todays_price():
    """A share's newest minute from an earlier session is that session's last trade, and dated
    today it would be a stale price wearing a fresh date. Unpriced, with both routes' reasons."""
    minutes = {SYM[PENCE]: [_minute("2026-09-28T15:29:00", 48.0)],
               SYM[THIRD]: [_minute("2026-09-29T12:44:00", 30.6)]}
    r = _sweep(_conn(refuse="screener 429", minutes=minutes), NOW_1400_UK)
    (f,) = r["failed"]
    assert f["key"] == PENCE
    assert "screener 429" in f["why"] and "before this session opened" in f["why"]


def test_a_minute_still_running_is_struck_when_read_and_never_called_a_close():
    """The rates' minute bars are current: the newest may be a minute still running. Its instant
    is the read, not the minute's end; and its source must not say "close", which a reader
    takes for a session's close."""
    now = dt.datetime(2026, 9, 29, 13, 0, 20, tzinfo=UTC)
    conn = FakeConnection(bars={"FX_IDC:GBPUSD": [{"t": _t("2026-09-28T22:00:00"), "c": 1.3239}]},
                          minutes={"FX_IDC:GBPUSD": [_minute("2026-09-29T13:00:00", 1.3221)]},
                          refuse_quotes="screener 429")
    (rate,) = tv.sweep(tickers=[], currencies=["USD"], now=now, conn=conn)["rates"]
    assert (rate["rate"], rate["struck"], rate["at"], rate["as_of"]) == \
        (1.3221, "live", "2026-09-29T13:00:20Z", "2026-09-29")
    assert "close" not in rate["source"].lower()


@HOLDS_LINES
def test_the_pence_trap_is_caught_by_the_vendors_own_unit():
    """PENR in GBX is divided by 100; an PENR quote in GBP would be a hundredfold error, refused —
    and not papered over by the minute bars, which a wrong unit in the map would make wrong too."""
    ok = _sweep(_conn(), NOW_1400_UK)
    assert next(p for p in ok["prices"] if p["mark_key"] == PENCE)["price"] == 0.5
    quotes = dict(_conn().quotes, **{SYM[PENCE]: {"close": 0.5, "currency": "GBP",
                                                  "update_mode": "streaming"}})
    bad = _sweep(_conn(quotes=quotes, minutes={SYM[PENCE]: [_minute("2026-09-29T12:45:00", 50.1)]}),
                 NOW_1400_UK)
    assert "expected 'GBX'" in next(f["why"] for f in bad["failed"] if f["key"] == PENCE)


def test_a_live_fx_source_never_reads_as_a_close_and_a_bar_always_does():
    """A live read must not call itself a close in its source, and a completed session must: the
    source is what a reader of fx-history.csv sees beside `struck`."""
    bars = {"FX_IDC:GBPUSD": [{"t": _t("2026-09-27T22:00:00"), "c": 1.3254},
                              {"t": _t("2026-09-28T22:00:00"), "c": 1.3239}]}
    quotes = {"FX_IDC:GBPUSD": {"close": 1.3241, "currency": "USD", "update_mode": "streaming"}}
    live = tv.sweep(tickers=[], currencies=["USD"], now=NOW_1400_UK,
                    conn=FakeConnection(quotes=quotes, bars=bars))["rates"][0]
    assert live["struck"] == "live" and "close" not in live["source"].lower()
    past = tv.closes("2026-09-28", tickers=[], currencies=["USD"],
                     conn=FakeConnection(bars=bars))["rates"][0]
    assert (past["currency"], past["as_of"], past["rate"]) == ("USD", "2026-09-28", 1.3254)
    assert "close" in past["source"].lower()


# =====================================================================================
# THE MAP AGAINST THE RECORD
# =====================================================================================

def test_every_share_the_book_prices_has_a_symbol_and_a_symbol_left_unpriced_is_held_by_nothing(book):
    """THE BOOK DECIDES WHAT IS PRICED. A share with no symbol is a line left unpriced forever. A
    symbol outlives its price: a share sold out keeps its listing, and nothing holds it."""
    from portfusion.record import rules as D
    contracts = set(D.LEG_CONTRACT.values())
    shares = {r[0]: r[2] for r in D.CURRENT_PRICES
              if r[0] not in contracts and r[0] not in D.STATEMENT_PRICED}
    assert set(shares) <= set(tv.symbols())
    unpriced = set(tv.symbols()) - set(shares) - set(D.STATEMENT_PRICED)
    held = set(book.holdings(by="ticker")["ticker"])
    assert not unpriced & held, f"held with a symbol and no price: {sorted(unpriced & held)}"
    for ticker, spec in ((t, s) for t, s in tv.symbols().items() if t in shares):
        assert tv._record_unit(spec["unit"])[0] == shares[ticker], (
            f"{ticker} is quoted in {spec['unit']} and held in {shares[ticker]}")


@needs("contracts", "current-prices")
def test_a_carried_rate_is_not_fetched(monkeypatch):
    """A currency the book carries (`rules.RATE_CARRIED`, settings.csv's `rate_carried`) is not
    asked for: refreshing it would assert an observation nobody made. Nothing is carried by
    default, so one is planted; the rest are still read, each
    from the pair its currency spells."""
    from portfusion.record import rules as D
    held = [r[0] for r in D.fx_rows]
    assert held, "no live rate at all — this asserts nothing"
    monkeypatch.setattr(D, "RATE_CARRIED", {held[0]: "planted for the test"})
    assert tv.rate_currencies() == held[1:]
    assert tv.rate_symbol("USD") == "FX_IDC:GBPUSD"


# =====================================================================================
# THE RULES IT SHARES WITH feeds/ig.py
# =====================================================================================

@pytest.mark.parametrize("feed, sign_in", [("tv", "SESSION_FILE"), ("ig", "SESSION_CACHE")])
def test_a_feed_writes_nothing_but_its_own_sign_in(feed, sign_in, tmp_path):
    """IT PRINTS. YOU TICK. `desk/doors/marks.py` writes. On the syntax tree (`harness.file_calls`):
    every write a feed makes is to its own sign-in file, never a mark or an event."""
    from harness import file_calls
    planted = tmp_path / "feed.py"
    planted.write_text(f'with open({sign_in}, "w") as fh:\n    fh.write("")\n'
                       'open("buys.csv", "a")\n')
    assert [(line, call) for line, call, target in file_calls(planted) if sign_in not in target] \
        == [(3, "open")], "a planted write beyond the sign-in is found"
    writes = file_calls(SRC / "feeds" / f"{feed}.py")
    assert writes, f"feeds/{feed}.py no longer saves its sign-in: has it moved?"
    elsewhere = [(line, call) for line, call, target in writes if sign_in not in target]
    assert not elsewhere, f"feeds/{feed}.py writes beyond {sign_in}: {elsewhere}"


#: What each feed holds that is a credential, by the name it holds it under.
_SECRETS = {"tv": ("token", "refresh_token", "access_token", "verifier", "_access_token"),
            "ig": ("token", "cst", "api_key", "password", "identifier", "_cred")}


def _credentials_said(src, secrets):
    """(line, name) for each `print` or `log.*` call in `src` that reaches one of `secrets`, as a
    name, an attribute or a key."""
    found = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and (
                getattr(node.func, "id", None) == "print"
                or getattr(getattr(node.func, "value", None), "id", None) == "log"):
            said = ast.dump(node)
            found += [(node.lineno, s) for s in secrets if f"'{s}'" in said]
    return found


def test_the_token_travels_in_a_header_and_is_never_printed_or_logged():
    """A CREDENTIAL IS NEVER SAID: no `print` and no `log.*` call in either feed reaches one. The
    feeds speak through `portfusion.log`, so a guard that read `print` alone held nothing."""
    assert _credentials_said('log.info(f"renewed {self.token}")', _SECRETS["tv"]), "planted, found"
    src = (SRC / "feeds" / "tv.py").read_text()
    assert src.count('f"Bearer {self.token}"') == 1
    for feed, secrets in _SECRETS.items():
        said = _credentials_said((SRC / "feeds" / f"{feed}.py").read_text(), secrets)
        assert not said, f"feeds/{feed}.py says a credential: {said}"


# =====================================================================================
# THE DATED RATES A RECORD LACKS — one read per currency, however many dates
# =====================================================================================

def test_the_closes_a_record_lacks_take_one_read_per_currency():
    """Each wanted date takes the close of its newest session on or before it, from ONE read of
    the pair's daily bars: an FX bar stamped 22:00 UTC the evening before is that session's, a
    Saturday is answered by the Friday before it, and two dates one session serves come back
    as one row naming both."""
    usd = [{"t": _t("2026-03-30T22:00:00"), "c": 1.2901}, {"t": _t("2026-07-23T22:00:00"), "c": 1.3402}]
    sek = [{"t": _t("2026-03-30T22:00:00"), "c": 12.51}]
    conn = FakeConnection(bars={"FX_IDC:GBPUSD": usd, "FX_IDC:GBPSEK": sek})
    got = tv.rate_closes({"USD": ["2026-03-31", "2026-07-24", "2026-07-25"], "SEK": ["2026-03-31"]},
                         conn=conn, today=dt.date(2026, 10, 14))
    assert [a["symbol"] for _, a in conn.calls] == ["FX_IDC:GBPSEK", "FX_IDC:GBPUSD"]
    assert not got["failed"]
    rows = {(r["currency"], r["as_of"]): r for r in got["rates"]}
    assert set(rows) == {("USD", "2026-03-31"), ("USD", "2026-07-24"), ("SEK", "2026-03-31")}
    assert rows[("USD", "2026-07-24")]["wanted"] == ["2026-07-24", "2026-07-25"]
    assert rows[("USD", "2026-03-31")]["rate"] == 1.2901 and rows[("SEK", "2026-03-31")]["rate"] == 12.51
    assert all(r["struck"] == "close" and "close" in r["source"] for r in got["rates"])


def test_a_date_before_the_bars_reach_is_named_and_never_filled():
    """A date the bars do not reach back to is FAILED with its reason, never answered by a later
    session: a rate for the wrong day is the conversion error `rules.FX_RATE_AGE_LIMIT_DAYS` describes."""
    conn = FakeConnection(bars={"FX_IDC:GBPUSD": [{"t": _t("2026-03-30T22:00:00"), "c": 1.29}]})
    got = tv.rate_closes({"USD": ["2025-12-31"]}, conn=conn, today=dt.date(2026, 10, 14))
    assert got["rates"] == [] and [f["wanted"] for f in got["failed"]] == ["2025-12-31"]
    assert "no session on or before 2025-12-31" in got["failed"][0]["why"]


# =====================================================================================
# THE SYMBOL SEARCH — a symbol is looked up, never guessed
# =====================================================================================

def test_the_search_reads_the_hits_where_tradingview_puts_them():
    """THE REPLY NESTS ITS HITS UNDER `data.symbols`."""
    hits = [{"symbol": "LSE:MARL", "type": "stock", "exchange": "LSE", "description": "Marlow Group plc"},
            {"symbol": "GETTEX:MRL", "type": "stock", "exchange": "GETTEX", "description": "Marlow Group plc"}]
    conn = FakeConnection(hits=hits)
    assert tv.search("Marlow Group", conn=conn) == hits
    assert conn.calls == [("mcp-tv-search-symbols", {"query": "Marlow Group"})]
