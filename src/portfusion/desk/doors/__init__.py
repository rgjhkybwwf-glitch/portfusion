"""desk/doors/ — the only modules that write to store/.

`commit` appends an event, `marks` replaces a mark, `observations` replaces an account reading,
and `freeze` appends a frozen quarter end. Append against replace is the marks rule's distinction,
and the reason these are separate modules. tests/desk/test_boundaries.py holds the set: every
store write under desk/ is made from here, and everything here makes one.
"""
