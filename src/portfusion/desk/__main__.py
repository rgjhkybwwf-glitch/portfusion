"""`portfusion desk` — start the desk.

Localhost only, always (`HOST`). These are the book's real figures and the desk has no
sign-in; binding it to anything else would put them on the network.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import webbrowser

from portfusion.log import log

#: Where the desk listens: this Mac only. There is no flag to change it.
HOST = "127.0.0.1"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="portfusion desk", description="the desk, in a browser, on this Mac only (127.0.0.1)")
    ap.add_argument("--port", type=int, default=8765, help="the desk's port (default 8765)")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    ap.add_argument("--install-agent", action="store_true",
                    help="start the desk at login for this book, as a macOS LaunchAgent "
                         "(desk/agent.py); installed again, it restarts on the code now "
                         "installed")
    ap.add_argument("--uninstall-agent", action="store_true",
                    help="stop the desk's LaunchAgent and remove it")
    ap.add_argument("--reload", action="store_true",
                    help="restart on a source change. Use it while the desk is being built: "
                         "without it a running server keeps executing the code it imported at "
                         "startup, and a panel fixed on disk goes on failing in the browser.")
    args = ap.parse_args(argv)
    if args.install_agent or args.uninstall_agent:
        return _agent(args)

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
    uvicorn.run("portfusion.desk.app:app", host=HOST, port=args.port, log_level="warning",
                reload=args.reload, reload_dirs=[str(pathlib.Path(__file__).parent)] if args.reload else None)


def _agent(args) -> int:
    """Install or remove the desk's LaunchAgent, for the loaded book."""
    from portfusion.desk import agent
    if args.uninstall_agent:
        log.info(f"\n  {agent.uninstall()}\n")
        return 0
    from portfusion.record import schema
    try:
        log.info(f"\n  {agent.install(schema.BOOK)}\n")
    except agent.Refused as e:
        log.error(f"\n  No agent: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    # sys.exit, so a failure to start reaches the shell as a non-zero status.
    sys.exit(main())
