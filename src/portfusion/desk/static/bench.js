/* ---------------------------------------------------------------------------------------
   THE BENCH. An event, from evidence to an approved row.

   Every value here is typed, picked or approved by the owner; the screen's job is to make the
   wrong value hard — closed vocabularies as dropdowns, a live word count against the cap, and
   the three statement-grade limbs as fields rather than a paragraph to remember.
   --------------------------------------------------------------------------------------- */

let BENCH = null;          // the panel payload: forms, limbs, documents
let OPEN_ID = null;        // which item is being worked
let DRAWN = 0;             // the revision of it on screen, sent with every save
let REVIEWING = false;     // the review before writing is on screen
let BENCH_GONE = null;     // an item opened from a list that was out of date: its title
/* Whether the document preview is open, remembered ACROSS a drawItem() rebuild. Not read off
   `#preview-pane`, which every re-render empties. */
let PREVIEW_OPEN = false;

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
         SENT ONLY WHEN THE FILE HAS ONE: an empty `modified=` is no number, and is refused. */
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
    const { body: it, error } = await post("/api/bench", { origin: "document", title: landed[0],
                                                           document: { name: landed[0] } });
    if (error) notOpened(error);
    else openItem(it.id);
  }
}

/* AN ITEM THAT COULD NOT BE OPENED SAYS WHY, in the drop-off's box under the list. */
function notOpened(error) {
  const out = $("#dropout");
  if (!out) return;
  out.hidden = false;
  out.textContent = `not opened — ${error}`;
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

/* ONE SAVE AT A TIME. Each save waits for the one before it, and so carries the revision that
   one drew. */
let SAVING = Promise.resolve();

function benchSave(patch) {
  const run = SAVING.then(() => saveNow(patch));
  SAVING = run.catch(() => {});
  return run;
}

/* WHAT THE OWNER IS TYPING SURVIVES A REDRAW. A field not yet left has fired no change, so its
   text is in no save, and a redraw would wipe it. It is put back, with the caret, in the field
   of the same name. */
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
     would write its old rows over a newer save. The server refuses a save from an older
     revision; the item is drawn again as it now is, and the change is made again on that. */
  const { body: d, status, error } = await post(`/api/bench/${OPEN_ID}`,
                                                { ...patch, revision: DRAWN }, "PUT");
  if (status === 409) {
    const d = await get(`/api/bench/${OPEN_ID}`);
    keepingTheField(() => drawItem(d));
    $("#item").insertAdjacentHTML("afterbegin",
      `<ul class="items"><li class="gap"><span class="tag">changed</span>drawn again; make the change again</li></ul>`);
    return d;
  }
  /* A SAVE REFUSED FOR ANY OTHER REASON SAYS SO. */
  if (error) {
    $("#item").insertAdjacentHTML("afterbegin",
      `<ul class="items"><li class="gap"><span class="tag">not saved</span>${esc(error)}</li></ul>`);
    return null;
  }
  keepingTheField(() => drawItem(d));
  return d;
}

