/* The shell. It draws whatever the server registers — it has no list of panels in it, because
   a list here would be a second place to update every time a panel is added.

   IT FORMATS, IT DOES NOT CALCULATE. Every number arrives from the engine already derived; the
   only thing this file decides is how many decimal places it wears. A percentage computed here
   would be a second calculation of something engine.py already answers. */

const $ = (s) => document.querySelector(s);

/* The sign goes OUTSIDE the currency symbol: -£5.82, never £-5.82. */
const money = (n) =>
  n === null || n === undefined ? "—"
  : (n < 0 ? "-" : "") + "£" +
    Math.abs(n).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/* EVERY PERCENTAGE AT THE HOUSE'S PLACES, house/precision.py's PCT_DP, which each panel answer
   carries beside its heads (paintPanel takes it). `portfusion record` and the report print the
   same places, so a figure reads the same on all three. */
let PRECISION = {};

/* A LOCAL PRICE, in its line's own currency (which the Ccy column names) at house/precision.py's
   places for it, carried in PRECISION with the fields that are one. Never money(): a £ on a
   dollar price is wrong twice. GBP is 4dp because LSE prices are quoted in pence and stored
   /100; the raw float printed 0.49887600000000004. */
const localPrice = (v, cur) => v == null ? "—"
  : Number(v).toFixed(PRECISION.local_price_dp[cur] ?? PRECISION.local_price_default);
const pct = (n) =>
  n === null || n === undefined ? "—"
  : (n * 100).toLocaleString("en-GB", { minimumFractionDigits: PRECISION.pct_dp,
                                        maximumFractionDigits: PRECISION.pct_dp }) + "%";

/* EVERY DATE A READER SEES, house/precision.py's day(): "14 Oct 2026", and a moment "14 Oct
   2026, 10:39". The months arrive with PRECISION. What is not an ISO date is left as it came,
   and a stored date stays ISO in the row, which is what a table sorts by. */
const ISOMOMENT = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/;
const day = (v) => {
  const m = v == null ? null : String(v).match(ISOMOMENT);
  if (!m || !PRECISION.months) return v == null ? "—" : String(v);
  return `${Number(m[3])} ${PRECISION.months[Number(m[2]) - 1]} ${m[1]}` + (m[4] ? `, ${m[4]}:${m[5]}` : "");
};

const fmt = (v, kind) => (kind === "pct" ? pct(v) : kind === "count" ? Number(v).toLocaleString("en-GB") : money(v));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function get(path) {
  const r = await fetch(path);
  const text = await r.text();
  let body;
  try { body = JSON.parse(text); } catch (e) { body = { error: r.statusText }; }
  if (!r.ok) {
    const e = new Error(body.detail || body.error || r.statusText);
    /* 401 IS THE HOSTED DESK ASKING WHO YOU ARE. The Mac's own door never sends it. */
    e.signIn = r.status === 401;
    /* A 502 or 504 that is not the desk's JSON is Netlify's proxy finding no Mac behind the
       tunnel. The desk's own refusals always come as JSON.
       SO IS A 500 WITH NOTHING IN IT (found 5 Oct 2026 with the Funnel turned off): Netlify
       answers that, not a 502, when there is no tunnel at all. The desk's own 500 always says
       "Internal Server Error", so a crash on the Mac is not mistaken for it. */
    e.unreachable = ([502, 504].includes(r.status) && !body.detail)
                    || (r.status === 500 && !text.trim());
    throw e;
  }
  return body;
}

/* A RESPONSE THAT IS NOT JSON MUST NOT BECOME A BROWSER MESSAGE.
   `await r.json()` on a 500 whose body is the plain string "Internal Server Error" throws, and
   Safari words that as "SyntaxError: The string did not match the expected pattern." — which
   says nothing about brokers, credentials or what to do. That is what the desk showed when it
   asked IG for live equity and feeds/ig.py died on an unrelated entry in credentials.json.
   The failure was real. The MESSAGE was the second bug, and it is the one that made the first
   one hard to find. */
async function readJson(r) {
  const text = await r.text();
  try {
    return { ok: r.ok, body: JSON.parse(text) };
  } catch (e) {
    return { ok: false, body: null,
             raw: `HTTP ${r.status} ${r.statusText}\n\n${text.trim() || "(empty response)"}` +
                  `\n\nThe server did not return JSON. Its log has the traceback:` +
                  `\n  ~/Library/Logs/portfusion-desk.log` };
  }
}

/* RESTART — the button for "it does not show".

   A running desk serves what it IMPORTED at startup, so a change to engine.py or a panel is
   invisible until the process is replaced and a browser refresh cannot fix it. The Dock icon
   replaces a stale server, but only one IT started; a desk run from a terminal never meets that
   check, and that is how it is run while being worked on.

   IT WAITS FOR THE NEW PROCESS RATHER THAN GUESSING. /api/health carries `started`, so the page
   polls until that value MOVES and only then reloads. Reloading on a timer would land on either
   the dying server or a refused connection, which looks like a crash. */
async function wireRestart() {
  const b = $("#restart");
  if (!b || b.dataset.wired) return;
  b.dataset.wired = "1";
  b.addEventListener("click", async () => {
    let was = null;
    try {
      was = (await (await fetch("/api/health")).json()).started;
    } catch (e) { /* if it cannot be asked now, the poll below still works on any answer */ }
    b.disabled = true;
    b.textContent = "restarting…";
    try {
      /* THE PAGE NAMES ITS OWN PORT. The action cannot default to 8765: a desk started on
         another port would then restart the one on 8765 instead — someone else's server. The
         browser is talking to exactly one server and knows which. */
      await fetch("/api/action/restart-desk", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ port: Number(location.port) || 8765 }) });
    } catch (e) { /* the server dies mid-reply by design — that is not a failure */ }

    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 250));
      try {
        const h = await (await fetch("/api/health", { cache: "no-store" })).json();
        if (h.started && h.started !== was) { location.reload(); return; }
      } catch (e) { /* still down, keep waiting */ }
    }
    b.textContent = "restart did not come back — see the terminal";
  });
}

function drawFreshness(f) {
  /* THE DESK'S OWN CODE, and it names what moved. A running server serves what it IMPORTED,
     while /static/* is read from disk per request — so a stale desk runs THIS file against an
     older engine and renders new markup over missing data. The restart button has always been
     on this line; until 7 Sep 2026 nothing said when to press it. */
  const source = !f.source_stale ? "" :
    ` · <span class="stale" title="${esc((f.source_files || []).join("\n"))}">` +
    `running older code — ${esc((f.source_files || []).join(", "))}` +
    `${f.source_count > (f.source_files || []).length
        ? ` +${f.source_count - f.source_files.length} more` : ""}` +
    ` changed since it started; restart it</span>`;
  /* THE PRICE DATE. Book.valued_at() is the newest mark, the same answer the Dashboard heads
     its glance with. The Price Refresh tab sits directly below this line, so a link to it
     here was a second way to the same tab (dropped 29 Sep 2026). */
  const prices = f.prices_as_at ? ` · prices as at ${esc(f.prices_as_at)}` : "";
  /* THE HOSTED DESK, as this Mac sees it (desk/publish.py:status()): its tunnel, and whether the
     version published is the one on disk. Drawn on the Mac only; the hosted page checks the
     version for itself before drawing anything. A STALE DESK CANNOT SAY THE HOSTED ONE IS BEHIND:
     its own version is worked out partly from the code it loaded, so it says restart first. */
  const h = f.hosted;
  const hosted = !h || REMOTE ? "" :
    !h.tunnel ? ` · <span class="stale">hosted: tunnel off</span>` :
    h.published !== h.current
      ? ` · <span class="stale">hosted: ${!h.published ? "not published"
          : f.source_stale ? "restart first" : "behind, publish"}</span>`
      : ` · hosted: live`;
  /* THE BUTTONS ARE THE SERVER'S TO OFFER. The remote door lists no actions, so a hosted page
     shows the line and neither button. */
  $("#fresh").innerHTML =
    `store changed ${esc(f.store_changed || "—")}${source}${prices}${hosted}` +
    (ACTIONS["restart-desk"] ? ` · <button class="link" id="restart">restart the desk</button>` : "") +
    (REMOTE ? ` · <button class="link" id="leave">sign out</button>` : "");
  wireRestart();
  $("#leave")?.addEventListener("click", async () => {
    await fetch("/auth/sign-out", { method: "POST" }).catch(() => null);
    location.reload();
  });
}

/* SWITCH TO A PANEL FROM ANYWHERE. The Holdings "trades" link already did this by finding the
   tab button and clicking it; the freshness line's "refresh" link is the second caller, so it
   becomes one function rather than two copies of a selector. Clicking the real tab rather than
   calling show() keeps the tab strip's own selected state correct — it is the tab that owns it. */
function openPanel(name) {
  const tab = [...document.querySelectorAll(".tabs button")].find((x) => x.dataset.name === name);
  if (tab) tab.click();
}

function drawTabs(panels, active, onPick) {
  const tab = (p) =>
    `<button role="tab" aria-selected="${p.name === active}" data-name="${esc(p.name)}">` +
    `${esc(p.title)}</button>`;
  /* THE PAGES APART FROM THE WORK sit below a rule, off the thread, with no heading: Method and
     Access on the Mac (`APART` on the panel module). The rule alone sets them apart; a heading
     over them read "The Mac only", which four pages on the thread also are (13 Oct 2026). */
  const apart = panels.filter((p) => p.apart);
  $("#tabs").innerHTML =
    `<div class="thread">${panels.filter((p) => !p.apart).map(tab).join("")}</div>` +
    (apart.length ? `<div class="apart">${apart.map(tab).join("")}</div>` : "");
  $("#tabs").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => onPick(b.dataset.name)));
  /* ON A PHONE THE RAIL FOLDS behind one button (app.css, `.pages-toggle`), which names the open
     page; choosing a page folds it again. The button is the shell's, so it is wired once. */
  const toggle = $("#pages-toggle");
  if (!toggle) return;
  toggle.textContent = (panels.find((p) => p.name === active) || {}).title || "Pages";
  toggle.setAttribute("aria-expanded", "false");
  $("#rail").classList.remove("open");
  if (toggle.dataset.wired) return;
  toggle.dataset.wired = "1";
  toggle.addEventListener("click", () => {
    toggle.setAttribute("aria-expanded", String($("#rail").classList.toggle("open")));
  });
}

/* Renderers, one per panel name. A panel the shell has no renderer for still LISTS — it shows
   its raw payload rather than vanishing, so a half-built panel is visible while it is built. */
let RENDER_LATE = {};

/* The open tab's own name, set as each panel is painted, so `page()` titles the page with the
   word the tab strip already uses rather than a second spelling of it. */
let PAGE_TITLE = "";

const RENDER = {
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

    /* THE SECOND CLOCK, added 7 Sep 2026 with store/journal.csv. Market time above, record
       time below, and each block says which — a mark banked at a month end and a dividend
       from the month before, entered days later, sit weeks apart on this page and answer different questions.

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

       NO BASIS PILL: a call-out box beside the figure added nothing. The label
       names what each figure is, and the panel still hands over its basis, held to
       Book.HEADLINE by tests/test_figures.py. */
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
      /* THE FIGURES BESIDE WHAT NEEDS ATTENTION: the list of figures took 360px
         of a 1,415px frame, the attention list ran on below it, and the page was taller than
         the window. Side by side, the page is one screen. */
      work: `<div class="glance">
        ${figures(rest.map((f) => [f.label, fmt(f.value, f.kind), f.indent ? "indent" : ""]))}
        <section><h2>Needs attention</h2><ul class="items">${items}</ul></section></div>`,
    });
  },
};

/* ---------------------------------------------------------------------------------------
   THE BENCH. An event, from evidence to an approved row.

   IT PROPOSES NOTHING. Every value here is typed or picked by the owner; the screen's job is to
   make the wrong value hard — closed vocabularies as dropdowns, a live word count against the
   cap, and the three statement-grade limbs as fields rather than a paragraph to remember.
   --------------------------------------------------------------------------------------- */
/* THE ACTION REGISTRY, held once. `desk/actions.py` is "the one place that says what this
   thing can do", and two screens ask it what an action writes and what it reaches. Cached
   rather than re-fetched because the answer is a property of the code, not of the store —
   and because `drawItem()` is synchronous and cannot await it. Primed by `loadActions()`
   before any screen that renders a badge. */
let ACTIONS = {};
/* And the pages, so a link to one the server does not list can say so rather than do nothing. */
let PANELS = new Set();
/* Whether this page is the hosted desk, which the remote door says of itself. */
let REMOTE = false;

function takeState(s) {
  ACTIONS = Object.fromEntries(s.actions.map((a) => [a.name, a]));
  PANELS = new Set(s.panels.map((p) => p.name));
  REMOTE = !!s.remote;
}

async function loadActions() {
  const s = await get("/api/state").catch(() => null);
  if (s && s.actions) takeState(s);
  return ACTIONS;
}

/* THE TWO AXES, WORN. `writes` says what may reach the record and `reaches` whether this
   leaves the machine; the registry answers both for every action and a screen that shows
   neither lets a button read as though it touched nothing. THE RAW VALUES, matching the
   registry's own words rather than a friendlier retelling. */
const badge = (kind, value) =>
  value ? ` <span class="muted small">${kind} ${esc(value)}</span>` : "";

const badges = (name) => {
  const a = ACTIONS[name] || {};
  return badge("writes", a.writes) + badge("reaches", a.reaches);
};

let BENCH = null;          // the panel payload: forms, limbs, documents
let OPEN_ID = null;        // which item is being worked
let DRAWN = 0;             // the revision of it on screen, sent with every save
let REVIEWING = false;     // the review before writing is on screen
let BENCH_GONE = null;     // an item opened from a list that was out of date: its title
/* Whether the document preview is open, remembered ACROSS a drawItem() rebuild. It used to be
   inferred from `#preview-pane` having content, which is true of the DOM and not of the
   intention: every re-render emptied the pane and so "forgot" that someone was reading. */
let PREVIEW_OPEN = false;
/* Set by a "trades" link (Holdings, Round Trips) and taken once by Trades, which then HOLDS the
   company as a filter chosen there (14 Oct 2026): the box shows it and "clear filters" sits
   beside it, so it narrows nothing out of sight. */
let PENDING_COMPANY = null;
/* THE RECEIPT FOR A REFRESH JUST WRITTEN, carried from the Price Refresh to What Changed and shown
   once. Same idiom and same reason as PENDING_COMPANY above: a completed write moves you to the
   panel that says what it did, and its own one-line summary would otherwise be lost on the way.
   What the destination cannot state for itself is the BANKING — how many outgoing marks went to
   their histories — so that is the half worth carrying. CONSUMED ONCE: a receipt that stuck
   would still be claiming a refresh a week later. */
let LAST_REFRESH = null;
/* The last sweep's events, by deal id. A button names a ref rather than carrying a whole row
   through the DOM — the same reason `collect()` rebuilds a bench row from named inputs. */
let IG_EVENTS = {};

/* THE SWEEP SURVIVES LEAVING THE TAB. It lived only in the DOM, so working
   ONE event and going back to its tab to carry on lost every other event the sweep had found —
   and the only way back was another 30-day call to the broker. Held here and re-rendered on
   return, which also repopulates IG_EVENTS, since the renderer fills it as it draws. */
let LAST_SWEEP = null;

/* A FETCHED PRICE SWEEP SURVIVES LEAVING THE TAB until it is written or
   discarded: it costs two vendors' calls, and a tab switch redrew the bay from the record. Held:
   the fetch's reply, the day it asked for, when it landed, and each row's tick and any figure
   typed into a line it left open — so the form comes back as it was left. */
let PRICE_SWEEP = null;

/* EACH PAGE'S FILTERS, kept while the desk is open: a switch redraws a
   panel from the record, and its filters fell back to their defaults with it. By panel, then
   by the control's id. */
const HELD_FILTERS = {};

/* LOCAL TIME, because it is read against a wall clock. The desk's other timestamps come from
   the server already formatted; this one is made in the browser at the moment an answer lands,
   and UTC would under-report the age of a reading by an hour for half the year. */
