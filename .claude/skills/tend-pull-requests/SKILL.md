---
name: tend-pull-requests
description: "Builder: before a new issue, brings each of the agent's own open pull requests level with main and makes it green (CONTRIBUTING.md, Which issues)."
---

# Tending its own pull requests

The rule is in `CONTRIBUTING.md`, The loop, Which issues, in what order: its own open
pull requests come first.

Before a new issue, for each open pull request from a branch whose name begins claude/:

1. **Level with `main`**: `main` is merged in, never rebased. A pushed commit is never rewritten.
2. **Its pictures**: retaken when a page it changed moved under it (the skill `pictures`).
3. **Its CI**: made green, waited for in the foreground. One that will not go green at a second
   attempt is left as a draft, with what blocks it at the top.
4. **A `Change:` on it**: left for the coordinator, which records it and plans again.
5. **A `hold` on it**: kept level and green, nothing added to it, and its auto-merge left off
   until the maintainer's `Resume:` takes the label off.
6. **A draft whose top names nothing that blocks it** (a run ended before its review came back):
   the skill `review-and-merge`, from its start.

So none waits on the maintainer for anything but what it asked of them. An open pull request of an
issue that is not under Next is kept level and green, and nothing is added to it.

A pull request that waits for the maintainer to enable auto-merge is never turned on by the agent.
