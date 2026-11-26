"""The runs' pointers: CONTRIBUTING's runs table names a level's role book, a role book names step
skills, and a step skill names its helper agent. Each is a name written in one file about another,
so a renamed skill or a cut heading would leave a run following a pointer to nothing, and say
nothing. Pointers only go down: no step skill names a role book, and none names the loop's section
of CONTRIBUTING, since a step's rules are in its own skill. A rule has one home: no rule's lead is
written in two files."""
import re

import pytest

from harness import NO_CHECKOUT, ROOT

if ROOT is None:
    pytest.skip(NO_CHECKOUT, allow_module_level=True)

SKILLS = ROOT / ".claude" / "skills"
AGENTS = ROOT / ".claude" / "agents"
SECTION = "### The loop"
WHO = ("Any run:", "Any session:", "Coordinator:", "Builder:", "Role book:")
TICKED = re.compile(r"`([^`\n]+)`")
LINKED = re.compile(r"\]\((?:\.\./)?\.claude/skills/([^/)]+)/SKILL\.md\)")
SAID = re.compile(r"\bskills? `([^`\n]+)`")
CITED = re.compile(r"\(([\w/.-]+\.md), ([^()]+)\)")
#: The most words each kind of file may hold, its frontmatter and its links' addresses apart.
#: Every run reads the charter and its role book whole, and a step skill when its step comes: a
#: file that outgrows its budget is cut or split, or the budget is raised here with the reason
#: beside it. Words, not lines: a table's row is one line however long.
BUDGET = {"the charter": 2800, "a role book": 1350, "a step skill": 1250}
#: The copies of shared wording those files may hold between them, a pointer counted as one word.
SHARED_WORDING_HIGH_WATER = 190
#: Each model by its name in the runs table, with its name in a helper's frontmatter.
MODELS = {"Fable 5.2": "claude-fable-5-2", "Opus 5.5": "claude-opus-5-5",
          "Sonnet 5.5": "claude-sonnet-5-5", "Haiku 5.5": "claude-haiku-5-5"}
#: Each effort likewise: said in words there, and by its key here.
EFFORTS = {"low": "low", "medium": "medium", "high": "high", "extra high": "xhigh", "max": "max"}


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


def _books(skills):
    """The role books: a level's order of work, and its own rules."""
    return {name for name in skills if name.startswith("role-")}


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
        assert said[1:].startswith("Role book:") == name.startswith("role-"), name


def test_the_runs_table_names_each_levels_role_book_and_the_book_each_of_its_runs(runs, skills):
    """THE CASE THAT MAKES IT FAIL: the table gains a row that no book names, and the run it
    starts loads its level's book and finds no line for itself."""
    assert runs, "CONTRIBUTING's runs table was not found"
    named = set()
    for row in runs:
        books = LINKED.findall(row["Role book"])
        assert books == [f"role-{row['Level'].lower()}"], f"{row['Run']}: {books}"
        assert books[0] in skills, f"{row['Run']}: no role book {books[0]}"
        starts = re.findall(r"^\| ([^|]+) \|", skills[books[0]][1], re.M)
        assert row["Run"] in starts, f"{books[0]} has no line for the run {row['Run']}"
        named.update(books)
    assert named == _books(skills)
    for book in sorted(named):
        level = book.removeprefix("role-")
        listed = {start for start in re.findall(r"^\| ([^|]+) \|", skills[book][1], re.M)
                  if start not in ("Start", "---")}
        assert listed == {row["Run"] for row in runs if row["Level"].lower() == level}, book


def test_every_skill_named_is_a_skill(skills, contributing):
    texts = {name: text for name, (_, _, text) in skills.items()}
    texts["CONTRIBUTING.md"] = contributing
    for guide in sorted((ROOT / "docs").glob("*.md")):
        texts[f"docs/{guide.name}"] = guide.read_text(encoding="utf-8")
    for where, text in texts.items():
        for name in set(SAID.findall(text)) | set(LINKED.findall(text)):
            assert name in skills, f"{where} names the skill {name}, and there is none"


