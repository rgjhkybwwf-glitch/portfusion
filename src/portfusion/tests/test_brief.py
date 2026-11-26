"""tools/brief.py: the facts a run starts from, worked out in code. A brief that names the wrong
row gives a run the wrong cap; one that calls a held line free sends a builder onto an issue the
maintainer stopped; one that fails loudly stops a run that could have read for itself; and one
that writes is a run nobody started. Every example is invented."""
import importlib.util
import re
from datetime import datetime, timezone

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:
    pytest.skip(NO_CHECKOUT, allow_module_level=True)

QUEUE = """\
The builders build only lines under **Next**.

## Next
0.9.1 An invented milestone · opened 1 Jan 2030.
- [ ] #11 A first line (placed 1 Jan 2030: a small safe fix; its wait on #5 met 2 Jan 2030)
- [ ] #12 A second line · waits #11 (added 2 Jan 2030: both change one file)
- [ ] #13 B4 · confirm inside the page · waits on #11, #40 (#40 added 3 Jan 2030)
- [x] #14 A line already ticked
- [ ] #15 The release checklist: the gate · last, after every line above has merged

## Design next
- #20 A feature whose card is drafted next

## After the gate
- [ ] #30 A line of the next milestone · waits #15
"""


@pytest.fixture(scope="module")
def brief():
    spec = importlib.util.spec_from_file_location("brief", ROOT / "tools" / "brief.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def table(brief):
    return brief.rows((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))


def uk(brief, day, hour, minute):
    return datetime(2030, 1, day, hour, minute, tzinfo=brief.starts.ZONE).astimezone(timezone.utc)


def issue(*labels, title="An issue"):
    return {"labels": list(labels), "title": title, "created": datetime(2030, 1, 1, tzinfo=timezone.utc)}


def pull(number, closes, draft=False, ref="claude/a-branch"):
    return {"number": number, "draft": draft, "head": {"ref": ref, "sha": "a" * 40},
            "body": f"Closes #{closes}", "labels": [], "user": {"login": "owner"}}


def test_a_run_finds_its_row_by_its_clock_or_by_the_gates_own_text(brief, table):
    """THE CASE THAT MAKES IT FAIL: a row found wrongly gives the run another's cap, and a builder
    started for an answer build that reads "Answer:" takes the coordinator's row. Each clocked row
    is found at its own hour and for three hours after, and every text the gate sends finds the
    row the gate's own table names."""
    clocked = [row for row in table if brief.CLOCK.search(row["What starts it"])]
    assert len(clocked) >= 3
    for row in clocked:
        said = brief.CLOCK.search(row["What starts it"])
        for late in (0, 5, 179):       # the fixture's 2nd is a Wednesday
            at = int(said[1]) * 60 + int(said[2]) + late
            now = uk(brief, 2 + at // (24 * 60), at // 60 % 24, at % 60)
            assert brief.which(table, row["Level"].lower(), "", now)["Run"] == row["Run"], (row, late)
        at = int(said[1]) * 60 + int(said[2]) + brief.ROW_FOR
        assert brief.which(table, row["Level"].lower(), "", uk(brief, 2, at // 60 % 24, at % 60)) != row, \
            "hours past its clock, a run with no text is not that row's"
        if said[3] == "Monday to Friday":
            assert brief.which(table, row["Level"].lower(), "", uk(brief, 5, int(said[1]), int(said[2]))) \
                is None, "a weekday's clock names no run on a Saturday"
    for key, start in brief.starts.STARTS.items():
        text = brief.starts.text(key, "9", "https://example.invalid/9", "v9.9.9")
        assert brief.which(table, start.level, text, uk(brief, 3, 12, 0))["Run"] == start.run, key
    assert brief.which(table, "builder", "Answer: an answer", uk(brief, 3, 0, 31)) is None
    assert brief.which(table, "coordinator", "A text that names no row", uk(brief, 3, 6, 31)) is None


def test_the_lines_under_next_are_read_in_order_with_their_waits(brief):
    lines = brief.next_lines(QUEUE)
    assert [line.number for line in lines] == [11, 12, 13, 15], "Next only, unticked, in order"
    assert [line.waits for line in lines] == [(), (11,), (11, 40), (11, 12, 13)], \
        ("a wait is what follows \"waits\" or \"waits on\", not a number in the brackets after "
         "it; and the line that is last waits on every line above")
    assert lines[2].title == "B4 · confirm inside the page"
    assert lines[3].title == "The release checklist: the gate"
    assert brief.next_lines("No list here.") == []


def test_a_builder_is_sent_only_to_a_line_it_may_take(brief):
    """THE CASE THAT MAKES IT FAIL: a line called free that carries `hold`, has a pull request of
    its own, waits on an open issue, or was marked "Re-plan" since its plan."""
    lines = [brief.Line(n, f"Line {n}", waits) for n, waits in
             ((1, ()), (2, ()), (3, ()), (4, ()), (5, (90,)), (6, (91,)), (7, ()), (8, ()), (9, ()))]
    issues = {1: issue(), 2: issue("planned", "hold"), 3: issue("planned", "decision"),
              4: issue("planned", "building"), 5: issue("planned"), 6: issue("planned"),
              7: issue("planned"), 8: issue("planned"), 90: issue()}
    own = {7: [pull(70, 7)], 8: [pull(80, 8)]}
    plans = {8: {"at": None, "commit": "", "since": ["Re-plan"]}}
    said, takeable, standing = brief.lines_said(lines, issues, own, plans)
    assert takeable == [6], "only the planned line whose one wait is closed"
    assert brief.lines_said(lines, issues, own, plans, holes=("#6's comments",))[1] == [], \
        "with a read it rests on failed, no line is called free"
    unread = brief.lines_said(lines, issues, own, plans, holes=("the open issues, past its first 500",))
    assert "#9 not read" in unread[0][8] and "waits #91 (not read)" in unread[0][5], \
        "an issue the cut list does not hold is not called closed"
    assert brief.lines_said(lines, issues, own, plans, marked=True)[1] == [], "an answer build's rule"
    plans[6] = {"at": None, "commit": "", "since": ["Build"]}
    assert brief.lines_said(lines, issues, own, plans, marked=True)[1] == [6]
    del plans[6]
    assert "a builder may take it" in said[5] and "waits #90 (open)" in said[4]
    assert "closed, not yet ticked" in said[8], "a line whose issue is closed is said so"
    assert standing == [2, 3, 4, 5, 6, 8], \
        "a planned line with a ready pull request is built and holds no place, unless it is re-planned"
    own[7][0]["draft"] = True
    assert 7 in brief.lines_said(lines, issues, own, plans)[2], "a draft is not yet built"


def test_the_run_log_and_an_issues_comments_are_read_as_the_gate_reads_them(brief):
    log = [
        {"created_at": "2030-01-02T06:31:00Z", "body": "📋 **Coordinator** · start · 2 Jan 06:30 · the morning run"},
        {"created_at": "2030-01-02T06:58:00Z", "body": "📋 **Coordinator** · 2 Jan 6:30–06:58 · planned #11 · Next: the night build"},
        {"created_at": "2030-01-03T00:31:00Z", "body": "🌙 **Builder** · start · 3 Jan 00:30 · the night build"},
        {"created_at": "2030-01-03T00:50:00Z", "body": "🌙 **Builder** · 3 Jan 00:30–00:50 · built #11 · Next: you"},
        {"created_at": "2030-01-03T06:31:00Z", "body": "📋 **Coordinator** · start · 3 Jan 06:30 · the morning run"},
    ]
    began, line = brief.last_run("coordinator", log)
    assert began == datetime(2030, 1, 2, 6, 31, tzinfo=timezone.utc), \
        ("the changes are read from the start of the last run that ended, not of this one, and "
         "\"6:30\" and \"06:30\" are one minute, as the gate reads them")
    assert line.endswith("Next: the night build")
    assert brief.last_run("builder", log)[1].startswith("🌙 **Builder** · 3 Jan 00:30–00:50")
    assert brief.last_run("builder", log[:2]) == (None, "")

    comments = [
        {"created_at": "2030-01-02T06:40:00Z", "body": "📋 **Coordinator** · 2 Jan 2030 · **Plan, checked** against `main` at abc1234. The files"},
        {"created_at": "2030-01-02T07:00:00Z", "body": "Plan, checked? I am not sure."},
        {"created_at": "2030-01-02T07:30:00Z", "body": "📋 **Coordinator** · 2 Jan 2030 · recorded your answer; the **Plan, checked** stands"},
        {"created_at": "2030-01-02T07:40:00Z", "body": "🌙 **Builder** · 2 Jan 2030 · **Plan, checked** is what I built on"},
        {"created_at": "2030-01-02T08:00:00Z", "body": "🌙 **Builder** · Build: it failed on the walk"},
        {"created_at": "2030-01-02T09:00:00Z", "body": "📋 **Coordinator** · Build: answered as recommended, so the **Plan, checked, if answered as recommended** stands"},
    ]
    plan = brief.plan_of(comments)
    assert plan["commit"] == "abc1234" and plan["since"] == ["Build"], \
        "a comment that quotes the plan is no new plan, and only the coordinator's \"Build:\" counts"
    later = comments + [{"created_at": "2030-01-03T06:40:00Z", "body":
                         "📋 **Coordinator** · 3 Jan 2030 · **Plan, checked, if answered as recommended** against `main` at def5678."}]
    assert brief.plan_of(later) == {"at": datetime(2030, 1, 3, 6, 40, tzinfo=timezone.utc),
                                    "commit": "def5678", "since": []}, "a new plan starts the count again"


@pytest.mark.parametrize("body, bot, kind", [
    ("Q1: a", False, "the maintainer's answer"),
    ("all as recommended", False, "the maintainer's answer"),
    ("Change: build it another way", False, "the maintainer's `Change:`"),
    ("hold: not yet", False, "the maintainer's `Hold:`"),
    ("I would rather it read like this", False, "the maintainer's other words"),
    ("**Session note** · 2 Jan 2030: the maintainer settled it", False, "a session's note"),
    ("🌙 **Builder** · Re-plan: main moved under it", False, 'a run\'s "Re-plan:"'),
    ("🌙 **Builder** · 2 Jan 2030 · built it", False, ""),
    ("🤖 **PortFusion agent** · this waits for you", True, "the bot wrote"),
])
def test_a_comment_since_the_last_run_is_named_by_whose_it_is(brief, body, bot, kind):
    """A run's own words are never counted as the maintainer's: the brief sorts by the gate's own
    reading of the first line."""
    comment = {"body": body, "issue_url": "https://example.invalid/issues/12",
               "user": {"type": "Bot" if bot else "User"}}
    assert brief.comment_said(comment) == (kind, "12")


class Canned:
    """GitHub, canned: what is asked for by its path, and what is missing."""

    def __init__(self, answers, missing=()):
        self.answers, self.missing, self.missed, self.paths = answers, missing, [], []

    def get(self, path, what, pages=1, key="", one=False, newest=False):
        self.paths.append(path)
        if what in self.missing:
            self.missed.append(what)
        elif path in self.answers:
            return self.answers[path]
        return {} if one else []


def test_the_brief_says_the_line_what_it_could_not_read_and_stops_at_a_pause(brief):
    """THE CASES THAT MAKE IT FAIL: a clock's run in a pause sent on to the Queue; a read that
    failed passed over in silence, so the run trusts a brief with a hole in it."""
    now = uk(brief, 3, 0, 31)
    answers = {
        f"issues/{brief.starts.QUEUE}": {"labels": [], "body": QUEUE},
        "issues?state=open": [
            {"number": 11, "labels": [{"name": "planned"}], "title": "A first line",
             "created_at": "2030-01-01T00:00:00Z"},
            {"number": 12, "labels": [], "title": "A second line", "created_at": "2030-01-01T00:00:00Z"},
        ],
    }
    out = "\n".join(brief.brief("builder", "", now, Canned(answers)))
    assert "Run: Night build" in out and "The line to take: #11." in out
    assert "Not read" not in out

    asked = Canned(answers, missing=("the open pull requests",))
    out = "\n".join(brief.brief("builder", "", now, asked))
    assert "Not read, so read it as the role book says: the open pull requests" in out
    assert "The line to take: not decided here" in out and "may take it" not in out, \
        "a line whose own pull request could not be looked for is not called free"
    assert "The agent's open pull requests: not read" in out
    morning = uk(brief, 3, 6, 31)
    out = "\n".join(brief.brief("coordinator", "", morning, Canned(answers, missing=("the open pull requests",))))
    assert "Plans that stand and are not yet built: not counted here" in out, \
        "a count that rests on a failed read is not given as a number"
    assert "Plans that stand and are not yet built: 1 (#11)" in "\n".join(
        brief.brief("coordinator", "", morning, Canned(answers)))
    out = brief.brief("builder", "", now, Canned(answers, missing=("the Queue",)))
    assert "Paused: not read" in out[-1] and "Next, in" not in "\n".join(out), \
        "a Queue that could not be read is never read as a loop that is not paused"

    paused = dict(answers, **{f"issues/{brief.starts.QUEUE}": {"labels": [{"name": "paused"}], "body": QUEUE}})
    asked = Canned(paused)
    out = brief.brief("builder", "", now, asked)
    assert "Paused: yes" in out[-1] and len(asked.paths) == 1, "a paused clock's run reads no further"
    assert "Paused: yes" in brief.brief("builder", "night", now, Canned(paused))[-1], \
        "a stray word after the level does not make a clock's run the gate's"
    out = "\n".join(brief.brief("coordinator", "Re-plan: the maintainer resumed the loop", now, Canned(paused)))
    assert "Run: Re-plan" in out and "Next, in the Queue's order" in out, \
        "a run the gate started is never met by a pause: the gate starts none in one"

    out = brief.brief("builder", brief.starts.text("hand"), now, Canned({}))
    assert len(out) == 2 and "dry run" in out[1].lower()


def test_the_brief_only_reads_and_never_stops_a_run(brief, monkeypatch, capsys):
    """It asks GitHub by `gh api` with no method and no field, so every call is a read; and a
    failure of its own is said in a line, with a clean exit."""
    source = (ROOT / "tools" / "brief.py").read_text(encoding="utf-8")
    calls = re.findall(r"subprocess\.run\(\s*\[([^\]]+)\]", source)
    assert len(calls) == 2 and all(c.startswith(('"gh", "api", f"repos/', '"git", "-C"')) for c in calls)
    for word in ('"-X"', "--method", '"-f"', '"-F"', "--field", "--input", "POST", "PATCH", "DELETE"):
        assert word not in source, word

    def fails(*args, **kwargs):
        raise OSError("no network")
    monkeypatch.setattr(brief.subprocess, "run", fails)
    asked = brief.Asked("owner/invented")
    assert asked.get("issues?state=open", "the open issues", pages=5) == []
    assert asked.get("issues/1", "the Queue", one=True) == {}
    assert asked.missed == ["the open issues", "the Queue"], "a read that failed is named, and empty"

    class Full:
        stdout = "[" + ", ".join(["{}"] * 100) + "]"
    monkeypatch.setattr(brief.subprocess, "run", lambda *args, **kwargs: Full())
    asked = brief.Asked("owner/invented")
    assert len(asked.get("issues/9/comments", "#9's comments", pages=2)) == 200
    assert asked.missed == ["#9's comments, past its first 200"], "a read cut short is named"
    assert len(asked.get("pulls?state=closed", "the closed", newest=True)) == 100
    assert len(asked.missed) == 1, "the head of a list asked for newest first is all that is wanted"
    assert asked.get("issues/1", "the Queue", one=True) == {} and asked.missed[-1] == "the Queue", \
        "an answer that is not the one thing asked for was not read"

    said = {}
    monkeypatch.setattr(brief, "_repo", lambda: "owner/invented")
    monkeypatch.setattr(brief, "brief", lambda level, text, now, asked: said.update(text=text) or [])
    assert brief.main(["coordinator", "Re-plan: marked", "Re-plan", "since their last"]) == 0
    assert said["text"] == "Re-plan: marked Re-plan since their last", \
        "a starting text a shell split at its quotes is still one text"
    monkeypatch.undo()
    monkeypatch.setattr(brief, "_repo", fails)
    assert brief.main(["builder"]) == 0
    assert "it failed and says nothing" in capsys.readouterr().out
    assert brief.main(["maintainer"]) == 2
