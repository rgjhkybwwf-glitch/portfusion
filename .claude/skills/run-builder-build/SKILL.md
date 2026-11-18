---
name: run-builder-build
description: "Playbook: a builder's run, by night or after an answer. It tends the agent's open pull requests, builds planned issues up to its cap, and takes each pull request to its end (CONTRIBUTING.md, How it runs)."
---

# A builder's run

The order of the run's work. Each step's procedure is in the skill named; the rules are in
`CONTRIBUTING.md`, The nightly agent. A builder never writes a plan.

1. **The start line**: the skill `beat`. A run that follows the answer run's first half has
   written it already.
2. **After a tag**: the skill `open-milestone` if the Queue's lines are not yet moved, then the
   next version's pull request (the skill `release`, After the tag).
3. **Its own open pull requests first**: the skill `tend-pull-requests`.
4. **Take a line**: the first under Next whose issue carries `planned` and neither `decision` nor
   `building`, has no open pull request of its own, and whose "waits" are all closed. Skip the
   rest, and never reorder. **Started by an answer**, take only the answered issues under Next
   whose plan still stands, in the Queue's order, and no other line.
5. **Build it**: the skill `build-an-issue`.
6. **Take its pull request to its end**: the skill `review-and-merge`.
7. **Again from step 4**, up to the cap.
8. **No line it can build and nothing to tend: stop**, posting nothing on GitHub but its lines in
   the run log. The debrief names each line under Next and what holds it.
9. **The end**: the skill `end-of-run`.

Every choice on the way goes through the skill `ask-or-decide`, and every find outside the change
through `fix-fold-report`.
