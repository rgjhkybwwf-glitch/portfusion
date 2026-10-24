"""THE REMOTE DOOR — what the hosted desk may ask, and who may ask it.

`desk/remote.py` is reached from the internet through the tunnel, so everything it answers is
pinned here, and nothing at all is answered to a caller with no session.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from portfusion.desk import actions, app as local, auth, engine, naming, panels, remote
from harness import SRC, needs

TUNNEL = "https://mac.example.ts.net"

#: The proxy secret every test's door holds, never the Mac's.
SECRET = "a-test-secret-that-is-not-the-macs"
#: The hosted desk every test's door serves, never the loaded book's: a book need not name one.
ORIGIN, RP_ID = "https://desk.example.test", "example.test"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _sign(secret=SECRET, alg="HS256", **claims):
    """A JWS as Netlify's signed proxy sends it in `x-nf-sign`, from the claims its docs show."""
    claims = {"deploy_context": "production", "exp": int(time.time()) + 3600, "iss": "netlify",
              "netlify_id": "a-site", "site_url": "https://example.netlify.app", **claims}
    head = _b64(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    body = _b64(json.dumps(claims).encode())
    sig = hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
    return f"{head}.{body}.{_b64(sig)}"


#: What every client here sends: Netlify's signature, as the hosted page's requests carry it.
SIGNED = {remote.SIGNATURE: _sign()}


@pytest.fixture(autouse=True)
def hosted(monkeypatch):
    """EVERY TEST'S DOOR SERVES ONE HOSTED DESK, the test's own, whatever the book names."""
    monkeypatch.setattr(remote, "ORIGIN", ORIGIN)
    monkeypatch.setattr(remote, "RP_ID", RP_ID)


@pytest.fixture(autouse=True)
def proxy_secret(tmp_path, monkeypatch):
    """EVERY TEST'S DOOR HOLDS ITS OWN SECRET, never the Mac's, and logs afresh."""
    path = tmp_path / "proxy_secret.json"
    path.write_text(json.dumps({"secret": SECRET}))
    monkeypatch.setattr(auth, "PROXY_SECRET", path)
    monkeypatch.setattr(remote, "_unsigned_logged", [0.0])
    return path


@pytest.fixture(autouse=True)
def readers(tmp_path, monkeypatch):
    """EVERY TEST ITS OWN FILES, never the Mac's: passkeys, readers and the sign-in log. Two
    readers to start: "test" at owner and "reader" at principal."""
    monkeypatch.setattr(auth, "KEYS", tmp_path / "passkeys.json")
    monkeypatch.setattr(auth, "READERS", tmp_path / "readers.json")
    monkeypatch.setattr(auth, "SIGNINS", tmp_path / "signins.jsonl")
    auth._save(auth.READERS, {"test": {"level": "owner", "since": 0},
                              "reader": {"level": "principal", "since": 0}})


def _opened(who):
    token = auth.open_session(who)
    yield {"Cookie": f"{auth.COOKIE}={token}"}
    auth.close(token)


@pytest.fixture()
def session():
    yield from _opened("test")


@pytest.fixture()
def principal():
    yield from _opened("reader")


@pytest.fixture(scope="module")
def client():
    return TestClient(remote.door, base_url=TUNNEL, headers=SIGNED)


def _routes(application):
    return {(m, r.path) for r in application.routes if hasattr(r, "methods")
            for m in r.methods if m != "HEAD"}


def test_the_remote_door_serves_only_the_pinned_routes():
    """EVERY ROUTE IS NAMED. A route added to the door without joining `REMOTE_ROUTES` fails
    here, so opening the hosted desk further is always a line somebody reads."""
    assert _routes(remote.door) == remote.REMOTE_ROUTES


def _reads():
    return sorted(p for m, p in remote.REMOTE_ROUTES if not p.startswith("/auth/"))


def test_every_remote_route_only_reads():
    """Reads, and nothing that runs an action, touches the bench or carries a document. The
    writing and reaching actions `test_boundaries.py` pins are all behind /api/action, which
    this door does not have. Signing in is the one exception, and it lives under /auth/."""
    assert {m for m, p in remote.REMOTE_ROUTES if not p.startswith("/auth/")} == {"GET"}
    for path in _reads():
        assert not path.startswith(("/api/action", "/api/bench", "/api/inbox", "/api/document",
                                    "/api/sweep-status")), f"{path} is work, not reading"
        assert ("GET", path) in _routes(local.app), f"{path} is not one of the Mac desk's reads"


def test_no_remote_page_is_where_the_desk_works():
    """A PAGE THAT OWNS AN ACTION IS A WORK SURFACE, and stays on the Mac. Bench and Price Refresh
    hold every action there is; a reading page that grew one would need deciding again."""
    worked = {a.panel for a in actions.all_actions()}
    assert set(remote.REMOTE_PANELS) & worked == set()
    names = [m.NAME for m in panels.all_panels()]
    assert set(remote.REMOTE_PANELS) <= set(names)
    assert list(remote.REMOTE_PANELS) == [n for n in names if n in remote.REMOTE_PANELS], \
        "the remote pages are not in the Mac desk's own order"


@needs("accounts")
def test_nothing_answers_the_remote_door_without_a_session(client, session):
    """Every route, with no cookie, with a made-up one, and with a closed one: 401 each time.
    A route that takes a quarter end is asked for the latest report the gate allows."""
    from portfusion.desk import engine
    ready = next(q["quarter_end"] for q in engine.reports()["quarters"]
                 if q["closed"] and not q["gaps"])
    token = auth.open_session("closed")
    auth.close(token)
    for path in _reads():
        url = path.replace("{name}", "dashboard").replace("{quarter_end}", ready)
        for headers in ({}, {"Cookie": f"{auth.COOKIE}=made-up"},
                        {"Cookie": f"{auth.COOKIE}={token}"}):
            assert client.get(url, headers=headers).status_code == 401, f"{url} answered"
        assert client.get(url, headers=session).status_code == 200, f"{url} refused a session"


def test_a_session_ends_when_idle_or_old():
    t = auth.open_session("test", now=0)
    assert auth.signed_in(t, now=auth.IDLE - 1) == "test"
    assert auth.signed_in(t, now=2 * auth.IDLE + 1) is None, "an idle session stayed open"
    t = auth.open_session("test", now=0)
    for hour in range(1, auth.LIFETIME // 3600 + 2):
        last = auth.signed_in(t, now=hour * 3600)
    assert last is None, "a session in use outlived its lifetime"


def test_the_remote_state_offers_no_action(client, session):
    """No buttons, and only the reading pages, so the shell draws neither the header's restart
    nor a tab the door would refuse."""
    s = client.get("/api/state", headers=session).json()
    assert s["remote"] is True and s["actions"] == []
    assert [p["name"] for p in s["panels"]] == list(remote.REMOTE_PANELS)
    assert s["freshness"] == local.state()["freshness"]


def test_a_page_kept_on_the_mac_is_refused_remotely(client, session):
    for name in ("bench", "price-refresh", "access"):
        assert client.get(f"/api/panel/{name}", headers=session).status_code == 404


def test_the_remote_door_and_the_mac_give_the_same_figures(client, session):
    """The door narrows the Mac's answers and never computes its own."""
    for name in remote.REMOTE_PANELS:
        assert client.get(f"/api/panel/{name}", headers=session).json() == \
            TestClient(local.app, base_url="http://127.0.0.1:8765").get(
                f"/api/panel/{name}").json(), f"{name} differs between the doors"


def test_a_book_that_names_no_hosted_desk_has_a_door_that_refuses_everything(
        client, session, monkeypatch):
    """The origin and the passkey domain are the book's settings. Without either the door fails
    shut, as it does with no proxy secret, and says which setting is missing."""
    for missing in ("ORIGIN", "RP_ID"):
        with monkeypatch.context() as m:
            m.setattr(remote, missing, None)
            r = client.get("/api/state", headers=session)
            assert r.status_code == 503 and "the book's settings name no" in r.json()["detail"]
            assert client.post("/auth/options", headers=session).status_code == 503
    assert client.get("/api/state", headers=session).status_code == 200


def test_a_write_from_any_other_page_is_refused(client, session):
    """`remote.ORIGIN` only, signed in or not."""
    for origin in (None, f"https://{RP_ID}", "http://127.0.0.1:8765"):
        headers = dict(session, **({"Origin": origin} if origin else {}))
        assert client.post("/api/state", headers=headers).status_code == 403


def test_every_remote_answer_is_kept_by_nobody(client, session):
    """`no-store, private` on everything, refusals included, so Netlify's proxy and the
    browser's cache hold nothing of the book."""
    for headers in ({}, session):
        r = client.get("/api/state", headers=headers)
        assert r.headers["cache-control"] == "no-store, private"
        assert r.headers["x-robots-tag"] == "noindex"


def test_the_door_sends_what_the_shells_files_are_sent_with(client, session):
    """Every header the published `/*` rule gives the shell's files, on every answer here too,
    because a proxied answer gets none of them from Netlify. The policy aside: a policy is a
    page's, and the one page this door serves, a report, sends its own."""
    from portfusion.desk import publish
    rule = publish._HEADERS.split("\n/\n", 1)[0].splitlines()
    assert rule[0] == "/*", "the first rule in _headers is no longer the shell's every file"
    shell = dict(line.strip().split(": ", 1) for line in rule[1:])
    assert shell.pop("Content-Security-Policy")
    for headers in ({}, session):
        r = client.get("/api/state", headers=headers)
        assert {k: r.headers.get(k) for k in shell} == shell


# =====================================================================================
# SIGNING IN — a passkey made in software, so enrolment and sign-in run end to end
# =====================================================================================

class SoftPasskey:
    """A P-256 passkey held in memory, answering exactly as a phone or a Mac would: a "none"
    attestation to enrol, and a signature over the authenticator data and the client data's
    hash to sign in. `origin` is the page it believes it is on."""

    def __init__(self, origin=ORIGIN, rp_id=RP_ID):
        from cryptography.hazmat.primitives.asymmetric import ec
        import os
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.id, self.count, self.user = os.urandom(16), 0, None
        self.origin, self.rp_id = origin, rp_id

    def _client(self, kind, options):
        import json
        return json.dumps({"type": kind, "challenge": options["challenge"],
                           "origin": self.origin, "crossOrigin": False}).encode()

    def create(self, options):
        import cbor2
        import hashlib
        import struct
        n = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"),
                            -3: n.y.to_bytes(32, "big")})
        data = (hashlib.sha256(self.rp_id.encode()).digest() + bytes([0x45])   # UP, UV, AT
                + struct.pack(">I", 0) + bytes(16) + struct.pack(">H", len(self.id))
                + self.id + cose)
        self.user = options["user"]["id"]
        return {"id": _b64u(self.id), "rawId": _b64u(self.id), "type": "public-key",
                "clientExtensionResults": {},
                "response": {"clientDataJSON": _b64u(self._client("webauthn.create", options)),
                             "attestationObject": _b64u(cbor2.dumps(
                                 {"fmt": "none", "attStmt": {}, "authData": data})),
                             "transports": ["internal"]}}

    def get(self, options):
        import hashlib
        import struct
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        self.count += 1
        data = (hashlib.sha256(self.rp_id.encode()).digest() + bytes([0x05])    # UP, UV
                + struct.pack(">I", self.count))
        client = self._client("webauthn.get", options)
        sig = self.key.sign(data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": _b64u(self.id), "rawId": _b64u(self.id), "type": "public-key",
                "clientExtensionResults": {},
                "response": {"clientDataJSON": _b64u(client), "authenticatorData": _b64u(data),
                             "signature": _b64u(sig), "userHandle": self.user}}


