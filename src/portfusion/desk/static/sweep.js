/* THE IG SWEEP, worked from the Bench. */

/* The last sweep's events, by deal id. A button names a ref rather than carrying a whole row
   through the DOM — the same reason `collect()` rebuilds a bench row from named inputs. */
let IG_EVENTS = {};

/* THE SWEEP SURVIVES LEAVING THE TAB. Losing it would cost another 30-day call to the broker.
   Held here and re-rendered on return, which also repopulates IG_EVENTS, since the renderer
   fills it as it draws. */
let LAST_SWEEP = null;
/* What has happened to those events SINCE. Fetched every time the sweep is drawn, never cached
   with it: the sweep is a snapshot and this is the half that moves. */
let SWEEP_STATUS = {};

/* HOW EACH BROKER ANSWER IS SHOWN. Rendering only — every figure arrives already computed by
   feeds/ig.py, and working one out here would be a second calculation of something the feed already
   answered. A key with no renderer falls back to JSON, which is honest about being unfinished
   rather than hiding the result. */
/* THE ACTION STRIP: a page's standing broker buttons. */
async function wireActions(panelName) {
  /* INLINE ACTIONS ARE NOT PANEL BUTTONS. "Work this event" belongs to one row of a sweep
     and is rendered there; listed here it would be a button with nothing to work.

     EVERY OTHER ACTION OF THE PAGE IS A STANDING BUTTON. The restart is the shell's own
     ("desk"), drawn by the rail, and no page's list needs trimming. */
  const acts = Object.values(await loadActions())
    .filter((a) => a.panel === panelName && !a.inline);
  /* THE BUTTON AND WHAT IT REACHES, and no paragraph: what it does is in the page's fold. */
  $("#acts").innerHTML = acts.map((a) =>
    `<p><button class="link" data-act="${esc(a.name)}">
       ${esc(a.label)}</button>` + badges(a.name) + `</p>`).join("");

  $("#acts").querySelectorAll("[data-act]").forEach((b) =>
    b.addEventListener("click", async () => {
      const out = $("#actout"), view = $("#actview");
      view.hidden = true; view.innerHTML = "";
      out.hidden = false; out.textContent = "asking the broker…";
      try {
        const { result, error } = await runAction(b.dataset.act);
        if (error) { out.textContent = error; return; }

        /* THE ANSWER IS FIGURES, NOT JSON. A renderer per action, and JSON only where there is
           none, so a NEW action still shows its result rather than nothing while its view is
           written. */
        const draw = ACTION_VIEW[b.dataset.act];
        if (!draw) { out.textContent = JSON.stringify(result, null, 2); return; }
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

       A BUTTON PER EVENT, and deliberately not one button for the sweep.
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
        /* THE STATUS SITS BESIDE THE EVENT, NOT UNDER IT. `.swept` gives the row a fixed shape —
           description left, status right, neither wrapping into the other. */
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

/* Draw a sweep into the Bench, and remember it.
   `data-wide` is the house signal that this is DATA rather than prose — widenForData() watches
   for it and takes the measure off the page. A swept row carries a generated CSV line, which is
   the widest thing on the desk and the one thing there is no point clipping. */
async function showSweep(result) {
  LAST_SWEEP = result;
  const out = $("#actout"), view = $("#actview");
  if (!view) return;
  out.hidden = true;
  view.hidden = false;
  view.setAttribute("data-wide", "");

  /* ASK WHAT HAS HAPPENED TO THESE EVENTS. The snapshot supplies the events; the server
     supplies their state. Without it a carried row would offer "work it" again, and a written
     one read as missing. */
  const refs = ["opens", "closes", "costs", "capital", "setups"]
    .flatMap((k) => (result[k] || []).map((r) => r.ref)).filter(Boolean);
  SWEEP_STATUS = {};
  if (refs.length) {
    const { ok, body, error } = await post("/api/sweep-status", { refs });
    /* A STATUS WE COULD NOT FETCH shows as unknown, not as new. */
    if (ok) SWEEP_STATUS = body || {};
    else console.error(error);
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
  /* THE CONTRACT FOLLOWS THE TICKER until it is typed itself: the ticker's root and the epic's
     month. A company not in the register asks for its sector and region. */
  main.addEventListener("input", (e) => {
    const form = e.target.closest("[data-setup-form]");
    if (!form) return;
    const name = e.target.dataset.su;
    const ev = IG_EVENTS[form.dataset.setupForm] || {};
    const contract = form.querySelector('[data-su="contract"]');
    if (name === "contract") contract.dataset.typed = "1";
    if (name === "ticker" && !contract.dataset.typed) {
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
  return `<div class="grid">${box("ticker")}${box("company", "", ' list="su-company"')}
      ${pick("currency", choices("buys", "cur"))}${box("symbol")}${box("points_per_unit")}${
        box("shares_per_unit")}
      ${box("sector", "", ' list="su-sector"', " data-su-new hidden")}${
        box("region", "", ' list="su-region"', " data-su-new hidden")}
      ${box("contract", ev.suffix || "")}${box("epic", ev.epic || "", " readonly")}
      ${pick("funding", choices("contracts", "funding"), ev.funding)}</div>
    ${options("su-company", choices("securities", "company"))}${options("su-sector",
      choices("companies", "sector"))}${options("su-region", choices("companies", "region"))}
    <p><button class="link" data-setup-go="${esc(ev.ref)}">work it</button></p>`;
}

/* The rows a set-up carries, each in its table's own column order: a line not in the register,
   a company not in it, and always the contract, which is what made the bet unreadable. */
function setupEvent(ev, form) {
  const got = (k) => ((form.querySelector(`[data-su="${k}"]`) || {}).value || "").trim();
  const choices = (t, f) => ((BENCH.forms[t] || []).find((s) => s.name === f) || {}).choices || [];
  const row = (table, v) => ({ table, values: Object.fromEntries(
    (BENCH.forms[table] || []).map((s) => [s.name, v[s.name] ?? ""])) });
  const ticker = got("ticker"), company = got("company"), contract = got("contract");
  const rows = [];
  if (!choices("buys", "ticker").includes(ticker)) {
    rows.push(row("securities", { ticker, company, held_as: "spread bet", currency: got("currency"),
      symbol: got("symbol"), points_per_unit: got("points_per_unit"),
      shares_per_unit: got("shares_per_unit") }));
  }
  if (!choices("securities", "company").includes(company)) {
    rows.push(row("companies", { company, sector: got("sector"), region: got("region") }));
  }
  rows.push(row("contracts", { contract, epic: got("epic"), funding: got("funding"), ticker }));
  return { ...ev, values: { ...ev.values, ticker, contract }, with: rows };
}

async function toBench(b, ev, action = "ig-event-to-bench") {
  b.disabled = true;
  b.textContent = "opening…";
  try {
    /* The action's own answer, not this function's opinion of it: for_event() refuses a row
       whose shape does not match its table, and that refusal must reach the screen. */
    const { result: res, error, refused } = await runAction(action, { event: ev });
    if (error) {
      b.textContent = `${refused ? "refused" : "failed"} — ${error.split("\n")[0]}`;
      console.error(error);
      return;
    }
    b.textContent = res.blocked && res.blocked.length
      ? `on the bench — ${res.blocked.join(", ")} still owed`
      : "on the bench";
    /* THE LIST ABOVE REDRAWS, the sweep with it from its snapshot. */
    await show("bench");
  } catch (err) {
    b.textContent = "failed — see the log";
    console.error(err);
  }
}
