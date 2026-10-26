"""A PAST DAY'S CLOSE FOR A CONTRACT IG DOES NOT QUOTE THROUGH THE EVENING, read off that day's IG
statement once the bench has filed it.

`feeds/ig.py:contract_closes()` takes a contract's close from IG's 21:00 hour bar and leaves the
far contracts unpriced, because IG does not quote them through the evening. Their close is the
level that day's statement prints. The statement reaches
`_archive/statements/` through the bench like any other document; this reads the level off the
filed copy, so the figure comes in through the door the document did.

IT READS AND NOTHING MORE. Its rows go on the Price Refresh's review beside the bar closes, are
ticked like them, and are banked by `marks.bank_closes()`, the one door for a past day's closes.

WHAT IT WILL NOT DO:

  · PLACE A POSITION BY ITS NAME. A statement names the market, which is the same for every
    expiry. The deal reference is unique, and the record already holds it: `buys.csv`
    `broker_ref` -> the trade -> `rules.LEG_CONTRACT`. A deal the book does not hold is reported.
  · CHOOSE BETWEEN TWO LEVELS. IG values every position on one contract at one level; two
    different levels for one contract are reported, and neither is used.
  · TAKE THE FILENAME'S WORD FOR THE DAY. The date the document prints must be the day asked for.
"""
from __future__ import annotations

import datetime as _dt
import fnmatch
import re

from portfusion.record import rules as D
from portfusion.record import schema
from portfusion.desk.intake import read_document

#: One open position as the extractor gives it: the deal on its own line, then the market, the
#: stake, the opening level and the current level. A deal confirmation or a closed position is
#: laid out differently and does not match.
_POSITION = re.compile(r"^(DIAAAA[A-Z0-9]+)\n(.+?) £ [+-][\d.]+ [\d,]+(?:\.\d+)? "
                       r"([\d,]+(?:\.\d+)?) ", re.MULTILINE)
_PRINTED_DATE = re.compile(r"^(\d{1,2} [A-Z][a-z]+ \d{4})$", re.MULTILINE)


def closes(on: str) -> dict:
    """Each contract's level on the IG statements filed for `on`, as close rows.

    Returns {"rows": {contract: row}, "read": [document names], "problems": [sentences]}. A row
    has the fields `contract_closes()` gives a priced contract, so the desk fills and the door
    banks it the same way, and `origin` says it came off a filed document.
    """
    day = _dt.date.fromisoformat(on)
    label = f"{day:%d %b %Y}"
    contract_of = {t.broker_ref: (D.LEG_CONTRACT[t.trade_id], t.acct) for t in D.buys
                   if D.LEG_CONTRACT.get(t.trade_id) and t.broker_ref}
    found, read, problems = {}, [], []
    for name in schema.filed_statements():
        if not fnmatch.fnmatchcase(name, f"{label}*IG statement*.pdf"):
            continue
        path = schema.statements() / name
        doc = read_document.extract_file(path)
        printed = _PRINTED_DATE.search(doc["text"])
        if doc["scanned"] or not printed or (
                _dt.datetime.strptime(printed.group(1), "%d %B %Y").date() != day):
            problems.append(f"{path.name} does not print {label} as its date, so it was not read")
            continue
        read.append(path.name)
        for deal, market, level in _POSITION.findall(doc["text"]):
            if deal not in contract_of:
                problems.append(f"{path.name}: deal {deal} ({market}) is not in the book")
                continue
            contract, acct = contract_of[deal]
            found.setdefault(contract, []).append((level, deal, market, acct))

    rows = {}
    for contract, seen in sorted(found.items()):
        levels = sorted({level for level, *_ in seen})
        if len(levels) > 1:
            problems.append(f"{contract} is valued at {' and '.join(levels)} on the statements "
                            f"filed for {label}, so neither is used")
            continue
        level, market, acct = seen[0][0], seen[0][2], seen[0][3]
        raw = float(level.replace(",", ""))
        rows[contract] = {
            "contract": contract, "as_of": on, "raw": raw, "priced": True,
            "level": raw, "struck": "close", "at": "",
            "status": "CLOSE", "origin": "filed",
            "source": (f"{D.evidence_source('ig-statement', label)} ({acct}), {market} "
                       f"current level {level}, "
                       f"deal{'s' if len(seen) > 1 else ''} "
                       f"{', '.join(deal for _l, deal, *_ in seen)}"),
        }
    return {"rows": rows, "read": read, "problems": problems}
