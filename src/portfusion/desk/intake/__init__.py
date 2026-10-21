"""desk/intake/ — the workbench: a document in, proposed rows out.

Nothing here writes to store/. A document lands in _inbox/ through `dropoff`, is read
(`read_document`, `read_rows`, or a Claude session through `propose`, held to `verify`), worked
as a bench item (`bench`), and leaves through a door in desk/doors/ or back out through
`withdraw`. `broker` and `statement_closes` read the broker's side; `research` reads the notes
repository.
"""