const stampNow = () => {
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  return day(`${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
             + `${p(d.getHours())}:${p(d.getMinutes())}`);
};
/* A FEED'S UTC INSTANT ON THE WALL CLOCK, local for the reason stampNow is. */
const clock = (at) => {
  const d = new Date(at), p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
};
/* What has happened to those events SINCE. Fetched every time the sweep is drawn, never cached
   with it: the sweep is a snapshot and this is the half that moves. */
let SWEEP_STATUS = {};

/* A FILE DROPPED ANYWHERE ELSE ON THE PAGE MUST DO NOTHING AT ALL. A browser's default for a
   dropped file is to NAVIGATE TO IT: the desk would be replaced by a PDF viewer, which looks
   like a crash and takes any half-typed bench form with it. Registered once, at the document,
   so it holds on every panel — the zone below re-preventDefaults on its own way up. */
["dragover", "drop"].forEach((e) =>
  document.addEventListener(e, (ev) => ev.preventDefault()));

/* THE DROP-OFF. Files go to /api/inbox one at a time, and the SERVER decides what may land —
   every rule about extensions, size, a leading dot and never overwriting lives in
   desk/intake/dropoff.py. Nothing is checked here that is not also checked there; this only reports.

   A REFUSAL IS SHOWN IN FULL, never swallowed. Those messages name the rule that stopped the
   drop, which is the half worth reading — "that filename starts with a dot, so nothing would
   ever list it" teaches where a silent failure would not. */
async function landFiles(files) {
  const landed = [], refused = [];
  for (const f of files) {
    try {
      /* `modified` is when the file was downloaded; it dates a document that states no date.
         SENT ONLY WHEN THE FILE HAS ONE: an empty `modified=` is no number, and the drop was
         refused for it (the review of 21 Oct 2026). */
      const r = await fetch(`/api/inbox?name=${encodeURIComponent(f.name)}` +
                            (f.lastModified ? `&modified=${f.lastModified}` : ""),
                            { method: "POST", body: f });
      const body = await r.json().catch(() => ({}));
      if (r.ok) landed.push(body.name);
      else refused.push(`${f.name} — ${body.detail || r.statusText}`);
    } catch (e) { refused.push(`${f.name} — ${e}`); }
  }

  /* The document list is the SERVER's — it reads _inbox/ rather than remembering what was
     sent — so the panel is re-asked rather than patched. */
  await show("bench");
  if (refused.length) {
    const out = $("#dropout");
    out.hidden = false;
    out.textContent = (landed.length ? `landed: ${landed.join(", ")}\n\n` : "")
      + `not accepted — nothing was written for these:\n`
      + refused.map((r) => `  ${r}`).join("\n");
  }

  /* ONE DOCUMENT OPENS ITS ITEM; SEVERAL JUST LAND. Dropping one file is a decision to work
     on it now, which is what "drop it on the bench" is expected to mean. Dropping three is a
     decision to file three, and a screen cannot open three items at once. */
  if (landed.length === 1 && !refused.length) {
    const it = await fetch("/api/bench", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin: "document", title: landed[0],
                             document: { name: landed[0] } }) }).then((r) => r.json());
    openItem(it.id);
  }
}

/* The zone itself. `dragenter`/`dragover` must both preventDefault or the drop never fires —
   the default action of a dragover is to REFUSE the drop. */
function wireDrop() {
  const zone = $("#drop");
  if (!zone) return;
  const lit = (on) => zone.classList.toggle("over", on);
  ["dragenter", "dragover"].forEach((e) => zone.addEventListener(e, (ev) => {
    ev.preventDefault(); lit(true);
  }));
  ["dragleave", "dragend"].forEach((e) => zone.addEventListener(e, () => lit(false)));
  zone.addEventListener("drop", (ev) => {
    ev.preventDefault(); lit(false);
    const files = [...(ev.dataTransfer?.files || [])];
    if (files.length) landFiles(files);
  });

  /* THE PICKER IS THE SAME ROUTE, not a second one. Drag-and-drop out of some applications is
     awkward or impossible — a mail attachment, a file behind a scroll — and a control that only
     accepts a drag would send that document back through Finder, which is the hop this removes. */
  const pick = $("#pick");
  pick.addEventListener("change", () => {
    const files = [...pick.files];
    pick.value = "";                 // so the same file can be chosen twice running
    if (files.length) landFiles(files);
  });
  $("#pickbtn").addEventListener("click", () => pick.click());
}

/* ONE SAVE AT A TIME. Every change saved at once, so two in flight raced: the second carried the
   revision the first was about to replace and came back 409, and each answer redrew the whole
   item under the owner's hands (the review of 21 Oct 2026). Each save now waits for the one
   before it, and so carries the revision that one drew. */
let SAVING = Promise.resolve();

function benchSave(patch) {
  const run = SAVING.then(() => saveNow(patch));
  SAVING = run.catch(() => {});
  return run;
}

/* WHAT THE OWNER IS TYPING SURVIVES A REDRAW. A field not yet left has fired no change, so its
   text was in no save, and the redraw a save ends with wiped it. It is put back, with the caret,
   in the field of the same name. */
function keepingTheField(draw) {
  const el = document.activeElement;
  const attr = el && $("#item") && $("#item").contains(el)
    && ["data-f", "data-limb", "data-why", "data-ratio"].find((a) => el.hasAttribute(a));
  if (!attr) return draw();
  const row = el.closest("[data-row]");
  const at = (row ? `[data-row="${row.dataset.row}"] ` : "") +
             `[${attr}="${CSS.escape(el.getAttribute(attr))}"]`;
  const value = el.value, start = el.selectionStart, end = el.selectionEnd;
  draw();
  const back = $("#item").querySelector(at);
  if (!back) return;
  back.value = value;
  back.focus();
  try { back.setSelectionRange(start, end); } catch (_) { /* a select has no caret */ }
}

async function saveNow(patch) {
  /* A SAVE SAYS WHICH REVISION IT WAS MADE FROM. The page sends the whole item, so one left open
     while a session handed in a reading wrote its old rows back over the reading (19 Oct 2026).
     The server refuses a save from an older revision; the item is drawn again as it now is, and
     the change is made again on that. */
  const r = await fetch(`/api/bench/${OPEN_ID}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...patch, revision: DRAWN }),
  });
  if (r.status === 409) {
    const d = await get(`/api/bench/${OPEN_ID}`);
    keepingTheField(() => drawItem(d));
    $("#item").insertAdjacentHTML("afterbegin",
      `<ul class="items"><li class="gap"><span class="tag">changed</span>drawn again; make the change again</li></ul>`);
    return d;
  }
  /* A SAVE REFUSED FOR ANY OTHER REASON SAYS SO. It read the refusal as the item and drew
     nothing, so the change looked made. */
  if (!r.ok) {
    const said = await r.json().catch(() => ({}));
    $("#item").insertAdjacentHTML("afterbegin",
      `<ul class="items"><li class="gap"><span class="tag">not saved</span>${esc(said.detail || r.statusText)}</li></ul>`);
    return null;
  }
  const d = await r.json();
  keepingTheField(() => drawItem(d));
  return d;
}

function field(spec, value, quote, drafted) {
  const v = value == null ? "" : String(value);
  const req = spec.required ? ` <span class="req">required</span>` : "";
  let input;
  if (spec.choices) {
    /* EVERY CHOICE FIELD IS SEARCHABLE, not only the ticker. The combobox first went only to the
       OPEN vocabularies — ticker and category — because those were the long ones. But `evidence`
       has ten entries and `acct` can hold names that differ only in their last word (an ISA
       against a SIPP at the same broker, say), and picking from a menu you cannot type into is the
       slow way to reach either.

       CLOSED STILL MEANS CLOSED. The difference is not whether you may type — it is whether
       what you typed is allowed to stand: a closed field that does not resolve to a listed
       value is CLEARED when you leave it, so the only value that can survive is one from the
       list. Typing is a way of finding the option, not a way past it. record/schema.py refuses a bad
       value on load either way; this stops it being entered in the first place. An OPEN field
       keeps whatever you type, because a first-ever purchase of a new company must not be
       refused by its own ticker being unknown.

       AND IT IS A REAL COMBOBOX, NOT A <datalist>. A datalist is the correct HTML and is not
       reliably a SEARCH: Safari does not filter one as you type the way Chrome does, so a few
       dozen tickers behaved as a long menu to scroll rather than something you type three letters
       into. This filters on every keystroke, in every browser. */
    input = `<div class="combo"><input data-f="${esc(spec.name)}" value="${esc(v)}"` +
      ` autocomplete="off" role="combobox" aria-expanded="false"` +
      (spec.closed ? ` data-closed="1"` : "") +
      ` data-choices="${esc(JSON.stringify(spec.choices))}">` +
      `<ul class="combo-list" hidden></ul></div>`;
    } else if (spec.long) {
    /* PROSE DOES NOT FIT ON ONE LINE. The drafted note runs to a sentence or three, and a
       one-line input made it something to scroll sideways rather than read — which is exactly
       backwards for the one cell the machine wrote and the owner has to check. */
    input = `<textarea data-f="${esc(spec.name)}" rows="3">${esc(v)}</textarea>`;
  } else {
    input = `<input data-f="${esc(spec.name)}" value="${esc(v)}"` +
      (spec.suggested && !v ? ` placeholder="${esc(spec.suggested)}"` : "") + `>`;
  }
  /* THE QUOTE IS THE WHOLE SAFETY MECHANISM, so it renders under the value rather than behind
     a hover. The owner is checking a quote against a document — a thing eyes are good at — and
     can only do that with the quote in front of them. A field with no quote is either the owner's
     or the record's, and says nothing. */
  /* A DRAFTED CELL IS A WEAKER CLAIM THAN A QUOTED ONE and is never dressed as one. The note
     is composed prose — a reading of the document rather than a piece of it — so it says so
     instead of showing a quote it does not have. */
  const q = drafted === "drafted"
    ? `<em class="quote drafted">drafted from the document — check it</em>`
    : drafted === "derived"
    ? `<em class="quote derived"${quote ? ` title="${esc(quote)}"` : ""}>from the record` +
      (quote ? ` — matched “${esc(quote)}”` : ", not the document") + `</em>`
    : quote ? `<em class="quote" title="${esc(quote)}">“${esc(quote)}”</em>` : "";
  return `<label class="f${spec.long ? " long" : ""}"><span>${head(spec.name)}${req}` +
    (spec.help ? `<em>${esc(spec.help)}</em>` : "") + `</span>${input}${q}</label>`;
}

/* A NEW CONTRACT'S FIRST MARK, read from IG when its set-up was pressed: written with the bet,
   so shown with it. */
function firstMarks(it) {
  return (it.marks || []).map((m) => `<div class="row-card"><div class="row-head">
      <strong>First mark</strong></div><dl class="detail">${["ticker", "price", "currency", "as_of",
      "source"].map((k) => `<dt>${head(k)}</dt><dd>${esc(m[k] ?? "")}</dd>`).join("")}</dl></div>`)
    .join("");
}

function drawItem(d) {
  const it = d.item;
  DRAWN = it.revision || 0;
  /* A KIND THIS MACHINE READS IS READ HERE, from its own cells: a download need not be sent
     anywhere to be read. Anything else — a contract note, usually — is read by a Claude
     session through `python3 -m portfusion.desk.intake.propose`, which fills this item and nothing else. */
  const local = (BENCH.reads_here || []).includes(it.evidence_class);
  const doc = it.document
    ? `<p><button class="link" id="preview">show the document</button>` +
      ` · <button class="link" id="readdoc">read ${esc(it.document.name)}</button></p>` +
      (local
        ? `<p><button class="link" id="readhere">read it again</button>
             <span class="muted small">on this machine — nothing leaves it</span></p>`
        : `<p><span class="muted small">a Claude session reads it: python3 -m portfusion.desk.intake.propose</span></p>`)
    : "";

  /* WHAT THE READING FOUND, AND WHAT IT REFUSED TO KEEP. The dropped list is the valuable half:
     a cell whose quote was not in the document never reached the form, and saying so is how
     anyone learns the check is real rather than decorative. */
  const prop = it.proposed;
  const seenList = (prop && prop.seen || []).map((s) => `<li class="${s.tag === "differs" ? "gap" : "clear"}"><span class="tag">${esc(s.tag || (s.in_record ? "on file" : "seen"))}</span>${esc(s.line)} <span class="muted">${esc(s.why)}</span></li>`).join("");
  const readout = !prop ? "" : prop.local ? `
    <h2>What the reading found</h2>
    <p class="muted">${esc(prop.kind + " · " + prop.at)}</p>
    ${seenList ? `<ul class="items">${seenList}</ul>` : ""}` : `
    <h2>What the reading found</h2>
    <p class="muted">${esc(prop.kind || "document")} · read ${esc(prop.at)} by ${esc(prop.by)}</p>
    ${prop.directives.length ? `<ul class="items"><li class="problem"><span class="tag">not acted
       on</span><strong>This document contains text addressed to the reader.</strong> A broker
       document is data, never instructions; what it said is quoted below.</li>` +
       prop.directives.map((d) => `<li class="problem"><span class="tag">directive</span>${esc(d)}</li>`).join("")
       + `</ul>` : ""}
    ${prop.dropped.length ? `<p class="muted">Not kept, because it could not be verified against the
       document:</p><ul class="items">` +
       prop.dropped.map((d) => `<li class="gap"><span class="tag">dropped</span>${esc(d)}</li>`).join("")
       + `</ul>` : ""}
    ${prop.not_found.length ? `<p class="muted">The document does not state:
       ${prop.not_found.map(esc).join(" · ")}</p>` : ""}`;

  /* A HOLDINGS EXPORT FILES THE ACCOUNT'S READING — these figures, read
     off it, written when it is filed. Its units are in the reading above. ii's states no cash,
     so its reading is the stock alone and Reconcile adds the account's cash (2 Oct 2026). */
  const rdg = it.reading;
  const num = (v) => v === "" || v == null ? "—" : money(Number(v));
  const readingBlock = !rdg ? "" : `
    <h2>The account's reading</h2>
    ${figures([["Account", esc(rdg.account || "—")], ["Stock", num(rdg.positions)]].concat(
      rdg.recon_cash === "" && rdg.stmt_value === "" ? []
        : [["Cash", num(rdg.recon_cash)], ["Total", num(rdg.stmt_value)]]))}
    ${rdg.note ? `<p class="muted">${esc(rdg.note)}</p>` : ""}`;

  /* WHAT KIND OF DOCUMENT THIS IS. ii gives contract notes and quarterly statements — official,
     referenced, reconciled — and a recent-transactions download, which is a snapshot between
     quarters carrying no reference NUMBER. All three limbs still apply to every class; what the
     class knows is the SHAPE of each, so the reference box says what would retrieve this one. */
  const klass = (BENCH.evidence_classes || []).find((c) => c.key === it.evidence_class);
  const classPicker =
    `<label class="f long"><span>What kind of document is this?</span>
       <select id="evclass"><option value="">— choose —</option>` +
    /* A CLOSED CLASS IS NOT OFFERED, but an item already citing one still shows it. */
    (BENCH.evidence_classes || []).filter((c) => !c.closed || c.key === it.evidence_class).map((c) =>
      `<option value="${esc(c.key)}"${c.key === it.evidence_class ? " selected" : ""}>` +
      `${esc(c.label)}${c.official ? "" : " — a snapshot, not the official document"}</option>`
    ).join("") + `</select></label>`;

  const limbs = BENCH.limbs.map((l) => {
    /* The class knows what THIS limb looks like for THIS kind of document, so the help text
       stops being generic the moment one is chosen. THE AUTHORITY IS THE KIND'S OWN WORDS,
       shown and never typed: the record keeps no typed one, and the server sets it on save. */
    const help = (klass && l.key === "reference") ? klass.reference_is : l.help;
    const fixed = l.key === "authority";
    const value = fixed ? (klass ? klass.authority : "") : (it.evidence[l.key] || "");
    return `<label class="f"><span>${esc(l.label)}${fixed ? "" : ` <span class="req">required</span>`}` +
      `<em>${esc(help)}</em></span>` +
      `<input data-limb="${esc(l.key)}" value="${esc(value)}"${fixed ? " readonly" : ""}></label>`;
  }).join("");

  const rows = (it.rows || []).map((r, i) => {
    const form = BENCH.forms[r.table] || [];
    /* A SPLIT OR CONSOLIDATION carries its ratio beside the trades form; the server derives the
       rest of the row from it and the holding (bench.adjustment_cells), on every save. */
    const ratio = r.adjustment ? `<div class="grid">${["from", "to"].map((k) =>
      `<label class="f"><span>${k === "from" ? "Shares before" : "Shares after"}
         <span class="req">required</span></span>
         <input data-ratio="${k}" inputmode="numeric" value="${esc(r.adjustment[k] ?? "")}"></label>`)
      .join("")}</div>` : "";
    return `<div class="row-card" data-row="${i}">
      <div class="row-head"><strong>${esc(r.adjustment ? BENCH.adjustment_label
        : (BENCH.table_labels || {})[r.table] || r.table)}</strong>${
        /* income.csv HOLDS BOTH, and its own schema doc says so: "COSTS ARE NEGATIVE, income
           positive". A -1.50 funding charge headed simply "income" reads as the opposite of
           what it is. The sign is the record's own rule, so the label follows it. */
        r.table === "income" && parseFloat(r.values.amount) < 0
          ? ` <span class="muted small">a cost — negative</span>` : ""}
        <button class="link danger" data-delrow="${i}">remove</button></div>
      ${ratio}
      <div class="grid">${form.map((s) =>
        field(s, r.values[s.name], (r.sources || {})[s.name],
              (r.drafted || []).includes(s.name) ? "drafted"
              : (r.derived || []).includes(s.name) ? "derived" : "")).join("")}</div>
    </div>`;
  }).join("");

  /* The two judgement fields, with whether each is owed taken from the GATES rather than
     worked out again here — the bench already decides that from the rows. */
  const said = it.why || { why_entered: it.reasoning || "", why_exited: "" };
  const WHYS = [
    { name: "why_entered", label: "Why we entered" },
    { name: "why_exited", label: "Why we exited" },
  ].map((w) => {
    const text = said[w.name] || "";
    const gate = d.gates.find((g) => g.name === w.name) || {};
    return { ...w, text, required: !!gate.required };
  });

  const gates = d.gates.map((g) =>
    `<li class="${g.ok ? "ok" : "no"}"><span class="tag">${g.ok ? "ok" : "blocked"}</span>` +
    `<strong>${esc(g.label || g.name)}</strong> ${esc(g.detail)}` +
    /* A DUPLICATE IS ACKNOWLEDGED, NOT OVERRIDDEN SILENTLY. Two identical legs closed on one
       day are legitimate and can occur, so this cannot be a refusal — but it must
       cost a deliberate click that says "yes, I know, and it is still a separate event". */
    (!g.ok && (g.findings || []).length
      ? ` <button class="link danger" data-ack="${esc(g.name)}">` +
        `${esc(g.ack || "I know — this is a separate event")}</button>` : "") +
    `</li>`).join("");

  $("#item").innerHTML = `
    <div class="row-head"><button class="link" id="back">back to the Bench</button></div>
    <div class="row-head"><h2>${esc(it.title)}</h2>
      ${it.document && it.document.name
        ? `<button class="link danger" id="withdraw">withdraw document</button>` : ""}
      <button class="link danger" id="discard">discard item</button></div>
    ${doc}
    <div id="preview-pane"></div>
    <div id="docbody"></div>
    ${readout}
    ${readingBlock}
    <h2>Evidence — statement-grade</h2>
    <div class="grid">${classPicker}</div>
    <div class="grid">${limbs}</div>
    <h2>Proposed rows</h2>
    <div id="rows">${rows || `<p class="muted">nothing proposed yet</p>`}${firstMarks(it)}</div>
    <p>${BENCH.tables.map((t) =>
        `<button class="link" data-addrow="${esc(t)}">+ ${esc(
          ((BENCH.table_labels || {})[t] || t).toLowerCase())}</button>`).join(" ")}
      <button class="link" data-addadjustment>+ ${esc(BENCH.adjustment_label.toLowerCase())}</button></p>
    <h2>Reasoning</h2>
    ${WHYS.map((w) => `
      <label class="f"><span>${esc(w.label)}${w.required ? ` <span class="req">required</span>` : ""}</span>
        <textarea data-why="${esc(w.name)}" rows="3">${esc(w.text)}</textarea></label>` +
      /* WHAT THE RECORD ALREADY SAYS. A new why is added beside these and replaces none, so they
         are shown as the record so far: the thesis an addition builds on, the reason a trim
         departs from. */
      Object.entries(d.existing_why || {}).map(([tk, rows]) => rows.filter((r) => r[w.name])
        .map((r) => `<ul class="items"><li><span class="tag">on file</span><strong>${esc(tk)}</strong>
             <span class="muted small">${esc(day(r.date))}</span><br><em>${esc(r[w.name])}</em></li></ul>`)
        .join("")).join("")
    ).join("")}
    <h2>Gates</h2><ul class="items gates">${gates}</ul>
    ${nextStep(d)}`;

  const collect = () => (it.rows || []).map((r, i) => {
    const values = Object.fromEntries([...$("#rows").querySelectorAll(`[data-row="${i}"] [data-f]`)]
      .map((el) => [el.dataset.f, el.value]));
    /* TWO THINGS THAT WOULD SILENTLY LOSE THE PROVENANCE, both handled here.
       First, this function rebuilds every row from the DOM, so a `sources` map left out would
       be dropped on the very next save — the quotes would survive exactly until the owner touched
       anything. Second, A QUOTE BELONGS TO THE VALUE IT WAS READ FOR. The moment the owner types in
       a field the provenance is theirs rather than the document's, so the quote goes instead of
       sitting under a number it no longer describes. */
    const untouched = (k) => values[k] === String(r.values[k] ?? "");
    const sources = Object.fromEntries(Object.entries(r.sources || {}).filter(([k]) => untouched(k)));
    const drafted = (r.drafted || []).filter(untouched);
    const derived = (r.derived || []).filter(untouched);
    const ratio = Object.fromEntries([...$("#rows").querySelectorAll(`[data-row="${i}"] [data-ratio]`)]
      .map((el) => [el.dataset.ratio, el.value]));
    /* A ROW THE OWNER HAS EDITED IS THEIRS. It kept `machine`, and a re-read replaces machine
       rows, so the correction went with the reading it corrected (the review of 21 Oct 2026). */
    const mine = Object.keys(values).some((k) => !untouched(k));
    return { table: r.table, values, sources, drafted, derived, machine: r.machine && !mine,
             ...(r.adjustment ? { adjustment: ratio } : {}) };
  });

  const ev = $("#evclass");
  if (ev) ev.addEventListener("change", () => {
    /* Picking a class fills the authority for you, but never overwrites something already
       typed — the class is a shortcut, not an owner of the field. */
    const chosen = (BENCH.evidence_classes || []).find((c) => c.key === ev.value);
    const authority = $('[data-limb="authority"]');
    const patch = { evidence_class: ev.value };
    if (chosen && authority && !authority.value.trim()) {
      patch.evidence = Object.fromEntries([...$("#item").querySelectorAll("[data-limb]")]
        .map((e2) => [e2.dataset.limb,
                      e2.dataset.limb === "authority" ? chosen.authority : e2.value]));
    }
    benchSave(patch);
  });

  $("#item").querySelectorAll("[data-limb]").forEach((el) =>
    el.addEventListener("change", () => benchSave({
      evidence: Object.fromEntries([...$("#item").querySelectorAll("[data-limb]")]
        .map((e2) => [e2.dataset.limb, e2.value])) })));
  $("#item").querySelectorAll("[data-f], [data-ratio]").forEach((el) =>
    el.addEventListener("change", () => benchSave({ rows: collect() })));
  $("#item").querySelectorAll("[data-why]").forEach((el) =>
    el.addEventListener("change", () => benchSave({
      why: Object.fromEntries([...$("#item").querySelectorAll("[data-why]")]
        .map((e2) => [e2.dataset.why, e2.value])) })));
  $("#item").querySelectorAll("[data-addrow]").forEach((b) =>
    b.addEventListener("click", () => benchSave({
      rows: [...collect(), { table: b.dataset.addrow, values: {} }] })));
  $("#item").querySelectorAll("[data-addadjustment]").forEach((b) =>
    b.addEventListener("click", () => benchSave({
      rows: [...collect(), { table: "trades", adjustment: { from: "", to: "" }, values: {} }] })));
  $("#item").querySelectorAll("[data-delrow]").forEach((b) =>
    b.addEventListener("click", () => benchSave({
      rows: collect().filter((_, i) => i !== +b.dataset.delrow) })));
  // Withdraw takes the document with it; discard leaves it on the workbench, which is what
  // that button has always done and what its API route promises. The two are side by side
  // because the choice between them is the choice the operator actually has.
  const wd = $("#withdraw");
  if (wd) wd.addEventListener("click", async () => {
    const why = prompt("Why is this not needed? Recorded on the archived item.");
    if (why === null) return;
    const name = encodeURIComponent(it.document.name);
    const r = await fetch(`/api/inbox/${name}?why=${encodeURIComponent(why)}`,
                          { method: "DELETE" });
    if (!r.ok) { alert((await r.json()).detail || "refused"); return; }
    OPEN_ID = null;
    await show("bench");
  });
  $("#discard").addEventListener("click", async () => {
    await fetch(`/api/bench/${OPEN_ID}`, { method: "DELETE" });
    OPEN_ID = null;
    await show("bench");
  });
  $("#item").querySelectorAll("[data-ack]").forEach((b) => b.addEventListener("click", () => {
    const g = d.gates.find((x) => x.name === b.dataset.ack);
    benchSave({ acknowledged: [...(it.acknowledged || []), ...(g ? g.findings : [])] });
  }));
  const rh = $("#readhere");
  if (rh) rh.addEventListener("click", async () => {
    rh.disabled = true;
    const r = await fetch(`/api/bench/${OPEN_ID}/read`, { method: "POST" });
    if (r.ok) drawItem(await r.json());
    else $("#docbody").innerHTML = `<pre class="error">${esc((await r.json()).detail || r.statusText)}</pre>`;
  });

  $("#back").addEventListener("click", () => { OPEN_ID = null; show("bench"); });
  const nx = $("#nextitem");
  if (nx) nx.addEventListener("click", () => openItem(nx.dataset.open));
  const ra = $("#reviewall");
  if (ra) ra.addEventListener("click", () => reviewItems());
  /* THE DOCUMENT BESIDE THE FORM. Sticky, because the whole job is cross-referencing a quote
     against the page it came from, and a preview that scrolls away during a long form is a
     preview you stop using. The item breaks out of the page measure while it is open. */
  /* THE DOCUMENT STAYS OPEN ACROSS A RE-RENDER.
     drawItem() rebuilds the whole item — after a read, after a save — and the template emits
     an EMPTY #preview-pane, so the document vanished while `body.wide` stayed on: a two-column
     layout with nothing in the right column, and the toggle back at "show the document". It
     read as the preview needing a second press to come back.
     A preview you have to reopen every time the form changes is one you stop using, which is
     the same reason it was made sticky in the first place. */
  const showDoc = (on) => {
    const pane = $("#preview-pane");
    if (!pane) return;
    pane.innerHTML = on
      ? `<iframe class="docframe" title="${esc(it.document.name)}"
           src="/api/document/${encodeURIComponent(it.document.name)}/raw"></iframe>`
      : "";
    document.body.classList.toggle("wide", on);
    const b = $("#preview");
    if (b) b.textContent = on ? "hide the document" : "show the document";
    PREVIEW_OPEN = on;
  };
  const pv = $("#preview");
  if (pv) pv.addEventListener("click", () => showDoc(!PREVIEW_OPEN));
  /* Restore it after the rebuild, before the eye has moved. */
  if (it.document && PREVIEW_OPEN) showDoc(true);

  const rd = $("#readdoc");
  if (rd) rd.addEventListener("click", async () => {
    const t2 = await get(`/api/document/${encodeURIComponent(it.document.name)}`);
    $("#docbody").innerHTML = t2.scanned
      ? `<p class="overcap">no text extracted — this is a scan. Do not enter a figure from it;
         read it by eye or ask for a text copy.</p>`
      : `<pre class="doc">${esc(t2.text)}</pre>`;
  });
}

