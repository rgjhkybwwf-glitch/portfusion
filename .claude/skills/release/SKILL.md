---
name: release
description: "Builder: makes a release's pull request, says what the maintainer does to tag it, and opens the next version after the tag (CONTRIBUTING.md, Which issues)."
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

Once the release is tagged, its milestone closed and the next milestone's lines moved to Next
(the skill `open-milestone`), a builder opens the next version: a pull request that sets
`__version__` to the next milestone's number with `.dev0` and puts an empty Unreleased above the
release's entry. It merges only when the maintainer enables auto-merge, since it changes
`__version__`.