def test_every_step_skill_is_named_from_above_and_none_names_a_run(skills, contributing):
    books = _books(skills)
    # From above: CONTRIBUTING, and a guide that hands its own procedure to a skill. The loop's
    # guide is no such guide: its map names every skill, and no run reads it.
    reached = _named(contributing, skills)
    for guide in sorted((ROOT / "docs").glob("*.md")):
        if guide.name != "loop.md":
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
        assert not sorted(book for book in books if book in text), f"{name} names a role book"
        assert "quiet minute" not in " ".join(text.split()), f"{name} holds a run's wait"


def test_no_step_skill_points_back_up_at_the_loops_section(skills, contributing, section):
    """A skill holds its own rules, so a run can follow it when its step comes with nothing above
    it open. THE CASE THAT MAKES IT FAIL: every skill said "the rule is in CONTRIBUTING", so no run
    could skip the 538 lines of the section and trust the skill. A skill may still name a
    convention every change follows, by a heading of CONTRIBUTING outside the loop's section, and
    a heading it cites is there. So a skill names CONTRIBUTING only as a file in a list, as the
    conventions' home, or with such a heading straight after, "under Building" being none; and it
    names none of the section's parts as a place, in brackets or with "above", "below", "says" or
    "'s rule". A role book may name the runs table, which is the charter's."""
    parts = set(re.findall(r"^\*\*([^*\n]+)\*\*$", section, re.M))
    parts |= {part.split(",")[0] for part in parts}
    assert len(parts) >= 7, "the loop's parts were not found"
    headings = set(re.findall(r"^#+ (.+)$", contributing.replace(section, ""), re.M))
    mention = re.compile(r"CONTRIBUTING(?:\.md)?`?(?:\]\([^)]*\))?(?=(.{0,60}))")
    fine = re.compile(r"'s conventions\b|, `|(?:'s|,) (?:%s)(?!\w)"
                      % "|".join(re.escape(heading) for heading in headings))
    place = "|".join(re.escape(part) for part in sorted(parts, key=len, reverse=True))
    place = re.compile(rf"\((?:{place})[,)]|\b(?:{place})(?:, (?:above|below)| says|'s rule)")
    for name, (front, _, text) in skills.items():
        for guide, cited in CITED.findall(front["description"]):
            known = set(re.findall(r"^#+ (.+)$", (ROOT / guide).read_text(encoding="utf-8"), re.M))
            if guide == "CONTRIBUTING.md":
                known = headings
            for heading in re.split(r", and |, ", cited):
                assert heading in known, f"{name} cites {guide}, {heading}"
        flat = " ".join(text.split())
        assert not re.search(r"(?:, |\"|section |`)The loop\b", flat), \
            f"{name} names the loop's section"
        for after in mention.findall(flat):
            assert fine.match(after), \
                f"{name} names CONTRIBUTING with no heading outside the loop's section: {after!r}"
        assert not place.search(flat), f"{name} names a part: {place.search(flat).group()}"


def _leads(text):
    """The rules a text states: the bold words a bullet or a paragraph opens with, of four words
    or more, their line breaks gone."""
    found = re.findall(r"^(?:[-*] |\d+\. )?\*\*([^*]+)\*\*", text, re.M)
    return {" ".join(lead.split()).rstrip(".:,") for lead in found if len(lead.split()) >= 4}


def test_a_rule_has_one_home(skills, section):
    """A rule stated in two files is two rules the day one of them is changed. Each rule opens
    with its name in bold, and no name is written in the loop's section and a skill, or in two
    skills, a role book included. It holds the names alone:
    a rule said again in other words is for its reader to catch. THE CASE THAT MAKES IT FAIL: a
    rule moved into its step skill and left behind too."""
    homes = {}
    texts = {"CONTRIBUTING.md": section, **{name: body for name, (_, body, _) in skills.items()}}
    for where, text in texts.items():
        for lead in _leads(text):
            homes.setdefault(lead, []).append(where)
    twice = {lead: where for lead, where in homes.items() if len(where) > 1}
    assert not twice, f"stated in two places: {twice}"
    assert len(homes) >= 80, "the rules' names were not found"


