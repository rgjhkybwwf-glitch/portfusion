---
name: run-coordinator-morning
description: "Playbook: the coordinator's morning run. It reads what changed, records, shapes, plans the lines under Next, then takes one long job (CONTRIBUTING.md, How it runs)."
---

# The coordinator's morning run

The order of the run's work. Each step's procedure is in the skill named; the rules are in
`CONTRIBUTING.md`, The loop. The coordinator writes no code and opens no branch.

1. **The start line**: the skill `beat`.
2. **Read the direction**: `docs/direction.md` first, cited for a milestone, a cut or an idea, and
   `docs/content-map.md` beside it, cited for a design card and for a plan that changes which page
   or section answers a job.
3. **Read what changed since the last run**: the pull requests merged or stopped, each run's
   comments on the issues, every answer and `Change:` the maintainer gave, each "Re-plan" left,
   every other comment of the maintainer's, and each run of the workflow `start` that failed: a
   start the gate did not make, named in the digest. The last run began at the start on this run's own
   last line in the run log, whose lines are never acted on, or three days ago when there is none.
   Clear a `building` label more than three hours old: a run that long has died.
4. **Nothing changed: stop.** When nothing has merged, closed, been answered, changed or filed
   since, Next holds as many `planned` lines as the cap or no line that could be planned, and no
   review of the Queue is due, go to the last step with a one-line debrief; where this run met
   a fault, or an end line since its last names one, the Faults head comes before that line (the
   skill `end-of-run`).
5. **Record**: the skill `record-answer`, for each answer or `Change:` not yet recorded. Any other
   comment of the maintainer's is applied where its issue is shaped or planned, and otherwise
   named in the debrief.
6. **The Queue**: the skill `keep-the-queue`, Each run: tick what merged, and sort what the
   builders reported.
7. **After a tag**: the skill `open-milestone`.
8. **Each open `Idea:` issue**: the skill `shape-an-issue`.
9. **The dependencies**: the skill `dependencies`.
10. **Plan** the lines under Next, in order, to the cap: the skill `plan`.
11. **One long job, at most**: the skill `gate-review` on the day the gate is reached; else
    `keep-the-queue`, The review, on a Monday or a Thursday; else `design-card`, or `slice-a-feature` for a feature
    whose shape is decided. The rest wait for the next run, and the debrief says which.
12. **The end**: the skill `end-of-run`.

Whatever it files or shapes on the way takes its place by the skill `place-an-issue`, and every
choice goes through `ask-or-decide`.
