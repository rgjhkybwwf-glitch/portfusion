"""
THE IG PRICE SWEEP — invariants of feeds/ig.py.

The module reaches a live broker API that can open and close real positions, so
most of what is tested here is the promise that it CANNOT. A comment saying
"read-only" is worth nothing the day someone adds a convenient dealing helper;
these tests are what makes it true.

Nothing here touches the network. The guard is checked at the point it runs —
before a request is built — so it can be exercised with no session at all.

If one fails after a change you meant to make, update the expectation and say why
in the commit message. Do not delete a test to make a build pass.
"""
import ast
import subprocess

import re

import pytest

from portfusion.feeds import ig
from harness import SRC, needs


def _fake_session(answer):
    """An `IGSession` stand-in whose transport answers `answer(label, path)`, THROUGH THE REAL
    ALLOWLIST, so no fake reaches a path the feed itself may not."""
    class _Fake:
        def __init__(self, cred, label): self.label = label
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def _request(self, method, path, version, body=None):
            ig._assert_readonly(method, path)
            return answer(self.label, path), None
    return _Fake


# =====================================================================================
# The read-only guard. This is the security claim, so it is tested hardest.
# =====================================================================================

DEALING_CALLS = [
    ("POST", "/positions/otc"),              # open a position
    ("PUT", "/positions/otc/DEAL123"),       # amend one
    ("DELETE", "/positions/otc/DEAL123"),    # close one
    ("POST", "/workingorders/otc"),          # place a working order
    ("DELETE", "/workingorders/otc/X"),
    ("GET", "/confirms/DEAL123"),            # deal confirmation — trips the "confirm" marker
    ("GET", "/positions"),                   # READ-ONLY AT IG, AND STILL REFUSED HERE: it trips
                                             # the "position" marker. Making the marker
                                             # check method-aware is a decision, not a
                                             # tweak — this line is the tripwire.
    ("POST", "/markets/../positions/otc"),   # traversal dressed up as an allowed prefix
]


@pytest.mark.parametrize("method,path", DEALING_CALLS)
def test_guard_refuses_everything_that_is_not_a_read(method, path):
    """A dealing call must be impossible, not merely absent.

    Defends against: someone adds a helper that posts to /positions/otc and the
    module quietly gains the ability to trade the book's real money.
    """
    with pytest.raises(RuntimeError):
        ig._assert_readonly(method, path)


@pytest.mark.parametrize("method,path", [
    ("POST", "/session"),
    ("DELETE", "/session"),
    ("GET", "/markets/CS.D.EXAMPLE.IP"),
    ("GET", "/markets?searchTerm=Zephyr"),
    ("GET", "/markets?epics=SB.D.HALV.DEC.IP%2CSH.D.ZEPHUS.MAR.IP&filter=SNAPSHOT_ONLY"),
    ("GET", "/accounts"),
    # Reads with no side effect, none of which trips a forbidden marker — the dealing guard
    # is untouched rather than loosened.
    ("GET", "/history/activity?from=2026-08-01T00:00:00&to=2026-08-31T23:59:59"),
    ("GET", "/history/transactions?from=2026-08-01T00:00:00"),
    ("GET", "/prices/SB.D.HALV.MAR.IP/DAY/2026-08-28T00:00:00/2026-08-28T23:59:59"),
])
def test_guard_allows_the_read_endpoints(method, path):
    """The guard must not be so tight that the sweep itself cannot run."""
    ig._assert_readonly(method, path)


def test_a_dealid_in_a_query_string_does_not_trip_the_marker_check():
    """THE MARKERS SCAN THE PATH, NOT THE QUERY. /history/activity takes a dealId filter, and
    the string "deal" is a forbidden marker — so a query parameter must not be able to refuse
    a legitimate read. _assert_readonly splits on "?" before checking, and this pins that.

    The other direction still holds: a dealing PATH is refused however it is dressed up, which
    is what the traversal case in DEALING_CALLS covers."""
    ig._assert_readonly("GET", "/history/activity?dealId=DIAAAAA0000001A&detailed=true")
    with pytest.raises(RuntimeError):
        ig._assert_readonly("GET", "/history/activity/deal/DIAAAAA0000001A")


# The guard's own vocabulary. It has to be able to NAME what it forbids, and the
# module docstring has to be able to explain the design, without this test firing
# on the explanation. Everything else is fair game.
_GUARD_NAMES = {"_ALLOWED", "_FORBIDDEN_MARKERS"}


def _code_strings(path):
    """Every string literal in the module that is NOT a docstring and NOT part of
    the guard's own definition. Comments are excluded by construction — the ast
    never sees them, and a comment cannot make a request."""
    tree = ast.parse(path.read_text())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if names & _GUARD_NAMES:
                for sub in ast.walk(node.value):
                    docstrings.add(id(sub))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


def test_no_dealing_endpoint_appears_in_code():
    """Belt-and-braces against the guard being bypassed rather than tripped.

    Defends against: a future edit that builds a urllib request directly instead
    of going through _request(), skipping _assert_readonly entirely. Endpoint
    paths in this module are string literals, so a static scan of them catches
    exactly that — while leaving the prose free to describe what is forbidden.
    """
    offenders = [s for s in _code_strings(SRC / "feeds" / "ig.py")
                 if any(m in s for m in ("/positions", "/workingorders", "/confirms"))]
    assert not offenders, (
        f"feeds/ig.py builds dealing endpoints in code: {offenders} — if a dealing "
        "call is genuinely needed it does not belong in the read-only price sweep")


# =====================================================================================
# The points convention
# =====================================================================================

def test_a_contract_mark_is_the_level_its_note_quotes(D):
    """IG quotes points and the record keeps the level as IG states it: a mark and the bid its
    own source note quotes are ONE figure, on every contract.

    SELF-ANCHORING. One hardcoded pair — a level and its mark — would move at every price run
    and need a hand edit to a literal in a test file; the note already states the raw level, so
    the record carries the expectation for EVERY contract and the test reads it. That is this
    project's own rule — derive it, never type it twice.
    """
    assert ig._level({"bid": 9862.4}, "bid") == 9862.4       # as IG states it
    pat = re.compile(r"bid\s+([\d.]+)(?:,|$)")
    checked = []
    for ticker, price, _cur, _date, source, *_ in D.CURRENT_PRICES:
        m = pat.search(str(source))
        if not m:
            continue
        raw = float(m.group(1))
        checked.append(ticker)
        assert price == raw, (
            f"{ticker}: source note says bid {raw}, but the record stores {price} — the "
            f"note and the figure were updated separately")
        assert " / 100" not in str(source) and " \u00f7 100" not in str(source), (
            f"{ticker}: the note still says the level was divided, and the record no longer "
            f"divides it")
    assert len(checked) == len(ig.epics()), (
        f"only {len(checked)} of {len(ig.epics())} mapped contracts carry a parseable raw "
        f"level in their source note ({sorted(checked)}). Every IG mark must state the "
        f"points figure it came from, or this guard silently covers less than it claims")


