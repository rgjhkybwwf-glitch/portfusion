---
name: place-an-issue
description: "Coordinator: gives every issue it files or shapes its labels and its place: a line in the release whose headline needs it, or in Upkeep, and says where and why. A milestone being worked only gets shorter."
---

# Placing an issue

- **Every issue has a place.** Each issue the coordinator files or shapes is given its labels and
  its line: in the first release whose headline needs it, among that milestone's lines in the
  order of the work, or else in Upkeep. The placement is decided, not asked (the skill
  `ask-or-decide`), and the debrief names each and why. The maintainer moves a line by editing
  the Queue, or with `Change:` on it, and a line they placed is never moved by a run. Only a
  feature the arc does not name is left unplaced, for the gate review to ask.
- **A milestone is a release with a headline**: its row in the direction's arc, what it is for
  and where it is first seen. A line joins a release only when its headline needs it: an issue
  the row names by its number, a slice of a feature it names, an issue one of those waits on,
  at any remove, or a fault in a file one of those changes, so that file is opened once.
- **Every other issue is Upkeep.** It takes no milestone, and its line stands under the Queue's
  Upkeep heading, the worst first. A release draws its share of Upkeep at its gate (the skill
  `gate-review`), so a fault no headline needs is still built, and none stands ahead of a
  feature.
- **A milestone being worked only gets shorter**, except for the slices of a feature already in
  it: nothing else joins Next but by the maintainer's placing. What is filed while it is worked,
  a bug included, is placed in the next milestone at the earliest.

Read the Queue afresh just before each edit: the maintainer may have changed it.

## Its labels

The area labels of the issue it came from, or of the files its Cause names.

## Its milestone

By each release's headline, its row in `docs/direction.md`, The arc:

- **The next milestone at the earliest**, never the one being worked, whatever the issue is: a
  bug or a wrong figure included.
- **The first release whose headline needs it**: the row names the issue by its number, it is
  a slice of a feature the row names, the "waits" of one of those names it, at any remove, or its
  Cause names a file that one of those names in its Cause or plan. The placing comment says
  which. A feature not yet sliced names no file, so until then a fault in its files is Upkeep.
- **Upkeep, when no headline needs it**: no milestone, whatever its page or its size.
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
- **In Upkeep, the worst first**: a wrong figure or a security alert, then a fault that stops
  one of the owner's jobs, then the rest, and within each the oldest first. A line the maintainer placed there
  keeps its place.

## A move the maintainer answers

An answer to a move Monday's review asked (the skill `keep-the-queue`) is recorded on its issue
(the skill `record-answer`) and applied here, in the same run. A yes moves the line, which then
ends `· yours`, and its issue takes the release's milestone, or none in Upkeep. A feature's
slices move with it, and the arc follows, as step 3 of the skill `slice-a-feature` edits it.
A no stays in the issue's
Decisions, and the move is not asked again.

## Saying so

**A line is one short line: what the issue is, why it stands there in brackets, and what it waits
on**, about 200 characters at most, as in "- [ ] #315 The Bench files a document under the wrong
name (a bug, after both its waits) · waits #185, #186". The maintainer's own lines, whether typed or
answered, end `· yours`, and no run moves one. Where the issue came from, who placed it and when go
in a comment on the issue, and the debrief names each placement and why, under "Decided for you".
The Queue keeps no history: GitHub keeps every edit of its body.
