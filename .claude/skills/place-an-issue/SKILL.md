---
name: place-an-issue
description: "Coordinator: gives an issue it files or shapes its labels, its milestone and its line in the Queue, and says where (CONTRIBUTING.md, Which issues)."
---

# Placing an issue

The rules are in `CONTRIBUTING.md`, The nightly agent, Which issues, in what order: the Queue sets
the order, and a milestone being worked only gets shorter.

Read the Queue afresh just before each edit: another run may have changed it.

## Its labels and milestone

An issue the agent files takes the area labels of the issue it came from. It takes a milestone
only when it fits the theme of the one being worked or the next, by the direction page's arc.

## Its line

- **One for the next milestone** goes among that milestone's lines, in the order of the work:
  first what changes how the work is made, so what follows is built and tested on it (a split, a
  guard, a tool); then unblockers, bugs and wrong figures, small safe fixes, features and polish.
  Each goes after every line it waits on, and lines already there keep their order.
- **One for the milestone being worked, a later one, or none** goes under To rank, for the
  maintainer to place: nothing joins Next but by their placing.
- **A decided feature's slices** go at the feature's line, in order, wherever that stands in the
  Queue, and under To rank when it has none (the skill `slice-a-feature`).

## Saying so

The line says in brackets where the issue came from and why it stands where it does. The debrief
names each placement and why. The maintainer moves a line by editing the Queue, or with `Change:`
on it.
