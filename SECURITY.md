# Security

PortFusion keeps a book's record on the owner's own machine, and its desk can be served to
readers beyond it. A fault that would let someone read a book they were not given, write to one
without the owner's approval, or take a credential from it is a security fault.

## Reporting one

Report it privately, through this repository's **Security → Report a vulnerability** on GitHub,
not in a public issue. Say what you ran, on which release (`portfusion --version`), and what it
let you do. Use the demo book or an invented one: never send a real book's files, figures or
credentials.

A fix ships as a release, and the report is credited in the changelog unless you ask otherwise.

## What is supported

The newest release. Fixes are not back-ported to older ones.

## Where the guards are

- **The desk's sign-in**: passkeys and the access levels, `docs/access-levels.md`.
- **The doors**: the only code that writes to a book, `src/portfusion/desk/doors/`.
- **The feeds**: read-only by construction; a dealing endpoint is refused in code.
- **The secret gate**: a commit that would put a credential into git is refused, in this
  repository and in every book `portfusion init` makes (`src/portfusion/hooks/pre_commit.py`).
