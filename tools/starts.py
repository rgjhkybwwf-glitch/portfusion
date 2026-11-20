"""WHAT STARTS A RUN, AND WHEN: the start gate's table (CONTRIBUTING.md, When a run starts).
`start.yml` sees what happens on GitHub (the maintainer's words, a release, a run's own line) and
asks this what it is, what to do at once, and which run it starts after how many quiet minutes.
It keeps no clock: every run a clock starts is started by its routine's own. `notify.yml` asks it
whether the maintainer's working day is on. It reads only the standard library and
`portfusion.log`, and both workflows run the default branch's copy of it, never a pull request's.

    python3 tools/starts.py --read      what an event is, from the environment: one line of JSON
    python3 tools/starts.py --working   "yes" in the maintainer's working hours, "no" outside them
    python3 tools/starts.py --queue     the Queue's number
    python3 tools/starts.py --log       the run log's number
    python3 tools/starts.py --at-work <level> <comments file>
                                        "yes" while a run of that level is at work, read from the
                                        run log's comments, a JSON list of {body, created_at}

THE RUNS WRITE AS THE MAINTAINER'S ACCOUNT, so whose a comment is is told by its first words: a
run's mark, a session's note, or else the maintainer's own.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, time, timedelta, timezone
from typing import NamedTuple
from zoneinfo import ZoneInfo

from portfusion.log import log

#: The Queue. Its `paused` label stops every start.
QUEUE = 206
#: The run log, where each run writes its start line and its end line (the skill `beat`).
RUN_LOG = 289
#: A start line with no end line after it this long is a run that died, not one at work.
AT_WORK_FOR = timedelta(hours=3)
#: The maintainer's working day, Monday to Friday, by this clock.
ZONE = ZoneInfo("Europe/London")
OPENS, CLOSES = time(8), time(17)
WEEK = range(5)

#: Each run's mark, as the runs table gives it, and the level that signs with it. The marks of
#: before the restart are kept though no row has them: a comment that opens with one is still a
#: run's, not the maintainer's.
MARKS = {"📋 **Coordinator**": "coordinator", "🌙 **Builder**": "builder",
         "📋 **Ready check**": "coordinator", "🌙 **Night run**": "builder",
         "💬 **Answer run**": ""}
NOTE = "**Session note**"


class Start(NamedTuple):
    run: str        # the row of the runs table it starts; its starting text begins with this
    level: str      # the level whose routine carries it
    wait: int       # quiet minutes after the last start of its level


STARTS = {
    "answer": Start("Answer", "coordinator", 30),
    "change": Start("Answer", "coordinator", 30),
    "idea": Start("Idea", "coordinator", 10),
    "release": Start("Release", "coordinator", 10),
    "resume": Start("Re-plan", "coordinator", 10),
    "replan": Start("Re-plan", "coordinator", 10),
    "build": Start("Answer build", "builder", 2),
}

ANSWER = re.compile(r"^(q[0-9]+\s*:|all\s+as\s+rec)", re.I)
WORD = re.compile(r"^(change|hold|resume)\s*:", re.I)
IDEA = re.compile(r"^idea\s*:", re.I)
LINE = re.compile(r"^(?:\*\*)?(Re-plan|Build):")
TAG = re.compile(r"^v\d+\.\d+\.\d+$")


def working(now: datetime) -> bool:
    """Whether `now` is in the maintainer's working day."""
    local = now.astimezone(ZONE)
    return local.weekday() in WEEK and OPENS <= local.time() < CLOSES


def _lines(body: str) -> list[str]:
    return [line.strip() for line in body.splitlines() if line.strip()]


def whose(body: str) -> str:
    """"" for the maintainer's own words, "session" for a session's note, else "run"."""
    first = (_lines(body) or [""])[0]
    if first.startswith(NOTE):
        return "session"
    return "run" if first.startswith(tuple(MARKS)) else ""


def runs_line(body: str) -> tuple[str, str]:
    """A run's own line, and the level that wrote it: ("Re-plan", "builder"), ("Build",
    "coordinator"), or ("", level). It is the first thing after the run's mark, on the mark's
    line or the next."""
    lines = _lines(body)[:2]
    level = next((lv for mark, lv in MARKS.items() if lines and lines[0].startswith(mark)), "")
    rest = " ".join(lines).partition("·")[2].strip()
    found = LINE.match(rest)
    return (found.group(1) if found else "", level)


