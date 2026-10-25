"""THE LOCK'S KNOWN ADVISORIES: every pin in `requirements.lock`, asked of OSV, the advisory
database GitHub's own alerts draw on. GitHub cannot read the lock, so this is what sees it. Fails
on any hit, and on no answer.

    python3 tools/advisories.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

from portfusion.log import log

LOCK = pathlib.Path(__file__).resolve().parents[1] / "requirements.lock"
OSV = "https://api.osv.dev/v1/querybatch"


def pins(text: str) -> list[tuple[str, str]]:
    return [tuple(line.split("==")) for line in text.splitlines()
            if line and not line.startswith("#")]


def main() -> int:
    locked = pins(LOCK.read_text())
    ask = {"queries": [{"package": {"name": n, "ecosystem": "PyPI"}, "version": v}
                       for n, v in locked]}
    request = urllib.request.Request(OSV, json.dumps(ask).encode(),
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as r:
        results = json.load(r)["results"]
    hits = [(n, v, [x["id"] for x in res.get("vulns", [])])
            for (n, v), res in zip(locked, results, strict=True) if res.get("vulns")]
    for n, v, ids in hits:
        log.info(f"{n}=={v}: {len(ids)} advisories — {', '.join(ids)}")
    log.info(f"{len(locked)} pins asked, {len(hits)} with an advisory")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
