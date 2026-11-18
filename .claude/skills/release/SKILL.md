---
name: release
description: Makes a release's pull request, says what the maintainer does to tag it, and opens the next milestone and version after the tag (CONTRIBUTING.md, Which issues, in what order).
---

# The release, the tag and the next version

The rules that call for each step are in `CONTRIBUTING.md`, The nightly agent, Which issues, in
what order.

## The release's pull request

- `__version__` in `src/portfusion/__init__.py` loses its `.dev0`.
- `CHANGELOG.md`'s Unreleased becomes the release's entry, `## N.N.N — beta, D Mon YYYY`, dated
  the day it merges.
- The README installs `vN.N.N`.

`test_brand.py` holds the three together.

## The tag

The maintainer tags `vN.N.N` on the release's merge, in the GitHub app: Releases, Draft a new
release, and closes the milestone. No cloud session can push a tag.

## After the tag

A night run or ready check that finds the release tagged and its milestone closed first moves the
Queue's lines (#206) from after the gate to Next, in the order answered, the checklist last.

A night run also opens the next version: a pull request that sets `__version__` to the next
milestone's number with `.dev0` and puts an empty Unreleased above the release's entry. It merges
itself once `guard` is green.
