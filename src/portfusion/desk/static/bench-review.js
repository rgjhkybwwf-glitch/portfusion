/* WHAT COMES NEXT, once an item's checks are green: the next item still owed, in the bench's
   order after this one, or the review once every item is ready. */
function nextStep(d) {
  if (!d.approved) return "";
  const all = d.bench || [], at = all.findIndex((i) => i.id === d.item.id);
  const owed = [...all.slice(at + 1), ...all.slice(0, Math.max(at, 0))].find((i) => !i.ready);
  return owed
    ? `<p>${goButton(`data-open="${esc(owed.id)}" id="nextitem"`, `next item: ${esc(owed.title)}`)}</p>`
    : `<p>${goButton(`id="reviewall"`, "review and write")}</p>`;
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
    const priced = firstMarks(it);
    const whys = ["why_entered", "why_exited"].filter((w) => (said[w] || "").trim())
      .map((w) => `<dt>${head(w)}</dt><dd>${esc(said[w])}</dd>`).join("")
      + ((d.retires || []).length ? `<dt>${head("retires")}</dt><dd>${esc(d.retires.join(", "))}</dd>` : "")
      + ((d.renumbers || []).length ? `<dt>${head("renumbers")}</dt><dd>${esc(d.renumbers.join("; "))}</dd>` : "");
    return `<section class="review-item" data-item="${esc(it.id)}">
      <div class="row-head"><h2>${esc(it.title)}</h2></div>
      ${rows}${priced}${whys ? `<dl class="detail">${whys}</dl>` : ""}
      <ul class="items gates">${d.gates.map((g) =>
        `<li class="ok"><span class="tag">ok</span><strong>${esc(g.label || g.name)}</strong></li>`).join("")}</ul>
      <p>${actButton(`data-write="${esc(it.id)}"`, rdg
        ? "file the document and write the reading" : "write to the record")}</p>
      <pre class="paste" data-out="${esc(it.id)}" hidden></pre></section>`;
  };
  $("#item").innerHTML = `
    <div class="row-head">${goButton(`id="back"`, "back to the Bench")}</div>
    ${ready.map(card).join("")}
    ${owed.length ? `<h2>Still owed</h2><ul class="items">${owed.map((i) => {
      const open = goButton(`data-open="${esc(i.id)}"`, esc(i.title));
      return `<li class="note"><span class="tag">${esc(i.state)}</span>${open} <span class="muted">${
        esc(i.blocked_by.join(", "))}</span></li>`;
    }).join("")}</ul>` : ""}`;
  $("#back").addEventListener("click", () => { REVIEWING = false; show("bench"); });
  $("#item").querySelectorAll("[data-open]").forEach((b) =>
    b.addEventListener("click", () => openItem(b.dataset.open)));
  /* ASKED IN THE PAGE FIRST (`benchAsk()`); a write refused says why there, and nothing is written. */
  $("#item").querySelectorAll("[data-write]").forEach((b) => b.addEventListener("click", async () => {
    const id = b.dataset.write;
    const written = await benchAsk("Write this to the record? It cannot be undone from the desk.",
      actButton(`data-ask-write`, "write to the record"),
      async () => (await post(`/api/bench/${id}/commit`)).error);
    if (!written) return;
    b.disabled = true;
    const out = $(`[data-out="${id}"]`);
    out.hidden = false;
    out.textContent = "written";
    setTimeout(() => show("bench"), 1200);
  }));
}
