---
name: end-of-run
description: "Any run: the run's last three steps, in order, once nothing is left to wait for. It stops watching its pull requests, writes its end line on the run log, and sends the debrief, whose last line begins Next."
---

# Ending a run

**When nothing is left to wait for, the run takes its last three steps**: it stops watching each
pull request it leaves, writes its end line on the run log, then ends its turn with the debrief.
None of the three is ever done while something is still running.

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

Each page the run published goes after "Decided for you:" and before `Next:`, after the word
`Page:`, by its title and link, as the skill `beat` gives it. A run that published none leaves
the part out.

## 3. The debrief

A few lines, the message that ends the turn:

- what merged;
- what waits on the maintainer: a question, or a pull request for them to enable auto-merge on;
- **Decided for you**: each choice the run made in place of a question (the skill
  `ask-or-decide`), a line each with its issue, so the maintainer can reverse one with `Change:`.
  Left out when the run decided nothing;
- **Faults**: each fault the run met, in one line, in its end line's words. Left out when it met
  none;
- **Pages**: each page the run published, by its title and link. Left out when it published none;
- or, with nothing merged, waiting, decided or published, that the run had nothing to do;
- last, its `Next:` line. **Its last line begins with the word `Next:`**, then who acts next, on
  what, and when, as in "Next: the night build, at 00:30, builds #250." When no line under Next
  can be built, it names each line and what holds it: a question (whose), no plan yet or a
  "Re-plan" (the coordinator's), `building` (which run), an open pull request, a "waits" or the
  gate.

While a gate review stands unanswered, or a release untagged, the debrief says in one line what
the run waits on.

## Which runs also send it to the phone

**Only the coordinator sends a debrief to the maintainer's phone, and only for two kinds of
run**, by the `PushNotification` tool, just before the message that ends the turn. No other run
pushes anything.

- **The coordinator's morning run** sends the day's digest. Under the same five heads, what
  merged, what waits on the maintainer, Decided for you, Faults and Pages, it gives its own and
  those of every run since the last morning run, and any start the gate failed to make: it reads
  each end line on the run log written since the end line of the morning run before it (the
  coordinator's line whose start line says "the morning run", or where none does, its last that
  began before 08:00 on a weekday), and of a line written before that and edited since (the
  comment's `updated_at`), its faults, holds and pages alone, each said as added since, and, for
  each issue an end line's `Decided for you:` part names, up to its next `·`, the "Decided by the
  run" line in that issue's Decisions. Under Faults, each fault an end line names after `Fault:` is said once,
  with the number of runs that met it: one fault two lines say in different words is counted as
  one. With nothing merged, nothing waiting, nothing decided, no fault and no page, the digest is
  one line. It reads the last four days of the run log, never the whole of it: `gh api --paginate
  "repos/{owner}/{repo}/issues/289/comments?since=<four days ago>T00:00:00Z&per_page=100"` returns
  each line written or edited since, a weekend and a missed morning included, and of those it
  takes the lines this rule names.
- **A run of the coordinator's that the maintainer started**, by an answer, a `Change:`, an
  `Idea:`, a release or a `Resume:`, sends its own debrief: they wait for it. A builder's run,
  an answer build included, and a re-plan a run began send none: what they did is in the run log,
  and in the next morning's digest.

## A run the hook holds after its end line

The Stop hook holds a run that would end with `guard` running, a helper agent out, or no `Next:`
line, and logs each hold. A run held after it wrote its end line does what the hook asks, runs
`python3 tools/stop_hook.py --holds` again, and edits its end line to carry what that prints, with
the time it now ends. It edits the one line: it never adds a second.

## A fault met after its end line

A run that meets a fault once its end line is written, a push that fails among them, edits that
one line to carry it, as for a hold. A page it publishes after its end line is carried the same
way, after `Page:`.

## A run woken after its debrief

It sends no push, adds no second line to the run log, and ends in one line, which begins
`Next:`.

## A dry run

It takes none of the three steps. Its last message says what it would have done, step by step,
and ends with the `Next:` line it would have sent.
