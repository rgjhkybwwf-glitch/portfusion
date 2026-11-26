---
name: review-and-merge
description: "Builder: takes an open pull request to its end. The skeptic reviewer reads it, the guard is waited for, and it merges itself or says what waits for the maintainer. It holds what makes a pull request clean, and the three that never are."
---

# Review and merge

- **Done means `guard` green on the last push.** No pull request is called clean, and none is
  left, until CI's `guard` has passed on its newest commit; a local run is a quick check, not the
  proof.
- **A clean pull request merges itself**: one that asks the maintainer nothing, passes the guard,
  the walk and the reviewer (tier 0: the guard alone), and has its finds placed. A choice the run
  decided, said at its top, keeps it clean; an Important review finding said there does not, and
  waits for the maintainer's yes. The agent opens it as a draft, and turns its auto-merge on only
  once the reviewer has come back and `guard` is green on its newest commit, as it marks it
  ready; GitHub then merges it. Pictures retaken for a page the issue meant to change keep it
  clean.
- **Three are never clean**: a pull request that moves the store (a table or column of
  `record/schema.py`, or a move in `record/migrations.py`), a slice that moves a figure (what an
  engine method returns on the demo), and the slice that turns a feature on. `tiers.yml` holds the
  store and a moved headline figure; any other figure, and the third, are the builder's to say.
  The first two are never hidden: each says what moves at the top of its pull request, and in the
  changelog.
- **Any other waits for the maintainer's yes**, auto-merge off, with what is needed from them at
  the top of its description. The yes is the maintainer pressing Enable auto-merge, so the merge
  is theirs and everything after it runs.

The pull request is a draft until its end (the skill `build-an-issue` opens it so): nothing can
merge it, and `notify.yml` asks nothing of it, while it is read and its guard runs. Auto-merge is
the last thing done, never the first.

## 1. The reviewer

**A reviewer who did not build it.** Before a pull request of tier 1 or above is called clean,
the skeptic reviewer
([`.claude/agents/skeptic-reviewer.md`](../../agents/skeptic-reviewer.md)), given only the issue's
"Done" checks and the diff, reviews it. Its findings are fixed, or said at the top of the pull
request. Tier 0 takes the builder's own review of its diff, and no walk.

## 2. The guard

**A CI failure on its pull request** is the agent's to fix, and it waits for the guard's result
before it leaves a pull request. **It waits in the foreground**, on the newest commit, by a
command that polls the checks, and the `baselines/<branch>` ref when pictures are being retaken,
run again until they finish, **never by ending its turn**.

- **A failure** is the agent's to fix, in a new commit, reviewed before it is pushed as
  `CONTRIBUTING.md`, Commits and pull requests, says.
- **The walk fails only because a page the issue meant to change looks different**: the skill
  `pictures`.
- **A failure the agent cannot fix** is said at the top of the pull request, with what would fix
  it, and the pull request stays a draft, for the next run's `tend-pull-requests` and the debrief's
  Faults.

## 3. Clean, or waiting

Only once the reviewer has come back, its findings are fixed or said, and `guard` is green on the
newest commit. First wait until `tiers.yml` has a run on the newest commit and every run of it
there has finished (`gh run list --workflow tiers.yml --commit <sha>`; none yet is not finished),
then read the labels it set. A press after the tier is judged is taken as the maintainer's yes, so
nothing in `tiers.yml` catches a wrong one: a run there that failed, or no `tier` label, is read
as `tier 3`.

Then read the pull request and its issue again. A `hold` or `decision` label, or a `Change:` reply,
that came while it was read leaves it a draft, for `tend-pull-requests` and the coordinator.

**Nothing is left saying it is pending once it is not.** Before either, the first paragraph of
the pull request says where it stands, between the marks `<!-- state -->` and `<!-- /state -->`,
each on a line of its own: "Merges itself once `guard` is green." for a clean one, or what is
needed from the maintainer. When the pull request merges or closes, `notify.yml` rewrites what is
between the marks to say so, with the time, so it is never written to say what happened after.

An Important finding of the `code-review` skill that stands, said at the top, keeps it from being
clean; one said there as judged wrong, with why, does not.

- **Clean**: mark it ready (`gh pr ready <n>`) and turn auto-merge on straight after
  (`gh pr merge <n> --auto --merge`), inside the minute `notify.yml` waits before it asks. GitHub
  merges it once `guard` is green; when GitHub refuses the press because the pull request is
  already clean, merge it (`gh pr merge <n> --merge`). Refused for anything else, it is made a
  draft again at once (`gh pr ready <n> --undo`), before `notify.yml` asks, and the refusal is put
  right or said at its top. Never press on `tier 3` or `figures moved`,
  whatever the review found. `tiers.yml` turns off only a press it finds as a commit arrives; one
  made later is taken as the maintainer's yes. Auto-merge is never on, nor the pull request ready,
  while a commit is still to come: one needed after the press turns auto-merge off and makes it a
  draft again first (`gh pr merge <n> --disable-auto`, `gh pr ready <n> --undo`), and the pull
  request goes back through 1 and 2.
- **Not clean**: write what is needed from the maintainer at the top of the description first,
  then mark it ready and leave auto-merge off: `notify.yml` asks a minute later, and points them to
  the top. A pull request that moves the store or a figure says what moves there, and in the
  changelog. A pull request of tier 3, or of tier 2 with a headline figure moved,
  is never the agent's to turn on, at any moment: `tiers.yml` turns off what it finds on as a
  commit arrives, and a press made after the tier is judged stands as the maintainer's yes.

## 4. After it merges

Nothing on the Queue: the coordinator ticks the issue's line at its next run (the skill
`keep-the-queue`). A builder chooses its next line by the issues' state, not by the ticks.

The agent goes on to the next issue without waiting for a merge that waits on the maintainer.
