---
name: queue-review
description: Posts the ready check's Queue review on #206 and sorts the walk finds (#220) with it (CONTRIBUTING.md, The ready check). Twice a week, and never while a gate review stands unanswered.
---

# The Queue review

When it is due is in `CONTRIBUTING.md`, The nightly agent, The ready check. Its questions follow
Asking and answering there.

## The review

It reads every open issue of the milestone being worked and the next, against today's `main`, by
a helper agent (A run reads narrow), and posts a **Queue review** on #206:

- issues that duplicate one another, to merge;
- overlaps by file and function that no "waits" orders;
- causes that no longer hold, to close with the reason;
- a place for each walk find left to sort;
- a suggested order.

Each is a question, with its recommendation, and #206 takes `decision`. Below its questions it
lists three ideas for improving a feature, a line each with the job it serves and its cost; they
are not asked, and the maintainer takes one up with an `Idea:` issue. A review with nothing to ask
is posted for its ideas alone, without `decision`, so it pings no one.

## The walk finds (#220)

With the review, and not each run, it sorts "Walk finds: to sort":

- A find goes onto the open issue that covers it, as evidence, or onto the decided feature that
  will rework its page.
- One not worth an issue is struck through with the reason.
- The rest stay one line each, and the review proposes their place.
- A find the maintainer has placed is shaped then, with others like it, into an issue that meets
  the Definition of Ready, on the line answered, its questions written but not asked.

Each line handled is struck through, so the list only holds what is unsorted.
