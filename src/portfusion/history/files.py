"""THE HISTORIES' FILES: each one's name and its columns, and nothing that loads a book.

Here rather than in each history because `tools/make_demo.py` writes these files before any book
exists. A history module imports the record, and the record loads a store on import, so the
generator could not run after a change to the very schema it was being run to follow.

Each history reads its own pair from here (`prices.CSV_NAME`, `prices.FIELDS` and so on), so the
names a caller already uses stand.
"""

# The FILE, not a path to it: `AppendOnlyCSV` resolves it against whichever store the record
# is reading.
PRICES = "price-history.csv"
PRICE_FIELDS = ["mark_key", "date", "price", "currency", "quality", "struck", "status", "source"]

FX = "fx-history.csv"
FX_FIELDS = ["currency", "date", "rate", "kind", "quality", "struck", "status", "source"]

ACCOUNTS = "account-statements.csv"
ACCOUNT_FIELDS = ["account", "as_of", "positions_value", "cash", "funds", "running_pl", "equity",
                  "deposit", "source", "quality", "status"]
