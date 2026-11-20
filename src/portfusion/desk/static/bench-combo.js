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