def test_price_side_is_a_real_side():
    """PRICE_SIDE is read straight into a snapshot lookup; a typo would KeyError
    mid-sweep, after logging in and burning API allowance."""
    assert ig.PRICE_SIDE in ("bid", "offer")


# =====================================================================================
# The epic map
# =====================================================================================

def test_every_mapped_epic_names_a_contract_the_record_prices(D):
    """A typo'd EPICS key fetches a real price and files it under a contract that
    does not exist, so the leg it was meant for stays stale and nothing complains.
    """
    priced = {t for t, *_ in D.CURRENT_PRICES}
    unknown = sorted(set(ig.epics()) - priced)
    assert not unknown, (
        f"EPICS keys not present in CURRENT_PRICES: {unknown} — keys must match the "
        "contract keys the record already uses (see LEG_CONTRACT)")


def test_mapped_epics_are_well_formed():
    """Defends against a placeholder like '<epic>' being left in and hitting the API."""
    for key, value in ig.epics().items():
        assert isinstance(value, tuple) and len(value) == 2, (
            f"EPICS[{key!r}] should be (account, epic)")
        account, epic = value
        assert account and not account.startswith("<"), f"EPICS[{key!r}] has placeholder account"
        assert epic and not epic.startswith("<"), f"EPICS[{key!r}] has placeholder epic"


# =====================================================================================
# Keeping the credentials out of git
# =====================================================================================

def test_credentials_file_is_gitignored(repo_root):
    """The one rule that must not fail: no credential ever enters this repo."""
    for name in ("credentials.json", "credentials.yaml", ".env"):
        r = subprocess.run(["git", "check-ignore", "-q", name],
                           cwd=repo_root, capture_output=True)
        assert r.returncode == 0, f"{name} is NOT gitignored — fix .gitignore before adding keys"


def test_no_credentials_file_is_tracked(repo_root):
    """Defends against a credentials file that was committed before the ignore
    rule existed — .gitignore does nothing for an already-tracked file."""
    r = subprocess.run(["git", "ls-files"], cwd=repo_root,
                       capture_output=True, text=True, check=True)
    tracked = r.stdout.split()
    bad = [f for f in tracked
           if f.startswith("credentials.") or f.endswith(".key") or f == ".env"]
    assert not bad, f"credential-shaped files are TRACKED IN GIT: {bad}"


# =====================================================================================
# The session cache, which keeps logins under IG's rate limit.
# =====================================================================================

def test_session_cache_file_is_gitignored(repo_root):
    """The cached CST and X-SECURITY-TOKEN are bearer credentials the full IG API
    accepts, dealing included, for up to 72 hours.

    Defends against: `credentials.*` looking like it covers everything sensitive.
    It does NOT match .ig_session.json, which is why that name is listed separately.
    """
    r = subprocess.run(["git", "check-ignore", "-q", ".ig_session.json"],
                       cwd=repo_root, capture_output=True)
    assert r.returncode == 0, ".ig_session.json is NOT gitignored"


def test_a_corrupt_cache_is_not_fatal(tmp_path, monkeypatch):
    """A half-written cache must mean 'log in again', never a crash mid-price-run."""
    cache = tmp_path / ".ig_session.json"
    cache.write_text("{not json")
    monkeypatch.setattr(ig, "SESSION_CACHE", str(cache))
    assert ig._load_session_cache() == {}


def test_exit_does_not_log_out():
    """__exit__ must NOT close the session.

    Logging out on exit forces every command to authenticate again, and a dozen logins in ten
    minutes rate-limit the API key. The tokens are meant to be left live and cached; --ig-logout is
    the deliberate way to end one.
    """
    src = (SRC / "feeds" / "ig.py").read_text()
    exit_body = src.split("def __exit__", 1)[1].split("def ", 1)[0]
    assert "DELETE" not in exit_body, (
        "__exit__ closes the IG session again — see the comment in that method")


# =====================================================================================
# THE EVENT SWEEP
#
# The history endpoints are a structured way, beside a statement, to learn what happened on the
# account. These test the parts that can go wrong WITHOUT a network call, which is most of them
# — the sweep's real risks are mapping and matching, not fetching.
# =====================================================================================

@needs("contracts", "buys")
def test_an_unknown_epic_resolves_to_no_ticker(D):
    """THE FAILURE THAT MATTERS. Filing a real trade against the wrong position is worse
    than not filing it, so an epic the book cannot resolve must return NOTHING and be
    reported — never guessed at by name similarity.
    """
    m = ig._epic_to_ticker(D)
    assert m, "the map is empty"
    assert m.get("XX.D.NOTREAL.DEC.IP") is None
    assert m.get("") is None


@needs("contracts", "buys")
def test_every_open_contract_resolves_to_its_line(D):
    """An epic resolves to the code its contract names, so the first bet on a contract reads
    with no leg before it."""
    m = ig._epic_to_ticker(D)
    for contract, epic in D.CONTRACTS.items():
        if epic:
            assert m[epic] == D.CONTRACT_CODE[contract]
            assert D.KIND_OF_CODE[m[epic]] == "spread bet", f"{epic} resolved to a share line"


def test_the_generated_rows_are_real_csv(D):
    """The rows are pasted into the store, so they must survive the store's own reader —
    a comma or a quote in an instrument name would otherwise split a row silently."""
    import csv
    import io
    line = ig._csv_row(["E-999", "2026-08-28", "Voss IG Spread bet", "HALV SB", 300,
                        25.5, "GBP", 7650.00, "IG REST",
                        'Closes X. Note with, a comma and "quotes"'])
    back = next(csv.reader(io.StringIO(line)))
    assert len(back) == 10
    assert back[9] == 'Closes X. Note with, a comma and "quotes"'
    assert back[3] == "HALV SB"


#: A flag that takes a required argument cannot be SELECTED without one — --ig-search
#: exits rather than opening a search for nothing. That is the command's own contract, so
#: the sample lives here rather than being softened out of dispatch().
FLAG_ARGS = {"--ig-search": ["Zephyr"]}


