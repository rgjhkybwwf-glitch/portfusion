---
name: gate-review
description: Posts the gate review on #206 on the day a milestone's gate is reached, holding the Queue review for the next milestone (CONTRIBUTING.md, Which issues and The ready check).
---

# The gate review

The gate, and when the review is posted, are in `CONTRIBUTING.md`, The nightly agent: Which
issues, in what order, and The ready check.

Posted on #206, once, headed "Gate review" with the milestone's name. It takes the Queue review's
place and holds all of it for the next milestone (the `queue-review` skill), with the questions of
any Queue review standing unanswered folded in, and:

- what a helper's read of every open issue, and of the Decisions of the issues closed since the
  last gate, finds: decisions that conflict or were never carried over, answers not recorded,
  issues with no line in the Queue, and a `decision` with no question waiting, each folded into
  its questions or its proposals;
- what shipped, against the milestone's sentence in `docs/direction.md`;
- keep or pull, for each feature the maintainer has trialled;
- each design card unanswered, and a move for each feature left under Next with no shape;
- the next milestone's proposed shape: its order, its cuts and its moves;
- at most three ideas, a line each with its cost; an idea never pings on its own;
- the rules of The nightly agent that cost a run a wrong turn, time or money, each with its run;
- at most five questions in all, the direction page's open ones among them. What it holds beyond
  five is listed as proposals, and asked in the next review.

#206 takes `decision`.
