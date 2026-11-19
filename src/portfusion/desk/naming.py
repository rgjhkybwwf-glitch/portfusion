"""AN ACCOUNT BY ITS LABEL OR ITS CODE, back to the register's name the engine knows.

    from portfusion.desk import naming
    naming.of(engine.book()).account("A4 · IG Spread bet")     # "Sam IG Spread bet"

The reading pages name an account by its label, so a filter a page sends comes back as a label or
a code; this maps it to the account. The codes and labels are `Book.account_codes()`. Nothing
here is typed: a new account joins by being registered.
"""
from __future__ import annotations


class Naming:
    def __init__(self, codes):
        self._back = {**{v.lower(): a for a, v in zip(codes["account"], codes["label"])},
                      **{v.lower(): a for a, v in zip(codes["account"], codes["code"])}}

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
    """The map for this engine, made once for each engine the desk loads, so it follows the
    register as the store changes."""
    if _made["book"] is not book:
        _made["naming"] = Naming(book.account_codes())
        _made["book"] = book
    return _made["naming"]