def _b64u(b):
    import base64
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


HOSTED = {"Origin": ORIGIN}


@pytest.fixture()
def door(monkeypatch):
    """A door of our own: no code waiting, no ceremony pending, a fresh limit, and a client
    whose cookie jar no other test shares."""
    monkeypatch.setattr(auth, "_code", None)
    monkeypatch.setattr(auth, "_PENDING", {})
    monkeypatch.setattr(auth, "_SESSIONS", {})
    monkeypatch.setattr(remote, "_asked", {})
    return TestClient(remote.door, base_url=TUNNEL, headers=SIGNED)


def _code(who="nia", level="owner"):
    """Asked of the Mac's own door, as the Access page and `portfusion desk --enrol` ask it."""
    r = TestClient(local.app, base_url="http://127.0.0.1:8765").post(
        "/api/enrol", json={"who": who, "level": level})
    assert r.status_code == 200, r.text
    return r.json()["code"]


def _enrol(door, pk, code, headers=None):
    headers = {**HOSTED, **(headers or {})}
    options = door.post("/auth/enrol/options", json={"code": code}, headers=headers)
    assert options.status_code == 200, options.text
    return door.post("/auth/enrol/verify", json=pk.create(options.json()), headers=headers)


def _sign_in(door, pk, headers=None):
    headers = {**HOSTED, **(headers or {})}
    options = door.post("/auth/options", headers=headers).json()
    return door.post("/auth/verify", json=pk.get(options), headers=headers)


