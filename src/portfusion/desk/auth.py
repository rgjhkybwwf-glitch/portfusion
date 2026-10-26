"""WHO IS SIGNED IN AT THE REMOTE DOOR, AT WHICH LEVEL, and the sessions a passkey opens.

    from portfusion.desk import auth
    token = auth.open_session("alex")        # after a passkey is verified
    auth.signed_in(token)                     # "alex", or None once idle, expired or revoked
    auth.level("alex")                        # "owner", or None: a reader with none opens nothing

ONLY THE REMOTE DOOR ASKS. The Mac's own door answers on 127.0.0.1 alone and has no sign-in;
`desk/remote.py` is reached through the tunnel and refuses everything but signing in until this
says who is asking, and at which level.

SESSIONS LIVE IN MEMORY, so a restart signs everyone out and costs one Face ID. Nothing about a
session is written to disk, and a stolen cookie dies with the process.

A LEVEL BELONGS TO A READER, NOT TO A DEVICE, and it is read on every request rather than carried
in the session, so a change on the Mac's Access page holds from the next request. What each level
opens is `desk/remote.py`'s `OPENS`. A reader with no level signs in to nothing until the owner
gives them one.

THREE FILES, ALL ON THIS MAC AND OUT OF GIT (.gitignore): the passkeys, the readers and their
levels, and the sign-in log. None of them is the record.
"""
from __future__ import annotations

import functools
import json
import pathlib
import secrets
import threading
import time
from dataclasses import dataclass

from portfusion import brand
from portfusion.record import schema

#: Who may read a book is that book's: the three files live in its folder (`schema.BOOK`).
BOOK = schema.BOOK

#: The cookie. `__Host-` makes the browser refuse it unless it is Secure, has Path=/ and names no
#: Domain — bound to the hosted desk's exact host and never sent to the passkey domain itself.
COOKIE = "__Host-desk"

#: Signed out after this long without a request, and after this long whatever happens.
IDLE = 12 * 3600
LIFETIME = 7 * 24 * 3600

#: The levels a reader may hold, highest first. The owner is the
#: firm's own reader; a principal is a holder of the book, who reads it with the holders taken out.
LEVELS = ("owner", "principal")

#: ONE LOCK ROUND THE PASSKEYS, THE READERS AND THE TABLES IN MEMORY. The doors answer on a pool
#: of threads, so each function that reads a file and writes it back, or reads or changes a table,
#: holds it whole: a revoke cannot fall between a sign-in's read and its write-back, and a session
#: is opened only while its passkey is still on file.
LOCK = threading.RLock()


def _held(fn):
    @functools.wraps(fn)
    def under_the_lock(*args, **kwargs):
        with LOCK:
            return fn(*args, **kwargs)
    return under_the_lock


@dataclass
class _Session:
    who: str
    key: str            # the passkey that opened it, so revoking a device closes its sessions
    opened: float
    seen: float


_SESSIONS: dict[str, _Session] = {}


@_held
def open_session(who: str, key: str = "", now: float | None = None) -> str:
    """A new session for `who`, opened by passkey `key`, returned as the token the cookie
    carries."""
    now = time.time() if now is None else now
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = _Session(who, key, now, now)
    return token


@_held
def signed_in(token: str | None, now: float | None = None) -> str | None:
    """Who holds this token, or None. An idle or expired session is closed on the way."""
    now = time.time() if now is None else now
    s = _SESSIONS.get(token or "")
    if s is None:
        return None
    if now - s.seen > IDLE or now - s.opened > LIFETIME:
        del _SESSIONS[token]
        return None
    s.seen = now
    return s.who


@_held
def close(token: str | None) -> None:
    _SESSIONS.pop(token or "", None)


@_held
def _close_where(match) -> int:
    gone = [t for t, s in _SESSIONS.items() if match(s)]
    for t in gone:
        del _SESSIONS[t]
    return len(gone)


def sign_everyone_out() -> int:
    """Close every open session; each reader's next request asks for their passkey again."""
    return _close_where(lambda s: True)


def cookie(token: str, max_age: int = LIFETIME) -> str:
    """The Set-Cookie value. HttpOnly, so no script on the page can read it; SameSite=Strict, so
    no other site's page can send it."""
    return (f"{COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; "
            f"Max-Age={max_age}")