async function openItem(id) {
  /* A DIFFERENT ITEM STARTS CLOSED. Remembering the preview is about not losing your place in
     THIS document; carrying the flag to the next item would open one you had not asked for. */
  if (id !== OPEN_ID) PREVIEW_OPEN = false;
  OPEN_ID = id;
  REVIEWING = false;
  /* AN ITEM GONE FROM UNDER THE LIST SAYS SO. Written, discarded or withdrawn in another window,
     it 404s; the click did nothing and the page read as frozen (12 Oct 2026). */
  let d;
  try { d = await get(`/api/bench/${id}`); }
  catch (e) {
    BENCH_GONE = (BENCH.items.find((i) => i.id === id) || {}).title || id;
    OPEN_ID = null;
    await show("bench");
    return;
  }
  benchFocus(true);
  drawItem(d);
}

/* ONE THING ON THE PAGE AT A TIME (12 Oct 2026). An opened item was drawn at the foot of the
   page, under the drop zone and the sweep, its title in the section heading's small capitals,
   and nothing moved you to it. While an item or the review is open, the list steps aside. */
function benchFocus(on) {
  const list = $("#bench-list");
  if (list) list.hidden = on;
  if (on) window.scrollTo(0, 0);
}

/* WHAT COMES NEXT, once an item's checks are green: the next item still owed, in the bench's
   order after this one, or the review once every item is ready. */
function nextStep(d) {
  if (!d.approved) return "";
  const all = d.bench || [], at = all.findIndex((i) => i.id === d.item.id);
  const owed = [...all.slice(at + 1), ...all.slice(0, Math.max(at, 0))].find((i) => !i.ready);
  return owed
    ? `<p><button class="link" data-open="${esc(owed.id)}" id="nextitem">next item: ${esc(owed.title)}</button></p>`
    : `<p><button class="link" id="reviewall">review and write</button></p>`;
}

/* THE REVIEW BEFORE WRITING (12 Oct 2026). Every ready item, each row in the desk's words, its
   reasons and its checks, and ONE PRESS PER ITEM: each event keeps its own approval, and a press
   that wrote them all would be a background pass in all but name. */
async function reviewItems() {
  REVIEWING = true;
  OPEN_ID = null;
  benchFocus(true);
  const all = (await get("/api/panel/bench")).data.items;
  const ready = await Promise.all(all.filter((i) => i.ready)
    .map((i) => get(`/api/bench/${i.id}`)));
  const owed = all.filter((i) => !i.ready);
  if (!ready.length) {           // nothing left to write: back to the list
    REVIEWING = false;
    benchFocus(false);
    $("#item").innerHTML = "";
    return;
  }
  const labels = BENCH.table_labels || {};
  const card = (d) => {
    const it = d.item, rdg = it.reading;
    const rows = (it.rows || []).map((r) => `<h3>${esc(r.adjustment ? BENCH.adjustment_label
      : labels[r.table] || r.table)}</h3>
      <dl class="detail">${Object.entries(r.values).filter(([, v]) => v !== "" && v != null)
        .map(([k, v]) => `<dt>${head(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>`).join("");
    const said = it.why || {};
    const marked = firstMarks(it);
    const whys = ["why_entered", "why_exited"].filter((w) => (said[w] || "").trim())
      .map((w) => `<dt>${head(w)}</dt><dd>${esc(said[w])}</dd>`).join("")
      + ((d.retires || []).length ? `<dt>${head("retires")}</dt><dd>${esc(d.retires.join(", "))}</dd>` : "");
    return `<section class="review-item" data-item="${esc(it.id)}">
      <div class="row-head"><h2>${esc(it.title)}</h2></div>
      ${rows}${marked}${whys ? `<dl class="detail">${whys}</dl>` : ""}
      <ul class="items gates">${d.gates.map((g) =>
        `<li class="ok"><span class="tag">ok</span><strong>${esc(g.label || g.name)}</strong></li>`).join("")}</ul>
      <p><button class="link" data-write="${esc(it.id)}">${rdg
        ? "file the document and write the reading" : "write to the record"}</button></p>
      <pre class="paste" data-out="${esc(it.id)}" hidden></pre></section>`;
  };
  $("#item").innerHTML = `
    <div class="row-head"><button class="link" id="back">back to the Bench</button></div>
    ${ready.map(card).join("")}
    ${owed.length ? `<h2>Still owed</h2><ul class="items">${owed.map((i) =>
      `<li class="note"><span class="tag">${esc(i.state)}</span><button class="link" data-open="${
        esc(i.id)}">${esc(i.title)}</button> <span class="muted">${esc(i.blocked_by.join(", "))}</span></li>`)
      .join("")}</ul>` : ""}`;
  $("#back").addEventListener("click", () => { REVIEWING = false; show("bench"); });
  $("#item").querySelectorAll("[data-open]").forEach((b) =>
    b.addEventListener("click", () => openItem(b.dataset.open)));
  $("#item").querySelectorAll("[data-write]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("Write this to the record?\n\nIt cannot be undone from the desk.")) return;
    b.disabled = true;
    const r = await fetch(`/api/bench/${b.dataset.write}/commit`, { method: "POST" });
    const out = $(`[data-out="${b.dataset.write}"]`);
    out.hidden = false;
    if (r.ok) {
      out.textContent = "written";
      setTimeout(() => show("bench"), 1200);
    } else {
      out.textContent = "not written\n\n" + ((await r.json()).detail || "");
      b.disabled = false;
    }
  }));
}

/* ---------------------------------------------------------------------------------------
   Three panels that read; none of them computes. Every figure below is rendered
   exactly as the engine handed it over — a percentage worked out here would be a second
   calculation of something engine.py already answers, one remove further out.

   THEY USE THE STYLE LAYER AND INVENT NOTHING. The first version reached for `class="n"`,
   `.cards` and `.card`, none of which exist in app.css, so figures ran together as
   "Realisations24" and no number was right-aligned. The house classes are `num` on a cell,
   `.items` for a list, `.muted` for prose: use the style layer, never set it at a call site.
   --------------------------------------------------------------------------------------- */

/* SENTENCE CASE for a heading, a column head and a label: the words as written, first letter
   up. The CSS set them all in capitals until 1 Oct 2026, which hid that "company" and
   "Accounts" headed neighbouring columns. */
const sentence = (t) => t ? t.charAt(0).toUpperCase() + t.slice(1) : t;

/* COLUMN HEADINGS ARE NOT WRITTEN HERE. Each panel arrives with `heads`, its columns in
   house/headings.py's words for its tab, and paintPanel() keeps them for the page — the one list
   the report reads too. This file kept its own map until
   then, and "Entry" headed a local price on Holdings and a sterling cost on Round Trips. A field
   the list has not named shows its own name, and tests/test_figures.py fails before it ships. */
let HEADS = {};
/* A HEAD MAY BREAK AFTER A SLASH. "Proceeds/share (GBP)", a Round Trips head until 14 Oct 2026,
   was otherwise one 85px word over figures 56px wide, and it pushed the page 9px past a 1,728px
   window. The words stay the list's. */
const head = (c) => esc(sentence(HEADS[c] || c.replace(/_/g, " "))).replace(/\//g, "/<wbr>");

const MONEYCOL = ["cost", "value", "gain", "proceeds",
                  "opening_nav", "closing_nav", "capital_deployed", "return_income",
                  "change", "price_effect", "fx_effect", "transacted", "value_to",
                  "exposure", "nav", "opening_capital", "capital_employed", "capital_growth",
                  "income", "amount", "cash"];
const PCTCOL = ["gain_pct", "weight", "return", "price_move_pct", "ytd"];

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
   Book.HEADLINE, because a renderer must not decide what a figure MEANS by reading its label —
   that is the defect that got figures.py deleted. Colour's job here is scanning a column, and
   the Dashboard is a summary list rather than a table you scan. */
const MOVEMENTCOL = ["gain", "gain_pct", "return",
                     "change", "price_effect", "fx_effect", "price_move_pct"];

/* THE FOUR ADDED 6 SEP 2026 FOR What Changed, AND THE ONE HELD BACK. `change`, `price_effect`,
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

   Price Refresh and Reconcile each opened with four explanation blocks, so the table on one and
   What disagrees on the other began below the fold. The steps keep their TAG, their LABEL and
   their STATE line — "13 days old · limit 21 days" — which
   is the work. The paragraph saying why the step exists comes here, closed.

   ONE MECHANISM, NOT TWO. A second fold with its own markup would drift from this one the way
   the four Reconcile blocks and the four Price Refresh blocks already had. */
/* THE STEPS, EXPLAINED ONCE AND BELOW THE TABLE. `Reading` keeps its links on screen because
   those are the work; the reasons live here, Events' among them: the step that reported a
   sweep went on 13 Oct 2026, being only this browser tab's memory of one. */
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

const whyFold = (summary, pairs) => pairs.length ? `
  <details class="why-fold"><summary>${esc(summary)}</summary>
    <dl>${pairs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
  </details>` : "";

/* THE STEPS ON ONE LINE. Price Refresh and Reconcile each stacked their
   steps one to a row, so a step's state, its button and the date box sat rows apart and the
   work began below them. Every step now reads the same way, left to right: its state, its name,
   then what can be pressed. A step with no state yet shows no badge. `body` is markup. */
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

/* THE PAGE TEMPLATE: the pages had been adjusted one at a time, and it showed. Every tab is drawn
   through this, so the bands come in one order everywhere and a change to a band is a change
   to every page that has it:

     1 TITLE    the tab's own name, and one short line of what the page's figures are
     2 STATUS   the step line: state, name, what can be pressed            `stepLine()`
     3 FIGURES  the headline strip                                          `figures()`
     4 FILTERS  one row of filters                                          `filters()`
     5 WORK     the tables and lists, the one band a page writes for itself
     6 WHY      every explanation, closed, at the foot                       `whyFold()`

   A band a page has nothing for is left out. NOTHING EXPLAINS ITSELF ABOVE THE WORK: a note box
   between the figures and the table pushed the table down to be read once. Every page fills the
   window; `data-wide` is what widens it. */
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
   run to several sentences — rendered plain they made every row several centimetres deep and
   the table unreadable. Clamped to one line with the whole text on hover and in the title.

   NOR MUST A LABEL. With the notes clamped, Round Trips' rows were still three to five lines
   deep, because a date, an account and a company wrapped in their narrow columns (measured
   29 Sep 2026). Every cell of a data row is one line (app.css); a company name and Holdings'
   list of accounts are read WHOLE, where they had been clipped at 16rem.
   The table scrolls sideways instead. */
const ONELINE = ["closed", "realisation_id", "ticker", "account"];
/* A DATE IS READ WHOLE WHATEVER ITS COLUMN IS CALLED: Holdings' Opened broke at its hyphens and
   doubled every row (30 Sep 2026). */
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

/* A HEADING MUST MEET ITS NUMBERS. cell() decides right-alignment per
   VALUE, but every <th> here was rendered plain — so a right-aligned column of figures sat
   under a left-aligned heading, and Holdings, Performance and Round Trips each read as though
   the headings belonged to the column to their left. `th.num` has been in app.css all along
   and the two hand-built tables already used it; only this generic one did not. Decided per
   COLUMN, not per cell, because a heading cannot be right for some of its rows. */
const isNumCol = (c, rows) => {
  if (MONEYCOL.includes(c) || PCTCOL.includes(c)) return true;
  const first = rows.find((r) => r[c] != null);
  return first ? typeof first[c] === "number" : false;
};

/* ONE FILTER ROW, THREE PANELS: the same form, order and layout across Holdings, Round
   Trips and Trades, in the grey filter boxes.

   They had three shapes. Trades used labelled `.f` boxes in a grid; Holdings and Round
   Trips used inline controls in a paragraph with the label sitting to the LEFT of the select,
   so the same "Account" dropdown was a different object on each tab. The `.f` box is the one
   chosen, and it is already the bench's field, so this is the desk having one idea of a
   labelled control rather than two.

   THE ORDER IS FIXED AND THE SAME EVERYWHERE, applying only the fields a panel has (S8, 14 Oct
   2026): account · company · ticker · from · to, then the page's own control (direction on Trades,
   the group by on Holdings). Who, then what, then when, so a box shared by two pages sits in the
   same place on both: Account is the first box on every page, Company and Ticker the second and
   third, the dates the fourth and fifth. No filter reads "all" everywhere. */
const filterField = (label, control) =>
  `<label class="f"><span>${esc(sentence(label))}</span>${control}</label>`;

const filters = (fields, clearId) => `
  <div class="grid filters">${fields.filter(Boolean).join("")}</div>
  ${clearId ? `<p class="filter-clear"><button class="link" id="${clearId}">clear filters</button></p>` : ""}`;

/* TWO THINGS A COLUMN OF FIGURES CANNOT DO ON ITS OWN, both in `opts` so the other call sites
   are untouched.

   `inserts` PUTS A HAND-BUILT COLUMN IN THE MIDDLE. `extraCell` only ever appends, so a
   column it renders lands after everything — including the row's controls, 340px past the
   right edge of Holdings. A column belongs where its meaning puts it, so `{after, head, cell}`
   names the column it follows.

   `afterRow` OPENS A FULL-WIDTH ROW UNDER EACH ROW, which is the only way a table can carry a
   detail pane: a note cannot live inside a <tr> and still span the columns. The colspan is
   DERIVED from what was actually rendered — declared columns, inserts, and however many <th>
   the caller's own header string added. A hardcoded number would go stale the first time a
   column joined, silently, leaving the last cell of every expansion outside the table.

   `cells` DRAWS A DECLARED COLUMN BY HAND, in its own place: Trades' Quantity and Traded price
   read a spread bet in its own terms, a stake per point at a level in points.

   `rowClass` NAMES A ROW'S STATE for the stylesheet: a superseded mark is drawn struck through. */
/* EVERY TABLE SORTS BY ITS HEADINGS. A heading pressed sorts its column —
   figures largest first, words and dates A to Z first — pressed again reverses it, and a third
   press puts the page's own order back. A row's detail moves with it. The sort is held per page
   and table, as the filters are, so a filter redraw keeps it. It orders what the engine sent;
   nothing is worked out. A table whose order IS its layout opts out (`sort: false`): the tables
   that name the book first and then each account once (Performance's quarters and its year,
   Accounts' Income and costs; S8, 14 Oct 2026), and a detail's mark history.

   A SORTING TABLE NAMES ITSELF (`name`), and its sort is held under the page and that name. It
   was held under the page and the table's COLUMNS, so two tables drawn with the same columns
   held one sort between them: Change pressed on What Changed's Shares ordered its Spread bets
   the next time the page was drawn (14 Oct 2026). */
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
                               : local.has(c) ? (r.stake_per_point != null ? pointsCell(r[c])
                                                 : `<td class="num">${localPrice(r[c], r.currency)}</td>`)
                               : draw(c, r[c])) + at(c).map((i) => i.cell(r)).join("")).join("")}` +
      `${extraCell(r)}</tr>` + (afterRow ? afterRow(r, span) : "")).join("")}</tbody>
  </table></div>`;
};

