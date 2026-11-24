---
name: end-of-run
description: "Any run: the run's last three steps, in order, once nothing is left to wait for. It stops watching its pull requests, writes its end line on the run log, and sends the debrief (CONTRIBUTING.md, Telling the maintainer)."
---

# Ending a run

The rules, what the debrief's last line must say among them, are in `CONTRIBUTING.md`, The loop,
Telling the maintainer. None of the three steps is taken while something is still running.

## 1. Stop watching

`unsubscribe_pr_activity` for each pull request the run subscribed to, merged or waiting: a run
woken after it reloads its whole context for nothing.

## 2. The end line

One comment on the run log, as the skill `beat` gives it:

`🌙 **Builder** · 17 Nov 00:30–01:17 · built #250, merged · Decided for you: #250 · Next: …`

It is the source for a run's length, its stops, its faults and which run was at work, and the
morning's digest is put together from it.

Before writing it, run `python3 tools/stop_hook.py --holds`. It prints the Stop hook's holds of
this run in the words the line takes, as in "held 1× for `guard`, 12 min", or nothing for a run
that was never held. What it prints goes after what the run did, between two `·`.

A fault the run met goes next, after the word `Fault:`, between two `·`: what counts as one, and
the words it takes, are the skill `beat`'s. A run that met none leaves the part out.

## 3. The debrief

A few lines, the message that ends the turn:

- what merged;
- what waits on the maintainer: a question, or a pull request for them to enable auto-merge on;
- **Decided for you**: each choice the run made in place of a question (the skill
  `ask-or-decide`), a line each with its issue, so the maintainer can reverse one with `Change:`.
  Left out when the run decided nothing;
- **Faults**: each fault the run met, in one line, in its end line's words. Left out when it met
  none;
- or, with nothing merged, waiting or decided, that the run had nothing to do;
- last, its `Next:` line, as CONTRIBUTING.md says, as in "Next: the night build, at 00:30, builds
  #250."

## Which runs also send it to the phone

Two, by the `PushNotification` tool, just before the message that ends the turn. No other run
pushes anything.

- **The coordinator's morning run** sends the day's digest. Under the same four heads, what
  merged, what waits on the maintainer, Decided for you and Faults, it gives its own and those of
  every run since the last morning run: it reads each end line on the run log written since the
  last morning run's end line (the coordinator's line whose start line says "the morning run"),
  and of a line written before it and edited since (the comment's `updated_at`), only a fault or a
  hold that yesterday's digest did not give,
  and, for each issue an end line names after "Decided for you", the "Decided by the run" line in
  that issue's Decisions. Under Faults, each fault an end line names after `Fault:` is said once,
  with the number of runs that met it: one fault two lines say in different words is counted as
  one. With nothing merged, nothing waiting, nothing decided and no fault, the digest is one
  line.
- **A run of the coordinator's that the maintainer started**, by an answer, a `Change:`, an
  `Idea:`, a release or a `Resume:`, sends its own debrief: they wait for it. A builder's run
  sends none, an answer build included.

## A run the hook holds after its end line

The Stop hook holds a run that would end with `guard` running, a helper agent out, or no `Next:`
line, and logs each hold. A run held after it wrote its end line does what the hook asks, runs
`python3 tools/stop_hook.py --holds` again, and edits its end line to carry what that prints, with
the time it now ends. It edits the one line: it never adds a second.

## A fault met after its end line

A run that meets a fault once its end line is written, a push that fails among them, edits that
one line to carry it, as for a hold.

## A run woken after its debrief

It sends no push, adds no second line to the run log, and ends in one line, which begins
`Next:`.

## A dry run

It takes none of the three steps. Its last message says what it would have done, step by step,
and ends with the `Next:` line it would have sent.
