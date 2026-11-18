---
name: run-coordinator-answer
description: "Playbook: the coordinator's answer run, started by the maintainer's answer or Change. It records each one, applies a Change on the Queue and an answered gate review, before anything is built (CONTRIBUTING.md, How it runs)."
---

# The coordinator's answer run

Started by `answer.yml`, thirty quiet minutes after the maintainer's last answer or `Change:`.
Nothing of a comment is passed to the run: it finds the answers itself. The rules are in
`CONTRIBUTING.md`, The nightly agent, Asking and answering, and The answer run.

1. **The start line**: the skill `beat`, saying it was started by an answer.
2. **Find and record** every answer and `Change:`, before anything is built: the skill
   `record-answer`.
3. **The Queue**: the skill `keep-the-queue`, Each run, and A `Change:` on the Queue.
4. **An answered gate review**: the skill `gate-review`, Applying its answer.
5. **What no longer stands** is marked "Re-plan:", as `record-answer` says, and left: the re-plan
   run plans it.
6. **Then the build**: the answered issues under Next whose plan still stands go to the playbook
   `run-builder-build`, in the same run while the runs table gives the answer run both.
7. **The end**: the skill `end-of-run`, once, after the build.

An issue not under Next, a feature, and the issue a design card was answered on are recorded and
left there: nothing of them is built.
