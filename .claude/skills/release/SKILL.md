---
name: release
description: "Builder: makes a release's pull request, says what the maintainer does to tag it, and opens the next version after the tag."
---

# The release, the tag and the next version

- **The release's pull request names the release**, after the release's read (the skill
  `release-read`). It waits for the maintainer, since a tag follows it.
- **The checklist is never closed.** Its pull request says "For #156", not "Closes", and ticks
  its boxes.
- **The tag and the milestone are the maintainer's.** They tag the release's merge and close the
  milestone; no cloud session can push a tag.

## The release's pull request

- `__version__` in `src/portfusion/__init__.py` loses its `.dev0`.
- `CHANGELOG.md`'s Unreleased becomes the release's entry, `## N.N.N — beta, D Mon YYYY`, dated
  the day it merges.
- The README installs `vN.N.N`.

`test_about.py` holds the three together.

## The tag

The maintainer tags `vN.N.N` on the release's merge, in the GitHub app: Releases, Draft a new
release, and closes the milestone. No cloud session can push a tag. The release's pull request
says, at its top, each issue still open in the milestone, so none is left in it when it closes.

## After the tag

Once the release is tagged, its milestone closed and the next milestone's lines moved to Next
(the skill `open-milestone`), a builder opens the next version: a pull request that sets
`__version__` to the next milestone's number with `.dev0` and puts an empty Unreleased above the
release's entry, opened as a draft and taken to its end by the skill `review-and-merge`. It
merges only when the maintainer enables auto-merge, since it changes `__version__`.
