"""THE BROKER READ WRAPPER — the Bench's IG event sweep goes through it.

It sits outside the panel so a second panel that calls IG can share it: a panel may not import
another (`desk/panels/__init__.py`). The price sweep has its own, in `feeds/refresh.py`.

IT IS NOT A STORE DOOR. It reads no CSV and writes nothing; it turns the ways a broker call
can legitimately fail into something a screen can render.
"""
from __future__ import annotations


def _ig(fn, *a):
    """Run an IG read, turning the ways it can legitimately fail into something renderable.

    A broker being down, or credentials not being present, is an ORDINARY outcome for a panel
    and must not look like a bug. The message is passed through as-is: `load_credentials` says
    exactly which file is missing, and paraphrasing would throw that away.
    """
    try:
        from portfusion.feeds import ig
    except Exception as e:
        return {"ok": False, "error": f"feeds/ig.py could not be imported: {e}"}
    try:
        return {"ok": True, "result": fn(ig, *a)}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"no credentials: {e}",
                "hint": "credentials.json is gitignored and is not present until you create it."}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

