---
name: role-coordinator
description: "Role book: every run of the coordinator's. It holds the one order the coordinator's work follows, which parts of it each start takes (the morning's clock, an answer, an idea, a release, a re-plan, a top-up), and the rules of the level."
---

# The coordinator's book

A coordinator's run follows this book from its start line to its debrief. Its row of the runs
table says what started it, its mark and its cap, and the brief says which row it is (the skill
`beat`). Each part's rules and its procedure are in the skill named, opened when the part comes.
The coordinator writes no code, opens no branch and builds nothing.

## The level's rules

- **A run the gate starts takes all that waits**: an answer or a `Change:` not yet recorded, a
  release whose lines are not moved, an open `Idea:` not shaped, a "Re-plan" not planned, a
  place a merge left empty. A start
  within another's quiet minutes takes its place, so the run its text names may not be the only
  one owed. After a pause that is all that came in while the loop was paused.
- **One long job, at most, a run**, after its plans: the first that is due of those part 11
  names, in its order. The rest wait for the next run, and its debrief says which.
- **Whatever it files or shapes takes its place** by the skill `place-an-issue`, and every choice
  goes through `ask-or-decide`.

## The order

A run works the parts it takes in this order, and no part twice. A release is the one
exception, and the table says so.

1. **The start line**: the skill `beat`, saying what started the run: the morning run, an
   answer, an idea, a release with its tag, a re-plan, a top-up, or a `Resume:`.
2. **Read the direction**: `docs/direction.md` first, cited for a milestone, a cut or an idea,
   and `docs/content-map.md` beside it, cited for a design card and for a plan that changes which
   page or section answers a job.
3. **Read what changed since the last run**: the pull requests merged or stopped, the pull
   requests still open (a planned issue with a ready one holds no place: the skill `plan`), each
   run's comments on the issues, every answer and `Change:` the maintainer gave, each "Re-plan"
   left, every other comment of the maintainer's, and each run of the workflow `start` that
   failed: a start the gate did not make, named in the digest. The last run began at the start on
   this run's own last line in the run log, whose lines are never acted on, or three days ago
   when there is none. Clear a `building` label more than three hours old: a run that long has
   died.
4. **Nothing changed: stop.** When nothing has merged, closed, been answered, changed or filed
   since, as many plans hold a place as the cap or no line under Next or in Upkeep could be planned
   (the skill `plan`), and no review of the Queue is due, go to the last part with a one-line
   debrief; where this run met a fault, or an end line since its last names one, the Faults head
   comes before that line, and the Pages head likewise for a page (the skill `end-of-run`).
5. **Record** every answer and `Change:` not yet recorded, before anything is built: the skill
   `record-answer`. With it, a `Change:` on the Queue is applied by the skill `keep-the-queue`,
   and an answered gate review by the skill `gate-review`, Applying its answer. Any other comment
   of the maintainer's is applied where its issue is shaped or planned, and otherwise named in
   the debrief.
6. **The Queue**: the skill `keep-the-queue`, Each run: tick what merged, and sort what the
   builders reported.
7. **After a tag**: the skill `open-milestone`. A run that finds the release's milestone still
   open says so in the debrief and moves nothing.
8. **Each open `Idea:` issue**, the oldest first: the skill `shape-an-issue`, then its place by
   `place-an-issue` and its questions by `ask-or-decide`, asked as it is shaped. An idea an open
   issue already covers is added to that issue and closed.
9. **The dependencies**: the skill `dependencies`.
10. **Plan**: the skill `plan`. First each issue under Next or in Upkeep marked "Re-plan" since its
    last **Plan, checked**, and an issue the maintainer resumed whose plan no longer stands; then
    the lines under Next, in order, to the cap; then Upkeep, for a place Next leaves empty.
11. **One long job, at most**: the skill `gate-review` on the day the gate is reached; else
    `keep-the-queue`, The review, on a Monday or a Thursday; else `design-card`, or
    `slice-a-feature` for a feature whose shape is decided.
12. **The marks**: what no longer stands is marked "Re-plan:", and what a builder may build is
    marked "Build:", both as `record-answer` says. The gate starts the next run from each.
13. **The end**: the skill `end-of-run`.

## Which parts a start takes

The run's row is named by the first words of the text it was started with, or by its clock.
Every start takes the start line and the end; the table names the rest, and the first rule
under it the parts a waiting start brings with it.

| Start | Its text begins | The parts it takes | Its debrief |
|---|---|---|---|
| Morning | nothing: its routine's clock | every part | the day's digest |
| Answer | `Answer:` | 5, 6 and 12, and of 7, 8 and 10 what waits | its own |
| Idea | `Idea:` | 2 and 8, and of 5, 6, 7 and 10 what waits | its own: for each idea, the issue it became, where it was placed and why, and what is asked |
| Release | `Release:` and the tag | 7 before 6, then 10 to the cap, and of 5 and 8 what waits | its own |
| Re-plan | `Re-plan:` | 10, and of 5, 6, 7 and 8 what waits | its own: a line an issue |
| Top-up | `Top-up:` | 6, then 10 to the cap, and of 5, 7 and 8 what waits | its own: a line a plan |

- **Of a part taken only for what waits**, a run does what the start that waits would have
  done: an answer is recorded, the Queue kept and the marks left (5, 6 and 12); a release's
  lines are moved, the Queue kept, and its first lines planned to the cap of the runs table's
  Release row (7, 6 and 10); an idea is shaped (2 and 8); an issue marked "Re-plan", or
  resumed, is planned (10); and where a line under Next merged since the coordinator's last run,
  it is ticked and the lines planned to the cap of the Top-up row (6 and 10).
- **Only the morning run, a top-up, and a run that moves a release's lines, plan to a cap.** In
  any other run only what is marked "Re-plan" or resumed is planned, beside a top-up that waits:
  a shaped idea takes its plan when its line is reached, and an answered issue is marked for a
  re-plan or for a builder.
- **A release's lines are moved before the Queue is kept**, 7 before 6, in a release run and in
  a run that takes a waiting release and has not yet kept the Queue; the morning run works the
  two as numbered. A run that finds the release's milestone still open moves nothing and plans
  nothing for it, and the next morning run opens it; what else waits is still taken.
- **The next version's own pull request is a builder's** (the skill `release`, After the tag).
- **An idea is never placed in the milestone being worked** by the run that shapes it: that is
  the maintainer's to do.
- **Only the morning run takes 3, 4, 9 and 11.**
- **Which debriefs also go to the maintainer's phone** is in the skill `end-of-run`: the digest,
  and that of a run the maintainer started.
