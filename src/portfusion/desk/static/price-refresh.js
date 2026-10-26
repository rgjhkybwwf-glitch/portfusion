/* THE PRICE REFRESH. */

/* A FETCHED PRICE SWEEP SURVIVES LEAVING THE TAB until it is written or
   discarded: it costs two vendors' calls, and a tab switch redraws from the record. Held:
   the fetch's reply, the day it asked for, when it landed, and each row's tick and any figure
   typed into a line it left open — so the form comes back as it was left. */
let PRICE_SWEEP = null;

Object.assign(DRAW, {
  /* PRICE REFRESH — the screen that writes marks.

     THE FOUR STEPS ARE THE PANEL, not decoration. feeds/refresh.py exists as ONE command because
     two commands mean two chances to forget the first. Here the same ordering is what you look at
     while you work.

     A ROW CANNOT BE TICKED UNTIL IT IS COMPLETE. Rule 1 of docs/prices.md — update a price and
     its date together — enforced at the point of entry rather than explained afterwards. The
     SERVER refuses the same thing; this only makes the refusal visible before it happens, which
     is the difference between a form that teaches and a form that scolds. */
  "price-refresh"(d) {
    /* THE REVIEW STEP LEADS WITH THE MARKS' AGE, the engine's figure and the Dashboard's words
      , against the limit that judges it; a count past the limit is its tag. */
    const stale = (d.prices || []).filter((r) => r.stale).length;

    /* THE BANK STEP ASKS NOTHING OF A READER: the write banks the outgoing marks whether or not
       they are on file. It is drawn only when the histories cannot be read; its
       rule stays in the fold. */
    const b = d.banked;
    const bank = !b.unavailable ? [] : [{ label: d.steps[0].label, state: "problem",
      title: `history/ could not be read: ${b.unavailable}`,
      body: quiet("history/ could not be read") }];

    /* ONE ROW PER MARK. `was` is the outgoing value and its age, which is the thing you are
       replacing; the three cells beside it are what a FETCH puts there, READ-ONLY. A price is
       never typed: the door refuses one without an instant (`struck`, `at`), which only a feed
       supplies — and a fetched figure edited before it was ticked would have travelled under
       the vendor's source. A RATE the sweep left unpriced is the one line opened for typing,
       by `unpriced()`. The tick waits for all three cells. */
    /* WHERE THE FIGURE CAME FROM, once it is there. Empty until something fills the row, then
       `fetched` or `derived` — quotes and a cross ticked identically in one column is
       how the difference stops being visible, and the difference is the whole of the glossary's
       provenance section. A DERIVED mark may never be labelled sourced. */
    const priceRow = (r) => `
      <tr data-kind="price" data-key="${esc(r.mark_key)}">
        <td class="oneline">${esc(r.mark_key)}</td>
        <td class="num muted">${r.price} ${r.contract ? "pts" : esc(r.currency)}</td>
        <td class="small ${r.stale ? "stale" : "muted"}">${esc(day(r.as_of))} · ${r.age_days}d</td>
        <td class="num"><input data-f="price" readonly size="10"></td>
        <td class="oneline"><input data-f="as_of" readonly size="10"> <span class="muted small" data-when></span></td>
        <td class="wide-cell"><input data-f="source" readonly></td>
        <td class="origin"></td>
        <td><label class="tick"><input type="checkbox" data-tick disabled
          aria-label="${head("take")}"></label></td>
      </tr>`;

    /* AN IG ACCOUNT, previewed like a price: its outgoing equity and date, then what the sweep
       reads. Its equity is written WITH the levels read in the same pass (retick). */
    const readingRow = (r) => `
      <tr data-kind="reading" data-key="${esc(r.account)}">
        <td class="oneline">${esc(r.account)}</td>
        <td class="num muted">${money(r.equity)}</td>
        <td class="muted small">${esc(day(r.as_of))} · ${r.age_days}d</td>
        <td class="num"><input data-f="equity" readonly size="10"></td>
        <td><input data-f="as_of" readonly size="10"></td>
        <td class="wide-cell"><input data-f="source" readonly></td>
        <td class="origin"></td>
        <td><label class="tick"><input type="checkbox" data-tick disabled
          aria-label="${head("take")}"></label></td>
      </tr>`;

    const rateRow = (r) => `
      <tr data-kind="rate" data-key="${esc(r.currency)}">
        <td class="oneline">${esc(r.currency)}</td>
        <td class="num muted">${r.rate}</td>
        <td class="muted small">${esc(day(r.as_of))}${r.age_days == null ? "" : ` · ${r.age_days}d`}</td>
        <td class="num"><input data-f="rate" readonly inputmode="decimal" size="10"></td>
        <td class="oneline"><input data-f="as_of" readonly size="10"> <span class="muted small" data-when></span></td>
        <td class="wide-cell"><input data-f="source" readonly></td>
        <td class="origin"></td>
        <td><label class="tick"><input type="checkbox" data-tick disabled
          aria-label="${head("take")}"></label></td>
      </tr>`;

    /* A DATED RATE THE RECORD LACKS: one row per currency and date, showing the
       rate that date converts at today, filled by its fetch with the close of the date's newest
       session and BANKED into the history, never written over a live rate. Nothing is typed into
       one: a dated rate is a close. */
    const lackingRow = (r) => `
      <tr data-kind="lacking" data-key="${esc(r.currency)}@${esc(r.date)}" data-currency="${esc(r.currency)}">
        <td class="oneline">${esc(r.currency)}</td>
        <td class="num muted">${r.rate == null ? "—" : r.rate}</td>
        <td class="muted small">${esc(day(r.date))} · ${esc(r.why)}</td>
        <td class="num"><input data-f="rate" readonly inputmode="decimal" size="10"></td>
        <td class="oneline"><input data-f="as_of" readonly size="10"> <span class="muted small" data-when></span></td>
        <td class="wide-cell"><input data-f="source" readonly></td>
        <td class="origin"></td>
        <td><label class="tick"><input type="checkbox" data-tick disabled
          aria-label="${head("take")}"></label></td>
      </tr>`;

    /* The header control. `data-all` names the KIND it governs, so the wiring below never has
       to know which table it is in — the same hook the rows already carry. */
    const takeAll = (kind) =>
      `<label class="tick"><input type="checkbox" data-all="${kind}" disabled> all</label>`;

    /* ONE TABLE, BY KIND. One set of columns puts every tick under the one above it; each group
       keeps its own take-all, because they arrive by different routes and are finished at
       different moments. */
    const group = (label, kind, rows) => `
      <tbody><tr><th colspan="7">${label}</th><th>${takeAll(kind)}</th></tr>${rows.join("")}</tbody>`;

    return page({
      scope: `the marks stand at ${day(d.valued_at)}`,
      status: [
        ...bank,
        { label: d.steps[1].label, state: null, body: `
          <button class="link" id="rb-fetch">fetch everything</button>
          ${d.lacking.length ? `<button class="link" id="rb-lacking">${d.lacking.length} rate(s) the record lacks</button>` : ""}
          <span class="muted small">or closes of</span> <input type="date" id="rb-on">
          <button class="link" id="rb-discard" hidden></button>` },
        { label: d.steps[2].label, state: stale ? "gap" : null, tag: `${stale} past the limit`,
          body: quiet(`${d.age_days} days old · limit ${d.age_limit} days`) },
        { label: d.steps[3].label, state: null, body: `
          <button class="link" id="rb-write" disabled>write the ticked marks</button>
          <span class="muted small" id="rb-count">nothing ticked</span>` },
      ],
      why: [["Nothing happens until asked", "Nothing here leaves the machine or touches the "
                                            + "record until you ask it to."],
            ...d.steps.map((s) => [s.label, s.detail])],
      work: `
      ${/* WHAT THIS FORM CAN REPLACE, NOT WHAT NEEDS REPLACING. The LIST is the whole set
            (docs/prices.md: the whole book or none); the stale count is in words. `stale` is
            the engine's, against rules.PRICE_AGE_LIMIT. */ ""}
      <div id="rb-fetched"></div>
      <pre id="rb-out" class="paste" aria-live="polite" hidden></pre>
      ${/* TAKE THE WHOLE COLUMN. A fetch fills many rows at once. One per group, not one for the
            page: the groups arrive by different routes and are finished at different moments.

            IT ONLY EVER TICKS A COMPLETE ROW, and that is the rule surviving the convenience.
            A line without its figure, its date AND its source cannot be ticked one at a time,
            and a select-all that could tick one would be a way round `docs/prices.md` rule 1
            dressed up as a shortcut. The count beside it says what it took and what it left. */ ""}
      <div class="scroll" id="rb-form"><table>
        <thead><tr><th>${head("mark_key")}</th><th class="num">${head("was")}</th>
          <th>${head("was_at")}</th><th class="num">${head("new")}</th><th>${head("new_at")}</th>
          <th>${head("source")}</th><th>${head("origin")}</th><th>${head("take")}</th></tr></thead>
        ${group("Prices", "price", d.prices.map(priceRow))}
        ${group("Rates", "rate", d.rates.map(rateRow))}
        ${d.lacking.length ? group("Rates the record lacks", "lacking", d.lacking.map(lackingRow)) : ""}
        ${group("IG accounts", "reading", d.readings.map(readingRow))}
      </table></div>`,
    });
  },
});

