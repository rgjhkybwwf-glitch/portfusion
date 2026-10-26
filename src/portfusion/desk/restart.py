"""RESTART THE DESK — the button for "it does not show".

    from portfusion.desk import restart
    restart.restart()          # replace this server with one that has read the source again

WHY IT EXISTS. A running desk serves what it IMPORTED at startup: change engine.py and the
browser shows yesterday's figures with nothing wrong in the code. Nothing else replaces a stale
server — the LaunchAgent that starts the desk does not check what code it is running
(docs/desk-app.md) — so the check is a button inside the page, because the page is what you are
looking at when you notice.

IT IS NOT A WRITER AT ALL. It touches no file: store/ and `_inbox/` are untouched. What it
changes is which PROCESS is listening, which is why it is a module of its own rather than a
function in a panel.
`tests/desk/test_process.py` holds that it writes nothing.

HOW IT REPLACES ITSELF, and why not simply exec. The listening socket has to be released before
a new server can bind it, and a process cannot both hold a port and wait for it to be free. So a
DETACHED CHILD is spawned first: it waits for this pid to disappear, then starts a fresh desk on
the same port. This process answers the request, then exits. The browser polls /api/health until
`started` moves, and reloads.

UNDER THE AGENT, LAUNCHD RESTARTS IT. A replacement this process spawned would be nobody's
child (ppid 1), and the LaunchAgent would no longer own the desk: a later `launchctl kickstart`
could not stop it, and the agent's fresh copy would find the ports taken. So when launchd names
THIS pid as its job's, the detached child asks launchd to `kickstart -k` that job instead, and
the plist's own arguments and environment come back with it. `XPC_SERVICE_NAME` alone is not
proof — a desk started from a terminal or an app inherits that app's — so the label it gives is
believed only if launchd reports this pid for it.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading

from portfusion.desk.actions import Action, register

#: How long the caller has to receive its answer before this process goes away. The response is
#: already written by then; this is only about not dying mid-write.
EXIT_DELAY = 0.5

_WAITER = """
import os, socket, subprocess, sys, time
pid, port, project, extra = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4:]

# WAIT FOR THE OLD PROCESS, NOT FOR A FIXED DELAY. os.kill(pid, 0) raises once it is gone.
for _ in range(400):
    try:
        os.kill(pid, 0)
    except OSError:
        break
    time.sleep(0.05)

# AND THEN FOR EACH PORT, which outlives the process by a moment in TIME_WAIT.
for p in [port, *extra[1::2]]:
    for _ in range(400):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", int(p)))
            s.close()
            break
        except OSError:
            s.close()
            time.sleep(0.05)

os.chdir(project)
subprocess.Popen([sys.executable, "-m", "portfusion.desk", "--no-open", "--port", port, *extra],
                 cwd=project, start_new_session=True)
"""


_KICKSTART = """
import subprocess, sys, time
time.sleep(float(sys.argv[1]))
subprocess.run(["/bin/launchctl", "kickstart", "-k", sys.argv[2]],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
"""


def launchd_job() -> str | None:
    """The launchd service target (`gui/<uid>/<label>`) whose running pid is THIS process, or None.

    None for a desk started by hand, and for one that merely inherited another job's
    `XPC_SERVICE_NAME` — launchd must report this pid for the label before it is believed.
    """
    label = os.environ.get("XPC_SERVICE_NAME", "")
    if not label or label == "0":
        return None
    target = f"gui/{os.getuid()}/{label}"
    try:
        out = subprocess.run(["/bin/launchctl", "print", target], capture_output=True,
                             text=True, timeout=5).stdout
    except Exception:                           # noqa: BLE001 — no launchctl: started by hand
        return None
    m = re.search(r"^\s*pid = (\d+)$", out, re.MULTILINE)
    return target if m and int(m.group(1)) == os.getpid() else None


def _exit() -> None:
    """os._exit, NOT sys.exit: uvicorn catches SystemExit and would keep serving. Dying abruptly
    is right here, since a replacement is already waiting for the port, but never part-way through
    a write: every door holds `schema.LOCK` from its first read to its last write."""
    from portfusion.record import schema
    with schema.LOCK:
        os._exit(0)


def restart(port: int = 8765) -> dict:
    """Hand this server's port to a fresh process. Returns before it goes.

    Side effects: under the agent, SPAWNS a detached `launchctl kickstart -k` of its job, which
    stops this process and starts the plist's; otherwise SPAWNS a detached replacement and EXITS
    this process shortly after replying. Writes nothing, anywhere. The caller gets
    `{"ok": True, "pid": ...}` and should then poll `/api/health` until `started` changes.
    """
    job = launchd_job()
    if job:
        try:
            child = subprocess.Popen(
                [sys.executable, "-c", _KICKSTART, str(EXIT_DELAY), job],
                start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:                  # noqa: BLE001 — the button must report, not raise
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return {"ok": True, "pid": child.pid, "port": port,
                "detail": f"launchd restarts {job} once this reply is sent"}

    from portfusion.record import schema
    project = str(schema.BOOK)              # the book's folder: the desk needs no checkout
    # THE REMOTE DOOR COMES BACK WITH IT, on the port it had: a restart that dropped it would
    # leave the hosted desk pointing at nothing until someone noticed.
    from portfusion.desk import remote
    extra = ["--remote-port", str(remote.PORT)] if remote.PORT else []
    try:
        child = subprocess.Popen(
            [sys.executable, "-c", _WAITER, str(os.getpid()), str(port), project, *extra],
            cwd=project, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:                      # noqa: BLE001 — the button must report, not raise
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    threading.Timer(EXIT_DELAY, _exit).start()
    return {"ok": True, "pid": child.pid, "port": port,
            "detail": "a replacement is waiting for this process to exit"}


# THE BUTTON IS THE SHELL'S. Every page draws it on the rail's freshness line, which is where a
# stale desk is noticed; no page lists it, and the hosted desk, whose door lists no actions, never
# shows it. `writes=None` IS LITERAL: it touches no file at all; what it replaces is the PROCESS.
# `desk/actions.py:_load_panels()` imports this module so the button is in the registry before
# the registry is read, as every panel's are.
register(Action(
    name="restart-desk", label="Restart the desk", panel="desk",
    writes=None,
    gate="The owner clicks it — nothing restarts on a timer, on a file change, or after a commit",
    summary=("Replace this server with one that has read the source again. A running desk "
             "serves what it imported at startup, so a change to engine.py or a panel is "
             "invisible until it restarts — a browser refresh cannot fix that. It writes "
             "nothing: the store and _inbox/ are untouched."),
    # NO DEFAULT PORT. The page sends the one it is connected to; a default of 8765 would let
    # a desk on another port restart the one on 8765 instead — a different server entirely.
    run=lambda port: restart(int(port)),
))
