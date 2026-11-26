---
name: run-coordinator-replan
description: "Playbook: the coordinator's re-plan run, started by a run's Re-plan comment or the maintainer's Resume. It plans the issues marked for it and nothing else (CONTRIBUTING.md, How it runs)."
---

# The coordinator's re-plan run

Started by the gate, ten quiet minutes after a run's last "Re-plan:" or the maintainer's
`Resume:`, with a text that begins "Re-plan:". The plan's rules are in the skill named; the rules
every run works by are in `CONTRIBUTING.md`, The loop.

1. **The start line**: the skill `beat`, saying it was started for a re-plan, or by a `Resume:`.
2. **All else that waits**: a start within another's quiet minutes takes its place
   (`CONTRIBUTING.md`, When a run starts), so an answer or a `Change:` not recorded, a release
   and an open `Idea:` that wait are taken first, each by the middle steps of its own playbook:
   `run-coordinator-answer`, `run-coordinator-release`, `run-coordinator-idea`. After a pause
   that is all that came in while the loop was paused.
3. **Plan**, by the skill `plan`, only the issues under Next marked "Re-plan" since their last
   **Plan, checked**, and an issue the maintainer resumed whose plan no longer stands. Nothing
   else of the morning run is done.
4. **The end**: the skill `end-of-run`. Its debrief is a line an issue. It goes to the
   maintainer's phone only when their `Resume:` started the run.
