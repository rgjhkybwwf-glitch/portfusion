"""WHAT A READER WHO MAY NOT SEE THE HOLDERS READS IN THEIR PLACE — the remote door's renaming.

    from portfusion.desk import naming
    n = naming.of(engine.book())
    n.rename({"account": "Sam IG Spread bet", "note": "per Alex"})
        # {"account": "A4 · IG Spread bet", "note": "per [withheld]"}

DECIDED 6 OCT 2026: an account is named by its register code to anyone but the
owner, and a holder's name and an account's number are taken out of every word such a reader is
sent, notes included. The register is `Book.account_register()`; the codes and labels are
`Book.account_codes()`. Nothing here is typed: a new account or holder joins by being registered.

THREE KINDS OF WORD, LONGEST FIRST, matched in any case wherever no letter or digit touches them:

  a register name, whole         "Sam IG Spread bet"    -> "A4 · IG Spread bet", its label
  a short form of exactly one    "Sam IG", "SAM_IG"     -> "A4", its code
  what names a holder or an      "Alex", "Example",     -> "[withheld]"
  account and is left over       "0123456"

A short form is a leading run of two or more of an account's words that begins no other
account's name, so "Alex ii" is withheld rather than guessed between the ISA and the SIPP.

THEN A CHECK, ON THE ANSWER AS IT WILL BE SENT: every holder's word, register name and number is
looked for again. One found means the renaming missed a place, and the answer is refused rather
than sent (`Withheld`). A note that names a holder in a shape nobody foresaw costs that reader one
page, never the holder's name.

WHAT COMES BACK IN is a label or a code, never a register name: a filter the page sends is mapped
to the account the engine knows, and anything else is refused, so the door cannot be asked
whether a name exists.
"""
from __future__ import annotations

import json
import re

#: What a holder's name or an account's number reads as, to a reader who may not see it.
WITHHELD = "[withheld]"

#: No letter or digit may touch a word that is renamed, so "Sam" is found in "Sam's" and in
#: "SAM_IG" but not inside a longer word.
_LEFT, _RIGHT = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])"


class Withheld(Exception):
    """An answer still naming a holder or a number after renaming, and so not sent."""


class Naming:
    def __init__(self, register, codes):
        label = dict(zip(codes["account"], codes["label"]))
        code = dict(zip(codes["account"], codes["code"]))
        words = {a: a.split() for a in register["account"]}
        self._subs: dict[str, str] = {}
        for r in register.itertuples(index=False):
            for w in (r.holder, *r.holder_names, r.number):
                if str(w).strip():
                    self._subs.setdefault(str(w).lower(), WITHHELD)
        for a, ws in words.items():
            for n in range(2, len(ws)):
                lead = [w.lower() for w in ws[:n]]
                if not any(b != a and [w.lower() for w in words[b][:n]] == lead for b in words):
                    for sep in (" ", "_"):
                        self._subs[sep.join(lead)] = code[a]
            self._subs[a.lower()] = label[a]
        # A REGISTER WITH NO ACCOUNT HAS NOTHING TO RENAME, and an empty alternation would match
        # every gap between two letters: `(?!)` matches nowhere.
        self._pattern = re.compile(
            _LEFT + "(" + ("|".join(re.escape(k) for k in sorted(self._subs, key=len, reverse=True))
                           or "(?!)") + ")" + _RIGHT, re.IGNORECASE)
        self._names = sorted({w.lower() for r in register.itertuples(index=False)
                              for w in (*r.holder_names, r.account)})
        self._numbers = sorted({str(n).lower() for n in register["number"] if str(n).strip()})
        self._back = {**{v.lower(): a for a, v in label.items()},
                      **{v.lower(): a for a, v in code.items()}}

    def _text(self, s: str) -> str:
        return self._pattern.sub(lambda m: self._subs[m.group(0).lower()], s)

    def rename(self, answer):
        """The answer with every string renamed, dictionary keys included, and checked."""
        def walk(v):
            if isinstance(v, str):
                return self._text(v)
            if isinstance(v, dict):
                return {walk(k): walk(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [walk(x) for x in v]
            return v
        out = walk(answer)
        self.check(json.dumps(out, ensure_ascii=False, default=str))
        return out

    def check(self, text: str) -> None:
        """Refuse a text still carrying a holder's word or an account's register name with no
        letter beside it, or an account's number anywhere at all."""
        low = text.lower()
        found = [w for w in self._names
                 if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low)]
        found += [n for n in self._numbers if n in low]
        if found:
            raise Withheld(f"{len(found)} word(s) that name a holder or an account were left in "
                           f"this answer, so it was not sent")

    def account(self, sent: str) -> str:
        """The register's account for a label or a code the page sent; "" stays "" (every
        account). Anything else is refused."""
        if not sent:
            return ""
        try:
            return self._back[sent.strip().lower()]
        except KeyError:
            raise ValueError(f"no account is called {sent!r}") from None


_made: dict = {"book": None, "naming": None}


def of(book) -> Naming:
    """The renaming for this engine, made once for each engine the desk loads, so it follows the
    register as the store changes."""
    if _made["book"] is not book:
        _made["naming"] = Naming(book.account_register(), book.account_codes())
        _made["book"] = book
    return _made["naming"]
