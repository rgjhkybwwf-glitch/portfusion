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
