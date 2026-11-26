"""THE RUN BRIEF: the facts a run of the loop starts from, worked out once, in code
(CONTRIBUTING.md, How it runs). A run used to read the whole Queue to find one line, the run log to
find its own last line, every pull request and every run of the start gate; this reads them and
prints the few lines the run needs, each with where it came from.

    python3 tools/brief.py builder                    a run its routine's clock started
    python3 tools/brief.py coordinator "Answer: …"    a run the gate started, with its starting text

IT READS AND NEVER WRITES: GitHub by `gh api`, and CONTRIBUTING.md for the runs table. It decides
nothing a rule leaves to the run: it says which line under Next a builder may take by the labels
and the Queue's "waits", and the run still reads that issue and its plan whole. What it could not
read it names under "Not read", and the run reads that itself, as its playbook says. A brief that
fails prints why and exits 0: it never stops a run.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
import starts                           # noqa: E402 — the gate's table: the marks, the Queue, the day
from portfusion.log import log          # noqa: E402 — the brief runs without the venv: src/ is put first

TABLE = "| Level | Run |"
CLOCK = re.compile(r"(\d\d):(\d\d) UK time, (every day|Monday to Friday)")
NEXT = re.compile(r"^- \[ \] #(\d+) (.*)$")
WAITS = re.compile(r"· waits (?:on )?((?:#\d+(?:, | and )?)+)")
#: The release checklist's line waits on every line above it, in these words.
LAST = "· last, after every line above"
OWN = re.compile(r"\b(?:Closes|Part of|For) #(\d+)")
#: A plan's comment, as the skill `plan` posts it: the mark, the date, then these words.
PLAN = re.compile(r"[^·]*(?:·[^·]*)?· \*\*Plan, checked(?:, if answered as recommended)?\*\*"
                  r"(?: against `main` at ([0-9a-f]{7,40}))?")
#: A clock's run is its row for this long after the row's hour; the rows are four hours apart.
ROW_FOR = 4 * 60
#: The labels that keep a builder off a planned line (the playbook's "Take a line").
KEEPS_OFF = ("decision", "building", "hold")
#: A `building` label this old is a run that died (CONTRIBUTING.md, Building).
DIED_AFTER = starts.AT_WORK_FOR
#: Where the last run cannot be told, what changed is read from this long ago.
ELSE_SINCE = timedelta(days=3)
REVIEW_DAYS = {0: "Monday", 3: "Thursday"}


class Line(NamedTuple):
    number: int
    title: str
    waits: tuple[int, ...]


def rows(contributing: str) -> list[dict[str, str]]:
    """The runs table's rows, each by its column heads."""
    lines = [line.strip() for line in contributing.splitlines() if line.strip().startswith("|")]
    head = next((i for i, line in enumerate(lines) if line.startswith(TABLE)), None)
    if head is None:
        return []
    names = [cell.strip() for cell in lines[head].strip("|").split("|")]
    found = []
    for line in lines[head + 2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(names):
            break
        found.append(dict(zip(names, cells)))
    return found


def which(table: list[dict[str, str]], level: str, text: str, now: datetime) -> dict[str, str] | None:
    """The run's row. A run the gate started is the row its starting text names, the row's name
    and a colon; one its routine's clock started is, of its level's clocked rows, the one whose
    hour was reached less than ROW_FOR minutes ago, on a day the row names. None when no row
    fits: the run then finds its row itself."""
    mine = [row for row in table if row["Level"].lower() == level]
    named = [row for row in mine if text.strip().startswith(row["Run"] + ":")]
    if named:
        return max(named, key=lambda row: len(row["Run"]))
    if text.strip():
        return None
    local = now.astimezone(starts.ZONE)
    for row in mine:
        said = CLOCK.search(row["What starts it"])
        if said:
            late = (local.hour * 60 + local.minute - int(said[1]) * 60 - int(said[2])) % (24 * 60)
            day = (local - timedelta(minutes=late)).weekday()
            if late < ROW_FOR and (said[3] == "every day" or day in starts.WEEK):
                return row
    return None


def next_lines(queue: str) -> list[Line]:
    """The Queue's lines under Next, in its order, each with the issues its "waits" names; the
    line that is "last, after every line above" waits on each of them."""
    lines, under = [], False
    for line in queue.splitlines():
        if line.startswith("## "):
            under = line.strip() == "## Next"
            continue
        found = NEXT.match(line.strip()) if under else None
        if found:
            waits = WAITS.search(found[2])
            title = found[2].split(" (")[0].split(" · waits")[0].split(LAST)[0].strip()
            named = tuple(int(n) for n in re.findall(r"#(\d+)", waits[1])) if waits else ()
            above = tuple(line.number for line in lines) if LAST in found[2] else ()
            lines.append(Line(int(found[1]), title[:70], named + above))
    return lines


def _at(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _uk(at: datetime) -> str:
    return at.astimezone(starts.ZONE).strftime("%a %-d %b %H:%M")


def last_run(level: str, log_comments: list[dict]) -> tuple[datetime | None, str]:
    """When the level's last ended run began, and its end line: the start the coordinator reads
    what changed from. (None, "") when the run log shows no ended run of the level."""
    began, last = {}, (None, "")
    for c in log_comments:
        lines = [line.strip() for line in c.get("body", "").splitlines() if line.strip()] or [""]
        if next((lv for mark, lv in starts.MARKS.items() if lines[0].startswith(mark)), "") != level:
            continue
        parts = [part.strip() for part in lines[0].split("·")]
        if len(parts) > 2 and parts[1] == "start" and starts._when(parts[2]):
            began[starts._when(parts[2])] = _at(c["created_at"])
        elif len(parts) > 1 and starts._when(parts[1]):
            last = (began.get(starts._when(parts[1])) or _at(c["created_at"]), lines[0])
    return last


def plan_of(comments: list[dict]) -> dict:
    """An issue's latest plan, read from its comments: the commit of `main` it names, when it was
    posted, and the runs' lines since it: any run's "Re-plan:", and the coordinator's "Build:",
    the only one the gate starts a build from. A plan is the coordinator's comment that opens
    with the plan's words; a comment that quotes them further on is none."""
    plan = {"at": None, "commit": "", "since": []}
    for c in comments:
        body = c.get("body", "")
        if starts.whose(body) != "run":
            continue
        line, level = starts.runs_line(body)
        found = PLAN.match(" ".join(starts._lines(body)[:2])) if level == "coordinator" else None
        if found and not line:
            plan = {"at": _at(c["created_at"]), "commit": found[1] or "", "since": []}
        elif plan["at"] and (line == "Re-plan" or (line == "Build" and level == "coordinator")):
            plan["since"].append(line)
    return plan


def own_pulls(pulls: list[dict]) -> dict[int, list[dict]]:
    """Each issue's own open pull requests: the agent's, whose body says Closes, Part of or For it."""
    own: dict[int, list[dict]] = {}
    for pull in pulls:
        if pull["head"]["ref"].startswith("claude/"):
            for number in set(OWN.findall(pull.get("body") or "")):
                own.setdefault(int(number), []).append(pull)
    return own


def lines_said(lines: list[Line], issues: dict[int, dict], own: dict[int, list[dict]],
               plans: dict[int, dict], holes: tuple[str, ...] = (),
               marked: bool = False) -> tuple[list[str], list[int], list[int]]:
    """Each line under Next in a line of the brief, the lines a builder may take, in order, and
    the lines whose plan stands and is not yet built (the coordinator's count). `holes` names the
    reads that failed or were cut short: with any, no line is called free, and an issue the list
    of open ones does not hold is "not read", not closed. `marked` is an answer build's rule:
    only a line marked "Build:" since its plan is taken."""
    said, takeable, standing = [], [], []
    unread = any(hole.startswith("the open issues") for hole in holes)
    for line in lines:
        issue = issues.get(line.number)
        if issue is None:
            said.append(f"  #{line.number} {'not read' if unread else 'closed, not yet ticked'}"
                        f" · {line.title}")
            continue
        labels = issue["labels"]
        parts = ["planned" if "planned" in labels else "no plan"]
        plan = plans.get(line.number)
        if plan and plan["at"]:
            parts[0] += f" {_uk(plan['at'])}" + (f" at {plan['commit'][:7]}" if plan["commit"] else "")
            parts += [f'"{word}:" since its plan' for word in dict.fromkeys(plan["since"])]
        parts += [f"`{label}`" for label in KEEPS_OFF if label in labels]
        pulls = own.get(line.number, [])
        parts += [f"its pull request #{p['number']} is open, {'a draft' if p['draft'] else 'ready'}"
                  for p in pulls]
        open_waits = [n for n in line.waits if n in issues or unread]
        state = "not read" if unread else "open"
        if len(open_waits) > 5:
            parts.append(f"waits {len(open_waits)} issues, {state}, #{open_waits[0]} the first")
        elif open_waits:
            parts.append("waits " + ", ".join(f"#{n}" for n in open_waits) + f" ({state})")
        replan = bool(plan and "Re-plan" in plan["since"])
        ready = any(not p["draft"] for p in pulls)
        if "planned" in labels and (replan or not ready):
            standing.append(line.number)
        if (not holes and "planned" in labels and not replan and not pulls and not open_waits
                and not any(label in labels for label in KEEPS_OFF)
                and (not marked or "Build" in (plan or {}).get("since", []))):
            takeable.append(line.number)
            parts.append("a builder may take it")
        said.append(f"  #{line.number} " + " · ".join(parts) + f" · {line.title}")
    return said, takeable, standing


def comment_said(comment: dict) -> tuple[str, str]:
    """What a comment since the last run is, for the coordinator, and the issue it is on: the
    maintainer's answer, `Change:`, `Hold:` or `Resume:`, their other words, a run's "Re-plan:"
    or "Build:", a session's note, or the bot's. ("", …) for a run's other comments."""
    body, number = comment.get("body", ""), comment["issue_url"].rsplit("/", 1)[-1]
    if (comment.get("user") or {}).get("type") == "Bot":
        return "the bot wrote", number
    by = starts.whose(body)
    if by == "session":
        return "a session's note", number
    if by == "run":
        line, _ = starts.runs_line(body)
        return (f'a run\'s "{line}:"' if line else ""), number
    first = (starts._lines(body) or [""])[0]
    word = starts.WORD.match(first)
    if word:
        return f"the maintainer's `{word.group(1).capitalize()}:`", number
    if starts.ANSWER.match(first):
        return "the maintainer's answer", number
    return "the maintainer's other words", number


class Asked:
    """GitHub, by `gh api`. What cannot be read is kept in `missed`, and reads as empty: a list,
    or for `one` thing asked for, a dict."""

    def __init__(self, repo: str):
        self.repo, self.missed = repo, []

    def get(self, path: str, what: str, pages: int = 1, key: str = "", one: bool = False,
            newest: bool = False):
        """A list read page by page. One that fills its last page was cut short, and is named
        in `missed`, unless it was asked for `newest` first and only its head is wanted."""
        found: list = []
        for page in range(1, pages + 1):
            more = "&" if "?" in path else "?"
            try:
                out = subprocess.run(
                    ["gh", "api", f"repos/{self.repo}/{path}{more}per_page=100&page={page}"],
                    capture_output=True, text=True, check=True, timeout=30).stdout
                data = json.loads(out)
                if one:
                    if not isinstance(data, dict):
                        raise TypeError(what)
                    return data
                data = data[key] if key else data
                found += data
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
                self.missed.append(what)
                return {} if one else found
            if len(data) < 100:
                return found
        if not newest:
            self.missed.append(f"{what}, past its first {pages * 100}")
        return found


def _repo() -> str:
    url = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"],
                         capture_output=True, text=True, check=True, timeout=20).stdout.strip()
    return "/".join(url.removesuffix(".git").split("/")[-2:])


def brief(level: str, text: str, now: datetime, asked: Asked) -> list[str]:
    """The brief's lines, for a run of `level` started with `text`, or by its clock with none."""
    out = [f"RUN BRIEF · {level} · {_uk(now)} UK time"]
    if text.strip().startswith("Dry run"):
        return out + ["A dry run: follow no playbook, write nothing, and end in one line that "
                      "begins \"Next:\"."]
    table = rows((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))
    row = which(table, level, text, now)
    gate = bool(row) and bool(text.strip())     # a text that names no row is no gate's
    if row is None:
        out.append("Run: no row of the runs table fits this "
                   + ("text" if text.strip() else "hour and day")
                   + ": find it as CONTRIBUTING.md, How it runs, says.")
    else:
        how = "named by its starting text" if gate else "its routine's clock, by the hour"
        out.append(f"Run: {row['Run']} ({how}) · cap: {row['Cap']} · mark: {row['Mark']}")

    queue = asked.get(f"issues/{starts.QUEUE}", "the Queue", one=True)
    if "the Queue" in asked.missed:
        return out + ["Paused: not read. The Queue could not be read: read its labels and its "
                      "lines yourself, as the playbook says, before the start line."]
    paused = "paused" in [label["name"] for label in queue.get("labels", [])]
    if paused and not gate:
        return out + [f"Paused: yes, the Queue (#{starts.QUEUE}) carries `paused`. A run its "
                      "routine's clock started writes neither line and ends in one line that begins "
                      "\"Next:\" and says the loop is paused (the skill `beat`)."]
    out.append(f"Paused: {'yes' if paused else 'no'} (the Queue's labels)")

    log_since = (now - ELSE_SINCE - timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_log = asked.get(f"issues/{starts.RUN_LOG}/comments?since={log_since}", "the run log",
                        pages=3)
    began, end_line = last_run(level, run_log)
    since = began or now - ELSE_SINCE
    out.append(f"Last {level} run: " + (end_line or "none on the run log in a week"))
    other = "builder" if level == "coordinator" else "coordinator"
    for lv in (level, other):
        if starts.at_work(lv, run_log, now):
            out.append(f"At work: a {lv}'s run has a start line and no end line yet (the run log)")

    found = asked.get("issues?state=open", "the open issues", pages=5)
    issues = {i["number"]: {"labels": [label["name"] for label in i["labels"]], "title": i["title"],
                            "created": _at(i["created_at"])}
              for i in found if "pull_request" not in i}
    pulls = asked.get("pulls?state=open", "the open pull requests", pages=2)
    own = own_pulls(pulls)
    lines = next_lines(queue.get("body") or "")
    plans = {}
    for line in lines:
        if "planned" in issues.get(line.number, {}).get("labels", []):
            plans[line.number] = plan_of(asked.get(f"issues/{line.number}/comments",
                                                   f"#{line.number}'s comments", pages=5))

    holes = tuple(what for what in dict.fromkeys(asked.missed)
                  if what.startswith(("the open issues", "the open pull requests"))
                  or "'s comments" in what)
    no_pulls = any(hole.startswith("the open pull requests") for hole in holes)
    agents = [p for p in pulls if p["head"]["ref"].startswith("claude/")]
    out.append("The agent's open pull requests" + (": not read" if no_pulls else
                                                    ":" if agents else ": none"))
    for p in agents:
        what = f"#{p['number']}'s guard"
        runs = asked.get(f"commits/{p['head']['sha']}/check-runs?check_name=guard", what,
                         key="check_runs")
        guard = "not read" if what in asked.missed else next(
            (r["conclusion"] or r["status"] for r in runs), "not started")
        closes = ", ".join(f"#{n}" for n, mine in own.items() if p in mine) or "no issue named"
        out.append(" · ".join([f"  #{p['number']} {'a draft' if p['draft'] else 'ready'}",
                               f"guard {guard}", f"auto-merge {'on' if p.get('auto_merge') else 'off'}",
                               f"for {closes}", *(f"`{label['name']}`" for label in p.get("labels", []))]))

    answer_build = bool(row) and row["Run"] == "Answer build"
    said, takeable, standing = lines_said(lines, issues, own, plans, holes, marked=answer_build)
    out.append(f"Next, in the Queue's order ({len(lines)} lines; \"waits\" as the Queue's lines "
               "say them):")
    out += said or ["  none read"]
    if level == "builder":
        if holes:
            out.append("The line to take: not decided here, since " + ", ".join(holes)
                       + " could not be read. Take it as the playbook says.")
            return out + _missed(asked)
        out.append("The line to take: " + (
            f"#{takeable[0]}. Read it whole, with its latest Plan, checked, and confirm the plan "
            "stands (the skill `build-an-issue`)." if takeable else
            "none. No line under Next is planned, free of `decision`, `building` and `hold`, "
            "without a pull request of its own, and with its \"waits\" closed"
            + (", and marked \"Build:\" since its plan, which is all an answer build takes."
               if answer_build else ".")))
        return out + _missed(asked)

    out.append("Plans that stand and are not yet built: "
               + ("not counted here, since " + ", ".join(holes) + " could not be read" if holes else
                  str(len(standing)) + (f" ({', '.join(f'#{n}' for n in standing)})" if standing else ""))
               + (f" · the cap is {row['Cap']}" if row else ""))
    out += _changed(asked, since, now, issues, pulls)
    return out + _missed(asked)


def _changed(asked: Asked, since: datetime, now: datetime, issues: dict[int, dict],
             pulls: list[dict]) -> list[str]:
    """The changes since the coordinator's last run began: its morning run's third step."""
    stamp = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = [f"Since the last run began, {_uk(since)}:"]
    head = asked.get("pulls?state=closed&sort=updated&direction=desc", "the closed pull requests",
                     newest=True)
    if len(head) == 100 and _at(head[-1]["updated_at"]) >= since:
        asked.missed.append("the closed pull requests, past the first 100 changed")
    closed = [p for p in head if p.get("closed_at") and _at(p["closed_at"]) >= since]
    merged = [f"#{p['number']}" for p in closed if p.get("merged_at")]
    stopped = [f"#{p['number']}" for p in closed if not p.get("merged_at")]
    out.append(f"  Merged: {', '.join(merged) or 'none'} · closed unmerged: "
               f"{', '.join(stopped) or 'none'}")
    touched = asked.get(f"issues?state=all&since={stamp}", "the issues changed since", pages=3)
    filed = [f"#{i['number']}" for i in touched
             if "pull_request" not in i and _at(i["created_at"]) >= since]
    shut = [f"#{i['number']}" for i in touched if "pull_request" not in i
            and i.get("closed_at") and _at(i["closed_at"]) >= since]
    out.append(f"  Issues filed: {', '.join(filed) or 'none'} · closed: {', '.join(shut) or 'none'}")
    kinds: dict[str, list[str]] = {}
    for c in asked.get(f"issues/comments?since={stamp}&sort=created", "the comments since", pages=5):
        kind, number = comment_said(c)
        if kind and _at(c["created_at"]) >= since and number != str(starts.RUN_LOG):
            kinds.setdefault(kind, [])
            if f"#{number}" not in kinds[kind]:
                kinds[kind].append(f"#{number}")
    out += [f"  Comments, {kind}: on {', '.join(numbers)}" for kind, numbers in kinds.items()]
    if not kinds:
        out.append("  Comments: none but the runs' own")
    failed = [str(r["run_number"]) for r in asked.get(
        "actions/workflows/start.yml/runs?created=" + quote(f">={stamp}"),
        "the start gate's runs", key="workflow_runs") if r.get("conclusion") == "failure"]
    out.append("  Starts the gate failed to make: " + (", ".join(f"run {n}" for n in failed) or "none"))
    release = asked.get("releases/latest", "the latest release", one=True)
    if release.get("tag_name"):
        new = _at(release["published_at"]) >= since
        out.append(f"  Latest release: {release['tag_name']}, published "
                   f"{_uk(_at(release['published_at']))}" + (", since the last run" if new else ""))
    out.append("Now:")
    ideas = [f"#{n}" for n, i in issues.items() if starts.IDEA.match(i["title"].strip())]
    out.append(f"  Open issues titled Idea: {', '.join(ideas) or 'none'}")
    bumps = [f"#{p['number']}" for p in pulls if p["user"]["login"].startswith("dependabot")]
    out.append(f"  Dependabot's open pull requests: {', '.join(bumps) or 'none'}")
    died = []
    for number, issue in issues.items():
        if "building" in issue["labels"]:
            events = asked.get(f"issues/{number}/events", f"#{number}'s events", pages=3)
            put = [_at(e["created_at"]) for e in events
                   if e.get("event") == "labeled" and e.get("label", {}).get("name") == "building"]
            if put and now - max(put) > DIED_AFTER:
                died.append(f"#{number}")
    out.append(f"  `building` for more than three hours: {', '.join(died) or 'none'}")
    local = now.astimezone(starts.ZONE)
    if local.weekday() in REVIEW_DAYS:
        today = local.replace(hour=0, minute=0, second=0).astimezone(timezone.utc)
        posted = any("**Queue review**" in c.get("body", "")[:200] and _at(c["created_at"]) >= today
                     for c in asked.get(f"issues/{starts.QUEUE}/comments?since="
                                        f"{today.strftime('%Y-%m-%dT%H:%M:%SZ')}",
                                        "the Queue's comments today", pages=2))
        out.append(f"  A Queue review: it is {REVIEW_DAYS[local.weekday()]}, and "
                   + ("one is posted today" if posted else "none is posted today: it is due"))
    else:
        out.append("  A Queue review: not due today")
    out.append("  Not read here: security alerts (the skill `dependencies`).")
    return out


def _missed(asked: Asked) -> list[str]:
    if not asked.missed:
        return []
    return ["Not read, so read it as the playbook says: " + ", ".join(dict.fromkeys(asked.missed))]


def main(args: list[str]) -> int:
    if not args or args[0] not in ("coordinator", "builder"):
        log.error(__doc__)
        return 2
    try:    # a starting text holds quotes, so a shell may hand it over in pieces
        lines = brief(args[0], " ".join(args[1:]), datetime.now(timezone.utc), Asked(_repo()))
    except Exception as e:              # noqa: BLE001 — a brief that fails must not stop a run
        lines = [f"RUN BRIEF · it failed and says nothing: {e!r}. Read as the playbook says."]
    log.info("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