/* THE HEADLINE STRIP, the template's third band: a label, its figure, and optionally `lead` or
   `indent`, which is how the Dashboard sets a total above its parts. The label says what each
   figure is; the basis pill beside it went on 1 Oct 2026. */
const figures = (rows) => `<table class="figures"><tbody>${rows.map(([label, value, kind]) =>
  `<tr${kind === "lead" ? ` class="lead"` : ""}>` +
  `<td${kind === "indent" ? ` class="indent"` : ""}>${esc(label)}</td>` +
  `<td class="num">${value}</td></tr>`).join("")}</tbody></table>`;

/* HOW EACH BROKER ANSWER IS SHOWN. Rendering only — every figure arrives already computed by
   feeds/ig.py, and working one out here would be a second calculation of something the feed already
   answered. A key with no renderer falls back to JSON, which is honest about being unfinished
   rather than hiding the result. */
/* THE ACTION STRIP, SHARED BY TWO PANELS FROM 8 SEPTEMBER 2026.
   It lived inside the `accounts` renderer (the Reconcile tab), which was fine while that was the
   only panel with broker buttons. The 30-day event sweep moved to the Bench that day — it belongs where its
   output goes — so two panels render actions now, and a copied strip would be two strips
   drifting apart. The panel NAME is the only thing that differs. */
