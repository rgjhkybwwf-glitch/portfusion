"""tools/stop_hook.py: when a run of the loop may end. A run that ends with its pull request's
`guard` still running leaves it red unseen; one that ends with a helper agent out acts on a guess
of its result; one that ends without "Next:" leaves the maintainer not knowing who acts next. A
session with the maintainer is never held, no run is held forever, and each hold is logged for
the run's end line."""
import importlib.util
import json

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:
    pytest.skip(NO_CHECKOUT, allow_module_level=True)

RUN = "Read CLAUDE.md and CONTRIBUTING.md. Follow CONTRIBUTING's section \"The loop\" as the builder, exactly."
DEBRIEF = "Merged #250.\nNothing waits on you.\nNext: the night build, at 00:30, builds #251."


@pytest.fixture(scope="module")
def hook():
    spec = importlib.util.spec_from_file_location("stop_hook", ROOT / "tools" / "stop_hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_run_waits_for_guard_for_its_helper_then_for_its_debrief(hook):
    """THE CASE THAT MAKES IT FAIL: a run ending with `guard` pending, a helper out, or no "Next:"."""
    reason, state = hook.decide(RUN, DEBRIEF, ["#292"], {}, now=1000.0)
    assert reason and "#292" in reason and state["since"]["guard"] == 1000.0
    reason, state = hook.decide(RUN, DEBRIEF, [], {}, now=1000.0, helpers=["plan-checker"])
    assert reason and "plan-checker" in reason and state["since"]["helper"] == 1000.0
    reason, state = hook.decide(RUN, "All done.", [], {}, now=1000.0)
    assert reason and "Next:" in reason
    assert hook.decide(RUN, DEBRIEF, [], {}, now=1000.0, helpers=[])[0] is None
    assert hook.decide(RUN, "**Next:** the morning run, at 06:30.", [], {}, now=0)[0] is None
    assert hook.decide(RUN, "- Next: the night build.", [], {}, now=0)[0] is None


def test_a_run_is_told_by_the_section_the_runs_table_is_under(hook, repo_root):
    """A renamed section, or a new row, needs no change to the hook: it reads the heading, and a
    prompt that names any other section is not a run's."""
    contributing = (repo_root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    name = hook.section(contributing)
    assert f"\n### {name} (" in contributing or f"\n### {name}\n" in contributing
    assert hook.section(contributing.replace(f"### {name}", "### The works")) == "The works"
    assert hook.section("# A guide\n\nNo table here.\n") == ""
    assert hook.decide(f"Follow CONTRIBUTING's section \"{name}\" as the coordinator, exactly.\n"
                       "Idea: the maintainer opened an idea, the last #9.", "done", [], {}, now=0)[0]
    assert hook.decide(RUN.replace("The loop", "The works"), "done", [], {}, now=0)[0] is None


def test_no_run_is_held_forever_and_no_other_session_at_all(hook):
    state = {}
    assert hook.decide(RUN, DEBRIEF, ["#292"], state, now=0.0)[0]
    assert hook.decide(RUN, DEBRIEF, ["#292"], state, now=hook.WAIT_GUARD * 60 + 1)[0] is None
    state = {}
    assert hook.decide(RUN, DEBRIEF, [], state, now=0.0, helpers=["skeptic-reviewer"])[0]
    late = hook.WAIT_HELPER * 60 + 1
    assert hook.decide(RUN, DEBRIEF, [], state, now=late, helpers=["skeptic-reviewer"])[0] is None
    state = {}
    asked = [hook.decide(RUN, "done", [], state, now=0, held=n > 0)[0] for n in range(hook.ASK_DEBRIEF + 1)]
    assert all(asked[:-1]) and asked[-1] is None
    assert hook.decide(RUN, "done", [], state, now=0, held=False)[0]   # a new attempt to end asks again
    state = {}
    hook.decide(RUN, DEBRIEF, ["#292"], state, now=0.0)
    hook.decide(RUN, DEBRIEF, [], state, now=10.0)                      # the wait is over
    assert hook.decide(RUN, DEBRIEF, ["#293"], state, now=hook.WAIT_GUARD * 60 + 20)[0]
    assert hook.decide("Fix the walk on #292, please.", "done", ["#292"], {}, now=0)[0] is None
    asked = 'Read CONTRIBUTING.md (especially the section "The loop") and build #284.'
    assert hook.decide(asked, "done", ["#292"], {}, now=0, helpers=["plan-checker"])[0] is None


def test_what_cannot_be_asked_holds_nothing_and_forgets_nothing(hook):
    assert hook.decide(RUN, DEBRIEF, None, {}, now=0)[0] is None        # GitHub out of reach
    assert hook.decide(RUN, DEBRIEF, [], {}, now=0, helpers=None)[0] is None
    state = {}
    hook.decide(RUN, DEBRIEF, ["#292"], state, now=0.0)
    assert hook.decide(RUN, DEBRIEF, None, state, now=60.0)[0] is None
    assert hook.decide(RUN, DEBRIEF, ["#292"], state, now=120.0)[0]
    assert len(state["holds"]) == 1 and state["since"]["guard"] == 0.0  # one wait, not two


def test_only_a_helper_agent_still_out_is_a_helper(hook):
    tasks = [{"id": "t1", "type": "shell", "status": "running", "command": "portfusion desk"},
             {"id": "t2", "type": "subagent", "status": "running", "agent_type": "plan-checker",
              "description": "check #250's plan"},
             {"id": "t3", "type": "subagent", "status": "running", "description": "a wide read"},
             {"id": "t4", "type": "monitor", "status": "running"}]
    assert hook.helpers({"background_tasks": tasks}) == ["plan-checker", "a wide read"]
    assert hook.helpers({"background_tasks": []}) == []
    assert hook.helpers({}) is None                                     # Claude Code sent no list


def test_each_hold_is_logged_and_said_as_the_end_line_says_it(hook):
    state = {}
    assert hook.said(state.get("holds", []), now=0.0) == ""            # never held: nothing to say
    hook.decide(RUN, DEBRIEF, ["#292"], state, now=0.0)
    hook.decide(RUN, DEBRIEF, ["#292"], state, now=300.0)               # the same wait: one hold
    assert hook.said(state["holds"], now=420.0) == "held 1× for `guard`, 7 min"   # open: to now
    hook.decide(RUN, DEBRIEF, [], state, now=720.0, helpers=["plan-checker"])
    hook.decide(RUN, "done", [], state, now=900.0, helpers=[])
    hook.decide(RUN, "still done", [], state, now=901.0, held=True, helpers=[])
    assert hook.decide(RUN, DEBRIEF, [], state, now=902.0, held=True, helpers=[])[0] is None
    assert hook.said(state["holds"], now=5000.0) == (
        "held 1× for `guard`, 12 min; 1× for a helper, 3 min; 2× for the debrief")
    assert [hold["cause"] for hold in state["holds"]] == ["guard", "helper", "debrief", "debrief"]
    state = {}
    hook.decide(RUN, DEBRIEF, ["#292"], state, now=0.0)
    hook.decide(RUN, DEBRIEF, ["#292"], state, now=hook.WAIT_GUARD * 60.0)
    assert hook.said(state["holds"], now=9e9) == f"held 1× for `guard`, {hook.WAIT_GUARD} min, 1 let go"


def test_holds_prints_the_sessions_log_and_nothing_for_a_run_never_held(hook, monkeypatch, tmp_path,
                                                                        capsys):
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(hook.sys, "argv", ["stop_hook.py", "--holds"])
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    assert hook.main() == 0 and capsys.readouterr().out == ""
    holds = [{"cause": "guard", "what": ["#292"], "from": 0.0, "to": 720.0}]
    hook.kept("abc").write_text(json.dumps({"holds": holds}))
    hook.kept("other").write_text(json.dumps({"holds": holds * 2}))
    assert hook.main() == 0 and capsys.readouterr().out == "held 1× for `guard`, 12 min\n"
    hook.kept("abc").write_text("not json")
    assert hook.main() == 0 and capsys.readouterr().out == ""


def test_a_stop_is_read_held_and_logged_end_to_end(hook, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(hook.sys, "argv", ["stop_hook.py"])
    monkeypatch.setattr(hook, "pending", lambda cwd, now: [])
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps({"type": "user", "message": {"content": RUN}}) + "\n", encoding="utf-8")
    stop = {"session_id": "abc", "transcript_path": str(path), "cwd": str(tmp_path),
            "last_assistant_message": DEBRIEF,
            "background_tasks": [{"id": "t", "type": "subagent", "agent_type": "plan-checker"}]}
    monkeypatch.setattr(hook.sys, "stdin", __import__("io").StringIO(json.dumps(stop)))
    assert hook.main() == 0
    said = json.loads(capsys.readouterr().out)
    assert said["decision"] == "block" and "plan-checker" in said["reason"]
    assert json.loads(hook.kept("abc").read_text())["holds"][0]["cause"] == "helper"
    stop["background_tasks"] = []
    monkeypatch.setattr(hook.sys, "stdin", __import__("io").StringIO(json.dumps(stop)))
    assert hook.main() == 0 and capsys.readouterr().out == ""
    assert json.loads(hook.kept("abc").read_text())["holds"][0]["to"] is not None


def test_the_transcript_gives_the_first_prompt_and_the_last_words(hook, tmp_path):
    lines = [{"type": "user", "isMeta": True, "message": {"content": "<system>caveat</system>"}},
             {"type": "user", "message": {"content": RUN}},
             {"type": "assistant", "message": {"content": [{"type": "text", "text": "Working."}]}},
             {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
             {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
             {"type": "assistant", "message": {"content": [{"type": "text", "text": DEBRIEF}]}}]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n", encoding="utf-8")
    assert hook.transcript(str(path)) == (RUN, DEBRIEF)


def test_a_hook_that_fails_holds_nothing_and_says_so(hook, monkeypatch, capsys):
    monkeypatch.setattr(hook.sys, "argv", ["stop_hook.py"])
    monkeypatch.setattr(hook.sys, "stdin", __import__("io").StringIO("not json"))
    assert hook.main() == 0
    assert "held nothing" in capsys.readouterr().out


def test_settings_run_the_hook_on_stop(repo_root):
    settings = json.loads((repo_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [h["command"] for entry in settings["hooks"]["Stop"] for h in entry["hooks"]]
    assert any("tools/stop_hook.py" in c for c in commands), commands
