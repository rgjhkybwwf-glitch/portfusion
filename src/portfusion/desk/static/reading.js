/* THE PAGES THAT READ: What Changed, the Dashboard, Holdings, Round Trips, Method, Accounts,
   Reports, Performance, Trades and Reconcile. */

Object.assign(DRAW, {
  /* WHAT CHANGED — two bases, one under the other, never added. The panel hands over totals
     already computed per basis, because Book.change_totals() refuses to span them; this draws
     them, each block with its own columns.

     THE BLOCK TOTALS STAY PLAIN, deliberately, and it is the same rule the Dashboard's headline
     gains follow: movement colour's job is scanning a COLUMN, and a short summary is a list
     you read rather than a column you scan. The per-line table below is the scannable thing and
     it wears the colour. */
  "what-changed"(d) {
    const windows = (d.windows || []).map((w) =>
      `<span class="win">${w.priced_from ? esc(day(w.priced_from)) : "new line"} &rarr; ` +
      `${esc(day(w.priced_at))} <span class="muted">${w.lines} ` +
      `line${w.lines === 1 ? "" : "s"}</span></span>`).join("");

    /* THE TWO BLOCKS ARE ONE GRID: the same columns in the same widths, so a
       spread bet's figure sits under a share's; the From FX a bet has no part in is a dash. */
    const grid = d.grid || [];
    const block = (b) => {
      const t = b.totals;
      return `
        <section class="diff">
          <h3>${esc(b.label)}</h3>
          ${figures([
            ["Value then", money(t.value_from)],
            ["From price", money(t.price_effect)],
            ...(grid.includes("fx_effect")
              ? [["From FX", b.columns.includes("fx_effect") ? money(t.fx_effect) : "—"]] : []),
            ["From dealing", money(t.transacted)],
            ["Change", money(t.change)],
            ["Value now", money(t.value_to)],
          ])}
          ${b.rows.length
            ? table(b.rows, grid, "", () => "", { align: "blocks", name: b.label, cells: Object.fromEntries(
                grid.filter((c) => !b.columns.includes(c)).map((c) => [c, () => `<td class="num">—</td>`])) })
            : `<p class="muted">no lines on this basis.</p>`}
        </section>`;
    };

    /* THE SECOND CLOCK, store/journal.csv. Market time above, record time below, and each block
       says which — a mark banked at a month end and a dividend from the month before, entered
       days later, sit weeks apart on this page and answer different questions.

       NOTHING IS COUNTED HERE. The rows are Book.journal()'s and the discrepancy is
       Book.journal_reconciliation()'s; the panel selected them and this draws them. */
    const r = d.record || {};
    const gap = (r.unaccounted || []).map((u) =>
      `<li class="note"><span class="tag">by hand</span><strong>${esc(u.table)}</strong> —
       ${u.on_file} rows on file against ${u.expected} the journal accounts for.</li>`).join("");

    /* SHOWN ONCE, AND ONLY WHEN YOU ARRIVED HERE FROM A WRITE. It states the one thing this
       panel cannot: how many outgoing marks were banked before the new ones landed, which is
       the rule the Price Refresh exists to enforce and the only evidence that it ran. */
    /* THE FIGURES BELOW HAVE ALREADY MOVED and the receipt must not claim otherwise. The engine
       is cached on the STORE's mtime, so a write invalidates it and the next read is against
       the new marks — `marks.py` reloads the record for the same reason, and
       test_the_written_mark_is_visible_to_the_engine_without_a_restart holds it. */
    const wrote = LAST_REFRESH;
    LAST_REFRESH = null;
    const n = (k, word) => `${k} ${word}${k === 1 ? "" : "s"}`;
    const receipt = !wrote ? [] : [{ state: "clear", tag: "written", label: "Refresh",
      body: quiet(`${n(wrote.prices, "price")}, ${n(wrote.rates, "rate")} and
        ${n(wrote.readings || 0, "IG reading")} replaced ·
        ${n(wrote.banked_before.prices + wrote.banked_before.rates, "outgoing mark")} banked
        first, ${wrote.banked_after.prices + wrote.banked_after.rates || "none"} after`) }];

    /* RECORD TIME OVER THE SPAN MARKET TIME COVERS, the rest folded under it: the journal grows
       with every write, and what the book learned since the last refresh is this page's half. */
    const opened = r.opened ? esc(day(r.opened.slice(0, 10))) : "—";
    const since = r.since ? esc(day(r.since)) : opened;
    const earlier = r.earlier || [];
    return page({
      scope: "what the marks did, then what the book learned",
      status: [...receipt, { label: "Compared", body: quiet(windows || "—") }],
      work: `
        <h2>Market time &mdash; what the marks did</h2>
        ${d.blocks.map(block).join("")}
        <h2>Record time &mdash; every write since ${since}</h2>
        ${gap ? `<ul class="items">${gap}</ul>` : ""}
        ${(r.rows || []).length
          ? table(r.rows, r.columns, "", () => "", { name: "record" })
          : `<p class="muted">nothing written since ${since}.</p>`}
        ${earlier.length ? `<details class="earlier"><summary>${earlier.length} earlier,
          since the journal opened ${opened}</summary>${table(earlier, r.columns, "", () => "", { name: "earlier" })}</details>`
          : ""}`,
      why: [["Market time", d.caveat], ["Record time", r.caveat || ""]],
    });
  },

  dashboard(d) {
    /* WHAT NEEDS ATTENTION, THEN WHAT WAS CHECKED: the record's notes, in the engine's words and
       in the order `portfusion record` prints them, under the problems and gaps. A tag's space
       and no dot, so the text lines up with the items above it. */
    const items = d.attention.map((a) =>
      `<li class="${esc(a.level)}"><span class="tag">${esc(a.level)}</span>${esc(a.text)}</li>`
    ).join("") + (d.checks || []).map((c) =>
      `<li class="check"><span class="tag"></span>${esc(c)}</li>`).join("");

    const p = d.prices, y = d.ytd;
    /* THE DATE THE FIGURES STAND AT.
       Book.valued_at() is the newest mark — not today, because a figure is only as current as
       the price behind it. The SPREAD is on the Prices step, which is what makes this a date
       rather than an instant.

       NO BASIS PILL: the label names what each figure is, and the panel still hands over its
       basis, held to Book.HEADLINE by tests/test_figures.py. */
    /* THE BAND TAKES THE FIGURES THE PANEL LEADS WITH, each
       with the indented parts that follow it in the engine's order; the rest stay in the list
       below. Which figures lead is the panel's `lead`, never a choice made here. */
    const band = [], rest = [];
    let under = null;
    for (const f of d.figures) {
      if (f.indent && under) { under.parts.push(f); continue; }
      under = f.lead ? { ...f, parts: [] } : null;
      if (under) band.push(under); else rest.push(f);
    }
    const field = `<div class="field-figures">${band.map((f) => `
      <div class="field-figure"><span class="label">${esc(f.label)}</span>
        <span class="numeral">${fmt(f.value, f.kind)}</span>
        ${f.parts.map((x) => `<span class="part">${esc(x.label)} ${fmt(x.value, x.kind)}</span>`)
          .join("")}</div>`).join("")}</div>`;
    return page({
      scope: `where the book stands, as at ${day(d.valued_at)}`,
      field,
      status: [{ label: "Prices", body: `${quiet(`${p.age_days} days old · ${p.marks} marks
        · newest ${esc(day(p.newest))} · oldest ${esc(day(p.oldest))} · spread ${p.spread_days}d`)}
        ${panelLink("price-refresh", "run a refresh")}` },
        { label: "Year to date", body: quiet(`from ${esc(day(y.opens))}${y.frozen ? "" : " · not frozen"}`) },
        ...(d.report ? [{ label: "Report", body: `${reportLink(d.report)}
          ${panelLink("reports", "every report")}` }] : [])],
      /* THE FIGURES BESIDE WHAT NEEDS ATTENTION, so the page is one screen. */
      work: `<div class="glance">
        ${figures(rest.map((f) => [f.label, fmt(f.value, f.kind), f.indent ? "indent" : ""]))}
        <section><h2>Needs attention</h2><ul class="items">${items}</ul></section></div>`,
    });
  },
});

