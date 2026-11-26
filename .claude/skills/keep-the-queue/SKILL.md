---
name: keep-the-queue
description: "Coordinator: keeps the Queue. Each run it ticks what merged and sorts what the builders reported; on Monday and Thursday it reviews the whole Queue, acts, and posts what it did."
---

# Keeping the Queue

- **The milestone being worked is the lowest open milestone.** The Queue's Next holds only its
  lines and ends with the release checklist, which stays open: each release ticks it, and the
  release's pull request links to it.
- **The coordinator keeps the Queue current**: each run it ticks the line of each pull request
  merged since its last and moves it to Done, and sorts what the builders reported. It reads the
  Queue afresh just before each edit, since the maintainer may have changed it. A line the
  maintainer placed, by hand or by an answer, is never moved. Such a line ends `· yours`, or,
  written before that mark, says in its brackets that the maintainer placed it.
- **The Queue holds what is live.** A line is one short line (the skill `place-an-issue`), a
  milestone's heading one sentence of what it is for, and Done only the milestone being worked. A
  wait met, a line that left and a review answered leave no note: GitHub keeps every edit.

What it does here is decided and told, not asked (the skill `ask-or-decide`): each act is listed,
and the maintainer reverses one with `Change:`.

## Each run

1. **Tick what merged.** For each pull request merged since the run's last, tick its issue's
   line and move it to Done, in a few words with the pull request's number. Delete each "waits"
   now met.
2. **Sort what was reported.** Read the **Reported** list of each of the agent's pull requests
   opened or merged since the run's last (the skill `fix-fold-report`), and give each find one of
   four ends, the first that fits:
   - **Folded** onto the open issue that covers it, as evidence, or onto the decided feature that
     will rework its page. "Covers" is by the code (the skill `shape-an-issue`).
   - **Filed**, when it earns an issue: a wrong figure, or a fault the owner of a book would
     meet; a break of a stability rule or of what a guide promises; or something that blocks or
     changes a line in the Queue. Finds of one cause make one issue. It is shaped to the
     Definition of Ready (`shape-an-issue`) and placed (`place-an-issue`).
   - **Held** on the walk finds, one line: how a page reads or looks, and too small for an issue
     of its own. The review gathers these.
   - **Dropped**, with the reason: by design, or not worth the change.
3. **Say so**, in one comment on that pull request, headed "Reported finds, sorted", a line a
   find with its end. A pull request that carries the comment is not sorted again. The debrief
   gives the counts: filed, folded, held and dropped.

## The review, on Monday and Thursday

**On Monday and Thursday it reviews the whole Queue, and acts**: on the morning run of a Monday
and of a Thursday, and not while a gate review stands unanswered. None of it is asked. It reads
every open issue against today's `main`, by the wide reader
([`.claude/agents/wide-reader.md`](../../agents/wide-reader.md)), which returns a short list, and
then acts:

- **Duplicates are merged**: the later issue is closed as a duplicate, and its evidence and
  Decisions are carried to the one kept.
- **Overlaps by file and function** that no "waits" orders get their "waits".
- **A cause that no longer holds** closes its issue, with what on `main` ended it.
- **An issue with no line** is placed (`place-an-issue`).
- **The walk finds are gathered**: three or more held for one page, or any for a page the next
  milestone works, become one issue or join the feature that reworks the page. Each line handled
  is removed, so the list holds only what waits; the review's post says where each went.
- **The sizes are kept**: the Queue's body under 15,000 characters, and each open issue's body
  under 8,000, measured by `gh api --paginate "repos/{owner}/{repo}/issues?state=open&per_page=100"
  --jq '.[] | select(.pull_request | not) | [.number, (.body | length)]'`.
  One over is trimmed by the rules that write it: a line by `place-an-issue`, Decisions by
  `record-answer`, a feature's sections by `shape-an-issue`.
- **The order is kept**: a line a run placed is moved when the order of the work asks it. A line
  the maintainer placed is not.
- **Work set aside has a home**: the Not in scope and Decisions of each issue closed since the
  last review, and the descriptions of the pull requests that closed them, are read for work put
  off as a later step, by the wide reader in the same read. Each item no open issue covers is
  filed, folded or dropped with the reason, as a reported find is (Each run, above).

What it never does unasked: cut a line from a milestone, add a feature the arc does not name, or
change what a milestone is for. Those are the gate review's questions (the skill `gate-review`).

It then posts a **Queue review** on the Queue: what it merged, ordered, closed, placed and
gathered, a line each with the reason, and the count of open issues beside the last review's.
The Queue takes no `decision` for it, so it pings no one, and it lists no ideas. The review
before it is then cut to one line, as in "Queue review of 23 Nov 2026, replaced by <link>", and
the comment's edit history keeps the rest. Only a run's own comment is cut, never the
maintainer's, and a cut starts no run: the gate reads only a comment as it is made.

## A `Change:` on the Queue

The maintainer's `Change:` under a review, or on an issue the review closed or moved, is recorded
(the skill `record-answer`) and applied here, not built: the issue is reopened, the line put
back, the "waits" taken off. The Queue takes no Decisions section: `· yours` says the maintainer
placed a line, and the issue's placing comment says who else did and why.
