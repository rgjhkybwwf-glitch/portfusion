"""record/ — the record's schema and rules. The facts themselves are in store/.

Each module's own docstring says what it is for, and why the two `rules_*` modules must stay pure.
Import a module, never its names — `from portfusion.record import rules` — for the reason
`rules.reload_store()` gives.
"""
