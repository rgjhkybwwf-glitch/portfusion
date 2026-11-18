---
name: end-of-run
description: The run's last three steps, in order, once nothing is left to wait for: stop watching its pull requests, add its line to the run log (#289), and send the debrief (CONTRIBUTING.md, Telling the maintainer).
---

# Ending a run

The rules are in `CONTRIBUTING.md`, The nightly agent, Telling the maintainer: a run is one turn,
it ends by sending its debrief, and nothing of these three is sent while something is still
running.

## 1. Stop watching

`unsubscribe_pr_activity` for each pull request the run subscribed to, merged or waiting: a run
woken after it reloads its whole context for nothing. One woken all the same sends no second push,
adds no second line to the run log, and ends in one line, which begins `Next:`.

## 2. The run log's line

One comment on the run log (#289): the run's mark, then the date and when it began and ended, UK
time, what it did in a line, and its `Next:` line, as in

`🌙 **Night run** · 17 Nov 02:00–02:47 · built #250, merged · Next: …`

The time stays first after the mark; a ready check started for a re-plan says so after its time.
It is the source for a run's length, its stops and which run was at work; it asks nothing and
pings no one.

## 3. The debrief

Sent to the maintainer's phone as a push notification (the `PushNotification` tool), a few lines:
what merged, what waits on the maintainer, or that the run had nothing to do.

- **Its last line begins with the word `Next:`**, then who acts next, on what, and when, as in
  "Next: the night run, at 02:00, builds #250."
- When no line under Next can be built, it names each line and what holds it: a question (whose),
  no plan yet or a "Re-plan" (the ready check's), `building` (which run), an open pull request, a
  "waits" or the gate.
- While a gate review stands unanswered, or a release untagged, the push and the debrief say in
  one line what the run waits on.

The message that ends the turn is the debrief in full.
