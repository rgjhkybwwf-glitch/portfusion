"""THE RUN'S STOP HOOK (`.claude/settings.json`): a run of the loop cannot end while a pull request
it pushed to has `guard` pending, while a helper agent it started has not returned, or when its last
message is not a debrief whose last line begins `Next:` (CONTRIBUTING.md, Telling the maintainer).
Claude Code runs it each time a turn would end, with the turn's details on stdin; a block is said
on stdout, and the run goes on with the reason.

A RUN is a session whose first message says `Follow CONTRIBUTING's section "…"` with the name of
the section the runs table is under, as each routine's prompt does. The name is read from
CONTRIBUTING.md each time, so a renamed section, or a new row in the table, needs no change here.
Any other session, one with the maintainer included, is never held.

IT NEVER HOLDS A RUN FOREVER. `guard` is waited for at most WAIT_GUARD minutes from the first hold
of a wait, a helper at most WAIT_HELPER, and a debrief asked for at most ASK_DEBRIEF times each time
the run would end; then the run may end. A pull request whose `guard` has not started counts only
for NOT_STARTED minutes from its last change: GitHub runs none on a pull request that cannot merge.
GitHub out of reach, Claude Code not saying which helpers are out, or the hook failing, holds
nothing. A run's pull request is the open one whose head is a local branch, `main` apart, that
`origin` also has; a helper is a subagent Claude Code lists as still in flight.

EACH HOLD IS WRITTEN DOWN, in the file the hook keeps for the session in the temp folder: no token
and no network. `python3 tools/stop_hook.py --holds` prints them as the run's end line says them,
"held 1× for `guard`, 12 min", and prints nothing for a run that was never held (the skill
`end-of-run`).
"""
from __future__ import annotations

import calendar
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from portfusion.log import log      # the hook runs without the venv: src/ is put first

ROOT = Path(__file__).resolve().parents[1]
FOLLOW = 'Follow CONTRIBUTING\'s section "{}"'
TABLE = "| Level | Run |"
LEGACY = ("The nightly agent",)     # the routines' prompts until the restart switches them
WAIT_GUARD = 60
WAIT_HELPER = 60
ASK_DEBRIEF = 2
NOT_STARTED = 10

LOGGED = (" This hold is logged: the run's end line on the run log says it (the skill "
          "`end-of-run`).")
REASON = {
    "guard": "`guard` has not finished on {}. Wait for it in the foreground, by a command that "
             "polls the checks, fix it if it fails, and only then send the debrief "
             "(CONTRIBUTING.md, Building and Telling the maintainer)." + LOGGED,
    "helper": "A helper agent has not returned: {}. Wait for its completion notification, by a "
              "command in the foreground, act on its result, and only then send the debrief "
              "(CONTRIBUTING.md, Telling the maintainer)." + LOGGED,
    "debrief": "The run ends with its debrief: a few lines, your last message, whose last line "
               "begins `Next:` (CONTRIBUTING.md, Telling the maintainer)." + LOGGED,
}
SAID = (("guard", "`guard`"), ("helper", "a helper"), ("debrief", "the debrief"))


def section(contributing: str) -> str:
    """The name of the section the runs table is under: its heading, without what follows in
    brackets. Empty when the table or its heading is not found."""
    lines = contributing.splitlines()
    at = next((i for i, line in enumerate(lines) if line.strip().startswith(TABLE)), None)
    heading = next((line for line in reversed(lines[:at or 0]) if line.startswith("### ")), "")
    return re.sub(r"\s*\(.*\)\s*$", "", heading[4:]).strip()


def names() -> tuple[str, ...]:
    """The section names a routine's prompt may say: the one in CONTRIBUTING.md, and the old."""
    try:
        now = section((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))
    except OSError:
        now = ""
    return tuple(name for name in (now, *LEGACY) if name)


def is_run(first: str) -> bool:
    return any(FOLLOW.format(name) in first for name in names())


def _texts(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content or [] if isinstance(c, dict))


def transcript(path: str) -> tuple[str, str]:
    """The session's first message from the person or routine that started it, and its last
    message that says anything, read from the transcript Claude Code keeps."""
    first = last = ""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("message") or {}
        text = _texts(message.get("content"))
        if entry.get("type") == "user" and not first and text.strip() and not entry.get("isMeta"):
            first = text
        elif entry.get("type") == "assistant" and text.strip():
            last = text
    return first, last


def ends_with_next(message: str) -> bool:
    lines = [line.strip() for line in message.strip().splitlines() if line.strip()]
    return bool(lines) and re.sub(r"^[-*_>\s]+", "", lines[-1]).startswith("Next:")


def _over(holds: list[dict], cause: str, now: float, let_go: bool = False) -> None:
    """The open hold of this cause ends now; a hold the cap let go says so."""
    for hold in reversed(holds):
        if hold["cause"] == cause and hold["to"] is None:
            hold["to"] = now
            if let_go:
                hold["let_go"] = True
            return


