---
name: run-coordinator-replan
description: "Playbook: the coordinator's re-plan run, started by a run's Re-plan comment. It plans the issues marked for it and nothing else (CONTRIBUTING.md, How it runs)."
---

# The coordinator's re-plan run

Started by `replan.yml`, its starting text beginning "Re-plan only". The rules are in
`CONTRIBUTING.md`, The nightly agent.

1. **The start line**: the skill `beat`, saying it was started for a re-plan.
2. **Plan**, by the skill `plan`, only the issues under Next marked "Re-plan" since their last
   **Plan, checked**. Nothing else of the morning run is done.
3. **The end**: the skill `end-of-run`. Its debrief is a line an issue.