def _usage_flags():
    import re
    return set(re.findall(r"--ig-[a-z]+", ig.USAGE))


def _invoke(flag):
    return ig.dispatch([flag] + FLAG_ARGS.get(flag, []))


def _commands():
    import ast
    tree = ast.parse((SRC / "feeds" / "ig.py").read_text())
    return {n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name.startswith("cmd_")}


def _selects(command):
    """The cmd_* name a dispatch result would call. Handles the lambda-wrapped ones."""
    if command is None:
        return None
    if getattr(command, "__name__", "") != "<lambda>":
        return command.__name__
    return next((n for n in command.__code__.co_names if n.startswith("cmd_")), None)


def test_every_ig_command_is_reachable_from_a_flag():
    """A command nothing can invoke is a command that does not exist.

    It asks the WIRING. A check of the source text proves only a SPELLING.
    """
    reachable = {_selects(_invoke(flag)) for flag in _usage_flags()}
    missing = _commands() - reachable
    assert not missing, f"no flag reaches {sorted(missing)} — an unreachable command"


def test_every_documented_flag_lands_somewhere():
    """The opposite failure, which a check on the source text cannot see: a flag written into USAGE
    that dispatches to nothing. The usage text is a promise."""
    for flag in _usage_flags():
        assert _invoke(flag) is not None, \
            f"{flag} is documented in USAGE but dispatches to nothing"


def test_the_sweep_is_wired_to_its_own_flag():
    """The sweep's own flag reaches the sweep, asserted against the wiring rather than the
    spelling."""
    assert "--ig-events" in ig.USAGE, "the sweep is not in the usage text"
    assert _selects(ig.dispatch(["--ig-events"])) == "cmd_events"
    assert _selects(ig.dispatch(["--ig-events", "2026-08-01"])) == "cmd_events"


def test_choosing_a_command_reaches_no_broker(monkeypatch):
    """dispatch() SELECTS; it must not do. If choosing opened a session, every test above
    would be a live call to IG."""
    def _refuse(*a, **k):
        raise AssertionError("dispatch() opened an IG session merely to choose a command")
    monkeypatch.setattr(ig, "IGSession", _refuse)
    monkeypatch.setattr(ig, "load_credentials", _refuse)
    for flag in _usage_flags():
        _invoke(flag)
    assert ig.dispatch([]) is None
    assert ig.dispatch(["--not-a-flag"]) is None


# =====================================================================================
# THE STRUCTURED READS — what the cmd_* functions compute, split out so the desk can reach it.
#
# Driven against SYNTHETIC payloads, so still no network — the module docstring's promise
# holds. The point of these is not the happy path: it is that the REFUSAL branches survive
# a refactor. Each one exists because a plausible-looking number could otherwise reach the
# record attached to the wrong account, built from a mis-parsed field, or filed against a
# ticker that was guessed. A refactor that quietly dropped a `continue` would still print
# something that looked right.
# =====================================================================================

def _feed_labels(D):
    """The register's own feed keys, sorted — the labels `account_state()` visits, derived
    so the stub speaks whatever book is loaded."""
    labels = sorted(ig.account_names(D))
    assert labels, "no account carries a feed_key — this stub has nothing to speak for"
    return labels


# Good: IG's identity holds (balance - deposit + profitLoss == available).
_GOOD_BALANCE = {"balance": 12000.0, "profitLoss": 1500.0,
                 "deposit": 2500.0, "available": 11000.0}
# Bad: the identity does NOT hold, so no row may be produced from it.
_BAD_BALANCE = {"balance": 9000.0, "profitLoss": 500.0,
                "deposit": 1000.0, "available": 99999.99}


def _stub_accounts(monkeypatch, D):
    """Every register label answers the stub: the FIRST (sorted) fails IG's identity, the
    rest hold. Returns (bad label, the good labels' accounts, the register's map)."""
    labels = _feed_labels(D)
    payloads = {label: {"accounts": [{"accountId": f"ID{n}", "accountType": "SPREADBET",
                                      "balance": dict(_GOOD_BALANCE if n else _BAD_BALANCE)}]}
                for n, label in enumerate(labels)}

    def answer(label, path):
        assert path.startswith("/accounts"), f"unexpected endpoint: {path}"
        return payloads[label]

    monkeypatch.setattr(ig, "load_credentials",
                        lambda *a, **k: {label: {"env": "LIVE"} for label in labels})
    monkeypatch.setattr(ig, "IGSession", _fake_session(answer))
    by_label = ig.account_names(D)
    return labels[0], [by_label[label] for label in labels[1:]], by_label


@needs("contracts", "buys")
def test_account_state_refuses_a_row_that_fails_igs_own_identity(monkeypatch, D):
    """balance - deposit + profitLoss must equal available, or no row is produced.

    A mis-parsed field would otherwise reach the record as a perfectly plausible balance.
    The refusal is REPORTED, not swallowed: a caller that sees fewer accounts than labels
    and no explanation has been told the wrong thing.
    """
    bad, good_accounts, _ = _stub_accounts(monkeypatch, D)
    r = ig.account_state()
    assert [row["account"] for row in r["rows"]] == good_accounts
    assert len(r["refusals"]) == 1
    assert "REFUSING to print a row" in r["refusals"][0]["text"]
    assert bad in r["refusals"][0]["text"]


@needs("contracts", "buys")
def test_account_state_keeps_rows_and_refusals_in_one_ordered_sequence(monkeypatch, D):
    """`entries` is what the printer walks, and the INTERLEAVING is part of the report.

    Accounts are visited in sorted credential-label order, so the refused first label
    precedes the rows — a refusal is not collected up and appended at the end. That ordering
    is what lets the printed block be read top to bottom as one pass over the accounts.
    """
    labels = _feed_labels(D)
    _stub_accounts(monkeypatch, D)
    r = ig.account_state()
    assert [e["kind"] for e in r["entries"]] == ["refusal"] + ["row"] * (len(labels) - 1)

    # rows/refusals are VIEWS of entries, not separate work: every entry appears in exactly
    # one of them, and nothing appears that is not in entries.
    assert len(r["rows"]) + len(r["refusals"]) == len(r["entries"])
    assert all(e in r["entries"] for e in r["rows"] + r["refusals"])


