"""THE QUOTE CHECK — why a Claude session's reading still traces every figure to its source.

**THE CHECK IS THE WHOLE ARGUMENT, NOT THE READER'S ACCURACY.** A session TRANSCRIBES a broker
document and `propose.py` takes the reading; nothing here or there parses one. Every proposed cell arrives
carrying the verbatim span it came from, and this module refuses the cell unless that span is
ACTUALLY IN THE DOCUMENT — a string match, in code, before any of it reaches the screen. So the
owner checks a QUOTE AGAINST A DOCUMENT, which eyes are good at, rather than a reader
against their memory. A figure that was never on the page cannot get through.

It is a module of its own because it has nothing to do with prompting: it is the safety
argument, and worth being able to read apart from the guide a session reads.

WHAT IT DELIBERATELY DOES NOT VERIFY: MAGNITUDE AND SIGN — `_digits` says why. The quote covers
the magnitude, sitting under the field where it can be read; the sign is the one figure the reader
composes, and the Bench asks the owner to confirm one its category does not usually carry
(`bench.unusual_signs()`).

IT TOUCHES NOTHING. No network, no disk, no state — every function here is a pure one over the
cell and the document text it was read from.
"""
from __future__ import annotations

import datetime as _dt
import re
from decimal import Decimal

#: The kinds whose value must also be found in its own quote.
NUMERIC_KINDS = ("int", "float", "number")


def _flat(text: str) -> str:
    """Whitespace collapsed and lowercased, for comparing a quote with the document.

    A PDF extracts with line breaks and runs of spaces where the page had a table, so a strict
    match would fail on correct quotes constantly. This is not a loosening that lets anything
    through: every character of the quote must still be present, in order.
    """
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _digits(text: str) -> str:
    """A number's significant digits: no separators, no sign, no decimal point, no leading zeros.

    WHY THE DECIMAL POINT IS DROPPED, WHICH LOOKS TOO LOOSE UNTIL YOU SEE THE BOOK. LSE prices
    are quoted in pence and STORED AS POUNDS: the ii contract note says 52.50p and
    `sales.csv` holds 0.525. Requiring the value to appear in its quote as written would reject
    that correct transcription every time, and rejecting correct work teaches people to
    switch the check off.

    So this tolerates a shift of the decimal point and NOTHING ELSE. A transposition (4859 for
    4895) fails. A figure that was never on the page fails. What it does not verify is
    MAGNITUDE — that is what the quote is for, sitting under the field where it can be read — nor
    SIGN, which a statement prints as a column, a word or a bracket.
    """
    digits = re.sub(r"\D", "", text or "")
    # ZERO IS A NUMBER: stripped to nothing, a value of 0 would skip the check that it stands in
    # its quote.
    return digits.lstrip("0") or ("0" if digits else "")


