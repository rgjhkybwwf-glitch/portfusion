---
name: build-an-issue
description: "Builder: builds one planned issue on a plan that stands. It claims the issue, works one branch by the conventions, runs the guard and opens one pull request (CONTRIBUTING.md, Building)."
---

# Building an issue

The rules are in `CONTRIBUTING.md`, The loop, Building, and the conventions above it. A
builder builds only on a plan that stands, and never writes its own.

## 1. Read it whole

The issue, its comments included, and its latest **Plan, checked**.

## 2. Confirm the plan still stands

From the diff of `main` since the plan's commit, in the files the plan names:

- A new line in `CHANGELOG.md`, the Queue, or a hunk away from the functions and tests the plan
  names leaves it standing. Build on today's `main`.
- A change to what the plan relies on does not. Leave a comment whose first line after the run's
  name is "Re-plan:" and why, take `planned` off, and move to the next line.

A line with no plan is left for the coordinator, and named in the debrief.

## 3. Claim it

Label the issue `building` before the first step on the issue, its branch or its pull request.
Take the label off on leaving the issue: its pull request clean or left for the maintainer, or the
issue stopped.

## 4. One branch

A branch `claude/<name>` from the latest `main`. An issue with a branch of its own continues on
it, brought level with `main` by merging. An open pull request from it is completed to the whole
issue, its own "Part of #n" made "Closes #n"; a slice's "Part of" its feature stays.

## 5. The work

By the conventions: one logical change a commit, a line under Unreleased in `CHANGELOG.md`,
each commit's diff reviewed before it is pushed (step 6).

- **A choice the issue did not make**: decided or asked by the skill `ask-or-decide`.
- **A find outside the change**: the skill `fix-fold-report`.
- **A changed desk page**: walked cold before the pull request opens (the skill `cold-walk`). The
  slice that turns a feature on is walked by the trial walker
  ([`.claude/agents/trial-walker.md`](../../agents/trial-walker.md)), over the whole feature by its
  Trial jobs, and its pull request shows each page's picture before and after.
- **The release checklist**: the skills `release-read` and `release`.

## 6. The review, the guard, then one pull request

Before each push, the `code-review` skill reviews the branch, at the level the branch's tier
takes (`python3 tools/tiers.py $(git diff --name-only origin/main...)`): `low` for tier 0,
`medium` for tiers 1 and 2, `high` for tier 3. `CONTRIBUTING.md`, Commits and pull requests, says
what comes first in a cloud checkout, and what is done with a finding by its severity (Important,
Pre-existing or Nit). For a builder:

- The review is given no target, so it reads the whole branch each time, and one review before a
  push covers every commit not yet pushed.
- A fix is a new commit, reviewed in turn.
- A Pre-existing finding takes the skill `fix-fold-report`, unless the rule in `CONTRIBUTING.md`,
  Commits and pull requests, leaves it.

The skeptic reviewer still reads the Done checks once it opens (`review-and-merge`).

Run the guard, and the desk walk if a desk file changed. Open one pull request that says
"Closes #n" ("For" the release checklist, which is never closed), with any choice the run decided
at its top. Then the skill `review-and-merge`.

No issue goes past a second attempt at a green guard: one that will not go green is left as a
draft pull request with what blocks it at the top, and the run moves on.
