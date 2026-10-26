/* ---------------------------------------------------------------------------------------
   The panels that read; none computes. Every figure below is rendered
   exactly as the engine handed it over — a percentage worked out here would be a second
   calculation of something engine.py already answers, one remove further out.

   THEY USE THE STYLE LAYER AND INVENT NOTHING. The house classes are `num` on a cell, `.items`
   for a list, `.muted` for prose: use the style layer, never set it at a call site.
   --------------------------------------------------------------------------------------- */

/* SENTENCE CASE for a heading, a column head and a label: the words as written, first letter
   up. */
const sentence = (t) => t ? t.charAt(0).toUpperCase() + t.slice(1) : t;

/* COLUMN HEADINGS ARE NOT WRITTEN HERE. Each panel arrives with `heads`, its columns in
   house/headings.py's words for its tab, and paintPanel() keeps them for the page — the one list
   the report reads too. A field the list has not named shows its own name, and
   tests/test_figures.py fails before it ships. */
let HEADS = {};
/* A HEAD MAY BREAK AFTER A SLASH: unbroken, a slashed head is one word, wider than its figures.
   The words stay the list's. */
const head = (c) => esc(sentence(HEADS[c] || c.replace(/_/g, " "))).replace(/\//g, "/<wbr>");

const MONEYCOL = ["cost", "value", "gain", "unrealised", "proceeds",
                  "opening_nav", "closing_nav", "capital_deployed", "return_income",
                  "change", "price_effect", "fx_effect", "transacted", "value_to",
                  "exposure", "nav", "capital_employed", "capital_growth",
                  "income", "amount", "cash", "realised", "dividends", "funding_interest",
                  "total", "life_gain"];
const PCTCOL = ["unrealised_pct", "realised_pct", "weight", "return", "price_move_pct", "ytd", "life_pct"];

/* MOVEMENT, WHICH IS NOT PROVENANCE — house/palette.py's own words, over the two constants these
   colours come from. The word matters: "direction" is already a COLUMN on Trades holding
   Buy · Sell · Adjustment, and one word for two things is what this project spends its time
   undoing.

   WHAT IS IN THIS LIST IS A JUDGEMENT, NOT A TYPE CHECK. Every one of these is a GAIN — a figure
   whose sign says whether the book is better or worse off. Plenty of other numeric columns are
   deliberately absent:

     difference   Reconcile. Book minus broker on a RECONCILIATION row. A gap is not a loss, and
                  red on an account that ties within its band would assert something untrue.
     weight       a share of exposure. Never negative, so a colour would only ever say "green".
     cost value capital_deployed return_income
                  money, but not a result.

   The Dashboard's headline gains stay plain on purpose. Colouring those needs a flag on
   Book.HEADLINE, because a renderer must not decide what a figure MEANS by reading its label.
   Colour's job here is scanning a column, and the Dashboard is a summary list rather than a
   table you scan. */
const MOVEMENTCOL = ["gain", "unrealised", "unrealised_pct", "realised_pct", "return",
                     "change", "price_effect", "fx_effect", "price_move_pct",
                     "realised", "life_gain", "life_pct"];

/* THE FOUR FOR What Changed, AND THE ONE HELD BACK. `change`, `price_effect`,
   `fx_effect` and `price_move_pct` are results: their sign says whether the book is better or
   worse off, which is the test above. `transacted` is NOT and must never join them — buying
   £5,000.00 of shares is not a gain and selling £2,500.00 of them is not a loss. It is the
   same exclusion as `difference` on Reconcile: a figure can be money, and negative, and still
   carry no judgement about how the book did. Colouring it would turn every purchase green and
   every sale red, which is the most confident way to be wrong about a column. */

/* Above zero, below zero, or neither. EXACTLY ZERO GETS NO COLOUR: a flat quarter is not a gain
   and must not read as one. */
const movement = (c, v) =>
  !MOVEMENTCOL.includes(c) || typeof v !== "number" || v === 0 ? ""
    : v > 0 ? " up" : " down";

/* Why it works that way, BELOW the work it describes: explanation above a table
   dilutes its data, and the desk is for managing the accounts.

   The steps keep their TAG, their LABEL and their STATE line — "13 days old · limit 21 days" —
   which is the work. The paragraph saying why the step exists comes here, closed.

   ONE MECHANISM, NOT TWO. A second fold with its own markup would drift from this one. */

const whyFold = (summary, pairs) => pairs.length ? `
  <details class="why-fold"><summary>${esc(summary)}</summary>
    <dl>${pairs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
  </details>` : "";

/* THE STEPS ON ONE LINE. Every step reads the same way, left to right: its state, its name, then
   what can be pressed. A step with no state yet shows no badge. `body` is markup. */
const stepLine = (steps) => `<ol class="steps">${steps.map((s) => `
  <li class="${s.state || "pending"}"${s.title ? ` title="${esc(s.title)}"` : ""}>${s.state
    ? `<span class="tag">${esc(s.tag || s.state)}</span>` : ""}<strong>${esc(s.label)}</strong>
    ${s.body || ""}</li>`).join("")}</ol>`;

/* A step's qualifier, and a link to another tab. One of each: the link is `data-panel`, which
   #main delegates, so a page that redraws keeps it working without wiring its own. */
const quiet = (text) => `<span class="muted small">${text}</span>`;
/* A page the server does not list — Bench and Price Refresh on the hosted desk — is left out:
   a pointer to a page the reader cannot open is an instruction they cannot follow. */
const panelLink = (panel, label) => !PANELS.has(panel) ? "" :
  `<button class="link" data-panel="${panel}">${esc(label)}</button>`;

/* ONE QUARTER'S REPORT, opened beside the desk: the report's page, rendered by
   the desk's /api/report route from the same frozen inputs. Three pages offer one, so the link is
   written once. */
const reportLink = (q) =>
  `<a href="/api/report/${esc(q.quarter_end)}" target="_blank" rel="noopener">${esc(q.quarter)}</a>`;

/* THE PAGE TEMPLATE. Every tab is drawn through this, so the bands come in one order everywhere
   and a change to a band is a change to every page that has it:

     1 TITLE    the tab's own name, and one short line of what the page's figures are
     2 STATUS   the step line: state, name, what can be pressed            `stepLine()`
     3 FIGURES  the headline strip                                          `figures()`
     4 FILTERS  one row of filters                                          `filters()`
     5 WORK     the tables and lists, the one band a page writes for itself
     6 WHY      every explanation, closed, at the foot                       `whyFold()`

   A band a page has nothing for is left out. NOTHING EXPLAINS ITSELF ABOVE THE WORK: a note box
   there pushes the table down. Every page fills the window; `data-wide` is what widens it. */
const page = ({ scope = "", field = null, status = null, figures: strip = null, filters: row = null,
                work = "", why = null }) => {
  const head = `<header class="page-head"><h1>${esc(PAGE_TITLE)}</h1>${scope
      ? `<span class="muted">${esc(scope)}</span>` : ""}</header>`;
  /* A FIELD CARRIES THE HEAD. The Dashboard's ultramarine band is the page's
     title band too, so its head sits inside it rather than above it. */
  return `
  <div class="page" data-wide>
    ${field ? `<section class="field">${head}${field}</section>` : head}
    ${status ? stepLine(status) : ""}
    ${strip ? figures(strip) : ""}
    ${row ? filters(row.fields, row.clear) : ""}
    ${work}
    ${why ? whyFold("How this page works", why) : ""}
  </div>`;
};

/* A LONG NOTE MUST NOT SET THE ROW HEIGHT. Round Trips carries the why, and some of those
   run to several sentences — rendered plain they would set the row's height. Clamped to one
   line with the whole text on hover and in the title.

   NOR MUST A LABEL. Every cell of a data row is one line (app.css); a company name and
   Holdings' list of accounts are read WHOLE. The table scrolls sideways instead. */
const ONELINE = ["closed", "realisation_id", "ticker", "account"];
/* A DATE IS READ WHOLE WHATEVER ITS COLUMN IS CALLED: an ISO date breaks at its hyphens. */
const ISODATE = ISOMOMENT;
const cell = (c, v) => {
  if (v == null) return `<td>—</td>`;
  const m = movement(c, v);
  if (MONEYCOL.includes(c)) return `<td class="num${m}">${money(v)}</td>`;
  if (PCTCOL.includes(c)) return `<td class="num${m}">${pct(v)}</td>`;
  if (typeof v === "number") return `<td class="num">${v.toLocaleString("en-GB")}</td>`;
  if (typeof v === "boolean") return `<td>${v ? "yes" : ""}</td>`;
  if (c === "note" || c === "detail") {
    return `<td class="clip" title="${esc(v)}">${esc(v)}</td>`;
  }
  if (ISODATE.test(v)) return `<td class="oneline">${esc(day(v))}</td>`;
  if (ONELINE.includes(c)) return `<td class="oneline">${esc(v)}</td>`;
  return `<td>${esc(v)}</td>`;
};

/* A HEADING MUST MEET ITS NUMBERS. cell() decides right-alignment per VALUE, so a heading over
   figures takes `th.num` too. Decided per COLUMN, not per cell, because a heading cannot be
   right for some of its rows. */
const isNumCol = (c, rows) => {
  if (MONEYCOL.includes(c) || PCTCOL.includes(c)) return true;
  const first = rows.find((r) => r[c] != null);
  return first ? typeof first[c] === "number" : false;
};

/* ONE FILTER ROW, THREE PANELS: the same form, order and layout across Holdings, Round
   Trips and Trades, in the grey filter boxes.

   The `.f` box, the bench's field: one idea of a labelled control.

   THE ORDER IS FIXED AND THE SAME EVERYWHERE, applying only the fields a panel has: account ·
   company · ticker · from · to, then the page's own control (direction on Trades, the group by
   on Holdings). Who, then what, then when, so a box shared by two pages sits in the same place
   on both: Account is the first box on every page, Company and Ticker the second and third, the
   dates the fourth and fifth. No filter reads "all" everywhere. */
const filterField = (label, control) =>
  `<label class="f"><span>${esc(sentence(label))}</span>${control}</label>`;

const filters = (fields, clearId) => `
  <div class="grid filters">${fields.filter(Boolean).join("")}</div>
  ${clearId ? `<p class="filter-clear"><button class="link" id="${clearId}">clear filters</button></p>` : ""}`;

/* THE FILTERS, WIRED ONE WAY. Each box re-asks the SERVER — the narrowing is the engine's, and
   re-filtering an already-fetched array in the browser would be a second answer to a question
   the engine answers. `ask(v)` is the route for the boxes' values, and its answer is drawn over
   the page's own data, its values as `chosen`; `clear(v)` is the route with none; `resets` names
   the box a change empties first.
   THE FILTERS HELD FOR THIS PAGE are asked for again on arrival — only then, and only when they
   differ from what was drawn, so the redraw that answers them cannot ask again. A VIEW MAY DRAW
   FEWER BOXES (Round Trips by company life has no account or ticker), so only the boxes on the
   page are read. */
function wireFilters(name, d, again, { ids, button, ask, clear, resets = {} }) {
  const boxes = ids.map((id) => $(`#${id}`)).filter(Boolean);
  const values = () => Object.fromEntries(ids.map((id) => [id, $(`#${id}`)?.value ?? ""]));
  const reload = async (path) => {
    const asked = ++ASKED;
    let q;
    try { q = await get(path); } catch (e) {
      if (asked === ASKED) drawFailure(e);
      return;
    }
    if (asked !== ASKED) return;
    const data = { ...d, ...q, chosen: HELD_FILTERS[name] || {} };
    $("#main").innerHTML = DRAW[name](data);
    WIRE[name](data, true);
  };
  const go = () => {
    HELD_FILTERS[name] = Object.fromEntries(boxes.map((el) => [el.id, el.value]));
    reload(ask(values()));
  };
  /* `change` and not `input`: a date input fires on every keystroke while a year is being
     typed, and each one would be a request for a range nobody meant. */
  boxes.forEach((el) => el.addEventListener("change", () => {
    const reset = resets[el.id] && $(`#${resets[el.id]}`);
    if (reset) reset.value = "";
    go();
  }));
  $(`#${button}`)?.addEventListener("click", () => {
    const v = values();
    delete HELD_FILTERS[name];
    reload(clear(v));
  });
  const held = HELD_FILTERS[name];
  if (again || !held || !boxes.length) return;
  if (boxes.every((el) => el.value === (held[el.id] ?? ""))) return;
  boxes.forEach((el) => { el.value = held[el.id] ?? ""; });
  go();
}

/* TWO THINGS A COLUMN OF FIGURES CANNOT DO ON ITS OWN, both in `opts` so the other call sites
   are untouched.

   `inserts` PUTS A HAND-BUILT COLUMN IN THE MIDDLE. `extraCell` only ever appends, so a
   column it renders lands after everything — including the row's controls. A column belongs
   where its meaning puts it, so `{after, head, cell}` names the column it follows.

   `afterRow` OPENS A FULL-WIDTH ROW UNDER EACH ROW, which is the only way a table can carry a
   detail pane: a note cannot live inside a <tr> and still span the columns. The colspan is
   DERIVED from what was actually rendered — declared columns, inserts, and however many <th>
   the caller's own header string added. A hardcoded number would go stale the first time a
   column joined, silently, leaving the last cell of every expansion outside the table.

   `cells` DRAWS A DECLARED COLUMN BY HAND, in its own place: Trades' Quantity and Traded price
   read a spread bet in its own terms, a stake per point at a level in points.

   `rowClass` NAMES A ROW'S STATE for the stylesheet: Performance rules off where the next
   account starts. */
/* EVERY TABLE SORTS BY ITS HEADINGS. A heading pressed sorts its column —
   figures largest first, words and dates A to Z first — pressed again reverses it, and a third
   press puts the page's own order back. A row's detail moves with it. The sort is held per page
   and table, as the filters are, so a filter redraw keeps it. It orders what the engine sent;
   nothing is worked out. A table whose order IS its layout opts out (`sort: false`): the tables
   that name the book first and then each account once (Performance's quarters and its year,
   Accounts' Income and costs), and a detail's mark history.

   A SORTING TABLE NAMES ITSELF (`name`), and its sort is held under the page and that name.
   Keyed by COLUMNS, two tables alike would share one sort. */
const SORTS = {};
const SORTED = new Map();
let SORTED_NEXT = 0;
const sortKey = (name) => `${PAGE_TITLE}|${name}`;
const byColumn = (rows, c, dir) => {
  const blank = (v) => v == null || v === "";
  const cmp = (a, b) => typeof a === "number" && typeof b === "number" ? a - b
    : String(a).localeCompare(String(b), "en-GB", { numeric: true, sensitivity: "base" });
  return rows.map((r, i) => i).sort((i, j) => {
    const a = rows[i][c], b = rows[j][c];
    if (blank(a) || blank(b)) return blank(a) - blank(b) || i - j;
    return (dir === "down" ? -cmp(a, b) : cmp(a, b)) || i - j;
  });
};
const sortOrder = (rows, key) => {
  const held = SORTS[key];
  return held ? byColumn(rows, held.col, held.dir) : rows.map((r, i) => i);
};

const table = (rows, cols, extraHead = "", extraCell = () => "", opts = {}) => {
  const { afterRow = null, inserts = [], cells = {}, rowClass = null, sort = true,
          align = null, name = null } = opts;
  /* A LOCAL PRICE'S FORMAT IS ITS ROW'S: it prints at its line's currency's places. */
  const local = new Set(PRECISION.local_price_fields || []);
  /* AN EMPTY FIGURE SITS WHERE ITS FIGURES DO: the dash in a column of figures is right-aligned
     under them, not at the column's left edge. */
  const num = Object.fromEntries(cols.map((c) => [c, isNumCol(c, rows)]));
  const draw = (c, v) => v == null && num[c] ? `<td class="num">—</td>` : cell(c, v);
  const at = (c) => inserts.filter((i) => i.after === c);
  const span = cols.length + inserts.length + (extraHead.match(/<th/g) || []).length;
  const key = sortKey(name);
  const id = sort ? SORTED_NEXT++ : null;
  if (sort) SORTED.set(id, { rows, key });
  const held = sort && SORTS[key];
  const th = (c) => {
    const klass = [num[c] ? "num" : "", sort ? "sortable" : ""].filter(Boolean).join(" ");
    const state = held && held.col === c ? held.dir : "";
    return `<th${klass ? ` class="${klass}"` : ""}${sort ? ` data-col="${esc(c)}" tabindex="0"
      aria-sort="${state === "up" ? "ascending" : state === "down" ? "descending" : "none"}"` : ""}>${
      head(c)}${state ? `<span class="arrow" aria-hidden="true">${state === "up" ? "▲" : "▼"}</span>` : ""}</th>`;
  };
  return `
  <div class="scroll"><table${sort ? ` data-sorts="${id}"` : ""}${align
    ? ` data-align="${esc(align)}" data-align-cols="${cols.length + inserts.length}"` : ""}>
    <thead><tr>${cols.map((c) => th(c) +
      at(c).map((i) => i.head).join("")).join("")}${extraHead}</tr></thead>
    <tbody>${(sort ? sortOrder(rows, key) : rows.map((r, i) => i)).map((n) => [rows[n], n]).map(([r, n]) =>
      `<tr${sort ? ` data-i="${n}"` : ""}${rowClass && rowClass(r) ? ` class="${rowClass(r)}"` : ""}>${cols.map((c) => (cells[c] ? cells[c](r)
                               : local.has(c) ? (r.stake != null ? pointsCell(r[c])
                                                 : `<td class="num">${localPrice(r[c], r.currency)}</td>`)
                               : draw(c, r[c])) + at(c).map((i) => i.cell(r)).join("")).join("")}` +
      `${extraCell(r)}</tr>` + (afterRow ? afterRow(r, span) : "")).join("")}</tbody>
  </table></div>`;
};

/* THE HEADLINE STRIP, the template's third band: a label, its figure, and optionally `lead` or
   `indent`, which is how the Dashboard sets a total above its parts. The label says what each
   figure is. */
const figures = (rows) => `<table class="figures"><tbody>${rows.map(([label, value, kind]) =>
  `<tr${kind === "lead" ? ` class="lead"` : ""}>` +
  `<td${kind === "indent" ? ` class="indent"` : ""}>${esc(label)}</td>` +
  `<td class="num">${value}</td></tr>`).join("")}</tbody></table>`;

/* HOW MUCH IS HELD. A share line is its count; a spread bet is its stake per point, the way
   Trades reads one; a company row is its shares, bets counted as share-equivalents. */
const heldCell = (r) => r.stake != null
  ? `<td class="num">£${r.stake}/pt</td>`
  : r.qty != null ? `<td class="num">${r.qty.toLocaleString("en-GB")}</td>` : `<td class="num">—</td>`;

/* A LEVEL IN POINTS, as IG states it: a bet's entry, traded, exit or current level. A row that
   carries a stake per point is a bet, and every price on it is a level, not a local price. */
const points = (v) => v == null ? "—"
  : Number(v).toLocaleString("en-GB", { maximumFractionDigits: 2 }) + " pts";
const pointsCell = (v) => `<td class="num">${points(v)}</td>`;

/* THE DETAIL UNDER A ROW: ONE LINK ACROSS THE DESK, AND ONE ORDER INSIDE IT.
   Every table's row opens the same way, by "detail", to whatever the record holds on it, each
   part under its own heading from house/headings.py and ALWAYS IN THIS ORDER: the judgement,
   then what happened, then where it came from and what it belongs to, then the marks, which are
   a table. A page names the parts it draws (its panel's DETAIL_COLUMNS, sent as `detail`); a
   heading with nothing logged under it is left out. */
const DETAIL = ["why_entered", "why_exited", "research_notes", "note", "source", "quality",
                "broker_ref", "trade_id", "sale_id", "realisation_id", "contract", "funding",
                "fx_at_trade",
                "fx_from", "marks", "realisations", "lines"];

/* EACH WHY UNDER ITS HALF, oldest first, with the date of the trade it explains. An OWED half
   says so in words; a blank before the cut-off says nothing, because nothing is owed — the
   engine's flag decides which, never this. */
const whyPart = (half) => (x) => {
  const ws = (x.whys || []).filter((w) => w.half === half);
  return ws.length
    ? ws.map((w) => `<dt>${head(half)} <span class="muted small">${esc(day(w.date))}</span></dt>` +
                    `<dd>${esc(w.text)}</dd>`).join("")
    : x[`${half}_owed`] ? `<dt>${head(half)}</dt><dd><span class="tag gap">owed</span></dd>` : "";
};
const listPart = (c) => (x) => !(x[c] || []).length ? "" :
  `<dt>${head(c)}</dt><dd>${x[c].map(esc).join(" · ")}</dd>`;
const DETAIL_PART = {
  realisations: listPart("realisations"),
  lines: listPart("lines"),
  why_entered: whyPart("why_entered"),
  why_exited: whyPart("why_exited"),
  research_notes: (x) => !(x.research_notes || []).length ? "" :
    `<dt>${head("research_notes")}</dt><dd>${x.research_notes.map((n) =>
      `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.ref)}</a> ` +
      `<span class="muted small">${esc(day(n.date))}</span>`).join(" · ")}</dd>`,
  /* THE LINE'S LAST FIVE REFRESHES, newest first. A spread bet on two contracts shows both, at
     their own levels, and a line whose older marks were banked under its TICKER shows those
     too. */
  marks: (x, markCols) => !(x.marks || []).length ? "" :
    `<dt>${head("marks")}</dt><dd class="wide">${table(x.marks, markCols, "", () => "",
      { sort: false,
        /* A MARK PRINTS AS THE LINE'S OWN PRICE DOES: a bet's level in points, a share's
           price at its currency's places — not the raw number it was banked as. */
        cells: { price: (m) => m.level ? pointsCell(m.price)
                                       : `<td class="num">${localPrice(m.price, m.currency)}</td>` } })}</dd>`,
};
const detailList = (x, fields, markCols) => {
  const parts = DETAIL.filter((c) => fields.includes(c)).map((c) => DETAIL_PART[c]
    ? DETAIL_PART[c](x, markCols)
    : x[c] == null || x[c] === "" ? "" : `<dt>${head(c)}</dt><dd>${esc(x[c])}</dd>`).join("");
  return parts ? `<dl class="detail">${parts}</dl>` : "";
};
/* THE LINK AND THE ROW IT OPENS, both or neither: a row with nothing logged has no link. The
   detail is the NEXT TABLE ROW, because a pane cannot live inside a <tr> and still span it. */
const detailLink = (html) => !html ? "" :
  ` <button class="link detail-toggle" aria-expanded="false">detail</button>`;
const detailRow = (html, span) => !html ? "" :
  `<tr class="detail-row" hidden><td colspan="${span}">${html}</td></tr>`;

/* THE DETAIL LINK. Delegated from the document because a table is rebuilt on every filter
   change, and per-button listeners would be lost or doubled each time. A plain button and a
   hidden row rather than <details>, so the link can sit at the END OF THE ROW while the detail
   opens at full width underneath it — which <details> cannot do, its content being trapped
   inside the same box as its summary. The detail is the row's NEXT row (`detailRow()`). */
function wireDetailLinks() {
  if (document.body.dataset.detailWired) return;
  document.body.dataset.detailWired = "1";
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".detail-toggle");
    if (!b) return;
    const pane = (b.closest("tr") || {}).nextElementSibling;
    if (!pane || !pane.classList.contains("detail-row")) return;
    const open = pane.hidden;
    pane.hidden = !open;
    b.setAttribute("aria-expanded", String(open));
    /* The label says what the link DOES next. */
    b.textContent = open ? "hide" : "detail";
  });
}
