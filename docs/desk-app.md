# Running the desk

How the desk is started on the Mac and kept current.

```bash
portfusion desk                         # start it, in the book's folder
portfusion desk --reload                # while working ON the desk
portfusion desk --port 8769             # another port; --no-open keeps the browser shut
portfusion desk --install-agent         # on a Mac: the desk at login, for this book
portfusion desk --uninstall-agent       # stop it and remove it
```

The desk answers on `127.0.0.1:8765` and has no sign-in, so it never listens beyond this machine.
It assumes one user account on the Mac: any process that reaches the port is answered as the owner ([`SECURITY.md`](../SECURITY.md)).

## At login, and in the Dock

`--install-agent` writes a LaunchAgent (`desk/agent.py`) that runs the desk on the venv that typed
the command, for the book it reads (`PORTFUSION_BOOK`, else the folder it is typed in), logging
to `~/Library/Logs/portfusion-desk.log`. One desk agent per Mac user. It starts at login and is
not restarted if it stops. A book that moves needs `--uninstall-agent`, then `--install-agent` in
its new folder.

To put it in the Dock: Safari → `http://127.0.0.1:8765/` → **File → Add to Dock**. The web app
only opens the page; if the desk is not running, Safari shows a blank error. It copies the icon
and name when added, so a new brand reaches the Dock only after a restart, by removing it and
adding it again.

## Restart, reload, or nothing

| Changed | What to do |
|---|---|
| any `.py` the desk imports | restart: *restart the desk* on the freshness line, under the pages, or `launchctl kickstart -k gui/$UID/org.portfusion.desk` |
| the book's `brand/` | restart: its name, colours and lockup are read once, and the desk does not say they changed |
| `desk/static/` | reload the page |
| `store/` | nothing: the next request reads it |

The desk says when it is running older code than is on disk, names the files, and offers the
restart. It watches PortFusion's own files only: an upgraded dependency is not noticed, so restart
after one.