def _words(text, names="keep"):
    """A text's words, lower case, as a run reads them: a link's address apart, its lines joined.
    With `names="one"`, each link and each ticked name of one word counts as the one word "name":
    a pointer to a skill, a file or a label is not wording, and naming one is how a rule is said
    once. A ticked form or command of several words is wording, and stays."""
    text = " ".join(text.split())
    if names == "one":
        text = re.sub(r"\[[^\]]*\]\([^)]*\)|`[^`\s]+`", " name ", text)
    return re.findall(r"[a-z0-9']+", re.sub(r"\]\([^)]*\)", "]", text).lower())


def test_each_file_a_run_reads_keeps_to_its_budget(skills, section):
    """THE CASE THAT MAKES IT FAIL: the loop's section grew a rule a surprise until it was 538
    lines, read whole by every run, and nothing said when it had become too long."""
    sizes = {"the charter": {"CONTRIBUTING.md, The loop": len(_words(section))},
             "a role book": {}, "a step skill": {}}
    for name, (_, body, _) in skills.items():
        kind = "a role book" if name.startswith("role-") else "a step skill"
        sizes[kind][name] = len(_words(body))
    over = {name: words for kind, files in sizes.items() for name, words in files.items()
            if words > BUDGET[kind]}
    assert not over, f"over its budget of words ({BUDGET}): {over}"


def test_the_charter_and_the_skills_share_no_more_wording_than_they_did(skills, section):
    """One home a rule is held by its lead alone, so a rule said again under another lead would
    pass. This counts the wording itself: each time an eight-word run stands in a file of the
    charter and the skills beyond its first, a link or a ticked name read as one word. THE CASE THAT MAKES IT FAIL: a second skill is given
    a copy of a rule to save its reader a step, and only one of the two is changed afterwards."""
    def runs_of(text):
        words = _words(text, names="one")
        return {" ".join(words[i:i + 8]) for i in range(len(words) - 7)}

    texts = {"the charter": section, **{name: body for name, (_, body, _) in skills.items()}}
    homes = {}
    for where, text in texts.items():
        for run in runs_of(text):
            homes.setdefault(run, []).append(where)
    by_files = {}
    for where in homes.values():
        if len(where) > 1:
            by_files[" + ".join(sorted(where))] = by_files.get(" + ".join(sorted(where)), 0) + 1
    copies = sum(len(where) - 1 for where in homes.values())
    assert copies <= SHARED_WORDING_HIGH_WATER, (
        f"{copies} copies of an eight-word run stand in a second file, above the "
        f"{SHARED_WORDING_HIGH_WATER} on file; say it once and name the skill, or raise this "
        f"with the reason beside it. Runs shared, by the files that share them: "
        f"{sorted(by_files.items(), key=lambda item: (-item[1], item[0]))}")


def test_each_routine_and_helper_runs_at_a_model_and_effort_the_tables_name(runs):
    """A routine's model and effort are set on claude.ai, where no test reads them: the runs table
    is what they are set to match, so it names both, and a routine's rows agree. A helper's are
    in its own file, and the loop's guide lists them for the maintainer. THE CASE THAT MAKES IT
    FAIL: a helper's file that names no effort, which then runs at whatever the session was
    given."""
    by_routine = {}
    for row in runs:
        assert row["Model"] in MODELS and row["Effort"] in EFFORTS, row["Run"]
        by_routine.setdefault(row["Routine"], set()).add((row["Model"], row["Effort"]))
    assert all(len(said) == 1 for said in by_routine.values()), by_routine
    guide = (ROOT / "docs" / "loop.md").read_text(encoding="utf-8")
    listed = {name: (model, effort) for name, model, effort in
              re.findall(r"^\s*\| `([\w-]+)` \|[^|]+\| ([^|]+?) \| ([^|]+?) \|$", guide, re.M)}
    agents = {}
    for agent in sorted(AGENTS.glob("*.md")):
        front = agent.read_text(encoding="utf-8").split("---\n", 2)[1]
        agents[agent.stem] = dict(line.split(": ", 1) for line in front.splitlines()
                                  if ": " in line)
    assert set(listed) == set(agents), "the guide's table lists each helper, and no other"
    for name, front in agents.items():
        model, effort = listed[name]
        assert model in MODELS and effort in EFFORTS, f"{name}: {model} at {effort}"
        assert front.get("model") == MODELS[model], f"{name}: {front.get('model')}, not {model}"
        assert front.get("effort") == EFFORTS[effort], \
            f"{name}: {front.get('effort')}, not {effort}"