def _session(r):
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{auth.COOKIE}=") and "HttpOnly" in cookie and "Secure" in cookie
    assert "SameSite=Strict" in cookie, \
        "the session cookie is not SameSite=Strict"
    return {"Cookie": cookie.split(";")[0]}


def test_a_passkey_enrolled_with_the_code_signs_in(door):
    pk = SoftPasskey()
    r = _enrol(door, pk, _code())
    assert r.status_code == 200 and r.json() == {"who": "nia", "level": "owner"}
    assert door.get("/api/state", headers=_session(r)).status_code == 200
    door.cookies.clear()

    r = _sign_in(door, pk)
    assert r.status_code == 200 and r.json() == {"who": "nia", "level": "owner"}
    assert door.get("/api/state", headers=_session(r)).status_code == 200
    assert oct(auth.KEYS.stat().st_mode & 0o777) == "0o600", "the key file is readable by others"


def test_an_enrol_code_works_once_within_ten_minutes_and_five_guesses(door):
    code = _code()
    assert _enrol(door, SoftPasskey(), code).status_code == 200
    second = door.post("/auth/enrol/options", json={"code": code}, headers=HOSTED)
    assert second.status_code == 403, "a code enrolled two devices"

    auth.enrol_code("nia", now=0)
    with pytest.raises(auth.Refused):
        auth.enrol_options(auth._code["code"], RP_ID, now=auth.CODE_LIFETIME + 1)

    right = auth.enrol_code("nia")["code"]
    for _ in range(auth.CODE_TRIES):
        with pytest.raises(auth.Refused):
            auth.enrol_options("WRON-GGGG", RP_ID)
    with pytest.raises(auth.Refused):
        auth.enrol_options(right, RP_ID)


def test_a_passkey_answering_another_page_is_refused(door):
    """The passkey signs the page it believes it is on. One made on any page but the hosted
    desk's is refused at enrolment and at sign-in."""
    assert _enrol(door, SoftPasskey(origin=f"https://{RP_ID}"), _code()).status_code == 403
    pk = SoftPasskey()
    assert _enrol(door, pk, _code()).status_code == 200
    pk.origin = "https://evil.example"
    assert _sign_in(door, pk).status_code == 403


def test_a_refused_passkey_tells_the_log_why_and_the_caller_only_that(door):
    """THE DOOR ANSWERS ANYONE BEFORE SIGN-IN, so the library's own words on a refused passkey,
    which name what the desk expected, never reach the caller. The caller is told the passkey was
    not accepted; the sign-in log keeps why."""
    pk = SoftPasskey()
    assert _enrol(door, pk, _code()).status_code == 200
    pk.origin = "https://evil.example"
    r = _sign_in(door, pk)
    assert r.status_code == 403 and r.json()["detail"] == "the passkey was not accepted", r.text
    refused = [s for s in auth.signins() if s["result"] == "refused"]
    assert refused and refused[-1]["detail"].startswith("the passkey was not accepted: "), refused