@needs("contracts", "buys")
def test_account_state_never_claims_a_notional(monkeypatch, D):
    """positions_value stays blank. Notional needs the open-positions endpoint, which the
    allowlist refuses — and the two bases differ, so a guess here would be a mislabel."""
    labels = _feed_labels(D)
    if len(labels) < 2:
        # One label, and the stub fails the first on purpose: feed the single label the
        # GOOD balance instead, so there is a row to ask about.
        _stub_accounts(monkeypatch, D)
        monkeypatch.setattr(ig, "load_credentials",
                            lambda *a, **k: {labels[0]: {"env": "LIVE"}})
        monkeypatch.setattr(ig, "IGSession", _fake_session(lambda label, path: {
            "accounts": [{"accountId": "ID0", "accountType": "SPREADBET",
                          "balance": dict(_GOOD_BALANCE)}]}))
    else:
        _stub_accounts(monkeypatch, D)
    row = ig.account_state()["rows"][0]
    assert row["positions_value"] is None
    assert row["equity"] == round(row["funds"] + row["running_pl"], 2)


def test_a_label_with_no_account_name_is_refused_rather_than_guessed(monkeypatch):
    """The register's feed_key maps a credential label to the book's account. An unmapped label must
    not be resolved by guessing — that is how a figure lands on the wrong account."""
    monkeypatch.setattr(ig, "load_credentials", lambda *a, **k: {"MYSTERY_IG": {"env": "LIVE"}})
    monkeypatch.setattr(ig, "IGSession", _fake_session(lambda label, path: {
        "accounts": [{"accountId": "X", "accountType": "SPREADBET",
                      "balance": {"balance": 1.0, "profitLoss": 0.0,
                                  "deposit": 0.0, "available": 1.0}}]}))
    r = ig.account_state()
    assert r["rows"] == []
    assert "no account's feed_key" in r["refusals"][0]["text"]


# =====================================================================================
# CREDENTIALS.JSON IS NOT ONLY IG'S
#
# Another service's block has no identifier, password or env, because it is not a broker
# login, and load_credentials() skips it.
#
# A problem raises, never sys.exit(): SystemExit inherits from BaseException and slips past
# the desk's `except Exception`.
# =====================================================================================

def _creds_file(tmp_path, blocks):
    import json
    p = tmp_path / "credentials.json"
    p.write_text(json.dumps(blocks))
    p.chmod(0o600)
    return p


IG_BLOCK = {"identifier": "u", "password": "p", "api_key": "k", "env": "demo",
            "account_id": "ABC12"}
ANTHROPIC_BLOCK = {"api_key": "sk-ant-x", "workspace_id": "ws"}


def test_a_non_ig_entry_does_not_break_the_ig_credentials(tmp_path):
    """An ANTHROPIC block beside the IG ones must be ignored, not judged."""
    from portfusion.feeds import ig as I
    path = _creds_file(tmp_path, {"VOSS_IG": dict(IG_BLOCK), "ANTHROPIC": dict(ANTHROPIC_BLOCK)})
    assert sorted(I.load_credentials(str(path))) == ["VOSS_IG"], \
        "the non-IG entry was not skipped"


def test_a_credentials_problem_raises_rather_than_exiting(tmp_path):
    """CATCHABLE, so a server can report it. sys.exit() raises SystemExit, which slips past
    every `except Exception` between here and the browser."""
    from portfusion.feeds import ig as I
    path = _creds_file(tmp_path, {"VOSS_IG": {"identifier": "u", "password": "", "api_key": "k",
                                              "env": "demo"}})
    with pytest.raises(I.CredentialsError):
        I.load_credentials(str(path))
    # A FILE ANOTHER ACCOUNT CAN READ is refused before a value is read from it.
    path = _creds_file(tmp_path, {"VOSS_IG": dict(IG_BLOCK)})
    path.chmod(0o644)
    with pytest.raises(I.CredentialsError, match="chmod 600"):
        I.load_credentials(str(path))


def test_a_missing_credentials_file_raises_rather_than_exiting(tmp_path):
    """The same rule for the missing file, so the desk names IG as the vendor that is down."""
    from portfusion.feeds import ig as I
    with pytest.raises(I.CredentialsError, match="NO CREDENTIALS FILE"):
        I.load_credentials(str(tmp_path / "credentials.json"))


# =====================================================================================
# THE GENERATED ROWS FILL THEIR TABLE'S COLUMNS
# =====================================================================================

def test_every_generated_row_names_its_tables_columns_exactly():
    """A GENERATED ROW FILLS ITS TABLE'S COLUMNS: a row short of one misaligns the paste.

    feeds/ig.py does not import schema (the sweep must run without the build beside it), so the
    contract is a constant there and this is what holds the two together.
    """
    from portfusion.record import schema
    for table, cols in ig.ROW_COLUMNS.items():
        assert tuple(f.name for f in schema.TABLES[table].fields) == cols, (
            f"ig.ROW_COLUMNS[{table!r}] no longer matches the store's own columns. "
            f"A generated row that does not fill every column misaligns the paste.")


def test_a_row_missing_a_column_is_refused_rather_than_rendered():
    """The refusal is the point: a half-built row must not become a CSV line at all."""
    with pytest.raises(ValueError) as e:
        ig._event("sales", "DIAAAATEST", "close", "Voss IG Spread bet", "x", {"sale_id": "E-999"})
    assert "missing" in str(e.value)


def test_a_generated_close_carries_the_deal_id_in_the_column_for_it():
    row = ig._event("sales", "DIAAAAREF", "close", "Voss IG Spread bet", "x",
                    {"sale_id": "E-999", "date": "2026-09-01", "account": "Voss IG Spread bet",
                     "ticker": "ORLA SB", "qty": "", "stake": 1, "traded_price": 100.0,
                     "cur": "GBP", "rate": "", "proceeds": 100.0, "source": "s", "broker_ref": "DIAAAAREF",
                     "realisation_id": "R-ZZZSB", "closes": "T-999C", "note": "n"})
    assert row["values"]["broker_ref"] == "DIAAAAREF"
    assert list(row["values"]) == list(ig.ROW_COLUMNS["sales"])
    # and the printed line is the same row, so the block and the bench cannot disagree
    assert row["line"].startswith("E-999,2026-09-01,")


