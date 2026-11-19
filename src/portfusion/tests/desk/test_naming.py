"""`desk/naming.py`, held to account codes these tests build for themselves."""
from __future__ import annotations

import pandas as pd
import pytest

from portfusion.desk import naming

CODES = pd.DataFrame({
    "account": ["Ann HL ISA", "Bob ii ISA", "Bob ii SIPP", "Ann IG Spread bet"],
    "code": ["A1", "A2", "A3", "A4"],
    "label": ["A1 · HL ISA", "A2 · ii ISA", "A3 · ii SIPP", "A4 · IG Spread bet"],
})


def test_an_account_comes_back_by_its_label_or_code_and_nothing_else():
    n = naming.Naming(CODES)
    assert n.account("A2 · ii ISA") == n.account("a2") == "Bob ii ISA"
    assert n.account("") == ""
    with pytest.raises(ValueError):
        n.account("Bob ii ISA")


def test_the_map_follows_the_engine_it_was_made_for():
    class Book:
        def account_codes(self):
            return CODES
    first, second = Book(), Book()
    assert naming.of(first) is naming.of(first)
    assert naming.of(second) is not naming.of(first)
