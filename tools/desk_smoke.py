"""THE DESK'S ANSWERS, for `desk_smoke.mjs`: the demo desk asked, in this process and with no
server, for the page, its script, `/api/state` and every panel, written as one JSON file. Fails on
any answer that is not a 200.

    npm ci --prefix tools                     # once: jsdom
    python3 tools/desk_smoke.py answers.json && node tools/desk_smoke.mjs answers.json
"""
from __future__ import annotations

import json
import os
import re
import sys

os.environ["PORTFUSION_BOOK"] = "demo"      # the file leaves the book behind: never a real one's

from fastapi.testclient import TestClient  # noqa: E402

from portfusion.desk import app  # noqa: E402
from portfusion.log import log  # noqa: E402


def main(out: str) -> int:
    client = TestClient(app.app, base_url="http://127.0.0.1:8765")
    answers = {}

    def ask(url: str) -> str:
        r = client.get(url)
        answers[url] = {"status": r.status_code, "body": r.text}
        return r.text

    script = re.search(r'<script src="([^"]+)"></script>', ask("/"))[1]
    answers["/"]["script"] = script
    ask(script)
    for p in json.loads(ask("/api/state"))["panels"]:
        ask(f"/api/panel/{p['name']}")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(answers, f)
    bad = [f"{u} ({a['status']})" for u, a in answers.items() if a["status"] != 200]
    log.info(f"{len(answers)} answers recorded" + (f"; not 200: {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