def _numbers_in(quote: str) -> set[str]:
    r"""Every number in the quote, as significant digits.

    THE CHARACTER CLASS MUST NOT INCLUDE WHITESPACE. A contract note is a TABLE, so a quote
    covering one row reads "1,200 1.098667" — quantity and price, two columns, one space. With
    `\s` inside the run that is ONE token, `12001098667`, which matches neither figure. **The
    most likely quote to check is a table row**, so the tokeniser splits on the gap between
    columns rather than swallowing it.
    """
    return {_digits(tok) for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", quote or "")}


_MONTH = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def _dates_in(quote: str) -> set[str]:
    """Every date the quote prints, as ISO: 2026-09-03, 03/09/2026, 03-09-26, 3 Sep 2026, 3 September
    2026, 03-Sep-26. Day first, as a UK document prints one."""
    found = set()

    def add(y, m, d):
        y = int(y) + (2000 if len(str(y)) == 2 else 0)
        try:
            found.add(_dt.date(y, int(m), int(d)).isoformat())
        except ValueError:
            pass
    q = quote or ""
    for y, m, d in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", q):
        add(y, m, d)
    for d, m, y in re.findall(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b", q):
        add(y, m, d)
    for d, mon, y in re.findall(r"\b(\d{1,2})[\s-]+([A-Za-z]{3})[a-z]*[\s-]+(\d{4}|\d{2})\b", q):
        if mon.lower() in _MONTH:
            add(y, _MONTH[mon.lower()], d)
    return found


def as_stored(value: str, kind: str) -> str:
    """A quoted number in the store's spelling: separators out, value unchanged.

    THE DOCUMENT PRINTS "1,200" AND "1,318.40" AND THE STORE CANNOT LOAD EITHER — `int("1,200")`
    and `float("1,318.40")` both raise. A reader is told to report the figure EXACTLY as
    printed, which is right (it is what makes the quote check possible) and leaves this last step
    here, where it is a formatting change with the quote still showing what the page said.

    THE CURRENCY SYMBOL GOES TOO: a cash statement prints "£1,318.40". The symbol is not
    information the cell holds; `cur` and `account` say the currency, and the store holds bare
    numbers.

    NOTHING ELSE IS TOUCHED. No rounding, no unit conversion, no sign flipped — only the
    separators and symbols the store has no way to read. A price printed in pence is the one
    conversion, and it is the caller's, on the quote's word (`in_pence()`).

    Side effects: none.
    """
    if kind not in NUMERIC_KINDS:
        return value
    cleaned = re.sub(r"[,\s£$€]", "", value).strip()
    return cleaned or value


def in_pence(value: str, quote: str) -> bool:
    """Does the page print THIS figure in pence? It does when the figure as reported stands in
    its quote followed by "p" ("19.30p"), or the quote says its figures are pence ("Price (p)
    52.50"). A figure the reader already put in pounds ("0.1930" for "19.30p") is not the one
    printed, so it is never taken for pence twice.

    Side effects: none.
    """
    v = re.sub(r"[,\s£$€]", "", value or "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", v):
        return False
    printed = rf"(?<![\d.,]){re.escape(value.strip())}(?![\d,]|\.\d)"
    if re.search(printed + r"\s?p\b", quote or ""):
        return True
    return bool(re.search(printed, quote or "")) and bool(
        re.search(r"\(p\)|\bpence\b", quote or "", re.IGNORECASE))


def in_pounds(value: str) -> str:
    """A price in pence, in pounds: the same digits, the point two places left. Exact — decimal
    arithmetic, no float — so 52.50 is 0.525 and never 0.5249999.

    Side effects: none.
    """
    return format((Decimal(re.sub(r"[,\s£$€]", "", value)) / 100).normalize(), "f")


def check(cell: dict, kind: str, doc: str) -> str | None:
    """Why this cell must be dropped, or None if it survives.

    Side effects: none.
    """
    value = str(cell.get("value", "")).strip()
    quote = str(cell.get("quote", "")).strip()

    if not value:
        return "no value"
    if not quote:
        return "no quote — a value with nothing behind it is not enterable"
    if _flat(quote) not in _flat(doc):
        return f"the quote {quote!r} is not in the document"

    if kind in NUMERIC_KINDS and _digits(value) and _digits(value) not in _numbers_in(quote):
        return (f"{value!r} does not appear in its own quote {quote!r} — the digits must match, "
                f"allowing only for a decimal point moving")

    if kind == "date" or cell.get("field") == "date":
        try:
            _dt.date.fromisoformat(value)
        except ValueError:
            return f"{value!r} is not an ISO date, and a misread date is a real defect here"
        # THE DATE MUST BE ONE ITS QUOTE PRINTS. Checked for its shape alone, a day and a month
        # swapped would pass — 2026-03-09 for a quote saying 03/09/2026. A quote printing no date
        # the check can read is left to the eye.
        printed = _dates_in(quote)
        if printed and value not in printed:
            return (f"{value!r} is not a date its quote {quote!r} prints "
                    f"({', '.join(sorted(printed))})")
    return None