def test_an_answer_counts_once_and_a_stranger_counts_never(door):
    pk = SoftPasskey()
    assert _enrol(door, pk, _code()).status_code == 200
    answer = pk.get(door.post("/auth/options", headers=HOSTED).json())
    assert door.post("/auth/verify", json=answer, headers=HOSTED).status_code == 200
    assert door.post("/auth/verify", json=answer, headers=HOSTED).status_code == 403, \
        "the same answer signed in twice"
    assert _sign_in(door, SoftPasskey()).status_code == 403, "an unenrolled passkey signed in"


def test_signing_in_is_limited_per_address(door, monkeypatch):
    """ONE STRANGER CANNOT KEEP ANYONE ELSE OUT. A flood from one address leaves one "limited"
    line, and another address is still answered."""
    monkeypatch.setattr(auth, "MAX_PENDING", remote.AUTH_PER_MINUTE + 5)
    flood = {**HOSTED, "x-nf-client-connection-ip": "203.0.113.9"}
    codes = [door.post("/auth/options", headers=flood).status_code
             for _ in range(remote.AUTH_PER_MINUTE + 3)]
    assert codes[:remote.AUTH_PER_MINUTE] == [200] * remote.AUTH_PER_MINUTE
    assert set(codes[remote.AUTH_PER_MINUTE:]) == {429}
    owner = {**HOSTED, "x-nf-client-connection-ip": "198.51.100.4"}
    assert door.post("/auth/options", headers=owner).status_code == 200, \
        "one address's flood kept another out"
    limited = [s for s in auth.signins() if s["result"] == "limited"]
    assert [s["address"] for s in limited] == ["203.0.113.9"]


def test_challenges_waiting_are_held_per_address(door):
    """The same for the challenges waiting to be answered: one address fills its own share."""
    one = {**HOSTED, "x-nf-client-connection-ip": "203.0.113.9"}
    codes = [door.post("/auth/options", headers=one).status_code
             for _ in range(auth.MAX_PENDING + 1)]
    assert codes[-1] == 403 and codes[:-1] == [200] * auth.MAX_PENDING
    other = {**HOSTED, "x-nf-client-connection-ip": "198.51.100.4"}
    assert door.post("/auth/options", headers=other).status_code == 200


def test_the_address_is_the_one_the_proxy_names(door):
    from starlette.requests import Request

    def asked(headers):
        return remote.address(Request({"type": "http", "client": ("127.0.0.1", 1),
                                       "headers": [(k.encode(), v.encode())
                                                   for k, v in headers.items()]}))
    assert asked({"x-nf-client-connection-ip": "203.0.113.9",
                  "x-forwarded-for": "198.51.100.4, 10.0.0.1"}) == "203.0.113.9"
    # NOT X-FORWARDED-FOR: its first entry is the caller's own claim, a fresh one per request.
    assert asked({"x-forwarded-for": "198.51.100.4, 10.0.0.1"}) == "127.0.0.1"
    assert asked({}) == "127.0.0.1"


def test_an_ipv6_caller_is_limited_as_its_network(door):
    """ONE /64 IS ONE CALLER: eleven addresses in one prefix are refused as one would be, and
    the next prefix along is someone else."""
    codes = [door.post("/auth/options", headers={
        **HOSTED, "x-nf-client-connection-ip": f"2001:db8:1:2::{i + 1:x}"}).status_code
        for i in range(auth.MAX_PENDING + 1)]
    assert codes[-1] == 403 and codes[:-1] == [200] * auth.MAX_PENDING
    elsewhere = {**HOSTED, "x-nf-client-connection-ip": "2001:db8:1:3::1"}
    assert door.post("/auth/options", headers=elsewhere).status_code == 200


def test_a_flood_does_not_evict_an_enrolment_or_spend_its_code(monkeypatch):
    """A FULL TABLE GIVES UP A SIGN-IN BEFORE AN ENROLMENT, whose code is spent; a refused
    enrolment leaves its code to be used."""
    monkeypatch.setattr(auth, "_PENDING", {})
    monkeypatch.setattr(auth, "MAX_PENDING_ALL", 5)
    enrol = auth._pending("enrol", "reader", 0.0, "198.51.100.7", "read")
    for i in range(20):
        auth._pending("sign-in", None, float(i + 1), f"203.0.113.{i + 1}")
    assert enrol in auth._PENDING, "the reader's enrolment was evicted by the flood"

    monkeypatch.setattr(auth, "_PENDING", {})
    monkeypatch.setattr(auth, "MAX_PENDING_ALL", 500)
    monkeypatch.setattr(auth, "_code", {"code": "ABCDEFGH", "who": "reader", "level": "read",
                                        "expires": 1e12, "tries": 0})
    for _ in range(auth.MAX_PENDING):
        auth._pending("sign-in", None, 0.0, "198.51.100.7")
    with pytest.raises(auth.Refused, match="too many"):
        auth.enrol_options("ABCD-EFGH", "example.test", now=0.0, address="198.51.100.7")
    assert auth._code is not None, "a refused enrolment spent its code"


