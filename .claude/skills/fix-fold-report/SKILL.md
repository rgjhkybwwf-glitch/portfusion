---
name: fix-fold-report
description: "Builder: what to do with a find the change did not cause. Fix it there when it is small and in a file the change touches, else fold it onto the issue that covers it, else report it (CONTRIBUTING.md, Building)."
---

# A find outside the change: fix, fold, then report

The rule is in `CONTRIBUTING.md`, The loop, Building: a builder files no issue and
writes neither the Queue nor the walk finds. What it meets outside its issue takes the first of
these three that fits.

A find **the change caused** is not one of these: it is the change's to fix, in this pull request.
Nor is a finding of the `code-review` skill's that the rule in `CONTRIBUTING.md`, Commits and pull
requests, leaves: that one is left, and listed nowhere. A Pre-existing finding judged wrong is
neither fixed nor folded: it is reported (step 3), with why it is judged wrong.

## 1. Fix

A small find in a file the change already touches is fixed in this pull request, in a commit of
its own. Small is a few lines that need no plan: no new function, no figure moved, no store
change, nothing that would change the pull request's tier. The pull request lists it under
**Also fixed**, a line each with the file.

## 2. Fold

Otherwise it goes onto the open issue that covers it, as a comment of evidence: what was met,
where, and the pull request it was met in. "Covers" is by the code: the issue's Cause or Done
names the same file and function. The pull request lists it under **Folded**, with the issue.

## 3. Report

The rest go in the pull request's description, under **Reported**, a line each, written so the
coordinator can act on it without opening the code again:

`- <page or file, and function>: <what was met, and what was expected> (<how it was met: the walk, the review, the build>)`

A cold walk's finds are reported the same way. So is something a comment of the maintainer's
raises outside the issue, quoted. The coordinator sorts what is reported at its next run (the
skill `keep-the-queue`): it files what earns an issue, and says what it dropped.

A pull request with nothing under a heading leaves the heading out. A run that is going nowhere
stops and says so: it reports no finds to show work.
