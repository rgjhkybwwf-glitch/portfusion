/* TRADES: the page's draw and its filters, through the one mechanism, wireFilters(). */

Object.assign(DRAW, {
  /* TRADES — every buy and sale on file, interrogable.
     Dates and account go to book.activity(); ticker and direction narrow the result. Nothing
     is computed here. */
  trades(d) {
    const price = localPrice, v = d.chosen || {};
    const opts = (list, sel) => `<option value="">all</option>` +
      list.map((x) => `<option${x === sel ? " selected" : ""}>${esc(x)}</option>`).join("");
    const date = (id) => `<input id="${id}" type="date" min="${esc(d.span.first || "")}"
               max="${esc(d.span.last || "")}" value="${esc(v[id] || "")}">`;
    /* THE TICKER BOX IS THE CHOSEN COMPANY'S, so it cannot name a line the Company box has ruled
       out; a company chosen starts its ticker afresh. */
    const co = v["q-company"] || "";
    const count = `${d.total} trade${d.total === 1 ? "" : "s"}` +
      (d.span.first ? ` · ${day(d.span.first)} to ${day(d.span.last)}` : "");

    return page({
      scope: "every buy and sale on file",
      status: [{ label: "Trades", body: `<span id="q-count" class="muted small">${esc(count)}</span>` }],
      filters: { clear: "q-clear", fields: [
        filterField("account", `<select id="q-account">${opts(d.accounts, v["q-account"])}</select>`),
        filterField("company", `<select id="q-company">${opts(d.companies || [], co)}</select>`),
        filterField("ticker", `<select id="q-ticker">${
          opts(co ? d.company_tickers[co] || [] : d.tickers, v["q-ticker"])}</select>`),
        filterField("from", date("q-start")),
        filterField("to", date("q-end")),
        filterField("direction", `<select id="q-direction">${opts(d.directions, v["q-direction"])}</select>`),
      ] },
      /* A TABLE IN HOLDINGS' ORDER: the deal as struck on the line, and
         everything else the record holds on the trade in its detail. A spread bet reads in its
         own terms, a stake per point at a level in points, with no currency of its own. */
      work: `<div id="q-rows">${d.rows.length ? table(d.rows, d.columns, "", () => "",
        { name: "trades", afterRow: (r, span) => detailRow(detailList(r, d.detail), span),
          cells: {
            currency: (r) => r.level_points == null ? cell("currency", r.currency) : `<td>—</td>`,
            qty: heldCell,
            traded_price: (r) => r.level_points == null
              ? `<td class="num">${price(r.traded_price, r.currency)}</td>`
              : pointsCell(r.level_points) } })
        : `<p class="muted">nothing matches those filters.</p>`}</div>`,
    });
  },
});

Object.assign(WIRE, {
  /* Dates and account go to book.activity(); ticker and direction narrow the result. Its answer
     is the rows, drawn over the page's own data. */
  trades(d, again) {
    /* ARRIVED FROM A "trades" LINK: the link's company is taken once, as the filter held, and
       asked for below; from then on it is held as any filter here is. */
    if (PENDING_COMPANY && !again) {
      HELD_FILTERS.trades = { "q-company": PENDING_COMPANY };
      PENDING_COMPANY = null;
    }
    wireFilters("trades", d, again, {
      ids: ["q-account", "q-company", "q-ticker", "q-start", "q-end", "q-direction"], button: "q-clear",
      resets: { "q-company": "q-ticker" },
      ask: (v) => `/api/trades?${new URLSearchParams({ start: v["q-start"], end: v["q-end"],
        account: v["q-account"], ticker: v["q-ticker"], direction: v["q-direction"],
        company: v["q-company"] })}`,
      clear: () => "/api/trades" });
  },
});
