"""`desk/naming.py`, held to a register these tests build for themselves: two holders, one of
them with two accounts at one broker, so a short form shared by two accounts can be seen to be
withheld rather than guessed.
"""
from __future__ import annotations

import pandas as pd
import pytest

from portfusion.desk import naming

REGISTER = pd.DataFrame({
    "account": ["Ann HL ISA", "Bob ii ISA", "Bob ii SIPP", "Ann IG Spread bet"],
    "holder": ["Ms Ann Smith", "Mr Bob Jones", "Mr Bob Jones", "Ms Ann Smith"],
    "number": ["1234567", "7654321", "0001112", "XYZ12"],
    "holder_names": [("Ann", "Smith"), ("Bob", "Jones"), ("Bob", "Jones"), ("Ann", "Smith")],
})
CODES = pd.DataFrame({
    "account": REGISTER["account"],
    "code": ["A1", "A2", "A3", "A4"],
    "label": ["A1 · HL ISA", "A2 · ii ISA", "A3 · ii SIPP", "A4 · IG Spread bet"],
})


@pytest.fixture()
def n():
    return naming.Naming(REGISTER, CODES)


def test_a_register_name_becomes_its_label_and_a_short_form_its_code(n):
    assert n.apply({"account": "Ann IG Spread bet"}) == {"account": "A4 · IG Spread bet"}
    assert n.apply("the Ann IG Zephyr leg, read via ANN_IG") == "the A4 Zephyr leg, read via A4"
    assert n.apply("Ann HL's dividend") == "A1's dividend"


def test_a_short_form_of_two_accounts_is_withheld_not_guessed(n):
    """"Bob ii" begins the ISA and the SIPP alike, so it names a holder and no one account."""
    assert n.apply("moved from Bob ii to Bob ii SIPP") == \
        f"moved from {naming.WITHHELD} ii to A3 · ii SIPP"


def test_a_holder_and_a_number_are_withheld_anywhere(n):
    assert n.apply("WHY (Bob, 31 Aug): per Ms Ann Smith, account 0001112") == \
        f"WHY ({naming.WITHHELD}, 31 Aug): per {naming.WITHHELD}, account {naming.WITHHELD}"


def test_keys_are_renamed_as_well_as_values(n):
    assert n.apply({"Bob ii ISA": [1, "Ann"]}) == {"A2 · ii ISA": [1, naming.WITHHELD]}


def test_a_word_inside_a_longer_word_is_left_alone(n):
    """"Annual" is not Ann, and "Bobsleigh" is not Bob."""
    assert n.apply("Annual Bobsleigh") == "Annual Bobsleigh"


def test_what_the_renaming_misses_is_refused_by_the_check(n):
    with pytest.raises(naming.Withheld):
        n.apply("Ann2 said so")
    with pytest.raises(naming.Withheld):
        n.check("ref ZZ1234567ZZ")


def test_an_account_comes_back_by_its_label_or_code_and_nothing_else(n):
    assert n.account("A2 · ii ISA") == n.account("a2") == "Bob ii ISA"
    assert n.account("") == ""
    with pytest.raises(ValueError):
        n.account("Bob ii ISA")


def test_the_renaming_follows_the_engine_it_was_made_for():
    class Book:
        def account_register(self):
            return REGISTER

        def account_codes(self):
            return CODES
    first, second = Book(), Book()
    assert naming.of(first) is naming.of(first)
    assert naming.of(second) is not naming.of(first)
