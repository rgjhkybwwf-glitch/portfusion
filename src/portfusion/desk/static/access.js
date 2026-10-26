/* THE ACCESS PAGE. */

Object.assign(DRAW, {
  /* ACCESS — who can open the hosted desk, at which level, and from which devices. THE MAC ONLY:
     the remote door has no route to it. Every button here is one of the Access panel's
     registered actions, and each refusal comes back in desk/auth.py's own words. */
  access(d) {
    const cols = d.columns;
    const levelOptions = (held) => (held ? "" : `<option value="">none</option>`) +
      d.levels.map((l) => `<option${l.level === held ? " selected" : ""}>${esc(l.level)}</option>`)
        .join("");
    const result = (s) => `<span class="tag ${s.result === "signed in" || s.result === "enrolled"
      ? "ok" : s.result === "refused" ? "problem" : "gap"}">${esc(s.result)}</span>`;

    return page({
      scope: "who can open the hosted desk, at which level, and from which devices",
      work: `
        <h2>Levels</h2>
        <ul class="items">${d.levels.map((l) => `<li class="report">
          <span class="tag ${l.names ? "ok" : "note"}">${esc(l.level)}</span>
          <span>${esc(l.pages.join(" · "))}</span>
          <span class="muted">${l.names ? "holders named" : "every account by its code, "
            + "holders and account numbers withheld"}</span></li>`).join("")}</ul>

        <h2>Readers</h2>
        ${table(d.readers,
          cols.readers.filter((c) => c !== "level" && c !== "now"), "<th></th>",
          (r) => `<td class="oneline"><button class="link" data-revoke-reader="${esc(r.who)}">` +
                 `revoke</button></td>`,
          { name: "readers", inserts: [
              { after: "who", head: `<th>${head("level")}</th>`, cell: (r) => `<td class="oneline">
                  <select data-level-for="${esc(r.who)}" aria-label="Level for ${esc(r.who)}">
                    ${levelOptions(r.level)}</select></td>` },
              { after: "last_signed_in", head: `<th>${head("now")}</th>`,
                cell: (r) => `<td class="oneline"><span class="tag ${r.now === "signed in"
                  ? "ok" : "note"}">${esc(r.now)}</span></td>` }],
            /* EACH READER'S DEVICES UNDER THEIR ROW, each with its own revoke. */
            afterRow: (r, span) => r.device_list.length ? `<tr class="devices"><td colspan="${span}">
              ${table(r.device_list, cols.devices, "<th></th>", (v) => `<td class="oneline">
                <button class="link" data-revoke-device="${esc(v.key)}"
                        data-device="${esc(v.device)}">revoke</button></td>`, { name: `devices ${r.who}` })}
              </td></tr>` : "" })}
        <p><button class="link" id="sign-everyone-out">sign everyone out</button></p>

        <h2>Enrol a device</h2>
        <div class="grid">
          ${filterField("reader", `<select id="enrol-who"><option value="">a new reader</option>
            ${d.readers.map((r) => `<option>${esc(r.who)}</option>`).join("")}</select>`)}
          ${filterField("name", `<input id="enrol-name" autocomplete="off" size="14">`)}
          ${filterField("level", `<select id="enrol-level">${levelOptions("principal")}</select>`)}
        </div>
        <p><button class="primary" id="enrol-code">Issue an enrol code</button></p>
        <p id="enrol-out" hidden></p>
        <pre id="access-out" class="error" aria-live="polite" hidden></pre>

        <h2>Sign-ins, the last ${d.log_days} days</h2>
        ${table(d.signins, cols.signins.filter((c) => c !== "result"), "", () => "",
            { name: "sign-ins", inserts: [{ after: "at", head: `<th>${head("result")}</th>`,
                          cell: (s) => `<td class="oneline">${result(s)}</td>` }] })}

        <h2>Account codes</h2>
        ${table(d.codes, cols.codes, "", () => "", { name: "codes" })}`,
      why: [["Levels", "What each level opens is decided by the remote door on every request, "
               + "never by the page; a change here holds from the reader's next request."],
            ["Enrolling", `A code lets one device enrol a passkey for one reader. It works once, `
               + `for ${d.code_minutes} minutes, typed into the hosted desk's sign-in. A new `
               + `reader's level comes with their first code; after that it is changed above.`]],
    });
  },
});

Object.assign(WIRE, {
  access(d) {
    const out = $("#access-out");
    const act = async (name, body, ask) => {
      if (ask && !confirm(ask)) return null;
      out.hidden = true;
      const { result, error } = await runAction(name, body);
      if (error) {
        out.hidden = false;
        out.textContent = error;
        return null;
      }
      return result;
    };
    const again = () => show("access");

    document.querySelectorAll("[data-level-for]").forEach((sel) =>
      sel.addEventListener("change", async () => {
        if (sel.value && await act("access-set-level", { who: sel.dataset.levelFor,
                                                         level: sel.value })) again();
      }));
    document.querySelectorAll("[data-revoke-device]").forEach((b) =>
      b.addEventListener("click", async () => {
        if (await act("access-revoke-device", { key: b.dataset.revokeDevice },
                      `Revoke ${b.dataset.device}? Its passkey stops working at once.`)) again();
      }));
    document.querySelectorAll("[data-revoke-reader]").forEach((b) =>
      b.addEventListener("click", async () => {
        const who = b.dataset.revokeReader;
        if (await act("access-revoke-reader", { who },
                      `Revoke ${who}? Every device of theirs stops working at once.`)) again();
      }));
    $("#sign-everyone-out").addEventListener("click", async () => {
      const res = await act("access-sign-everyone-out", {},
                            "Sign everyone out of the hosted desk?");
      if (res) again();
    });

    /* A NEW READER IS NAMED AND GIVEN A LEVEL; one already enrolled keeps theirs, so the two
       boxes are for a new reader only. */
    const who = $("#enrol-who");
    const fit = () => {
      const fresh = !who.value;
      $("#enrol-name").closest("label").hidden = !fresh;
      $("#enrol-level").closest("label").hidden = !fresh;
    };
    who.addEventListener("change", fit);
    fit();
    $("#enrol-code").addEventListener("click", async () => {
      const fresh = !who.value;
      const res = await act("access-enrol-code", {
        who: fresh ? $("#enrol-name").value : who.value,
        level: fresh ? $("#enrol-level").value : null });
      if (!res) return;
      const shown = $("#enrol-out");
      shown.hidden = false;
      shown.innerHTML = `<span class="enrol-code">${esc(res.code)}</span>
        <span class="muted">for ${esc(res.who)}, at ${esc(res.level)}. Typed on the device at the
        hosted desk's sign-in. Lasts ${esc(res.minutes)} minutes, once.</span>`;
    });
  },
});