def test_every_helper_agent_is_named_by_a_step_skill(skills):
    steps = "".join(text for name, (_, _, text) in skills.items() if not name.startswith("role-"))
    for agent in sorted(AGENTS.glob("*.md")):
        assert f".claude/agents/{agent.name}" in steps or f"`{agent.stem}`" in steps, agent.name


def test_a_fault_is_said_on_the_end_line_in_one_place_and_one_form(skills, section):
    """A run's fault can be counted only where every run says it in the same place: the rule, the
    skill that gives the end line's form and the skill that writes it all name the `Fault:` part,
    and it sits after the holds and before "Decided for you:" and `Next:`. THE CASE THAT MAKES IT
    FAIL: one fault stood on the run log three mornings, as loose words in what each run did, and
    nobody counted it."""
    def said(text, start, end):
        """One part of a text, from the words it starts with to `end`, its line breaks gone."""
        found = text.partition(start)[2].partition(end)[0]
        assert found, f"no part begins {start!r}"
        return " ".join(found.split())

    rule = said(section, "- **The loop's own work is not tracked here.**", "\n\n")
    assert "`Fault:`" in rule and "end line" in rule, "the rule sends a fault to the end line"
    beat, end = skills["beat"][1], skills["end-of-run"][1]
    shown = said(beat, "A run that met a fault says so next", "\n\n")
    parts = [shown.find(part) for part in ("· held ", "· Fault: ", "Decided for you:", "· Next:")]
    assert -1 not in parts and parts == sorted(parts), "holds, then faults, then what was decided"
    line = said(end, "## 2. The end line", "\n## ")
    assert -1 < line.find("--holds") < line.find("`Fault:`"), "the run writes it after the holds"
    assert "**Faults**" in said(end, "## 3. The debrief", "\n## "), "and its debrief says it"
    digest = said(end, "sends the day's digest", "\n- **")
    assert "Faults" in digest and "the number of runs that met it" in digest


def test_a_page_a_run_publishes_is_named_on_its_end_line(skills):
    """A routine runs outside the maintainer's project, so a page it publishes is missing from the
    project's list: the rule, the skill that gives the end line's form and the skill that writes
    it all name the `Page:` part, after "Decided for you:" and before `Next:`, and the debrief and
    the morning's digest list the pages. THE CASE THAT MAKES IT FAIL: two of the coordinator's
    pages, a design card's and a map a change asked for, stood outside the project, found only by
    their links on GitHub."""
    def said(text, start, end):
        """One part of a text, from the words it starts with to `end`, its line breaks gone."""
        found = text.partition(start)[2].partition(end)[0]
        assert found, f"no part begins {start!r}"
        return " ".join(found.split())

    beat, end = skills["beat"][1], skills["end-of-run"][1]
    rule = said(beat, "**A page a run publishes is named on its end line**", "\n\n")
    assert "`Page:`" in rule and "project" in rule, "the rule sends a page to the end line"
    shown = rule.partition(" as in ")[2]
    parts = [shown.find(part) for part in ("· Fault: ", "Decided for you:", "· Page: ", "· Next:")]
    assert -1 not in parts and parts == sorted(parts), "faults, what was decided, then pages"
    line = said(end, "## 2. The end line", "\n## ")
    assert -1 < line.find("`Fault:`") < line.find("`Page:`"), "the run writes it after the faults"
    assert "**Pages**" in said(end, "## 3. The debrief", "\n## "), "and its debrief lists it"
    digest = said(end, "sends the day's digest", "\n- **")
    assert "Pages" in digest and "holds and pages alone" in digest, "and so does the digest"
    assert "**Only the coordinator sends a debrief to the maintainer's phone" in end
    assert "`Page:`" in skills["design-card"][1], "the design card's page is named the same way"