async function wireActions(panelName) {
  /* INLINE ACTIONS ARE NOT PANEL BUTTONS. "Work this event" belongs to one row of a sweep
     and is rendered there; listed here it was a standing button with nothing to work.

     EVERY OTHER ACTION OF THE PAGE IS A STANDING BUTTON. The strip once took a list of names,
     because the restart was registered on the Bench for want of another home; since 13 Oct 2026
     it is the shell's own ("desk"), drawn by the rail, and no page's list needs trimming. */
  const acts = Object.values(await loadActions())
    .filter((a) => a.panel === panelName && !a.inline);
  /* THE BUTTON AND WHAT IT REACHES, and no paragraph: what it does is in the page's fold. */
  $("#acts").innerHTML = acts.map((a) =>
    `<p><button class="link" data-act="${esc(a.name)}"${a.available ? "" : " disabled"}>
       ${esc(a.label)}</button>` + badges(a.name) + `</p>`).join("");

  $("#acts").querySelectorAll("[data-act]").forEach((b) =>
    b.addEventListener("click", async () => {
      const out = $("#actout"), view = $("#actview");
      view.hidden = true; view.innerHTML = "";
      out.hidden = false; out.textContent = "asking the broker…";
      try {
        const r = await fetch(`/api/action/${b.dataset.act}`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        const { ok, body, raw } = await readJson(r);
        if (raw) { out.textContent = raw; return; }
        if (!ok) { out.textContent = body.detail || JSON.stringify(body, null, 2); return; }

        /* THE ANSWER IS FIGURES, NOT JSON: asking the broker had returned a screen of code. A
           renderer per action, and JSON only where there is none, so a
           NEW action still shows its result rather than nothing while its view is written. */
        const payload = body.result || {};
        if (payload.ok === false) {
          out.textContent = payload.error + (payload.hint ? `\n\n${payload.hint}` : "");
          return;
        }
        const draw = ACTION_VIEW[b.dataset.act];
        if (!draw) { out.textContent = JSON.stringify(payload.result ?? payload, null, 2); return; }
        const result = payload.result ?? payload;
        if (b.dataset.act === "ig-events") showSweep(result);
        else {
          out.hidden = true;
          view.hidden = false;
          /* STAMPED HERE, at the moment the answer arrived, rather than by the view — a
             timestamp made at render time would move every time the panel was redrawn and
             would say the reading was fresher than it is. */
          view.innerHTML = draw(result, stampNow());
        }
      } catch (e) { out.textContent = String(e); }
    }));

  /* BACK ON THIS TAB, THE LAST ANSWER IS STILL HERE. Re-rendered rather than re-fetched:
     another call to the broker to see what you were already looking at is not a refresh, and
     these are authenticated to the account. */
  if (panelName === "bench" && LAST_SWEEP) showSweep(LAST_SWEEP);
}


const ACTION_VIEW = {
  "ig-events"(d) {
    /* WHAT THE BOOK IS MISSING IS THE POINT of this sweep, so it goes first and the things
       that already tie are a count. An event is never written from here — it is reported, and
       worked on the bench.

       A BUTTON PER EVENT, from 3 Sep 2026, and deliberately not one button for the sweep.
       Carrying several events across in a single press would be a background pass in all but name.
       Each press opens ONE bench item, with the dealId as its evidence reference, and is
       idempotent on that id — press twice and you land on the item you already have. */
    const list = (label, items, tone) => !(items || []).length ? "" : `
      <h3>${esc(label)} <span class="tag ${tone}">${items.length}</span></h3>
      <ul class="items">${items.map((i) =>
        `<li>${esc(typeof i === "string" ? i
          : `${i.date || ""} ${i.amount ?? ""} ${i.detail || ""}`.trim())}</li>`).join("")}</ul>`;

    /* The swept events, held by deal id so a button can name one without carrying the whole
       row through the DOM. Replaced on every sweep — a stale ref must not be workable. */
    IG_EVENTS = {};
    const events = (label, rows, setup) => !(rows || []).length ? "" : `
      <h3>${esc(label)} <span class="tag gap">${rows.length}</span></h3>
      <ul class="items">${rows.map((r) => {
        IG_EVENTS[r.ref] = r;
        /* THE STATUS SITS BESIDE THE EVENT, NOT UNDER IT. `.event-head`, the ledger's old flex row,
           wrapped; once the button's label became "on the bench — why_exited still owed" it
           broke onto its own line and read as a second column. `.swept` gives the row a fixed
           shape — description left, status right, neither wrapping into the other. */
        /* WHAT THIS EVENT IS NOW, not what it was when the sweep ran. An event already in the
           record is DONE and offering to work it again is how a duplicate gets made; one on the
           bench is in progress and says what it still owes. */
        const st = SWEEP_STATUS[r.ref] || {};
        const done = st.in_record;
        const item = st.item;
        const state = done
          ? `<span class="tag ok swept-state">in the book</span>`
          : item
            ? `<span class="tag swept-state">on the bench${
                item.blocked && item.blocked.length
                  ? ` — ${esc(item.blocked.join(", "))} owed` : " — ready"}</span>`
            : setup
              ? `<button class="link swept-do" data-setup="${esc(r.ref)}">set it up</button>`
              : `<button class="link swept-do" data-ig-event="${esc(r.ref)}">work it</button>`;
        return `<li class="swept${done ? " swept-done" : ""}"><div class="swept-head">
            <span class="swept-what">${esc(r.what || r.ref)}</span>${state}</div>
          <p class="muted swept-meta">${esc(r.account || "")} · ${esc(r.ref)}</p>${
            setup ? `<div data-setup-form="${esc(r.ref)}" hidden></div>` : ""}</li>`;
      }).join("")}${setup ? (d.skipped || []).map((s) => `<li>${esc(s)}</li>`).join("") : ""}</ul>`;
    const missing = ["opens", "closes", "costs", "capital", "setups"]
      .reduce((n, k) => n + (d[k] || []).length, 0);
    return `
      <p class="muted">${esc(d.frm || "")} to ${esc(d.to || "")} ·
        <strong>${(d.matched || []).length}</strong> already in the book ·
        <strong>${missing}</strong> the book does not have.</p>

      ${events("Buys", d.opens)}
      ${events("Sales", d.closes)}
      ${events("Costs", d.costs)}
      ${events("Money in or out", d.capital)}
      ${list("Unmatched, and not obviously a book event", d.orphans, "note")}
      ${(d.setups || []).length ? events("Skipped", d.setups, true) : list("Skipped", d.skipped, "note")}
      ${(d.matched || []).length ? `<details><summary>${d.matched.length} matched</summary>
         <ul class="items">${d.matched.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>
       </details>` : ""}`;
  },
};

/* HOW MUCH IS HELD, BY TICKER. A share line is its count; a spread bet is its stake per point,
   the way Trades reads one. */
const heldCell = (r) => r.stake_per_point != null
  ? `<td class="num">£${r.stake_per_point}/pt</td>`
  : r.qty != null ? `<td class="num">${r.qty.toLocaleString("en-GB")}</td>` : `<td class="num">—</td>`;

/* A LEVEL IN POINTS, as IG states it: a bet's entry, traded, exit or current level. A row that
   carries a stake per point is a bet, and every price on it is a level, not a local price. */
const points = (v) => v == null ? "—"
  : Number(v).toLocaleString("en-GB", { maximumFractionDigits: 2 }) + " pts";
const pointsCell = (v) => `<td class="num">${points(v)}</td>`;

/* THE DETAIL UNDER A ROW: ONE LINK ACROSS THE DESK, AND ONE ORDER INSIDE IT (12 Oct 2026).
   Every table's row opens the same way, by "detail", to whatever the record holds on it, each
   part under its own heading from house/headings.py and ALWAYS IN THIS ORDER: the judgement,
   then what happened, then where it came from and what it belongs to, then the marks, which are
   a table. A page names the parts it draws (its panel's DETAIL_COLUMNS, sent as `detail`); a
   heading with nothing logged under it is left out. It replaced three toggles that each said
   what they opened differently — "why" over a trade's note, "detail" over its source, "note" or
   "why" on Round Trips, "marks" and "why" side by side on Holdings. */
const DETAIL = ["why_entered", "why_exited", "research_notes", "note", "source", "quality",
                "broker_ref", "trade_id", "realisation_id", "contract", "funding", "fx_at_trade",
                "fx_from", "marks"];

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
const DETAIL_PART = {
  why_entered: whyPart("why_entered"),
  why_exited: whyPart("why_exited"),
  research_notes: (x) => !(x.research_notes || []).length ? "" :
    `<dt>${head("research_notes")}</dt><dd>${x.research_notes.map((n) =>
      `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.ref)}</a> ` +
      `<span class="muted small">${esc(day(n.date))}</span>`).join(" · ")}</dd>`,
  /* THE LINE'S LAST FIVE REFRESHES, newest first. A spread bet on two contracts shows both, at
     their own levels, and a line whose older marks were banked under its TICKER shows those
     too. A correction — a superseded mark — sits struck through under the mark that replaced
     it. */
  marks: (x, markCols) => !(x.marks || []).length ? "" :
    `<dt>${head("marks")}</dt><dd class="wide">${table(x.marks, markCols, "", () => "",
      { sort: false, rowClass: (m) => m.status === "superseded" ? "superseded" : "",
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

Object.assign(RENDER, {
  holdings(d) {
    /* OWNED AND NOTIONAL, APART AND NEVER ADDED. Both come from the engine — this panel used
       to sum its own rows and was wrong whenever it grouped by issuer. */
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
               inserts: d.by === "ticker"
                 ? [{after: "held_as", head: `<th class="num">${head("qty")}</th>`, cell: heldCell}]
                 : []})}
      ${allocation(d)}`,
    });
  },

  "round-trips"(d) {
    /* THE FIGURES ARE THE SELECTION'S. They were the whole book's with the
       filtered ones relegated to a line underneath, so narrowing to an account changed the
       table and left the three headline numbers answering a question nobody had asked. When a
       filter is on, the whole book sits beside them as context rather than as the answer. */
    const t = d.totals, w = d.whole;
    return page({
      scope: "every closed position, gain net of dealing commission",
      status: d.narrowed ? [{ state: "note", tag: "selected", label: "Whole book",
        body: quiet(`${w.realisations} realisation(s) · proceeds ${money(w.proceeds)}
          · gain ${money(w.gain)}`) }] : null,
      figures: [["Realisations", t.realisations],
                ["Closed out", t.closed_out],
                ["Proceeds", money(t.proceeds)],
                ["Realised gain", money(t.gain)]],
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
      ] },
      /* THE SAME "trades" LINK AS HOLDINGS', by company: the sales a round trip took, and the
         buys before them, are Trades' to show (Sells and Realisation ID left the page for it,
         12 Oct 2026). Then the row's detail: its whys, research notes and note. */
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
                      currency: (r) => r.stake_per_point == null ? cell("currency", r.currency)
                                                                 : `<td>—</td>`,
                      qty: heldCell,
                      entry_price: (r) => r.stake_per_point != null
                        ? pointsCell(r.entry_level_points)
                        : `<td class="num">${localPrice(r.entry_price, r.currency)}</td>`,
                      exit_price: (r) => r.stake_per_point != null
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
     are not frozen yet, which "open" already says (13 Oct 2026). What stops a report shows from
     the day the quarter ends.

     NO DATE BESIDE A NAME: "Q3 2026" and "2026 year end" say the period, as Performance's
     Quarter does (13 Oct 2026). */
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
    /* THE INDEX COMPARISON WAS HERE AND IS GONE — the presentation on 2 Sep 2026 and the
       derivation behind it on 3 Sep, and there is to be no comparison to a benchmark of any kind. An
       index return is TIME-WEIGHTED, having no cash flows, and this book's is
       modified Dietz on NAV, day-weighted, which is MONEY-WEIGHTED and moves with the size and timing of every
       flow into positions. Subtracting one from the other asserted an equivalence that does
       not hold, and no index is coming back beside these figures. */
    return page({
      scope: `every return on ${d.measure}, modified Dietz (day-weighted)`,
      status: d.reports.length ? [{ label: "Reports",
        body: d.reports.map(reportLink).join(" · ") }] : null,
      /* THE BOOK AND EACH ACCOUNT IN ONE TABLE, under one set of heads:
         the same columns named alike, so a figure is read down its column from the book to
         any account. THE ACCOUNT IS A COLUMN, named on its first row and blank on the rest,
         with a rule where the next one starts: the title rows it replaced were bold on a band
         and held no figure (13 Oct 2026). */
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

RENDER_LATE = {
  /* ACCESS — who can open the hosted desk, at which level, and from which devices. THE MAC ONLY:
     the remote door has no route to it. Every button here is one of the Access panel's
     registered actions, and each refusal comes back in desk/auth.py's own words. */
  access(d) {
    const cols = d.columns;
    const levelOptions = (held) => (held ? "" : `<option value="">none</option>`) +
      d.levels.map((l) => `<option${l.level === held ? " selected" : ""}>${esc(l.level)}</option>`)
        .join("");
    const result = (s) => `<span class="tag ${s.result === "signed in" || s.result === "enrolled"
      ? "ok" : s.result === "refused" ? "problem" : "gap"}">${esc(s.result)}</span>`;

    $("#main").innerHTML = page({
      scope: "who can open the hosted desk, at which level, and from which devices",
      work: `
        <h2>Levels</h2>
        <ul class="items">${d.levels.map((l) => `<li class="report">
          <span class="tag ${l.names ? "ok" : "note"}">${esc(l.level)}</span>
          <span>${esc(l.pages.join(" · "))}</span>
          <span class="muted">${l.names ? "holders named" : "every account by its code, "
            + "holders and account numbers withheld"}</span></li>`).join("")}</ul>

        <h2>Readers</h2>
        ${table(d.readers,
          cols.readers.filter((c) => c !== "level" && c !== "now"), "<th></th>",
          (r) => `<td class="oneline"><button class="link" data-revoke-reader="${esc(r.who)}">` +
                 `revoke</button></td>`,
          { name: "readers", inserts: [
              { after: "who", head: `<th>${head("level")}</th>`, cell: (r) => `<td class="oneline">
                  <select data-level-for="${esc(r.who)}" aria-label="Level for ${esc(r.who)}">
                    ${levelOptions(r.level)}</select></td>` },
              { after: "last_signed_in", head: `<th>${head("now")}</th>`,
                cell: (r) => `<td class="oneline"><span class="tag ${r.now === "signed in"
                  ? "ok" : "note"}">${esc(r.now)}</span></td>` }],
            /* EACH READER'S DEVICES UNDER THEIR ROW, each with its own revoke. */
            afterRow: (r, span) => r.device_list.length ? `<tr class="devices"><td colspan="${span}">
              ${table(r.device_list, cols.devices, "<th></th>", (v) => `<td class="oneline">
                <button class="link" data-revoke-device="${esc(v.key)}"
                        data-device="${esc(v.device)}">revoke</button></td>`, { name: `devices ${r.who}` })}
              </td></tr>` : "" })}
        <p><button class="link" id="sign-everyone-out">sign everyone out</button></p>

        <h2>Enrol a device</h2>
        <div class="grid">
          ${filterField("reader", `<select id="enrol-who"><option value="">a new reader</option>
            ${d.readers.map((r) => `<option>${esc(r.who)}</option>`).join("")}</select>`)}
          ${filterField("name", `<input id="enrol-name" autocomplete="off" size="14">`)}
          ${filterField("level", `<select id="enrol-level">${levelOptions("principal")}</select>`)}
        </div>
        <p><button class="primary" id="enrol-code">Issue an enrol code</button></p>
        <p id="enrol-out" hidden></p>
        <pre id="access-out" class="error" hidden></pre>

        <h2>Sign-ins, the last ${d.log_days} days</h2>
        ${table(d.signins, cols.signins.filter((c) => c !== "result"), "", () => "",
            { name: "sign-ins", inserts: [{ after: "at", head: `<th>${head("result")}</th>`,
                          cell: (s) => `<td class="oneline">${result(s)}</td>` }] })}

        <h2>Account codes</h2>
        ${table(d.codes, cols.codes, "", () => "", { name: "codes" })}`,
      why: [["Levels", "What each level opens is decided by the remote door on every request, "
               + "never by the page; a change here holds from the reader's next request."],
            ["Enrolling", `A code lets one device enrol a passkey for one reader. It works once, `
               + `for ${d.code_minutes} minutes, typed into the hosted desk's sign-in. A new `
               + `reader's level comes with their first code; after that it is changed above.`]],
    });

    const out = $("#access-out");
    const act = async (name, body, ask) => {
      if (ask && !confirm(ask)) return null;
      out.hidden = true;
      const r = await fetch(`/api/action/${name}`, { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
      const { ok, body: b, raw } = await readJson(r);
      const res = (b && b.result) || {};
      if (raw || !ok || res.ok === false) {
        out.hidden = false;
        out.textContent = raw || res.error || (b && b.detail) || "refused";
        return null;
      }
      return res;
    };
    const again = () => show("access");

    document.querySelectorAll("[data-level-for]").forEach((sel) =>
      sel.addEventListener("change", async () => {
        if (sel.value && await act("access-set-level", { who: sel.dataset.levelFor,
                                                         level: sel.value })) again();
      }));
    document.querySelectorAll("[data-revoke-device]").forEach((b) =>
      b.addEventListener("click", async () => {
        if (await act("access-revoke-device", { key: b.dataset.revokeDevice },
                      `Revoke ${b.dataset.device}? Its passkey stops working at once.`)) again();
      }));
    document.querySelectorAll("[data-revoke-reader]").forEach((b) =>
      b.addEventListener("click", async () => {
        const who = b.dataset.revokeReader;
        if (await act("access-revoke-reader", { who },
                      `Revoke ${who}? Every device of theirs stops working at once.`)) again();
      }));
    $("#sign-everyone-out").addEventListener("click", async () => {
      const res = await act("access-sign-everyone-out", {},
                            "Sign everyone out of the hosted desk?");
      if (res) again();
    });

    /* A NEW READER IS NAMED AND GIVEN A LEVEL; one already enrolled keeps theirs, so the two
       boxes are for a new reader only. */
    const who = $("#enrol-who");
    const fit = () => {
      const fresh = !who.value;
      $("#enrol-name").closest("label").hidden = !fresh;
      $("#enrol-level").closest("label").hidden = !fresh;
    };
    who.addEventListener("change", fit);
    fit();
    $("#enrol-code").addEventListener("click", async () => {
      const fresh = !who.value;
      const res = await act("access-enrol-code", {
        who: fresh ? $("#enrol-name").value : who.value,
        level: fresh ? $("#enrol-level").value : null });
      if (!res) return;
      const shown = $("#enrol-out");
      shown.hidden = false;
      shown.innerHTML = `<span class="enrol-code">${esc(res.code)}</span>
        <span class="muted">for ${esc(res.who)}, at ${esc(res.level)}. Typed on the device at the
        hosted desk's sign-in. Lasts ${esc(res.minutes)} minutes, once.</span>`;
    });
  },

  /* TRADES — every buy and sale on file, interrogable.
     Dates and account go to book.activity(); ticker and direction narrow the result. Nothing
     is computed here. */
  async trades(d) {
    const price = localPrice;
    const opts = (list, sel) => `<option value="">all</option>` +
      list.map((v) => `<option${v === sel ? " selected" : ""}>${esc(v)}</option>`).join("");

    $("#main").innerHTML = page({
      scope: "every buy and sale on file",
      status: [{ label: "Trades", body: `<span id="q-count" class="muted small"></span>` }],
      filters: { clear: "q-clear", fields: [
        filterField("account", `<select id="q-account">${opts(d.accounts)}</select>`),
        filterField("company", `<select id="q-company">${opts(d.companies || [], PENDING_COMPANY)}</select>`),
        filterField("ticker", `<select id="q-ticker">${opts(d.tickers)}</select>`),
        filterField("from", `<input id="q-start" type="date" min="${esc(d.span.first || "")}"
               max="${esc(d.span.last || "")}">`),
        filterField("to", `<input id="q-end" type="date" min="${esc(d.span.first || "")}"
               max="${esc(d.span.last || "")}">`),
        filterField("direction", `<select id="q-direction">${opts(d.directions)}</select>`),
      ] },
      work: `<div id="q-rows"></div>`,
    });

    const draw = (res) => {
      $("#q-count").textContent =
        `${res.total} trade${res.total === 1 ? "" : "s"}` +
        (res.span.first ? ` · ${day(res.span.first)} to ${day(res.span.last)}` : "");
      /* A TABLE IN HOLDINGS' ORDER (12 Oct 2026): the deal as struck on the line, and
         everything else the record holds on the trade in its detail. A spread bet reads in its
         own terms, a stake per point at a level in points, with no currency of its own. */
      $("#q-rows").innerHTML = res.rows.length ? table(res.rows, d.columns, "<th></th>",
        (r) => `<td class="nowrap">${detailLink(detailList(r, d.detail))}</td>`,
        { name: "trades", afterRow: (r, span) => detailRow(detailList(r, d.detail), span),
          cells: {
            currency: (r) => r.level_points == null ? cell("currency", r.currency) : `<td>—</td>`,
            qty: heldCell,
            traded_price: (r) => r.level_points == null
              ? `<td class="num">${price(r.traded_price, r.currency)}</td>`
              : pointsCell(r.level_points) } })
        : `<p class="muted">nothing matches those filters.</p>`;
    };

    const run = async () => {
      HELD_FILTERS.trades = Object.fromEntries(FILTERS.map((id) => [id, $(`#${id}`).value]));
      const p = new URLSearchParams({
        start: $("#q-start").value, end: $("#q-end").value,
        account: $("#q-account").value, ticker: $("#q-ticker").value,
        direction: $("#q-direction").value, company: $("#q-company").value });
      draw(await get(`/api/trades?${p}`));
    };
    const FILTERS = ["q-account", "q-company", "q-ticker", "q-start", "q-end", "q-direction"];
    /* THE TICKER BOX IS THE CHOSEN COMPANY'S (14 Oct 2026), so it cannot name a line the
       Company box has ruled out; a company chosen starts its ticker afresh. Bound before `run`,
       so the query reads the ticker it leaves. */
    const tickers = (sel = "") => {
      const co = $("#q-company").value;
      $("#q-ticker").innerHTML = opts(co ? d.company_tickers[co] || [] : d.tickers, sel);
    };
    $("#q-company").addEventListener("change", () => tickers());
    FILTERS.forEach((id) => $(`#${id}`).addEventListener("change", run));
    $("#q-clear").addEventListener("click", () => {
      FILTERS.forEach((id) => ($(`#${id}`).value = ""));
      tickers();
      run();
    });
    /* ARRIVED FROM A "trades" LINK. The select is already showing the company, so run the query
       rather than drawing the unfiltered ledger underneath a filter that says otherwise. The
       link's company is taken once; from then on it is held as any filter here is. */
    const held = HELD_FILTERS.trades;
    if (PENDING_COMPANY) {
      PENDING_COMPANY = null;
      tickers();
      run();
    } else if (held && Object.values(held).some((v) => v)) {
      FILTERS.forEach((id) => ($(`#${id}`).value = held[id] ?? ""));
      tickers(held["q-ticker"] ?? "");
      run();
    } else {
      draw({ rows: d.rows, total: d.total, span: d.span });
    }
  },

  /* RECONCILE — what the book says beside what the broker says.
     Two checks, and they are not the same check: a share account agrees on units, checked at the
     door; an IG account's equity is read in one pass with its marks and held to a band. Neither
     is decided here — the verdict arrives already made, from the same function the audit and
     the Dashboard ask. */
  async reconcile(d) {
    /* EVERY VERDICT HAS A TAG. One that fell through to the default `note` would wear the colour
       of a row inside its band, for a row that has not been judged at all. */
    const verdictTag = { "units-agree": "ok", "within-band": "note", differs: "problem",
                         "no-statement": "gap", "no-holdings": "gap", "struck-apart": "gap" };
    /* THE TAG READS IN WORDS: the engine's code is "units-agree", the reader's is "units agree". */
    const verdictWords = (v) => v.replace(/-/g, " ");
    /* AN IG READING'S FIVE FIGURES, under the broker's figure, in IG's own words: the reading
       keeps them once each (13 Oct 2026), and a figure kept is a figure shown. */
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

    /* REPORT ONLY WHAT DISAGREES is the reconcile skill's instruction, and it is a reporting
       rule rather than a data one — the panel hands over every row, and the lead is what needs
       attention. A clean book leads with a clean line, not with silence. */
    const lead = d.disagreements.length
      ? `<ul class="items">${d.disagreements.map((r) =>
          `<li class="problem"><span class="tag">differs</span><strong>${esc(r.account)}</strong>
           book and broker differ by ${money(r.difference)} — past the
           ${r.band === null ? "penny" : money(r.band)} band.</li>`).join("")}</ul>`
      : `<ul class="items"><li class="clear"><span class="tag">clear</span>
         every account that can be checked, does.</li></ul>`;

    /* THE ENGINE'S OWN WORDS, ONCE. Each unjudged account's `rule` and its difference sit in
       its table row, where a reader already looks; the lead names the accounts and says once
       what a difference beside them is. It used to repeat each row's rule and a caveat
       sentence per account above the table (29 Sep 2026). */
    const gaps = d.gaps.length ? `<ul class="items"><li class="gap"><span class="tag">not
        judged</span><strong>${d.gaps.map((r) => esc(r.account)).join(" · ")}</strong> — the
        table says why.</li></ul>`
      : "";

    $("#main").innerHTML = page({
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

  async bench(d) {
    /* BACK TO THE LIST IS BACK TO ONE COLUMN. `wide` is the item's two-column layout and
       nothing on the list needs it; left on, it stretched the list across the window. */
    PREVIEW_OPEN = false;
    document.body.classList.remove("wide");
    BENCH = d;
    /* AN EMPTY LIST IS NOT DRAWN: the status line already counts it (12 Oct 2026). */
    const items = d.items.length ? d.items.map((i) =>
      `<li class="${i.ready ? "clear" : "note"}"><span class="tag">${i.ready ? "ready" : i.state}</span>` +
      `<button class="link" data-open="${esc(i.id)}">${esc(i.title)}</button> ` +
      `<span class="muted">${i.rows} row(s)` +
      (i.blocked_by.length ? ` · blocked: ${esc(i.blocked_by.join(", "))}` : "") +
      `</span></li>`).join("") : "";

    /* WHAT EACH DOCUMENT SAYS IT IS, before you open it. HL exports three different reports
       all titled "Portfolio Summary" and the -2/-3 on disk is macOS numbering downloads in the
       order they happened — so the filename is the one thing here that cannot be trusted, and
       the row says what the CONTENT matched instead. Two matches is reported as two: a class
       decides which columns mean what, and guessing between them would be worse than asking. */
    const seen = (r) => {
      if (!r) return "";
      if (r.why) return ` <span class="stale">unreadable — ${esc(r.why)}</span>`;
      if (r.scanned) return ` <span class="stale">a scan — read it by eye</span>`;
      if (!r.classes.length) return ` <span class="muted small">not recognised</span>`;
      const at = r.instant ? ` · as at ${esc(r.instant)}` +
        (r.instant_from === "download" ? " (downloaded)" : "") : "";
      return r.classes.length === 1
        ? ` <span class="muted small">${esc(r.classes[0])}${at}</span>`
        : ` <span class="stale">matches ${r.classes.map(esc).join(" or ")} — say which</span>`;
    };
    const docs = d.documents.length ? d.documents.map((f) =>
      `<li class="gap"><span class="tag">waiting</span>${esc(f.name)}${seen(f.recognised)} ` +
      `<button class="link" data-doc="${esc(f.name)}">work it</button></li>`).join("")
      : "";

    /* A PUBLISHED RESEARCH NOTE THE BOOK HAS NO ROW FOR, and the codes it would be filed under:
       one press each. */
    const notes = (d.notes || []).map((n) =>
      `<li class="gap"><span class="tag">published</span>${esc(n.ref)} · ${esc(day(n.date))} · ` +
      `${esc(n.company)} · ${esc(n.kind)} → ${esc(n.codes.join(", "))} ` +
      `<button class="link" data-note="${esc(n.ref)}">record</button></li>`).join("");

    /* WHAT MAY LAND COMES FROM THE SERVER. desk/intake/dropoff.py holds the list and the cap; the
       screen states them so a refusal is not the first time anyone hears the rule, and it
       would be a second copy of them if it were written out here. */
    const a = d.accepts;
    const mb = Math.round(a.max_bytes / (1024 * 1024));

    /* THE THIRD ROUTE IN, moved here from what is now Reconcile on 8 September 2026. The bench has
       three ways to start work — a dropped document, `+ new item`, and a swept IG event — and
       this was the only one that began on a different tab, so "Work this event" had to carry
       you across to reach the item it had just made. */
    const ready = d.items.filter((i) => i.ready).length;
    $("#main").innerHTML = page({
      scope: "an event, from evidence to an approved row",
      status: [
        { label: "Items", body: `${quiet(`${d.items.length} on the bench`)}
          <button class="link" id="newitem">+ new item</button>${ready
            ? ` <button class="link" id="review">review and write (${ready})</button>` : ""}` },
        { label: "Inbox", body: quiet(`${d.documents.length} document(s) waiting`) },
        { label: "Research", body: quiet(`${(d.notes || []).length} note(s) waiting`) },
      ],
      work: `
        <div id="bench-list">${BENCH_GONE ? `<ul class="items"><li class="gap"><span class="tag">gone</span>${
          esc(BENCH_GONE)} is no longer on the bench</li></ul>` : ""}
        ${items ? `<h2>On the bench</h2><ul class="items">${items}</ul>` : ""}
        ${docs ? `<h2>Documents waiting</h2><ul class="items">${docs}</ul>` : ""}
        ${notes ? `<h2>Research notes waiting</h2><ul class="items">${notes}</ul>
          <pre class="error" id="noteout" hidden></pre>` : ""}
        <div class="drop" id="drop">
          <strong>Drop a contract note or statement here</strong>
          <span class="muted">It waits under Documents and opens on the Bench.
            ${a.extensions.map(esc).join(" · ")} · up to ${mb} MB</span>
          <span class="muted"><button class="link" id="pickbtn">or choose a file</button></span>
          <input type="file" id="pick" multiple hidden>
        </div>
        <pre class="error" id="dropout" hidden></pre>
        <h2>Ask the broker</h2>
        <div id="acts"></div>
        <div id="actview" hidden></div>
        <pre id="actout" class="paste" hidden></pre>
        </div>
        <section id="item"></section>`,
      why: d.why,
    });

    BENCH_GONE = null;
    wireDrop();
    await wireActions("bench");
    const rv = $("#review");
    if (rv) rv.addEventListener("click", () => reviewItems());

    $("#newitem").addEventListener("click", async () => {
      const it = await fetch("/api/bench", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "untitled" }) }).then((r) => r.json());
      /* Re-render the panel so the list stops saying "nothing on the bench" while an item is
         open beneath it, then re-open what was just created. */
      OPEN_ID = it.id;
      await show("bench");
    });
    $("#main").querySelectorAll("[data-open]").forEach((b) =>
      b.addEventListener("click", () => openItem(b.dataset.open)));
    $("#main").querySelectorAll("[data-doc]").forEach((b) =>
      b.addEventListener("click", async () => {
        const it = await fetch("/api/bench", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ origin: "document", title: b.dataset.doc,
                                 document: { name: b.dataset.doc } }) }).then((r) => r.json());
        OPEN_ID = it.id;
        await show("bench");
      }));

    /* ONE PRESS WRITES ONE NOTE'S ROWS; a refusal stays on the page, saying why. */
    $("#main").querySelectorAll("[data-note]").forEach((b) =>
      b.addEventListener("click", async () => {
        b.disabled = true;
        const { ok, body, raw } = await readJson(await fetch(
          `/api/bench/notes/${encodeURIComponent(b.dataset.note)}`, { method: "POST" }));
        if (ok) { await show("bench"); return; }
        const out = $("#noteout");
        out.hidden = false;
        out.textContent = raw || (body && body.detail) || "refused";
        b.disabled = false;
      }));

    /* THE ITEM BEING WORKED COMES BACK OPEN, unless it has left the bench
       — written, discarded or withdrawn — and then there is nothing to reopen. */
    if (OPEN_ID && d.items.some((i) => i.id === OPEN_ID)) openItem(OPEN_ID);
    else OPEN_ID = null;
    if (REVIEWING) reviewItems();
  },

  /* PRICE REFRESH — the only screen on this desk that writes.

     THE FOUR STEPS ARE THE PANEL, not decoration. feeds/refresh.py exists as ONE command because two
     commands meant two chances to forget the first. Here the same ordering is what you look at while you work.

     A ROW CANNOT BE TICKED UNTIL IT IS COMPLETE. Rule 1 of docs/prices.md — update a price and
     its date together — enforced at the point of entry rather than explained afterwards. The
     SERVER refuses the same thing; this only makes the refusal visible before it happens, which
     is the difference between a form that teaches and a form that scolds. */
  async "price-refresh"(d) {
    /* Read before the form's first re-check, which would record the empty form over it. */
    const heldRows = PRICE_SWEEP ? PRICE_SWEEP.rows : null;
    /* THE REVIEW STEP LEADS WITH THE MARKS' AGE, the engine's figure and the Dashboard's words
      , against the limit that judges it; a count past the limit is its tag. */
    const stale = (d.prices || []).filter((r) => r.stale).length;

    /* THE BANK STEP ASKS NOTHING OF A READER: the write banks the outgoing marks whether or not
       they are on file. It is drawn only when the histories cannot be read; its
       rule stays in the fold. */
    const b = d.banked;
    const bank = !b.unavailable ? [] : [{ label: d.steps[0].label, state: "problem",
      title: `history/ could not be read: ${b.unavailable}`,
      body: quiet("history/ could not be read") }];

    /* ONE ROW PER MARK. `was` is the outgoing value and its age, which is the thing you are
       replacing; the three cells beside it are what a FETCH puts there, READ-ONLY. A price is
       never typed: the door refuses one without an instant (`struck`, `at`), which only a feed
       supplies — and a fetched figure edited before it was ticked would have travelled under
       the vendor's source. A RATE the sweep left unpriced is the one line opened for typing,
       by `unpriced()` (29 Sep 2026). The tick waits for all three cells. */
    /* WHERE THE FIGURE CAME FROM, once it is there. Empty until something fills the row, then
       `fetched` or `derived` — quotes and a cross ticked identically in one column is
       how the difference stops being visible, and the difference is the whole of the glossary's
       provenance section. A DERIVED mark may never be labelled sourced. */
    const priceRow = (r) => `
      <tr data-kind="price" data-key="${esc(r.line)}">
        <td class="oneline">${esc(r.line)}</td>
        <td class="num muted">${r.price} ${r.contract ? "pts" : esc(r.currency)}</td>
        <td class="small ${r.stale ? "stale" : "muted"}">${esc(day(r.as_of))} · ${r.age_days}d</td>
        <td class="num"><input data-f="price" readonly size="10"></td>
        <td class="oneline"><input data-f="as_of" readonly size="10"> <span class="muted small" data-when></span></td>
        <td class="wide-cell"><input data-f="source" readonly></td>
        <td class="origin"></td>
        <td><label class="tick"><input type="checkbox" data-tick disabled
          aria-label="${head("take")}"></label></td>
      </tr>`;

    /* AN IG ACCOUNT, previewed like a price: its outgoing equity and date, then what the sweep
       reads. Its equity is written WITH the levels read in the same pass (retick). */
    const readingRow = (r) => `
      <tr data-kind="reading" data-key="${esc(r.account)}">
        <td class="oneline">${esc(r.account)}</td>
        <td class="num muted">${money(r.equity)}</td>
        <td class="muted small">${esc(day(r.as_of))} · ${r.age_days}d</td>
        <td class="num"><input data-f="equity" readonly size="10"></td>
        <td><input data-f="as_of" readonly size="10"></td>
        <td class="wide-cell"><input data-f="source" readonly></td>
        <td class="origin"></td>
        <td><label class="tick"><input type="checkbox" data-tick disabled
          aria-label="${head("take")}"></label></td>
      </tr>`;

    const rateRow = (r) => `
      <tr data-kind="rate" data-key="${esc(r.currency)}">
        <td class="oneline">${esc(r.currency)}</td>
        <td class="num muted">${r.rate}</td>
        <td class="muted small">${esc(day(r.as_of))}${r.age_days == null ? "" : ` · ${r.age_days}d`}</td>
        <td class="num"><input data-f="rate" readonly inputmode="decimal" size="10"></td>
        <td class="oneline"><input data-f="as_of" readonly size="10"> <span class="muted small" data-when></span></td>
        <td class="wide-cell"><input data-f="source" readonly></td>
        <td class="origin"></td>
        <td><label class="tick"><input type="checkbox" data-tick disabled
          aria-label="${head("take")}"></label></td>
      </tr>`;

    /* A DATED RATE THE RECORD LACKS: one row per currency and date, showing the
       rate that date converts at today, filled by its fetch with the close of the date's newest
       session and BANKED into the history, never written over a live rate. Nothing is typed into
       one: a dated rate is a close. */
    const lackingRow = (r) => `
      <tr data-kind="lacking" data-key="${esc(r.currency)}@${esc(r.date)}" data-currency="${esc(r.currency)}">
        <td class="oneline">${esc(r.currency)}</td>
        <td class="num muted">${r.rate == null ? "—" : r.rate}</td>
        <td class="muted small">${esc(day(r.date))} · ${esc(r.why)}</td>
        <td class="num"><input data-f="rate" readonly inputmode="decimal" size="10"></td>
        <td class="oneline"><input data-f="as_of" readonly size="10"> <span class="muted small" data-when></span></td>
        <td class="wide-cell"><input data-f="source" readonly></td>
        <td class="origin"></td>
        <td><label class="tick"><input type="checkbox" data-tick disabled
          aria-label="${head("take")}"></label></td>
      </tr>`;

    /* The header control. `data-all` names the KIND it governs, so the wiring below never has
       to know which table it is in — the same hook the rows already carry. */
    const takeAll = (kind) =>
      `<label class="tick"><input type="checkbox" data-all="${kind}" disabled> all</label>`;

    /* ONE TABLE, THREE GROUPS. The IG accounts were a table of their own
       that appeared only after the fetch, with no take-all and its ticks out of line with the
       rest, and both readings were missed on the day's sweep. One set of columns puts every tick
       under the one above it; each group keeps its own take-all, because the three arrive by
       different routes and are finished at different moments. */
    const group = (label, kind, rows) => `
      <tbody><tr><th colspan="7">${label}</th><th>${takeAll(kind)}</th></tr>${rows.join("")}</tbody>`;

    $("#main").innerHTML = page({
      scope: `the marks stand at ${day(d.valued_at)}`,
      status: [
        ...bank,
        { label: d.steps[1].label, state: null, body: `
          <button class="link" id="rb-fetch">fetch everything</button>
          ${d.lacking.length ? `<button class="link" id="rb-lacking">${d.lacking.length} rate(s) the record lacks</button>` : ""}
          <span class="muted small">or closes of</span> <input type="date" id="rb-on">
          <button class="link" id="rb-discard" hidden></button>` },
        { label: d.steps[2].label, state: stale ? "gap" : null, tag: `${stale} past the limit`,
          body: quiet(`${d.age_days} days old · limit ${d.age_limit} days`) },
        { label: d.steps[3].label, state: null, body: `
          <button class="link" id="rb-write" disabled>write the ticked marks</button>
          <span class="muted small" id="rb-count">nothing ticked</span>` },
      ],
      why: [["Nothing happens until asked", "Nothing here leaves the machine or touches the "
                                            + "record until you ask it to."],
            ...d.steps.map((s) => [s.label, s.detail])],
      work: `
      ${/* WHAT THIS FORM CAN REPLACE, NOT WHAT NEEDS REPLACING. It read "N price(s) and M
            rate(s) due" whatever their ages, and some had been fetched minutes earlier by a
            reading on the Reconcile tab. The LIST is still the whole set —
            docs/prices.md: refresh the whole book or none of it — so the count that changed
            is the one in words. `stale` is the engine's, against rules.PRICE_AGE_LIMIT. */ ""}
      <div id="rb-fetched"></div>
      <pre id="rb-out" class="paste" hidden></pre>
      ${/* TAKE THE WHOLE COLUMN. Fetching the IG levels fills a row per
            contract at once and every one of them then had to be ticked by hand, a click per row
            to accept one machine answer. One per table, not one for the page: prices and rates
            are two populations that arrive by different routes and are finished at different
            moments — the contracts come from the broker while the shares are still being typed.

            IT ONLY EVER TICKS A COMPLETE ROW, and that is the rule surviving the convenience.
            A line without its figure, its date AND its source cannot be ticked one at a time,
            and a select-all that could tick one would be a way round `docs/prices.md` rule 1
            dressed up as a shortcut. The count beside it says what it took and what it left. */ ""}
      <div class="scroll" id="rb-form"><table>
        <thead><tr><th>${head("line")}</th><th class="num">${head("was")}</th>
          <th>${head("was_at")}</th><th class="num">${head("new")}</th><th>${head("new_at")}</th>
          <th>${head("source")}</th><th>${head("origin")}</th><th>${head("take")}</th></tr></thead>
        ${group("Prices", "price", d.prices.map(priceRow))}
        ${group("Rates", "rate", d.rates.map(rateRow))}
        ${d.lacking.length ? group("Rates the record lacks", "lacking", d.lacking.map(lackingRow)) : ""}
        ${group("IG accounts", "reading", d.readings.map(readingRow))}
      </table></div>`,
    });

    const rows = () => [...document.querySelectorAll("#main tr[data-kind]")];
    const fields = (tr) => Object.fromEntries(
      [...tr.querySelectorAll("[data-f]")].map((i) => [i.dataset.f, i.value.trim()]));

    /* COMPLETE MEANS EVERY FIELD, and the source counts. A price with a date and no source is a
       number nobody can ask about again, which is the half of `docs/prices.md`'s rule 1 that is
       easiest to skip. */
    const complete = (tr) => Object.values(fields(tr)).every((v) => v !== "");

    /* WHAT A HELD SWEEP REMEMBERS OF THE FORM: each row's tick, and what was typed into a field
       the sweep left open. A fetched figure is read-only and comes back from the reply itself. */
    const keep = () => {
      if (!PRICE_SWEEP) return;
      PRICE_SWEEP.rows = Object.fromEntries(rows().map((tr) => [
        `${tr.dataset.kind}:${tr.dataset.key}`,
        { ticked: tr.querySelector("[data-tick]").checked,
          typed: Object.fromEntries([...tr.querySelectorAll("[data-f]")]
            .filter((i) => !i.readOnly).map((i) => [i.dataset.f, i.value])) }]));
    };

    const retick = () => {
      let ticked = 0;
      /* AN ACCOUNT'S EQUITY TAKES THE LEVELS READ WITH IT. The book derives the account's figure
         from those levels, so writing the equity without them compares it with marks from some
         other time. While a reading is ticked, every level IG gave in this sweep is ticked and
         held; the server refuses a reading that arrives without one. */
      const reading = rows().some((tr) => tr.dataset.kind === "reading"
                                          && tr.querySelector("[data-tick]").checked);
      rows().forEach((tr) => {
        const box = tr.querySelector("[data-tick]");
        const ok = complete(tr);
        const held = reading && tr.dataset.ig === "1" && ok;
        box.disabled = !ok || held;
        if (!ok) box.checked = false;
        if (held) box.checked = true;
        if (box.checked) ticked += 1;
      });
      /* THE HEADER BOX FOLLOWS ITS COLUMN rather than driving it: on when every takeable row
         is taken, INDETERMINATE when some are, and disabled while none can be. A select-all
         that showed "on" over a half-ticked column would be the control lying about the thing
         it controls. */
      ["price", "rate", "lacking", "reading"].forEach((kind) => {
        const all = document.querySelector(`#main [data-all="${kind}"]`);
        if (!all) return;
        const boxes = rows().filter((tr) => tr.dataset.kind === kind)
                            .map((tr) => tr.querySelector("[data-tick]"));
        const takeable = boxes.filter((b) => !b.disabled);
        const on = takeable.filter((b) => b.checked);
        all.disabled = takeable.length === 0;
        all.checked = takeable.length > 0 && on.length === takeable.length;
        all.indeterminate = on.length > 0 && on.length < takeable.length;
      });
      $("#rb-write").disabled = ticked === 0;
      $("#rb-count").textContent = ticked ? `${ticked} line(s) ticked` : "nothing ticked";
      keep();
    };

    /* THE ONE THING data-all DOES, and it happens before retick() re-reads the column. It
       reaches only rows the form has already ENABLED, so an incomplete line stays untaken —
       select-all is a shortcut through the clicking, never through the rule.

       ON THE FORM, NOT ON #main (30 Sep 2026). #main outlives every panel, so each visit here
       added three more handlers that stayed behind: four visits in, a filter change on another
       page threw four errors, and a held sweep's ticks were one handler away from being
       recorded as empty. The form is redrawn with the panel, and its handlers with it. */
    const form = $("#rb-form");
    form.addEventListener("change", (e) => {
      const kind = e.target?.dataset?.all;
      if (!kind) return;
      rows().filter((tr) => tr.dataset.kind === kind)
            .map((tr) => tr.querySelector("[data-tick]"))
            .filter((b) => !b.disabled)
            .forEach((b) => { b.checked = e.target.checked; });
    });
    /* NOT WHILE THE SELECT-ALL BOX ITSELF IS THE TARGET. A checkbox fires `input` BEFORE
       `change`, and retick() treats the header box as a FOLLOWER of its column — so on `input`
       it overwrote the box the click had just set, and the `change` handler above then read the
       overwritten value. The control could only ever UNTICK: from an empty column it read
       `false` and did nothing, from a part-ticked one it read `false` and CLEARED the ticks,
       and from a full one it read `true` and left them. Found on the first live refresh
       on 8 Sep 2026. Row boxes and text fields still retick on `input` as before. */
    form.addEventListener("input", (e) => { if (!e.target?.dataset?.all) retick(); });
    form.addEventListener("change", retick);
    retick();

    /* ONE LINE INTO ONE ROW. `origin` is what the row wears afterwards — see priceRow. The
       fetch FILLS the form and never ticks it: every figure still has to be looked at and
       taken, which is the human check between a vendor's number and the record, and the
       contract feeds/ig.py has kept since it was written. */
    const fill = (key, kind, values, origin) => {
      const tr = rows().find((t) => t.dataset.key === key && t.dataset.kind === kind);
      if (!tr) return false;
      Object.entries(values).forEach(([f, v]) => {
        const input = tr.querySelector(`[data-f="${f}"]`);
        if (input) { input.value = v; input.title = v; }
      });
      tr.querySelectorAll("[data-f]").forEach((i) => { i.readOnly = true; });
      /* WHICH INSTANT is the feed's, not an input: a price typed into this form says neither,
         and the door refuses it. */
      tr.dataset.struck = values.struck || "";
      tr.dataset.at = values.at || "";
      tr.dataset.ig = values.ig ? "1" : "";
      /* A LIVE READ SAYS ITS TIME AND A CLOSE SAYS SO, beside the date the write
         sends: the two were the same date, and only the source told them apart. */
      const when = tr.querySelector("[data-when]");
      if (when) when.textContent = values.struck === "close" ? "close"
        : values.at ? clock(values.at) : "";
      const cell = tr.querySelector(".origin");
      if (cell) cell.innerHTML = `<span class="muted small">${esc(origin)}</span>`;
      return true;
    };

    /* A VENDOR'S FAILURE, ITS FIRST LINE. The rest is written for the terminal: a missing
       credentials file answers with the whole template to create. */
    const failed = (e) => esc(String(e || "").split("\n")[0]);

    /* A LINE THE SWEEP LEFT UNPRICED says so, with the reason on hover. A rate is then opened
       for typing — the door takes a rate without an instant; a price it would refuse. */
    const unpriced = (tr, why) => {
      const cell = tr.querySelector(".origin");
      if (cell) cell.innerHTML = `<span class="stale small" title="${esc(why)}">unpriced</span>`;
      if (tr.dataset.kind !== "rate") return;
      tr.querySelectorAll("[data-f]").forEach((i) => { i.readOnly = false; });
      const day = tr.querySelector('[data-f="as_of"]');
      if (!day.value) day.value = d.today;
    };

    /* THE IG ACCOUNTS, READ STRAIGHT AFTER THE LEVELS. Each is a whole reading, composed by
       feeds/refresh.py in the shape the observations door takes, so nothing here builds one:
       the row shows it, and the write sends it as it came. */
    let READINGS = {};

    /* A PAST DAY'S CLOSES — the quarter end fetched after it. Set by the fetch, read by the
       write: those closes are BANKED into the histories and the live marks are left alone
       (marks.bank_closes). A row left at today's date is refused by the door, not here. */
    let closeOf = null;

    /* ONE FILL, from a fetch or from a sweep held across a tab switch. `kept` is each row's
       tick and typed figures, laid back over the fill before the form is checked again. */
    const applySweep = (res, kept) => {
      const out = $("#rb-fetched");
      closeOf = res.on || null;
      /* THE RATES THE RECORD LACKS fill their own group and nothing else: no other line was
         asked for, so none is called unpriced. */
      const lacking = !!res.lacking;
      const notes = lacking ? [`<strong>closes of the dates the record lacks</strong>`]
        : closeOf
        ? [`<strong>closes of ${esc(closeOf)}</strong> — writing banks them into the history; `
           + `the live marks stay as they are`] : [];
      const why = {};

      /* EACH VENDOR REPORTS SEPARATELY, so one that is down is NAMED and the rest still
         lands. */
      const ig = res.ig_levels || {};
      if (lacking) {
        /* IG is not asked for a rate, so it is not reported. */
      } else if (ig.ok === false) {
        notes.push(`<span class="stale">IG: ${failed(ig.error)}</span>`);
      } else {
        const missing = [];
        (ig.rows || []).forEach((row) => {
          if (!row.priced) {
            missing.push(`${row.contract} (${row.status})`);
            why[row.contract] = row.status;
            return;
          }
          fill(row.contract, "price", {
            price: row.level, as_of: row.as_of, source: row.source,
            struck: row.struck, at: row.at, ig: true,
          }, row.origin || "fetched");
        });
        notes.push(`IG ${(ig.rows || []).length - missing.length} of ${(ig.rows || []).length}`);
        (ig.problems || []).forEach((p) => notes.push(`<span class="stale">${esc(p)}</span>`));
        if (missing.length) notes.push(
          `<span class="stale">no IG price for ${esc(missing.join(", "))} — chase these</span>`);
      }

      const tv = res.tv || {};
      if (tv.ok === false) {
        notes.push(`<span class="stale">TradingView: ${failed(tv.error)}</span>`);
      } else {
        (tv.prices || []).forEach((row) => {
          fill(row.ticker, "price",
                   { price: row.price, as_of: row.as_of, source: row.source,
                     struck: row.struck, at: row.at }, "fetched");
        });
        (tv.rates || []).forEach((row) => {
          if (lacking) {
            row.wanted.forEach((w) => fill(`${row.currency}@${w}`, "lacking",
              { rate: row.rate, as_of: row.as_of, source: row.source, struck: row.struck },
              "fetched"));
            return;
          }
          fill(row.currency, "rate",
                   { rate: row.rate, as_of: row.as_of, source: row.source,
                     struck: row.struck, at: row.at }, "fetched");
        });
        notes.push(`TradingView ${(tv.prices || []).length + (tv.rates || []).length}`);
        /* THE QUOTE SCREEN'S OWN ANSWER, when it is not `ok`: every line still trading
           waits on it, so one refusal is named once here as well as on each line. */
        if (tv.quote_screen && tv.quote_screen !== "ok") {
          notes.push(`<span class="stale">quote screen — ${esc(tv.quote_screen)}</span>`);
        }
        (tv.failed || []).forEach((f) => {
          why[f.wanted ? `${f.key}@${f.wanted}` : f.key] = f.why;
          notes.push(`<span class="stale">${esc(f.key)}: ${esc(f.why)}</span>`);
        });
      }
      READINGS = {};
      const eq = res.ig_equity;
      if (eq && eq.ok === false) {
        notes.push(`<span class="stale">IG accounts: ${failed(eq.error)}</span>`);
        (eq.rows || []).forEach((r) => { why[r.account] = eq.error; });
      } else if (eq) {
        (eq.readings || []).forEach((r) => {
          READINGS[r.account] = r;
          const read = (eq.rows || []).find((x) => x.account === r.account) || {};
          fill(r.account, "reading", {
            equity: money(r.equity), as_of: eq.read_at, source: read.source,
          }, "fetched");
        });
        notes.push(`IG accounts ${(eq.readings || []).length}, ${eq.gap_seconds}s after the levels`);
        (eq.refusals || []).forEach((x) => notes.push(`<span class="stale">${esc(x.text)}</span>`));
      }
      const figure = { price: "price", rate: "rate", lacking: "rate", reading: "equity" };
      rows().filter((tr) => lacking === (tr.dataset.kind === "lacking"))
        .filter((tr) => !fields(tr)[figure[tr.dataset.kind]])
        .forEach((tr) => unpriced(tr, why[tr.dataset.key] || "not returned by this sweep"));

      /* THE FLAG LISTS ARE CHECKED, NEVER CHANGED: a disagreement is named beside the result,
         in the feed's own words (feeds/tv.py:watchlist_check). */
      const wl = res.watchlist;
      if (wl && wl.ok === false) {
        notes.push(`<span class="stale">flag lists: ${failed(wl.error)}</span>`);
      } else if (wl) {
        (wl.findings || []).filter((f) => f.items.length).forEach((f) => notes.push(
          `<span class="stale">${esc(f.items.join(", "))} ${esc(f.said)}</span>`));
      }

      /* WHAT CAME BACK AND WHAT DID NOT, each vendor in turn: a filled row is
         its own receipt, so the line counts nothing else. */
      out.innerHTML = `<p class="muted">${notes.join(" · ")}</p>`;
      Object.entries(kept || {}).forEach(([id, k]) => {
        const tr = rows().find((t) => `${t.dataset.kind}:${t.dataset.key}` === id);
        if (!tr) return;
        Object.entries(k.typed).forEach(([f, v]) => {
          const input = tr.querySelector(`[data-f="${f}"]`);
          if (input && !input.readOnly) input.value = v;
        });
        tr.querySelector("[data-tick]").checked = k.ticked;
      });
      const drop = $("#rb-discard");
      drop.hidden = false;
      drop.textContent = `discard the sweep fetched ${PRICE_SWEEP.at}`;
      retick();
    };

    /* ONE FETCH, THREE ASKS: the whole sweep, one past day's closes, or the closes of the dated
       rates the record lacks — each one action (refresh-fetch-all), filling the one form. */
    const fetchSweep = async (button, ask, who) => {
      const out = $("#rb-fetched");
      button.disabled = true;
      out.innerHTML = `<p class="muted">asking ${who}…</p>`;
      try {
        const r = await fetch("/api/action/refresh-fetch-all", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ask) });
        const { body, raw } = await readJson(r);
        if (raw) { out.innerHTML = `<pre class="paste">${esc(raw)}</pre>`; return; }
        PRICE_SWEEP = { res: body.result || {}, on: ask.on || null, at: stampNow(), rows: {} };
        applySweep(PRICE_SWEEP.res, {});
      } finally {
        button.disabled = false;
      }
    };
    $("#rb-fetch").addEventListener("click", (e) => {
      const on = $("#rb-on").value || null;
      fetchSweep(e.currentTarget, on ? { on } : {}, "IG, then TradingView");
    });
    $("#rb-lacking")?.addEventListener("click", (e) =>
      fetchSweep(e.currentTarget, { lacking: true }, "TradingView"));

    $("#rb-discard").addEventListener("click", () => {
      PRICE_SWEEP = null;
      show("price-refresh");
    });

    $("#rb-write").addEventListener("click", async () => {
      const out = $("#rb-out"), button = $("#rb-write");
      const payload = { prices: [], rates: [], readings: [] };
      rows().forEach((tr) => {
        if (!tr.querySelector("[data-tick]").checked) return;
        const v = fields(tr);
        if (tr.dataset.kind === "reading") {
          payload.readings.push(READINGS[tr.dataset.key]);
        } else if (tr.dataset.kind === "lacking") {
          payload.rates.push({ currency: tr.dataset.currency, as_of: v.as_of, rate: v.rate,
                               source: v.source, struck: tr.dataset.struck });
        } else if (tr.dataset.kind === "price") {
          const was = d.prices.find((r) => r.line === tr.dataset.key);
          payload.prices.push({ ticker: tr.dataset.key, price: v.price,
                                currency: was.currency, as_of: v.as_of, source: v.source,
                                struck: tr.dataset.struck, at: tr.dataset.at });
        } else {
          payload.rates.push({ currency: tr.dataset.key, as_of: v.as_of, rate: v.rate,
                               source: v.source, struck: tr.dataset.struck });
        }
      });
      if (closeOf) payload.close_of = closeOf;
      button.disabled = true;
      out.hidden = false;
      out.textContent = closeOf ? `banking the closes of ${closeOf}…`
                                : "banking the outgoing marks, then writing…";
      try {
        const r = await fetch("/api/action/refresh-write-marks", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload) });
        const { body, raw } = await readJson(r);
        if (raw) { out.textContent = raw; return; }
        const res = body.result || body;
        /* A REFUSAL IS SHOWN IN FULL. Those messages name the rule that stopped the write —
           which line, and why — and that is the half worth reading. */
        if (res.ok === false) {
          out.textContent = `refused — nothing was written.\n\n${res.refused}`;
          return;
        }
        /* A WRITTEN REFRESH MOVES YOU ON. The bay is the machine and What
           changed is the report, so finishing here means reading there — and re-rendering the
           bay, which is what this used to do, left you looking at the empty form you had just
           emptied. A REFUSAL DOES NOT MOVE: the message names the line and the rule that
           stopped it, and navigating away from it would throw away the only thing worth reading.
           The receipt travels; see LAST_REFRESH. */
        PRICE_SWEEP = null;
        $("#rb-discard").hidden = true;
        if (closeOf) {
          out.textContent = `Banked the closes of ${(res.days || []).join(", ") || res.day}: `
            + `${res.banked.prices} price(s), `
            + `${res.banked.rates} rate(s)${res.already ? `, ${res.already} already on file` : ""}.`
            + ((res.superseded || []).length ? `\n\n${res.superseded.join("\n")}` : "");
          return;
        }
        LAST_REFRESH = res;
        out.textContent = `Written. ${res.prices} price(s), ${res.rates} rate(s), `
                        + `${res.readings} IG reading(s).`;
        openPanel("what-changed");
      } catch (e) {
        out.textContent = `write failed — ${e.message}`;
      } finally {
        button.disabled = false;
      }
    });

    if (PRICE_SWEEP) {
      $("#rb-on").value = PRICE_SWEEP.on || "";
      applySweep(PRICE_SWEEP.res, heldRows);
    }
  },
};

