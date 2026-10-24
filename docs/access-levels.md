# Access levels

Who reads the hosted desk ([`desk-app.md`](desk-app.md)), what each level opens, and how a
reader is added, changed or removed. The desk on the Mac has no levels: every page and every
button, on localhost only.

## The levels

A reader is a name with a passkey on each of their devices, and holds one level, read afresh
on every request.

| | Owner | Principal |
|---|---|---|
| **Pages** | The eight reading pages: Dashboard, What Changed, Reconcile, Performance, Holdings, Round Trips, Trades, Reports | The same eight |
| **Buttons** | None | None |
| **An account is called** | Its register name | Its code and label, `A1 · ISA` |
| **Holders' names, account numbers** | Shown | `[withheld]`, in notes too |

A page the renaming could not clear is refused, not sent. The quarterly report names accounts
by code at every level. What a level opens is `OPENS` in `desk/remote.py`.

## Adding a reader

1. **Issue a code on the Mac**: Access → *Enrol a device* → *a new reader*, their name, the
   level → **Issue an enrol code**; or `portfusion desk --enrol NAME --level principal`.
2. **Hand it over** in person or by a channel you trust. It is good for ten minutes, one device
   and five guesses, and a restart of the desk loses it.
3. **They enrol**: open the hosted desk, type the code, *Enrol this device*, then Face ID or
   Touch ID.
4. **Check Access**: the reader, their level, one device; the log says *enrolled*.

A second device is enrolled the same way with the reader's name chosen, and keeps their level.

## Changing and removing

On Access; each holds from the reader's next request.

| To | Press | What follows |
|---|---|---|
| Change a level | The level on the reader's row | Answered at the new one |
| Revoke a device | *revoke* on the device | Its sessions end; other devices carry on |
| Revoke a reader | *revoke* on the reader's row | Every passkey and the level go; back only as new |
| End every session | *sign everyone out* | All sign in again; passkeys and levels stay |

A session also ends after 12 hours unused, after 7 days, and at every restart of the desk.

## The log

Access shows the last 30 days of sign-ins, enrolments, refusals and limits. Worth a look:

- **An *enrolled* line nobody issued a code for**: revoke that device at once.
- **Refusals from an unknown address**: noise, unless it grows.
- **One address on every line, yours included**: Netlify is not naming the caller, so the
  sign-in limit is shared by everyone.
- **A run of *not through the hosted desk***: the proxy secrets differ, or someone found the
  tunnel, which buys them nothing.

The readers, passkeys and log are three files in the book's folder, which git ignores.
