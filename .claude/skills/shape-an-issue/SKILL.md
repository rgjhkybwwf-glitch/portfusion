---
name: shape-an-issue
description: "Coordinator: brings an issue, or the maintainer's Idea, to its Definition of Ready. It holds the two definitions, for a fix or a slice and for a feature, and what \"covers\" means."
---

# Shaping an issue

## The Definition of Ready

- **An issue is ready when it meets its Definition of Ready and carries no `decision` label**, so
  it can be built unattended and merged unread. A fix, and a slice of a feature, needs all five:
  - **Cause**: what in the code makes the symptom, by file and function. A symptom alone is
    evidence, not an issue. A slice's Cause is what the code lacks, by file and function.
  - **Done**: the checks that say it is done, each one a test, a walk step or a command can make.
  - **Not in scope**: what the fix leaves alone.
  - **Decisions**: every question answered by the maintainer, quoted with the date, and every
    choice a run decided in place of one, marked so (the skill `ask-or-decide`). An answer in a
    comment counts; the agent copies it into this section before it starts.
  - **Order**: what it waits on, and what waits on it. The issue's Order is the source; a Queue
    line's "waits" only copies it.
- **A feature, labelled `feature`, is ready when its shape is decided.** It is never built
  itself; its slices are (the skill `slice-a-feature`). It has Not in scope, Decisions and Order,
  and:
  - **Outcome**: who can do what they could not, on which page, in one sentence, and which job
    of the direction page it serves.
  - **Shape**: the option chosen on its design card, quoted with the date, and the options
    declined.
  - **Reach**: the stability rules it touches, the figures that move, and any store move with
    its migration.
  - **Slices**: two to six, in order. More than six makes it two features.
  - **Introduction**: how it stays hidden until its last slice, and what that slice turns on.
  - **Trial**: three jobs for the maintainer to try on their own book after the release.

## Does an open issue cover it?

**"Covers" is by the code, not the topic.** An open issue covers a find, an idea or a bump when
its Cause or Done names the same file and function; the coordinator reads every open issue's
Cause and Done for that before it files a new one, by the wide reader
([`.claude/agents/wide-reader.md`](../../agents/wide-reader.md)), which returns a short list. A
find about the look (colour, type, spacing, a part's shape) is covered by #9 alone while it is
open (the skill `fix-fold-report`). What is covered is added to that issue, as evidence, and no
new issue is filed.

## An `Idea:` issue

**An issue the owner opens with a title beginning `Idea:` is new work in their words.** The
coordinator shapes it in place, in the idea run the gate starts ten quiet minutes after, at any
hour:

1. The maintainer's words stay at the top, quoted.
2. The title is made an issue's title.
3. It takes its area labels, and the milestone whose theme it fits.
4. One that adds function is shaped as a feature and labelled `feature`, its Shape left for its
   design card. Any other gets a cause found in the code, then Done, Not in scope and Order.
5. Its line goes in the Queue by the skill `place-an-issue`.
6. What only the maintainer can settle is asked now, with `decision`; the rest is decided (the
   skill `ask-or-decide`).

An idea that is already an open issue's is added to that issue and closed.

## Any other issue

An issue short of its Definition of Ready is completed to it: a cause by file and function, the
checks that say it is done, what it leaves alone, its decisions and its order. A symptom alone is
evidence, not an issue: it goes onto the issue that meets the definition.

A question that cannot be settled yet is written at the issue's end, and its Decisions read
"Open: asked when it is under Next". The issue takes no `decision`, so it pings no one, and it is
not ready.