function field(spec, value, quote, drafted) {
  const v = value == null ? "" : String(value);
  const req = spec.required ? ` <span class="req">required</span>` : "";
  let input;
  if (spec.choices) {
    /* EVERY CHOICE FIELD IS SEARCHABLE, not only the ticker. `evidence` is long and `acct` can
       hold names that differ only in their last word (an ISA against a SIPP at the same broker,
       say), and picking from a menu you cannot type into is the slow way to reach either.

       CLOSED STILL MEANS CLOSED. The difference is not whether you may type — it is whether
       what you typed is allowed to stand: a closed field that does not resolve to a listed
       value is CLEARED when you leave it, so the only value that can survive is one from the
       list. Typing is a way of finding the option, not a way past it. record/schema.py refuses a bad
       value on load either way; this stops it being entered in the first place. An OPEN field
       keeps whatever you type, because a first-ever purchase of a new company must not be
       refused by its own ticker being unknown.

       AND IT IS A REAL COMBOBOX, NOT A <datalist>. A datalist is the correct HTML and is not
       reliably a SEARCH: Safari does not filter one as you type the way Chrome does, so a few
       dozen tickers become a long menu to scroll. This filters on every keystroke, in every
       browser. */
    input = `<div class="combo"><input data-f="${esc(spec.name)}" value="${esc(v)}"` +
      ` autocomplete="off" role="combobox" aria-expanded="false"` +
      (spec.closed ? ` data-closed="1"` : "") +
      ` data-choices="${esc(JSON.stringify(spec.choices))}">` +
      `<ul class="combo-list" hidden></ul></div>`;
    } else if (spec.long) {
    /* PROSE DOES NOT FIT ON ONE LINE. The drafted note runs to a sentence or three, and a
       one-line input makes it a thing to scroll, not read — which is exactly backwards for the
       one cell the machine wrote and the owner has to check. */
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
      <strong>First mark</strong></div><dl class="detail">${["mark_key", "price", "currency", "as_of",
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
     so its reading is the stock alone and Reconcile adds the account's cash. */
  const rdg = it.reading;
  const num = (v) => v === "" || v == null ? "—" : money(Number(v));
  const readingBlock = !rdg ? "" : `
    <h2>The account's reading</h2>
    ${figures([["Account", esc(rdg.account || "—")], ["Stock", num(rdg.positions)]].concat(
      rdg.cash === "" && rdg.total === "" ? []
        : [["Cash", num(rdg.cash)], ["Total", num(rdg.total)]]))}
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
    /* A ROW THE OWNER HAS EDITED IS THEIRS. A re-read replaces machine rows, so an edit drops
       `machine`. */
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
      rows: [...collect(), { table: "buys", adjustment: { from: "", to: "" }, values: {} }] })));
  $("#item").querySelectorAll("[data-delrow]").forEach((b) =>
    b.addEventListener("click", () => benchSave({
      rows: collect().filter((_, i) => i !== +b.dataset.delrow) })));
  // Withdraw takes the document with it; discard leaves it on the workbench, as its API route
  // promises. The two are side by side because the choice between them is the choice the
  // operator actually has.
  const wd = $("#withdraw");
  if (wd) wd.addEventListener("click", async () => {
    const why = prompt("Why is this not needed? Recorded on the archived item.");
    if (why === null) return;
    const name = encodeURIComponent(it.document.name);
    const { error } = await post(`/api/inbox/${name}?why=${encodeURIComponent(why)}`, undefined,
                                 "DELETE");
    if (error) { alert(error); return; }
    OPEN_ID = null;
    await show("bench");
  });
  $("#discard").addEventListener("click", async () => {
    const { error } = await post(`/api/bench/${OPEN_ID}`, undefined, "DELETE");
    if (error) { alert(error); return; }
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
    const { body, error } = await post(`/api/bench/${OPEN_ID}/read`);
    if (!error) drawItem(body);
    else $("#docbody").innerHTML = `<pre class="error">${esc(error)}</pre>`;
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
     an EMPTY #preview-pane, so the document is drawn into it again after each one.
     A preview you have to reopen every time the form changes is one you stop using. */
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
     it 404s, and the Bench is drawn again, naming it. */
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

/* ONE THING ON THE PAGE AT A TIME. While an item or the review is open, the list steps aside. */
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

/* THE REVIEW BEFORE WRITING. Every ready item, each row in the desk's words, its reasons and its
   checks, and ONE PRESS PER ITEM: each event keeps its own approval, and a press that wrote them
   all would be a background pass in all but name. */
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
      + ((d.retires || []).length ? `<dt>${head("retires")}</dt><dd>${esc(d.retires.join(", "))}</dd>` : "")
      + ((d.renumbers || []).length ? `<dt>${head("renumbers")}</dt><dd>${esc(d.renumbers.join("; "))}</dd>` : "");
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
    const { error } = await post(`/api/bench/${b.dataset.write}/commit`);
    const out = $(`[data-out="${b.dataset.write}"]`);
    out.hidden = false;
    if (!error) {
      out.textContent = "written";
      setTimeout(() => show("bench"), 1200);
    } else {
      out.textContent = "not written\n\n" + error;
      b.disabled = false;
    }
  }));
}

Object.assign(DRAW, {
  bench(d) {
    /* BACK TO THE LIST IS BACK TO ONE COLUMN. `wide` is the item's two-column layout and
       nothing on the list needs it; left on, it stretched the list across the window. */
    PREVIEW_OPEN = false;
    document.body.classList.remove("wide");
    BENCH = d;
    /* AN EMPTY LIST IS NOT DRAWN: the status line already counts it. */
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

    /* EVERY ROUTE IN STARTS HERE: a dropped document, `+ new item` and a swept IG event. */
    const ready = d.items.filter((i) => i.ready).length;
    return page({
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
          <pre class="error" id="noteout" aria-live="polite" hidden></pre>` : ""}
        <div class="drop" id="drop">
          <strong>Drop a contract note or statement here</strong>
          <span class="muted">It waits under Documents and opens on the Bench.
            ${a.extensions.map(esc).join(" · ")} · up to ${mb} MB</span>
          <span class="muted"><button class="link" id="pickbtn">or choose a file</button></span>
          <input type="file" id="pick" multiple hidden>
        </div>
        <pre class="error" id="dropout" aria-live="polite" hidden></pre>
        <h2>Ask the broker</h2>
        <div id="acts"></div>
        <div id="actview" hidden></div>
        <pre id="actout" class="paste" aria-live="polite" hidden></pre>
        </div>
        <section id="item"></section>`,
      why: d.why,
    });
  },
});

Object.assign(WIRE, {
  async bench(d) {
    BENCH_GONE = null;
    wireDrop();
    await wireActions("bench");
    const rv = $("#review");
    if (rv) rv.addEventListener("click", () => reviewItems());

    $("#newitem").addEventListener("click", async () => {
      const { body: it, error } = await post("/api/bench", { title: "untitled" });
      if (error) { notOpened(error); return; }
      /* Re-render the panel so the list stops saying "nothing on the bench" while an item is
         open beneath it, then re-open what was just created. */
      OPEN_ID = it.id;
      await show("bench");
    });
    $("#main").querySelectorAll("[data-open]").forEach((b) =>
      b.addEventListener("click", () => openItem(b.dataset.open)));
    $("#main").querySelectorAll("[data-doc]").forEach((b) =>
      b.addEventListener("click", async () => {
        const { body: it, error } = await post("/api/bench", { origin: "document",
          title: b.dataset.doc, document: { name: b.dataset.doc } });
        if (error) { notOpened(error); return; }
        OPEN_ID = it.id;
        await show("bench");
      }));

    /* ONE PRESS WRITES ONE NOTE'S ROWS; a refusal stays on the page, saying why. */
    $("#main").querySelectorAll("[data-note]").forEach((b) =>
      b.addEventListener("click", async () => {
        b.disabled = true;
        const { error } = await post(`/api/bench/notes/${encodeURIComponent(b.dataset.note)}`);
        if (!error) { await show("bench"); return; }
        const out = $("#noteout");
        out.hidden = false;
        out.textContent = error;
        b.disabled = false;
      }));

    /* THE ITEM BEING WORKED COMES BACK OPEN, unless it has left the bench
       — written, discarded or withdrawn — and then there is nothing to reopen. */
    if (OPEN_ID && d.items.some((i) => i.id === OPEN_ID)) openItem(OPEN_ID);
    else OPEN_ID = null;
    if (REVIEWING) reviewItems();
  },
});

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
         Exact match wins (correcting the case, because an account name typed in lower case
         plainly means that account); otherwise, if the filter leaves exactly ONE candidate, that
         is what you meant; anything else clears, because a half-typed account name that LOOKED
         accepted is the thing a closed vocabulary exists to prevent.
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
