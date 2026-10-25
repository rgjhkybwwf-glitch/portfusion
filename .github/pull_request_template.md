## What and why

<!-- One logical change, for a reader who was not there. Link the issue it was agreed in. -->

Agreed in: #

## Checks

- [ ] The change was agreed first, in an issue or with the maintainer
- [ ] The guard passes on the demo, run unpiped: `PORTFUSION_BOOK=demo python3 -m pytest`
- [ ] The linter is clean: `python3 -m ruff check`
- [ ] A test holds it where it could break silently, extending an existing test where one fits
- [ ] A line under **Unreleased** in `CHANGELOG.md`, if a user would notice it
- [ ] What the desk shows and what the report shows still agree
- [ ] Every example is invented: nothing of a real book's people, holdings, figures or dates
