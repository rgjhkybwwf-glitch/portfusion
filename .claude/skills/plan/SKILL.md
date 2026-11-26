---
name: plan
description: "Coordinator: has the plan drafter draft an issue's plan from the code, settles it, has the plan checker check it, and posts it as Plan, checked. It holds when a plan stands. A builder never writes one."
---

# The plan and its check

- **A plan, checked, before code, and the coordinator's.** The plan is the issue's latest
  **Plan, checked**, which names the commit of `main` it was checked against. It stands while
  `main` has not changed what it relies on since that commit, no answer recorded since changes
  what it assumed, and no "Re-plan" comment follows it. A builder builds only on a plan that
  stands, and never writes its own: a line without one it leaves for the coordinator, and names
  it in its debrief.
- **Every line under Next is planned ahead, in order, so each build has a plan**, until as many
  lines carry `planned`, with no ready pull request of their own, as the run's cap.

## Which lines

Every line under Next, in order:

- A line marked "Re-plan" first, then each line whose "waits" have closed, until as many carry
  `planned` as the run's cap, those already standing included. A line whose issue's own pull
  request is open and ready, not a draft, is built and holds no place. A line marked "Re-plan"
  holds a place whatever its pull request's state.
- Each line's questions are settled as it is reached, a line whose "waits" are still open
  included, so an answer is in before its turn comes (the skill `ask-or-decide`).
- Skipped: a feature, an issue labelled `planned`, `building` or `hold`, and one whose questions
  stand asked and unanswered. An issue with an open pull request of its own is planned only when it is
  marked "Re-plan", against that pull request's branch.

The issue carries `building` while it is planned.

## Writing it

The run puts the checkout on the latest `main` and starts the plan drafter
([`.claude/agents/plan-drafter.md`](../../agents/plan-drafter.md)) with the issue and that commit
of `main`, which is the commit the plan will name. For a line marked "Re-plan" it says too why
the last plan fell: the "Re-plan" comment, or the answer recorded or the change on `main` since.
The checkout does not move while a drafter or the plan checker is out; two drafts may be out
together.

The drafter reads the code, and the diff of the issue's own pull request where it has one, and
returns a draft with a file and line for each claim, and under Open what the code did not settle.
The run reads the issue and the draft, not the code again: it opens a file only where the draft's
Open, or a claim it doubts, sends it. It settles each open point (the skill `ask-or-decide`), and
the plan is its own: the drafter decides nothing and posts nothing. A draft that names another
commit, or says it could not read a part the plan rests on, is drafted again, once; after that
the run reads that part itself.

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
- **A plan replaces the one before.** Once it is posted, the issue's earlier plan comment is cut to
  one line that opens with the run's mark, as in "📋 **Coordinator** · Plan of 24 Nov 2026, replaced
  by the plan of 26 Nov 2026 <link>"; the old plan stays whole in the comment's history. The line
  never carries a plan's heading, so the brief does not read it as a plan.
- **The issue's cause or premise no longer holds**: no plan is posted. The issue is closed with
  the reason, or re-shaped to what does hold, as the skill `ask-or-decide` says.
