# Security

How a security fault in PortFusion is reported, and where its guards are. A security fault is one
that would let someone read a book they were not given, write to one without the owner's
approval, or take a credential from it.

## Reporting one

Report it privately, through this repository's **Security → Report a vulnerability** on GitHub,
not in a public issue. Say what you ran, on which release (`portfusion --version`), and what it
let you do. Use the demo book or an invented one: never send a real book's files, figures or
credentials.

A fix ships as a release, and the report is credited in the changelog unless you ask otherwise.

## What is supported

The newest release. Fixes are not back-ported to older ones.

## What the desk assumes

**One user account on the Mac.** The Mac's own desk listens on 127.0.0.1 only and has no sign-in:
any process that reaches the port is answered as the owner, every page and action and an
owner-level enrol code for the hosted desk included. A process of the owner's own account could
read the book's files anyway. A second account on the same Mac, or anything that forwards a port
to its loopback, would reach the desk as the owner, and is outside what it defends.

## Where the guards are

- **The desk's sign-in**: passkeys and the access levels,
  [`docs/access-levels.md`](docs/access-levels.md).
- **The writers**: every module that writes a file, named in `WRITERS`
  (`src/portfusion/tests/desk/test_boundaries.py`). The record is written only by the doors under
  `desk/`, and its histories by those doors and the price refresh, through `history/`; outside
  `desk/`, `portfusion init` and `portfusion migrate --write` write a book, and a feed writes only
  its own sign-in file.
- **The feeds**: read-only by construction; a dealing endpoint is refused in code.
- **The secret gate**: a commit that would put a credential into git, in a file or in its
  message, is refused, in this repository and in every book whose history `portfusion init`
  starts (`src/portfusion/hooks/pre_commit.py`). The files a book keeps secrets in are
  `src/portfusion/secret_scan.py`'s `SECRET_FILES`.
