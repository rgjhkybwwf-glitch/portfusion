"""ACCESS — who can open the hosted desk, at which level, and from which devices. The Mac only.

The readers, each with their level and their devices; the button that issues an enrol code; a
revoke for a device and for a reader; the sign-in log for the last 30 days; and the key from each
account's code to its name, which nobody but the owner is shown. It decides nothing: the levels'
reach and the readers who hold them are read from the remote door and from `desk/auth.py`.

THE REMOTE DOOR HAS NO ROUTE TO IT. It is not in `remote.REMOTE_PANELS`, and its actions, like
every action, answer only on the Mac's own door.

ITS ACTIONS WRITE NO RECORD. A level, a revoke and the log are the hosted desk's own files beside
the passkeys (`desk/auth.py`), so each declares `writes=None`; a code lives in memory for ten
minutes. Each is drawn by the page on the row it acts on, so all are inline.
"""
from __future__ import annotations

import datetime as _dt

from portfusion.desk import auth, engine
from portfusion.desk.actions import Action, register

NAME = "access"
TITLE = "Access"
#: Last, and apart from the thread of the work: who reads the book is not work on it.
ORDER = 90
APART = True

#: A READER'S "SINCE" is when they were given their first level, kept beside it in the readers
#: file; it was sent and drawn nowhere until 13 Oct 2026.
READER_COLUMNS = ("who", "level", "since", "devices", "last_signed_in", "now")
DEVICE_COLUMNS = ("device", "enrolled", "last_used")
SIGNIN_COLUMNS = ("at", "result", "who", "device", "address", "detail")
CODE_COLUMNS = ("code", "label", "account")

#: How long the log on the page reaches back.
LOG_DAYS = 30


def _when(t) -> str | None:
    """An instant as this Mac's wall clock reads it, to the minute."""
    return _dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M") if t else None


def data() -> dict:
    from portfusion.desk import panels, remote
    titles = {m.NAME: m.TITLE for m in panels.all_panels()}
    readers = [{
        "who": r["who"], "level": r["level"], "since": _when(r["since"]),
        "devices": len(r["devices"]), "last_signed_in": _when(r["last_signed_in"]),
        "now": "signed in" if r["signed_in"] else "signed out",
        "device_list": [{"key": d["key"], "device": d["device"], "enrolled": _when(d["enrolled"]),
                         "last_used": _when(d["last_used"])} for d in r["devices"]],
    } for r in auth.readers()]
    codes = engine.book().account_codes()
    return {
        "levels": [{"level": level, "pages": [titles[p] for p in opens.pages],
                    "names": opens.names} for level, opens in remote.OPENS.items()],
        "readers": readers,
        "signins": [{**s, "at": _when(s["at"])} for s in auth.signins(LOG_DAYS)],
        "log_days": LOG_DAYS,
        "codes": codes[list(CODE_COLUMNS)].to_dict("records"),
        "code_minutes": auth.CODE_LIFETIME // 60,
        "columns": {"readers": READER_COLUMNS, "devices": DEVICE_COLUMNS,
                    "signins": SIGNIN_COLUMNS, "codes": CODE_COLUMNS},
    }


def _answer(fn) -> dict:
    """An action's result, or its refusal in `desk/auth.py`'s own words."""
    try:
        return {"ok": True, **fn()}
    except auth.Refused as e:
        return {"ok": False, "error": str(e)}


# THE BUTTONS. The page draws each on the row it acts on and says on the button what it does, so
# none carries a summary for the registry's strip to show; revoking asks the owner to confirm first.
#
# ISSUE AN ENROL CODE: one device may enrol a passkey for one reader, typed at the hosted sign-in.
# A new reader's level comes with the code. It lives in this process's memory, for ten minutes.
register(Action(name="access-enrol-code", label="Issue an enrol code", panel=NAME, inline=True,
                run=lambda who, level=None: _answer(lambda: auth.enrol_code(who, level or None))))
# SET THE LEVEL, which the hosted desk applies from the reader's next request.
register(Action(name="access-set-level", label="Set the level", panel=NAME, inline=True,
                run=lambda who, level: _answer(lambda: auth.set_level(who, level))))
# REVOKE A DEVICE: its passkey is forgotten and every session it opened closes.
register(Action(name="access-revoke-device", label="Revoke", panel=NAME, inline=True,
                run=lambda key: _answer(lambda: auth.revoke_device(key))))
# REVOKE A READER: all their devices at once, and the level with them.
register(Action(name="access-revoke-reader", label="Revoke the reader", panel=NAME, inline=True,
                run=lambda who: _answer(lambda: auth.revoke_reader(who))))
# SIGN EVERYONE OUT of the hosted desk; each reader signs in again.
register(Action(name="access-sign-everyone-out", label="Sign everyone out", panel=NAME,
                inline=True,
                run=lambda: _answer(lambda: {"signed_out": auth.sign_everyone_out()})))
