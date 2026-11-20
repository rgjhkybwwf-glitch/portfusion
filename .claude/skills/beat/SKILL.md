---
name: beat
description: "Any run: writes the run's start line and its end line on the run log, in the form the dashboard reads (CONTRIBUTING.md, Telling the maintainer)."
---

# The beat

The rule is in `CONTRIBUTING.md`, The loop, Telling the maintainer: each run writes two
lines on the run log, one as it starts and one as it ends.

Both are comments on the run log. Each opens with the run's mark, as the runs table gives it, then
a date and a time, UK time. Neither asks anything, and neither pings anyone.

## The start line

The run's first act, before it reads anything else:

`🌙 **Builder** · start · 17 Nov 00:30 · building the first planned line`

After the word `start`: the date, the minute the run began, and in a few words what it sets out
to do. A run the gate started says there what started it: an answer, an idea, a release, a
re-plan, a `Resume:` or the coordinator's "Build:".

## A paused loop

Before the start line, read the Queue's labels. While it carries `paused`, a run its routine's
clock started writes neither line and does nothing: it ends in one line, which begins `Next:`
and says the loop is paused. The gate starts no run in a pause, so only a clock's run meets one.

## The end line

Written by the skill `end-of-run`, once nothing is left to wait for:

`🌙 **Builder** · 17 Nov 00:30–01:17 · built #250, merged · Decided for you: #250 · Next: …`

The mark, the date, when the run began and ended, what it did in a line, then "Decided for you:"
and each issue the run decided a choice on (left out when it decided nothing), and its `Next:`
line. The morning's digest is put together from these lines.

A run the Stop hook held says so after what it did, in the hook's own words, as in
"· built #250, merged · held 1× for `guard`, 12 min · Next: …". The skill `end-of-run` says where
the words come from; a run that was never held leaves the part out.
The time it began is the start line's, to the minute: the two lines are paired by it. The time
stays first after the mark; a run started for a re-plan says so after its time.

A dry run writes neither line.
