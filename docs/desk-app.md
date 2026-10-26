# Running the desk

How the desk is started on the Mac, kept current, and served to readers beyond it.

```bash
portfusion desk                         # start it, in the book's folder
portfusion desk --reload                # while working ON the desk
portfusion desk --install-agent         # on a Mac: the desk at login, for this book
portfusion desk --uninstall-agent       # stop it and remove it
```

The desk answers on `127.0.0.1:8765` and has no sign-in, so it never listens beyond this machine;
the hosted desk, below, is the one way in from outside. It assumes one user account on the Mac:
any process that reaches the port is answered as the owner ([`SECURITY.md`](../SECURITY.md)).

## At login, and in the Dock

`--install-agent` writes a LaunchAgent (`desk/agent.py`) that runs the desk on the venv that typed
the command, for the book it was typed in, logging to `~/Library/Logs/portfusion-desk.log`. One
desk agent per Mac user. It starts at login and is not restarted if it stops. A book that moves
needs `--uninstall-agent`, then `--install-agent` in its new folder.

To put it in the Dock: Safari → `http://127.0.0.1:8765/` → **File → Add to Dock**. The web app
only opens the page; if the desk is not running, Safari shows a blank error. It copies the icon
and name when added, so a new brand reaches the Dock only by removing it and adding it again.

## Restart, reload, or nothing

| Changed | What to do |
|---|---|
| any `.py` the desk imports | restart: the desk's **Restart** button, or `launchctl kickstart -k gui/$UID/org.portfusion.desk` |
| `desk/static/` | reload the page |
| `store/` | nothing: the next request reads it |

The desk says when it is running older code than is on disk, names the files, and offers the
restart. A rebuilt venv or an upgraded package is not noticed: restart after either.

## The hosted desk

The same screen, served by Netlify from a deploy-only repository, reading the Mac through a
Tailscale Funnel to the desk's remote door on `:8768`. Every figure still comes from the Mac, so
it answers only while the Mac is awake. It needs three of the book's settings in
`store/settings.csv` — `hosted_origin`, `passkey_domain` and `deploy_repo` — and without them it
refuses, naming the key.

**Once:** install Tailscale and run `tailscale funnel --bg 8768`; make a private deploy
repository, clone it to `deploy_repo`, and import it into Netlify with access to that repository
only, deploy previews off, and your domain on it. Then set the proxy secret; run
`portfusion desk --install-agent` again, which opens the remote door on `8768` (or
`portfusion desk --remote-port 8768`); publish; and enrol.

**The proxy secret** is how the Mac knows a request came through Netlify. Held twice: in Netlify as
`DESK_PROXY_SECRET` (scoped to Runtime), and in the book's folder as `.desk_proxy_secret.json`,
which git ignores. This makes one and puts it on the clipboard, never the screen:

```bash
python3 -c "import json,os,secrets; s=secrets.token_urlsafe(32); f=os.open('.desk_proxy_secret.json', os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600); os.write(f, json.dumps({'secret': s}).encode()); os.close(f); print(s, end='')" | pbcopy
```

Until both hold the same value, every request is refused, and the Access page says why.

| To | Do |
|---|---|
| Publish | `portfusion desk --publish`, from the book's `main`, clean and pushed, with the deploy clone on a clean `main`; restart the Mac's desk first if its code changed |
| Manage readers | [`access-levels.md`](access-levels.md) |
| See whether it is up | the desk's header shows its state: *live*, *tunnel off*, *not published*, *behind*, or *restart first*; nothing while the remote door is shut |
| Turn it off | `tailscale funnel --https=443 off` |
