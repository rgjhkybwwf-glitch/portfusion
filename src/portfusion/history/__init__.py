"""THE HISTORIES — prices, FX rates and account values over time.

`prices.py`, `fx.py`, `accounts.py`: one contract, three files. None is a record table — each
owns its own CSV, banks rather than replaces, and is read by `load_store()` so the engine can
value a past date. The build never imports them. A history is banked BEFORE a refresh replaces
the marks it holds; `python3 -m portfusion.feeds.refresh` does both, in that order. The price
and FX histories keep only the marks a figure can take (`AppendOnlyCSV.kept()`).
"""
