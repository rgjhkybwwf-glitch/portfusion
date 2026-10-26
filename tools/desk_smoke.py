"""THE DESK'S ANSWERS, for `desk_smoke.mjs`: the demo desk asked, in this process and with no
server, for the page, its scripts, `/api/state` and every panel, house's rounding of a few
figures, and the IG sweep's own answer to an invented ledger, written as one JSON file. Fails on
any answer that is not a 200.

    npm ci --prefix tools                     # once: jsdom
    python3 tools/desk_smoke.py answers.json && node tools/desk_smoke.mjs answers.json
"""
from __future__ import annotations

import json
import os
import sys

os.environ["PORTFUSION_BOOK"] = "demo"      # the file leaves the book behind: never a real one's

from fastapi.testclient import TestClient  # noqa: E402

from portfusion.desk import app  # noqa: E402
from portfusion.log import log  # noqa: E402


#: Halves, a binary float below its own digits, a large and a tiny figure, and a percentage.
ROUNDING = [(12.5, 0, 0), (-12.5, 0, 0), (0.125, 2, 0), (2.675, 2, 0), (1.005, 2, 0),
            (17576.326315789473, 2, 0), (123456789.125, 2, 0), (1e-7, 2, 0), (0.454301, 2, 2),
            (0.0045, 2, 2), (1.3158, 4, 0), (10480, 2, 0)]


def _sweep() -> dict:
    """`feeds/ig.ig_events()`'s answer to four invented deposits on every IG login the demo names,
    through the real allowlist, and their status with the first three already in the record."""
    from portfusion.feeds import ig
    day = ig._dt.date.today().isoformat()
    ledger = {"transactions": [{"dateUtc": f"{day}T00:00:00", "reference": f"TX-{n}",
                                "transactionType": "DEPO", "profitAndLoss": "£10.00",
                                "instrumentName": "Card deposit"} for n in range(4)]}

    class Session:
        def __init__(self, cred, label):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def _request(self, method, path, version):
            ig._assert_readonly(method, path)
            return ({"activities": []} if path.startswith("/history/activity") else ledger), {}
    ig.load_credentials = lambda *a, **k: {label: {} for label in ig.account_names()}
    ig.IGSession = Session
    result = ig.ig_events()
    refs = [r["ref"] for k in ("opens", "closes", "costs", "capital", "setups") for r in result[k]]
    return {"result": result, "status": {ref: {"in_record": n < 3, "tables": [], "item": None}
                                         for n, ref in enumerate(refs)}}


def main(out: str) -> int:
    client = TestClient(app.app, base_url="http://127.0.0.1:8765")
    answers = {}

    def ask(url: str) -> str:
        r = client.get(url)
        answers[url] = {"status": r.status_code, "body": r.text}
        return r.text

    scripts = [s.split('"', 1)[0] for s in ask("/").split('<script src="')[1:]]
    answers["/"]["scripts"] = scripts
    for script in scripts:
        ask(script)
    for p in json.loads(ask("/api/state"))["panels"]:
        ask(f"/api/panel/{p['name']}")
    # ONE ROUNDING: house's answers, which the page's own fixed() must give.
    from portfusion.house.precision import fixed
    answers["/"]["rounding"] = [[n, dp, shift, fixed(n, dp, ",", shift)]
                                for n, dp, shift in ROUNDING]
    answers["/"]["sweep"] = _sweep()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(answers, f)
    bad = [f"{u} ({a['status']})" for u, a in answers.items() if a["status"] != 200]
    log.info(f"{len(answers)} answers recorded" + (f"; not 200: {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
