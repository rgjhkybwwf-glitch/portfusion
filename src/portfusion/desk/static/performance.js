/* PERFORMANCE: the page's draw. */

Object.assign(DRAW, {
  performance(d) {
    const quarters = [...d.firm, ...d.accounts];
    /* WHAT A ROW'S CLOSING NAV RESTS ON: an account's, its source and quality; the book's, each
       account's part of it. The quarter still open has neither. */
    const rests = (r) => r.nav_rows ? detailList(r, ["nav_rows"], d.nav_columns)
                                    : detailList(r, d.detail);
    const opens = new Set(quarters.filter((r, n) => !n || r.account !== quarters[n - 1].account));
    /* NO BENCHMARK: an index return is TIME-WEIGHTED and this book's MONEY-WEIGHTED, and the two
       do not subtract. */
    return page({
      scope: `every return on ${d.measure}, modified Dietz (day-weighted)`,
      status: d.reports.length ? [{ label: "Reports",
        body: d.reports.map(reportLink).join(" · ") }] : null,
      /* SINCE THE RECORD BEGAN: the day, what the book stood at, and the engine's return from
         it. What was bought before that day is in the opening figure and in no return. */
      figures: [["Record begins", esc(day(d.since.begins))],
                [sentence(HEADS.opening_nav), money(d.firm[0]?.opening_nav)],
                [d.since.label, pct(d.since.return)]],
      /* THE BOOK AND EACH ACCOUNT IN ONE TABLE, under one set of heads:
         the same columns named alike, so a figure is read down its column from the book to
         any account. THE ACCOUNT IS A COLUMN, named on its first row and blank on the rest,
         with a rule where the next one starts. */
      /* ONE GRID FOR THE TWO TABLES: the year's table takes the Quarter
         column's place with "Year to date", so its opening NAV, capital deployed, income,
         closing value, gain and return each sit under the quarter table's, in the same widths;
         its year-only columns follow. */
      work: table(quarters, d.columns, "", () => "",
                  { sort: false, align: "performance",
                    cells: { account: (r) => `<td>${opens.has(r) ? esc(r.account) : ""}</td>` },
                    rowClass: (r) => opens.has(r) && r !== quarters[0] ? "opens" : "",
                    afterRow: (r, span) => detailRow(rests(r), span) }) +
        `<h2>The year so far, from ${esc(day(d.year_from))}</h2>` + table(d.year, d.year_columns,
          "", () => "", { sort: false, align: "performance",
            inserts: [{ after: "account", head: NO_HEAD, cell: () => "<td>Year to date</td>" }] }),
      why: d.caveats.map((c) => [c.scope, c.detail]),
    });
  },
});
