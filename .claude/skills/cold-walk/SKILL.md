---
name: cold-walk
description: "Builder: has the cold walker walk a changed desk page before its pull request opens, and fixes, folds or reports what it finds (CONTRIBUTING.md, Commits and pull requests, and Building)."
---

# The cold walk

The rule is in `CONTRIBUTING.md`, Commits and pull requests: a changed desk page is walked cold
before its pull request opens.

1. Serve the demo's desk on this machine (`portfusion desk --book demo --port 8769`).
2. Give the cold walker ([`.claude/agents/cold-walker.md`](../../agents/cold-walker.md)) the
   desk's address, a scratch folder for its pictures, the rows of
   [`docs/ux-audit.md`](../../../docs/ux-audit.md) the change means to close, and jobs about the
   change, in the owner's words. The walk keeps to the pages the change touched.
3. Each find is fixed, folded or reported, by the skill `fix-fold-report`.
4. The pull request lists the finds and where each went, and says which of the audit's rows the
   walk found closed.
