"""THE NEW SHELL, ON TRIAL: the desk as `portfusion desk` serves it, with the shell being tried
beside it at `/next`.

    export PORTFUSION_BOOK=demo
    python3 tools/trial_shell.py 8770          # then http://127.0.0.1:8770/next

IT ASKS ONE QUESTION of the front end's platform: whether plain scripts carry a side menu that
stays while the page beside it changes, an address for each object, tabs that keep their place
and a find field. `trial_shell/check.mjs` checks the four in a browser.

THE APP IS NOT CHANGED. The page, its script and its stylesheet are `tools/trial_shell/`'s, the
script asks only what the desk's API already answers, and it writes nothing. Today's desk is
still at `/`, on the same port and the same book, so the two are read side by side.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent / "trial_shell"

#: The trial's files, each by the name it is asked for and the type it is sent as. A name is
#: looked up here and never resolved against the folder, as `desk/bundle.py`'s are.
FILES = {"": ("index.html", "text/html"),
         "shell.css": ("shell.css", "text/css"),
         "shell.js": ("shell.js", "text/javascript")}


def mount(desk) -> None:
    """Add `/next` and its two files to the desk's own app, sent with the shell's headers: the
    page loads from this origin only, and nothing is cached."""
    from fastapi import HTTPException, Response

    from portfusion.desk import app, bundle

    def send(name: str) -> Response:
        if name not in FILES:
            raise HTTPException(404, "no such file")
        file, kind = FILES[name]
        return Response((HERE / file).read_bytes(), media_type=kind,
                        headers={**app.NO_STORE, **bundle.SHELL_HEADERS})

    def page() -> Response:
        return send("")

    desk.get("/next")(page)
    desk.get("/next/{name}")(send)


def main(port: str = "8770") -> None:
    import uvicorn

    from portfusion.desk import app
    from portfusion.desk.__main__ import HOST
    mount(app.app)
    uvicorn.run(app.app, host=HOST, port=int(port), log_level="warning")


if __name__ == "__main__":
    main(*sys.argv[1:2])
