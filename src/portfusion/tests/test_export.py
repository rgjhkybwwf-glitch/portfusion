"""tools/export_test.py: the copy leaves exactly the facts behind, and the known seams only shrink.

The export test itself takes a minute and a venv, so it is not run from here; what is held here
is the two judgements it makes, which are where a wrong answer would hide: which files are facts,
and whether a run's failures are the known seams; and that the workflow, which
runs it on GitHub, skips exactly the pushes it cannot fail on.
"""
import importlib.util
import re

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:                  # the whole module reads the checkout's tools/
    pytest.skip(NO_CHECKOUT, allow_module_level=True)


@pytest.fixture(scope="module")
def export():
    """tools/export_test.py, loaded from its file: a tool beside the app, not a module of it."""
    spec = importlib.util.spec_from_file_location("export_test", ROOT / "tools" / "export_test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path, fact", [
    ("store/trades.csv", True),
    ("_archive/statements/ii/2026/a contract note.pdf", True),
    ("_archive/bench/B-20261012-5b340f.json", True),
    ("docs/store.md", False),             # a guide travels; the store's facts do not
    ("docs/intake.md", False),
    ("docs/decisions.md", True),          # the guides that stay with the book stay behind too
    ("docs/backup.md", True),
    ("docs/publication.md", True),
    ("ROADMAP.md", True),
    ("src/portfusion/demo/store/trades.csv", False),     # the demo's facts ARE the export's book
    ("src/portfusion/demo/_archive/bench/B-20260928-5d3a01.json", False),
])
def test_the_facts_are_the_books_and_nothing_else(export, path, fact):
    assert export.is_fact(path) is fact


#: Two seams standing in for a list: the real one is empty since the code can leave, and the
#: ratchet must still hold the day a seam is listed again.
_SEAMS = {"tests/test_a.py::test_one": "An item", "tests/test_b.py::test_two": "An item"}


@pytest.fixture
def seams(export, monkeypatch):
    monkeypatch.setattr(export, "KNOWN_SEAMS", dict(_SEAMS))
    return export


def test_a_clean_run_on_the_real_list_is_green(export):
    assert export.verdict(0, "1141 passed, 24 skipped\n") == []


def test_a_run_failing_exactly_the_known_seams_is_as_expected(seams):
    said = "".join(f"FAILED {t} - why\n" for t in _SEAMS) + "2 failed, 1110 passed\n"
    assert seams.verdict(1, said) == []


def test_a_failure_outside_the_seams_is_red(seams):
    said = "".join(f"FAILED {t} - why\n" for t in _SEAMS)
    said += "ERROR tests/test_new.py::test_something - boom\n"
    assert seams.verdict(1, said) == ["FAILED, and not a known seam: tests/test_new.py::test_something"]


def test_a_seam_that_starts_passing_is_red_until_its_line_goes(seams):
    """The ratchet: the item that closes a seam deletes it from the list in the same change."""
    first, *rest = _SEAMS
    said = "".join(f"FAILED {t} - why\n" for t in rest)
    [problem] = seams.verdict(1, said)
    assert problem.startswith("PASSES now") and first in problem


def test_a_run_that_did_not_complete_is_red_whatever_it_listed(export):
    """pytest exits 2 when interrupted and 4 on a usage error; neither is a verdict on the code."""
    assert export.verdict(2, "") and export.verdict(4, "")


def test_a_failed_run_that_names_no_failure_is_red(export):
    """EXIT 1 WITH NO TEST NAMED: a crash after the tests ran, or the harness failing a run that
    moved the loaded book. With nothing to compare against the seams it read as green, so a wheel
    that broke in that way passed the export (the review of 21 Oct 2026)."""
    said = "FAILED: the run moved the loaded book's own files (1): _inbox/.bench\n1141 passed\n"
    assert export.verdict(1, said), "an exit 1 naming no failed test passed"


# =====================================================================================
# THE WORKFLOW RUNS IT
# =====================================================================================

WORKFLOW = ROOT / ".github" / "workflows" / "guard.yml"


def _ignored_paths(text: str) -> list[list[str]]:
    """Each `paths-ignore:` list in the workflow, in order. The file is read as lines rather than
    as YAML because the project installs no YAML reader, and these lists are one glob a line."""
    lists, current = [], None
    for line in text.splitlines():
        if line.strip() == "paths-ignore:":
            current = []
            lists.append(current)
        elif current is not None and line.strip().startswith("- "):
            current.append(line.strip()[2:].strip().strip("\"'"))
        else:
            current = None
    return lists


def test_the_workflow_skips_exactly_what_the_export_leaves_behind(export):
    """A push of facts alone cannot change the export test's answer, so the workflow skips it. A
    glob in one list and not the other would either spend a run on nothing or skip one that
    could fail."""
    lists = _ignored_paths(WORKFLOW.read_text(encoding="utf-8"))
    assert len(lists) == 2, "a pull request and a push to main each skip the facts"
    assert all(found == list(export.FACTS) for found in lists), (lists, export.FACTS)


def test_every_action_the_workflow_uses_is_pinned_to_a_commit():
    """A tag can be moved to other code after it is reviewed; a commit cannot. The repository
    also refuses an unpinned action, so this says why before GitHub does."""
    uses = re.findall(r"uses:\s*(\S+)", WORKFLOW.read_text(encoding="utf-8"))
    assert uses and all(re.fullmatch(r"actions/[\w.-]+@[0-9a-f]{40}", u) for u in uses), uses
