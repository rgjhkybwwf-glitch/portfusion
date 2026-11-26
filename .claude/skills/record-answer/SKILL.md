---
name: record-answer
description: "Coordinator: finds the maintainer's answers and changes, copies each into its issue's Decisions, and marks what must be planned again and what a builder may build. It holds what a Change does, and when a decision issue closes."
---

# Recording an answer

## Finding them

**Every answer and change is recorded before anything is built**: each is found by the
comments, not the labels, and recorded before a builder is started, so a run started later does
not take the same issue. The run that records them builds nothing.

List the owner's comments on issues and pull requests since this run's own last run began (the
start on its last line in the run log; the last three days when there is none). Leave out each
that opens with a run's mark or a session's note. Take each whose first words answer (`Q1:`,
`All as recommended`) or begin `Change:`.

A `decision` label taken off by hand, and a trigger that names one issue, hide nothing. An answer
already in its issue's Decisions is skipped.

## An answer

**The run that reads a full answer records it**, in the issue's Decisions, quoted with the date,
and takes `decision` off:

1. Copy the answers into the issue's Decisions, quoted, with the date.
   Under each, the options the answer left out, as "Declined:", each with what would bring it
   back ("Revisit when: …", from what the question said it costs), so the gate review can read
   them again (the skill `ask-or-decide`).
2. Take `decision` off.
3. An answer that leaves a question open: ask that question again, alone, and take `decision` off
   and put it back on, so the maintainer is told.

**An answer records a decision; only lines under Next are built.** Every answer is recorded,
wherever its issue stands. An issue not under Next, a feature, and the issue a design card was
answered on are left there: nothing of them is built, and the maintainer's placing or the
coordinator's slices come first. A card's answer takes its line out of Design next. An answer to
a gate review is applied by the skill `gate-review`, and a `Change:` on the Queue by
`keep-the-queue`.

## A `Change:`

**A reply beginning `Change:` redirects an issue or one of the agent's pull requests**, and
reverses a choice a run decided. The gate marks it 🚀 and holds the work at once: the issue takes
`decision`, the pull request loses its auto-merge. The run that records it then reads the change
and rewrites the issue to match:

1. Rewrite the issue's Done, Not in scope and Decisions to match, quoting the change with the date.
   A change to a choice the run decided replaces that line in Decisions.
2. If nothing is left unclear, take `decision` off; otherwise ask what the change leaves open
   (the skill `ask-or-decide`).
3. A pull request already open is held for the new plan, or closed with the reason when the change
   makes it moot.

## What Decisions keep

**An issue's Decisions hold what stands.** A decision that a later answer or `Change:` replaces is
removed, and its "Declined:" and "Revisit when" lines move to the entry that replaces it, so the
gate review still finds them. A run's decision about a step of the work, such as which card goes
up first, is removed once that step is done. The maintainer's words in the answer that stands
stay quoted with the date. GitHub keeps every edit of the body, so nothing removed is lost.

## What no longer stands

A plan posted "if answered as recommended" stands when every answer is the recommended one. Any
other answer, an answer to a question raised mid-build, and a `Change:` leave the plan no longer
standing: write a comment whose first line after the run's name is "Re-plan:" and why, take
`planned` off, and leave the issue to be planned again. The gate starts the re-plan from that
comment.

## What a builder may build

**Then a builder builds the answered issues under Next whose plan still stands.** Once every
answer and change is recorded: on each answered issue under Next whose plan still stands, that
carries no `hold`, write a comment whose first line after the run's name is "Build:" and, in a few
words, that it was answered as recommended and its plan stands. The gate starts a builder after
the last of those comments. It builds the issues so marked one after another, in Queue order, up
to its cap, and no other line. An issue not under
Next, a feature, and the issue a design card was answered on get none. One still not ready, a
question open or a "waits" issue open, is named in the debrief and left.

## A decision issue

**A decision issue closes once it is decided.** An issue that only records a decision is closed
when every question on it is answered and recorded and each part of what it settles is filed or
written into the issue it settles. The closing comment names where each went. The Queue, the
release checklist, the walk finds, the run log and a feature are never closed so.