/* Filter controls for the reading panels. Each one re-asks the SERVER — the narrowing is the
   engine's, and re-filtering an already-fetched array in the browser would be a second answer
   to a question engine.py answers. */
function wireStage5(name, fresh = true) {
  const reload = async (path) => {
    const d = await get(path);
    $("#main").innerHTML = RENDER[name](d);
    wireStage5(name, false);
  };
  /* THE FILTERS HELD FOR THIS PAGE are asked for again on arrival — only then, and only when
     they differ from what was drawn, so the redraw that answers them cannot ask again. */
  const hold = (ids) => {
    HELD_FILTERS[name] = Object.fromEntries(ids.map((id) => [id, $(`#${id}`).value]));
  };
  const restore = (ids, go) => {
    const held = HELD_FILTERS[name];
    const els = ids.map((id) => $(`#${id}`));
    if (!fresh || !held || els.some((el) => !el)) return;
    if (els.every((el) => el.value === (held[el.id] ?? ""))) return;
    els.forEach((el) => { el.value = held[el.id] ?? ""; });
    go();
  };
  if (name === "holdings") {
    const by = $("#h-by"), acct = $("#h-acct"), ids = ["h-by", "h-acct"];
    const go = () => {
      hold(ids);
      reload(`/api/holdings?by=${encodeURIComponent(by.value)}`
        + `&account=${encodeURIComponent(acct.value)}`);
    };
    if (by) by.addEventListener("change", go);
    if (acct) acct.addEventListener("change", go);
    const clear = $("#h-clear");
    if (clear) clear.addEventListener("click", () => {
      delete HELD_FILTERS[name];
      reload("/api/holdings");
    });
    restore(ids, go);
  }
  if (name === "round-trips") {
    const tk = $("#rt-ticker"), acct = $("#rt-acct"), co = $("#rt-company");
    const from = $("#rt-from"), to = $("#rt-to"), clear = $("#rt-clear");
    const ids = ["rt-acct", "rt-company", "rt-ticker", "rt-from", "rt-to"];
    const go = () => {
      hold(ids);
      reload(`/api/round-trips?ticker=${encodeURIComponent(tk.value)}`
        + `&company=${encodeURIComponent(co ? co.value : "")}`
        + `&account=${encodeURIComponent(acct.value)}`
        + `&start=${encodeURIComponent(from ? from.value : "")}`
        + `&end=${encodeURIComponent(to ? to.value : "")}`);
    };
    if (tk) tk.addEventListener("change", go);
    if (acct) acct.addEventListener("change", go);
    /* A COMPANY CHOSEN STARTS ITS TICKER AFRESH, and the page comes back with that company's
       codes in the Ticker box (14 Oct 2026). */
    if (co) co.addEventListener("change", () => { tk.value = ""; go(); });
    /* `change` and not `input`: a date input fires on every keystroke while a year is being
       typed, and each one would be a request for a range nobody meant. */
    if (from) from.addEventListener("change", go);
    if (to) to.addEventListener("change", go);
    if (clear) clear.addEventListener("click", () => {
      delete HELD_FILTERS[name];
      reload("/api/round-trips");
    });
    restore(ids, go);
  }
}