def text(key: str, number: str = "", url: str = "", tag: str = "") -> str:
    """The one line a run is started with. It begins with its row's name, which is how the run
    finds its playbook; nothing of a comment is in it."""
    where = f"#{number} ({url})" if number else ""
    if key == "hand":
        return ("Dry run: the start gate was started by hand, to test this path. Follow no "
                "playbook, write nothing, and end in one line, which begins \"Next:\".")
    said = {
        "answer": f"the maintainer answered or changed something, the last on {where}. Find each "
                  f"answer and change yourself, and record them all.",
        "idea": f"the maintainer opened an idea, the last {where}.",
        "release": f"{tag} was published.",
        "resume": (f"the maintainer resumed {where}." if number != str(QUEUE)
                   else "the maintainer resumed the loop: take all that waited while it was paused."),
        "replan": f"a run left a re-plan, the last on {where}. Plan the issues under Next marked "
                  f"\"Re-plan\" since their last \"Plan, checked\".",
        "build": f"the coordinator left a build, the last on {where}. Build the issues under Next "
                 f"marked \"Build:\" since their last \"Plan, checked\", and no other line.",
    }
    said["change"] = said["answer"]
    return f"{STARTS[key].run}: {said[key]}"


def read(e: dict[str, str]) -> dict:
    """What an event is. "start" is the key of what it starts, or "" for nothing; "acts" is what
    `start.yml` does at once, in order; "said" is one line for the log.

    The acts: `rocket` and `eyes` mark the maintainer's words, the first when a run will start and
    the second when they were only seen; `decision`, `hold` and `unhold` change the issue's labels;
    `auto-off` turns a pull request's auto-merge off; `pause` and `unpause` change the Queue's
    `paused`."""
    event, number = e.get("EVENT", ""), e.get("NUMBER", "")
    paused = e.get("PAUSED") == "yes"
    queue = number == str(QUEUE)
    key, acts, said, mine = "", [], "nothing to do", False

    if event == "workflow_dispatch":
        level = e.get("LEVEL", "")
        if level not in ("coordinator", "builder"):
            return _seen("", [], f"started by hand for no level: {level!r}")
        return {"start": "hand", "level": level, "wait": 0, "text": text("hand"), "acts": [],
                "said": f"started by hand: the {level} starts now"}

    if event == "release":
        if TAG.match(e.get("TAG", "")):
            key, said = "release", f"{e['TAG']} was published"
        else:
            said = "a release whose tag is not a version: nothing to do"

    elif event == "issues" and e.get("ACTION") == "opened":
        if whose(e.get("ISSUE_BODY", "")):
            said = f"#{number} was opened by a run or a session: not the maintainer's idea"
        elif IDEA.match(e.get("TITLE", "").strip()):
            key, said, mine = "idea", f"an idea, #{number}", True
        else:
            said = f"#{number} was opened, and is not titled \"Idea:\""

    elif event == "issues" and e.get("ACTION") == "unlabeled":
        label = e.get("LABEL", "")
        if queue and label == "paused":
            key, said, paused = "resume", "`paused` came off the Queue: the loop is resumed", False
        elif label == "hold" and not queue:
            key, said = "resume", f"`hold` came off #{number}: it is resumed"

    elif event == "issue_comment":
        key, acts, said, mine, paused = _comment(e, number, queue, paused)

    if key and paused:
        key, said = "", f"{said}; the loop is paused, so no run starts until it is resumed"
    if mine:
        acts = ["rocket" if key else "eyes", *acts]
    if not key:
        return _seen("", acts, said)
    start = STARTS[key]
    return {"start": key, "level": start.level, "wait": start.wait,
            "text": text(key, number, e.get("URL", ""), e.get("TAG", "")), "acts": acts,
            "said": f"{said}: the {start.level}'s {start.run} run starts after {start.wait} "
                    f"quiet minutes"}


def _seen(key: str, acts: list[str], said: str) -> dict:
    return {"start": key, "level": "", "wait": 0, "text": "", "acts": acts, "said": said}


