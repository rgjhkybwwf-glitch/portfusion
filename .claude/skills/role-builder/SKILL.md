---
name: role-builder
description: "Role book: every run of a builder's, by night, in the evening or after an answer. It holds the order of a build, how a line is taken, and the rules of the level."
---

# The builder's book

A builder's run follows this book from its start line to its debrief. Its row of the runs table
says what started it, its mark and its cap, and the brief says which row it is and the line to
take (the skill `beat`). Each step's rules and its procedure are in the skill named, opened when
the step comes. A builder never writes a plan, files nothing and edits neither the Queue nor the
walk finds.

## The level's rules

- **It takes the first line it can build, and never reorders**: the first under Next whose issue
  carries `planned` and none of `decision`, `building` and `hold`, has no open pull request of its
  own, and whose "waits" issues are all closed. It skips the rest.
- **An answer build takes only what the coordinator marked**: the issues under Next marked
  "Build:" since their last **Plan, checked**, in the Queue's order, and no other line.
- **No line it can build and nothing to tend: stop**, posting nothing on GitHub but its lines in
  the run log. The debrief names each line under Next and what holds it.
- **Every choice on the way goes through the skill `ask-or-decide`**, and every find outside the
  change through `fix-fold-report`.

## The order

1. **The start line**: the skill `beat`, saying which build it is: the night's, the evening's,
   the late evening's, or an answer build, whose starting text begins "Answer build:".
2. **After a tag**: the next version's pull request (the skill `release`, After the tag). The
   Queue's lines are the coordinator's to move: until it has, Next holds nothing of the new
   milestone to build.
3. **Its own open pull requests first**: the skill `tend-pull-requests`.
4. **Take a line**, by the level's rules above.
5. **Build it**: the skill `build-an-issue`.
6. **Take its pull request to its end**: the skill `review-and-merge`.
7. **Again from step 4**, up to the cap.
8. **The end**: the skill `end-of-run`.

## Which build it is

| Start | Its text begins | What it builds |
|---|---|---|
| Night build | nothing: its routine's clock | the first line it can build, to the cap |
| Evening build | nothing: its routine's clock | the first line it can build, to the cap |
| Late evening build | nothing: its routine's clock | the first line it can build, to the cap |
| Answer build | `Answer build:` | only the issues marked "Build:", in the Queue's order, to the cap |
