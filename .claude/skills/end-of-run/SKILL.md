---
name: end-of-run
description: The run's last three steps, in order, once nothing is left to wait for: stop watching its pull requests, add its line to the run log (#289), and send the debrief (CONTRIBUTING.md, Telling the maintainer).
---

# Ending a run

The rules, what the debrief must say among them, are in `CONTRIBUTING.md`, The nightly agent,
Telling the maintainer.

## 1. Stop watching

`unsubscribe_pr_activity` for each pull request the run subscribed to, merged or waiting: a run
woken after it reloads its whole context for nothing. A run woken all the same follows
CONTRIBUTING.md, Telling the maintainer.

## 2. The run log's line

One comment on the run log (#289): the run's mark, then the date and when it began and ended, UK
time, what it did in a line, and its `Next:` line, as in

`🌙 **Night run** · 17 Nov 02:00–02:47 · built #250, merged · Next: …`

The time stays first after the mark; a ready check started for a re-plan says so after its time.
It is the source for a run's length, its stops and which run was at work; it asks nothing and
pings no one.

## 3. The debrief

Sent to the maintainer's phone as a push notification (the `PushNotification` tool), a few lines:
what merged, what waits on the maintainer, or that the run had nothing to do, and its `Next:`
line as CONTRIBUTING.md says, as in "Next: the night run, at 02:00, builds #250." Then the same
debrief is the message that ends the turn.
