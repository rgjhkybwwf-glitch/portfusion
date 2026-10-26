"""`portfusion desk` — start the desk.

Localhost only, always (`HOST`). These are the book's real figures and the Mac's own door has no
sign-in; binding it to anything else would put them on the network.

`--remote-port` opens the second door in the same process: `desk/remote.py`, signed in and read
only, which the tunnel forwards to the hosted desk. It too binds 127.0.0.1; the tunnel is the
only way to it from outside.
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
import webbrowser

from portfusion.log import log

#: Where both doors listen: this Mac only. There is no flag to change it.
HOST = "127.0.0.1"


def main(argv=None):
    from portfusion.desk import auth
    ap = argparse.ArgumentParser(prog="portfusion desk", description="the desk")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    ap.add_argument("--enrol", metavar="NAME",
                    help="print a one-time code for enrolling a passkey on the hosted desk, "
                         "asked of the desk running on --port. The Access page has the same "
                         "button")
    ap.add_argument("--level", choices=auth.LEVELS,
                    help="with --enrol, a new reader's level; a reader who has one keeps it")
    ap.add_argument("--publish", action="store_true",
                    help="publish the hosted desk: write the deploy repository, commit, push "
                         "(desk/publish.py). Uses --remote-port's tunnel, 8768 if not given")
    ap.add_argument("--remote-port", type=int, default=None,
                    help="also open the remote door (desk/remote.py) on this port, for the "
                         "tunnel to the hosted desk")
    ap.add_argument("--install-agent", action="store_true",
                    help="start the desk at login for this book, as a macOS LaunchAgent "
                         "(desk/agent.py), with the remote door when the book names a hosted "
                         "desk; installed again, it restarts on the code now installed")
    ap.add_argument("--uninstall-agent", action="store_true",
                    help="stop the desk's LaunchAgent and remove it")
    ap.add_argument("--reload", action="store_true",
                    help="restart on a source change. Use it while the desk is being built: "
                         "without it a running server keeps executing the code it imported at "
                         "startup, and a panel fixed on disk goes on failing in the browser.")
    args = ap.parse_args(argv)
    if args.enrol:
        return _enrol(args.enrol, args.port, args.level)
    if args.install_agent or args.uninstall_agent:
        return _agent(args)
    if args.publish:
        from portfusion.desk import publish
        return publish.main(args.remote_port or 8768)

    try:
        import uvicorn
    except ImportError:
        # The one thing that actually needs the venv. Say so plainly rather than failing
        # somewhere further in with a confusing error.
        sys.exit("\nThe desk needs its dependencies, which live in the project venv.\n\n"
                 "    source .venv/bin/activate\n"
                 "    portfusion desk\n\n"
                 "Or rebuild it:  python3 -m venv .venv && "
                 ".venv/bin/python3 -m pip install -e '.[dev]' -c requirements.lock\n")

    url = f"http://{HOST}:{args.port}/"
    log.info(f"\n  the desk — {url}")
    log.info("  reading the store directly. Ctrl-C to stop.\n")
    if not args.no_open:
        webbrowser.open(url)
    # RELOAD IS OFF BY DEFAULT, deliberately: this reads the book's record, and a watcher
    # restarting mid-request should not run unasked. But a desk left open across a code change
    # serves the code it imported at startup, so a panel fixed on disk goes on failing in the
    # browser. `--reload` is the answer while the desk is being worked on.
    if args.remote_port is None:
        uvicorn.run("portfusion.desk.app:app", host=HOST, port=args.port, log_level="warning",
                    reload=args.reload, reload_dirs=[str(pathlib.Path(__file__).parent)] if args.reload else None)
        return
    if args.reload:
        sys.exit("--reload watches one server; run the remote door without it")
    from portfusion.desk import remote
    if remote.unconfigured():
        log.warning(f"  the remote door stays shut: the book's settings name no "
                    f"{', '.join(remote.unconfigured())} (store/settings.csv)\n")
    remote.PORT = args.remote_port
    log.info(f"  the remote door — http://{HOST}:{args.remote_port}/, for the tunnel\n")
    asyncio.run(_serve([
        uvicorn.Server(uvicorn.Config("portfusion.desk.app:app", host=HOST, port=args.port,
                                      log_level="warning")),
        uvicorn.Server(uvicorn.Config("portfusion.desk.remote:door", host=HOST,
                                      port=args.remote_port, log_level="warning")),
    ]))


def _agent(args) -> int:
    """Install or remove the desk's LaunchAgent, for the loaded book."""
    from portfusion.desk import agent
    if args.uninstall_agent:
        log.info(f"\n  {agent.uninstall()}\n")
        return 0
    from portfusion.desk import remote
    from portfusion.record import schema
    port = args.remote_port or (None if remote.unconfigured() else agent.REMOTE_PORT)
    try:
        log.info(f"\n  {agent.install(schema.BOOK, port)}\n")
    except agent.Refused as e:
        log.error(f"\n  No agent: {e}\n")
        return 1
    return 0


def _enrol(who: str, port: int, level: str | None = None) -> int:
    """Ask the running desk for an enrol code. It must be the desk the tunnel reaches, since a
    code lives in that process's memory."""
    import json
    import urllib.error
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/enrol", method="POST",
                                 data=json.dumps({"who": who, "level": level}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            got = json.load(r)
    except urllib.error.HTTPError as e:         # the desk's own refusal, in its words
        detail = json.loads(e.read() or b"{}").get("detail", e.reason)
        log.info(f"\n  No enrol code: {detail}.\n")
        return 1
    except Exception as e:                      # noqa: BLE001 — say what failed, plainly
        log.info(f"\n  No enrol code: the desk on port {port} did not give one ({e}).\n")
        return 1
    log.info(f"\n  Enrol code for {got['who']}, at {got['level']}:  {got['code']}\n"
          f"  Type it into the hosted desk's sign-in page within {got['minutes']} minutes.\n"
          f"  It works once.\n")
    return 0


async def _serve(servers):
    """Both doors in one event loop. When either stops — Ctrl-C reaches only one of them — the
    other is told to stop too, so the process never lives on with half its doors."""
    tasks = [asyncio.create_task(s.serve()) for s in servers]
    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for s in servers:
        s.should_exit = True
    await asyncio.gather(*pending)


if __name__ == "__main__":
    # sys.exit, so a failure to start reaches the shell as a non-zero status.
    sys.exit(main())
