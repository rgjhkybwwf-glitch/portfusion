---
name: run-coordinator-release
description: "Playbook: the coordinator's release run, started when the maintainer publishes a release. It opens the next milestone in the Queue and plans its first lines, so the next build has a plan (CONTRIBUTING.md, How it runs)."
---

# The coordinator's release run

Started by the gate, ten quiet minutes after the maintainer publishes a release, at any hour,
with a text that begins "Release:" and names the tag. The ten minutes are for the milestone's
close, which follows the tag. The rules are in `CONTRIBUTING.md`, The nightly agent, Which
issues, in what order.

1. **The start line**: the skill `beat`, saying it was started by the release, with its tag.
2. **All else that waits**: a start within another's quiet minutes takes its place
   (`CONTRIBUTING.md`, When a run starts), so an answer or a `Change:` not recorded is taken
   first, by the middle steps of `run-coordinator-answer`.
3. **The milestone**: when the release's milestone is still open, say so in the debrief, move
   nothing, and go to the last step: the next morning run opens it.
4. **Open the next milestone**: the skill `open-milestone`.
5. **The Queue**: the skill `keep-the-queue`, Each run.
6. **Plan** the first lines under Next, in order, to the cap: the skill `plan`.
7. **The end**: the skill `end-of-run`. Its debrief goes to the maintainer's phone: they started
   this run.

The next version's own pull request is a builder's, before its first build (the skill `release`,
After the tag). Nothing is built in this run.