/* THE STEPS, EXPLAINED ONCE AND BELOW THE TABLE. `Reading` keeps its links on screen because
   those are the work; the reasons live here, Events' among them. */
const RECONCILE_WHY = [
  ["Events", "A missing trade makes the book's own figure wrong, and this check reports it as a "
             + "difference: a difference may be an event not yet entered. A sweep on the Bench "
             + "finds IG's; a dropped document, the rest."],
  ["Reading", "The contract levels and every IG account's equity are taken in one pass: the "
              + "book's figure comes from the marks and the broker's from the instant it is "
              + "asked, so struck apart the two differ by whatever the market did between."],
  ["Compare", "Every account is judged by the rule shown beside it. A share account's units "
              + "are counted when its reading is written; a spread-bet account gets a band, and "
              + "ties exactly when the reading is struck with the marks."],
];
const owes = (x, flags) => flags.some((f) => x[f]);
const TRIP_OWED = ["why_entered_owed", "why_exited_owed"];

/* A HOLDING'S DETAIL. Grouped by issuer, a row is every instrument the company is held through,
   and each carries its own thesis, so each is named; the mark history is a ticker row's. */
const holdingDetail = (r, d) => {
  const each = (r.reasons || []).map((x) => [x, detailList(x, d.detail)]).filter(([, h]) => h);
  return each.map(([x, h]) =>
    (r.reasons.length > 1 ? `<p><strong>${esc(x.ticker)}</strong></p>` : "") + h).join("")
    + detailList(r, ["marks"].filter((c) => d.detail.includes(c)), d.mark_columns);
};

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
    work: table(d.rows, d.columns, "<th></th>",
                (r) => `<td class="nowrap"><button class="link" data-trades="${esc(r.company)}">trades</button>${
                  detailLink(detailList(r, d.detail))}</td>`,
                { name: "company lives", afterRow: (r, span) => detailRow(detailList(r, d.detail), span),
                  cells: {
                    opened: (r) => `<td class="nowrap">${esc(day(r.opened))}${r.pre_baseline
                      ? ` <span class="tag">before the record</span>` : ""}</td>`,
                    qty: (r) => `<td class="num">${r.qty == null ? "—"
                      : r.qty.toLocaleString("en-GB")}</td>`,
                    currency: (r) => r.currency == null ? `<td>—</td>` : cell("currency", r.currency) } }),
  });
}

