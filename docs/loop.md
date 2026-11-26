# The loop's machinery

What works round the loop's runs, for the maintainer: the routines that carry them, the start gate
that starts them, the bot that asks, and the Stop hook that holds a run to its turn. The rules a
run works by are the loop's charter ([`CONTRIBUTING.md`](../CONTRIBUTING.md), The loop), its
level's role book and its steps' skills; this guide says how the machinery carries them, and
where each rule is kept. No run needs it, and no run changes it.

## The routines

- **A routine carries each level's runs**, and the runs table names it. Each routine is in the
  personal cloud environment "PortFusion", whose setup script builds the venv on Python 3.13 and
  installs `tools/`. A routine's prompt names the loop's section and its level; its schedule,
  model and effort are set on claude.ai to match the table, and nothing else is kept there.
- **A helper agent runs at the model and effort its own file names**, under
  [`.claude/agents/`](../.claude/agents), each chosen for its job: a helper that reasons about
  the code takes more than one that walks a page. `test_runs.py` holds this table to the files.

  | Helper | Its job | Model | Effort |
  |---|---|---|---|
  | `plan-drafter` | drafts an issue's plan from the code | Fable 5.2 | high |
  | `plan-checker` | checks a plan against the code | Opus 5.5 | high |
  | `skeptic-reviewer` | reviews a pull request it did not build | Fable 5.2 | high |
  | `wide-reader` | reads every open issue, and returns a short list | Opus 5.5 | medium |
  | `cold-walker` | walks a changed desk page cold | Sonnet 5.5 | medium |
  | `trial-walker` | walks a whole feature by its Trial jobs | Sonnet 5.5 | medium |

## When a run starts

- **The start gate starts every run its routine's clock does not** (`start.yml`; `tools/starts.py`
  holds its table, the rows of the runs table). A run cannot start another, so the gate does: it sees the
  maintainer's words, a release, a run's own line and a merge that closes a planned issue, and
  fires the routine of the level that takes it. It keeps no clock: GitHub runs a workflow's clock hours late, so a run a clock starts
  is started by its routine's. Nothing of a comment is sent: a run is told what started it last,
  and finds the rest itself.
- **Quiet minutes, and one wait a level.** A start waits its row's minutes, counted from the last
  start of its level: another within them takes the wait's place, so what comes together makes
  one run. So a coordinator's run the gate starts takes all that waits, as its role book
  says. **One run of a level at a time**: while the run log shows
  a run of that level at work, its start line with no end line yet, the start waits for it to end,
  for up to three hours. A run its routine's clock starts waits for no other, so it can run
  beside one the gate started; `building` keeps two builders off one issue. A release's ten
  minutes are for the milestone's close, which follows the tag.
- **The maintainer's day is 08:00 to 17:00 UK time, Monday to Friday.** What the maintainer
  starts, by an answer, a `Change:`, an `Idea:`, a release or a `Resume:`, starts at any hour, and
  a run's own line ("Build:", "Re-plan:") carries on what its run began; a merge is the
  maintainer's press or a builder's own, and its top-up follows it at any hour. No clock starts a run
  inside the day: the routines' are set outside it, and `test_starts.py` holds the runs table's
  hours to that. The bot asks only inside the day (Telling the maintainer, below).
- **The maintainer's answers start the answer run, in a batch.** The gate sees the owner's comment on an
  issue that begins `Q1:` or `All as recommended`, whatever its labels, or one that begins
  `Change:` on an issue or an agent's pull request, and starts the coordinator's answer run
  thirty quiet minutes after the last, so answers given together make one run. Nothing of a
  comment is passed, and the issue it names is only the last.
- **A re-plan starts the coordinator at once, by its comment.** A comment whose first line after
  the run's name is "Re-plan:" is all it takes: the gate sees it and, ten quiet minutes after the
  last, starts the re-plan run, so the plan is ready for the next build. No run starts a routine
  itself.
- **A merge tops the plans up.** A line that was built closes when its pull request merges, still
  carrying `planned`. The gate sees an issue close so, as done, and ten quiet minutes after the
  last starts the coordinator's top-up run, which ticks the line and plans to the cap. So the
  line that waited on the merge has its plan before the next build, and a place freed in the day
  is filled that day. An issue closed for any other reason, or with no plan, starts nothing.
- **Three builds a working day, each by a routine's clock of its own**: 18:30, 21:30 and 00:30.
  A run tells its row by the hour, so a level's clocks stand three hours apart or more. A build
  still at work when the next begins is not waited for: `building` keeps the second off its
  issue and off its pull request.
- **A start that fails is said.** The gate prints the routine's HTTP status alone, never the
  session's address, and fails its own workflow run; the next morning run names it in its digest.
  Each level's address and token are the repository's secrets, which `start.yml` names; without
  them the gate says so in its log and starts nothing.

`Hold:`, `Resume:` and a pause are the charter's, under the same name there: each is a rule a run
works by.

## Telling the maintainer