# =================================================================================================
# PASSKEYS. A public key per enrolled device, verified with the `webauthn` package. No password
# exists anywhere, so there is none to steal, and a passkey only answers the page it was made on.
#
# ENROLMENT NEEDS THE MAC. The Access page's button, or `portfusion desk --enrol alex`, asks the
# running desk for a one-time code; typed into the hosted sign-in page, it lets that device
# register a passkey for "alex". Nobody who cannot reach the Mac's own desk can enrol anything.
#
# A CEREMONY IS ONE CHALLENGE. Each sign-in or enrolment is handed a random challenge; the answer
# must sign that challenge, for the hosted page's own origin, within five minutes, once.
# =================================================================================================

#: The enrolled passkeys: who, the credential's id, its public key, its signature count, the
#: device it was made on and when it last signed in. Public keys, not secrets — but they say who
#: may sign in, so the file stays on this Mac (.gitignore).
KEYS = BOOK / ".desk_passkeys.json"

#: Each reader's level, and since when they have been a reader. Out of git with the keys.
READERS = BOOK / ".desk_readers.json"

#: One line per sign-in, enrolment, refusal and limit, appended: the Access page reads it.
SIGNINS = BOOK / ".desk_signins.jsonl"
#: Past this many lines the oldest half goes, so a flood of refusals cannot fill the disk.
SIGNINS_MAX_LINES = 20_000

#: THE SECRET NETLIFY SIGNS WITH, beside the passkeys and out of git (`.gitignore`, and
#: `.githooks/pre-commit` refuses its value in any file). `{"secret": "..."}`. Here rather than in
#: `desk/remote.py` so a publish can ask for it without loading the web framework.
PROXY_SECRET = BOOK / ".desk_proxy_secret.json"
#: The Netlify environment variable holding the same secret, which `desk/publish.py` names in the
#: signed redirects. Netlify needs it scoped to Runtime.
PROXY_SECRET_ENV = "DESK_PROXY_SECRET"

#: How the browser names the site in its passkey prompt: the book's name, since the hosted desk is
#: the book's, on its own domain.
RP_NAME = brand.NAME

#: An enrol code dies after this long, after one use, or after this many wrong guesses.
CODE_LIFETIME = 600
CODE_TRIES = 5
#: A challenge is answered within this long. At most `MAX_PENDING` wait for one address, so a
#: stranger fills their own share and nobody else's; past `MAX_PENDING_ALL` the address holding
#: the most gives up its oldest, so a flood spends its own share and not a reader's.
CEREMONY_LIFETIME = 300
MAX_PENDING = 10
MAX_PENDING_ALL = 500

#: Letters that cannot be misread for one another when typed from a terminal.
_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"

_code: dict | None = None
_PENDING: dict[bytes, dict] = {}

#: AN IPv6 CALLER IS ITS /64. One network is handed a /64 and can draw a fresh address from it for
#: every request, so a limit per IPv6 address is no limit.
IPV6_PREFIX = 64


def limit_key(address: str) -> str:
    """Who a limit counts: the address itself, or an IPv6 address's /64. Unparseable, as given."""
    import ipaddress
    try:
        ip = ipaddress.ip_address(str(address).strip())
    except ValueError:
        return str(address)
    if ip.version == 6:
        if ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/{IPV6_PREFIX}", strict=False))
    return str(ip)


class Refused(Exception):
    """A sign-in or enrolment that did not happen, with the reason the page shows. `detail` is
    what only the sign-in log hears: the door answers anyone before sign-in, so a library's own
    account of a refusal, which names what the desk expected, is not sent to the caller."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason)
        self.detail = detail


def proxy_secret() -> bytes | None:
    """The secret, read afresh on every call so a new one holds without a restart; None when the
    file is missing, empty or does not parse."""
    try:
        secret = json.loads(PROXY_SECRET.read_text()).get("secret", "")
    except (OSError, ValueError, AttributeError):
        return None
    return secret.encode() if secret else None


def _read(path: pathlib.Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _save(path: pathlib.Path, data: dict) -> None:
    """Written whole, to a temporary file first, so a crash cannot leave half a list."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.chmod(0o600)
    tmp.replace(path)


def _keys() -> dict[str, dict]:
    return _read(KEYS)


def _save_keys(keys: dict[str, dict]) -> None:
    _save(KEYS, keys)


# =================================================================================================
# READERS AND THEIR LEVELS — what the Mac's Access page shows and changes
# =================================================================================================