def test_the_sign_in_limit_remembers_a_bounded_number_of_callers(monkeypatch):
    """A FLOOD OF FRESH NETWORKS cannot grow the table without end: past its bound the longest
    quiet caller is forgotten."""
    monkeypatch.setattr(remote, "_asked", {})
    monkeypatch.setattr(remote, "MAX_ASKED", 3)
    for i in range(10):
        remote._ration(f"203.0.113.{i}", now=100.0 + i)
    assert len(remote._asked) <= 3


def test_signing_out_ends_the_session(door):
    r = _enrol(door, SoftPasskey(), _code())
    session = _session(r)
    assert door.post("/auth/sign-out", headers={**session, **HOSTED}).status_code == 200
    assert door.get("/api/state", headers=session).status_code == 401


def test_an_enrol_code_is_asked_of_the_mac_only(door):
    """The code comes from the Mac's door, and from a page only if it is the Mac desk's own."""
    assert ("POST", "/api/enrol") not in remote.REMOTE_ROUTES
    r = TestClient(local.app, base_url="http://127.0.0.1:8765").post(
        "/api/enrol", json={"who": "nia"}, headers={"Origin": ORIGIN})
    assert r.status_code == 403


# =====================================================================================
# ONE VERSION — the hosted page and the Mac's desk
# =====================================================================================

def test_the_remote_state_names_the_version_the_mac_would_serve(client, session):
    from portfusion.desk import bundle
    assert client.get("/api/state", headers=session).json()["version"] == bundle.version()


def test_a_mac_running_older_code_says_so_on_both_routes(client, session, monkeypatch):
    """A DESK RUNNING OLDER CODE THAN IS ON DISK works its version out partly from what it loaded
    before, so a publish cannot match it and the fix is a restart. The two routes a hosted page
    and a person at a terminal read both say whether that is the case."""
    for stale in (True, False):
        monkeypatch.setattr(engine, "source_stale",
                            lambda stale=stale: {"stale": stale, "changed_at": None, "files": []})
        assert client.get("/api/health", headers=session).json()["stale"] is stale
        assert client.get("/api/state",
                          headers=session).json()["freshness"]["source_stale"] is stale


def test_the_hosted_page_says_restart_when_the_mac_runs_older_code(repo_root):
    """A MAC RUNNING OLDER CODE CANNOT BE MATCHED BY A PUBLISH: it works its version out partly
    from the code it has loaded, so a restart is the fix. A stale Mac says restart: on the hosted
    page, with the command the guide gives, and in the Mac's header, which does not say publish
    until the desk has restarted."""
    js = (SRC / "desk" / "static" / "app.js").read_text()
    other = js[js.index("function otherVersion("):js.index("function drawUnreachable(")]
    restart = "launchctl kickstart -k gui/$UID/org.portfusion.desk"
    assert "source_stale" in other, "the version message does not ask whether the Mac is stale"
    assert restart in other, "the version message does not say how to restart the Mac's desk"
    assert restart in (repo_root / "docs" / "desk-app.md").read_text(), \
        "the page's restart command is not the one the guide gives"
    assert "portfusion desk --publish" in other, "a current Mac is no longer told to publish"
    fresh = js[js.index("function drawFreshness("):js.index("function openPanel(")]
    assert '"restart first"' in fresh and "f.source_stale ?" in fresh, \
        "the header can still say publish while the desk is stale"


def test_a_tunnel_that_is_off_reads_as_the_mac_not_answering(repo_root):
    """WITH THE FUNNEL TURNED OFF, NETLIFY ANSWERS 500 WITH AN EMPTY BODY, not a 502 or a 504, so
    an empty 500 counts as unreachable. The desk's own 500 always carries "Internal Server Error",
    so a crash on the Mac still reads as a crash."""
    js = (SRC / "desk" / "static" / "app.js").read_text()
    body = js[js.index("async function get(path)"):js.index("async function readJson(")]
    assert "r.status === 500 && !text.trim()" in body, \
        "an empty 500 from Netlify is not read as the Mac being unreachable"
    assert "[502, 504].includes(r.status)" in body, "the proxy's own 502 and 504 are no longer read"


def test_the_hosted_page_checks_the_version_before_drawing(repo_root):
    """The page reads its own version from the meta tag `desk/bundle.py` fills, and compares it
    with the door's before the first panel is painted and on every switch.

    The page is published when the owner chooses and the Mac moves at every merge, so an old
    screen over new data is the mixture `engine.source_stale()` names on the Mac: it draws
    nothing instead."""
    js = (SRC / "desk" / "static" / "app.js").read_text()
    assert 'meta[name="desk-version"]' in js
    start = js[js.index("(async function start()"):]
    assert start.index("otherVersion(s)") < start.index("paintPanel(first)"), \
        "the first panel is painted before the version is checked"
    show = js[js.index("async function show("):js.index("(async function start()")]
    assert "otherVersion(s)" in show, "a switch does not re-check the version"


def test_the_hosted_page_points_at_no_page_it_cannot_open(repo_root):
    """A POINTER TO A PAGE THE DOOR DOES NOT LIST, an instruction no hosted reader can follow, is
    left out, and Reconcile's reading line goes with it."""
    js = (SRC / "desk" / "static" / "app.js").read_text()
    link = js[js.index("const panelLink ="):js.index("const reportLink =")]
    assert '!PANELS.has(panel) ? ""' in link, "a page the door does not list is still named"
    reading = js[js.index('label: "Reading"') - 80:js.index('label: "Reading"')]
    assert 'PANELS.has("bench") ?' in reading, \
        "Reconcile's reading line is drawn where the Bench does not open"


