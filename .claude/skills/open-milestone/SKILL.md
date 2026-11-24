---
name: open-milestone
description: "Coordinator: after a release is tagged and its milestone closed, moves the next milestone's lines in the Queue to Next (CONTRIBUTING.md, Which issues)."
---

# Opening the next milestone

The rule is in `CONTRIBUTING.md`, The loop, Which issues, in what order: after the tag,
the next milestone opens.

A run that finds the release tagged and its milestone closed does this first:

1. Read the Queue afresh.
2. Move the lines under the heading for after the gate to Next, in the order answered, the
   release checklist last.
3. Clear each "waits" already met.
4. An issue still open in the closed milestone is moved to the next one, its line with it, and
   the debrief says which and why: a closed milestone holds none open.

The lines then take their plans in order (the skill `plan`). The next version's own pull request
is a builder's (the skill `release`, After the tag).