def _referenced_open_leg(D):
    """An OPEN spread-bet leg carrying its IG deal reference, on a mapped contract, whose
    ACCOUNT has sold the ticker since that leg was opened — the row a swept close must name,
    and the parcel it must join: that account's latest sale's. Derived, so whichever book is
    loaded supplies its own leg. Returns the leg, its deal, its epic, the parcel and the
    account's feed label."""
    from portfusion.record import schema
    th = schema.TABLES["buys"].header
    eh = schema.TABLES["sales"].header
    exits = schema.load("sales")
    closed = {r[eh.index("closes")] for r in exits if r[eh.index("closes")]}
    label_of = {acct: label for label, acct in ig.account_names(D).items()}
    for r in schema.load("buys"):
        tid, ticker, acct = r[th.index("trade_id")], r[th.index("ticker")], r[th.index("account")]
        ref, contract = str(r[th.index("broker_ref")] or ""), r[th.index("contract")]
        sales = sorted((str(e[eh.index("date")]), e[eh.index("realisation_id")]) for e in exits
                       if e[eh.index("account")] == acct and e[eh.index("ticker")] == ticker
                       and str(e[eh.index("date")]) >= str(r[th.index("date")]))
        if (str(ticker).endswith(" SB") and ref.startswith("DIAAAA") and tid not in closed
                and contract in ig.epics() and sales and acct in label_of):
            return tid, ref, ig.epics()[contract][1], sales[-1][1], label_of[acct]
    raise AssertionError("no open spread-bet leg carries a deal reference on a mapped "
                         "contract with a sale from its own holding on file — the premise is "
                         "gone")


@needs("contracts", "buys")
def test_a_swept_close_names_its_parcel_and_its_leg(monkeypatch, D):
    """The close carries the parcel and the leg on its own row, from IG's own ids: the leg whose
    broker_ref is the deal closed — including one this same sweep proposes — and the parcel its
    ACCOUNT's holding already has (named by ticker alone, a close could join a round trip in
    another account)."""
    leg_id, leg_ref, epic, parcel, label = _referenced_open_leg(D)

    def act(deal, kind, affected, day):
        return {"date": f"2026-09-{day}T10:00:00", "dealId": deal, "epic": epic,
                "details": {"size": 0.25, "level": 8000.0, "marketName": "Test",
                            "dealReference": "R", "limitLevel": None,
                            "actions": [{"actionType": kind, "affectedDealId": affected}]}}
    activity = {"activities": [
        act(leg_ref, "POSITION_OPENED", None, "27"),                       # on file already
        act("DIAAAATESTCLOSEA", "POSITION_CLOSED", leg_ref, "28"),       # the book's own leg
        act("DIAAAATESTOPEN", "POSITION_OPENED", None, "28"),
        act("DIAAAATESTCLOSEB", "POSITION_CLOSED", "DIAAAATESTOPEN", "29"),
    ]}

    _sweep_with(monkeypatch, label, lambda path:
                activity if path.startswith("/history/activity")
                else {"transactions": []} if path.startswith("/history/transactions") else None)

    r = ig.ig_events("2026-09-01")
    opened = r["opens"][0]["values"]["trade_id"]
    got = [(c["values"]["realisation_id"], c["values"]["closes"]) for c in r["closes"]]
    assert got == [(parcel, leg_id), (parcel, opened)], got

    # AND EACH READS AS THE TRADES PAGE SAYS IT: ticker, direction, stake per point, the level
    # in points or the day.
    leg = next(t for t in D.buys if t.trade_id == leg_id)
    assert [e["what"] for e in r["opens"]] == [f"{leg.ticker} · Buy · £0.25/pt · 8,000 pts"]
    assert [e["what"] for e in r["closes"]] == [f"{leg.ticker} · Sell · £0.25/pt · 8,000 pts"] * 2
    assert r["matched"] == [f"{leg.ticker} · Buy · £{leg.stake:g}/pt · 2026-09-27 · in the book"]


@pytest.mark.parametrize("epic, want", [
    ("DM.D.NEWUS.JUN.IP", ("-JUN27", "dated")), ("DM.D.NEWUS.DEC.IP", ("-DEC26", "dated")),
    ("DM.D.NEWUS.OCT.IP", ("-OCT26", "dated")), ("DM.D.NEWUS.DAILY.IP", ("-DFB", "daily")),
    ("DM.D.NEWUS.IP", ("", "dated"))])
def test_a_new_contracts_name_and_funding_are_read_off_its_epic(epic, want):
    """The month, in the year it next falls on or after the deal; a daily-funded bet is DFB."""
    got = ig.contract_suffix(epic, "2026-08-12")
    assert (got["suffix"], got["funding"]) == want


@needs("contracts", "buys")
def test_a_first_bet_on_a_contract_the_book_lacks_is_offered_for_set_up(monkeypatch, D):
    """An opening on an epic no contract carries is a set-up, carrying the trade, the epic and
    its contract's month; a close on one is skipped, having nothing in the book to close."""
    label = _referenced_open_leg(D)[4]
    epic = "DM.D.NEWUS.JUN.IP"

    def act(deal, kind, affected):
        return {"date": "2026-08-12T10:00:00", "dealId": deal, "epic": epic,
                "details": {"size": 1, "level": 50.0, "marketName": "Newco Inc (24 Hours)",
                            "dealReference": "R", "limitLevel": None,
                            "actions": [{"actionType": kind, "affectedDealId": affected}]}}
    activity = {"activities": [act("DIAAAATESTNEWOPEN", "POSITION_OPENED", None),
                               act("DIAAAATESTNEWCLOSE", "POSITION_CLOSED", "DIAAAAELSE")]}

    _sweep_with(monkeypatch, label, lambda path:
                activity if path.startswith("/history/activity")
                else {"transactions": []} if path.startswith("/history/transactions") else None)

    r = ig.ig_events("2026-08-01")
    assert not r["opens"]
    [s] = r["setups"]
    assert (s["epic"], s["suffix"], s["funding"]) == (epic, "-JUN27", "dated")
    assert (s["values"]["broker_ref"], s["values"]["ticker"], s["values"]["contract"]) == \
        ("DIAAAATESTNEWOPEN", "", "")
    assert s["what"] == "Newco Inc (24 Hours) · Buy · £1/pt · 50 pts"
    [skipped] = r["skipped"]
    assert "DIAAAATESTNEWCLOSE" in skipped and skipped.endswith("not in the book")


# =====================================================================================
# THE SWEEP ACTUALLY RUNS
#
# A store column that shares an `_event()` parameter's name (`account`) must not collide with it.
# This drives all four row kinds through the real function with a stubbed transport.
# =====================================================================================

