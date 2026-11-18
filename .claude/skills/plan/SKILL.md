---
name: plan
description: Writes an issue's plan, has the plan checker check it against the code, and posts it as Plan, checked (CONTRIBUTING.md, The ready check and Building). The ready check's alone; a builder never writes one.
---

# The plan and its check

The rules are in `CONTRIBUTING.md`, The nightly agent: when a line is planned (The ready check),
and when a plan stands and who builds on it (Building).

## Writing it

The plan is a comment on its issue, against today's `main` and the issue's branch if it has one.
It names:

- the files it will change;
- how each "Done" check will be made;
- the desk pages whose walk pictures it means to move, or none;
- what it will not touch;
- **its overlaps**: every open issue and open pull request whose Cause, Done or diff names a file
  or function the plan changes. Each is settled in the issue: a "waits" in Order when one must
  land first, a line in Not in scope when the other owns that part, or a question when the two
  issues' Done disagree;
- **the content map**, when the change adds or removes a page or a report section, or moves a
  job, or part of one, between them: `docs/content-map.md` is among its files, with the table that
  changes.

## Checking it

The plan checker ([`.claude/agents/plan-checker.md`](../../agents/plan-checker.md)), given only the
issue and the plan, checks it against the code, and looks for an overlap the plan missed and holds
it to the content map. The plan is mended from what it finds.

## Posting it

- **No question**: posted as **Plan, checked**, naming the commit of `main` it was checked
  against, and the issue takes `planned`.
- **Its only open points are its questions**: posted as **Plan, checked, if answered as
  recommended**, and asks them (CONTRIBUTING.md, Asking and answering); the issue takes `planned`
  and `decision`. So are asked the questions the issue was filed with, less any the maintainer
  has answered in a comment since.
- **The issue's cause or premise no longer holds**: it asks that, and posts no plan.
