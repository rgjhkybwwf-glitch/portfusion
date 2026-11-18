---
name: gate-review
description: "Coordinator: posts the gate review on the Queue on the day a milestone's gate is reached, and applies the maintainer's answer to it (CONTRIBUTING.md, Which issues, and The ready check)."
---

# The gate review

The gate, when the review is posted and what it may ask are in `CONTRIBUTING.md`, The nightly
agent: Which issues, in what order, and The ready check.

## The review

Posted on the Queue, once, headed "Gate review" with the milestone's name. It takes the Queue
review's place that day, and asks each line waiting under the Queue's heading for it.

**What it asks**, under "Questions for you", is of three kinds only, up to CONTRIBUTING's limit:

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
- the rules of The nightly agent that cost a run a wrong turn, time or money, each with its run.

The Queue takes `decision`.

## Applying its answer

1. Make the answered changes to the Queue: its lines, a "waits", an issue merged or closed with
   the reason.
2. Move issues between milestones.
3. Write the next milestone's lines, in the order answered, under the Queue's heading for after
   the gate.
4. File the issue for a pull (CONTRIBUTING.md, Features).
5. Edit `docs/direction.md` to the answer in a pull request that links the Queue. It may merge
   itself once `guard` is green, the answer being its yes.
6. Take `decision` off the Queue.
7. Leave a comment on the release checklist whose first line after the run's name is "Re-plan:
   the gate review for <milestone> is answered", and take `planned` off it.
