"""tools/stop_hook.py: when a run of the nightly agent may end. A run that ends with its pull
request's `guard` still running leaves it red unseen; one that ends without "Next:" leaves the
maintainer not knowing who acts next. A session with the maintainer is never held, and no run is
held forever."""
import importlib.util
import json

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:
    pytest.skip(NO_CHECKOUT, allow_module_level=True)

RUN = "Read CLAUDE.md and CONTRIBUTING.md. Follow CONTRIBUTING's section \"The nightly agent\" as the night run."
DEBRIEF = "Merged #250.\nNothing waits on you.\nNext: the night run, at 02:00, builds #251."


@pytest.fixture(scope="module")
def hook():
    spec = importlib.util.spec_from_file_location("stop_hook", ROOT / "tools" / "stop_hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_run_waits_for_guard_then_for_its_debrief(hook):
    """THE CASE THAT MAKES IT FAIL: a run ending with `guard` pending, or without "Next:"."""
    reason, state = hook.decide(RUN, DEBRIEF, ["#292"], {}, now=1000.0)
    assert reason and "#292" in reason and state["guard_since"] == 1000.0
    reason, state = hook.decide(RUN, "All done.", [], {}, now=1000.0)
    assert reason and "Next:" in reason
    assert hook.decide(RUN, DEBRIEF, [], {}, now=1000.0)[0] is None
    assert hook.decide(RUN, "**Next:** the ready check, at 06:50.", [], {}, now=0)[0] is None


def test_no_run_is_held_forever_and_no_other_session_at_all(hook):
    state = {"guard_since": 0.0}
    assert hook.decide(RUN, DEBRIEF, ["#292"], state, now=hook.WAIT_GUARD * 60 + 1)[0] is None
    state = {}
    asked = [hook.decide(RUN, "done", [], state, now=0)[0] for _ in range(hook.ASK_DEBRIEF + 1)]
    assert all(asked[:-1]) and asked[-1] is None
    assert hook.decide("Fix the walk on #292, please.", "done", ["#292"], {}, now=0)[0] is None
    asked = 'Read CONTRIBUTING.md (especially the section "The nightly agent") and build #284.'
    assert hook.decide(asked, "done", ["#292"], {}, now=0)[0] is None
    assert hook.decide(RUN, DEBRIEF, None, {}, now=0)[0] is None      # GitHub out of reach


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


def test_settings_run_the_hook_on_stop(repo_root):
    settings = json.loads((repo_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [h["command"] for entry in settings["hooks"]["Stop"] for h in entry["hooks"]]
    assert any("tools/stop_hook.py" in c for c in commands), commands
