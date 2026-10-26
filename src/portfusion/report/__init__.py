"""report/ — the quarterly report, a page rendered for the request: the desk's Reports page asks for
it, and `portfusion report --check` asks whether a quarter is ready.

IT FREEZES THE INPUTS, NOT THE OUTPUT. Every figure comes from dated rows in the store —
quarter-end NAV, prices, FX, statements — so a closed quarter regenerates as it first printed. The
page is not kept; a closed quarter's results are, in `quarter-results.csv`, and the suite fails
if the engine stops giving them.

gate.py refuses a half-arrived quarter, page.py renders the page and style.py styles it. None of
them computes a figure: every one is the engine's, held to the desk's by
tests/test_figures.py.
"""