def _name(who: str) -> str:
    who = str(who or "").strip().lower()
    if not who.isidentifier():
        raise Refused(f"{who!r} is not a reader's name: letters, digits and _ only")
    return who


def _level(level: str) -> str:
    if level not in LEVELS:
        raise Refused(f"{level!r} is not a level: {', '.join(LEVELS)}")
    return level


def level(who: str | None) -> str | None:
    """The reader's level, or None: no level is set, or there is no such reader."""
    return _read(READERS).get(who or "", {}).get("level")


@_held
def set_level(who: str, new: str, now: float | None = None) -> dict:
    """Give a reader a level, from the next request on. A reader is someone with a passkey."""
    who, new = _name(who), _level(new)
    if who not in {k["who"] for k in _keys().values()}:
        raise Refused(f"{who!r} has no passkey; enrol a device for them first")
    readers = _read(READERS)
    readers[who] = {**readers.get(who, {"since": int(time.time() if now is None else now)}),
                    "level": new}
    _save(READERS, readers)
    return {"who": who, "level": new}


@_held
def revoke_device(key: str) -> dict:
    """Forget one passkey, and close every session it opened."""
    keys = _keys()
    gone = keys.pop(key, None)
    if gone is None:
        raise Refused("no such device")
    _save_keys(keys)
    return {"who": gone["who"], "device": gone.get("device", ""),
            "signed_out": _close_where(lambda s: s.key == key)}


@_held
def revoke_reader(who: str) -> dict:
    """Forget a reader: every passkey they hold and their level, and close their sessions."""
    who = _name(who)
    keys = _keys()
    mine = [k for k, v in keys.items() if v["who"] == who]
    readers = _read(READERS)
    if not mine and who not in readers:
        raise Refused(f"no reader called {who!r}")
    for k in mine:
        del keys[k]
    _save_keys(keys)
    readers.pop(who, None)
    _save(READERS, readers)
    return {"who": who, "devices": len(mine), "signed_out": _close_where(lambda s: s.who == who)}


@_held
def readers(now: float | None = None) -> list[dict]:
    """Every reader, owner first: their level (None until one is set), their devices, when they
    last signed in, and whether a session of theirs is open now. Nothing secret: no public key
    and no session token leaves this function."""
    now = time.time() if now is None else now
    keys, held = _keys(), _read(READERS)
    names = sorted({v["who"] for v in keys.values()} | set(held),
                   key=lambda w: (LEVELS.index(held[w]["level"]) if held.get(w, {}).get("level")
                                  in LEVELS else len(LEVELS), w))
    out = []
    for who in names:
        devices = sorted(({"key": k, "device": v.get("device") or "a device",
                           "enrolled": v.get("enrolled"), "last_used": v.get("last_used")}
                          for k, v in keys.items() if v["who"] == who),
                         key=lambda d: d["enrolled"] or 0)
        used = [d["last_used"] for d in devices if d["last_used"]]
        out.append({"who": who, "level": held.get(who, {}).get("level"),
                    "since": held.get(who, {}).get("since"), "devices": devices,
                    "last_signed_in": max(used) if used else None,
                    "signed_in": any(s.who == who and now - s.seen <= IDLE
                                     and now - s.opened <= LIFETIME
                                     for s in _SESSIONS.values())})
    return out


def device_name(user_agent: str | None) -> str:
    """What kind of device and browser enrolled a passkey, from the browser's own description of
    itself — enough to tell a reader's phone from their Mac on the Access page, no more."""
    ua = user_agent or ""
    kind = next((name for name, mark in (("iPhone", "iPhone"), ("iPad", "iPad"),
                                         ("Android", "Android"), ("Mac", "Macintosh"),
                                         ("Windows", "Windows"), ("Linux", "Linux"))
                 if mark in ua), "a device")
    browser = next((name for name, mark in (("Edge", "Edg"), ("Firefox", "Firefox/"),
                                            ("Firefox", "FxiOS/"), ("Chrome", "CriOS/"),
                                            ("Chrome", "Chrome/"), ("Safari", "Safari/"))
                    if mark in ua), "")
    return f"{kind} · {browser}" if browser else kind


# =================================================================================================
# THE SIGN-IN LOG — every attempt the door answered, kept on the Mac
# =================================================================================================

#: What a line's `result` may say.
RESULTS = ("signed in", "enrolled", "refused", "limited")


