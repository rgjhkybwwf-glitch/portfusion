/* The shell, and the desk's entry: it loads last, after every file desk/bundle.py's SCRIPTS
   names before it, and starts the desk. It draws whatever the server registers — it has no list
   of panels in it, because a list here would be a second place to update every time a panel is
   added.

   IT FORMATS, IT DOES NOT CALCULATE. Every number arrives from the engine already derived; the
   only thing the desk's script decides is how many decimal places it wears. A percentage
   computed here would be a second calculation of something the engine already answers. */

/* RESTART — the button for "it does not show".

   A running desk serves what it IMPORTED at startup, so a change to the engine or a panel is
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
     older engine and renders new markup over missing data. */
  const source = !f.source_stale ? "" :
    ` · <span class="stale" title="${esc((f.source_files || []).join("\n"))}">` +
    `running older code — ${esc((f.source_files || []).join(", "))}` +
    `${f.source_count > (f.source_files || []).length
        ? ` +${f.source_count - f.source_files.length} more` : ""}` +
    ` changed since it started; restart it</span>`;
  /* THE PRICE DATE. Book.valued_at() is the newest mark, the same answer the Dashboard heads
     its glance with. The Price Refresh tab sits directly below this line, so it needs no link
     here. */
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

function drawTabs(panels, active, onPick) {
  const tab = (p) =>
    `<button${p.name === active ? ` aria-current="page"` : ""} data-name="${esc(p.name)}">` +
    `${esc(p.title)}</button>`;
  /* THE PAGES APART FROM THE WORK sit below a rule, off the thread, with no heading: Method and
     Access on the Mac (`APART` on the panel module). The rule alone sets them apart. */
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

/* HOLDINGS -> THE LEDGER, filtered to one company. Delegated from #main rather than bound per
   row, because the table is re-rendered on every grouping change and per-row listeners would be
   rebound each time — or worse, silently lost. */
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

/* A PAGE TAKES THE WINDOW BY WHAT IT RENDERED, never by a list of panel names, which would drift
   on the first addition: `data-wide`, which page() puts on every tab, or a `.scroll`, the
   wide-table helper's wrapper. A page with neither (an error, the sign-in) keeps the measure.

   WATCHED, NOT CALLED, since a call per render must find every path that writes to #main.
   An observer cannot be forgotten by the next person to add a render path. */
function widenForData() {
  const main = $("#main");
  if (!main) return;
  /* A LOADING PANEL HAS NO OPINION ABOUT ITS WIDTH, or the Dashboard renders in jerks.
     Every navigation writes "reading the store…" into #main first, which is no measure of a
     panel. Hold the current width until there is something to measure. */
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

/* ONE PAINT, NOT FOUR: the shell waits for the panel, so everything appears together. */
function paintPanel(p) {
  PAGE_TITLE = p.title;
  HEADS = p.heads || {};
  PRECISION = p.precision || PRECISION;
  $("#main").innerHTML = DRAW[p.name]
    ? DRAW[p.name](p.data)
    : `<h2>${esc(p.title)}</h2><pre class="error">${esc(JSON.stringify(p.data, null, 2))}</pre>`;
  return WIRE[p.name]?.(p.data, false);
}

/* A PAGE THAT COULD NOT BE READ: the hosted door asking who you are, no Mac behind it, or the
   record's own refusal, verbatim — it names the exact file that was missing, which is the useful
   half. */
function drawFailure(e) {
  if (e.signIn) return drawSignIn();
  if (e.unreachable) return drawUnreachable();
  $("#main").innerHTML = `<h2>The record refused to load</h2><pre class="error">${esc(e.message)}</pre>`;
}

async function show(name) {
  /* THE PLACEHOLDER IS DELAYED, NOT IMMEDIATE. Writing "reading the store…" the instant a tab is
     clicked guarantees two paints for every switch — the message, then the panel — and at 130ms
     the message is a flicker rather than information. Held back 180ms, it appears only when the
     store really is slow, which is the only time it says anything. Until then the previous panel
     stays up, which also keeps the page from collapsing to an empty measure on the way. */
  const asked = ++ASKED;
  const slow = setTimeout(() => {
    if (asked === ASKED) $("#main").innerHTML = `<p class="loading">reading the store…</p>`;
  }, 180);
  /* THE HEADER IS RE-READ ON EVERY SWITCH.

     A SWITCH, NOT A WRITE, is the hook, for the reason book() keys its cache on the store's
     mtime rather than trusting its callers: the three desk writers are not the only way the
     record moves, and a hand edit, a git pull, a checkout or a revert leaves no handler to
     hang this on. Fetched ALONGSIDE the panel rather than before it, so it costs no latency,
     and failure is swallowed — a header that could not refresh must not take the panel down. */
  const fresh = get("/api/state").catch(() => null);
  try {
    const p = await get(`/api/panel/${encodeURIComponent(name)}`);
    clearTimeout(slow);
    if (asked === ASKED) await paintPanel(p);
  } catch (e) {
    clearTimeout(slow);
    if (asked === ASKED) drawFailure(e);
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
  try {
    const o = await post(ask, body || {});
    if (o.error) throw new Error(o.error);
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
    if (v.error) throw new Error(v.error);
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
    /* THE ADDRESS NAMES THE PAGE, AND THE BROWSER'S BACK AND FORWARD MOVE IT.
       A tab writes its name into the address, so every page visited is a step in the browser's
       history, and a step of history shows the page it names, its filters as they were left
       (HELD_FILTERS) and where it was scrolled to; a page opened by a tab or a link starts at its
       top. `shown` is the page on screen, so the address change a tab makes itself is recognised
       and not shown twice. */
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
       around an await would put them on screen a beat apart. */
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
