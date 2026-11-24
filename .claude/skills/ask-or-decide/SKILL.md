---
name: ask-or-decide
description: "Any run: when a choice comes up, applies the test for asking. It either asks, under Questions for you, or decides and records the choice as decided by the run (CONTRIBUTING.md, Asking and answering)."
---

# Ask, or decide and tell

The test, and the limits on questions, are in `CONTRIBUTING.md`, The loop, Asking and
answering.

## First, settle what can be settled

What the code, the record's rules or an answer already given settles is neither a question nor a
decision: the run settles it and says so.

## The test

Ask and wait only when the step cannot be undone or changes direction, as CONTRIBUTING lists
them. Everything else the run decides.

## Deciding

1. Take the option the run would have recommended.
2. Write it in the issue's Decisions:
   `Decided by the run, D Mon YYYY: <the choice>, because <why, in a line>. Declined: <the others>.`
   Each option declined says what would bring it back, as in "Declined: b, a second cache.
   Revisit when: a page takes more than a second to load." The gate review reads these lines.
3. Carry on. A choice made mid-build is also said at the top of the pull request.
4. Keep it for the debrief's "Decided for you" (the skill `end-of-run`).

It takes no `decision` label and pings no one. The maintainer reverses it with `Change:`.

Three choices are always decided, never asked:

- **A plan finds the issue's cause or premise no longer holds.** The coordinator closes the issue
  with the reason, or re-shapes it to what does hold, and writes which in its Decisions. A builder
  that finds it leaves a "Re-plan:" for the coordinator.
- **Two issues whose Done disagree.** The coordinator picks one, and writes why in the Decisions
  of both.
- **A question raised mid-build that the test does not hold.**

## Asking

- **Where**: at the end, under "Questions for you": of an issue, or of a comment that stops one.
- **How**: one line a question, written to be answered on a phone:
  `**Q1** the question? **a** an option (recommended) · **b** another`, with what each costs in a
  few words. Tables above it are evidence, read only when wanted, and carry no column to fill in.
- **When**: once its issue is under Next, and within the limit on open questions. An `Idea:`'s
  questions and a design card's are asked sooner. A question written before then sits at the end
  of its issue, whose Decisions read "Open: asked when it is under Next".
- **The label**: the issue takes `decision`, which is what tells the maintainer.
- **Mid-build**: a question that meets the test stops the issue. It is asked at the end of a
  comment on the issue, the issue takes `decision` and loses `planned`, what is built so far is
  pushed to its branch with no pull request, and the run moves on.
