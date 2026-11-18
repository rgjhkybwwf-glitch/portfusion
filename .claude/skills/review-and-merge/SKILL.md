---
name: review-and-merge
description: "Builder: takes an open pull request to its end. The skeptic reviewer reads it, the guard is waited for, and it merges itself or says what waits for the maintainer (CONTRIBUTING.md, Merging)."
---

# Review and merge

The tiers, what makes a pull request clean and the three that never are, are in `CONTRIBUTING.md`,
The nightly agent, Merging.

## 1. The reviewer

For a pull request of tier 1 or above: the skeptic reviewer
([`.claude/agents/skeptic-reviewer.md`](../../agents/skeptic-reviewer.md)), given only the issue's
"Done" checks and the diff, reviews it. Its findings are fixed, or said at the top of the pull
request. Tier 0 takes the builder's own review of its diff, and no walk.

## 2. Clean, or waiting

- **Clean**: turn auto-merge on as the pull request opens. GitHub merges it once `guard` is green.
- **Not clean**: leave auto-merge off, with what is needed from the maintainer at the top of the
  description. A pull request that moves the store or a figure says what moves there, and in the
  changelog. `tiers.yml` turns auto-merge off for tier 3 and for a moved headline figure; the
  agent never turns it on again.

## 3. The guard

Wait for CI's `guard` on the newest commit, in the foreground: a command that polls the checks,
and the `baselines/<branch>` ref when pictures are being retaken, run again until they finish.
Never by ending the turn.

- **A failure** is the agent's to fix, in a new commit.
- **The walk fails only because a page the issue meant to change looks different**: the skill
  `pictures`.
- **A failure the agent cannot fix** is said at the top of the pull request, with what would fix
  it.

## 4. After it merges

Tick the issue's line in the Queue and move it to Done, reading the Queue afresh just before the
edit. A run that finds one of the agent's pull requests merged since, by the maintainer's hand,
ticks its line the same way.

The agent goes on to the next issue without waiting for a merge that waits on the maintainer.
