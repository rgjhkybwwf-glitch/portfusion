---
name: plan
description: "Coordinator: writes an issue's plan, has the plan checker check it against the code, and posts it as Plan, checked (CONTRIBUTING.md, Building). A builder never writes one."
---

# The plan and its check

The rules are in `CONTRIBUTING.md`, The nightly agent, Building: a plan, checked, before code, and
when a plan stands.

## Which lines

Every line under Next, in order, so each build has a plan:

- A line marked "Re-plan" first, then each line whose "waits" have closed, until as many carry
  `planned` as the run's cap, those already standing included.
- Each line's questions are settled as it is reached, a line whose "waits" are still open
  included, so an answer is in before its turn comes (the skill `ask-or-decide`).
- Skipped: a feature, an issue labelled `planned`, `building` or `hold`, and one whose questions
  stand asked and unanswered. An issue with an open pull request of its own is planned only when it is
  marked "Re-plan", against that pull request's branch.

The issue carries `building` while it is planned.

## Writing it

The plan is a comment on its issue, against today's `main` and the issue's branch if it has one.
It names:

- the files it will change;
- how each "Done" check will be made;
- the desk pages whose walk pictures it means to move, or none;
- what it will not touch;
- **its overlaps**: every open issue and open pull request whose Cause, Done or diff names a file
  or function the plan changes. Each is settled in the issue: a "waits" in Order when one must
  land first, or a line in Not in scope when the other owns that part. Two issues whose Done
  disagree are decided (the skill `ask-or-decide`);
- **the content map**, when the change adds or removes a page or a report section, or moves a
  job, or part of one, between them: `docs/content-map.md` is among its files, with the table that
  changes.

## Checking it

The plan checker ([`.claude/agents/plan-checker.md`](../../agents/plan-checker.md)), given only the
issue and the plan, checks it against the code, looks for an overlap the plan missed, and holds
it to the content map. The plan is mended from what it finds.

## Posting it

- **Nothing left to ask**: posted as **Plan, checked**, naming the commit of `main` it was checked
  against, and the issue takes `planned`. What the run decided on the way is in the issue's
  Decisions, as decided by the run.
- **A question that must be asked is its only open point**: posted as **Plan, checked, if answered
  as recommended**, with the question asked; the issue takes `planned` and `decision`.
- **The issue's cause or premise no longer holds**: no plan is posted. The issue is closed with
  the reason, or re-shaped to what does hold, as the skill `ask-or-decide` says.
