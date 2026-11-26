---
name: run-coordinator-answer
description: "Playbook: the coordinator's answer run, started by the maintainer's answer or Change. It records each one, applies a Change on the Queue and an answered gate review, and marks what a builder may now build (CONTRIBUTING.md, How it runs)."
---

# The coordinator's answer run

Started by the gate, thirty quiet minutes after the maintainer's last answer or `Change:`, with a
text that begins "Answer:". Nothing of a comment is passed to the run: it finds the answers
itself. Each step's rules are in the skill named; what starts the run is in `CONTRIBUTING.md`, The
loop, The answer run. The coordinator builds nothing.

1. **The start line**: the skill `beat`, saying it was started by an answer.
2. **Find and record** every answer and `Change:`, before anything is built: the skill
   `record-answer`.
3. **The Queue**: the skill `keep-the-queue`, Each run, and A `Change:` on the Queue.
4. **An answered gate review**: the skill `gate-review`, Applying its answer.
5. **All else that waits**: a start within another's quiet minutes takes its place
   (`CONTRIBUTING.md`, When a run starts), so a release, an open `Idea:` and a "Re-plan" that
   wait are taken now, each by the middle steps of its own playbook: `run-coordinator-release`,
   `run-coordinator-idea`, `run-coordinator-replan`.
6. **What no longer stands** is marked "Re-plan:", and **what a builder may build** is marked
   "Build:", both as `record-answer` says. The gate starts the next run from each.
7. **The end**: the skill `end-of-run`. Its debrief goes to the maintainer's phone: they started
   this run.

An issue not under Next, a feature, and the issue a design card was answered on are recorded and
left there: nothing of them is built.
