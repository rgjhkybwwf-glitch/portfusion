/* RECONCILE: the page's draw. */

/* THE STEPS, EXPLAINED ONCE AND BELOW THE TABLE. `Reading` keeps its links on screen because
   those are the work; the reasons live here, Events' among them. */
const RECONCILE_WHY = [
  ["Units", "A share account is checked on units: every holding in its holdings export against "
            + "the book's at the export's day. The Bench files an export only if they agree, and "
            + "this page counts them again from the filed export, so an event entered since "
            + "shows here. The book's value sits beside the broker's for information; it is "
            + "never the verdict."],
  ["Equity", "An IG account is checked on equity: the book's own figure, from its prices, "
             + "against IG's, read together on Price Refresh. Read apart, the two differ by "
             + "whatever the market did between, and the account is not checked."],
  ["Last broker check", "The newest broker document or reading on the account's history, as the "
                        + "report names it."],
];

Object.assign(DRAW, {
  /* RECONCILE — what the book says beside what the broker says.
     Two checks, and they are not the same check: a share account agrees on units, counted
     from its filed export; an IG account's equity is read in one pass with its marks. Neither is
     decided or worded here — the verdict and its sentence arrive already made, from the same
     function the audit and the Dashboard ask. */
  reconcile(d) {
    /* THE TAG READS IN WORDS: the engine's code is "units-agree", the reader's is "units agree". */
    const verdictWords = (v) => v.replace(/-/g, " ");
    /* AN IG READING'S FIGURES, under the broker's figure, in IG's own words: the ones the
       reading holds, so a figure it lacks is left out rather than shown as a dash. */
    const igFigures = (r) => r.ig_figures.length ? `<br><span class="muted small">${
      r.ig_figures.map((f) => `${esc(f.label)} ${money(f.value)}`).join(" · ")}</span>` : "";
    /* EACH ROW'S VERDICT AND ITS TAG ARE THE PANEL'S, and its words the engine's: what the
       account was checked on and found under its name, the step that clears it by its tag —
       drawn only where its page opens, on the Mac. */
    const cells = {
      account: (r) => `<td>${esc(r.account)}<br><span class="muted small">${esc(r.state)}</span></td>`,
      book: (r) => `<td class="num">${money(r.book)}</td>`,
      broker: (r) => `<td class="num">${money(r.broker)}${igFigures(r)}</td>`,
      difference: (r) => `<td class="num">${money(r.difference)}</td>`,
      verdict: (r) => `<td><span class="tag ${esc(r.tag)}">${esc(verdictWords(r.verdict))}</span>${
        r.next && PANELS.has(r.reads) ? `<br>${panelLink(r.reads, r.next)}` : ""}</td>`,
      document: (r) => `<td>${r.document ? esc(r.document) : "—"}</td>`,
    };

    /* REPORT ONLY WHAT DISAGREES: a reporting rule rather than a data one — the panel hands over
       every row, and the lead is what needs attention, each in the engine's sentence. A clean
       book leads with a clean line, not with silence. */
    const lead = d.disagreements.length
      ? `<ul class="items">${d.disagreements.map((r) =>
          `<li class="problem"><span class="tag">differs</span>${esc(r.sentence)}</li>`).join("")}</ul>`
      : `<ul class="items"><li class="clear"><span class="tag">clear</span>
         every account that can be checked, does.</li></ul>`;

    /* THE ENGINE'S OWN WORDS, ONCE. Each unchecked account's state and step sit in its table
       row, where a reader already looks; the lead names the accounts. */
    const gaps = d.gaps.length ? `<ul class="items"><li class="gap"><span class="tag">not
        judged</span><strong>${d.gaps.map((r) => esc(r.account)).join(" · ")}</strong> — the
        table says why.</li></ul>`
      : "";

    return page({
      scope: "the book against each broker, account by account",
      work: `
        <h2>What disagrees</h2>${lead}${gaps}
        <h2>Every account</h2>
        ${table(d.rows, d.columns, "", () => "", { name: "accounts", cells, rowClass: (r) => r.verdict })}`,
      why: RECONCILE_WHY,
    });
  },
});
