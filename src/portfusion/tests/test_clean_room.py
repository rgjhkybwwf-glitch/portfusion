"""tools/clean_room.py: the judgement it makes on a run, and the workflow that runs it.

The clean-room test itself takes a minute and a venv, so it is not run from here; what is held
here is whether a run's output reads as green, which is where a wrong answer would hide, and that
every action the workflow runs it with is pinned.
"""
import importlib.util
import re

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:                  # the whole module reads the checkout's tools/
    pytest.skip(NO_CHECKOUT, allow_module_level=True)


@pytest.fixture(scope="module")
def clean_room():
    """tools/clean_room.py, loaded from its file: a tool beside the app, not a module of it."""
    spec = importlib.util.spec_from_file_location("clean_room", ROOT / "tools" / "clean_room.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_clean_run_is_green(clean_room):
    assert clean_room.verdict(0, "1141 passed, 24 skipped\n") == []


def test_a_failure_is_red(clean_room):
    said = "ERROR tests/test_new.py::test_something - boom\n1 failed, 1140 passed\n"
    assert clean_room.verdict(1, said) == ["FAILED: tests/test_new.py::test_something"]


def test_a_run_that_did_not_complete_is_red_whatever_it_listed(clean_room):
    """pytest exits 2 when interrupted and 4 on a usage error; neither is a verdict on the code."""
    assert clean_room.verdict(2, "") and clean_room.verdict(4, "")


def test_a_failed_run_that_names_no_failure_is_red(clean_room):
    """EXIT 1 WITH NO TEST NAMED: a crash after the tests ran, or the harness failing a run that
    moved the loaded book. With nothing to compare against, it read as green, so a wheel that
    broke in that way passed (the review of 21 Oct 2026)."""
    said = "FAILED: the run moved the loaded book's own files (1): _inbox/.bench\n1141 passed\n"
    assert clean_room.verdict(1, said), "an exit 1 naming no failed test passed"


WORKFLOW = ROOT / ".github" / "workflows" / "guard.yml"


def test_every_action_the_workflow_uses_is_pinned_to_a_commit():
    """A tag can be moved to other code after it is reviewed; a commit cannot. The repository
    also refuses an unpinned action, so this says why before GitHub does."""
    uses = re.findall(r"uses:\s*(\S+)", WORKFLOW.read_text(encoding="utf-8"))
    assert uses and all(re.fullmatch(r"actions/[\w.-]+@[0-9a-f]{40}", u) for u in uses), uses
