"""THE DESK'S LAUNCHAGENT — the desk started at login, for one book, by `portfusion desk
--install-agent` typed in that book's folder. macOS only.

ONE DESK AGENT PER MAC USER, under one label (`LABEL`): the desk listens on one port, so a second
agent could only fight the first for it. Installing again for the same book rewrites the plist
and restarts the agent on it; an agent already installed for ANOTHER book is refused, never
replaced, and so is any other agent that runs the desk — each is named, with the command that
removes it. Nothing is deleted that this module did not write.

WHAT THE PLIST SAYS is everything the agent needs, so no shell profile is read:
  * the interpreter that typed the command — the book's own venv, which runs the release the
    book pins (docs/environment.md);
  * `PORTFUSION_BOOK`, absolute, and the book's folder to run in;
  * the remote door on `REMOTE_PORT`, when the book's settings name a hosted desk;
  * a log in ~/Library/Logs.

`desk/restart.py` finds the job again from inside it (`launchd_job()`), whatever its label.
"""
from __future__ import annotations

import pathlib
import plistlib
import subprocess
import sys
import time

#: The agent's launchd label, and its plist's name.
LABEL = "org.portfusion.desk"
#: Where a user's LaunchAgents live; a test points it elsewhere.
AGENTS = pathlib.Path.home() / "Library" / "LaunchAgents"
#: Where the agent's output goes.
LOG = pathlib.Path.home() / "Library" / "Logs" / "portfusion-desk.log"
#: The remote door's port, which the tunnel forwards to (docs/desk-app.md).
REMOTE_PORT = 8768


class Refused(Exception):
    """The agent was not installed, and the message says why and what to do."""


def plist_path() -> pathlib.Path:
    return AGENTS / f"{LABEL}.plist"


def plist(book: pathlib.Path, python: str, remote_port: int | None) -> dict:
    """The agent's plist for `book`, run by `python`, with the remote door on `remote_port` (None:
    the Mac's desk alone)."""
    args = [python, "-m", "portfusion.desk", "--no-open"]
    if remote_port is not None:
        args += ["--remote-port", str(remote_port)]
    return {"Label": LABEL, "ProgramArguments": args,
            "EnvironmentVariables": {"PORTFUSION_BOOK": str(book)},
            "WorkingDirectory": str(book), "RunAtLoad": True, "ProcessType": "Interactive",
            "StandardOutPath": str(LOG), "StandardErrorPath": str(LOG)}


def _desk_agents() -> dict[str, dict]:
    """Every LaunchAgent of this user's that runs the desk, by its plist's file name."""
    found = {}
    for path in sorted(AGENTS.glob("*.plist")):
        try:
            data = plistlib.loads(path.read_bytes())
        except Exception:                       # noqa: BLE001 — not ours to judge, only to skip
            continue
        if "portfusion.desk" in data.get("ProgramArguments", []):
            found[path.name] = data
    return found


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["/bin/launchctl", *args], capture_output=True, text=True)


def _target() -> str:
    import os
    return f"gui/{os.getuid()}/{LABEL}"


def _pid() -> int | None:
    import re
    m = re.search(r"^\s*pid = (\d+)$", _launchctl("print", _target()).stdout, re.MULTILINE)
    return int(m.group(1)) if m else None


def _unload() -> None:
    """Boot the agent out and wait for its desk to exit: bootstrapping while the old process
    still holds the label fails with launchd's "Input/output error"."""
    pid = _pid()
    _launchctl("bootout", _target())
    for _ in range(100):
        if pid is None or _launchctl("print", _target()).returncode != 0:
            break
        time.sleep(0.1)


def install(book: pathlib.Path, remote_port: int | None, python: str = sys.executable) -> str:
    """Write the agent's plist for `book` and (re)load it. Returns what was done, in a line.

    Side effects: writes `plist_path()`; boots out and bootstraps the launchd job `LABEL`.
    Raises Refused, writing nothing, off macOS, when the agent serves another book, or when
    another agent runs the desk."""
    if sys.platform != "darwin":
        raise Refused("the desk's agent is a macOS LaunchAgent: on this system, start the desk "
                      "with `portfusion desk`")
    others = {name: data for name, data in _desk_agents().items() if name != plist_path().name}
    if others:
        raise Refused("another LaunchAgent already runs the desk, and would hold its port:\n"
                      + "".join(f"  ~/Library/LaunchAgents/{name}  (label {data.get('Label')})\n"
                                f"    launchctl bootout gui/$UID/{data.get('Label')} && "
                                f"rm ~/Library/LaunchAgents/{name}\n"
                                for name, data in others.items()))
    if plist_path().exists():
        held = plistlib.loads(plist_path().read_bytes()).get("EnvironmentVariables", {}) \
            .get("PORTFUSION_BOOK")
        if held != str(book):
            raise Refused(f"the desk's agent serves another book, {held}. To move it here, "
                          f"remove it first:  portfusion desk --uninstall-agent")
    AGENTS.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    plist_path().write_bytes(plistlib.dumps(plist(book, python, remote_port)))
    _unload()
    done = _launchctl("bootstrap", _target().rsplit("/", 1)[0], str(plist_path()))
    if done.returncode != 0:
        raise Refused(f"the plist is written ({plist_path()}), but launchd would not load it: "
                      f"{done.stderr.strip() or done.returncode}")
    door = f", the remote door on {remote_port}" if remote_port is not None else ""
    return f"the desk starts at login for {book}{door} — {plist_path()}"


def uninstall() -> str:
    """Stop the agent and remove its plist. Returns what was done, in a line.

    Side effects: boots out the launchd job `LABEL`; deletes `plist_path()`, which this module
    wrote, and nothing else."""
    if not plist_path().exists():
        return "no desk agent is installed"
    _unload()
    plist_path().unlink()
    return f"the desk's agent is stopped and removed ({plist_path()})"