@_held
def log(result: str, address: str = "", who: str | None = None, device: str | None = None,
        detail: str = "", now: float | None = None) -> None:
    """Append one line. Never raises: a log that cannot be written must not stop a sign-in, and
    nothing here is the record."""
    assert result in RESULTS, result
    line = {"at": int(time.time() if now is None else now), "result": result,
            "address": address, "who": who, "device": device, "detail": detail}
    try:
        with SIGNINS.open("a") as f:
            f.write(json.dumps(line) + "\n")
        SIGNINS.chmod(0o600)
        if SIGNINS.stat().st_size > SIGNINS_MAX_LINES * 120:
            lines = SIGNINS.read_text().splitlines()
            if len(lines) > SIGNINS_MAX_LINES:
                tmp = SIGNINS.with_suffix(".tmp")
                tmp.write_text("\n".join(lines[len(lines) // 2:]) + "\n")
                tmp.chmod(0o600)
                tmp.replace(SIGNINS)
    except OSError:
        pass


def signins(days: int = 30, now: float | None = None) -> list[dict]:
    """The log's lines from the last `days`, newest first."""
    since = (time.time() if now is None else now) - days * 86400
    if not SIGNINS.exists():
        return []
    out = []
    for raw in SIGNINS.read_text().splitlines():
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if line.get("at", 0) >= since:
            out.append(line)
    return out[::-1]


# =================================================================================================
# THE CEREMONIES
# =================================================================================================

@_held
def enrol_code(who: str, new_level: str | None = None, now: float | None = None) -> dict:
    """A one-time code that lets one device enrol a passkey for `who`. Replaces any earlier code.

    A NEW READER NEEDS A LEVEL, given here and set when their first device enrols. A reader who
    has one keeps it: a level is changed on the Access page, never by enrolling a device."""
    global _code
    who = _name(who)
    held = level(who)
    if held and new_level and new_level != held:
        raise Refused(f"{who} reads at {held}; change the level on Access, not with a code")
    if not held:
        if not new_level:
            raise Refused(f"{who} has no level yet: give one with the code ({', '.join(LEVELS)})")
        _level(new_level)
    now = time.time() if now is None else now
    code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    _code = {"code": code, "who": who, "level": held or new_level,
             "expires": now + CODE_LIFETIME, "tries": 0}
    return {"code": f"{code[:4]}-{code[4:]}", "who": who, "level": held or new_level,
            "minutes": CODE_LIFETIME // 60}


@_held
def _pending(kind: str, who: str | None, now: float, address: str = "",
             new_level: str | None = None) -> bytes:
    from webauthn.helpers import generate_challenge
    for c in [c for c, p in _PENDING.items() if p["expires"] < now]:
        del _PENDING[c]
    key = limit_key(address)
    if sum(limit_key(p["address"]) == key for p in _PENDING.values()) >= MAX_PENDING:
        raise Refused("too many sign-ins at once; try again in a few minutes")
    while len(_PENDING) >= MAX_PENDING_ALL:
        # NOT THE OLDEST OF ALL, which puts a flood from many networks ahead of a reader part-way
        # through signing in, or through an enrolment whose code is already spent.
        # A SIGN-IN GOES BEFORE AN ENROLMENT, which cannot be begun again without a new code.
        pool = [c for c in _PENDING if _PENDING[c]["kind"] != "enrol"] or list(_PENDING)
        counts = {}
        for c in pool:
            counts[limit_key(_PENDING[c]["address"])] = \
                counts.get(limit_key(_PENDING[c]["address"]), 0) + 1
        most = max(counts, key=counts.get)
        del _PENDING[min((c for c in pool if limit_key(_PENDING[c]["address"]) == most),
                         key=lambda c: _PENDING[c]["expires"])]
    challenge = generate_challenge()
    _PENDING[challenge] = {"kind": kind, "who": who, "level": new_level, "address": address,
                           "expires": now + CEREMONY_LIFETIME}
    return challenge


def _answered(credential: dict, kind: str, now: float) -> tuple[bytes, dict]:
    """The challenge this answer signed, if it is one we asked, of this kind, still waiting."""
    from webauthn.helpers import base64url_to_bytes
    try:
        client = json.loads(base64url_to_bytes(credential["response"]["clientDataJSON"]))
        challenge = base64url_to_bytes(client["challenge"])
    except (KeyError, TypeError, ValueError):
        raise Refused("that is not a passkey's answer")
    p = _PENDING.pop(challenge, None)
    if p is None or p["kind"] != kind or p["expires"] < now:
        raise Refused("that sign-in had expired; start again")
    return challenge, p


@_held
def enrol_options(code: str, rp_id: str, now: float | None = None, address: str = "") -> str:
    """Spend the code, and hand the browser what it needs to make a passkey."""
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers import base64url_to_bytes
    from webauthn.helpers.structs import (AuthenticatorSelectionCriteria,
                                          PublicKeyCredentialDescriptor,
                                          ResidentKeyRequirement, UserVerificationRequirement)
    global _code
    now = time.time() if now is None else now
    held = _code
    if held is None or held["expires"] < now:
        raise Refused("no enrol code is waiting; issue one on the Mac's Access page")
    if code.replace("-", "").strip().upper() != held["code"]:
        held["tries"] += 1
        if held["tries"] >= CODE_TRIES:
            _code = None
        raise Refused("that is not the code")
    who = held["who"]
    # THE CEREMONY IS OPENED BEFORE THE CODE IS SPENT, so a refusal for too many waiting leaves
    # the code unspent.
    challenge = _pending("enrol", who, now, address, held["level"])
    _code = None
    options = generate_registration_options(
        rp_id=rp_id, rp_name=RP_NAME, user_name=who, user_id=who.encode(),
        challenge=challenge,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(k))
                             for k, v in _keys().items() if v["who"] == who])
    return options_to_json(options)


@_held
def enrol_verify(credential: dict, rp_id: str, origin: str, now: float | None = None,
                 device: str = "") -> tuple[str, str]:
    """Keep the new passkey, give a new reader the level their code carried, and open their
    session: (who, the session's token)."""
    from webauthn import verify_registration_response
    from webauthn.helpers import bytes_to_base64url
    from webauthn.helpers.exceptions import WebAuthnException
    now = time.time() if now is None else now
    challenge, p = _answered(credential, "enrol", now)
    try:
        v = verify_registration_response(
            credential=credential, expected_challenge=challenge, expected_rp_id=rp_id,
            expected_origin=origin, require_user_verification=True)
    except WebAuthnException as e:
        raise Refused("the passkey was not accepted", detail=str(e))
    key = bytes_to_base64url(v.credential_id)
    keys = _keys()
    keys[key] = {"who": p["who"], "public_key": bytes_to_base64url(v.credential_public_key),
                 "sign_count": v.sign_count, "enrolled": int(now), "last_used": int(now),
                 "device": device}
    _save_keys(keys)
    if not level(p["who"]) and p.get("level"):
        readers = _read(READERS)
        readers[p["who"]] = {"level": p["level"], "since": int(now)}
        _save(READERS, readers)
    return p["who"], open_session(p["who"], key, now)


def sign_in_options(rp_id: str, now: float | None = None, address: str = "") -> str:
    """A challenge for any passkey this desk knows; the browser offers the ones it holds."""
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement
    now = time.time() if now is None else now
    return options_to_json(generate_authentication_options(
        rp_id=rp_id, challenge=_pending("sign-in", None, now, address),
        user_verification=UserVerificationRequirement.REQUIRED))


@_held
def sign_in_verify(credential: dict, rp_id: str, origin: str,
                   now: float | None = None) -> tuple[str, str]:
    """Who signed in, and their session's token — (who, token) — once their passkey has signed
    the challenge AND they hold a level. A reader with none is refused here, before any session."""
    from webauthn import verify_authentication_response
    from webauthn.helpers import base64url_to_bytes
    from webauthn.helpers.exceptions import WebAuthnException
    now = time.time() if now is None else now
    challenge, _ = _answered(credential, "sign-in", now)
    keys = _keys()
    name = credential.get("id", "")
    key = keys.get(name)
    if key is None:
        raise Refused("this passkey is not enrolled on the desk")
    try:
        v = verify_authentication_response(
            credential=credential, expected_challenge=challenge, expected_rp_id=rp_id,
            expected_origin=origin, credential_public_key=base64url_to_bytes(key["public_key"]),
            credential_current_sign_count=key["sign_count"], require_user_verification=True)
    except WebAuthnException as e:
        raise Refused("the passkey was not accepted", detail=str(e))
    if not level(key["who"]):
        raise Refused(f"{key['who']} has no level yet; the owner sets one on the Mac's Access page")
    key["sign_count"], key["last_used"] = v.new_sign_count, int(now)
    _save_keys(keys)
    return key["who"], open_session(key["who"], name, now)
