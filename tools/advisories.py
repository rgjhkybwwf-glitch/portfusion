"""THE LOCKS' KNOWN ADVISORIES: every pin in `requirements.lock` and in the JavaScript tools'
`tools/package-lock.json`, asked of OSV, the advisory database GitHub's own alerts draw on. GitHub
cannot read the Python lock, so this is what sees it. Fails on any hit, and on no answer.

    python3 tools/advisories.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

from portfusion.log import log

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements.lock"
NPM_LOCK = ROOT / "tools" / "package-lock.json"
OSV = "https://api.osv.dev/v1/querybatch"


def pins(text: str) -> list[tuple[str, str]]:
    return [tuple(line.split("==")) for line in text.splitlines()
            if line and not line.startswith("#")]


def npm_pins(text: str) -> list[tuple[str, str]]:
    """Each package the lock installs, once: its key is its path under `node_modules/`. The root,
    and a link to a local folder, carry no version."""
    return sorted({(path.rpartition("node_modules/")[2], p["version"])
                   for path, p in json.loads(text)["packages"].items() if path and "version" in p})


def main() -> int:
    locked = ([("PyPI", n, v) for n, v in pins(LOCK.read_text())]
              + [("npm", n, v) for n, v in npm_pins(NPM_LOCK.read_text())])
    ask = {"queries": [{"package": {"name": n, "ecosystem": e}, "version": v}
                       for e, n, v in locked]}
    request = urllib.request.Request(OSV, json.dumps(ask).encode(),
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as r:
        results = json.load(r)["results"]
    hits = [(e, n, v, [x["id"] for x in res.get("vulns", [])])
            for (e, n, v), res in zip(locked, results, strict=True) if res.get("vulns")]
    for e, n, v, ids in hits:
        log.info(f"{e} {n}=={v}: {len(ids)} advisories — {', '.join(ids)}")
    log.info(f"{len(locked)} pins asked, {len(hits)} with an advisory")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
