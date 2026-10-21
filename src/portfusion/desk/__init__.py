"""desk/ — the book in a browser.

`store/` holds the facts, `engine.py` is the engine, and this package renders it to a browser, as
`report/` renders a quarter to a page. Both are renderers of the same view data; neither defines it.

NOTHING IN THE BOOK IMPORTS THIS — `tests/desk/test_boundaries.py` holds it. Delete this
directory and the report builds exactly as before.

Each module's docstring holds the rules for it; running the desk, and every macOS trap, is
`docs/desk-app.md`.
"""
