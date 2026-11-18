---
name: place-an-issue
description: "Coordinator: gives every issue it files or shapes its labels, its milestone and its line in the Queue, and says where and why (CONTRIBUTING.md, Which issues)."
---

# Placing an issue

The rules are in `CONTRIBUTING.md`, The nightly agent, Which issues, in what order: the
coordinator places every issue, the Queue sets the order, and a milestone being worked only gets
shorter. A placement is decided, not asked (the skill `ask-or-decide`): the maintainer moves a
line by editing the Queue, or with `Change:` on it.

Read the Queue afresh just before each edit: the maintainer may have changed it.

## Its labels

The area labels of the issue it came from, or of the files its Cause names.

## Its milestone

By what each milestone is for, in `docs/direction.md`, The arc:

- **The next milestone at the earliest**, never the one being worked, whatever the issue is: a
  bug or a wrong figure included.
- **The first milestone whose purpose it serves.** One that serves none takes the nearest by the
  arc, and its line says "nearest fit" and why.
- **A feature the arc does not name** is not placed: adding it would change what a milestone is
  for, which is the maintainer's. It gets a line under the Queue's heading for the next gate
  review, with the milestone proposed, and the gate review asks it.

## Its line

Among its milestone's lines, under that milestone's heading in the Queue, which the coordinator
adds when the milestone has none:

- **In the order of the work**: first what changes how the work is made, so what follows is built
  and tested on it (a split, a guard, a tool); then unblockers, bugs and wrong figures, small
  safe fixes, features and polish.
- **After every line it waits on**, with its "waits" written.
- **Lines already there keep their order**, and a line the maintainer placed is never moved.
- **A decided feature's slices** go at the feature's line, in order (the skill
  `slice-a-feature`).

## Saying so

The line says in brackets where the issue came from, who placed it and when, and why it stands
where it does, as in "(reported by #318's build; placed 19 Nov 2026 by the coordinator: a bug,
after both its waits)". The debrief names each placement and why, under "Decided for you".
