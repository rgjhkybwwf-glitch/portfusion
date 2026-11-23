---
name: review-and-merge
description: "Builder: takes an open pull request to its end. The skeptic reviewer reads it, the guard is waited for, and it merges itself or says what waits for the maintainer (CONTRIBUTING.md, Merging)."
---

# Review and merge

The tiers, what makes a pull request clean and the three that never are, are in `CONTRIBUTING.md`,
The loop, Merging.

The pull request is a draft until its end (the skill `build-an-issue` opens it so): nothing can
merge it, and `notify.yml` asks nothing of it, while it is read and its guard runs. Auto-merge is
the last thing done, never the first.

## 1. The reviewer

For a pull request of tier 1 or above: the skeptic reviewer
([`.claude/agents/skeptic-reviewer.md`](../../agents/skeptic-reviewer.md)), given only the issue's
"Done" checks and the diff, reviews it. Its findings are fixed, or said at the top of the pull
request. Tier 0 takes the builder's own review of its diff, and no walk.

## 2. The guard

Wait for CI's `guard` on the newest commit, in the foreground: a command that polls the checks,
and the `baselines/<branch>` ref when pictures are being retaken, run again until they finish.
Never by ending the turn.

- **A failure** is the agent's to fix, in a new commit.
- **The walk fails only because a page the issue meant to change looks different**: the skill
  `pictures`.
- **A failure the agent cannot fix** is said at the top of the pull request, with what would fix
  it, and the pull request stays a draft.

## 3. Clean, or waiting

Only once the reviewer has come back, its findings are fixed or said, and `guard` is green on the
newest commit. First wait until `tiers.yml` has a run on the newest commit and every run of it
there has finished (`gh run list --workflow tiers.yml --commit <sha>`; none yet is not finished),
then read the labels it set.

- **Clean**: mark it ready (`gh pr ready <n>`) and turn auto-merge on straight after, inside the
  minute `notify.yml` waits before it asks. GitHub merges it once `guard` is green, at once when it
  already is. Never press on `tier 3` or `figures moved`, whatever the review found. `tiers.yml`
  turns off only a press it finds as a commit arrives; one made later is taken as the maintainer's
  yes. Auto-merge is never on while a commit is still to come: one needed after the press turns it
  off first (`gh pr merge <n> --disable-auto`), and the pull request goes back through 1 and 2.
- **Not clean**: mark it ready, and leave auto-merge off, with what is needed from the maintainer
  at the top of the description. A pull request that moves the store or a figure says what moves
  there, and in the changelog. A pull request of tier 3, or of tier 2 with a headline figure moved,
  is never the agent's to turn on, at any moment: `tiers.yml` turns off what it finds on as a
  commit arrives, and a press made after the tier is judged stands as the maintainer's yes.

## 4. After it merges

Nothing on the Queue: the coordinator ticks the issue's line at its next run (the skill
`keep-the-queue`). A builder chooses its next line by the issues' state, not by the ticks.

The agent goes on to the next issue without waiting for a merge that waits on the maintainer.
