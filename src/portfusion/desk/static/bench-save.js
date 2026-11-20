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
