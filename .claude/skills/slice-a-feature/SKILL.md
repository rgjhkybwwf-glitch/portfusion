---
name: slice-a-feature
description: "Coordinator: turns a feature's decided shape into two to six slices, each an issue that leaves main green and stays hidden until the last (CONTRIBUTING.md, Features)."
---

# Slicing a feature

The rules are in `CONTRIBUTING.md`, The loop, Features: a decided shape becomes slices,
a slice stays hidden until the last, and one feature is being built at a time.

1. **Complete the feature**: its Shape is the option chosen on its design card, quoted with the
   date, with the options declined; then its Reach, Slices, Introduction and Trial.
2. **Write each slice as an issue**, "Part of #n", that meets the Definition of Ready and leaves
   `main` green with its own changelog line. Its Decisions quote the card. Its Cause is what the
   code lacks, by file and function.
3. **Its labels and milestone** are the feature's.
4. **Place them** at the feature's line, in order, wherever that stands in the Queue (the skill
   `place-an-issue`).
5. **The last slice** turns the feature on: its pull request closes the feature too, and its line
   is ticked with the slice's.

Slices are written only when no other feature's slices stand open under Next.
