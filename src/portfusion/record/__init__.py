"""record/ — the record's schema and rules. The facts themselves are in store/.

    schema.py  rules.py  rules_evidence.py  rules_brokers.py

What each is for is README.md's folder map; why the two `rules_*` modules must stay
pure is their own docstrings'. Import a module, never its names — `from portfusion.record import rules` — for the reason
`rules.reload_store()` gives.
"""
