---
name: slice-a-feature
description: "Coordinator: turns a feature's decided shape into two to six slices, each an issue that leaves main green and stays hidden until the last."
---

# Slicing a feature

- **A decided shape becomes slices**, each an issue "Part of #n" that leaves `main` green with its
  own changelog line. The last slice's pull request closes the feature too.
- **A slice stays hidden until the last**: nothing registers it on a page, a tab or the report.
  One that moves the store or a figure is the exception (the skill `review-and-merge`, Three are
  never clean). The last slice turns the feature on. Its walk is the trial walker's, over the
  whole feature by its Trial jobs
  ([`.claude/agents/trial-walker.md`](../../agents/trial-walker.md)), and its pull request shows
  the maintainer each page's picture before and after.

1. **Complete the feature**: its Shape is the option chosen on its design card, quoted with the
   date, with the options declined; then its Reach, Slices, Introduction and Trial.
2. **Write each slice as an issue**, "Part of #n", that meets the Definition of Ready and leaves
   `main` green with its own changelog line. Its Decisions quote the card. Its Cause is what the
   code lacks, by file and function.
3. **Its labels** are the feature's, **and its milestone** the release its card's answer names, or the
   one the feature stands in where its card asked none. Where that is not the one the feature stands in, the feature moves there first, its line
   with it, and the arc's rows in `docs/direction.md` are edited to the answer as a gate
   review's are (the skill `gate-review`, Applying its answer).
4. **Place them** at the feature's line, in order, wherever that stands in the Queue (the skill
   `place-an-issue`).
5. **The last slice** turns the feature on: its pull request closes the feature too, and its line
   is ticked with the slice's.

Slices are written only when no other feature's slices stand open under Next: one feature is
being built at a time (the skill `design-card`).
