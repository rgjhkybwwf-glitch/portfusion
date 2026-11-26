---
name: beat
description: "Any run: asks for the run's brief, then writes the run's start line and its end line on the run log, in the form the dashboard reads."
---

# The beat

**Each run writes two lines on the run log**: one as it starts, and one as it ends, which gives
when it began and ended, UK time, what it did in a line, each fault it met, the issues it decided
a choice on, each page it published, and its `Next:` line. They are the source for which run is
at work, a run's length, its stops and its faults, and for the morning's digest; they ask nothing
and ping no one.

Both are comments on the run log. Each opens with the run's mark, as the runs table gives it, then
a date and a time, UK time.

## The brief

Before anything else, the run asks for its brief, with the text it was started with if the gate
started it:

`python3 tools/brief.py builder` · `python3 tools/brief.py coordinator "Answer: …"`

It reads GitHub once, writes nothing, and prints in a few lines: the run's row, cap and mark;
whether the loop is paused; the level's last end line; the agent's open pull requests, each with
its `guard`; and every line under Next with its labels, its plan, its own pull request and its open
"waits". A builder is told the line to take. The coordinator is told how many plans stand, and
what changed since its last run began: what merged and closed, what was filed, whose comments are
on which issues, a start the gate failed to make, a tag, an open `Idea:`, a `building` label that
is too old, and whether a Queue review is due.

What the brief says, the run does not read again to find out: a builder does not read the Queue,
and no run reads the run log or the list of the gate's runs. It still reads whole each issue,
comment and pull request it acts on. What the brief lists under "Not read", and all of it when the
brief fails, the run reads as its role book says.

## The start line

The run's first act on GitHub:

`🌙 **Builder** · start · 17 Nov 00:30 · building the first planned line`

After the word `start`: the date, the minute the run began, and in a few words what it sets out
to do. A run the gate started says there what started it: an answer, an idea, a release, a
re-plan, a `Resume:` or the coordinator's "Build:". The coordinator's morning run says "the
morning run" there: the next morning's digest reads from its end line.

## A paused loop

Before the start line, the brief says whether the Queue carries `paused`; without a brief, read
the Queue's labels. While it carries `paused`, a run its routine's clock started writes neither
line and does nothing: it ends in one line, which begins `Next:` and says the loop is paused. The
gate starts no run in a pause, so only a clock's run meets one.

## The end line

Written by the skill `end-of-run`, once nothing is left to wait for:

`🌙 **Builder** · 17 Nov 00:30–01:17 · built #250, merged · Decided for you: #250 · Next: …`

The mark, the date, when the run began and ended, what it did in a line, then "Decided for you:"
and each issue the run decided a choice on (left out when it decided nothing), each page it
published after `Page:` (left out when it published none), and its `Next:` line. A hold and a
fault, when the run had one, go between what it did and "Decided for you:", the hold first, as
below. The morning's digest is put together from these lines.

A run the Stop hook held says so after what it did, in the hook's own words, as in
"· built #250, merged · held 1× for `guard`, 12 min · Next: …". The skill `end-of-run` says where
the words come from; a run that was never held leaves the part out.

A run that met a fault says so next, after the word `Fault:`, as in "· planned #250 · held 1× for
a helper, 3 min · Fault: security alerts, not readable from this session · Decided for you: #250 ·
Next: …". A fault is the loop's own: a rule the run could not
follow as written, or a tool or an access its rules call for, and give no way round, that failed
it. A red guard, a plan the checker refused and a question are the work, and are no fault. The
part is one line: each fault in a few words, the tool or the place first and then what it did, two
faults parted by `;`. A run that met none leaves the part out.

**A page a run publishes is named on its end line**, after "Decided for you:" and before `Next:`,
after the word `Page:`, by its title and link, as in "· Fault: … · Decided for you: #145 · Page: A
spread bet's life https://claude.ai/artifact/… · Next: …". Two pages are parted by `;`, and a
title loses any `·` or `;` it holds, so the line still parts where it should. A routine runs
outside the maintainer's project, so a page it publishes with the Artifact tool is private to
their account but missing from the project's list of pages; the project copies in each page an
end line names. The issue the page is for links it too. A run that published none leaves the part
out.

The time it began is the start line's, to the minute: the two lines are paired by it. The time
stays first after the mark; a run started for a re-plan says so after its time.

A dry run writes neither line.
