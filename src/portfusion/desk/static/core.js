/* THE DESK'S CORE: formats, fetch, and the state the pages share. It loads first; the order
   is desk/bundle.py's SCRIPTS. */

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
   /100; a raw float prints 0.49887600000000004. */
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
       SO IS A 500 WITH NOTHING IN IT: Netlify answers that, not a 502, when there is no tunnel
       at all. The desk's own 500 always says "Internal Server Error", so a crash on the Mac is
       not mistaken for it. */
    e.unreachable = ([502, 504].includes(r.status) && !body.detail)
                    || (r.status === 500 && !text.trim());
    throw e;
  }
  return body;
}

/* A RESPONSE THAT IS NOT JSON MUST NOT BECOME A BROWSER MESSAGE.
   `await r.json()` on a 500 whose body is the plain string "Internal Server Error" throws, and
   Safari words that as "SyntaxError: The string did not match the expected pattern." — which
   says nothing about brokers, credentials or what to do. */
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
/* SWITCH TO A PANEL FROM ANYWHERE. Every panel link calls it. Clicking the real tab rather than
   calling show() keeps the tab strip's own selected state correct — it is the tab that owns it. */
function openPanel(name) {
  const tab = [...document.querySelectorAll(".tabs button")].find((x) => x.dataset.name === name);
  if (tab) tab.click();
}

/* Renderers, one per panel name. A panel the shell has no renderer for still LISTS — it shows
   its raw payload rather than vanishing, so a half-built panel is visible while it is built. */
let RENDER_LATE = {};

/* The open tab's own name, set as each panel is painted, so `page()` titles the page with the
   word the tab strip already uses rather than a second spelling of it. */
let PAGE_TITLE = "";
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
/* Set by a "trades" link (Holdings, Round Trips) and taken once by Trades, which then HOLDS the
   company as a filter chosen there: the box shows it and "clear filters" sits beside it, so it
   narrows nothing out of sight. */
let PENDING_COMPANY = null;
/* THE RECEIPT FOR A REFRESH JUST WRITTEN, carried from the Price Refresh to What Changed and shown
   once. Same idiom and same reason as PENDING_COMPANY above: a completed write moves you to the
   panel that says what it did, and its own one-line summary would otherwise be lost on the way.
   What the destination cannot state for itself is the BANKING — how many outgoing marks went to
   their histories — so that is the half worth carrying. CONSUMED ONCE: a receipt that stuck
   would still be claiming a refresh a week later. */
let LAST_REFRESH = null;

/* EACH PAGE'S FILTERS, kept while the desk is open: a switch redraws a panel from the record,
   and its filters would reset with it. By panel, then by the control's id. */
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
