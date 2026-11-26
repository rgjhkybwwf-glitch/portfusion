---
name: gate-review
description: "Coordinator: posts the gate review on the Queue on the day a milestone's gate is reached, and applies the maintainer's answer to it."
---

# The gate review

- **The gate: when only the checklist is left under Next, with any feature whose shape is not
  decided, nothing of the next milestone is built.** The coordinator posts the gate review that
  day. The gate is answered when a comment headed "Gate review" for the milestone is on the Queue
  and the Queue carries no `decision`; only then is the checklist planned and worked: the answer
  run that applies the gate review marks it for a re-plan (Applying its answer, below), or else
  the next morning run plans it.
- **On the day the gate is reached it posts the gate review** on the Queue, once. It asks at most
  five questions in all, and only of three kinds: what shipped against the direction, keep or
  pull, and the next milestone's shape. Its housekeeping is done and listed, not asked, and an
  idea never pings on its own.
- **The trial is on the release.** The maintainer tries the Trial jobs on their own book, and
  keep or pull is asked in the next gate review. Pull applies to display slices only: a store
  move is not pulled back. A pull answered becomes an issue, its Decisions the answer, first
  under Next; its pull request reverts the slices and is never clean.
- **An answered gate review is applied, not built**, and so is a `Change:` on the Queue, which
  undoes what a review did (the skill `keep-the-queue`). The Queue is never an issue to build and
  takes no Decisions section. A gate review's edit of `docs/direction.md` may merge itself once
  `guard` is green, the answer being its yes.

## The review

Posted on the Queue, once, headed "Gate review" with the milestone's name. It takes the Queue
review's place that day, and asks each line waiting under the Queue's heading for it.

**What it asks**, under "Questions for you", is of three kinds only, five questions at most:

- **what shipped**, against the milestone's sentence in `docs/direction.md`, the direction page's
  open questions among them;
- **keep or pull**, for each feature the maintainer has trialled;
- **the next milestone's shape**: its order, its cuts and its moves, with each design card
  unanswered and a move for each feature left under Next with no shape.

**What it does and lists, unasked**, under "Done with this review": the housekeeping a helper's
read of every open issue, and of the Decisions of the issues closed since the last gate, turns
up. An answer not recorded is recorded, an issue with no line in the Queue is placed (the skill
`place-an-issue`), a `decision` with no question waiting is taken off, and a decision never
carried over is written where it belongs. Decisions that conflict are settled as the skill
`ask-or-decide` says.

**What it only lists**:

- at most three ideas, a line each with its cost;
- **the options to look at again**: each option declined in an issue's Decisions, by a run or by
  the maintainer, whose "Revisit when" has come true since the last gate, or that has none and
  was declined more than one milestone ago, a line each with its issue. The maintainer reopens one
  with `Change:` or an `Idea:`;
- the loop's own rules that cost a run a wrong turn, time or money, each with its run.

The Queue takes `decision`.

## Applying its answer

1. Make the answered changes to the Queue: its lines, a "waits", an issue merged or closed with
   the reason.
2. Move issues between milestones.
3. Write the next milestone's lines, in the order answered, under the Queue's heading for after
   the gate.
4. File the issue for a pull (The trial is on the release, above).
5. Edit `docs/direction.md` to the answer in a pull request that links the Queue. It may merge
   itself once `guard` is green, the answer being its yes.
6. Take `decision` off the Queue.
7. Leave a comment on the release checklist whose first line after the run's name is "Re-plan:
   the gate review for <milestone> is answered", and take `planned` off it.