_EVENT_ACCOUNTS = {"accounts": [{"accountId": "ABC12", "accountType": "SPREADBET",
                                 "balance": {"balance": 1.0, "deposit": 0.0,
                                             "profitLoss": 0.0, "available": 1.0}}]}

_ACTIVITY = {"activities": [
    {"date": "2026-08-20T09:17:00", "dealId": "DIAAAASWEEPOPEN", "epic": "IX.D.FTSE.DAILY.IP",
     "details": {"size": 2.0, "level": 10056.0, "marketName": "Test", "dealReference": "R1",
                 "limitLevel": None,
                 "actions": [{"actionType": "POSITION_OPENED", "affectedDealId": None}]}},
]}

_TRANSACTIONS = {"transactions": [
    {"dateUtc": "2026-08-21T00:00:00", "reference": "TX-COST", "transactionType": "WITH",
     "profitAndLoss": "£-1.34", "instrumentName": "Funding charge"},
    {"dateUtc": "2026-08-22T00:00:00", "reference": "TX-DEPO", "transactionType": "DEPO",
     "profitAndLoss": "£5,000.00", "instrumentName": "Bank transfer"},
]}


def _canned(path):
    for prefix, payload in (("/history/activity", _ACTIVITY), ("/accounts", _EVENT_ACCOUNTS),
                            ("/history/transactions", _TRANSACTIONS)):
        if path.startswith(prefix):
            return payload
    raise AssertionError(f"unexpected endpoint: {path}")


def _sweep_with(monkeypatch, label, answer=lambda path: None):
    """Sweep the register label `label`, whose session answers `answer(path)`, or the canned
    payloads where that gives None."""
    monkeypatch.setattr(ig, "load_credentials", lambda *a, **k: {label: {"env": "LIVE"}})
    monkeypatch.setattr(ig, "IGSession", _fake_session(
        lambda _label, path: got if (got := answer(path)) is not None else _canned(path)))


@pytest.fixture
def stub_events(monkeypatch, D):
    """One register label, answering the canned payloads; yields the account it maps to."""
    label = _feed_labels(D)[0]
    _sweep_with(monkeypatch, label)
    return ig.account_names(D)[label]


@needs("contracts", "buys")
def test_a_sweep_runs_and_builds_every_kind_of_row(stub_events):
    """EVERY KIND OF ROW IS BUILT, though a cost row and a capital row carry an `account` COLUMN
    of the same name as `_event()`'s own parameter."""
    account = stub_events
    r = ig.ig_events("2026-08-01")
    assert len(r["costs"]) == 1, "the funding charge did not become a row"
    assert len(r["capital"]) == 1, "the deposit did not become a row"
    assert r["costs"][0]["values"]["account"] == account
    assert r["capital"][0]["values"]["account"] == account
    # the event's own account is separate from the row's column of the same name
    assert r["costs"][0]["account"] == account


@needs("contracts", "buys")
def test_every_swept_row_fills_its_tables_columns(stub_events):
    """Not just that a row was built — that it is PASTEABLE."""
    from portfusion.record import schema
    r = ig.ig_events("2026-08-01")
    for kind in ("opens", "closes", "costs", "capital"):
        for row in r[kind]:
            want = tuple(f.name for f in schema.TABLES[row["table"]].fields)
            assert tuple(row["values"]) == want, f"{kind}: {row['table']} row misaligned"
            assert row["line"], "a row that renders no CSV line cannot be pasted"


@needs("contracts", "buys")
def test_a_swept_row_carries_what_the_bench_needs(stub_events):
    """The bench keys on the deal reference and titles the item from `what`."""
    r = ig.ig_events("2026-08-01")
    for kind in ("opens", "closes", "costs", "capital"):
        for row in r[kind]:
            assert row["ref"], f"{kind}: a row with no reference cannot reach the bench"
            assert row["what"], f"{kind}: a row with no description cannot be titled"
            assert row["kind"] in ("open", "close", "cost", "capital")


@needs("contracts", "buys")
def test_a_withdrawal_is_capital_and_only_a_funding_line_is_a_cost(monkeypatch, D):
    """IG FILES ITS FUNDING CHARGES AND A WITHDRAWAL UNDER ONE TYPE, `WITH`. A line IG names as
    interest or funding is the cost; any other `WITH` is capital leaving, proposed for the
    reader to confirm, as a deposit is."""
    txns = {"transactions": [
        {"dateUtc": "2026-08-21T00:00:00", "reference": "TX-INT", "transactionType": "WITH",
         "profitAndLoss": "£-1.52", "instrumentName": "Long Interest for US/Can shares 20/08/26"},
        {"dateUtc": "2026-08-22T00:00:00", "reference": "TX-OUT", "transactionType": "WITH",
         "profitAndLoss": "£-2,500.00", "instrumentName": "Bank withdrawal"}]}
    _sweep_with(monkeypatch, _feed_labels(D)[0], lambda path:
                txns if path.startswith("/history/transactions")
                else {"activities": []} if path.startswith("/history/activity") else None)
    r = ig.ig_events("2026-08-01")
    assert [c["ref"] for c in r["costs"]] == ["TX-INT"], r["costs"]
    assert [(c["ref"], c["values"]["amount"]) for c in r["capital"]] == [("TX-OUT", -2500.0)]


@needs("contracts", "buys")
def test_the_sweep_reads_every_page_of_both_histories(monkeypatch, D):
    """EVERY PAGE IS READ, or a busy window loses the rest. Activity links its next page
    (`metadata.paging.next`); transactions number theirs (`metadata.pageData.totalPages`)."""
    def tx(ref, day):
        return {"dateUtc": f"2026-08-{day}T00:00:00", "reference": ref, "transactionType": "DEPO",
                "profitAndLoss": "£10.00", "instrumentName": "Card deposit"}
    asked = []

    def answer(path):
        asked.append(path)
        if path.startswith("/history/activity"):
            if "page=2" in path:
                return {"activities": [], "metadata": {"paging": {"size": 0, "next": None}}}
            return {"activities": [], "metadata": {"paging": {
                "size": 0, "next": "/history/activity?version=3&page=2"}}}
        if path.startswith("/history/transactions"):
            n = 2 if "pageNumber=2" in path else 1
            return {"transactions": [tx(f"TX-{n}", f"1{n}")],
                    "metadata": {"pageData": {"pageNumber": n, "pageSize": 1, "totalPages": 2}}}
        return None
    _sweep_with(monkeypatch, _feed_labels(D)[0], answer)
    r = ig.ig_events("2026-08-01")
    assert sorted(c["ref"] for c in r["capital"]) == ["TX-1", "TX-2"], r["capital"]
    assert sum(p.startswith("/history/activity") for p in asked) == 2, asked


