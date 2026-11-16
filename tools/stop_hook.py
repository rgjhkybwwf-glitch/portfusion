"""THE RUN'S STOP HOOK (`.claude/settings.json`): a run of the nightly agent cannot end while a pull
request it pushed to has `guard` pending, or when its last message is not a debrief whose last line
begins `Next:` (CONTRIBUTING.md, Telling the maintainer). Claude Code runs it each time a turn would
end, with the turn's details on stdin; a block is said on stdout, and the run goes on with the reason.

A RUN is a session whose first message says `Follow CONTRIBUTING's section "The nightly agent"`, as
each routine's prompt does. Any other session, one with the maintainer included, is never held.

IT NEVER HOLDS A RUN FOREVER. `guard` is waited for at most WAIT_GUARD minutes from the first hold
of a wait, and a debrief asked for at most ASK_DEBRIEF times each time the run would end; then the
run may end. A pull request whose `guard` has not started counts only for NOT_STARTED minutes from
its last change: GitHub runs none on a pull request that cannot merge. GitHub out of reach, or the
hook failing, holds nothing. A run's pull request is the open one whose head is a local branch,
`main` apart, that `origin` also has.
"""
from __future__ import annotations

import calendar
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from portfusion.log import log      # the hook runs without the venv: src/ is put first

RUN = 'Follow CONTRIBUTING\'s section "The nightly agent"'
WAIT_GUARD = 60
ASK_DEBRIEF = 2
NOT_STARTED = 10


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


def decide(first: str, last: str, pending: list[str] | None, state: dict, now: float,
           held: bool = False) -> tuple[str | None, dict]:
    """The reason to hold the run, or None to let it end, and the state the next call reads.
    `pending` is the pull requests whose `guard` has not finished, or None when GitHub could not
    be asked; `held` says the run goes on because this hook held it, so a new attempt to end
    starts the debrief's asks again."""
    if RUN not in first:
        return None, state
    if not held:
        state["asked"] = 0
    if not pending:
        state.pop("guard_since", None)
    else:
        since = state.setdefault("guard_since", now)
        if now - since < WAIT_GUARD * 60:
            return (f"`guard` has not finished on {', '.join(pending)}. Wait for it in the foreground, "
                    "by a command that polls the checks, fix it if it fails, and only then send the "
                    "debrief (CONTRIBUTING.md, Building and Telling the maintainer)."), state
    if not ends_with_next(last):
        state["asked"] = state.get("asked", 0) + 1
        if state["asked"] <= ASK_DEBRIEF:
            return ("The run ends with its debrief: a few lines, sent as a push notification and "
                    "repeated as your last message, whose last line begins `Next:` (CONTRIBUTING.md, "
                    "Telling the maintainer)."), state
    return None, state


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


def main() -> int:
    try:
        return _main()
    except Exception as e:                  # noqa: BLE001 — a hook that fails must not trap a run
        log.info(json.dumps({"systemMessage": f"the Stop hook failed and held nothing: {e!r}"}))
        return 0


def _main() -> int:
    hook = json.load(sys.stdin)
    first, last = transcript(hook["transcript_path"])
    last = hook.get("last_assistant_message") or last
    if RUN not in first:
        return 0
    kept = Path(tempfile.gettempdir()) / f"portfusion-stop-{hook.get('session_id', 'run')}.json"
    state = json.loads(kept.read_text()) if kept.exists() else {}
    now = time.time()
    reason, state = decide(first, last, pending(hook.get("cwd", "."), now), state, now,
                           held=bool(hook.get("stop_hook_active")))
    kept.write_text(json.dumps(state))
    if reason:
        log.info(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