/* WHERE THE EXPOSURE SITS, under Holdings' table: the report's split by currency, region and
   sector, in its words, one bar per slice, largest first. The bar is drawn on a 0–1 scale, so
   its length IS the engine's share_of_largest: nothing here divides, and no width is set
   inline (app.css draws it). It follows the account filter as the table does. */
const allocation = (d) => !d.allocation ? "" : `<h2>Where the exposure sits</h2>
  <div class="allocs">${Object.entries(d.allocation).map(([axis, slices]) => `
    <table class="alloc"><thead><tr><th>${esc(sentence(d.allocation_heads[axis]))}</th><th></th>
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
            share AND a spread bet, and a link that showed one leg would answer half the question while
            looking complete. */ ""}
      ${table(d.rows, d.columns, "<th></th>",
              (r) => `<td class="nowrap">` +
                (r.company ? `<button class="link" data-trades="${esc(r.company)}">trades</button>`
                           : "") +
                detailLink(holdingDetail(r, d)) +
                ((r.reasons || []).some((x) => x.why_entered_owed) ? ` <span class="tag gap">owed</span>` : "") +
                `</td>`,
              {name: "holdings", afterRow: (r, span) => detailRow(holdingDetail(r, d), span),
               inserts: [{after: "held_as", head: `<th class="num">${head("qty")}</th>`,
                          cell: heldCell}]})}
      ${allocation(d)}`,
    });
  },

  "round-trips"(d) {
    if (d.view === "life") return companyLives(d);
    /* THE FIGURES ARE THE SELECTION'S. When a filter is on, the whole book sits beside them as
       context rather than as the answer. */
    const t = d.totals, w = d.whole;
    return page({
      scope: "every closed position, gain net of dealing commission",
      status: d.narrowed ? [{ state: "note", tag: "selected", label: "Whole book",
        body: quiet(`${w.realisations} realisation(s) · proceeds ${money(w.proceeds)}
          · realised gain ${money(w.realised)}`) }] : null,
      figures: [["Realisations", t.realisations],
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
        viewField(d),
      ] },
      /* THE SAME "trades" LINK AS HOLDINGS', by company: the sales a round trip took, and the
         buys before them, are Trades' to show. Then the row's detail: its whys, research notes
         and note. */
      work: table(d.rows, d.columns, "<th></th>",
                  (r) => `<td class="nowrap">${r.company
                    ? `<button class="link" data-trades="${esc(r.company)}">trades</button>` : ""}${
                    detailLink(detailList(r, d.detail))}${owes(r, TRIP_OWED)
                    ? ` <span class="tag gap">owed</span>` : ""}</td>`,
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

  /* METHOD — how the numbers are made, then the line and the door, as the engine's record states
     them. Read down as prose, so a definition list rather than a table. */
  method(d) {
    return page({
      scope: "how the numbers are made, and how a row gets in",
      work: d.sections.map((s) => `<h2>${esc(s.heading)}</h2><dl class="method">${s.rows.map((r) =>
        `<dt>${esc(r.topic)}</dt><dd>${esc(r.text)}</dd>`).join("")}</dl>`).join(""),
    });
  },

  /* ACCOUNTS — the register, the money that crossed each account's boundary, and the year's
     income and costs. The engine's tables, drawn as they come.

     THE YEAR'S INCOME IS ONE LINE PER ACCOUNT, the book first, each category a sum of money;
     an account's own rows open beneath its line, as a quarter's detail does on Performance. */
  accounts(d) {
    const asMoney = Object.fromEntries([...d.categories, "total"].map((c) =>
      [c, (r) => cell("amount", r[c])]));
    /* A FOREIGN ROW'S CONVERSION, and nothing on a sterling one: the amount at its currency's
       places, as a local price is printed. */
    const paid = (draw) => (r) => r.currency ? draw(r) : "<td></td>";
    const conversion = { currency: paid((r) => cell("currency", r.currency)),
                         local_amount: paid((r) => `<td class="num">${localPrice(r.local_amount, r.currency)}</td>`),
                         rate_date: paid((r) => cell("rate_date", r.rate_date)) };
    return page({
      scope: "who each account is, and the money that crossed its boundary",
      work: `<h2>Register</h2>${table(d.register, d.columns.register, "", () => "",
          { name: "register", cells: { feed_key: (r) => cell("feed_key", r.feed_key || "") } })}
        <h2>External capital</h2>${table(d.movements, d.columns.movements, "", () => "", { name: "capital" })}
        <h2>Income and costs, ${esc(d.year)}</h2>${table(d.income, d.columns.summary, "<th></th>",
          (r) => `<td class="nowrap">${detailLink(r.rows.length ? "rows" : "")}</td>`,
          { sort: false, cells: asMoney,
            afterRow: (r, span) => detailRow(r.rows.length
              ? table(r.rows, r.columns, "", () => "", { name: r.account, cells: conversion }) : "", span) })}`,
    });
  },

  /* REPORTS — every quarter the record closes, and each year, grouped by year. A quarter whose
     report the gate allows opens it; one it refuses shows the gate's own words beneath it. The
     state's word is the tag; whether a quarter is ready is the engine's answer, never decided
     here.

     A QUARTER STILL OPEN SHOWS ITS TAG ALONE: before its end the gate can only say its NAV rows
     are not frozen yet, which "open" already says. What stops a report shows from the day the
     quarter ends.

     NO DATE BESIDE A NAME: "Q3 2026" and "2026 year end" say the period, as Performance's
     Quarter does. */
  reports(d) {
    const state = (q) => !q.closed ? ["note", q.ended ? "to close" : "open"]
                       : q.gaps.length ? ["gap", "not ready"] : ["ok", "ready"];
    const row = (q) => {
      const [tone, word] = state(q);
      return `<li class="report"><span class="tag ${tone}">${word}</span>
        <strong>${q.closed && !q.gaps.length ? reportLink(q) : esc(q.quarter)}</strong>
        ${q.reported ? "" : `<span class="muted">for the record</span>`}
        ${q.ended && q.gaps.length
          ? `<ul class="gaps">${q.gaps.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>` : ""}</li>`;
    };
    return page({
      scope: "every quarter the record closes, and each year",
      work: d.years.map((y) => `
        <h2>${esc(y.year)}</h2>
        <ul class="items">
          <li class="report"><span class="tag note">${y.built ? "ready" : "not built"}</span>
            <strong>${esc(y.year)} year end</strong></li>
          ${d.quarters.filter((q) => q.quarter_end.startsWith(y.year)).map(row).join("")}
        </ul>`).join(""),
    });
  },

  performance(d) {
    const quarters = [...d.firm, ...d.accounts];
    const opens = new Set(quarters.filter((r, n) => !n || r.account !== quarters[n - 1].account));
    /* NO BENCHMARK: an index return is TIME-WEIGHTED and this book's MONEY-WEIGHTED, and the two
       do not subtract. */
    return page({
      scope: `every return on ${d.measure}, modified Dietz (day-weighted)`,
      status: d.reports.length ? [{ label: "Reports",
        body: d.reports.map(reportLink).join(" · ") }] : null,
      /* THE BOOK AND EACH ACCOUNT IN ONE TABLE, under one set of heads:
         the same columns named alike, so a figure is read down its column from the book to
         any account. THE ACCOUNT IS A COLUMN, named on its first row and blank on the rest,
         with a rule where the next one starts. */
      /* ONE GRID FOR THE TWO TABLES: the year's table takes the Quarter
         column's place with "Year to date", so its opening NAV, capital deployed, income,
         closing value, gain and return each sit under the quarter table's, in the same widths;
         its year-only columns follow. */
      work: table(quarters, d.columns, "<th></th>",
                  (r) => `<td class="nowrap">${detailLink(detailList(r, d.detail))}</td>`,
                  { sort: false, align: "performance",
                    cells: { account: (r) => `<td>${opens.has(r) ? esc(r.account) : ""}</td>` },
                    rowClass: (r) => opens.has(r) && r !== quarters[0] ? "opens" : "",
                    afterRow: (r, span) => detailRow(detailList(r, d.detail), span) }) +
        `<h2>The year so far, from ${esc(day(d.year_opens))}</h2>` + table(d.year, d.year_columns,
          "", () => "", { sort: false, align: "performance",
            inserts: [{ after: "account", head: "<th></th>", cell: () => "<td>Year to date</td>" }] }),
      why: d.caveats.map((c) => [c.scope, c.detail]),
    });
  },
});

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
      work: `<div id="q-rows">${d.rows.length ? table(d.rows, d.columns, "<th></th>",
        (r) => `<td class="nowrap">${detailLink(detailList(r, d.detail))}</td>`,
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

  /* RECONCILE — what the book says beside what the broker says.
     Two checks, and they are not the same check: a share account agrees on units, checked at the
     door; an IG account's equity is read in one pass with its marks and held to a band. Neither
     is decided here — the verdict arrives already made, from the same function the audit and
     the Dashboard ask. */
  reconcile(d) {
    /* EVERY VERDICT HAS A TAG. One that fell through to the default `note` would wear the colour
       of a row inside its band, for a row that has not been judged at all. */
    const verdictTag = { "units-agree": "ok", "within-band": "note", differs: "problem",
                         "no-statement": "gap", "no-holdings": "gap", "struck-apart": "gap" };
    /* THE TAG READS IN WORDS: the engine's code is "units-agree", the reader's is "units agree". */
    const verdictWords = (v) => v.replace(/-/g, " ");
    /* AN IG READING'S FIVE FIGURES, under the broker's figure, in IG's own words: the reading
       keeps them once each, and a figure kept is a figure shown. */
    const fig = (v) => v == null ? "—" : money(v);
    const igFigures = (r) => r.funds == null ? "" : `<br><span class="muted small">funds ${fig(r.funds)}
        · running P/L ${fig(r.running_pl)} · deposit ${fig(r.deposit)} · available ${fig(r.available)}</span>`;
    const rows = d.rows.map((r) => `<tr class="${r.verdict}">
        <td>${esc(r.account)}<br><span class="muted small">${esc(r.rule)}</span></td>
        <td class="num">${money(r.book)}</td>
        <td class="num">${money(r.broker)}${igFigures(r)}</td>
        <td class="num">${r.difference === null ? "—" : money(r.difference)}</td>
        <td><span class="tag ${esc(verdictTag[r.verdict] || "note")}">${
          esc(verdictWords(r.verdict))}</span></td>
        <td>${esc(r.last_check)}</td>
        <td>${r.document ? esc(r.document) : "—"}</td>
      </tr>`).join("");

    /* REPORT ONLY WHAT DISAGREES: a reporting rule rather than a data one — the panel hands over
       every row, and the lead is what needs attention. A clean book leads with a clean line, not
       with silence. */
    const lead = d.disagreements.length
      ? `<ul class="items">${d.disagreements.map((r) =>
          `<li class="problem"><span class="tag">differs</span><strong>${esc(r.account)}</strong>
           book and broker differ by ${money(r.difference)} — past the
           ${r.band === null ? "penny" : money(r.band)} band.</li>`).join("")}</ul>`
      : `<ul class="items"><li class="clear"><span class="tag">clear</span>
         every account that can be checked, does.</li></ul>`;

    /* THE ENGINE'S OWN WORDS, ONCE. Each unjudged account's `rule` and its difference sit in
       its table row, where a reader already looks; the lead names the accounts and says once
       what a difference beside them is. */
    const gaps = d.gaps.length ? `<ul class="items"><li class="gap"><span class="tag">not
        judged</span><strong>${d.gaps.map((r) => esc(r.account)).join(" · ")}</strong> — the
        table says why.</li></ul>`
      : "";

    return page({
      scope: "the book against each broker, account by account",
      /* Where each reading is taken, so drawn only where those pages open: on the Mac. */
      status: PANELS.has("bench") ? [{ label: "Reading",
        body: `${quiet("IG equity")} ${panelLink("price-refresh", "Price Refresh")}
               ${quiet("· a holdings export")} ${panelLink("bench", "Bench")}` }] : null,
      work: `
        <h2>What disagrees</h2>${lead}${gaps}
        <h2>Every account</h2>
        <div class="scroll"><table><thead><tr><th>${head("account")}</th><th class="num">${head("book")}</th>
          <th class="num">${head("broker")}</th><th class="num">${head("difference")}</th>
          <th>${head("verdict")}</th><th>${head("last_check")}</th>
          <th>${head("document")}</th></tr></thead><tbody>${rows}</tbody></table></div>`,
      why: RECONCILE_WHY,
    });
  },
});

