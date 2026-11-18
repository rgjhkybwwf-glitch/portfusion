---
name: release-read
description: Reads a release's guides whole before its tag, one reader to a guide and one writer, and ticks what its pull request must show (CONTRIBUTING.md, Commits and pull requests).
---

# The release's read

The rule is in `CONTRIBUTING.md`, Commits and pull requests: a release's guides are read whole
before its tag.

1. **Start from the guides left behind**: those the pre-push hook names as left behind since the
   last tag (`behind()` in `src/portfusion/hooks/pre_push.py`, its base the tag).
2. **One reader to a guide**, each running its commands and opening its paths.
3. **One writer** makes the changes.
4. **Its pull request ticks**, for `README.md`, `CONTRIBUTING.md`, `CLAUDE.md` and each guide in
   `docs/` but the audit's log:
   - [ ] the way in, the folder map and the commands hold;
   - [ ] the glossary has every word the milestone changed and none it retired;
   - [ ] the changelog's entry says what a book's owner needs before moving;
   - [ ] the desk's Method and each page's help agree;
   - [ ] history, finished plans and decided questions are gone;
   - [ ] each document's lines before and after.
