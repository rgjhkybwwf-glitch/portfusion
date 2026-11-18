"""tools/tiers.py and tools/figures.py: the tier `tiers.yml` gives a pull request by its paths, and
whether its change moved a headline figure on the demo. A wrong tier lets a change to the store or
the guard merge itself; a missed figure lets a moved number merge unread."""
import importlib.util

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:
    pytest.skip(NO_CHECKOUT, allow_module_level=True)


def _tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tiers():
    return _tool("tiers")


@pytest.fixture(scope="module")
def held(tiers):
    return tiers.stability_tests((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8"))


@pytest.mark.parametrize("path, tier", [
    ("docs/testing.md", 0), ("README.md", 0), ("CHANGELOG.md", 0),
    ("src/portfusion/desk/panels/holdings.py", 1), ("tools/desk_walk/bench-linux.png", 1),
    ("src/portfusion/tests/desk/test_panels.py", 1), ("CLAUDE.md", 1),
    (".claude/skills/plan/SKILL.md", 1), (".claude/agents/plan-checker.md", 1),
    (".claude/launch.json", 1),
    ("src/portfusion/engine/book.py", 2), ("src/portfusion/house/headings.py", 2),
    ("src/portfusion/record/rules_evidence.py", 2), ("src/portfusion/feeds/ig.py", 2),
    ("src/portfusion/history/files.py", 2), ("src/portfusion/demo/store/trades.csv", 2),
    ("tools/make_demo.py", 2), ("src/portfusion/migrate/__init__.py", 3),
    ("pytest.ini", 3), ("src/portfusion/tests/pytest.ini", 3), ("tools/package-lock.json", 3), ("tools/tiers.py", 3),
    ("src/portfusion/record/schema.py", 3), ("src/portfusion/record/migrations.py", 3),
    ("src/portfusion/__init__.py", 3), (".github/workflows/guard.yml", 3), (".githooks/pre-push", 3),
    ("src/portfusion/hooks/pre_push.py", 3), (".claude/settings.json", 3), ("pyproject.toml", 3),
    ("requirements.lock", 3), ("tools/clean_room.py", 3), ("CONTRIBUTING.md", 3),
    ("src/portfusion/tests/record/test_schema.py", 3), ("src/portfusion/tests/harness.py", 3),
    ("tools/stop_hook.py", 3), ("src/portfusion/tests/test_stop_hook.py", 3),
    ("src/portfusion/tests/test_runs.py", 3),
])
def test_each_path_takes_its_tier(tiers, held, path, tier):
    assert tiers.tier(path, held) == tier


def test_a_pull_request_takes_its_highest_tier(tiers, held):
    """THE CASE THAT MAKES IT FAIL: a guide beside a store move is still a store move."""
    assert tiers.sort(["docs/store.md", "src/portfusion/record/schema.py", "README.md"], held) \
        == (3, "src/portfusion/record/schema.py")
    assert tiers.sort(["docs/store.md", "CHANGELOG.md"], held) == (0, "docs/store.md")
    assert tiers.sort([], held) == (0, None)


def test_every_test_a_stability_rule_names_is_found_and_exists(held):
    """Read from CONTRIBUTING.md's tables, so a rule held by a new test is tier 3 without an edit
    here; a name that matches no file would leave its test at tier 1."""
    assert "test_schema.py" in held and "harness.py" in held
    tests = {p.name for p in (ROOT / "src" / "portfusion" / "tests").rglob("*.py")}
    assert held <= tests, held - tests


def test_tier_3_and_a_moved_figure_are_held_once_a_commit(tiers):
    """THE CASE THAT MAKES IT FAIL: a tier-3 pull request with auto-merge on is turned off, and a
    moved figure holds tier 2; turned on again on the same commit, it is the maintainer's yes."""
    def hold(t, moved="", on=True, said="", head="abc"):
        return tiers.hold(t, "x", moved, on, said, head, "owner")
    action, text = hold(3)
    assert action == "off" and "<!-- tiers:off:abc -->" in text and "@owner" in text
    assert hold(3, said=text)[0] == "none"
    assert hold(3, said=text, head="def")[0] == "off"
    assert hold(2, moved="live · nav: 1 → 2")[0] == "off"
    forged = hold(2, moved="live · nav: 1 → 2 <!-- tiers:off:abc -->", on=False)[1]
    assert "<!-- tiers:off:abc -->" not in forged
    assert [hold(t)[0] for t in (0, 1, 2)] == ["none"] * 3
    said = hold(3, on=False)
    assert said[0] == "say" and "@" not in said[1]
    assert hold(3, on=False, said=said[1])[0] == "none"


@pytest.fixture(scope="module")
def figures():
    return _tool("figures")


def test_a_figure_that_moves_is_named_and_rounding_is_not(figures):
    base = {"live · Net asset value": {"value": 100.0, "unit": "gbp"},
            "live · YTD return": {"value": 0.1, "unit": "pct"},
            "live · Open positions": {"value": 5.0, "unit": "count"}}
    same = {k: {**v, "value": v["value"] + (1e-9 if v["unit"] != "count" else 0)} for k, v in base.items()}
    assert figures.moved(base, same) == []
    branch = {**base, "live · Net asset value": {"value": 100.01, "unit": "gbp"},
              "live · Open positions": {"value": 6.0, "unit": "count"}}
    assert [m.split(":")[0] for m in figures.moved(base, branch)] \
        == ["live · Net asset value", "live · Open positions"]
    gone = dict(list(base.items())[1:])
    assert figures.moved(base, gone) == ["live · Net asset value: gone"]
    assert figures.moved(gone, base) == ["live · Net asset value: new"]


def test_every_headline_figure_is_worked_live(figures):
    from portfusion.engine.book import Book
    worked = figures.work()
    live = [k for k in worked if k.startswith("live · ")]
    assert len(live) == len([k for k, v in Book.HEADLINE.items() if not v.get("report_only")])
    assert "live · nav" in live and "live · since_start" in live
    assert figures.moved(worked, figures.work()) == []