/* THE READING PAGES' FILTERS, through the one mechanism, wireFilters(). */
Object.assign(WIRE, {
  holdings(d, again) {
    wireFilters("holdings", d, again, { ids: ["h-by", "h-acct"], button: "h-clear",
      ask: (v) => `/api/holdings?by=${encodeURIComponent(v["h-by"])}`
        + `&account=${encodeURIComponent(v["h-acct"])}`,
      clear: () => "/api/holdings" });
  },

  "round-trips"(d, again) {
    const view = (v) => `/api/round-trips?view=${encodeURIComponent(v["rt-view"] || "holding")}`;
    /* A COMPANY CHOSEN STARTS ITS TICKER AFRESH, and the page comes back with that company's
       codes in the Ticker box. */
    wireFilters("round-trips", d, again, {
      ids: ["rt-view", "rt-acct", "rt-company", "rt-ticker", "rt-from", "rt-to"], button: "rt-clear",
      resets: { "rt-company": "rt-ticker" },
      ask: (v) => view(v) + `&ticker=${encodeURIComponent(v["rt-ticker"])}`
        + `&company=${encodeURIComponent(v["rt-company"])}`
        + `&account=${encodeURIComponent(v["rt-acct"])}`
        + `&start=${encodeURIComponent(v["rt-from"])}`
        + `&end=${encodeURIComponent(v["rt-to"])}`,
      clear: view });
  },

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
