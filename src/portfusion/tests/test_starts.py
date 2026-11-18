"""tools/starts.py and the two workflows that ask it: what starts a run, after how many quiet
minutes, and when the bot may ask. A comment misread starts a run on the agent's own words, or
none on the maintainer's; a clock an hour out builds in their working day; and a table that has
left CONTRIBUTING's leaves a run started with a text that names no row."""
import importlib.util
import re
from datetime import datetime, timedelta, timezone

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:
    pytest.skip(NO_CHECKOUT, allow_module_level=True)

FLOWS = ROOT / ".github" / "workflows"
WORDS = {30: "thirty", 10: "ten", 2: "two"}


@pytest.fixture(scope="module")
def starts():
    spec = importlib.util.spec_from_file_location("starts", ROOT / "tools" / "starts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def contributing():
    return (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rows(contributing):
    """The runs table's rows by the run's name."""
    lines = [line for line in contributing.splitlines() if line.strip().startswith("|")]
    head = next(i for i, line in enumerate(lines) if line.strip().startswith("| Level | Run |"))
    names = [cell.strip() for cell in lines[head].strip().strip("|").split("|")]
    found = {}
    for line in lines[head + 2:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(names):
            break
        found[cells[1]] = dict(zip(names, cells))
    return found


def uk(text):
    """A moment by London's clock, as the gate would be handed it: in UTC."""
    return datetime.fromisoformat(text).replace(tzinfo=_zone()).astimezone(timezone.utc)


def _zone():
    from zoneinfo import ZoneInfo
    return ZoneInfo("Europe/London")


NOON = "2026-11-18 12:00"       # a Wednesday


def comment(starts, body, number="250", **more):
    event = {"EVENT": "issue_comment", "BODY": body, "NUMBER": number, "IS_PR": "no",
             "STATE": "open", "URL": f"https://example.test/issues/{number}", **more}
    return starts.read(event, uk(NOON))


def test_each_start_is_a_row_of_the_runs_table_and_the_table_says_its_wait(starts, rows):
    for key, start in starts.STARTS.items():
        row = rows.get(start.run)
        assert row, f"{key} starts the run {start.run!r}, which the runs table does not list"
        assert row["Level"].lower() == start.level, key
        what = row["What starts it"]
        if start.wait:
            assert f"{WORDS[start.wait]} quiet minutes" in what, (key, what)
        if start.by == "clock":
            at, _ = starts.CLOCK[key]
            assert f"{at:%H:%M} UK time" in what and "the gate's clock" in what, (key, what)
        assert starts.text(key, "250", "u", "v0.4.2").startswith(f"{start.run}: "), key
    # What the gate does not start has a clock of its routine's own.
    gated = {start.run for start in starts.STARTS.values()}
    for run, row in rows.items():
        assert (run in gated) != ("its routine's clock" in row["What starts it"]), run


def test_each_runs_mark_is_one_the_gate_knows_for_its_level(starts, rows):
    """A run writes as the maintainer's account: the gate tells its comments from theirs by the
    mark alone, so a mark it does not know would be read as the maintainer's own words."""
    for run, row in rows.items():
        mark = row["Mark"].strip("`").removesuffix("·").strip()
        assert starts.MARKS.get(mark) == row["Level"].lower(), run


def test_the_queue_is_the_one_contributing_names(starts, contributing):
    named = re.search(r"\*\*the Queue\*\*,[^()]*\(#(\d+)\)", contributing)
    assert named and int(named.group(1)) == starts.QUEUE
    log = re.search(r"\*\*the run log\*\* \(#(\d+)\)", contributing)
    assert log and int(log.group(1)) == starts.RUN_LOG


def test_a_start_waits_while_a_run_of_its_level_is_at_work(starts):
    """THE CASE THAT MAKES IT FAIL: the morning run writes "Re-plan:" early, and ten minutes later
    a second coordinator plans and writes the Queue beside it."""
    from datetime import datetime, timezone
    now = datetime(2026, 11, 19, 7, 0, tzinfo=timezone.utc)

    def line(body, at):
        return {"body": body, "created_at": f"2026-11-19T{at}:00Z"}
    began = line("📋 **Ready check** · start · 19 Nov 06:30 · the morning", "06:30")
    ended = line("📋 **Ready check** · 19 Nov 06:30–06:58 · planned #250 · Next: …", "06:58")
    night = line("🌙 **Night run** · start · 19 Nov 06:40 · building #251", "06:40")
    assert starts.at_work("coordinator", [began], now)
    assert not starts.at_work("coordinator", [began, ended], now)
    assert starts.at_work("builder", [began, ended, night], now)
    assert not starts.at_work("coordinator", [night], now)
    died = line("📋 **Ready check** · start · 19 Nov 02:30 · the answer", "02:30")
    assert not starts.at_work("coordinator", [died], now), "a run that died holds nothing"
    seen = [line("**Session note** · start · nothing", "06:50"), line("start: Q1: a", "06:55")]
    assert starts.at_work("coordinator", [began, *seen], now), "only a run's lines count"
    # Each start line is paired with its own end line: one run's end hides no other at work.
    other = line("📋 **Ready check** · start · 19 Nov 06:40 · a re-plan", "06:40")
    assert starts.at_work("coordinator", [began, other, ended], now)
    assert not starts.at_work("coordinator", [began, other, ended, line(
        "📋 **Ready check** · 19 Nov 06:40–06:59 · planned #251 · Next: …", "06:59")], now)
    # One that died is let go once a later run of its level has begun and ended.
    later = line("📋 **Ready check** · start · 19 Nov 06:45 · the clock", "06:45")
    done = line("📋 **Ready check** · 19 Nov 06:45—06:55 · planned · Next: …", "06:55")
    assert not starts.at_work("coordinator", [began, later, done], now)
    assert not starts.at_work("coordinator", [line("📋 **Ready check** · start · 19 Nov 6:30, a re-plan", "06:30"), ended], now)
    gate = (FLOWS / "start.yml").read_text(encoding="utf-8").partition("\n  fire:")[2]
    assert "starts.py --at-work" in gate and gate.index("--at-work") < gate.index("grep -qx paused")


@pytest.mark.parametrize("body, start, acts", [
    ("Q1: a", "answer", ["rocket"]),
    ("  q2 : b, and keep the old name", "answer", ["rocket"]),
    ("All as recomemded", "answer", ["rocket"]),
    ("Change: build it on the Method page instead", "change", ["rocket", "decision"]),
    ("Hold: I am still thinking", "", ["eyes", "hold"]),
    ("Resume:", "resume", ["rocket", "unhold"]),
    ("Looks good to me", "", ["eyes"]),
    ("Question: why this one?", "", ["eyes"]),
    ("**Session note** · Q1: a", "", []),
    ("📋 **Coordinator** · Q1 is asked below", "", []),
    ("🌙 **Builder** · **Re-plan:** the answer changed the plan", "replan", []),
    ("💬 **Answer run** ·\n\nRe-plan: #250 was answered b", "replan", []),
    ("📋 **Ready check** · Re-plan: answered b", "replan", []),
    ("📋 **Coordinator** · Build: answered as recommended, and the plan stands", "build", []),
    ("🌙 **Builder** · Build: me too", "", []),
    ("🌙 **Builder** · 17 Nov 00:30–01:17 · built #250 · Next: Re-plan: nothing", "", []),
])
def test_a_comment_is_read_by_its_first_words(starts, body, start, acts):
    seen = comment(starts, body)
    assert (seen["start"], seen["acts"]) == (start, acts), seen["said"]
    if start:
        assert seen["level"] == starts.STARTS[start].level
        assert seen["wait"] == starts.STARTS[start].wait
        assert "\n" not in seen["text"] and body not in seen["text"]


def test_a_pull_request_takes_a_change_and_a_hold_only_when_it_is_the_agents(starts):
    ours = {"IS_PR": "yes", "HEAD_REF": "claude/fix-250"}
    assert comment(starts, "Change: not this way", **ours)["acts"] == ["rocket", "auto-off"]
    held = comment(starts, "Hold:", **ours)
    assert (held["start"], held["acts"]) == ("", ["eyes", "auto-off", "hold"])
    back = comment(starts, "Resume:", **ours)
    assert (back["start"], back["acts"]) == ("", ["eyes", "unhold"])
    # An answer is given on an issue; on a pull request it is a comment.
    assert comment(starts, "Q1: a", **ours)["start"] == ""
    theirs = {"IS_PR": "yes", "HEAD_REF": "dependabot/pip/x"}
    for body in ("Change: no", "Hold:", "Looks fine"):
        seen = comment(starts, body, **theirs)
        assert (seen["start"], seen["acts"]) == ("", []), body
    # A run's line on a pull request, or on a closed issue, starts nothing.
    line = "🌙 **Builder** · Re-plan: again"
    assert comment(starts, line, **ours)["start"] == ""
    assert comment(starts, line, STATE="closed")["start"] == ""


def test_an_idea_and_a_release_start_the_coordinator(starts):
    def opened(title, body="Let the desk show dividends by month."):
        return starts.read({"EVENT": "issues", "ACTION": "opened", "TITLE": title,
                            "ISSUE_BODY": body, "NUMBER": "330", "URL": "u"}, uk(NOON))
    idea = opened("Idea: dividends by month")
    assert (idea["start"], idea["acts"], idea["wait"]) == ("idea", ["rocket"], 10)
    assert opened("idea : lower case too")["start"] == "idea"
    assert opened("Dividends by month")["start"] == ""
    assert opened("Idea: from a run", "📋 **Coordinator** · filed from a find")["acts"] == []
    assert opened("Idea: from a session", "**Session note** · filed with the maintainer")["start"] == ""

    def published(tag):
        return starts.read({"EVENT": "release", "ACTION": "published", "TAG": tag}, uk(NOON))
    release = published("v0.4.2")
    assert (release["start"], release["level"], release["wait"]) == ("release", "coordinator", 10)
    assert "v0.4.2" in release["text"]
    assert published("nightly\"; rm -rf")["start"] == ""


def test_a_pause_stops_every_start_and_keeps_every_hold(starts):
    queue = str(starts.QUEUE)
    paused = {"PAUSED": "yes"}
    answer = comment(starts, "Q1: a", **paused)
    assert (answer["start"], answer["acts"]) == ("", ["eyes"]) and "paused" in answer["said"]
    change = comment(starts, "Change: no", **paused)
    assert (change["start"], change["acts"]) == ("", ["eyes", "decision"])
    assert comment(starts, "🌙 **Night run** · Re-plan: x", **paused)["start"] == ""
    assert comment(starts, "Resume:", **paused)["acts"] == ["eyes", "unhold"]
    evening = {"EVENT": "schedule", "CRON": "30 18 * * 1-5"}
    assert starts.read(evening, uk("2026-11-18 18:31"))["start"] == "evening"
    assert starts.read({**evening, **paused}, uk("2026-11-18 18:31"))["start"] == ""
    # "Hold:" on the Queue is the pause, and "Resume:" there ends it and starts the coordinator.
    hold = comment(starts, "Hold: away this week", number=queue)
    assert (hold["start"], hold["acts"]) == ("", ["eyes", "pause"])
    back = comment(starts, "Resume:", number=queue, **paused)
    assert (back["start"], back["acts"], back["level"]) == ("resume", ["rocket", "unpause"],
                                                            "coordinator")
    assert "all that waited" in back["text"]
    # Taken off by a session, the label's going is the resume.
    off = {"EVENT": "issues", "ACTION": "unlabeled", "LABEL": "paused", "NUMBER": queue, **paused}
    assert starts.read(off, uk(NOON))["start"] == "resume"
    assert starts.read({**off, "LABEL": "bug"}, uk(NOON))["start"] == ""
    assert starts.read({**off, "LABEL": "hold", "NUMBER": "250", "PAUSED": "no"},
                       uk(NOON))["start"] == "resume"


def test_the_working_day_is_eight_to_five_monday_to_friday_by_londons_clock(starts):
    for when, on in [("2026-11-18 07:59", False), ("2026-11-18 08:00", True),
                     ("2026-11-18 16:59", True), ("2026-11-18 17:00", False),
                     ("2026-11-21 12:00", False), ("2026-11-22 12:00", False),
                     ("2026-07-15 08:00", True), ("2026-07-15 07:59", False)]:
        assert starts.working(uk(when)) is on, when
    # In summer London is an hour ahead of UTC: 08:00 there is 07:00 UTC.
    assert starts.working(datetime(2026, 7, 15, 7, 0, tzinfo=timezone.utc))
    assert not starts.working(datetime(2026, 11, 18, 7, 0, tzinfo=timezone.utc))


def test_the_clock_fires_once_in_season_and_never_in_the_working_day(starts):
    gate = (FLOWS / "start.yml").read_text(encoding="utf-8")
    for key, (at, days) in starts.CLOCK.items():
        assert starts.STARTS[key].by == "clock"
        assert not (starts.OPENS <= at < starts.CLOSES and set(days) & set(starts.WEEK)), key
        winter = f"{at.minute} {at.hour} * * 1-5"
        summer = f"{at.minute} {at.hour - 1} * * 1-5"
        assert f'cron: "{winter}"' in gate and f'cron: "{summer}"' in gate, key
        late = timedelta(minutes=14)
        wednesday = datetime(2026, 11, 18, at.hour, at.minute, tzinfo=timezone.utc) + late
        july = datetime(2026, 7, 15, at.hour - 1, at.minute, tzinfo=timezone.utc) + late
        assert starts.due(key, winter, wednesday) and not starts.due(key, summer, wednesday)
        assert starts.due(key, summer, july) and not starts.due(key, winter, july + timedelta(hours=1))
        assert not starts.due(key, winter, wednesday + timedelta(hours=3)), "three hours late"
        saturday = datetime(2026, 11, 21, at.hour, at.minute, tzinfo=timezone.utc)
        assert not starts.due(key, winter, saturday)
    assert not starts.due("evening", "not a cron", uk(NOON))
    # Every cron the gate carries is one the table has a start for.
    carried = set(re.findall(r'cron: "(\d+ \d+ \* \* 1-5)"', gate))
    assert len(carried) == 2 * len(starts.CLOCK)


def test_the_gate_fires_by_the_table_makes_no_comment_and_sends_nothing_of_one(starts):
    gate = (FLOWS / "start.yml").read_text(encoding="utf-8")
    assert not (FLOWS / "answer.yml").exists() and not (FLOWS / "replan.yml").exists()
    for trigger in ("issue_comment:", "issues:", "release:", "schedule:", "workflow_dispatch:"):
        assert f"\n  {trigger}" in gate, trigger
    assert "pull_request" not in gate.partition("\njobs:")[0].partition("\non:")[2], \
        "the gate runs the default branch's table, never a pull request's"
    assert "tools/starts.py --read" in gate and "gh issue comment" not in gate \
        and "gh pr comment" not in gate
    assert "group: start-${{ needs.read.outputs.level }}" in gate and "cancel-in-progress: true" in gate
    fire = gate.partition("\n  fire:")[2]
    assert "github.event.comment.body" not in fire and "BODY" not in fire
    for level in {start.level for start in starts.STARTS.values()}:
        assert f"secrets.ROUTINE_{level.upper()}_URL" in fire, level
        assert f"secrets.ROUTINE_{level.upper()}_TOKEN" in fire, level
    assert "-o /dev/null -w '%{http_code}'" in fire, "only the status is printed"
    assert fire.count("grep -qx paused") == 1, "a wait that ends in a pause starts nothing"
    # Every act the table can ask for is one the workflow does.
    acts = set(re.findall(r'"(rocket|eyes|decision|auto-off|hold|unhold|pause|unpause)"',
                          (ROOT / "tools" / "starts.py").read_text(encoding="utf-8")))
    case = gate.partition('case "$act" in')[2].partition("esac")[0]
    for act in acts:
        assert re.search(rf"(^|\|)\s*{act}[|)]", case, re.M), act


def test_the_bot_asks_only_in_the_working_day_and_holds_the_rest_to_eight(starts):
    notify = (FLOWS / "notify.yml").read_text(encoding="utf-8")
    assert "tools/starts.py --working" in notify and 'if [ "$day" != no ]; then' in notify, \
        "only a clear no holds a question: a fault in reading the hours asks now"
    at = starts.OPENS
    for cron in (f"{at.minute} {at.hour} * * 1-5", f"{at.minute} {at.hour - 1} * * 1-5"):
        assert f'cron: "{cron}"' in notify, cron
    assert "ref: ${{ github.event.pull_request.base.sha || github.sha }}" in notify, \
        "the hours are the base's, never a pull request's"
    assert notify.count("labels[]=ask-held") == 1 and "labels/ask-held" in notify
