---
name: keep-the-queue
description: "Coordinator: keeps the Queue. Each run it ticks what merged and sorts what the builders reported; on Monday and Thursday it reviews the whole Queue, acts, and posts what it did (CONTRIBUTING.md, Which issues, and The ready check)."
---

# Keeping the Queue

The rules are in `CONTRIBUTING.md`, The loop: only the coordinator writes the Queue and
the walk finds, and only it files an issue. What it does here is decided and told, not asked
(the skill `ask-or-decide`): each act is listed, and the maintainer reverses one with `Change:`.

Read the Queue afresh just before each edit: the maintainer may have changed it. A line the
maintainer placed, by hand or by an answer, is never moved.

## Each run

1. **Tick what merged.** For each pull request merged since the run's last, tick its issue's
   line and move it to Done, with the pull request's number. Clear each "waits" now met.
2. **Sort what was reported.** Read the **Reported** list of each of the agent's pull requests
   opened or merged since the run's last (the skill `fix-fold-report`), and give each find one of
   four ends, the first that fits:
   - **Folded** onto the open issue that covers it, as evidence, or onto the decided feature that
     will rework its page. "Covers" is by the code (the skill `shape-an-issue`).
   - **Filed**, when it earns an issue: a wrong figure, or a fault the owner of a book would
     meet; a break of a stability rule or of what a guide promises; or something that blocks or
     changes a line in the Queue. Finds of one cause make one issue. It is shaped to the
     Definition of Ready (`shape-an-issue`) and placed (`place-an-issue`).
   - **Held** on the walk finds, one line: how a page reads or looks, and too small for an issue
     of its own. The review gathers these.
   - **Dropped**, with the reason: by design, or not worth the change.
3. **Say so**, in one comment on that pull request, headed "Reported finds, sorted", a line a
   find with its end. A pull request that carries the comment is not sorted again. The debrief
   gives the counts: filed, folded, held and dropped.

## The review, on Monday and Thursday

On the morning run of a Monday and of a Thursday, and not while a gate review stands unanswered.
It reads every open issue against today's `main`, by a helper agent that returns a short list,
and then acts:

- **Duplicates are merged**: the later issue is closed as a duplicate, and its evidence and
  Decisions are carried to the one kept.
- **Overlaps by file and function** that no "waits" orders get their "waits".
- **A cause that no longer holds** closes its issue, with what on `main` ended it.
- **An issue with no line** is placed (`place-an-issue`).
- **The walk finds are gathered**: three or more held for one page, or any for a page the next
  milestone works, become one issue or join the feature that reworks the page. Each line handled
  is struck through with where it went, so the list holds only what waits.
- **The order is kept**: a line a run placed is moved when the order of the work asks it. A line
  the maintainer placed is not.

What it never does unasked: cut a line from a milestone, add a feature the arc does not name, or
change what a milestone is for. Those are the gate review's questions (the skill `gate-review`).

It then posts a **Queue review** on the Queue: what it merged, ordered, closed, placed and
gathered, a line each with the reason, and the count of open issues beside the last review's.
The Queue takes no `decision` for it, and it lists no ideas.

## A `Change:` on the Queue

The maintainer's `Change:` under a review, or on an issue the review closed or moved, is recorded
(the skill `record-answer`) and applied here: the issue is reopened, the line put back, the
"waits" taken off. The Queue takes no Decisions section: the line's brackets say who placed it.
