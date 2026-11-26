<!-- state -->
Where it stands: what it waits for, or that it merges itself once `guard` is green.
<!-- /state -->
<!-- Between the state marks, each on a line of its own: `notify.yml` rewrites it when the pull
     request merges or closes (the skill `review-and-merge`). -->

## What and why

<!-- One logical change, for a reader who was not there. Link the issue it was agreed in. -->

Agreed in: #

Pictures: none
<!-- The desk pages whose walk pictures this change means to move, from its plan, as
     `Pictures: bench, dashboard`; `baselines.yml` retakes those and refuses any other. -->

## Checks

- [ ] The change was agreed first, in an issue or with the maintainer
- [ ] Each commit's diff was reviewed by the `code-review` skill before it was pushed, at the level its tier takes (CONTRIBUTING.md, Commits and pull requests), at: <!-- low, medium or high --> . Findings answered as the rule takes them, and what stands is listed above
- [ ] The guard passes on the demo, run unpiped: `PORTFUSION_BOOK=demo python3 -m pytest`
- [ ] The linter is clean: `python3 -m ruff check`
- [ ] A test holds it where it could break silently, extending an existing test where one fits
- [ ] A line under **Unreleased** in `CHANGELOG.md`, if a user would notice it
- [ ] What the desk shows and what the report shows still agree
- [ ] Every example is invented: nothing of a real book's people, holdings, figures or dates
