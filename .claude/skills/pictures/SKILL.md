---
name: pictures
description: Retakes the walk's pictures when CI's walk fails only because a page the issue meant to change looks different (CONTRIBUTING.md, Building).
---

# Retaking the pictures

The rule is in `CONTRIBUTING.md`, The nightly agent, Building: a CI failure on the agent's pull
request is the agent's to fix, waited for in the foreground.

When the walk fails only because a page the issue meant to change looks different:

1. Label the pull request `baselines`, its description's `Pictures:` line naming the plan's pages.
2. A workflow (`baselines.yml`) retakes those pages' Linux pictures onto a branch beside it,
   `baselines/<branch>`. A page whose picture changed and is not named fails the retake, by name:
   the change moved a page its plan did not, which is a fault to find, not a picture to add.
3. The workflow takes the label off as it starts, so a retake not landed ten minutes after the
   label is asked for again by putting it back on.
4. Merge `baselines/<branch>` in and push, which runs the guard.

The pictures are compared on Linux alone.
