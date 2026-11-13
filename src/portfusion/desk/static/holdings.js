/* HOLDINGS: the page's draw and its filters, through the one mechanism, wireFilters(). */

/* A HOLDING'S DETAIL. Grouped by issuer, a row is every instrument the company is held through,
   and each carries its own thesis, so each is named; the mark history is a ticker row's. */
const holdingDetail = (r, d) => {
  const each = (r.reasons || []).map((x) => [x, detailList(x, d.detail)]).filter(([, h]) => h);
  return each.map(([x, h]) =>
    (r.reasons.length > 1 ? `<p><strong>${esc(x.ticker)}</strong></p>` : "") + h).join("")
    + [["life", d.life_columns], ["income", d.income_columns], ["marks", d.mark_columns]]
      .map(([c, cols]) => d.detail.includes(c) ? detailList(r, [c], cols) : "").join("");
};

/* WHERE THE EXPOSURE SITS, under Holdings' table: the report's split by currency, region and
   sector, in its words, one bar per slice, largest first. The bar is drawn on a 0–1 scale, so
   its length IS the engine's share_of_largest: nothing here divides, and no width is set
   inline (pages.css draws it). It follows the account filter as the table does. */
const allocation = (d) => !d.allocation ? "" : `<h2>Where the exposure sits</h2>
  <div class="allocs">${Object.entries(d.allocation).map(([axis, slices]) => `
    <table class="alloc"><thead><tr><th>${esc(sentence(d.allocation_heads[axis]))}</th>${NO_HEAD}
      <th class="num">${esc(sentence(d.allocation_heads.share))}</th></tr></thead>
      <tbody>${slices.map((s) => `<tr><td class="oneline">${esc(s.key ?? "—")}</td>
        <td class="alloc-bar"><svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">
          <rect class="track" width="1" height="1"/><rect width="${Number(s.share_of_largest) || 0}" height="1"/></svg></td>
        <td class="num">${pct(s.share)}</td></tr>`).join("")}</tbody></table>`).join("")}
  </div>`;

Object.assign(DRAW, {
  holdings(d) {
    /* OWNED AND NOTIONAL, APART AND NEVER ADDED. Both come from the engine. */
    return page({
      scope: "securities owned and spread-bet notional, shown apart and never added",
      /* A SECOND DOOR TO THE BAY, because this is where you are standing when you doubt a
         value — but a LINK, never a second button. One refresh, two ways in; two buttons
         would be two places to keep telling the same story about what a refresh does. */
      status: [{ label: "Marks", body: `${quiet(`as at ${esc(day(d.valued_at))}`)}
        ${panelLink("price-refresh", "run a refresh")}` }],
      figures: [["Securities owned", money(d.owned)],
                ["Spread-bet notional", money(d.notional)]],
      filters: { clear: "h-clear", fields: [
        filterField("account", `<select id="h-acct"><option value="">all</option>${d.accounts.map((a) =>
          `<option${a === d.account ? " selected" : ""}>${esc(a)}</option>`).join("")}</select>`),
        filterField("group by", `<select id="h-by">${d.groupings.map((g) =>
          `<option value="${esc(g)}"${g === d.by ? " selected" : ""}>${esc(d.grouping_words[g])}</option>`)
          .join("")}</select>`),
      ] },
      why: [["Securities owned and notional", d.note]],
      work: `${/* ONE CLICK TO THE WHOLE HISTORY, by COMPANY and not by ticker: one company can be a
            share AND a spread bet, and a button that showed one leg would answer half the question
            while looking complete. */ ""}
      ${table(d.rows, d.columns, NO_HEAD,
              (r) => `<td class="nowrap">` + tradesButton(r.company) +
                ((r.reasons || []).some((x) => x.why_entered_owed) ? ` ${owedTag()}` : "") +
                `</td>`,
              {name: "holdings", afterRow: (r, span) => detailRow(holdingDetail(r, d), span),
               inserts: [{after: "held_as", head: `<th class="num">${head("qty")}</th>`,
                          cell: heldCell}]})}
      ${allocation(d)}`,
    });
  },
});

Object.assign(WIRE, {
  holdings(d, again) {
    wireFilters("holdings", d, again, { ids: ["h-by", "h-acct"], button: "h-clear",
      ask: (v) => `/api/holdings?by=${encodeURIComponent(v["h-by"])}`
        + `&account=${encodeURIComponent(v["h-acct"])}`,
      clear: () => "/api/holdings" });
  },
});
