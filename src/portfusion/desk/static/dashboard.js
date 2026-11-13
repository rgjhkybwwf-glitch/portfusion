/* THE DASHBOARD: the page's draw. */

Object.assign(DRAW, {
  dashboard(d) {
    /* WHAT NEEDS ATTENTION, THEN WHAT WAS CHECKED: the record's notes, in the engine's words and
       in the order `portfusion record` prints them, under the problems and gaps. A tag's space
       and no dot, so the text lines up with the items above it. */
    const items = [...d.attention, ...(PANELS.has("bench") ? d.bench || [] : [])].map((a) =>
      `<li class="${esc(a.level)}"><span class="tag">${esc(a.level)}</span>${esc(a.text)}
        ${a.panel ? panelLink(a.panel) : ""}</li>`
    ).join("") + (d.checks || []).map((c) =>
      `<li class="check"><span class="tag"></span>${esc(c)}</li>`).join("");

    const p = d.prices, y = d.ytd;
    /* THE DATE THE FIGURES STAND AT.
       Book.valued_at() is the newest mark — not today, because a figure is only as current as
       the price behind it. The SPREAD is on the Prices step, which is what makes this a date
       rather than an instant.

       NO BASIS PILL: the label names what each figure is, and the panel still hands over its
       basis, held to Book.HEADLINE by tests/test_figures.py. */
    /* THE BAND TAKES THE FIGURES THE PANEL LEADS WITH, each
       with the indented parts that follow it in the engine's order; the rest stay in the list
       below. Which figures lead is the panel's `lead`, never a choice made here. */
    const band = [], rest = [];
    let under = null;
    for (const f of d.figures) {
      if (f.indent && under) { under.parts.push(f); continue; }
      under = f.lead ? { ...f, parts: [] } : null;
      if (under) band.push(under); else rest.push(f);
    }
    const field = `<div class="field-figures">${band.map((f) => `
      <div class="field-figure"><span class="label">${esc(f.label)}</span>
        <span class="numeral">${fmt(f.value, f.kind)}</span>
        ${f.parts.map((x) => `<span class="part">${esc(x.label)} ${fmt(x.value, x.kind)}</span>`)
          .join("")}</div>`).join("")}</div>`;
    return page({
      scope: `where the book stands, as at ${day(d.valued_at)}`,
      field,
      status: [{ label: "Prices", body: `${quiet(`${p.age_days} days old · ${p.marks} marks
        · newest ${esc(day(p.newest))} · oldest ${esc(day(p.oldest))} · spread ${p.spread_days}d`)}
        ${panelLink("price-refresh", "run a refresh")}` },
        { label: d.ytd_name, body: quiet(`from ${esc(day(y.first_day))} · MWR on NAV${
          y.frozen ? "" : " · not frozen"}`) },
        ...(d.report ? [{ label: "Report", body: `${reportLink(d.report)}
          ${panelLink("reports", "every report")}` }] : [])],
      /* THE FIGURES BESIDE WHAT NEEDS ATTENTION, so the page is one screen. */
      work: `<div class="glance">
        ${figures(rest.map((f) => [f.label, `${fmt(f.value, f.kind)}${f.panel
          ? ` ${panelLink(f.panel, `see ${PANELS.get(f.panel)}`)}` : ""}`, f.indent ? "indent" : ""]))}
        <section><h2>Needs attention</h2><ul class="items">${items}</ul></section></div>`,
    });
  },
});
