"""FILING — where a Bench item's document waits, and the name and date it is filed under in
`_archive/statements/`. It names; the commit door moves the document.

How `_archive/statements/` names a document is `rules.ARCHIVE_CONVENTION`, whose parts are the
three evidence limbs — so the name is derived from the evidence, never typed, and a document
filed by the desk reads like one filed by hand.
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import re

from portfusion.record import schema

_DATE_FORMATS = ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y", "%d %b %y")


def archive_date(raw: str):
    """The document's date, however it was typed; None if it will not parse, and then the
    document keeps its original filename. Never guessed: this folder's job is retrieval."""
    text = str(raw or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _covers(item: dict) -> str:
    """What the document covers, from the rows: tickers and accounts. Factual, never
    editorial — a hand-filed "(PENR trim 3)" knows which trim it was; nothing here can."""
    rows = item.get("rows") or []
    tickers, accounts = [], []
    for row in rows:
        v = row.get("values") or {}
        for key in ("ticker",):
            if v.get(key) and v[key] not in tickers:
                tickers.append(str(v[key]))
        if v.get("account") and v["account"] not in accounts:
            accounts.append(str(v["account"]))
    # A document that yields no rows still covers an account, and says whose.
    #
    # ACCOUNT FIRST WHEN THE REFERENCE IS ONLY A DATE. A contract note number is unique across
    # every account, so tickers can lead. A date range is not: two accounts' GBP ledgers over
    # the same dates are identical files, and the account is the whole identification.
    from portfusion.record import rules as D
    ev = D.EVIDENCE_BY_KEY.get(item.get("evidence_class") or "")
    account_first = ev is not None and ev.key in D.REFERENCE_IS_A_DATE
    first, second = (accounts, tickers) if account_first else (tickers, accounts)
    parts = first or second or ([item["account"]] if item.get("account") else [])
    return ", ".join(parts)


def _document_stamp(original: str, when) -> str:
    """`HH.MM` from the document's own "as at" line, or "". Never raises: a document that
    cannot be read is still filed, and the time is provenance, not something filing needs."""
    from portfusion.record import rules as D
    from portfusion.desk.intake import read_document
    src = schema.inbox() / original
    if not src.is_file():
        return ""
    try:
        inst = D.document_instant(read_document.extract_file(src).get("text") or "")
    except Exception:                     # noqa: BLE001 — a name is worth more than a stamp
        return ""
    return f"{inst:%H.%M}" if inst and inst.date() == when else ""


def _instant_in(reference: str, when) -> tuple[str, str]:
    """(`HH.MM`, the reference without it) where the reference states an instant on `when`'s
    day, else ("", the reference unchanged).

    THE INSTANT IS NAMED ONCE. A download is referenced by the instant it was pulled, and the
    name already leads with the date and the time, so repeating them in the reference would
    write both twice. A period that ENDS on that day keeps its date, because there the date is
    the period's, not the pull's.
    """
    m = re.search(rf"\b0?{when.day} {when:%b} {when.year}[ ,]+([01]\d|2[0-3])[:.\-]([0-5]\d)\b",
                  reference)
    if not m:
        return "", reference
    before, after = reference[:m.start()], reference[m.end():]
    if re.search(r"(\bto|-)\s*$", before):
        before += f"{when.day} {when:%b} {when.year}"
    return f"{m.group(1)}.{m.group(2)}", " ".join(f"{before}{after}".strip(" ,;-").split())


def archive_name(item: dict, original: str) -> str:
    """The filename this document should be filed under. Falls back to what it arrived as."""
    evidence = item.get("evidence") or {}
    when = archive_date(evidence.get("dated"))
    authority = " ".join(str(evidence.get("authority") or "").split())
    if not when or not authority:
        return original

    # THE DOCUMENT'S OWN TIME, when it states one: a valuation moves within the day, and
    # several exports can share a date and a title. Only when it falls on the `dated` limb's
    # day — a time from one document spliced onto another's date would invent a third instant.
    stamp = _document_stamp(original, when)
    suffix = pathlib.Path(original).suffix
    reference = " ".join(str(evidence.get("reference") or "").split())
    typed, rest = _instant_in(reference, when)
    if typed and (not stamp or typed == stamp):     # the same instant: name it once
        stamp, reference = typed, rest
    bits = [f"{when:%d %b %Y}"] + ([stamp] if stamp else []) + [authority]
    if reference and reference.lower() not in authority.lower():
        bits.append(reference)
    name = " ".join(b for b in bits if b)
    covers = _covers(item)
    if covers:
        name += f" ({covers})"
    # A filename, so nothing that would make it one path segment too many.
    name = re.sub(r"[/\\:]", "-", name).strip()
    return f"{name}{suffix}"


def document_on_the_bench(item: dict) -> pathlib.Path | None:
    """Where the item's document waits to be filed — on the workbench, `_inbox/` — or None if
    it names none. The gate asks here and the filing reads here, so the two cannot disagree."""
    name = (item.get("document") or {}).get("name")
    return schema.inbox() / name if name else None


def filed_as(path) -> str:
    """A path as an item names it: relative to the book when inside it, whole when not."""
    try:
        return str(path.relative_to(schema.BOOK))
    except ValueError:
        return str(path)
