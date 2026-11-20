/* THE NEW SHELL, ON TRIAL (tools/trial_shell.py): a menu that stays, the Companies list and a
   company's page, in one plain script on the desk's own core.js and kit.js.

   IT FORMATS, IT DOES NOT CALCULATE, as the desk's script does not. Every figure is the
   engine's, asked from the API the desk already answers; a figure that API does not answer is
   left off the page, never worked out here.

   THE ADDRESS IS THE STATE. `#/companies?show=sold&find=tarn` and `#/company/<name>/<tab>` say
   everything a page shows, so a link, a reload and the browser's back land on the same screen.

   A PAGE IS DRAWN ONCE AND THEN MOVED WITHIN. Each page names the object it shows (`key`), reads
   it (`load`), draws its frame (`draw`) and fills the part of the frame the address picks
   (`update`). An address that names the same object calls `update` alone, so a tab or a filter
   changes one region and leaves the head, the reader's place and their typing where they were. */

/* THE ADDRESS, READ AND WRITTEN. `parts` are the path's steps and `asks` what follows the `?`.
   An address that will not decode names no page. */
const address = () => {
  const [path, asks = ""] = location.hash.replace(/^#\/?/, "").split("?");
  let parts;
  try { parts = path.split("/").filter(Boolean).map(decodeURIComponent); } catch (e) { parts = ["?"]; }
  return { parts, asks: new URLSearchParams(asks) };
};
const href = (parts, asks = {}) => {
  const q = new URLSearchParams(Object.entries(asks).filter(([, v]) => v)).toString();
  return `#/${parts.map(encodeURIComponent).join("/")}${q ? `?${q}` : ""}`;
};

/* A TABLE'S HEADINGS ARE ITS PANEL'S: house/headings.py words a column for the tab it is on, and
   each panel answer carries its own. A page made of three panels' tables draws each under the
   headings of the panel it came from. */
const KEPT = {};
const under = (panel, draw) => { HEADS = KEPT[panel].heads; return draw(); };
const plain = (rows, cols, opts = {}) => table(rows, cols, "", () => "", { sort: false, ...opts });

const card = (title, body, id = "") =>
  `<section class="card"${id ? ` id="${id}"` : ""}>${title ? `<h2>${title}</h2>` : ""}${body}</section>`;
const empty = (text) => `<p class="empty">${esc(text)}</p>`;
const signed = (c, v) => `<span class="figure${movement(c, v)}">${money(v)}</span>`;

/* ── The menu ─────────────────────────────────────────────────────────────────────────────── */

/* THE MENU, in the order agreed for the structure: the book's objects, the two places work is
   done, the lists, and the reference. An entry with a `page` is drawn in this shell; one with a
   `panel` is today's page, opened on today's desk, and is left out where the server lists no
   such panel. A list and the reference keep the name the server gives their tab; an object and
   a place of work take the structure's name for it. */
const MENU = [
  ["The book", [{ label: "Home", panel: "dashboard" }, { label: "Companies", page: "companies" },
                { label: "Accounts", panel: "accounts" }, { label: "Quarters", panel: "performance" }]],
  ["Work", [{ label: "Inbox", panel: "bench" }, { label: "Prices", panel: "price-refresh" }]],
  ["Lists", [{ panel: "trades" }, { panel: "round-trips" }, { panel: "what-changed" }]],
  ["Reference", [{ panel: "method" }]],
];

/* DRAWN ONCE. A page change moves `aria-current` and a late answer fills a note; a menu drawn
   again under the reader would take their focus with it. */
function drawMenu() {
  const entry = (m) => m.page
    ? `<a href="${href([m.page])}" data-page="${m.page}"><span>${esc(m.label)}</span>` +
      `<span class="note" data-note="${m.page}"></span></a>`
    : !PANELS.has(m.panel) ? ""
    : `<a href="/#${esc(m.panel)}" class="old"><span>${esc(m.label || PANELS.get(m.panel))}</span>` +
      `<span class="note" data-note="${esc(m.panel)}"></span>` +
      `<span class="out" title="Opens today's desk">↗</span></a>`;
  $("#menu").innerHTML = MENU.map(([group, entries]) =>
    `<div class="group"><h2>${esc(group)}</h2>${entries.map(entry).join("")}</div>`).join("") +
    `<p class="legend">↗ opens today's desk: a page this trial has not built.</p>`;
  const toggle = $("#menu-toggle");
  toggle.addEventListener("click", () =>
    toggle.setAttribute("aria-expanded", String($("#menu").classList.toggle("open"))));
}
function markMenu(page) {
  document.querySelectorAll("#menu a[data-page]").forEach((a) => {
    if (a.dataset.page === page) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  $("#menu").classList.remove("open");
  $("#menu-toggle").setAttribute("aria-expanded", "false");
}
const noteMenu = (name, text) => {
  const at = document.querySelector(`#menu [data-note="${name}"]`);
  if (at) at.textContent = text;
};

/* ── Companies ────────────────────────────────────────────────────────────────────────────── */

const SHOWS = [["held", "Held"], ["sold", "Sold"], ["all", "All"]];
const COMPANY_COLUMNS = ["company", "held_as", "accounts", "value", "unrealised", "life_gain", "weight"];

const companies = {
  menu: "companies",
  key: () => "companies",

  /* ONE ROW A COMPANY, held or sold. Holdings by company answers the held; Round Trips' company
     lives names every company and gives each life's gain; Trades names every code a company
     has traded under, a sold company's too. A company's life here is its open one, or its last.
     The rows come largest value first, the sold after the held. */
  async load() {
    const [held, lives] = await Promise.all([
      get("/api/holdings?by=issuer"), get("/api/round-trips?view=life")]);
    const of = new Map(held.rows.map((r) => [r.company, r]));
    const rows = lives.companies.map((company) => {
      const all = lives.rows.filter((r) => r.company === company);
      const life = all.find((r) => r.closed == null) || all[0] || {}, h = of.get(company) || {};
      return { company, held: of.has(company), state: life.state, closed: life.closed,
               tickers: KEPT.trades.data.company_tickers[company] || [],
               held_as: h.held_as ?? life.held_as, accounts: h.accounts ?? life.accounts,
               value: h.value ?? null, unrealised: h.unrealised ?? null,
               life_gain: life.life_gain ?? null, weight: h.weight ?? null };
    });
    return { rows: byColumn(rows, "value", "down").map((i) => rows[i]), valued_at: held.valued_at };
  },

  draw(d) {
    return `<header class="page-head">
        <div><h1 tabindex="-1">Companies</h1>
          <p class="sub">Every company the book holds or has held · valued at ${esc(day(d.valued_at))}</p></div>
        <label class="find"><span>Find a company or ticker</span>
          <input id="find" type="search" autocomplete="off" placeholder="Name or ticker"></label>
      </header>
      <nav class="chips" id="shows" aria-label="Which companies">${SHOWS.map(([s, label]) =>
        `<a data-show="${s}">${label} · <span></span></a>`).join("")}
        <span class="note" id="found" role="status"></span></nav>
      <section class="card" id="rows"></section>
      <p class="foot-note">A row is one company, however and wherever it is held. Its value is
        everything held in it: shares owned and spread-bet notional together.</p>`;
  },

  view(at) {
    const show = at.asks.get("show");
    return { show: SHOWS.some(([s]) => s === show) ? show : "held", find: at.asks.get("find") || "" };
  },
  at: (v) => href(["companies"], { show: v.show === "held" ? "" : v.show, find: v.find }),

  /* WHAT IS TYPED NARROWS THE LIST WHERE IT STANDS. The box is never drawn again, so it keeps
     the caret; the address follows each key, so back, a reload and a link carry the search, and
     an address arrived at puts its own search in the box (`update`). */
  wire(d) {
    $("#find").addEventListener("input", (e) => {
      const v = { ...this.view(address()), find: e.target.value };
      rewrite(this.at(v));
      this.paint(d, v);
    });
    /* THE ROW IS THE WAY IN: a press anywhere on it is a press on its company's link, which is
       the link a keyboard and a screen reader find. A press that selected text opens nothing. */
    $("#rows").addEventListener("click", (e) => {
      const row = e.target.closest("tbody tr");
      if (row && !e.target.closest("a") && !String(getSelection())) row.querySelector(".row-link")?.click();
    });
  },

  update(d, at) {
    const v = this.view(at), box = $("#find");
    if (at.parts.length > 1) rewrite(this.at(v));
    if (box.value !== v.find) box.value = v.find;
    this.paint(d, v);
  },

  /* THE THREE CHOICES ARE BUILT ONCE and a choice moves `aria-current`, as the menu's does. Each
     counts what the search leaves it, and carries the search to the choice it leads to. */
  paint(d, v) {
    const find = v.find.trim().toLowerCase();
    const found = d.rows.filter((r) => !find || r.company.toLowerCase().includes(find)
      || r.tickers.some((t) => t.toLowerCase().includes(find)));
    const within = (s) => found.filter((r) => s === "all" || (s === "held") === r.held);
    document.querySelectorAll("#shows a").forEach((a) => {
      const s = a.dataset.show;
      a.href = this.at({ show: s, find: v.find });
      a.querySelector("span").textContent = within(s).length;
      if (s === v.show) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current");
    });
    const rows = within(v.show);
    $("#found").textContent = `${rows.length} of ${d.rows.length} · largest value first`;
    $("#rows").innerHTML = !rows.length
      ? empty(find ? `No company ${v.show === "all" ? "" : `${v.show} `}matches “${v.find.trim()}”.`
                   : v.show === "all" ? "The book has held no company yet." : `No company is ${v.show}.`)
      : under("holdings", () => plain(rows, COMPANY_COLUMNS, { cells: {
          company: (r) => `<td><a class="row-link" href="${href(["company", r.company])}">${esc(r.company)}</a>` +
            `<span class="below">${esc(r.closed ? `${r.state} ${day(r.closed)}` : r.state || "")}</span></td>` } }));
    document.title = "Companies | PortFusion";
  },
};

/* ── A company's page ─────────────────────────────────────────────────────────────────────── */

/* A BET IN ITS OWN TERMS, as Trades and Round Trips read one: a stake per point, a level in
   points and no currency of its own. A share's price is in its line's currency. */
const BET_CELLS = {
  currency: (r) => r.stake == null ? cell("currency", r.currency) : `<td>—</td>`,
  qty: heldCell,
};
const priceCell = (price, level) => (r) => r.stake != null && r[level] != null
  ? pointsCell(r[level]) : `<td class="num">${localPrice(r[price], r.currency)}</td>`;
const heldText = (r) => r.stake != null ? `£${r.stake}/pt` : r.qty == null ? "" : r.qty.toLocaleString("en-GB");
const notHeld = () => empty("The desk answers this for a company still held, and this one is sold.");

/* EVERY WHY ON FILE FOR THE COMPANY, each once, and each half the engine says is owed, those
   first. A line carries the whys of the position now open and a round trip those of what was
   sold, so both are read: a why, and an owed half, may be on either. */
const reasons = (d) => {
  const all = new Map();
  [...(d.held ? d.held.reasons : []), ...d.trips.rows].forEach((x) => {
    (x.whys || []).forEach((w) =>
      all.set(`${w.date} ${w.half} ${x.ticker} ${w.text}`, { ...w, ticker: x.ticker }));
    ["why_entered", "why_exited"].filter((half) => x[`${half}_owed`]).forEach((half) =>
      all.set(`owed ${half} ${x.ticker}`, { half, ticker: x.ticker, owed: true }));
  });
  return [...all.values()].sort((a, b) => (b.owed || 0) - (a.owed || 0)
    || String(b.date).localeCompare(String(a.date)));
};

const LINE_COLUMNS = ["ticker", "held_as", "accounts", "currency", "entry_price", "price", "value",
                      "unrealised", "unrealised_pct"];

/* THE TABS, each a region of the one page: its name in the address, its label, what it counts
   and what it draws. */
const TABS = [
  { name: "overview", label: "Overview", draw: (d) =>
      card("Lines held", d.lines.length
        ? under("holdings", () => plain(d.lines, LINE_COLUMNS, {
            inserts: [{ after: "held_as", head: `<th class="num">${head("qty")}</th>`, cell: heldCell }] }))
        : empty(`Nothing is held: the last of it was sold on ${day(d.life.closed)}.`)) +
      (d.held ? card(under("holdings", () => head("life")),
                     under("holdings", () => plain(d.held.life, d.columns.life))) : "") },
  { name: "trades", label: "Trades", count: (d) => d.trades.total, draw: (d) =>
      card("Trades", d.trades.rows.length
        ? under("trades", () => plain(d.trades.rows, KEPT.trades.data.columns, { cells: {
            ...BET_CELLS, currency: (r) => r.level_points == null ? cell("currency", r.currency) : `<td>—</td>`,
            traded_price: priceCell("traded_price", "level_points") } }))
        : empty("No trade is on file for this company.")) },
  { name: "round-trips", label: "Round trips", count: (d) => d.trips.total, draw: (d) =>
      card("Round trips", d.trips.rows.length
        ? under("round-trips", () => plain(d.trips.rows, d.trips.columns.filter((c) => c !== "company"),
            { cells: { ...BET_CELLS, entry_price: priceCell("entry_price", "entry_level_points"),
                       exit_price: priceCell("exit_price", "exit_level_points") } }))
        : empty("Nothing has been sold: this company has no round trip yet.")) },
  { name: "income", label: "Income", count: (d) => d.held ? d.held.income.length : null, draw: (d) =>
      card("Income and costs", !d.held ? notHeld() : d.held.income.length
        ? under("holdings", () => plain(d.held.income, d.columns.income))
        : empty("No dividend, funding interest or fee names this company's lines.")) },
  { name: "price", label: "Price", draw: (d) =>
      card("Price history", !d.held ? notHeld() : !d.held.marks.length
        ? empty("No price is on file for this company's lines.")
        : under("holdings", () => plain(d.held.marks, d.columns.marks,
            { cells: { price: (m) => m.level ? pointsCell(m.price)
                                             : `<td class="num">${localPrice(m.price, m.currency)}</td>` } }))) },
  { name: "reasoning", label: "Reasoning", count: (d) => reasons(d).filter((w) => !w.owed).length, draw: (d) => {
      const all = reasons(d);
      return card("Reasoning", !all.length ? empty("No reasoning is written for this company.")
        : under("holdings", () => `<ul class="whys">${all.map((w) => `<li>
            <div><strong>${head(w.half)}</strong>
              <span class="below">${esc([w.date && day(w.date), w.ticker].filter(Boolean).join(" · "))}</span></div>
            <p>${w.owed ? `<span class="tag owed">owed</span>` : esc(w.text)}</p></li>`).join("")}</ul>`));
    } },
];

const company = {
  menu: "companies",
  key: (at) => `company/${at.parts[1] || ""}`,

  /* FIVE ASKS FOR ONE COMPANY: its row by company, its lines, its trades, its life and its round
     trips. Holdings answers every company and the page keeps this one's. */
  async load(at) {
    const name = at.parts[1] || "", q = encodeURIComponent(name);
    const [byCompany, lines, trades, lives, trips] = await Promise.all([
      get("/api/holdings?by=issuer"), get("/api/holdings"), get(`/api/trades?company=${q}`),
      get(`/api/round-trips?view=life&company=${q}`), get(`/api/round-trips?company=${q}`)]);
    return { name, known: lives.companies.includes(name),
             held: byCompany.rows.find((r) => r.company === name) || null,
             columns: { life: byCompany.life_columns, income: byCompany.income_columns,
                        marks: byCompany.mark_columns },
             lines: lines.rows.filter((r) => r.company === name),
             life: lives.rows.find((r) => r.closed == null) || lives.rows[0] || null,
             trades, trips };
  },

  /* THE FRAME EVERY OBJECT PAGE SHARES: the trail back to its list, the head with its one large
     figure, the tabs, the region a tab fills, and the status panel beside it. */
  draw(d) {
    if (!d.known || !d.life) {
      return `<nav class="trail" aria-label="Trail"><a href="${href(["companies"])}">Companies</a></nav>
        <h1 tabindex="-1">No company of that name</h1>
        ${empty(`This book has never held “${d.name}”.`)}`;
    }
    const h = d.held, life = d.life, facts = h || life;
    const large = h
      ? [money(h.value), `Value at ${day(h.priced_at)} · ${pct(h.weight)} of exposure`]
      : [money(life.realised), `Realised gain · sold ${day(life.closed)}`];
    const fact = (c, v) => `<div><dt>${head(c)}</dt><dd>${esc(v)}</dd></div>`;
    const small = (c, v, more = "") => `<div class="small-figure"><div class="label">${head(c)}</div>
      <div>${signed(c, v)}${more}</div></div>`;
    const owed = reasons(d).filter((w) => w.owed);
    return under("holdings", () => `
      <nav class="trail" aria-label="Trail"><a href="${href(["companies"])}">Companies</a>
        <span aria-hidden="true">/</span><span>${esc(d.name)}</span></nav>
      <section class="card object-head">
        <div><h1 tabindex="-1">${esc(d.name)}</h1>
          <dl class="facts">${fact("held_as", facts.held_as)}${fact("accounts", facts.accounts)}
            ${fact("opened", day(life.opened))}${fact("days_held", life.days_held)}</dl>
          <div class="large-figure">${large[0]}</div>
          <p class="sub">${esc(large[1])}</p></div>
        <div class="small-figures">${small("unrealised", life.unrealised)}${small("realised", life.realised)}
          ${small("life_gain", life.life_gain, life.life_pct == null ? "" : ` <span class="sub">${pct(life.life_pct)}</span>`)}</div>
      </section>
      <div class="object-body">
        <div class="object-main">
          <nav class="chips" id="tabs" aria-label="Sections">${TABS.map((t) => {
            const n = t.count ? t.count(d) : null;
            return `<a href="${href(["company", d.name, t.name])}" data-tab="${t.name}">${t.label}${
              n == null ? "" : ` · ${esc(n)}`}</a>`; }).join("")}</nav>
          <div id="tab"></div>
        </div>
        <aside class="status" aria-label="Status">
          ${card("What it needs", owed.length
            ? `<span class="tag owed">Reasoning owed</span><p class="sub">${owed.map((w) =>
                `${head(w.half)}, ${esc(w.ticker)}`).join(" · ")}</p>`
            : `<span class="tag">Nothing owed</span><p class="sub">${h
                ? `Priced at ${esc(day(h.priced_at))}.` : "Sold. No reasoning is owed."}</p>`)}
          ${card("Latest", d.trades.rows.length ? `<ul class="latest">${d.trades.rows.slice(0, 3).map((r) => `<li>
              ${esc(`${r.direction} ${heldText(r)} ${r.ticker}`)}
              <span class="below">${esc(`${day(r.date)} · ${r.account}`)}</span></li>`).join("")}</ul>`
            : empty("No trade is on file."))}
          ${card(head("accounts"), `<ul class="latest">${(h && h.life.length > 1 ? h.life.slice(1) : h && h.life.length ? h.life : [life]).map((a) =>
            `<li>${esc(a.accounts)}${a.life_gain == null ? "" : `<span class="below">${head("life_gain")} ${money(a.life_gain)}</span>`}</li>`).join("")}</ul>`)}
        </aside>
      </div>`);
  },

  /* A TAB FILLS ITS REGION AND NOTHING ELSE MOVES. The tab strip is not drawn again, so the tab
     pressed keeps the focus, and the page stays where the reader had scrolled it. */
  update(d, at) {
    if (!d.known || !d.life) { document.title = "No company of that name | PortFusion"; return; }
    /* A TAB THE PAGE DOES NOT HAVE is the first one, a step past the tab is no step, and the
       address is put right to say so. */
    const tab = TABS.find((t) => t.name === at.parts[2]) || TABS[0];
    if (at.parts.length > 3 || (at.parts[2] && at.parts[2] !== tab.name)) {
      rewrite(href(["company", d.name, tab.name]));
    }
    document.querySelectorAll("#tabs a").forEach((a) => {
      if (a.dataset.tab === tab.name) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
    $("#tab").innerHTML = tab.draw(d);
    document.title = `${d.name} · ${tab.label} | PortFusion`;
  },
};

/* ── The pages, and moving between them ───────────────────────────────────────────────────── */

const nowhere = {
  menu: null,
  key: () => `?${location.hash}`,
  load: async () => null,
  draw: () => `<h1 tabindex="-1">No page at this address</h1>
    <p><a href="${href(["companies"])}">Companies</a></p>`,
  update() { document.title = "No page at this address | PortFusion"; },
};
const PAGES = { companies, company };

/* THE PAGE ON SCREEN: its key, its page and what was read for it. */
let SHOWN = null;

/* WHERE EACH STEP OF HISTORY WAS SCROLLED TO. The shell stamps every step it draws with a name
   of its own, kept in the step's `history.state`, which the browser gives back on back, forward
   and a reload and gives no new step. So a step is known when it is met again, and three rules
   follow, and no other:

     a step met for the first time (a link, an address typed) opens its page at the top, with
       the reader at its heading; one within the page on screen (a tab, a choice) leaves the
       page where it is;
     a step met again is put back where it was left;
     a place is kept only for the step whose page is on screen (`DRAWN`), as it is scrolled and
       as it is left, so a scroll while the next page is still being read is nobody's.

   Every place goes with the tab as the document unloads, so a reload and the way back from
   today's desk find theirs. An address the shell rewrites keeps its step's stamp (`rewrite`),
   and a step the browser would not let it stamp has no place: it opens at the top. */
const PLACE = new Map();
const LEFT_AT = "trial-shell-places";
const STARTED = Date.now();
let STEPS = 0, DRAWN = null, AT = null;
const step = () => history.state?.step ?? null;
/* THE NEWEST PLACE IS LAST, so the cut at unload drops the steps longest unused. */
const keep = (name, y) => { PLACE.delete(name); PLACE.set(name, y); };
const keepPlace = () => { if (DRAWN != null && step() === DRAWN) keep(DRAWN, window.scrollY); };
const arrive = (name) => { DRAWN = name; if (name != null) keep(name, window.scrollY); };
const leave = () => { SHOWN = null; DRAWN = null; };
const stored = () => {
  try { return JSON.parse(sessionStorage.getItem(LEFT_AT) || "[]"); } catch (unreadable) { return []; }
};
/* A browser may refuse an address or a stamp written too often; the page is drawn all the same.
   `AT` is the address the page on screen was drawn for, so it follows a rewrite. */
const rewrite = (to, state = history.state) => {
  try { history.replaceState(state, "", to); } catch (refused) { /* the address stays */ }
  AT = location.hash;
};

async function go() {
  /* AN ADDRESS THAT NAMES NO STEP is the first page's, and is written so. */
  if (!address().parts.length) rewrite(href(["companies"]));
  const at = address(), page = Object.hasOwn(PAGES, at.parts[0]) ? PAGES[at.parts[0]] : nowhere;
  const key = page.key(at);
  /* THE STEP BEING LEFT keeps the place it has at this moment, and the step arrived at is
     stamped. MET AGAIN is a step the shell has drawn before, which is one it kept a place for. */
  if (DRAWN != null) keep(DRAWN, window.scrollY);
  AT = location.hash;
  if (step() == null) rewrite(location.href, { step: `${STARTED}.${++STEPS}` });
  const name = step(), again = name != null && PLACE.has(name);
  markMenu(page.menu);
  /* THE LATEST ASK IS THE ONE PAINTED, the desk's own rule (core.js, ASKED): a move within the
     page on screen also drops an answer still on its way for another. */
  const asked = ++ASKED;
  if (SHOWN && SHOWN.key === key) {
    SHOWN.page.update(SHOWN.data, at);
    if (again) window.scrollTo(0, PLACE.get(name));
    arrive(name);
    return;
  }
  const slow = setTimeout(() => {
    if (asked !== ASKED) return;
    leave();
    $("#main").innerHTML = `<p class="loading">reading the store…</p>`;
  }, 180);
  try {
    const data = await page.load(at);
    clearTimeout(slow);
    if (asked !== ASKED) return;
    $("#main").innerHTML = page.draw(data, at);
    SHOWN = { key, page, data };
    page.wire?.(data);
    page.update(data, at);
    window.scrollTo(0, again ? PLACE.get(name) : 0);
    if (!again) $("#main h1")?.focus({ preventScroll: true });
    arrive(name);
  } catch (e) {
    clearTimeout(slow);
    if (asked !== ASKED) return;
    leave();
    $("#main").innerHTML = `<h1>The record refused to load</h1><pre class="error">${esc(e.message)}</pre>`;
  }
}

(async function start() {
  try {
    /* THE HOUSE'S PLACES, WORDS AND HEADINGS arrive with a panel's answer, so three panels are
       asked before anything is drawn: the three whose tables these pages draw. */
    const [state, ...panels] = await Promise.all([get("/api/state"),
      ...["holdings", "trades", "round-trips"].map((n) => get(`/api/panel/${n}`))]);
    takeState(state);
    panels.forEach((p) => { KEPT[p.name] = p; });
    PRECISION = panels[0].precision;
    WORDS = panels[0].words;
    drawMenu();
    $("#book").textContent = `prices as at ${state.freshness.prices_as_at || "—"}`;
    noteMenu("trades", KEPT.trades.data.total);
    noteMenu("round-trips", KEPT["round-trips"].data.total);
    /* THE SLOW ANSWERS FILL THEIR NOTES WHEN THEY LAND, and the menu does not wait for them. */
    get("/api/round-trips?view=life").then((d) => noteMenu("companies", d.companies.length)).catch(() => {});
    get("/api/panel/dashboard").then((p) => {
      noteMenu("dashboard", `${p.data.attention.length} to do`);
      noteMenu("price-refresh", `${p.data.prices.age_days} days old`);
    }).catch(() => {});

    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    stored().forEach(([name, y]) => PLACE.set(name, y));
    /* WHAT ANOTHER DOCUMENT OF THE SHELL STORED STAYS: this one's places are added to it. */
    window.addEventListener("pagehide", () => {
      keepPlace();
      const all = new Map(stored());
      PLACE.forEach((y, name) => { all.delete(name); all.set(name, y); });
      try { sessionStorage.setItem(LEFT_AT, JSON.stringify([...all].slice(-200))); }
      catch (refused) { /* a browser that keeps nothing reloads at the top */ }
    });
    window.addEventListener("scroll", keepPlace, { passive: true });
    /* A STEP OF HISTORY TO THE SAME ADDRESS changes no hash, so it is met here. */
    window.addEventListener("hashchange", go);
    window.addEventListener("popstate", () => { if (location.hash === AT) go(); });
    /* A LINK TO THE ADDRESS ALREADY SHOWN moves no history, and is still an ask: it folds the
       menu and reads again a page that had refused to load. */
    document.addEventListener("click", (e) => {
      if (e.target.closest('a[href^="#/"]')?.hash === location.hash) go();
    });
    /* A DOCUMENT THE BROWSER KEPT AND BROUGHT BACK shows what was read before it was left, and
       the record may have moved on today's desk since: its page is read again. */
    window.addEventListener("pageshow", (e) => { if (e.persisted) { leave(); go(); } });
    await go();
  } catch (e) {
    $("#main").innerHTML = `<h1>The shell could not start</h1><pre class="error">${esc(e.message)}</pre>`;
  }
})();
