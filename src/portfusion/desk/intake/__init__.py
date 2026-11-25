"""desk/intake/ — the workbench: a document in, proposed rows out.

Nothing here writes to store/. A document lands in _inbox/ through `dropoff`, the one door in, is
read (`read_document`, `read_rows`, or a Claude session through `propose`, held to `verify`),
worked as a bench item (`bench`) on its form (`bench_form`) until its gates clear
(`bench_gates`), against what the record already holds (`recorded`), and leaves through a door in
desk/doors/, filed under its name (`filing`), or, not used, through `withdraw`, the one door out.
`sweep` asks the feeds and writes nothing; `statement_closes` reads the broker's filed side;
`research` reads the notes repository.
"""
