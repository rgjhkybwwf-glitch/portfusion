---
name: record-answer
description: "Coordinator: finds the maintainer's answers and changes, copies each into its issue's Decisions, and marks what must be planned again (CONTRIBUTING.md, Asking and answering, and The answer run)."
---

# Recording an answer

What counts as an answer, and what a `Change:` does, are in `CONTRIBUTING.md`, The nightly agent,
Asking and answering. Every answer is recorded, wherever its issue stands, and each is recorded
before anything is built on it, so a run started later does not take the same issue.

## Finding them

By the comments, not the labels. List the owner's comments on issues and pull requests since this
run's own last run began (the start on its last line in the run log; the last three days when
there is none). Leave out each that opens with a run's mark or a session's note. Take each whose
first words answer (`Q1:`, `All as recommended`) or begin `Change:`.

A `decision` label taken off by hand, and a trigger that names one issue, hide nothing. An answer
already in its issue's Decisions is skipped.

## An answer

1. Copy the answers into the issue's Decisions, quoted, with the date.
2. Take `decision` off.
3. An answer that leaves a question open: ask that question again, alone, and take `decision` off
   and put it back on, so the maintainer is told.

A card's answer also takes its line out of Design next. An answer to a gate review is applied
by the skill `gate-review`, and a `Change:` on the Queue by `keep-the-queue`.

## A `Change:`

`answer.yml` has already held the work: the issue carries `decision`, the pull request has lost
its auto-merge.

1. Rewrite the issue's Done, Not in scope and Decisions to match, quoting the change with the date.
   A change to a choice the run decided replaces that line in Decisions.
2. If nothing is left unclear, take `decision` off; otherwise ask what the change leaves open
   (the skill `ask-or-decide`).
3. A pull request already open is held for the new plan, or closed with the reason when the change
   makes it moot.

## What no longer stands

A plan posted "if answered as recommended" stands when every answer is the recommended one. Any
other answer, an answer to a question raised mid-build, and a `Change:` leave the plan no longer
standing: write a comment whose first line after the run's name is "Re-plan:" and why, and take
`planned` off. `replan.yml` starts the re-plan from that comment.

## A decision issue

An issue that only records a decision is closed when every question on it is answered and
recorded and each part of what it settles is filed or written into the issue it settles. The
closing comment names where each went. The Queue, the release checklist, the walk finds, the run
log and a feature are never closed so.
