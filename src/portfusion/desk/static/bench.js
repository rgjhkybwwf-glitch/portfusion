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
let BENCH_GONE = null;     // an item gone from the list or discarded from it: its tag and title
/* Whether the document preview is open, remembered ACROSS a drawItem() rebuild. Not read off
   `#preview-pane`, which every re-render empties. */
let PREVIEW_OPEN = false;

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
      `${goButton(`data-open="${esc(i.id)}"`, esc(i.title))} ` +
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
      `${actButton(`data-doc="${esc(f.name)}"`, "work it")}</li>`).join("")
      : "";

    /* A PUBLISHED RESEARCH NOTE THE BOOK HAS NO ROW FOR, and the codes it would be filed under:
       one press each. */
    const notes = (d.notes || []).map((n) =>
      `<li class="gap"><span class="tag">published</span>${esc(n.ref)} · ${esc(day(n.date))} · ` +
      `${esc(n.company)} · ${esc(n.kind)} → ${esc(n.codes.join(", "))} ` +
      `${actButton(`data-note="${esc(n.ref)}"`, "record")}</li>`).join("");

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
          ${actButton(`id="newitem"`, "+ new item")}${ready
            ? ` ${goButton(`id="review"`, `review and write (${ready})`)}` : ""}` },
        { label: "Inbox", body: quiet(`${d.documents.length} document(s) waiting`) },
        { label: "Research", body: quiet(`${(d.notes || []).length} note(s) waiting`) },
      ],
      work: `
        <div id="bench-list">${BENCH_GONE ? `<ul class="items"><li class="gap"><span class="tag">${
          esc(BENCH_GONE.tag)}</span>${esc(BENCH_GONE.title)} ${BENCH_GONE.tag === "discarded"
          ? "was discarded" : "is no longer on the bench"}</li></ul>` : ""}
        ${items ? `<h2>On the bench</h2><ul class="items">${items}</ul>` : ""}
        ${docs ? `<h2>Documents waiting</h2><ul class="items">${docs}</ul>` : ""}
        ${notes ? `<h2>Research notes waiting</h2><ul class="items">${notes}</ul>
          <pre class="error" id="noteout" aria-live="polite" hidden></pre>` : ""}
        <div class="drop" id="drop">
          <strong>Drop a contract note or statement here</strong>
          <span class="muted">It waits under Documents and opens on the Bench.
            ${a.extensions.map(esc).join(" · ")} · up to ${mb} MB</span>
          <span class="muted">${actButton(`id="pickbtn"`, "or choose a file")}</span>
          <input type="file" id="pick" multiple hidden>
        </div>
        <pre class="error" id="dropout" aria-live="polite" hidden></pre>
        <h2>Ask the broker</h2>
        <div id="acts"></div>
        <div id="actview" hidden></div>
        <pre id="actout" class="paste" aria-live="polite" hidden></pre>
        </div>
        <section id="item"></section>
        <dialog id="bench-ask" aria-labelledby="ask-words"></dialog>`,
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
