/* ROUND TRIPS: the page's draw and its filters, through the one mechanism, wireFilters(). */

const owes = (x, flags) => flags.some((f) => x[f]);

/* ROUND TRIPS' TWO VIEWS, in the engine's words. */
const viewField = (d) => filterField("view", `<select id="rt-view">${d.views.map((v) =>
  `<option value="${esc(v)}"${v === d.view ? " selected" : ""}>${esc(d.view_words[v])}</option>`)
  .join("")}</select>`);

/* A COMPANY LIFE, Round Trips' second view: its shares and bets in every account, first purchase
   to final sale. A life spans accounts and codes, so only company and dates narrow it. */
function companyLives(d) {
  const t = d.totals, w = d.whole;
  return page({
    scope: "each company, first purchase to final sale, shares and bets together",
    status: d.narrowed ? [{ state: "note", tag: "selected", label: "Whole book",
      body: quiet(`${w.lives} lives · life gain ${money(w.life_gain)}`) }] : null,
    figures: [["Lives", t.lives], ["Open", t.open],
              ["Realised gain", money(t.realised)], ["Life gain", money(t.life_gain)]],
    filters: { clear: "rt-clear", fields: [
      filterField("company", `<select id="rt-company"><option value="">all</option>${d.companies.map((c) =>
        `<option${c === d.company ? " selected" : ""}>${esc(c)}</option>`).join("")}</select>`),
      filterField("closed from", `<input type="date" id="rt-from" value="${esc(d.start)}"
             min="${esc(d.span.first || "")}" max="${esc(d.span.last || "")}">`),
      filterField("closed to", `<input type="date" id="rt-to" value="${esc(d.end)}"
             min="${esc(d.span.first || "")}" max="${esc(d.span.last || "")}">`),
      viewField(d),
    ] },
    work: table(d.rows, d.columns, NO_HEAD,
                (r) => `<td class="nowrap">${tradesButton(r.company)}</td>`,
                { name: "company lives", afterRow: (r, span) => detailRow(detailList(r, d.detail), span),
                  cells: {
                    opened: (r) => `<td class="nowrap">${esc(day(r.opened))}${r.pre_baseline
                      ? ` <span class="tag">before the record</span>` : ""}</td>`,
                    qty: (r) => `<td class="num">${r.qty == null ? "—"
                      : r.qty.toLocaleString("en-GB")}</td>`,
                    currency: (r) => r.currency == null ? `<td>—</td>` : cell("currency", r.currency) } }),
  });
}

Object.assign(DRAW, {
  "round-trips"(d) {
    if (d.view === "life") return companyLives(d);
    /* THE FIGURES ARE THE SELECTION'S. When a filter is on, the whole book sits beside them as
       context rather than as the answer. */
    const t = d.totals, w = d.whole;
    return page({
      scope: "every position sold, in part or whole, gain net of dealing commission",
      status: d.narrowed ? [{ state: "note", tag: "selected", label: "Whole book",
        body: quiet(`${w.realisations} round trip(s) · proceeds ${money(w.proceeds)}
          · realised gain ${money(w.realised)}`) }] : null,
      figures: [["Round trips", t.realisations],
                ["Closed out", t.closed_out],
                ["Proceeds", money(t.proceeds)],
                ["Realised gain", money(t.realised)]],
      filters: { clear: "rt-clear", fields: [
        filterField("account", `<select id="rt-acct"><option value="">all</option>${d.accounts.map((a) =>
          `<option${a === d.account ? " selected" : ""}>${esc(a)}</option>`).join("")}</select>`),
        filterField("company", `<select id="rt-company"><option value="">all</option>${d.companies.map((c) =>
          `<option${c === d.company ? " selected" : ""}>${esc(c)}</option>`).join("")}</select>`),
        filterField("ticker", `<select id="rt-ticker"><option value="">all</option>${d.tickers.map((x) =>
          `<option${x === d.ticker ? " selected" : ""}>${esc(x)}</option>`).join("")}</select>`),
        filterField("closed from", `<input type="date" id="rt-from" value="${esc(d.start)}"
               min="${esc(d.span.first || "")}" max="${esc(d.span.last || "")}">`),
        filterField("closed to", `<input type="date" id="rt-to" value="${esc(d.end)}"
               min="${esc(d.span.first || "")}" max="${esc(d.span.last || "")}">`),
        /* THE CLOSED-OUT LINES ALONE, under the column's own heading and in its cells' word. */
        filterField(HEADS.fully_closed, `<select id="rt-closed"><option value="">all</option>
          <option value="yes"${d.closed_only ? " selected" : ""}>yes</option></select>`),
        viewField(d),
      ] },
      /* THE SAME Trades BUTTON AS HOLDINGS', by company: the sales a round trip took, and the
         buys before them, are Trades' to show. The row opens its detail: its whys, research
         notes and note. */
      work: table(d.rows, d.columns, NO_HEAD,
                  (r) => `<td class="nowrap">${tradesButton(r.company)}${owes(r, d.owed)
                    ? ` ${owedTag()}` : ""}</td>`,
                  { name: "round trips", afterRow: (r, span) => detailRow(detailList(r, d.detail), span),
                    /* A SPREAD BET IN ITS OWN TERMS, as Trades reads one: its stake per point
                       for a quantity, its entry and exit as levels in points, and no currency
                       of its own. A share's prices are in the Ccy column's currency. */
                    cells: {
                      currency: (r) => r.stake == null ? cell("currency", r.currency)
                                                                 : `<td>—</td>`,
                      qty: heldCell,
                      entry_price: (r) => r.stake != null
                        ? pointsCell(r.entry_level_points)
                        : `<td class="num">${localPrice(r.entry_price, r.currency)}</td>`,
                      exit_price: (r) => r.stake != null
                        ? pointsCell(r.exit_level_points)
                        : `<td class="num">${localPrice(r.exit_price, r.currency)}</td>` } }),
    });
  },
});

Object.assign(WIRE, {
  "round-trips"(d, again) {
    /* ARRIVED FROM A "company life" LINK: the life view, narrowed to the link's company. The
       Company box lists the companies with a round trip, so one with none yet is added to it. */
    if (PENDING_COMPANY && !again) {
      const box = $("#rt-company");
      if (box && ![...box.options].some((o) => o.value === PENDING_COMPANY)) box.add(new Option(PENDING_COMPANY));
      HELD_FILTERS["round-trips"] = { "rt-view": "life", "rt-company": PENDING_COMPANY };
      PENDING_COMPANY = null;
    }
    const view = (v) => `/api/round-trips?view=${encodeURIComponent(v["rt-view"] || "holding")}`;
    /* A COMPANY CHOSEN STARTS ITS TICKER AFRESH, and the page comes back with that company's
       codes in the Ticker box. */
    wireFilters("round-trips", d, again, {
      ids: ["rt-view", "rt-acct", "rt-company", "rt-ticker", "rt-from", "rt-to", "rt-closed"],
      button: "rt-clear",
      resets: { "rt-company": "rt-ticker" },
      ask: (v) => view(v) + `&ticker=${encodeURIComponent(v["rt-ticker"])}`
        + `&company=${encodeURIComponent(v["rt-company"])}`
        + `&account=${encodeURIComponent(v["rt-acct"])}`
        + `&start=${encodeURIComponent(v["rt-from"])}`
        + `&end=${encodeURIComponent(v["rt-to"])}`
        + (v["rt-closed"] === "yes" ? "&closed_only=true" : ""),
      clear: view });
  },
});
