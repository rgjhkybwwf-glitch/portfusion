---
name: pictures
description: "Builder: retakes the walk's pictures when CI's walk fails only because a page the issue meant to change looks different."
---

# Retaking the pictures

A CI failure on the agent's pull request is the agent's to fix, waited for in the foreground (the
skill `review-and-merge`). **The pictures are the agent's to keep**, compared on Linux alone; the
maintainer never takes them, and reads them only for a feature's last slice.

When the walk fails only because a page the issue meant to change looks different:

1. Label the pull request `baselines`, its description's `Pictures:` line naming the plan's pages.
2. A workflow (`baselines.yml`) retakes those pages' Linux pictures onto a branch beside it,
   `baselines/<branch>`. A page whose picture changed and is not named fails the retake, by name:
   the change moved a page its plan did not, which is a fault to find, not a picture to add.
3. The workflow takes the label off as it starts, so a retake not landed ten minutes after the
   label is asked for again by putting it back on.
4. Merge `baselines/<branch>` in, review it as `CONTRIBUTING.md`, Commits and pull requests,
   says, and push, which runs the guard.

The retake leaves no comment. What it did, or why it refused, is its `push` job's result, that
job's log and the run's summary.