Object.assign(WIRE, {
  async "price-refresh"(d) {
    /* Read before the form's first re-check, which would record the empty form over it. */
    const heldRows = PRICE_SWEEP ? PRICE_SWEEP.rows : null;

    const rows = () => [...document.querySelectorAll("#main tr[data-kind]")];
    const fields = (tr) => Object.fromEntries(
      [...tr.querySelectorAll("[data-f]")].map((i) => [i.dataset.f, i.value.trim()]));

    /* COMPLETE MEANS EVERY FIELD, and the source counts. A price with a date and no source is a
       number nobody can ask about again, which is the half of `docs/prices.md`'s rule 1 that is
       easiest to skip. */
    const complete = (tr) => Object.values(fields(tr)).every((v) => v !== "");

    /* WHAT A HELD SWEEP REMEMBERS OF THE FORM: each row's tick, and what was typed into a field
       the sweep left open. A fetched figure is read-only and comes back from the reply itself. */
    const keep = () => {
      if (!PRICE_SWEEP) return;
      PRICE_SWEEP.rows = Object.fromEntries(rows().map((tr) => [
        `${tr.dataset.kind}:${tr.dataset.key}`,
        { ticked: tr.querySelector("[data-tick]").checked,
          typed: Object.fromEntries([...tr.querySelectorAll("[data-f]")]
            .filter((i) => !i.readOnly).map((i) => [i.dataset.f, i.value])) }]));
    };

    const retick = () => {
      let ticked = 0;
      /* AN ACCOUNT'S EQUITY TAKES THE LEVELS READ WITH IT. The book derives the account's figure
         from those levels, so writing the equity without them compares it with marks from some
         other time. While a reading is ticked, every level IG gave in this sweep is ticked and
         held; the server refuses a reading that arrives without one. */
      const reading = rows().some((tr) => tr.dataset.kind === "reading"
                                          && tr.querySelector("[data-tick]").checked);
      rows().forEach((tr) => {
        const box = tr.querySelector("[data-tick]");
        const ok = complete(tr);
        const held = reading && tr.dataset.ig === "1" && ok;
        box.disabled = !ok || held;
        if (!ok) box.checked = false;
        if (held) box.checked = true;
        if (box.checked) ticked += 1;
      });
      /* THE HEADER BOX FOLLOWS ITS COLUMN rather than driving it: on when every takeable row
         is taken, INDETERMINATE when some are, and disabled while none can be. A select-all
         that showed "on" over a half-ticked column would be the control lying about the thing
         it controls. */
      ["price", "rate", "lacking", "reading"].forEach((kind) => {
        const all = document.querySelector(`#main [data-all="${kind}"]`);
        if (!all) return;
        const boxes = rows().filter((tr) => tr.dataset.kind === kind)
                            .map((tr) => tr.querySelector("[data-tick]"));
        const takeable = boxes.filter((b) => !b.disabled);
        const on = takeable.filter((b) => b.checked);
        all.disabled = takeable.length === 0;
        all.checked = takeable.length > 0 && on.length === takeable.length;
        all.indeterminate = on.length > 0 && on.length < takeable.length;
      });
      $("#rb-write").disabled = ticked === 0;
      $("#rb-count").textContent = ticked ? `${ticked} line(s) ticked` : "nothing ticked";
      keep();
    };

    /* THE ONE THING data-all DOES, and it happens before retick() re-reads the column. It
       reaches only rows the form has already ENABLED, so an incomplete line stays untaken —
       select-all is a shortcut through the clicking, never through the rule.

       ON THE FORM, NOT ON #main. #main outlives every panel, so handlers there pile up a set per
       visit. The form is redrawn with the panel, and its handlers with it. */
    const form = $("#rb-form");
    form.addEventListener("change", (e) => {
      const kind = e.target?.dataset?.all;
      if (!kind) return;
      rows().filter((tr) => tr.dataset.kind === kind)
            .map((tr) => tr.querySelector("[data-tick]"))
            .filter((b) => !b.disabled)
            .forEach((b) => { b.checked = e.target.checked; });
    });
    /* NOT WHILE THE SELECT-ALL BOX ITSELF IS THE TARGET. A checkbox fires `input` BEFORE
       `change`, and retick() treats the header box as a FOLLOWER of its column — so on `input`
       it would overwrite the box the click set before `change` reads it. Row boxes and text
       fields retick on `input`. */
    form.addEventListener("input", (e) => { if (!e.target?.dataset?.all) retick(); });
    form.addEventListener("change", retick);
    retick();

    /* ONE LINE INTO ONE ROW. `origin` is what the row wears afterwards — see priceRow. The
       fetch FILLS the form and never ticks it: every figure still has to be looked at and
       taken, which is the human check between a vendor's number and the record. */
    const fill = (key, kind, values, origin) => {
      const tr = rows().find((t) => t.dataset.key === key && t.dataset.kind === kind);
      if (!tr) return false;
      Object.entries(values).forEach(([f, v]) => {
        const input = tr.querySelector(`[data-f="${f}"]`);
        if (input) { input.value = v; input.title = v; }
      });
      tr.querySelectorAll("[data-f]").forEach((i) => { i.readOnly = true; });
      /* WHICH INSTANT is the feed's, not an input: a price typed into this form says neither,
         and the door refuses it. */
      tr.dataset.struck = values.struck || "";
      tr.dataset.at = values.at || "";
      tr.dataset.ig = values.ig ? "1" : "";
      /* A LIVE READ SAYS ITS TIME AND A CLOSE SAYS SO, beside the date the write
         sends: the two can share a date. */
      const when = tr.querySelector("[data-when]");
      if (when) when.textContent = values.struck === "close" ? "close"
        : values.at ? clock(values.at) : "";
      const cell = tr.querySelector(".origin");
      if (cell) cell.innerHTML = `<span class="muted small">${esc(origin)}</span>`;
      return true;
    };

    /* A VENDOR'S FAILURE, ITS FIRST LINE. The rest is written for the terminal: a missing
       credentials file answers with the whole template to create. */
    const failed = (e) => esc(String(e || "").split("\n")[0]);

    /* A LINE THE SWEEP LEFT UNPRICED says so, with the reason on hover. A rate is then opened
       for typing — the door takes a rate without an instant; a price it would refuse. */
    const unpriced = (tr, why) => {
      const cell = tr.querySelector(".origin");
      if (cell) cell.innerHTML = `<span class="stale small" title="${esc(why)}">unpriced</span>`;
      if (tr.dataset.kind !== "rate") return;
      tr.querySelectorAll("[data-f]").forEach((i) => { i.readOnly = false; });
      const day = tr.querySelector('[data-f="as_of"]');
      if (!day.value) day.value = d.today;
    };

    /* THE IG ACCOUNTS, READ STRAIGHT AFTER THE LEVELS. Each is a whole reading, composed by
       feeds/refresh.py in the shape the observations door takes, so nothing here builds one:
       the row shows it, and the write sends it as it came. */
    let READINGS = {};

    /* A PAST DAY'S CLOSES — the quarter end fetched after it. Set by the fetch, read by the
       write: those closes are BANKED into the histories and the live marks are left alone
       (marks.bank_closes). A row left at today's date is refused by the door, not here. */
    let closeOf = null;

    /* ONE FILL, from a fetch or from a sweep held across a tab switch. `kept` is each row's
       tick and typed figures, laid back over the fill before the form is checked again. */
    const applySweep = (res, kept) => {
      const out = $("#rb-fetched");
      closeOf = res.on || null;
      /* THE RATES THE RECORD LACKS fill their own group and nothing else: no other line was
         asked for, so none is called unpriced. */
      const lacking = !!res.lacking;
      const notes = lacking ? [`<strong>closes of the dates the record lacks</strong>`]
        : closeOf
        ? [`<strong>closes of ${esc(closeOf)}</strong> — writing banks them into the history; `
           + `the live marks stay as they are`] : [];
      const why = {};

      /* EACH VENDOR REPORTS SEPARATELY, so one that is down is NAMED and the rest still
         lands. */
      const ig = res.ig_levels || {};
      if (lacking) {
        /* IG is not asked for a rate, so it is not reported. */
      } else if (ig.ok === false) {
        notes.push(`<span class="stale">IG: ${failed(ig.error)}</span>`);
      } else {
        const missing = [];
        (ig.rows || []).forEach((row) => {
          if (!row.priced) {
            missing.push(`${row.contract} (${row.status})`);
            why[row.contract] = row.status;
            return;
          }
          fill(row.contract, "price", {
            price: row.level, as_of: row.as_of, source: row.source,
            struck: row.struck, at: row.at, ig: true,
          }, row.origin || "fetched");
        });
        notes.push(`IG ${(ig.rows || []).length - missing.length} of ${(ig.rows || []).length}`);
        (ig.problems || []).forEach((p) => notes.push(`<span class="stale">${esc(p)}</span>`));
        if (missing.length) notes.push(
          `<span class="stale">no IG price for ${esc(missing.join(", "))} — chase these</span>`);
      }

      const tv = res.tv || {};
      if (tv.ok === false) {
        notes.push(`<span class="stale">TradingView: ${failed(tv.error)}</span>`);
      } else {
        (tv.prices || []).forEach((row) => {
          fill(row.mark_key, "price",
                   { price: row.price, as_of: row.as_of, source: row.source,
                     struck: row.struck, at: row.at }, "fetched");
        });
        (tv.rates || []).forEach((row) => {
          if (lacking) {
            row.wanted.forEach((w) => fill(`${row.currency}@${w}`, "lacking",
              { rate: row.rate, as_of: row.as_of, source: row.source, struck: row.struck },
              "fetched"));
            return;
          }
          fill(row.currency, "rate",
                   { rate: row.rate, as_of: row.as_of, source: row.source,
                     struck: row.struck, at: row.at }, "fetched");
        });
        notes.push(`TradingView ${(tv.prices || []).length + (tv.rates || []).length}`);
        /* THE QUOTE SCREEN'S OWN ANSWER, when it is not `ok`: every line still trading
           waits on it, so one refusal is named once here as well as on each line. */
        if (tv.quote_screen && tv.quote_screen !== "ok") {
          notes.push(`<span class="stale">quote screen — ${esc(tv.quote_screen)}</span>`);
        }
        (tv.failed || []).forEach((f) => {
          why[f.wanted ? `${f.key}@${f.wanted}` : f.key] = f.why;
          notes.push(`<span class="stale">${esc(f.key)}: ${esc(f.why)}</span>`);
        });
      }
      READINGS = {};
      const eq = res.ig_equity;
      if (eq && eq.ok === false) {
        notes.push(`<span class="stale">IG accounts: ${failed(eq.error)}</span>`);
        (eq.rows || []).forEach((r) => { why[r.account] = eq.error; });
      } else if (eq) {
        (eq.readings || []).forEach((r) => {
          READINGS[r.account] = r;
          const read = (eq.rows || []).find((x) => x.account === r.account) || {};
          fill(r.account, "reading", {
            equity: money(r.equity), as_of: eq.read_at, source: read.source,
          }, "fetched");
        });
        notes.push(`IG accounts ${(eq.readings || []).length}, ${eq.gap_seconds}s after the levels`);
        (eq.refusals || []).forEach((x) => notes.push(`<span class="stale">${esc(x.text)}</span>`));
      }
      const figure = { price: "price", rate: "rate", lacking: "rate", reading: "equity" };
      rows().filter((tr) => lacking === (tr.dataset.kind === "lacking"))
        .filter((tr) => !fields(tr)[figure[tr.dataset.kind]])
        .forEach((tr) => unpriced(tr, why[tr.dataset.key] || "not returned by this sweep"));

      /* THE FLAG LISTS ARE CHECKED, NEVER CHANGED: a disagreement is named beside the result,
         in the feed's own words (feeds/tv.py:watchlist_check). */
      const wl = res.watchlist;
      if (wl && wl.ok === false) {
        notes.push(`<span class="stale">flag lists: ${failed(wl.error)}</span>`);
      } else if (wl) {
        (wl.findings || []).filter((f) => f.items.length).forEach((f) => notes.push(
          `<span class="stale">${esc(f.items.join(", "))} ${esc(f.said)}</span>`));
      }

      /* WHAT CAME BACK AND WHAT DID NOT, each vendor in turn: a filled row is
         its own receipt, so the line counts nothing else. */
      out.innerHTML = `<p class="muted">${notes.join(" · ")}</p>`;
      Object.entries(kept || {}).forEach(([id, k]) => {
        const tr = rows().find((t) => `${t.dataset.kind}:${t.dataset.key}` === id);
        if (!tr) return;
        Object.entries(k.typed).forEach(([f, v]) => {
          const input = tr.querySelector(`[data-f="${f}"]`);
          if (input && !input.readOnly) input.value = v;
        });
        tr.querySelector("[data-tick]").checked = k.ticked;
      });
      const drop = $("#rb-discard");
      drop.hidden = false;
      drop.textContent = `discard the sweep fetched ${PRICE_SWEEP.at}`;
      retick();
    };

    /* ONE FETCH, THREE ASKS: the whole sweep, one past day's closes, or the closes of the dated
       rates the record lacks — each one action (refresh-fetch-all), filling the one form. */
    const fetchSweep = async (button, ask, who) => {
      const out = $("#rb-fetched");
      button.disabled = true;
      out.innerHTML = `<p class="muted">asking ${who}…</p>`;
      try {
        const { result, error } = await runAction("refresh-fetch-all", ask);
        if (error) { out.innerHTML = `<pre class="paste">${esc(error)}</pre>`; return; }
        PRICE_SWEEP = { res: result, on: ask.on || null, at: stampNow(), rows: {} };
        applySweep(PRICE_SWEEP.res, {});
      } finally {
        button.disabled = false;
      }
    };
    $("#rb-fetch").addEventListener("click", (e) => {
      const on = $("#rb-on").value || null;
      fetchSweep(e.currentTarget, on ? { on } : {}, "IG, then TradingView");
    });
    $("#rb-lacking")?.addEventListener("click", (e) =>
      fetchSweep(e.currentTarget, { lacking: true }, "TradingView"));

    $("#rb-discard").addEventListener("click", () => {
      PRICE_SWEEP = null;
      show("price-refresh");
    });

    $("#rb-write").addEventListener("click", async () => {
      const out = $("#rb-out"), button = $("#rb-write");
      const payload = { prices: [], rates: [], readings: [] };
      rows().forEach((tr) => {
        if (!tr.querySelector("[data-tick]").checked) return;
        const v = fields(tr);
        if (tr.dataset.kind === "reading") {
          payload.readings.push(READINGS[tr.dataset.key]);
        } else if (tr.dataset.kind === "lacking") {
          payload.rates.push({ currency: tr.dataset.currency, as_of: v.as_of, rate: v.rate,
                               source: v.source, struck: tr.dataset.struck });
        } else if (tr.dataset.kind === "price") {
          const was = d.prices.find((r) => r.mark_key === tr.dataset.key);
          payload.prices.push({ mark_key: tr.dataset.key, price: v.price,
                                currency: was.currency, as_of: v.as_of, source: v.source,
                                struck: tr.dataset.struck, at: tr.dataset.at });
        } else {
          payload.rates.push({ currency: tr.dataset.key, as_of: v.as_of, rate: v.rate,
                               source: v.source, struck: tr.dataset.struck });
        }
      });
      if (closeOf) payload.close_of = closeOf;
      button.disabled = true;
      out.hidden = false;
      out.textContent = closeOf ? `banking the closes of ${closeOf}…`
                                : "banking the outgoing marks, then writing…";
      try {
        const { result: res, error, refused } = await runAction("refresh-write-marks", payload);
        /* A REFUSAL IS SHOWN IN FULL. Those messages name the rule that stopped the write —
           which line, and why — and that is the half worth reading. */
        if (error) {
          out.textContent = refused ? `refused — nothing was written.\n\n${error}` : error;
          return;
        }
        /* A WRITTEN REFRESH MOVES YOU ON. The bay is the machine and What Changed is the report,
           so finishing here means reading there. A REFUSAL DOES NOT MOVE: the message names the
           line and the rule that stopped it, and navigating away from it would throw away the
           only thing worth reading. The receipt travels; see LAST_REFRESH. */
        PRICE_SWEEP = null;
        $("#rb-discard").hidden = true;
        if (closeOf) {
          out.textContent = `Banked the closes of ${(res.days || []).join(", ") || res.day}: `
            + `${res.banked.prices} price(s), `
            + `${res.banked.rates} rate(s)${res.already ? `, ${res.already} already on file` : ""}.`
            + ((res.replaced || []).length ? `\n\n${res.replaced.join("\n")}` : "");
          return;
        }
        LAST_REFRESH = res;
        out.textContent = `Written. ${res.prices} price(s), ${res.rates} rate(s), `
                        + `${res.readings} IG reading(s).`;
        openPanel("what-changed");
      } catch (e) {
        out.textContent = `write failed — ${e.message}`;
      } finally {
        button.disabled = false;
      }
    });

    if (PRICE_SWEEP) {
      $("#rb-on").value = PRICE_SWEEP.on || "";
      applySweep(PRICE_SWEEP.res, heldRows);
    }
  },
});
