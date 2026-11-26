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
- **A milestone is a release with a headline**: what the direction's arc says is first seen in
  it. A line joins a release only when its headline needs it: a slice of its feature, an issue a
  slice waits on, or a fault in a file a slice changes, so that file is opened once.
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

By each release's headline, in `docs/direction.md`, The arc, under "Where you first see
something new":

- **The next milestone at the earliest**, never the one being worked, whatever the issue is: a
  bug or a wrong figure included.
- **The first release whose headline needs it**, by the code: the issue is a slice of the
  headline's feature, a slice's "waits" names it, or its Cause names a file a slice's Cause or
  plan names. The placing comment says which.
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
- **In Upkeep, the worst first**: a wrong figure, then a fault that stops one of the owner's
  jobs, then the rest, and within each the oldest first. A line the maintainer placed there
  keeps its place.

## Saying so

**A line is one short line: what the issue is, why it stands there in brackets, and what it waits
on**, about 200 characters at most, as in "- [ ] #315 The Bench files a document under the wrong
name (a bug, after both its waits) · waits #185, #186". The maintainer's own lines, whether typed or
answered, end `· yours`, and no run moves one. Where the issue came from, who placed it and when go
in a comment on the issue, and the debrief names each placement and why, under "Decided for you".
The Queue keeps no history: GitHub keeps every edit of its body.
