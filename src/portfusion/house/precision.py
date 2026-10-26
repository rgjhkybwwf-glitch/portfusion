"""house/precision.py — how many decimal places a figure shows, and how a date reads, on every
renderer.

A LOCAL PRICE is a price in its line's own currency, which the Ccy column beside it names:
LOCAL_PRICE_FIELDS says which fields are one. Its precision is per currency: GBP keeps 4dp
because LSE prices are quoted in pence and stored /100 (a line at 12.35p is 0.1235, which 2dp would
round to 0.12). The desk sends all of it to the page with every panel answer, as it stands.

EVERY PERCENTAGE THE PROJECT PRINTS has one precision, PCT_DP: the desk, `portfusion record`, the
report and the Method page. Printing only — stored figures keep their own precision
(quarter-results to six places).

STERLING is to the penny, MONEY_DP, on the desk, in the audit and in the engine's own words; the
published report rounds it to the pound, REPORT_MONEY_DP, but for its two cash tables (money in
and out; income and costs), which keep the penny as a statement does. MONEY_FIELDS and PCT_FIELDS
name the fields the desk prints as each. A negative amount reads -£5.82, the sign outside the £.
A RATE, per £1, is at RATE_DP.

ONE ROUNDING: an exact half rounds away from zero, once, at display, from the figure's own
decimal digits (its shortest spelling), never from the binary float under them. The desk's
core.js rounds the same way. A total is the engine's exact sum, rounded; never rounded parts
added up.

EVERY DATE A READER SEES reads "14 Oct 2026": the day without
a leading nought, the month's three letters, the year; a moment adds the time, "14 Oct 2026,
10:39". The desk, `portfusion record` and the report's tables print it, and the report's prose
keeps the full month ("30 September 2026"). The desk is sent MONTHS with every panel, so core.js
types no month of its own. A stored date stays ISO, which is also what a table sorts by: this is
printing only.

Imports nothing but the standard library, so the desk reads it without loading the record.
"""
from decimal import ROUND_HALF_UP, Decimal

LOCAL_PRICE_FIELDS = ("entry_price", "exit_price", "price", "traded_price",
                      "life_cost_per_share")

LOCAL_PRICE_DP = {"USD": 2, "EUR": 2, "DKK": 2, "GBP": 4}
DEFAULT_LOCAL_PRICE_DP = 2

PCT_DP = 2

MONEY_DP = 2
REPORT_MONEY_DP = 0
RATE_DP = 4

MONEY_FIELDS = ("cost", "value", "gain", "unrealised", "proceeds",
                "opening_nav", "closing_nav", "capital_deployed", "return_income",
                "change", "price_effect", "fx_effect", "transacted", "value_to",
                "exposure", "nav", "capital_employed", "capital_growth",
                "amount", "cash", "realised", "dividends", "funding_interest",
                "total", "life_gain", "book", "broker", "difference")
PCT_FIELDS = ("unrealised_pct", "realised_pct", "weight", "return", "price_move_pct", "ytd",
              "life_pct")

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def fixed(value, places: int, spec: str = ",", shift: int = 0) -> str:
    """`value` at `places`, an exact half away from zero, from its own decimal digits; `spec` is
    the format's sign and grouping ("+," signed and grouped, "" neither), `shift` moves the point
    first. fixed(2.675, 2) -> '2.68', fixed(-12.5, 0, "+,") -> '-13'."""
    d = Decimal(repr(float(value))).scaleb(shift)
    return format(d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP),
                  f"{spec}.{places}f")


def money(value, places: int = MONEY_DP, signed: bool = False, symbol: bool = True) -> str:
    """Sterling at `places`, the sign outside the £: money(-5.821) -> '-£5.82'; `signed` writes
    a plus too, `symbol=False` no £ (the report's cells, under a heading that names it). A dash
    where there is none."""
    if value is None or value != value:
        return "—"
    text = fixed(value, places, "+," if signed else ",")
    sign = text[0] if text[0] in "+-" else ""
    return f"{sign}£{text[len(sign):]}" if symbol else text


def rate(value) -> str:
    """A rate per £1 at RATE_DP places: 1.33 -> '1.3300'. A dash where there is none."""
    if value is None or value != value:
        return "—"
    return fixed(value, RATE_DP, "")


def local_price(value, currency: str) -> str:
    """Printed at LOCAL_PRICE_DP's places for `currency`, as the desk's localPrice() prints it:
    0.1235 GBP, 150.00 USD. A dash where there is none."""
    if value is None or value != value:
        return "—"
    return fixed(value, LOCAL_PRICE_DP.get(currency, DEFAULT_LOCAL_PRICE_DP), "")


def points(value) -> str:
    """A spread bet's level, as the desk's points() prints one: grouped, to two places at most,
    "10,000.5 pts". A dash where none."""
    if value is None or value != value:
        return "—"
    return fixed(value, 2).rstrip("0").rstrip(".") + " pts"


def pct(fraction: float) -> str:
    """`fraction` printed as a percentage at PCT_DP places: 0.454301 -> '45.43%'."""
    return fixed(fraction, PCT_DP, "", shift=2) + "%"


def day(value) -> str:
    """A date as a reader sees it: '2026-10-14', a date, a datetime or a Timestamp -> '14 Oct 2026'.
    What is not a date is left as it came, as core.js's day() leaves it, and none is a dash."""
    if value is None:
        return "—"
    text = str(value)
    if not (len(text) >= 10 and text[4] == text[7] == "-" and text[:4].isdigit()
            and text[5:7].isdigit() and text[8:10].isdigit()):
        return text
    y, m, d = text[:10].split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def day_month(value) -> str:
    """A date's day and month, where its year is said beside it: '2026-09-30' -> '30 Sep'."""
    return day(value).rsplit(" ", 1)[0]


def moment(value) -> str:
    """A date and its time: '2026-10-14T10:39:43' or a datetime -> '14 Oct 2026, 10:39'. A value
    with no time is a day."""
    text = str(value)
    return f"{day(text)}, {text[11:16]}" if len(text) >= 16 else day(text)