# =====================================================================================
# LEVELS — what each reader opens, decided here on every request
# =====================================================================================

def test_each_level_opens_what_was_agreed():
    """Pinned as agreed: the same eight pages at both levels, holders off for the principal,
    and no button at either. Narrowing one changes this test."""
    assert remote.OPENS == {
        "owner": remote.Opens(pages=remote.REMOTE_PANELS, names=True),
        "principal": remote.Opens(pages=remote.REMOTE_PANELS, names=False),
    }
    assert auth.LEVELS == ("owner", "principal")


def _register_words():
    """Every word the principal may not read: register names, holders' words, numbers."""
    reg = engine.book().account_register()
    return {str(w).lower() for r in reg.itertuples(index=False)
            for w in (r.account, r.number, *r.holder_names)}


def _every_read(client, headers, ready):
    for path in _reads_paths():
        url = path.replace("{name}", "dashboard").replace("{quarter_end}", ready)
        names = remote.REMOTE_PANELS if "{name}" in path else [None]
        for name in names:
            yield client.get(url if name is None else path.replace("{name}", name),
                             headers=headers)


def _reads_paths():
    return sorted(p for m, p in remote.REMOTE_ROUTES if not p.startswith("/auth/"))


def _ready():
    return next(q["quarter_end"] for q in engine.reports()["quarters"]
                if q["closed"] and not q["gaps"])


