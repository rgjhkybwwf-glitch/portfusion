/* REPORTS: the page's draw. */

Object.assign(DRAW, {
  /* REPORTS — every quarter the record closes, and each year, grouped by year. A quarter whose
     report the gate allows opens it; one it refuses shows the gate's own words beneath it. The
     state's word is the tag; whether a quarter is ready is the engine's answer, never decided
     here.

     A QUARTER STILL OPEN SHOWS ITS TAG ALONE: before its end the gate can only say its NAV rows
     are not frozen yet, which "open" already says. What stops a report shows from the day the
     quarter ends.

     NO DATE BESIDE A NAME: "Q3 2026" and "2026 year end" say the period, as Performance's
     Quarter does. */
  reports(d) {
    const state = (q) => !q.closed ? ["note", q.ended ? "to close" : "open"]
                       : q.gaps.length ? ["gap", "not ready"] : ["ok", "ready"];
    const row = (q) => {
      const [tone, word] = state(q);
      return `<li class="report"><span class="tag ${tone}">${word}</span>
        <strong>${q.closed && !q.gaps.length ? reportLink(q) : esc(q.quarter)}</strong>
        ${q.reported ? "" : `<span class="muted">for the record</span>`}
        ${q.ended && q.gaps.length
          ? `<ul class="gaps">${q.gaps.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>` : ""}</li>`;
    };
    return page({
      scope: "every quarter the record closes, and each year",
      work: d.years.map((y) => `
        <h2>${esc(y.year)}</h2>
        <ul class="items">
          <li class="report"><span class="tag note">${y.built ? "ready" : "not built"}</span>
            <strong>${esc(y.year)} year end</strong></li>
          ${d.quarters.filter((q) => q.quarter_end.startsWith(y.year)).map(row).join("")}
        </ul>`).join(""),
    });
  },
});
