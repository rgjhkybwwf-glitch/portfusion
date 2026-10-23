"""house/precision.py — how many decimal places a figure shows, and how a date reads, on every
renderer.

A LOCAL PRICE is a price in its line's own currency, which the Ccy column beside it names:
LOCAL_PRICE_FIELDS says which fields are one. Its precision is per currency: GBP keeps 4dp
because LSE prices are quoted in pence and stored /100 (a line at 12.35p is 0.1235, which 2dp would
round to 0.12). The desk sends all of it to the page with every panel answer, as it stands.

EVERY PERCENTAGE THE PROJECT PRINTS has one precision, PCT_DP (the desk review, Holdings decision
4, 10 Oct 2026): the desk, `portfusion record`, the report and the Method page. Printing only —
stored figures keep their own precision (quarter-results to six places).

EVERY DATE A READER SEES reads "14 Oct 2026": the day without
a leading nought, the month's three letters, the year; a moment adds the time, "14 Oct 2026,
10:39". The desk, `portfusion record` and the report's tables print it, and the report's prose
keeps the full month ("30 September 2026"). The desk is sent MONTHS with every panel, so app.js
types no month of its own. A stored date stays ISO, which is also what a table sorts by: this is
printing only.

Imports nothing, so the desk reads it without loading the record.
"""

LOCAL_PRICE_FIELDS = ("entry_price", "exit_price", "current_price", "traded_price",
                      "net_cost_per_share")

LOCAL_PRICE_DP = {"USD": 2, "EUR": 2, "DKK": 2, "GBP": 4}
DEFAULT_LOCAL_PRICE_DP = 2

PCT_DP = 2

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def local_price(value, currency: str) -> str:
    """Printed at LOCAL_PRICE_DP's places for `currency`, as the desk's localPrice() prints it:
    0.1235 GBP, 150.00 USD. A dash where there is none."""
    if value is None or value != value:
        return "—"
    return f"{value:.{LOCAL_PRICE_DP.get(currency, DEFAULT_LOCAL_PRICE_DP)}f}"


def points(value) -> str:
    """A spread bet's level, as the desk's points() prints one: grouped, to two places at most,
    "10,000.5 pts". A dash where none."""
    if value is None or value != value:
        return "—"
    return f"{value:,.2f}".rstrip("0").rstrip(".") + " pts"


def pct(fraction: float) -> str:
    """`fraction` printed as a percentage at PCT_DP places: 0.454301 -> '45.43%'."""
    return f"{fraction * 100:.{PCT_DP}f}%"


def day(value) -> str:
    """A date as a reader sees it: '2026-10-14', a date, a datetime or a Timestamp -> '14 Oct 2026'."""
    y, m, d = str(value)[:10].split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def moment(value) -> str:
    """A date and its time: '2026-10-14T10:39:43' or a datetime -> '14 Oct 2026, 10:39'. A value
    with no time is a day."""
    text = str(value)
    return f"{day(text)}, {text[11:16]}" if len(text) >= 16 else day(text)
