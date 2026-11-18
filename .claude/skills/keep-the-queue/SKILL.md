---
name: keep-the-queue
description: "Coordinator: reviews the whole Queue twice a week, sorts the walk finds with it, and applies a review the maintainer has answered (CONTRIBUTING.md, The ready check, and The answer run)."
---

# Keeping the Queue

When a review is due, and that an answered review is applied and never built, are in
`CONTRIBUTING.md`, The nightly agent. Its questions follow the skill `ask-or-decide`.

Read the Queue afresh just before each edit.

## The review

It reads every open issue of the milestone being worked and the next, against today's `main`, by
a helper agent that returns a short list, and posts a **Queue review** on the Queue:

- issues that duplicate one another, to merge;
- overlaps by file and function that no "waits" orders;
- causes that no longer hold, to close with the reason;
- a place for each walk find left to sort;
- a suggested order.

Each is a question, with its recommendation, and the Queue takes `decision`. Below its questions
it lists three ideas for improving a feature, a line each with the job it serves and its cost.
They are not asked: the maintainer takes one up with an `Idea:` issue.

A review with nothing to ask is posted for its ideas alone, without `decision`.

## The walk finds

With the review, and not each run, it sorts the walk finds:

- A find goes onto the open issue that covers it, as evidence, or onto the decided feature that
  will rework its page.
- One not worth an issue is struck through with the reason.
- The rest stay one line each, and the review proposes their place.
- A find the maintainer has placed is shaped then, with others like it, into an issue that meets
  the Definition of Ready, on the line answered (the skill `shape-an-issue`).

Each line handled is struck through, so the list holds only what is unsorted.

## Applying an answered review

The run makes the answered changes: the Queue's lines, a "waits", an issue merged or closed with
the reason, a find's place noted on the walk finds. Then it takes `decision` off the Queue. The
Queue takes no Decisions section.
