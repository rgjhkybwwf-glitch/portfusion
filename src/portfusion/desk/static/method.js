/* METHOD: the page's draw. */

Object.assign(DRAW, {
  /* METHOD — how the numbers are made, then the line and the door, as the engine's record states
     them. Read down as prose, so a definition list rather than a table. */
  method(d) {
    return page({
      scope: "how the numbers are made, and how a row gets in",
      work: d.sections.map((s) => `<h2>${esc(s.heading)}</h2><dl class="method">${s.rows.map((r) =>
        `<dt>${esc(r.topic)}</dt><dd>${esc(r.text)}</dd>`).join("")}</dl>`).join(""),
    });
  },
});
