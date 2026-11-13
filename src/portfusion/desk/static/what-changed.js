/* WHAT CHANGED: the page's draw. */

Object.assign(DRAW, {
  /* WHAT CHANGED — two bases, one under the other, never added. The panel hands over totals
     already computed per basis, because Book.change_totals() refuses to span them; this draws
     them, each block with its own columns.

     THE BLOCK TOTALS STAY PLAIN, deliberately, and it is the same rule the Dashboard's headline
     gains follow: movement colour's job is scanning a COLUMN, and a short summary is a list
     you read rather than a column you scan. The per-line table below is the scannable thing and
     it wears the colour. */
  "what-changed"(d) {
    const windows = (d.windows || []).map((w) =>
      `<span class="win">${w.priced_from ? esc(day(w.priced_from)) : "new line"} &rarr; ` +
      `${esc(day(w.priced_at))} <span class="muted">${w.lines} ` +
      `line${w.lines === 1 ? "" : "s"}</span></span>`).join("");

    /* THE TWO BLOCKS ARE ONE GRID: the same columns in the same widths, so a
       spread bet's figure sits under a share's; the From FX a bet has no part in is a dash. */
    const grid = d.grid || [];
    const block = (b) => {
      const t = b.totals;
      return `
        <section class="diff">
          <h3>${esc(b.label)}</h3>
          ${figures([
            ["Value then", money(t.value_from)],
            ["From price", money(t.price_effect)],
            ...(grid.includes("fx_effect")
              ? [["From FX", b.columns.includes("fx_effect") ? money(t.fx_effect) : "—"]] : []),
            ["From dealing", money(t.transacted)],
            ["Change", money(t.change)],
            ["Value now", money(t.value_to)],
          ])}
          ${b.rows.length
            ? table(b.rows, grid, "", () => "", { align: "blocks", name: b.label, cells: Object.fromEntries(
                grid.filter((c) => !b.columns.includes(c)).map((c) => [c, () => `<td class="num">—</td>`])) })
            : `<p class="muted">no lines on this basis.</p>`}
        </section>`;
    };

    /* THE SECOND CLOCK, store/journal.csv. Market time above, record time below, and each block
       says which — a mark banked at a month end and a dividend from the month before, entered
       days later, sit weeks apart on this page and answer different questions.

       NOTHING IS COUNTED HERE. The rows are Book.journal()'s and the discrepancy is
       Book.journal_reconciliation()'s; the panel selected them and this draws them. */
    const r = d.record || {};
    const gap = (r.unaccounted || []).map((u) =>
      `<li class="note"><span class="tag">by hand</span><strong>${esc(u.table)}</strong> —
       ${u.on_file} rows on file against ${u.expected} the journal accounts for.</li>`).join("");

    /* SHOWN ONCE, AND ONLY WHEN YOU ARRIVED HERE FROM A WRITE. It states the one thing this
       panel cannot: how many outgoing marks were banked before the new ones landed, which is
       the rule the Price Refresh exists to enforce and the only evidence that it ran. */
    /* THE FIGURES BELOW HAVE ALREADY MOVED and the receipt must not claim otherwise. The engine
       is cached on the STORE's mtime, so a write invalidates it and the next read is against
       the new marks — `marks.py` reloads the record for the same reason, and
       test_the_written_mark_is_visible_to_the_engine_without_a_restart holds it. */
    const wrote = LAST_REFRESH;
    LAST_REFRESH = null;
    const n = (k, word) => `${k} ${word}${k === 1 ? "" : "s"}`;
    const receipt = !wrote ? [] : [{ state: "clear", tag: "written", label: "Refresh",
      body: quiet(`${n(wrote.prices, "price")}, ${n(wrote.rates, "rate")} and
        ${n(wrote.readings || 0, "IG reading")} replaced ·
        ${n(wrote.banked_before.prices + wrote.banked_before.rates, "outgoing mark")} banked
        first, ${wrote.banked_after.prices + wrote.banked_after.rates || "none"} after`) }];

    /* RECORD TIME OVER THE SPAN MARKET TIME COVERS, the rest folded under it: the journal grows
       with every write, and what the book learned since the last refresh is this page's half. */
    const opened = r.opened ? esc(day(r.opened.slice(0, 10))) : "—";
    const since = r.since ? esc(day(r.since)) : opened;
    const earlier = r.earlier || [];
    return page({
      scope: "what the marks did, then what the book learned",
      status: [...receipt, { label: "Compared", body: quiet(windows || "—") }],
      work: `
        <h2>Market time &mdash; what the marks did</h2>
        ${d.blocks.map(block).join("")}
        <h2>Record time &mdash; every write since ${since}</h2>
        ${gap ? `<ul class="items">${gap}</ul>` : ""}
        ${(r.rows || []).length
          ? table(r.rows, r.columns, "", () => "", { name: "record" })
          : `<p class="muted">nothing written since ${since}.</p>`}
        ${earlier.length ? `<details class="earlier"><summary>${earlier.length} earlier,
          since the journal opened ${opened}</summary>${table(earlier, r.columns, "", () => "", { name: "earlier" })}</details>`
          : ""}`,
      why: [["Market time", d.caveat], ["Record time", r.caveat || ""]],
    });
  },
});