def test_every_commit_is_reviewed_before_it_is_pushed(contributing):
    """The maintainer's rule: every commit's diff, by a run or a session, goes through
    the `code-review` skill before it is pushed. THE CASE THAT MAKES IT FAIL: a day of the loop's
    own rebuild merged unreviewed, since the only reviewer named was a run's, after the pull
    request opened. What is done with a finding goes by the severity the review gives it: the
    rule and the builder's skill both name the three, and the skill the one a skill takes. The
    rule holds the command that gives a cloud checkout's review its base. What the rule leaves is
    no find, and the builder's skill and the finds' skill both point at the rule for it. A
    Pre-existing finding judged wrong is said at the top, so the judgment can be read, and a
    cleanup takes a Nit's answer whatever severity it was given."""
    assert "Every commit's diff is reviewed by the `code-review` skill before it is pushed" \
        in contributing
    build = (SKILLS / "build-an-issue" / "SKILL.md").read_text(encoding="utf-8")
    assert build.index("`code-review`") < build.index("Run the guard"), "reviewed before it opens"
    rule = contributing.partition("- **Every commit's diff is reviewed")[2].partition("\n- **")[0]
    step = build.partition("## 6. The review")[2].partition("Run the guard")[0]
    for severity in ("Important", "Pre-existing", "Nit"):
        assert severity in rule and severity in step, f"a finding that is {severity}"
    assert "`fix-fold-report`" in step, "a Pre-existing finding is a find outside the change"
    finds = " ".join((SKILLS / "fix-fold-report" / "SKILL.md").read_text(encoding="utf-8").split())
    rule, step = " ".join(rule.split()), " ".join(step.split())
    assert "(the skill [`fix-fold-report`]" in rule and "is no find for that skill" in rule, \
        "what the rule leaves, and where a find outside the change goes"
    for skill in (step, finds):
        assert "Commits and pull requests, leaves" in skill, "both skills point at what it leaves"
    assert "judged wrong: then it is said at the top" in rule, \
        "a Pre-existing finding judged wrong leaves a trace"
    assert "a cleanup takes a Nit's" in rule, "a cleanup has one answer, whatever its severity"
    assert "`git remote set-head origin main`" in rule, "the review measures from today's main"
    assert "The review's rounds end at two" in rule, \
        "the review's rounds end at two, so a change does not go round for ever"
    assert "keeps a run's pull request from being clean" in rule, \
        "a finding said at the top has a reader, and a clean pull request carries none that stands"
    template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    assert "reviewed by the `code-review` skill" in template
    assert "`code-review` skill" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_nothing_set_aside_or_left_pending_is_lost(skills):
    """What a run puts off is given a home, an option declined says what brings it back, and what
    says it waits stops saying so once it does not. THE CASES THAT MAKE IT FAIL: work an issue set
    aside as a later step is filed by no run; an answer's options left out are never looked at
    again; a pull request's top still says "a draft until then" after it merged; and `ask-held`
    stays on what has closed."""
    def flat(text):
        return " ".join(text.split())

    finds = flat(skills["fix-fold-report"][1])
    assert "Work set aside for later is never left in prose" in finds
    assert "Revisit when" in finds and "`gate-review`" in finds
    assert "Work set aside has a home" in flat(skills["keep-the-queue"][1])
    for name in ("ask-or-decide", "record-answer", "gate-review"):
        assert "Revisit when" in skills[name][1], f"{name} keeps what brings an option back"
    merge = flat(skills["review-and-merge"][1])
    assert "Nothing is left saying it is pending once it is not" in merge
    assert "`<!-- state -->`" in merge and "`notify.yml` rewrites" in merge
    guide = flat((ROOT / "docs" / "loop.md").read_text(encoding="utf-8"))
    assert "loses it at once, and `planned` and `building` with it" in guide