def _comment(e: dict[str, str], number: str, queue: bool,
             paused: bool) -> tuple[str, list[str], str, bool, bool]:
    """A comment from the owner's account: the key it starts, its acts, a line for the log,
    whether the words are the maintainer's own, and whether the loop is still paused after it."""
    body = e.get("BODY", "")
    is_pr = e.get("IS_PR") == "yes"
    agents = e.get("HEAD_REF", "").startswith("claude/")
    by = whose(body)
    if by == "session":
        return "", [], f"a session's note on #{number}: skipped", False, paused
    if by == "run":
        line, level = runs_line(body)
        if is_pr or e.get("STATE", "open") != "open" or not line:
            return "", [], f"a run's comment on #{number}: nothing to do", False, paused
        if line == "Build" and level != "coordinator":
            return "", [], f"\"Build:\" on #{number} is not the coordinator's: left", False, paused
        return ("replan" if line == "Re-plan" else "build", [],
                f"a run's \"{line}:\" on #{number}", False, paused)
    if is_pr and not agents:
        return "", [], f"a comment on #{number}, a pull request not the agent's: left alone", \
            False, paused
    first = (_lines(body) or [""])[0]
    word = WORD.match(first)
    word = word.group(1).lower() if word else ""
    if word == "change":
        return ("change", ["auto-off" if is_pr else "decision"],
                f"a change on #{number}: held", True, paused)
    if word == "hold":
        if queue:
            return "", ["pause"], "a hold on the Queue: the loop is paused", True, True
        return ("", ["auto-off", "hold"] if is_pr else ["hold"],
                f"a hold on #{number}", True, paused)
    if word == "resume":
        if queue:
            return "resume", ["unpause"], "the loop is resumed", True, False
        # A pull request resumed is tended by the next builder's run: nothing is planned for it.
        return ("" if is_pr else "resume", ["unhold"], f"#{number} is resumed", True, paused)
    if not is_pr and ANSWER.match(first):
        return "answer", [], f"an answer on #{number}", True, paused
    return "", [], f"a comment on #{number} that is no answer and no word of command: seen", \
        True, paused


WHEN = re.compile(r"^(\d{1,2}) (\w{3}) (\d{1,2}):(\d\d)")


def _when(part: str) -> str:
    """A line's run, by the date and minute it began: "19 Nov 6:30" and "19 Nov 06:30" alike."""
    found = WHEN.match(part)
    return "{} {} {}:{}".format(int(found[1]), found[2], int(found[3]), found[4]) if found else ""


def at_work(level: str, comments: list[dict], now: datetime) -> bool:
    """Whether a run of `level` is at work: one of its start lines ("<mark> · start · 19 Nov
    06:30 · …"), written less than AT_WORK_FOR ago, has no end line of its own ("<mark> · 19 Nov
    06:30–06:58 · …", the skill `beat`), and no run of the level that began after it has ended,
    which says it died. The gate waits for it to end before it starts another of the level."""
    began, ended = [], set()
    for c in comments:
        lines = _lines(c.get("body", "")) or [""]
        if whose(c.get("body", "")) != "run" or next(
                (lv for mark, lv in MARKS.items() if lines[0].startswith(mark)), "") != level:
            continue
        parts = [part.strip() for part in lines[0].split("·")]
        if len(parts) > 2 and parts[1] == "start" and _when(parts[2]):
            at = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
            began.append((_when(parts[2]), at))
        elif len(parts) > 1 and _when(parts[1]):
            ended.add(_when(parts[1]))
    later_ended = [at for when, at in began if when in ended]
    return any(when not in ended and now - at < AT_WORK_FOR
               and not any(other > at for other in later_ended)
               for when, at in began)


def main(args: list[str]) -> int:
    now = datetime.now(timezone.utc)
    if args[:1] == ["--working"]:
        log.info("yes" if working(now) else "no")
        return 0
    if args[:1] == ["--queue"]:
        log.info(str(QUEUE))
        return 0
    if args[:1] == ["--log"]:
        log.info(str(RUN_LOG))
        return 0
    if args[:1] == ["--at-work"] and len(args) == 3:
        comments = json.loads(open(args[2], encoding="utf-8").read() or "[]")
        log.info("yes" if at_work(args[1], comments, now) else "no")
        return 0
    if args[:1] == ["--read"]:
        log.info(json.dumps(read(dict(os.environ)), ensure_ascii=False))
        return 0
    log.error(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
