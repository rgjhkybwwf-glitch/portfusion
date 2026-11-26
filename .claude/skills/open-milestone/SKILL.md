---
name: open-milestone
description: "Coordinator: after a release is tagged and its milestone closed, moves the next milestone's lines in the Queue to Next."
---

# Opening the next milestone

**After the tag, the next milestone opens.** The gate starts the coordinator's release run ten
quiet minutes after the maintainer publishes the release, at any hour. Finding the release tagged
and its milestone closed, it moves the Queue's lines from after the gate to Next and plans the
first of them, so the next build has a plan; a builder opens the next version (the skill
`release`). A run that finds the milestone still open says so and moves nothing, and the next
morning run does it.

A run that finds the release tagged and its milestone closed does this first:

1. Read the Queue afresh.
2. Move the lines under the heading for after the gate to Next, in the order answered, the
   release checklist last.
3. Clear each "waits" already met.
4. An issue still open in the closed milestone is moved to the next one, its line with it, and
   the debrief says which and why: a closed milestone holds none open.

The lines then take their plans in order (the skill `plan`). The next version's own pull request
is a builder's (the skill `release`, After the tag).