/* A PANEL WITH A WIDE TABLE TAKES THE WINDOW; everything else keeps the reading measure.
   DERIVED FROM THE RENDERED PANEL, never from a list of names: `.scroll` is the wrapper the
   shared wide-table helper already emits, so a new wide table widens its page by existing. A
   list here would be a second statement of which panels are wide and would drift on the first
   addition — the defect this codebase keeps deleting things for.

   WATCHED, NOT CALLED, and that is the second version. Calling it after each render meant
   finding every place that writes to #main, and I missed one immediately: the panels in
   RENDER_LATE return early from show(), so the Bench kept the previous panel's width — click
   Holdings then Bench and the form was 1,616px wide with the `data` class still on the body.
   An observer cannot be forgotten by the next person to add a render path. */
/* HOLDINGS -> THE LEDGER, filtered to one company. Delegated from #main rather than bound per
   row, because the table is re-rendered on every grouping change and per-row listeners would be
   rebound each time — or worse, silently lost. */
/* THE COMBOBOX. Delegated from the document, so a field rendered by a later drawItem() works
   without rewiring — the bench rebuilds its form constantly and per-input listeners would be
   lost or doubled. */
function wireCombos() {
  if (document.body.dataset.combosWired) return;
  document.body.dataset.combosWired = "1";

  const listFor = (inp) => inp.parentElement.querySelector(".combo-list");
  const choicesOf = (inp) => { try { return JSON.parse(inp.dataset.choices || "[]"); }
                               catch (e) { return []; } };

  const render = (inp) => {
    const ul = listFor(inp);
    const q = inp.value.trim().toLowerCase();
    /* STARTS-WITH FIRST, then contains. Typing "AB" should offer ABC before something that
       merely has those letters in the middle — the first match is the one Enter takes. */
    const all = choicesOf(inp);
    const hits = [...all.filter((c) => c.toLowerCase().startsWith(q)),
                  ...all.filter((c) => !c.toLowerCase().startsWith(q)
                                       && c.toLowerCase().includes(q))].slice(0, 12);
    ul.innerHTML = hits.map((c, i) =>
      `<li role="option" data-v="${esc(c)}"${i === 0 ? ' class="on"' : ""}>${esc(c)}</li>`).join("");
    ul.hidden = !hits.length;
    inp.setAttribute("aria-expanded", String(!ul.hidden));
  };

  const pick = (inp, value) => {
    inp.value = value;
    listFor(inp).hidden = true;
    inp.setAttribute("aria-expanded", "false");
    /* The form saves on `change`, and setting .value in script does not fire one. */
    inp.dispatchEvent(new Event("change", { bubbles: true }));
  };

  document.addEventListener("input", (e) => {
    if (e.target.matches(".combo input[data-choices]")) render(e.target);
  });
  document.addEventListener("focusin", (e) => {
    if (e.target.matches(".combo input[data-choices]")) render(e.target);
  });
  document.addEventListener("focusout", (e) => {
    if (!e.target.matches(".combo input[data-choices]")) return;
    const inp = e.target;
    /* A CLICK ON AN OPTION IS A BLUR FIRST. Hiding immediately would cancel the pick, so the
       list closes on the next tick, after mousedown has landed. */
    setTimeout(() => {
      const ul = listFor(inp);
      if (ul) ul.hidden = true;
      /* A CLOSED FIELD RESOLVES WHAT YOU TYPED, and only clears if it cannot.
         The first version cleared anything that was not an exact match, which punished the
         search it had just been given: type "sipp", see the one account it can be, tab away,
         lose it. So — exact match wins (correcting the case, because an account name typed in
         lower case plainly means that account); otherwise, if the filter leaves exactly ONE
         candidate, that is what you meant; anything else clears, because a half-typed account
         name that LOOKED accepted is the thing a closed vocabulary exists to prevent.
         Ambiguity clears too: two candidates is not a choice, it is a guess. */
      if (!inp.dataset.closed) return;
      const typed = inp.value.trim();
      if (!typed) return;
      const all = choicesOf(inp);
      const low = typed.toLowerCase();
      const exact = all.find((c) => c.toLowerCase() === low);
      const near = all.filter((c) => c.toLowerCase().includes(low));
      const hit = exact || (near.length === 1 ? near[0] : "");
      if (hit !== inp.value) {
        inp.value = hit;
        /* Only when it actually moved: a change event re-saves the item and redraws the form,
           which is not something a blur that changed nothing should cause. */
        inp.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }, 150);
  });
  document.addEventListener("mousedown", (e) => {
    const li = e.target.closest(".combo-list li");
    if (!li) return;
    e.preventDefault();
    pick(li.closest(".combo").querySelector("input"), li.dataset.v);
  });
  document.addEventListener("keydown", (e) => {
    const inp = e.target;
    if (!inp.matches || !inp.matches(".combo input[data-choices]")) return;
    const ul = listFor(inp);
    if (ul.hidden) { if (e.key === "ArrowDown") render(inp); return; }
    const items = [...ul.querySelectorAll("li")];
    const at = items.findIndex((li) => li.classList.contains("on"));
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = e.key === "ArrowDown" ? Math.min(at + 1, items.length - 1)
                                         : Math.max(at - 1, 0);
      items.forEach((li) => li.classList.remove("on"));
      if (items[next]) { items[next].classList.add("on"); items[next].scrollIntoView({block: "nearest"}); }
    } else if (e.key === "Enter" && items[at]) {
      e.preventDefault();
      pick(inp, items[at].dataset.v);
    } else if (e.key === "Escape") {
      ul.hidden = true;
      inp.setAttribute("aria-expanded", "false");
    }
  });
}

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

/* Draw a sweep into the Bench, and remember it.
   `data-wide` is the house signal that this is DATA rather than prose — widenForData() watches
   for it and takes the measure off the page. A swept row carries a generated CSV line, which is
   the widest thing on the desk and the one thing there is no point clipping to 44rem. */
async function showSweep(result) {
  LAST_SWEEP = result;
  const out = $("#actout"), view = $("#actview");
  if (!view) return;
  out.hidden = true;
  view.hidden = false;
  view.setAttribute("data-wide", "");

  /* ASK WHAT HAS HAPPENED TO THESE EVENTS. The snapshot supplies the events; the server
     supplies their state. Without this a row carried to the bench offered "work it" again on
     the way back, and a row already WRITTEN stayed on the sweep as though it were missing. */
  const refs = ["opens", "closes", "costs", "capital", "setups"]
    .flatMap((k) => (result[k] || []).map((r) => r.ref)).filter(Boolean);
  SWEEP_STATUS = {};
  if (refs.length) {
    try {
      const r = await fetch("/api/sweep-status", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ refs }) });
      const { body } = await readJson(r);
      SWEEP_STATUS = body || {};
    } catch (e) { console.error(e); }   /* a status we could not fetch shows as unknown, not as new */
  }
  view.innerHTML = ACTION_VIEW["ig-events"](result);
}

function wireIgEvents() {
  const main = $("#main");
  if (!main || main.dataset.igWired) return;
  main.dataset.igWired = "1";
  main.addEventListener("click", async (e) => {
    const open = e.target.closest("[data-setup]");
    if (open) {
      const ev = IG_EVENTS[open.dataset.setup];
      const form = main.querySelector(`[data-setup-form="${CSS.escape(open.dataset.setup)}"]`);
      if (!ev || !form) { open.textContent = "sweep again — this event is stale"; return; }
      if (!form.innerHTML) form.innerHTML = setupForm(ev);
      form.hidden = !form.hidden;
      return;
    }
    const go = e.target.closest("[data-setup-go]");
    if (go) {
      const ev = IG_EVENTS[go.dataset.setupGo];
      if (!ev) { go.textContent = "sweep again — this event is stale"; return; }
      await toBench(go, setupEvent(ev, go.closest("[data-setup-form]")), "ig-setup-to-bench");
      return;
    }
    const b = e.target.closest("[data-ig-event]");
    if (!b) return;
    const ev = IG_EVENTS[b.dataset.igEvent];
    if (!ev) { b.textContent = "sweep again — this event is stale"; return; }
    await toBench(b, ev);
  });
  /* THE CONTRACT FOLLOWS THE CODE until it is typed itself: the code's root and the epic's
     month. A company not in the register asks for its sector and region. */
  main.addEventListener("input", (e) => {
    const form = e.target.closest("[data-setup-form]");
    if (!form) return;
    const name = e.target.dataset.su;
    const ev = IG_EVENTS[form.dataset.setupForm] || {};
    const contract = form.querySelector('[data-su="contract"]');
    if (name === "contract") contract.dataset.typed = "1";
    if (name === "code" && !contract.dataset.typed) {
      contract.value = e.target.value.trim().replace(/ SB$/i, "").toUpperCase() + (ev.suffix || "");
    }
    if (name === "company") {
      const known = ((BENCH.forms.securities || []).find((s) => s.name === "company") || {}).choices || [];
      form.querySelectorAll("[data-su-new]").forEach((l) => {
        l.hidden = !e.target.value.trim() || known.includes(e.target.value.trim());
      });
    }
  });
}

/* A FIRST BET ON A CONTRACT THE BOOK DOES NOT HAVE, set up with its line, its company when that
   is new, and its contract: typed once here, and carried to the bench as one item with the trade. */
