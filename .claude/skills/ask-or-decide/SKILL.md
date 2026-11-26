---
name: ask-or-decide
description: "Any run: when a choice comes up, applies the test for asking. It either asks, under Questions for you, or decides and records the choice as decided by the run. It holds the test, how a question is written and when, and the limit on open questions."
---

# Ask, or decide and tell

## First, settle what can be settled

What the code, the record's rules or an answer already given settles is neither a question nor a
decision: the run settles it and says so.

## The test

**A run asks only what cannot be undone or changes direction.**

- **Cannot be undone**: a move of the store, a moved figure, a release, a feature turned on, a
  change to the keel (tier 3).
- **Changes direction**: who PortFusion is for, what a milestone is for, a feature's shape, an
  `Idea:` of the maintainer's.

**Everything else it decides, and tells.** It takes the option it would have recommended, writes
it in the issue's Decisions as decided by the run, with the date, carries on, and lists it under
"Decided for you" in its debrief. The maintainer reverses one with `Change:`.

## Deciding

1. Take the option the run would have recommended.
2. Write it in the issue's Decisions:
   `Decided by the run, D Mon YYYY: <the choice>, because <why, in a line>. Declined: <the others>.`
   Each option declined says what would bring it back, as in "Declined: b, a second cache.
   Revisit when: a page takes more than a second to load." The gate review reads these lines.
3. Carry on. **A choice that comes up mid-build is decided, and said at the top of the pull
   request.**
4. Keep it for the debrief's "Decided for you" (the skill `end-of-run`).

It takes no `decision` label and pings no one.

Three choices are always decided, never asked:

- **A plan finds the issue's cause or premise no longer holds.** The coordinator closes the issue
  with the reason, or re-shapes it to what does hold, and writes which in its Decisions. A builder
  that finds it leaves a "Re-plan:" for the coordinator.
- **Two issues whose Done disagree.** The coordinator picks one, and writes why in the Decisions
  of both.
- **A question raised mid-build that the test does not hold.**

## Asking

- **Every question for the maintainer is asked at the end, under "Questions for you"**: of an
  issue, and of a comment that stops one. A question is one line, written to be answered on a
  phone: `**Q1** the question? **a** an option (recommended) · **b** another`, with what it
  costs in a few words. Tables above it are evidence, read only when wanted, and carry no column
  to fill in.
- **A question is asked when its issue is under Next, not when it is filed.** One the agent
  files, from a find or from a comment, has its Decisions read "Open: asked when it is under
  Next"; it takes no `decision`, so it pings no one, and it is not ready. Once the issue is under
  Next the coordinator asks or decides each, whether or not its "waits" have closed, so an answer
  is in before its turn comes. Three are asked sooner, within the limit below: an `Idea:`'s, as it
  is shaped, since the maintainer is waiting on it, a feature's shape, on its design card, and
  a move Monday's review asks (the skill `keep-the-queue`). A
  question written in a session the maintainer is part of keeps `decision` wherever its issue
  stands, and is not asked again. An answer the maintainer gives early, in a comment, counts when
  its line is planned.
- **At most five questions stand open at once**, counting the milestone being worked's issues, a
  design card's, a gate review's and a Queue review's moves; questions on issues of a later milestone, written in a
  session the maintainer is part of, apart. Beyond five it asks nothing new but what blocks the
  first line under Next: an `Idea:`'s and a card's questions are written, and wait. While a card
  of its own stands unanswered it posts no new one; the gate review is the exception (the skill
  `gate-review`).
- **The label**: the issue takes `decision`, which is what tells the maintainer.
- **Mid-build**: only a choice that meets the test stops the issue. It is asked at the end of a
  comment on the issue, the issue takes `decision` and loses `planned`, what is built so far is
  pushed to its branch with no pull request, and the run moves on. Its answer leaves the plan to
  the coordinator, which plans it again; then the issue starts again, whole, on that branch.
