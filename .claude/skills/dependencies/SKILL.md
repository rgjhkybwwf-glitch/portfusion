---
name: dependencies
description: "Coordinator: turns each Dependabot bump that does not merge itself, and each security alert, into an issue that meets the Definition of Ready (CONTRIBUTING.md, The ready check)."
---

# Keeping the dependencies

The rule is in `CONTRIBUTING.md`, The loop, The ready check. A Dependabot pull request
that stays in its major version merges itself (`dependabot-merge.yml`); this looks after the rest.

Each of these becomes an issue, unless an open issue covers it (the skill `shape-an-issue`):

- an open Dependabot pull request left for the maintainer: a major or a 0.x bump;
- one that has been red, or behind `main`, for a week;
- an open Dependabot security alert. They are read by REST, which a cloud session's `gh` allows
  where its GraphQL and the GitHub tools cannot reach them:
  `gh api "repos/rgjhkybwwf-glitch/portfusion/dependabot/alerts?state=open" --paginate`. A call
  that is refused, or fails, is a fault, said on the run's end line (the skill `beat`) with the
  command's own error; a list read and empty is none. Dependabot's security updates are on, so an
  alert with a fix also comes as its own pull request, above.

The issue:

- **Cause**: what the release notes change that this repository uses, by file.
- **Done**: each test that leans on the package is shown still able to fail.
- **Its pull request** makes the bump and closes Dependabot's, which is never merged on its own.
  It moves the lock file, so it waits for the maintainer.

It is placed by the skill `place-an-issue`.