@needs("contracts", "buys")
def test_a_full_page_that_says_nothing_of_paging_is_refused(monkeypatch, D):
    """What follows a full page with no paging is unknown, so the sweep says so rather than
    proposing the first page as the window."""
    full = {"transactions": [
        {"dateUtc": "2026-08-21T00:00:00", "reference": f"TX-{i}", "transactionType": "DEPO",
         "profitAndLoss": "£1.00", "instrumentName": "Card deposit"} for i in range(ig.PAGE)]}
    _sweep_with(monkeypatch, _feed_labels(D)[0], lambda path:
                full if path.startswith("/history/transactions")
                else {"activities": []} if path.startswith("/history/activity") else None)
    with pytest.raises(ig.IGError, match="no paging"):
        ig.ig_events("2026-08-01")


@needs("contracts", "buys")
def test_an_account_the_sweep_did_not_read_has_no_orphans(monkeypatch, D):
    """THE REVERSE CHECK ASKS ONLY OF THE ACCOUNTS SWEPT: an account with no credentials here is
    never told its charges are missing from IG."""
    _sweep_with(monkeypatch, _feed_labels(D)[0], lambda path: {"transactions": []}
                if path.startswith("/history/transactions")
                else {"activities": []} if path.startswith("/history/activity") else None)
    elsewhere = "Unswept IG Spread bet"
    monkeypatch.setattr(D, "ACCOUNT_KIND", {**D.ACCOUNT_KIND, elsewhere: "spread bet"})
    monkeypatch.setattr(D, "ci_rows", list(D.ci_rows) + [D.CostIncomeRow(
        "2026-08-21", elsewhere, "Funding interest", "Long Interest", -1.0, "test", "")])
    r = ig.ig_events("2026-08-01")
    assert not [o for o in r["orphans"] if o["account"] == elsewhere], r["orphans"]


def test_logout_clears_the_tokens_even_when_it_cannot_say_goodbye(monkeypatch, tmp_path):
    """THE CACHE IS CLEARED HOWEVER THE GOODBYE GOES: a missing credentials file or a dropped line
    leaves no session token on disk — the one thing `logout` exists to remove."""
    cache = tmp_path / ".ig_session.json"
    monkeypatch.setattr(ig, "SESSION_CACHE", str(cache))
    ig._save_session_cache({"X": {"cst": "c", "token": "t"}})

    def gone(*a, **k):
        raise ig.CredentialsError("credentials.json is missing")
    monkeypatch.setattr(ig, "load_credentials", gone)
    with pytest.raises(ig.CredentialsError):
        ig.cmd_logout()
    assert not cache.exists(), "the cache outlived the logout"



# =====================================================================================
# A PAST DAY'S CLOSE — the quarter end, fetched after it
# =====================================================================================

def _session_answering(payload, seen, env="demo"):
    """A real IGSession whose transport answers every request with `payload`."""
    from portfusion.feeds import ig
    s = ig.IGSession({"env": env, "api_key": "k", "identifier": "i", "password": "p"}, "VOSS_IG")

    def _request(method, path, version, body=None):
        ig._assert_readonly(method, path)          # the real guard, on the real path
        seen.append((method, path, version))
        return payload, {}
    s._request = _request
    return s


def _through(monkeypatch, session):
    """Every instrument read goes through `session`, with IG's pacing switched off."""
    from contextlib import nullcontext
    from portfusion.feeds import ig
    monkeypatch.setattr(ig, "_instrument_session", lambda: nullcontext(session))
    monkeypatch.setattr(ig.time, "sleep", lambda _s: None)


def _evening(on, closes=None):
    """IG's HOUR bars across one evening, as IG stamps them: 16:00 to 22:00 UTC, each priced
    unless `closes` says otherwise."""
    closes = closes or {h: 7600.0 + h for h in range(16, 23)}
    return [{"snapshotTimeUTC": f"{on}T{h}:00:00",
             "closePrice": {"bid": closes.get(h), "ask": None if closes.get(h) is None else 1.0}}
            for h in range(16, 23)]


@pytest.mark.parametrize("on,opens_utc", [("2026-08-18", "20"), ("2026-11-18", "21")])
def test_the_close_bar_opens_at_21_00_uk_on_either_side_of_the_clock_change(on, opens_utc):
    """21:00 UK is 20:00 UTC in summer and 21:00 in winter, and the bar is found by IG's UTC
    stamp against that. Asked for as HOUR bars through the real guard."""
    seen = []
    s = _session_answering({"prices": _evening(on)}, seen)
    assert s.close_bar("SH.D.ZEPHUS.DEC.IP", on)["snapshotTimeUTC"] == f"{on}T{opens_utc}:00:00"
    assert all(m == "GET" and p.startswith("/prices/") and v == 3 for m, p, v in seen), seen
    assert "resolution=HOUR" in seen[0][1]


def test_a_contract_ig_did_not_quote_through_the_evening_has_no_close_bar():
    """Empty bars from 18:00 UK, then a 21:00 close no statement vouches for: the far-contract
    shape, so there is no bar to take."""
    thin = {h: None for h in range(16, 20)} | {20: 7608.1, 21: 7608.1, 22: 7608.1}
    s = _session_answering({"prices": _evening("2026-08-18", thin)}, [])
    assert s.close_bar("SH.D.ZEPHUS.MAR.IP", "2026-08-18") is None


def test_no_close_bar_is_borrowed_from_another_day():
    """A bar stamped 21:00 on the day before is that day's close, not this one's."""
    s = _session_answering({"prices": _evening("2026-08-17")}, [])
    assert s.close_bar("SH.D.ZEPHUS.DEC.IP", "2026-08-18") is None


def test_every_mapped_epic_may_be_asked_for_its_history():
    """The /prices/ read is on the allowlist; this proves no mapped epic trips a forbidden
    marker on the way, which would only show on the night of a close."""
    from portfusion.feeds import ig
    for key, (_account, epic) in ig.epics().items():
        ig._assert_readonly("GET", f"/prices/{epic}?resolution=DAY&from=2026-09-26T00:00:00"
                                   f"&to=2026-09-30T23:59:59")