- **A question or pull request reaches the maintainer as a mention**: the agent works as the
  maintainer's account, so GitHub would tell them nothing; an issue labelled `decision`, and a pull
  request from a branch whose name begins claude/ that waits for a yes, get a comment from
  `github-actions[bot]`, headed "PortFusion agent", that names them (`notify.yml`).
- **The bot asks in the maintainer's working day, and holds the rest to 08:00.** A question or a
  pull request raised outside 08:00 to 17:00 UK time, Monday to Friday, takes the label
  `ask-held`, which tells no one; at 08:00 on the next working day the bot asks each that still
  waits, and takes the label off. An issue or pull request that closes loses it at once, and
  `planned` and `building` with it (`notify.yml`).
  A run the maintainer started tells them itself, in its debrief, at any hour.
- **The bot comments only to ask, or when it turned auto-merge off.** Every issue and pull request
  is under the maintainer's account, so GitHub tells them of each comment the bot makes, whether
  it names them or not. A note that asks nothing (a pull request merging itself, a tier that
  holds, the pictures retaken) is written in its workflow run's summary, where a run reads it.

## The Stop hook

- **The Stop hook holds a run to its turn** (`tools/stop_hook.py`, run by `.claude/settings.json`): a run
  cannot end while an open pull request of a branch it pushed has `guard` running, nor while a
  helper agent it started has not returned, each for up to an hour a wait, nor, asked twice, with a
  last message whose last line does not begin `Next:`, a one-line ending included. It holds only a
  session started by a routine's prompt, which names the loop's section, never one with the maintainer;
  it reads the section's name from the heading the runs table is under, so a new run needs no
  change to it. **Each hold is logged, and the run's end line says it**, as in "held 1× for
  `guard`, 12 min": the hook writes it in a file in the session, and
  `python3 tools/stop_hook.py --holds` prints it (the skill `end-of-run`).

## Where each rule is

A rule has one home, and `test_runs.py` holds that: the charter, a role book or one step skill.
It holds their size too: the charter, a role book and a step skill each have a budget of words,
and the wording the files share has a ceiling.

| The rule | Its home |
|---|---|
| the two levels, the runs table, the four issues, the labels, a cap, a dry run | the charter, How it runs |
| `Hold:`, `Resume:`, a pause | the charter, When a run starts |
| the Queue's order, whose words count, what an answer is | the charter |
| `building`, the tiers, a ping, a run's one turn, how a run signs what it writes, Never | the charter |
| the coordinator's order, what each start takes, one long job a run | [`role-coordinator`](../.claude/skills/role-coordinator/SKILL.md) |
| a builder's order, the line it takes, when it stops | [`role-builder`](../.claude/skills/role-builder/SKILL.md) |
| the run's brief, its two lines on the run log, a page it publishes | [`beat`](../.claude/skills/beat/SKILL.md) |
| the Definition of Ready, "covers", an `Idea:` | [`shape-an-issue`](../.claude/skills/shape-an-issue/SKILL.md) |
| an issue's place, a milestone that only gets shorter | [`place-an-issue`](../.claude/skills/place-an-issue/SKILL.md) |
| the milestone being worked, the Queue kept current, its review on Monday and Thursday | [`keep-the-queue`](../.claude/skills/keep-the-queue/SKILL.md) |
| the gate, its review, the trial, keep or pull | [`gate-review`](../.claude/skills/gate-review/SKILL.md) |
| the next milestone after a tag | [`open-milestone`](../.claude/skills/open-milestone/SKILL.md) |
| the test for asking, how and when a question is asked, five open at most | [`ask-or-decide`](../.claude/skills/ask-or-decide/SKILL.md) |
| how an answer is recorded, what a `Change:` does, "Re-plan:" and "Build:" | [`record-answer`](../.claude/skills/record-answer/SKILL.md) |
| a plan, checked, and when it stands | [`plan`](../.claude/skills/plan/SKILL.md) |
| a feature's design card | [`design-card`](../.claude/skills/design-card/SKILL.md) |
| a feature's slices, hidden until the last | [`slice-a-feature`](../.claude/skills/slice-a-feature/SKILL.md) |
| the dependencies | [`dependencies`](../.claude/skills/dependencies/SKILL.md) |
| a builder's own pull requests first | [`tend-pull-requests`](../.claude/skills/tend-pull-requests/SKILL.md) |
| one issue, one branch, one pull request; a commit never rewritten; the second attempt | [`build-an-issue`](../.claude/skills/build-an-issue/SKILL.md) |
| a find outside the change, work set aside | [`fix-fold-report`](../.claude/skills/fix-fold-report/SKILL.md) |
| the reviewer, `guard` green, clean or waiting, the three never clean | [`review-and-merge`](../.claude/skills/review-and-merge/SKILL.md) |
| the walk's pictures | [`pictures`](../.claude/skills/pictures/SKILL.md) |
| the release, its tag and the next version | [`release`](../.claude/skills/release/SKILL.md), [`release-read`](../.claude/skills/release-read/SKILL.md) |
| the last three steps, the debrief, `Next:`, the phone | [`end-of-run`](../.claude/skills/end-of-run/SKILL.md) |