def decide(first: str, last: str, pending: list[str] | None, state: dict, now: float,
           held: bool = False, helpers: list[str] | None = None) -> tuple[str | None, dict]:
    """The reason to hold the run, or None to let it end, and the state the next call reads.
    `pending` is the pull requests whose `guard` has not finished, and `helpers` the helper agents
    still out; either is None when it could not be asked, which holds nothing and forgets
    nothing. `held` says the run goes on because this hook held it, so a new attempt to end starts
    the debrief's asks again. `state["holds"]` is the log: a wait is one hold, from its first
    block to the call that finds it over, and each ask for the debrief is one."""
    if not is_run(first):
        return None, state
    if not held:
        state["asked"] = 0
    since, holds = state.setdefault("since", {}), state.setdefault("holds", [])
    for cause, what, wait in (("guard", pending, WAIT_GUARD), ("helper", helpers, WAIT_HELPER)):
        if what is None:
            continue
        if not what:
            if since.pop(cause, None) is not None:
                _over(holds, cause, now)
            continue
        if cause not in since:
            since[cause] = now
            holds.append({"cause": cause, "what": what, "from": now, "to": None})
        if now - since[cause] < wait * 60:
            return REASON[cause].format(", ".join(what)), state
        _over(holds, cause, now, let_go=True)
    if not ends_with_next(last):
        state["asked"] = state.get("asked", 0) + 1
        if state["asked"] <= ASK_DEBRIEF:
            holds.append({"cause": "debrief", "from": now, "to": now})
            return REASON["debrief"], state
    return None, state


def said(holds: list[dict], now: float) -> str:
    """The holds as the end line says them, or nothing: "held 1× for `guard`, 12 min; 2× for the
    debrief". A wait still open counts to now; "1 let go" is a wait the cap ended."""
    parts = []
    for cause, name in SAID:
        mine = [hold for hold in holds if hold["cause"] == cause]
        if not mine:
            continue
        part = f"{len(mine)}× for {name}"
        if cause != "debrief":
            seconds = sum((now if hold["to"] is None else hold["to"]) - hold["from"] for hold in mine)
            part += f", {round(seconds / 60)} min"
            let_go = sum(1 for hold in mine if hold.get("let_go"))
            part += f", {let_go} let go" if let_go else ""
        parts.append(part)
    return "held " + "; ".join(parts) if parts else ""


def helpers(hook: dict) -> list[str] | None:
    """The helper agents Claude Code lists as still in flight, each by its agent's name; None when
    it sent no list."""
    tasks = hook.get("background_tasks")
    if not isinstance(tasks, list):
        return None
    return [str(task.get("agent_type") or task.get("description") or task.get("id") or "a helper")
            for task in tasks if isinstance(task, dict) and task.get("type") == "subagent"]


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=20).stdout


def pending(cwd: str, now: float) -> list[str] | None:
    """The open pull requests of branches this checkout pushed whose `guard` has not finished;
    None when git or GitHub cannot be asked."""
    try:
        url = _run("git", "-C", cwd, "remote", "get-url", "origin").strip()
        repo = "/".join(url.removesuffix(".git").split("/")[-2:])
        local = _run("git", "-C", cwd, "for-each-ref", "--format=%(refname:short)", "refs/heads")
        remote = _run("git", "-C", cwd, "for-each-ref", "--format=%(refname:short)",
                      "refs/remotes/origin")
        branches = [b for b in local.split() if b != "main" and f"origin/{b}" in remote.split()]
        waiting = []
        for branch in branches:
            pulls = json.loads(_run("gh", "api", f"repos/{repo}/pulls?state=open&head="
                                    f"{repo.split('/')[0]}:{branch}"))
            for pull in pulls:
                runs = json.loads(_run("gh", "api", f"repos/{repo}/commits/{pull['head']['sha']}"
                                        "/check-runs?check_name=guard"))["check_runs"]
                changed = calendar.timegm(time.strptime(pull["updated_at"], "%Y-%m-%dT%H:%M:%SZ"))
                if (any(r["status"] != "completed" for r in runs)
                        or (not runs and now - changed < NOT_STARTED * 60)):
                    waiting.append(f"#{pull['number']}")
        return waiting
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return None


def kept(session: str) -> Path:
    return Path(tempfile.gettempdir()) / f"portfusion-stop-{session}.json"


def holds_said() -> str:
    """What `--holds` prints: this session's holds, read from the file the hook keeps. The session
    is the one Claude Code names in the environment; without it, the file last written."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if session:
        path = kept(session)
    else:
        files = sorted(Path(tempfile.gettempdir()).glob("portfusion-stop-*.json"),
                       key=lambda file: file.stat().st_mtime)
        path = files[-1] if files else None
    if not (path and path.exists()):
        return ""
    return said(json.loads(path.read_text()).get("holds", []), time.time())


def main() -> int:
    if "--holds" in sys.argv[1:]:
        try:
            line = holds_said()
        except Exception:                   # noqa: BLE001 — a log that cannot be read says nothing
            line = ""
        if line:
            log.info(line)
        return 0
    try:
        return _main()
    except Exception as e:                  # noqa: BLE001 — a hook that fails must not trap a run
        log.info(json.dumps({"systemMessage": f"the Stop hook failed and held nothing: {e!r}"}))
        return 0


def _main() -> int:
    hook = json.load(sys.stdin)
    first, last = transcript(hook["transcript_path"])
    last = hook.get("last_assistant_message") or last
    if not is_run(first):
        return 0
    file = kept(hook.get("session_id", "run"))
    state = json.loads(file.read_text()) if file.exists() else {}
    now = time.time()
    reason, state = decide(first, last, pending(hook.get("cwd", "."), now), state, now,
                           held=bool(hook.get("stop_hook_active")), helpers=helpers(hook))
    file.write_text(json.dumps(state))
    if reason:
        log.info(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