def _snapshots(leave_out=(), delay=0, currencies=({"code": "USD"},)):
    """IG's batch reply for every mapped epic, less `leave_out`."""
    from portfusion.feeds import ig
    return {"marketDetails": [
        {"instrument": {"epic": epic, "name": key, "expiry": "DEC-26",
                        "currencies": currencies and list(currencies)},
         "snapshot": {"bid": 7690.0, "offer": 7700.0, "updateTime": "22:29:58",
                      "delayTime": delay, "marketStatus": "TRADEABLE"}}
        for key, (_holder, epic) in ig.epics().items() if key not in leave_out]}


def _levels(monkeypatch, env="live", **reply):
    from portfusion.feeds import ig
    seen = []
    _through(monkeypatch, _session_answering(_snapshots(**reply), seen, env))
    monkeypatch.setattr(ig, "_utc_now", lambda: "2026-09-03T23:30:00Z")
    return ig.contract_levels()["rows"], seen


@needs("contracts", "buys")
def test_every_level_is_one_call_through_one_session(monkeypatch):
    """One request: the batch read through the real guard, naming every mapped epic, and every row
    saying which session read it."""
    from portfusion.feeds import ig
    rows, seen = _levels(monkeypatch)
    assert len(seen) == 1 and seen[0][0] == "GET" and seen[0][2] == 2, seen
    assert seen[0][1].startswith("/markets?epics=")
    assert all(epic in seen[0][1] for _holder, epic in ig.epics().values())
    assert len(rows) == len(ig.epics()) and all(r["priced"] and r["level"] == 7690.0 for r in rows)
    assert {r["read_via"] for r in rows} == {"VOSS_IG"}
    assert {r["contract"]: r["account"] for r in rows} == {k: a for k, (a, _e) in ig.epics().items()}


@needs("contracts", "buys")
def test_a_contract_the_batch_leaves_out_is_kept_unpriced(monkeypatch):
    """IG's reply is keyed by epic, so one it did not answer for is absent from it, and the
    row stays in the list, unpriced and with no source to bank."""
    left_out = sorted(ig.epics())[0]
    rows, _ = _levels(monkeypatch, leave_out=(left_out,))
    gone = [r for r in rows if not r["priced"]]
    assert [r["contract"] for r in gone] == [left_out]
    assert gone[0]["level"] is None and gone[0]["source"] == ""
    assert "no snapshot" in gone[0]["status"]


@needs("contracts", "buys")
def test_a_live_level_is_live_whichever_gateway_answered(monkeypatch):
    """`struck` answers WHICH MOMENT; it must not answer WHICH GATEWAY as well.

    The feed says it outright: the gateway (`env`, production or `demo`) plays no part, and the
    row is dated by the UK day of the instant IG was asked.
    """
    for env in ("demo", "live"):
        rows, _ = _levels(monkeypatch, env=env)
        assert {r["env"] for r in rows} == {env}
        assert all((r["struck"], r["at"], r["as_of"]) == ("live", "2026-09-03T23:30:00Z",
                                                          "2026-09-04") for r in rows), \
            "the gateway, or the UTC date, leaked into what a level describes"
        assert all("IG updateTime 22:29:58 UTC" in r["source"] for r in rows)


def test_a_level_in_no_currency_or_the_wrong_one_is_not_a_mark(monkeypatch):
    """The read leaves out `filter=SNAPSHOT_ONLY`, which answers no currency. Every row is kept,
    unpriced."""
    for currencies in (None, ({"code": "GBP"},)):
        rows, seen = _levels(monkeypatch, currencies=currencies)
        assert "SNAPSHOT_ONLY" not in seen[0][1]
        assert not any(r["priced"] or r["source"] for r in rows)
        assert all("the record in USD" in r["status"] for r in rows)


@needs("contracts", "buys")
def test_a_delay_ig_declares_moves_the_instant_back(monkeypatch):
    """`at` is the instant the level describes: the read, less the delay IG states. `feeds/tv.py`
    strikes its delayed lines the same way."""
    rows, _ = _levels(monkeypatch, delay=15)
    assert {r["at"] for r in rows} == {"2026-09-03T23:15:00Z"}
    assert all("IG delayTime 15 min" in r["source"] for r in rows)


@needs("contracts", "buys")
def test_verify_compares_the_sweeps_own_levels(monkeypatch, D):
    """`--ig-verify` reads through `contract_levels()` rather than asking IG again, and a
    contract that did not price is NAMED, never reported as unchanged."""
    from portfusion.feeds import ig
    left_out = sorted(ig.epics())[0]
    _levels(monkeypatch, leave_out=(left_out,))
    states = {r["contract"]: r["state"] for r in ig.verify_levels()["rows"]}
    assert states.pop(left_out) == "no-price"
    assert set(states.values()) == {"ok"}


@needs("contracts", "buys")
def test_a_contracts_close_is_its_bars_bid_and_a_far_one_waits_for_the_statement(monkeypatch):
    """The same side a live level uses, dated the day asked for, and a row that says it is a close.
    A contract IG has no evening bar for (every far one) is kept, unpriced, with its status naming
    where that day's level is."""
    from portfusion.feeds import ig

    class Near:
        label, env = "VOSS_IG", "live"

        def close_bar(self, epic, on):
            return {"closePrice": {"bid": 7690.0, "ask": 7700.0}} if ".DEC." in epic else None
    _through(monkeypatch, Near())

    r = ig.contract_closes("2026-09-30")
    priced = [row for row in r["rows"] if row["priced"]]
    assert {row["contract"] for row in priced} == {k for k in ig.epics() if k.endswith("DEC26")}
    assert all(row["level"] == 7690.0 and row["as_of"] == "2026-09-30" for row in priced)
    assert all((row["struck"], row["at"]) == ("close", "") for row in priced)
    assert all("HOUR bar 2026-09-30 21:00 UK, close bid 7690.0" in row["source"]
               for row in priced)
    far = [row for row in r["rows"] if not row["priced"]]
    assert far and all("statement" in row["status"] and row["source"] == "" for row in far)


def test_verify_prints_a_new_contract_with_no_level(monkeypatch, capsys):
    """A CONTRACT NOT IN THE RECORD AND WITH NO LEVEL — a wrong epic answers none — is printed,
    and the check reports rather than raising."""
    monkeypatch.setattr(ig, "verify_levels", lambda: {"side": "bid", "rows": [
        {"contract": "NEWONE", "state": "new", "stored": None, "as_of": None, "live": None,
         "pct": None, "status": "no epic"}]})
    ig.cmd_verify()
    assert "NEWONE" in capsys.readouterr().out