function setupForm(ev) {
  const choices = (t, f) => ((BENCH.forms[t] || []).find((s) => s.name === f) || {}).choices || [];
  const options = (id, xs) => `<datalist id="${id}">${xs.map((x) =>
    `<option value="${esc(x)}">`).join("")}</datalist>`;
  const box = (name, value = "", extra = "", shown = "") => `<label class="f"${shown}><span>${
    head(name)}</span><input data-su="${name}" value="${esc(value)}"${extra}></label>`;
  const pick = (name, xs, chosen = "") => `<label class="f"><span>${head(name)}</span>
    <select data-su="${name}"><option></option>${xs.map((x) =>
      `<option${x === chosen ? " selected" : ""}>${esc(x)}</option>`).join("")}</select></label>`;
  return `<div class="grid">${box("code")}${box("company", "", ' list="su-company"')}
      ${pick("currency", choices("trades", "cur"))}${box("tv_symbol")}
      ${box("sector", "", ' list="su-sector"', " data-su-new hidden")}${
        box("region", "", ' list="su-region"', " data-su-new hidden")}
      ${box("contract", ev.suffix || "")}${box("epic", ev.epic || "", " readonly")}
      ${pick("funding", choices("contracts", "funding"), ev.funding)}</div>
    ${options("su-company", choices("securities", "company"))}${options("su-sector",
      choices("issuers", "sector"))}${options("su-region", choices("issuers", "region"))}
    <p><button class="link" data-setup-go="${esc(ev.ref)}">work it</button></p>`;
}

/* The rows a set-up carries, each in its table's own column order: a line not in the register,
   a company not in it, and always the contract, which is what made the bet unreadable. */
function setupEvent(ev, form) {
  const got = (k) => ((form.querySelector(`[data-su="${k}"]`) || {}).value || "").trim();
  const choices = (t, f) => ((BENCH.forms[t] || []).find((s) => s.name === f) || {}).choices || [];
  const row = (table, v) => ({ table, values: Object.fromEntries(
    (BENCH.forms[table] || []).map((s) => [s.name, v[s.name] ?? ""])) });
  const code = got("code"), company = got("company"), contract = got("contract");
  const rows = [];
  if (!choices("trades", "ticker").includes(code)) {
    rows.push(row("securities", { code, company, kind: "spread bet", currency: got("currency"),
      tv_symbol: got("tv_symbol") }));
  }
  if (!choices("securities", "company").includes(company)) {
    rows.push(row("issuers", { company, sector: got("sector"), region: got("region") }));
  }
  rows.push(row("contracts", { contract, epic: got("epic"), funding: got("funding"), code }));
  return { ...ev, values: { ...ev.values, ticker: code, contract }, with: rows };
}

async function toBench(b, ev, action = "ig-event-to-bench") {
  b.disabled = true;
  b.textContent = "opening…";
  try {
    const r = await fetch(`/api/action/${action}`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ event: ev }) });
    const { body: d, raw } = await readJson(r);
    if (raw) { b.textContent = "failed — see the log"; console.error(raw); return; }
    /* The action's own answer, not this function's opinion of it: for_event() refuses a row
       whose shape does not match its table, and that refusal must reach the screen. */
    const res = d.result || d;
    if (res.ok === false) { b.textContent = `refused — ${res.error || "see the log"}`; return; }
    b.textContent = res.blocked && res.blocked.length
      ? `on the bench — ${res.blocked.join(", ")} still owed`
      : "on the bench";
    /* THE LIST ABOVE REDRAWS, the sweep with it from its snapshot: the item was made and the
       list went on without it, so the page read as stuck (12 Oct 2026). */
    await show("bench");
  } catch (err) {
    b.textContent = "failed — see the log";
    console.error(err);
  }
}

function wireTradeLinks() {
  const main = $("#main");
  if (!main || main.dataset.tradesWired) return;
  main.dataset.tradesWired = "1";
  /* ANY PANEL MAY SEND YOU TO ANOTHER, delegated from #main for the same reason the trades
     link is: a panel that re-renders on a filter change would lose a per-element listener. */
  main.addEventListener("click", (e) => {
    const go = e.target.closest("[data-panel]");
    if (go) { openPanel(go.dataset.panel); return; }
  });
  main.addEventListener("click", (e) => {
    const b = e.target.closest("[data-trades]");
    if (!b) return;
    PENDING_COMPANY = b.dataset.trades;
    openPanel("trades");
  });
}

function widenForData() {
  /* `.scroll` IS THE USUAL MARKER and it is not the only one. Trades is data-shaped and
     renders no table — it is a list of events, so it never matched, and it kept the 62rem
     reading measure while carrying six columns of figures AND a note: wasted screen space, and
     the account column wrapping onto four lines inside it. A panel can opt in with `data-wide`
     instead: still DERIVED from what was rendered, still not a list of panel names in here. */
  const main = $("#main");
  if (!main) return;
  /* A LOADING PANEL HAS NO OPINION ABOUT ITS WIDTH, or the Dashboard renders in jerks.
     Every navigation writes "reading the store…" into #main first, and the observer
     read that empty state as "no table here" and narrowed the page — then widened it again a
     beat later when the real content arrived. Going from one wide panel to another, the layout
     therefore COLLAPSED TO 992 AND SPRANG BACK TO 1,616 for no reason: two reflows, both
     avoidable, and the jerk was the page measuring a message rather than a panel.
     Hold the current width until there is something to measure. */
  if (main.querySelector(".loading")) return;
  document.body.classList.toggle("data", !!main.querySelector(".scroll, [data-wide]"));
  markOverflow();
}

/* A HEADING PRESSED: the next state of its column's sort, then the rows put in that order, each
   with the rows that belong under it (its detail). Delegated from #main, as the trades link is,
   so a table drawn again keeps it. */
function wireSorting() {
  const main = $("#main");
  if (!main || main.dataset.sortWired) return;
  main.dataset.sortWired = "1";
  const press = (th) => {
    const tbl = th.closest("table[data-sorts]");
    const t = tbl && SORTED.get(Number(tbl.dataset.sorts));
    if (!t) return;
    const c = th.dataset.col, held = SORTS[t.key];
    const figures = th.classList.contains("num");
    const first = figures ? "down" : "up", second = figures ? "up" : "down";
    const dir = !held || held.col !== c ? first : held.dir === first ? second : null;
    if (dir) SORTS[t.key] = { col: c, dir }; else delete SORTS[t.key];
    const body = tbl.tBodies[0];
    const groups = new Map();
    let cur = null;
    [...body.rows].forEach((tr) => {
      if (tr.dataset.i !== undefined) { cur = [tr]; groups.set(Number(tr.dataset.i), cur); }
      else if (cur) cur.push(tr);
    });
    sortOrder(t.rows, t.key).forEach((n) => (groups.get(n) || []).forEach((tr) => body.appendChild(tr)));
    tbl.querySelectorAll("th[data-col]").forEach((h) => {
      const s = SORTS[t.key] && SORTS[t.key].col === h.dataset.col ? SORTS[t.key].dir : "";
      h.setAttribute("aria-sort", s === "up" ? "ascending" : s === "down" ? "descending" : "none");
      h.querySelector(".arrow")?.remove();
      if (s) h.insertAdjacentHTML("beforeend",
        `<span class="arrow" aria-hidden="true">${s === "up" ? "▲" : "▼"}</span>`);
    });
  };
  main.addEventListener("click", (e) => {
    const th = e.target.closest("th[data-col]");
    if (th) press(th);
  });
  main.addEventListener("keydown", (e) => {
    const th = e.target.closest && e.target.closest("th[data-col]");
    if (th && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); press(th); }
  });
}

/* TABLES THAT READ AS ONE GRID (`align` in table()): What Changed's two blocks, Performance's
   quarters and year. Each shared column takes the widest of its fellows, so a figure sits under
   the one above it; a table's columns past the others' (the year's own) keep their own width. */
function alignTables() {
  const groups = {};
  document.querySelectorAll("#main table[data-align]").forEach((t) =>
    (groups[t.dataset.align] = groups[t.dataset.align] || []).push(t));
  Object.values(groups).forEach((ts) => {
    if (ts.length < 2) return;
    const heads = ts.map((t) => [...t.tHead.rows[0].cells]);
    const upto = Math.min(...ts.map((t) => Number(t.dataset.alignCols)));
    heads.forEach((h) => h.slice(0, upto).forEach((c) => { c.style.width = ""; }));
    for (let i = 0; i < upto; i++) {
      const w = Math.max(...heads.map((h) => h[i].getBoundingClientRect().width));
      heads.forEach((h) => { h[i].style.width = `${w}px`; });
    }
  });
}

/* A BOX THAT SCROLLS SIDEWAYS SAYS SO, for the stylesheet's edge on its pinned first column.
   And a table no longer on the page lets go of its rows. */
function markOverflow() {
  alignTables();
  const live = new Set([...document.querySelectorAll("#main table[data-sorts]")]
    .map((t) => Number(t.dataset.sorts)));
  [...SORTED.keys()].forEach((k) => { if (!live.has(k)) SORTED.delete(k); });
  document.querySelectorAll("#main .scroll").forEach((b) =>
    b.classList.toggle("overflows", b.scrollWidth > b.clientWidth + 1));
}
window.addEventListener("resize", markOverflow);

function watchForData() {
  const main = $("#main");
  if (!main) return;
  new MutationObserver(widenForData).observe(main, { childList: true, subtree: true });
  widenForData();
  wireTradeLinks();
  wireSorting();
  wireIgEvents();
  wireCombos();
  wireDetailLinks();
}

/* ONE PAINT, NOT FOUR: the Dashboard's content had popped in at delayed intervals.

   The cold start ran: fetch state → paint the freshness line → paint the tabs → paint "reading
   the store…" → fetch the panel → paint the content. FIVE steps, four of them visible, each one
   after an await. Nothing was slow — the whole thing is about 135ms — but it ARRIVED IN FOUR
   INSTALMENTS, which is what makes a fast page feel messy.

   So the shell now waits for the panel and everything appears together. It costs nothing: the
   state call returns in 4ms and the panel in ~130, and the page was not usable until the panel
   landed anyway. */
function paintPanel(p) {
  PAGE_TITLE = p.title;
  HEADS = p.heads || {};
  PRECISION = p.precision || PRECISION;
  if (RENDER_LATE[p.name]) return RENDER_LATE[p.name](p.data);
  const render = RENDER[p.name];
  $("#main").innerHTML = render
    ? render(p.data)
    : `<h2>${esc(p.title)}</h2><pre class="error">${esc(JSON.stringify(p.data, null, 2))}</pre>`;
  wireStage5(p.name);
}

async function show(name) {
  /* THE PLACEHOLDER IS DELAYED, NOT IMMEDIATE. Writing "reading the store…" the instant a tab is
     clicked guarantees two paints for every switch — the message, then the panel — and at 130ms
     the message is a flicker rather than information. Held back 180ms, it appears only when the
     store really is slow, which is the only time it says anything. Until then the previous panel
     stays up, which also keeps the page from collapsing to an empty measure on the way. */
  const slow = setTimeout(() => {
    $("#main").innerHTML = `<p class="loading">reading the store…</p>`;
  }, 180);
  /* THE HEADER IS RE-READ ON EVERY SWITCH. It was drawn once at boot,
     so a bench commit wrote the store while the line above it went on quoting the stamp it had
     at page load.

     A SWITCH, NOT A WRITE, is the hook, for the reason book() keys its cache on the store's
     mtime rather than trusting its callers: the three desk writers are not the only way the
     record moves, and a hand edit, a git pull, a checkout or a revert leaves no handler to
     hang this on. Fetched ALONGSIDE the panel rather than before it, so it costs no latency,
     and failure is swallowed — a header that could not refresh must not take the panel down. */
  const fresh = get("/api/state").catch(() => null);
  try {
    const p = await get(`/api/panel/${encodeURIComponent(name)}`);
    clearTimeout(slow);
    await paintPanel(p);
  } catch (e) {
    clearTimeout(slow);
    if (e.signIn) { drawSignIn(); return; }
    if (e.unreachable) { drawUnreachable(); return; }
    /* The record's own refusal comes through verbatim — it names the exact file that was
       missing, which is the useful half. */
    $("#main").innerHTML = `<h2>The record refused to load</h2><pre class="error">${esc(e.message)}</pre>`;
  }
  const s = await fresh;
  if (s) { takeState(s); drawFreshness(s.freshness); otherVersion(s); }
}

/* ---------------------------------------------------------------------------------------
   SIGNING IN — the hosted desk only, drawn when its door answers 401.

   A PASSKEY, NOT A PASSWORD. The browser keeps a key for the book's passkey_domain and signs the
   door's challenge with Face ID or Touch ID; desk/auth.py checks it. A device is enrolled once,
   with a code issued on the Mac's Access page. The reader's level is the door's to apply.

   The browser's passkey calls take and give binary, and the door speaks JSON, so the byte
   fields cross as base64url — the encoding WebAuthn's own JSON form uses.
   --------------------------------------------------------------------------------------- */
const b64u = {
  dec: (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")
                                  + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0)).buffer,
  enc: (b) => btoa(String.fromCharCode(...new Uint8Array(b)))
                .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""),
};

/* THE HOSTED PAGE AND THE MAC MUST BE ONE VERSION. The page is published when the owner chooses,
   and the Mac's desk moves at every merge; a page drawing data from a different version would
   be new figures in old screens, the mixture engine.source_stale() exists to name. So it
   draws nothing but the two versions until it is published again. */
const PAGE_VERSION = document.querySelector('meta[name="desk-version"]')?.content;

function otherVersion(s) {
  if (!s.remote || s.version === PAGE_VERSION) return false;
  document.body.classList.add("bare");
  $("#tabs").innerHTML = "";
  /* A MAC RUNNING OLDER CODE THAN IS ON DISK works its version out partly from what it loaded
     before, and no publish can match that, so it is told to restart before anything else. */
  const fix = s.freshness?.source_stale
    ? "the Mac's desk is running older code than is on disk: restart it there first\n" +
      "(its restart button, or launchctl kickstart -k gui/$UID/org.portfusion.desk)"
    : "on the Mac:  portfusion desk --publish";
  $("#main").innerHTML = `<h2>This page and the Mac's desk are different versions</h2>
    <pre class="error">this page   ${esc(PAGE_VERSION)}\nthe Mac     ${esc(s.version)}\n
${esc(fix)}</pre>`;
  return true;
}

function drawUnreachable() {
  document.body.classList.add("bare");
  $("#tabs").innerHTML = "";
  $("#fresh").innerHTML = "";
  $("#main").innerHTML = `<h2>The Mac isn't answering</h2>
    <pre class="error">asleep, offline, or the tunnel is off</pre>`;
}

/* THE FRONT DOOR: the field with the book's mark beside the form. The mark is the header's
   own, copied into the field, so it is still drawn once, from the book's brand. */
function drawSignIn(why) {
  document.body.classList.add("bare");
  $("#tabs").innerHTML = "";
  $("#fresh").innerHTML = "";
  const web = document.querySelector(".lockup svg")?.outerHTML || "";
  $("#main").innerHTML = `<section class="signin">
    <div class="signin-field">${web}<h1>The desk</h1></div>
    <div class="signin-form">
      <button class="primary" id="signin">Sign in with your passkey</button>
      <label class="f"><span>Enrol code</span><input id="enrol-code" autocomplete="off" size="10"></label>
      <button class="secondary" id="enrol">Enrol this device</button>
      <pre id="signin-out" class="error"${why ? "" : " hidden"}>${esc(why || "")}</pre>
    </div>
  </section>`;
  $("#signin").addEventListener("click", () =>
    passkey("/auth/options", "/auth/verify", "get"));
  $("#enrol").addEventListener("click", () =>
    passkey("/auth/enrol/options", "/auth/enrol/verify", "create",
            { code: $("#enrol-code").value }));
}

async function passkey(ask, answer, verb, body) {
  const out = $("#signin-out");
  const post = (url, data) => fetch(url, { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify(data || {}) })
    .then(readJson);
  try {
    const o = await post(ask, body);
    if (!o.ok) throw new Error(o.body?.detail || o.raw);
    const opts = o.body;
    opts.challenge = b64u.dec(opts.challenge);
    if (opts.user) opts.user.id = b64u.dec(opts.user.id);
    for (const c of [...(opts.excludeCredentials || []), ...(opts.allowCredentials || [])]) {
      c.id = b64u.dec(c.id);
    }
    const cred = await navigator.credentials[verb]({ publicKey: opts });
    const r = cred.response;
    const response = { clientDataJSON: b64u.enc(r.clientDataJSON) };
    if (r.attestationObject) {
      response.attestationObject = b64u.enc(r.attestationObject);
      response.transports = r.getTransports ? r.getTransports() : [];
    } else {
      response.authenticatorData = b64u.enc(r.authenticatorData);
      response.signature = b64u.enc(r.signature);
      if (r.userHandle) response.userHandle = b64u.enc(r.userHandle);
    }
    const v = await post(answer, { id: cred.id, rawId: b64u.enc(cred.rawId), type: cred.type,
                                   response, clientExtensionResults: {} });
    if (!v.ok) throw new Error(v.body?.detail || v.raw);
    location.reload();
  } catch (e) {
    out.hidden = false;
    out.textContent = e.message;
  }
}

(async function start() {
  try {
    watchForData();
    const s = await get("/api/state");
    takeState(s);
    if (otherVersion(s)) { drawFreshness(s.freshness); return; }
    let active = location.hash.slice(1) || s.panels[0]?.name;
    if (!s.panels.some((p) => p.name === active)) active = s.panels[0]?.name;
    /* THE ADDRESS NAMES THE PAGE, AND THE BROWSER'S BACK AND FORWARD MOVE IT (14 Oct 2026).
       A tab writes its name into the address, so every page visited is a step in the browser's
       history — but nothing listened when Back stepped the address back: from Holdings' trades
       link, Back left Trades on screen under an address naming Holdings, which Safari showed as
       its picture of Holdings flicking back to Trades. Now a step of history shows the page it
       names, its filters as they were left (HELD_FILTERS) and where it was scrolled to; a page
       opened by a tab or a link starts at its top. `shown` is the page on screen, so the address
       change a tab makes itself is recognised and not shown twice. */
    let shown = active;
    const scrolled = {};
    const leave = () => { scrolled[shown] = window.scrollY; };
    const pick = (n) => {
      leave(); shown = n;
      location.hash = n; drawTabs(s.panels, n, pick);
      show(n).then(() => { if (shown === n) window.scrollTo(0, 0); });
    };
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    window.addEventListener("hashchange", async () => {
      const n = location.hash.slice(1);
      if (n === shown || !s.panels.some((p) => p.name === n)) return;
      leave(); shown = n;
      drawTabs(s.panels, n, pick);
      await show(n);
      if (shown === n) window.scrollTo(0, scrolled[n] || 0);
    });
    if (!active) { drawFreshness(s.freshness); return; }

    /* FETCH BEFORE PAINTING ANYTHING. The three draws below are one frame's work; splitting them
       around an await is what put them on screen a beat apart. */
    location.hash = active;
    let first = null;
    try { first = await get(`/api/panel/${encodeURIComponent(active)}`); } catch (e) { /* below */ }
    drawFreshness(s.freshness);
    drawTabs(s.panels, active, pick);
    if (first) await paintPanel(first);
    else await show(active);          // let show() render the failure in its own words
  } catch (e) {
    if (e.signIn) { drawSignIn(); return; }
    if (e.unreachable) { drawUnreachable(); return; }
    $("#main").innerHTML = `<h2>The desk could not start</h2><pre class="error">${esc(e.message)}</pre>`;
  }
})();
