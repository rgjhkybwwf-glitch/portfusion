"""desk/doors/ — the only modules that write to store/.

`commit` appends an event, `marks` replaces a mark, `observations` replaces an account reading,
`freeze` appends a frozen quarter end, and `research_notes` appends a note's rows. Append against
replace is the marks rule's distinction, and the reason these are separate modules.
tests/desk/test_boundaries.py holds the set: every store write under desk/ is made from here, and
everything here makes one.
"""
