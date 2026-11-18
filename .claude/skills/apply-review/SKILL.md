---
name: apply-review
description: Applies an answered Queue review or gate review on #206, making the changes it answered (CONTRIBUTING.md, The answer run). A review is applied, never built.
---

# Applying an answered review

The rule is in `CONTRIBUTING.md`, The nightly agent, The answer run.

## A Queue review

The run makes the answered changes: the Queue's lines, a "waits", an issue merged or closed with
the reason, a find's place noted on #220. Then it takes `decision` off #206.

## A gate review

As for a Queue review, and it also:

1. moves issues between milestones;
2. writes the next milestone's lines, in the order answered, under the Queue's heading for after
   the gate;
3. files the issue for a pull (Features);
4. edits `docs/direction.md` to the answer in a pull request that links #206 and may merge itself
   once `guard` is green, the answer being its yes.

Then it takes `decision` off #206, leaves a comment on the checklist (#156) whose first line after
its name is "Re-plan: the gate review for <milestone> is answered", and takes `planned` off it.

Then the run goes on.