@needs("accounts")
def test_a_principal_reads_no_holder_and_no_number_anywhere(client, principal):
    """EVERY ROUTE, EVERY PAGE, the report included: no register name, no word of a holder's
    name and no account number in anything a principal is sent, notes and all."""
    import re
    words = _register_words()
    for r in _every_read(client, principal, _ready()):
        assert r.status_code == 200, f"{r.url} refused the principal: {r.text[:200]}"
        low = r.text.lower()
        left = [w for w in words if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", low)]
        assert not left, f"{r.url} names {left} to the principal"


def test_a_principal_reads_the_macs_figures_with_the_holders_renamed(client, principal):
    """The door renames; it never computes. Each page is the Mac's own answer, renamed."""
    n = naming.of(engine.book())
    mac = TestClient(local.app, base_url="http://127.0.0.1:8765")
    for name in remote.REMOTE_PANELS:
        assert client.get(f"/api/panel/{name}", headers=principal).json() == \
            n.rename(mac.get(f"/api/panel/{name}").json()), f"{name} differs from the Mac's"
    labels = list(engine.book().account_codes()["label"])
    assert client.get("/api/holdings", headers=principal).json()["accounts"] == labels


@needs("accounts")
def test_a_principal_asks_for_an_account_by_its_code(client, principal):
    """The label and the code both narrow the ledger; a register name is a 400."""
    codes = engine.book().account_codes()
    first = codes.iloc[0]
    for sent in (first["label"], first["code"]):
        r = client.get("/api/trades", params={"account": sent}, headers=principal)
        assert r.status_code == 200
        assert {row["account"] for row in r.json()["rows"]} <= {first["label"]}
    assert client.get("/api/holdings", params={"account": first["account"]},
                      headers=principal).status_code == 400


def test_the_state_says_the_readers_level(client, session, principal):
    assert client.get("/api/state", headers=session).json()["level"] == "owner"
    assert client.get("/api/state", headers=principal).json()["level"] == "principal"


@needs("accounts")
def test_an_answer_the_renaming_cannot_clear_is_refused(client, principal, monkeypatch):
    """A holder named in a shape the renaming did not foresee is a refusal, never a send.

    THE PROBE IS THE REGISTER'S OWN: a holder's word with a digit stuck to it, which the
    substitution's letter-or-digit boundary skips and the final check's letter-only
    boundary still sees. A typed name would stop probing the day the register changed."""
    register = engine.book().account_register()
    word = max((str(w) for r in register.itertuples(index=False) for w in r.holder_names
                if str(w).strip()), key=len)
    monkeypatch.setattr(local, "panel", lambda name: {"note": f"{word}2 said so"})
    r = client.get("/api/panel/dashboard", headers=principal)
    assert r.status_code == 500 and r.json()["error"] == "withheld"
    assert word.lower() not in r.text.lower()


def test_a_reader_with_no_level_opens_nothing(door):
    """A passkey with no level is refused at sign-in until Access gives it one, and a session
    whose reader loses theirs is closed at its next request."""
    pk = SoftPasskey()
    r = _enrol(door, pk, _code("rowe", "principal"))
    held = _session(r)
    assert door.get("/api/state", headers=held).status_code == 200
    readers = auth._read(auth.READERS)
    del readers["rowe"]
    auth._save(auth.READERS, readers)
    assert door.get("/api/state", headers=held).status_code == 401
    door.cookies.clear()
    refused = _sign_in(door, pk)
    assert refused.status_code == 403 and "no level" in refused.json()["detail"]
    auth.set_level("rowe", "principal")
    assert _sign_in(door, pk).status_code == 200


def test_a_level_changed_on_the_mac_holds_from_the_next_request(door):
    r = _enrol(door, SoftPasskey(), _code("rowe", "principal"))
    held = _session(r)
    assert door.get("/api/state", headers=held).json()["level"] == "principal"
    auth.set_level("rowe", "owner")
    assert door.get("/api/state", headers=held).json()["level"] == "owner"


def test_a_level_is_changed_on_access_and_never_by_enrolling():
    """A new reader needs a level with their first code; one who has a level keeps it."""
    with pytest.raises(auth.Refused, match="no level"):
        auth.enrol_code("newcomer")
    assert auth.enrol_code("reader")["level"] == "principal"
    with pytest.raises(auth.Refused, match="change the level on Access"):
        auth.enrol_code("reader", "owner")
    with pytest.raises(auth.Refused, match="not a level"):
        auth.enrol_code("newcomer", "admin")


def test_revoking_a_device_or_a_reader_ends_their_sessions(door):
    phone, mac = SoftPasskey(), SoftPasskey()
    on_phone = _session(_enrol(door, phone, _code("rowe", "principal")))
    door.cookies.clear()
    on_mac = _session(_enrol(door, mac, _code("rowe", None)))
    door.cookies.clear()
    key = next(d["key"] for r in auth.readers() if r["who"] == "rowe" for d in r["devices"])
    auth.revoke_device(key)
    states = [door.get("/api/state", headers=h).status_code for h in (on_phone, on_mac)]
    assert sorted(states) == [200, 401], "revoking one device closed the wrong sessions"
    auth.revoke_reader("rowe")
    assert door.get("/api/state", headers=on_mac).status_code == 401
    assert door.get("/api/state", headers=on_phone).status_code == 401
    assert "rowe" not in {r["who"] for r in auth.readers()}
    assert _sign_in(door, mac).status_code == 403


def test_signing_everyone_out_closes_every_session(client, session, principal):
    assert auth.sign_everyone_out() >= 2
    for headers in (session, principal):
        assert client.get("/api/state", headers=headers).status_code == 401


def test_every_sign_in_and_refusal_is_logged_with_its_device_and_address(door):
    phone = {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                           "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 "
                           "Safari/604.1", "x-nf-client-connection-ip": "198.51.100.4"}
    pk = SoftPasskey()
    _enrol(door, pk, _code("rowe", "principal"), headers=phone)
    door.cookies.clear()
    _sign_in(door, pk, headers=phone)
    door.post("/auth/enrol/options", json={"code": "WRON-GGGG"}, headers=HOSTED)
    lines = auth.signins()
    assert [line["result"] for line in lines] == ["refused", "signed in", "enrolled"]
    assert lines[1]["who"] == "rowe" and lines[1]["device"] == "iPhone · Safari"
    assert lines[1]["address"] == "198.51.100.4"
    assert oct(auth.SIGNINS.stat().st_mode & 0o777) == "0o600"
    device = next(r for r in auth.readers() if r["who"] == "rowe")["devices"][0]
    assert device["device"] == "iPhone · Safari" and device["last_used"]


def test_the_readers_list_carries_no_key_and_no_token(door):
    r = _enrol(door, SoftPasskey(), _code("rowe", "principal"))
    listed = repr(auth.readers())
    token = _session(r)["Cookie"].split("=", 1)[1]
    assert token not in listed
    assert all(v["public_key"] not in listed for v in auth._keys().values())


@pytest.mark.parametrize("agent, named", [
    ("Mozilla/5.0 (Macintosh; Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
     "Version/18.0 Safari/605.1.15", "Mac · Safari"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0", "Windows · Edge"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like "
     "Gecko) CriOS/130.0 Mobile/15E148 Safari/604.1", "iPhone · Chrome"),
    ("", "a device"),
])
def test_a_device_is_named_by_its_kind_and_browser(agent, named):
    assert auth.device_name(agent) == named


# =====================================================================================
# ACCESS — the Mac's own page for all of the above
# =====================================================================================

MAC = "http://127.0.0.1:8765"


def _act(name, **body):
    r = TestClient(local.app, base_url=MAC).post(f"/api/action/{name}", json=body)
    assert r.status_code == 200, r.text
    return r.json()["result"]


def test_access_lists_the_readers_their_devices_and_the_log(door):
    pk = SoftPasskey()
    _enrol(door, pk, _code("rowe", "principal"))
    door.post("/auth/enrol/options", json={"code": "WRON-GGGG"}, headers=HOSTED)
    d = TestClient(local.app, base_url=MAC).get("/api/panel/access").json()["data"]
    rowe = next(r for r in d["readers"] if r["who"] == "rowe")
    assert rowe["level"] == "principal" and rowe["devices"] == 1 and rowe["now"] == "signed in"
    # SINCE IS THE READERS FILE'S, drawn in the Readers table beside the level.
    from portfusion.desk.panels import access
    held = next(r for r in auth.readers() if r["who"] == "rowe")
    assert rowe["since"] == access._when(held["since"]) and "since" in access.READER_COLUMNS
    assert [s["result"] for s in d["signins"]] == ["refused", "enrolled"]
    assert [lvl["level"] for lvl in d["levels"]] == list(auth.LEVELS)
    assert [c["code"] for c in d["codes"]] == list(engine.book().account_codes()["code"])


def test_access_buttons_issue_a_code_set_a_level_and_revoke(door):
    """Every button is a registered action on the Mac's door, inline on its row, writing no
    record; each refusal comes back as auth's own words rather than an error page."""
    from portfusion.desk import actions
    mine = [a for a in actions.all_actions() if a.panel == "access"]
    assert {a.name for a in mine} == {"access-enrol-code", "access-set-level",
                                      "access-revoke-device", "access-revoke-reader",
                                      "access-sign-everyone-out"}
    assert all(a.inline and a.writes is None and a.reaches is None for a in mine)

    issued = _act("access-enrol-code", who="rowe", level="principal")
    assert issued["ok"] and issued["level"] == "principal" and len(issued["code"]) == 9
    assert _act("access-enrol-code", who="rowe")["ok"] is False, "a new reader needed no level"
    _enrol(door, SoftPasskey(), issued["code"])
    assert _act("access-set-level", who="rowe", level="owner") == \
        {"ok": True, "who": "rowe", "level": "owner"}
    key = next(r for r in auth.readers() if r["who"] == "rowe")["devices"][0]["key"]
    assert _act("access-revoke-device", key=key)["ok"]
    assert _act("access-revoke-device", key=key) == {"ok": False, "error": "no such device"}
    assert _act("access-revoke-reader", who="rowe")["ok"]
    assert _act("access-sign-everyone-out")["ok"]


def test_no_page_but_the_macs_own_may_press_an_access_button():
    r = TestClient(local.app, base_url=MAC).post(
        "/api/action/access-sign-everyone-out", json={}, headers={"Origin": ORIGIN})
    assert r.status_code == 403


# =================================================================================================
# ONLY NETLIFY MAY KNOCK — the signed proxy
# =================================================================================================

def _unsigned_client():
    return TestClient(remote.door, base_url=TUNNEL)


@pytest.mark.parametrize("why, token", [
    ("unsigned", None),
    ("another secret", _sign(secret="not-the-secret")),
    ("expired", _sign(exp=int(time.time()) - remote.SIGNATURE_LEEWAY - 60)),
    ("not Netlify's", _sign(iss="someone-else")),
    ("a deploy preview", _sign(deploy_context="deploy-preview")),
    ("another algorithm", _sign(alg="none")),
    ("garbage", "not.a.signature"),
])
def test_a_request_netlify_did_not_sign_is_refused_before_anything_else(why, token, session):
    """Every route, signing in included, refuses a request without Netlify's signature over it,
    with or without a session. Why the door needs it is the register's."""
    c = _unsigned_client()
    headers = {} if token is None else {remote.SIGNATURE: token}
    for method, path in [("GET", "/api/state"), ("GET", "/api/health"), ("POST", "/auth/options")]:
        r = c.request(method, path, headers={**headers, **session, **HOSTED})
        assert r.status_code == 403, f"{why}: {method} {path} answered {r.status_code}"
        assert r.json()["detail"] == "not through the hosted desk"
        assert r.headers["cache-control"] == remote.PRIVATE["Cache-Control"]


def test_a_signed_request_goes_on_to_the_session_check(session):
    c = _unsigned_client()
    assert c.get("/api/state", headers=SIGNED).status_code == 401
    assert c.get("/api/state", headers={**SIGNED, **session}).status_code == 200


def test_with_no_secret_on_the_mac_the_door_fails_shut(proxy_secret, session):
    """A door that cannot check the signature refuses everything, even a request Netlify
    signed: a missing or emptied secret file must never leave it open."""
    c = _unsigned_client()
    for body in (None, "{}", '{"secret": ""}', "not json"):
        if body is None:
            proxy_secret.unlink()
        else:
            proxy_secret.write_text(body)
        assert c.get("/api/state", headers={**SIGNED, **session}).status_code == 403, body


def test_a_flood_of_unsigned_requests_spends_nobodys_limit_and_logs_one_line(door):
    """Refused before the limit is asked, so a caller round the hosted page cannot use up a
    real reader's share; logged once a minute, so the Access page's log stays readable."""
    c = _unsigned_client()
    named = {**HOSTED, "x-nf-client-connection-ip": "203.0.113.9"}
    for _ in range(remote.AUTH_PER_MINUTE + 5):
        assert c.post("/auth/options", headers=named).status_code == 403
    assert remote._asked == {}
    lines = [s for s in auth.signins() if "not through the hosted desk" in s["detail"]]
    assert len(lines) == 1 and lines[0]["detail"].endswith("unsigned")
    assert door.post("/auth/options", headers=named).status_code == 200


def test_the_signature_is_checked_against_the_secret_and_the_clock():
    """The checks one by one, away from any route."""
    secret = SECRET.encode()
    assert remote.signed_by_netlify(_sign(), secret) is None
    late = int(time.time()) - 10
    assert remote.signed_by_netlify(_sign(exp=late), secret) is None, "the leeway was not given"
    later = time.time() + 7200
    assert remote.signed_by_netlify(_sign(), secret, now=later) == "an expired signature"
    head, body, sig = _sign().split(".")
    forged = _b64(json.dumps({"iss": "netlify", "exp": 2 ** 40,
                              "deploy_context": "production"}).encode())
    assert remote.signed_by_netlify(f"{head}.{forged}.{sig}", secret) == \
        "a signature that does not verify"
    assert remote.signed_by_netlify(_sign(), None) == "the Mac holds no proxy secret"
