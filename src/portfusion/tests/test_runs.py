"""The runs' pointers: CONTRIBUTING's runs table names a playbook, a playbook names step skills, and
a step skill names its helper agent and the heading its rule is under. Each is a name written in
one file about another, so a renamed skill or a cut heading would leave a run following a pointer
to nothing, and say nothing. Pointers only go down: no step skill names a run."""
import re

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:
    pytest.skip(NO_CHECKOUT, allow_module_level=True)

SKILLS = ROOT / ".claude" / "skills"
AGENTS = ROOT / ".claude" / "agents"
SECTION = "### The nightly agent"
WHO = ("Any run:", "Any session:", "Coordinator:", "Builder:", "Playbook:")
TICKED = re.compile(r"`([^`\n]+)`")
LINKED = re.compile(r"\]\((?:\.\./)?\.claude/skills/([^/)]+)/SKILL\.md\)")
SAID = re.compile(r"\bskills? `([^`\n]+)`")
CITED = re.compile(r"\(([\w/.-]+\.md), ([^()]+)\)")


def _front(text):
    """A skill's frontmatter as written, a key to the rest of its line, and its body."""
    _, front, body = text.split("---\n", 2)
    return dict(line.split(": ", 1) for line in front.splitlines()), body


@pytest.fixture(scope="module")
def skills():
    """Each skill by its folder's name: its frontmatter, its body, and its whole text."""
    found = {}
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        found[path.parent.name] = (*_front(text), text)
    return found


@pytest.fixture(scope="module")
def contributing():
    return (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def section(contributing):
    """The agent's own section of CONTRIBUTING, heading to the next heading."""
    start = contributing.index(SECTION)
    return contributing[start:contributing.index("\n### ", start + 1)]


@pytest.fixture(scope="module")
def runs(section):
    """The runs table's rows, each a dict by the table's own headings."""
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    head = next(i for i, line in enumerate(lines) if line.startswith("| Level | Run |"))
    names = [cell.strip() for cell in lines[head].strip("|").split("|")]
    rows = []
    for line in lines[head + 2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(names):
            break
        rows.append(dict(zip(names, cells)))
    return rows


def _playbooks(skills):
    return {name for name in skills if name.startswith("run-")}


def _named(text, skills):
    """The skills a text names: a ticked name that is a skill's, said in prose or linked."""
    return ({name for name in TICKED.findall(text) if name in skills}
            | set(LINKED.findall(text)))


def test_every_skill_is_one_folder_deep_and_says_whose_it_is(skills):
    assert not sorted(path.name for path in SKILLS.iterdir() if not (path / "SKILL.md").is_file())
    for name, (front, _, _) in skills.items():
        assert front["name"] == name, name
        said = front["description"]
        # Unquoted, YAML cuts a description at " #"; quoted, an issue's number still reads as one
        # the skill is tied to, and the loop's places are named once, in CONTRIBUTING.
        assert said.startswith('"') and said.endswith('"') and "#" not in said, name
        assert said[1:].startswith(WHO), name
        assert said[1:].startswith("Playbook:") == name.startswith("run-"), name


def test_the_runs_table_and_the_playbooks_name_one_another(runs, skills):
    assert runs, "CONTRIBUTING's runs table was not found"
    named = set()
    for row in runs:
        books = LINKED.findall(row["Playbook"])
        assert books, row["Run"]
        for book, level in zip(books, re.split(r", then ", row["Level"].lower())):
            assert book in skills, f"{row['Run']}: no playbook {book}"
            assert book.startswith(f"run-{level}-"), f"{row['Run']}: {book} is not the {level}'s"
        named.update(books)
    assert named == _playbooks(skills)


def test_each_runs_mark_is_one_the_answer_workflow_knows_for_a_runs(runs):
    """A run writes as the maintainer's account: `answer.yml` tells its comments from theirs by
    the mark alone, so a mark it does not list would be read as the maintainer's own words."""
    workflow = (ROOT / ".github" / "workflows" / "answer.yml").read_text(encoding="utf-8")
    for row in runs:
        mark = row["Mark"].strip("`").removesuffix("·").strip()
        assert f'"{mark}"*' in workflow, mark


def test_every_skill_named_is_a_skill(skills, contributing):
    texts = {name: text for name, (_, _, text) in skills.items()}
    texts["CONTRIBUTING.md"] = contributing
    for guide in sorted((ROOT / "docs").glob("*.md")):
        texts[f"docs/{guide.name}"] = guide.read_text(encoding="utf-8")
    for where, text in texts.items():
        for name in set(SAID.findall(text)) | set(LINKED.findall(text)):
            assert name in skills, f"{where} names the skill {name}, and there is none"


def test_every_step_skill_is_named_from_above_and_none_names_a_run(skills, contributing):
    books = _playbooks(skills)
    # From above: CONTRIBUTING, and a guide that hands its own procedure to a skill.
    reached = _named(contributing, skills)
    for guide in sorted((ROOT / "docs").glob("*.md")):
        reached |= set(LINKED.findall(guide.read_text(encoding="utf-8")))
    for book in books:
        reached |= _named(skills[book][1], skills)
    # A skill reached only through another skill (the end line, written by `end-of-run`) counts.
    while True:
        more = set().union(*(_named(skills[name][1], skills) for name in reached)) - reached
        if not more:
            break
        reached |= more
    assert not sorted(set(skills) - reached), "skills nothing names"
    for name in sorted(set(skills) - books):
        text = skills[name][2]
        assert not sorted(book for book in books if book in text), f"{name} names a run"


def test_each_skill_cites_a_heading_that_is_there(skills, contributing):
    parts = set(re.findall(r"^\*\*([^*\n]+)\*\*$", contributing, re.M))
    parts |= set(re.findall(r"^#+ (.+)$", contributing, re.M))
    parts |= {part.split(",")[0] for part in parts}
    for name, (front, _, _) in skills.items():
        cited = CITED.findall(front["description"])
        assert cited, f"{name} cites no rule"
        for guide, headings in cited:
            if guide == "CONTRIBUTING.md":
                known = parts
            else:
                known = set(re.findall(r"^#+ (.+)$", (ROOT / guide).read_text(encoding="utf-8"),
                                       re.M))
            for heading in re.split(r", and |, ", headings):
                assert heading in known, f"{name} cites {guide}, {heading}"


def test_every_helper_agent_is_named_by_a_step_skill(skills):
    steps = "".join(text for name, (_, _, text) in skills.items() if not name.startswith("run-"))
    for agent in sorted(AGENTS.glob("*.md")):
        assert f".claude/agents/{agent.name}" in steps or f"`{agent.stem}`" in steps, agent.name
