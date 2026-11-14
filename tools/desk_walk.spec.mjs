// THE DESK WALKED, IN CHROMIUM: the demo desk `desk_walk.py` serves, at 1440 × 900. Each page is
// opened by its tab and must draw no error, draw each control in the shape of what it does, hold
// no accessibility fault but the `KNOWN`, and look as its baseline does; a finding is followed to
// its page; a wide table's button to Trades is in view, a press on a row opens its detail in
// view, and a heading that sorts shows it; a box that
// scrolls sideways marks each edge with more beyond it, and one that does not marks none; an open
// detail leaves its table's width as it was, and runs whole as far as the box; a page chosen
// by keyboard puts focus on its heading, one Tab from its first control, its tab buttons kept, and
// a reader already in the page keeps their place; a heading reached by Tab is clear of the pinned
// columns, and a Tab between controls in view does not swing the box. It writes nothing, and does not prove a
// figure is right.
//
//     npm ci --prefix tools && npm --prefix tools run browser      # once: Playwright, its Chromium
//     npm --prefix tools run walk
//     npm --prefix tools run walk -- --update-snapshots            # a look changed on purpose
import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { DAY } from "./playwright.config.mjs";

// THE ACCESSIBILITY FAULTS ON FILE, each an axe rule and the pages it fires on. A fault not
// listed fails, and so does a listed one that has gone: the list only shrinks.
const KNOWN = {};

let said;
test.beforeEach(async ({ page }) => {
  said = [];
  page.on("pageerror", (e) => said.push(`error: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && said.push(`console.error: ${m.text()}`));
  page.on("response", (r) => r.status() >= 400 && said.push(`${r.status()}: ${r.url()}`));
  await page.clock.setFixedTime(new Date(DAY));
  await page.goto("/");
  await expect(page.locator("#tabs button[aria-current]")).toBeVisible();
});
test.afterEach(() => expect(said).toEqual([]));

const open = async (page, name) => {
  const answered = page.waitForResponse((r) => r.url().endsWith(`/api/panel/${name}`));
  await page.locator(`#tabs button[data-name="${name}"]`).click();
  await answered;
  await expect(page.locator(`#tabs button[data-name="${name}"]`)).toHaveAttribute("aria-current", "page");
  await page.waitForLoadState("networkidle");      // a page may ask again once it has drawn
};

// GO, ACT AND OPEN, AS DRAWN (`goButton()`, `actButton()` and `detailToggle()` in kit.js), each
// control found by its hook and read by its drawn style: a go has no underline and no border and
// ends in its arrow; an act has a border; a row that opens leads with the chevron. A row's first
// cell is read by what it leads with, so a row that opens by anything else is found.
const SHAPES = {
  go: "#main [data-panel], #main [data-trades], #main [data-life]",
  act: "#main .filter-clear button, #restart",
  open: "#main tr.has-detail > td:first-child",
};
const shapes = (page) => page.evaluate((found) => Object.fromEntries(Object.entries(found).map(([k, sel]) =>
  [k, [...document.querySelectorAll(sel)].map((at) => {
    const el = at.matches("td") ? at.firstElementChild ?? at : at;
    const s = getComputedStyle(el);
    return {
      shape: el.className,
      underlined: s.textDecorationLine.includes("underline"),
      bordered: ["Top", "Right", "Bottom", "Left"].some((e) =>
        s[`border${e}Style`] !== "none" && parseFloat(s[`border${e}Width`]) > 0),
      marked: el.textContent.trim().endsWith("→"),
      inPage: el.closest("#main") !== null,
    };
  })])), SHAPES);
const SHAPE = {
  go: { shape: "go", underlined: false, bordered: false, marked: true },
  act: { shape: "act", bordered: true },
  open: { shape: "detail-toggle" },
};

test("each page opens, holds no new accessibility fault and looks as it did", async ({ page }) => {
  const names = await page.locator("#tabs button").evaluateAll((bs) => bs.map((b) => b.dataset.name));
  const faults = {};
  for (const name of names) {
    await test.step(name, async () => {
      await open(page, name);
      await expect.soft(page.locator("pre.error:visible"), `${name} drew an error`).toHaveCount(0);
      const drawn = await shapes(page);
      for (const [kind, controls] of Object.entries(drawn)) {
        controls.forEach((c, i) => expect.soft(c, `${name}: control ${i} of its ${kind}s`).toMatchObject(SHAPE[kind]));
      }
      if (name === "holdings") {
        expect.soft(Object.fromEntries(Object.entries(drawn).map(([k, cs]) => [k, cs.some((c) => c.inPage)])),
          "Holdings draws a go, an act and an open").toEqual({ go: true, act: true, open: true });
      }
      // The screenshot waits for the page to stop moving, so it comes before axe reads it. Pictures
      // are compared on Linux alone, the guard's platform: a Mac sets type apart, and its pictures
      // would be one more set for a person to keep.
      if (process.platform === "linux") {
        await expect.soft(page).toHaveScreenshot(`${name}.png`, {
          fullPage: true, mask: [page.locator("footer.foot")],    // the footer names the commit
        });
      }
      for (const v of (await new AxeBuilder({ page }).analyze()).violations) {
        (faults[v.id] ??= []).push(name);
      }
    });
  }
  expect(faults).toEqual(KNOWN);
});

test("a finding leads to the page its work is done on", async ({ page }) => {
  await open(page, "dashboard");
  const link = page.locator("ul.items li button[data-panel]").first();
  await expect(link, "the Dashboard shows a finding with a page").toBeVisible();
  const to = await link.getAttribute("data-panel");
  await link.click();
  await expect(page.locator(`#tabs button[data-name="${to}"]`)).toHaveAttribute("aria-current", "page");
  await expect(page).toHaveURL(new RegExp(`#${to}$`));
});

test("the closed-out count leads to the round trips it counts", async ({ page }) => {
  await open(page, "dashboard");
  const figure = page.locator("table.figures tr", { has: page.locator('button[data-panel="round-trips"]') });
  const count = Number((await figure.locator("td.num").innerText()).match(/^[\d,]+/)[0].replace(/,/g, ""));
  await figure.locator("button[data-panel]").click();
  await expect(page.locator('#tabs button[data-name="round-trips"]')).toHaveAttribute("aria-current", "page");
  await expect(page.locator("#rt-closed")).toHaveValue("yes");
  // THE PAGE DRAWS FIRST, then asks for the link's filter: the count is waited for, not read.
  await expect(page.locator("#main .scroll > table > tbody > tr:not(.detail-row)")).toHaveCount(count);
});

// THE FOCUSABLE ELEMENTS a Tab can reach, in the page: what the walk asks a Tab to land on.
const TABBABLE = "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), " +
  "select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex='-1'])";
// WHERE A BOX STANDS once the page has had two frames to scroll it.
const settled = (box) => box.evaluate((b) => new Promise((done) =>
  requestAnimationFrame(() => requestAnimationFrame(() => done(b.scrollLeft)))));
// THE SIGN THAT A BOX SCROLLS, on a pinned cell's inner edge: the width of the line its
// box-shadow draws, 2 for the sign and 1 for the hairline of a box at that end.
const edge = (cell) => cell.evaluate((c) => {
  const s = getComputedStyle(c).boxShadow;
  return s === "none" ? 0 : Math.abs(parseFloat(s.match(/(-?[\d.]+)px/)[1]));
});
// A PAGE WITH NO CONTROL after its heading: Method reads, and asks nothing.
const NO_CONTROL = ["method"];

test("a page chosen by keyboard puts focus on its heading, one Tab from its first control", async ({ page }) => {
  const tabs = page.locator("#tabs");
  const names = await tabs.locator("button").evaluateAll((bs) => bs.map((b) => b.dataset.name));
  const markup = () => tabs.evaluate((t) => t.innerHTML.replaceAll(' aria-current="page"', ""));
  const drawn = await markup();
  const heading = page.locator("#main .page-head h1");
  for (const name of names) {
    await test.step(name, async () => {
      const button = tabs.locator(`button[data-name="${name}"]`);
      const pressed = await button.elementHandle();
      // THE PAGE'S ANSWER IS HELD, so the rail is read between the press and the paint.
      let release;
      const held = new Promise((r) => { release = r; });
      const panel = `**/api/panel/${name}`;
      await page.route(panel, async (route) => { await held; await route.continue(); });
      await button.focus();
      await page.keyboard.press("Enter");
      await expect(button).toHaveAttribute("aria-current", "page");
      expect(await pressed.evaluate((b) => b === document.activeElement), "the pressed button keeps focus").toBe(true);
      expect(await button.evaluate((b, was) => b === was, pressed), "the button is the same node").toBe(true);
      expect(await markup(), "only aria-current moved").toBe(drawn);
      release();
      await expect(heading).toBeFocused();
      await page.unroute(panel);
      await page.waitForLoadState("networkidle");
      await expect(heading).toBeFocused();
      const first = await page.evaluateHandle((sel) => {
        const h = document.querySelector("#main .page-head h1");
        return [...document.querySelectorAll(`#main ${sel}`)].find((el) =>
          (h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) &&
          el.checkVisibility()) || null;
      }, TABBABLE);
      if (NO_CONTROL.includes(name)) {
        expect(await first.evaluate((el) => el === null), `${name} has no control`).toBe(true);
        return;
      }
      await page.keyboard.press("Tab");
      expect(await first.evaluate((el) => el === document.activeElement),
        `one Tab from ${name}'s heading reaches its first control`).toBe(true);
    });
  }
});

test("a reader already in a page keeps their place when the page's header arrives", async ({ page }) => {
  // THE HEADER'S ANSWER IS HELD, so the reader is in the page before the pick has finished.
  let release;
  const held = new Promise((r) => { release = r; });
  await page.route("**/api/state", async (route) => { await held; await route.continue(); });
  await page.locator('#tabs button[data-name="trades"]').click();
  await expect(page.locator("#main .page-head h1")).toHaveText("Trades");
  const control = page.locator("#main select").first();
  await control.focus();
  release();
  await page.waitForLoadState("networkidle");
  await expect(control).toBeFocused();
});

for (const name of ["holdings", "round-trips"]) {
  test(`${name}: a row's button is in view, and a press on the row opens its detail in view`, async ({ page }) => {
    await open(page, name);
    const row = page.locator("#main table[data-links] tbody tr:not(.detail-row)").first();
    const chevron = row.locator(".detail-toggle");
    await expect(row.locator("[data-trades]")).toBeInViewport({ ratio: 1 });
    await expect(chevron).toBeInViewport({ ratio: 1 });
    // THE TABLE SAYS IT RUNS ON UNDER ITS PINS: at rest the Trades column's inner edge carries the
    // sign, a heading cut there going on under it; at the end of the scroll the first column's
    // does, and the button to Trades is still in view.
    const BOX = "#main .scroll:has(> table[data-links])";
    const box = page.locator(BOX).first();
    const pins = (end) => [page.locator(`${BOX} > table > thead > tr > :${end}-child`).first(),
      page.locator(`${BOX} > table > tbody > tr:not(.detail-row) > td:${end}-child`).first()];
    for (const [at, trades, first] of [["rest", 2, 1], ["end", 1, 2]]) {
      if (at === "end") await box.evaluate((b) => { b.scrollLeft = b.scrollWidth; });
      for (const cell of pins("last")) await expect.poll(() => edge(cell), `Trades' edge at ${at}`).toBe(trades);
      for (const cell of pins("first")) await expect.poll(() => edge(cell), `the first column's edge at ${at}`).toBe(first);
      expect(await box.evaluate((b) => parseFloat(getComputedStyle(b).borderRightWidth)),
        `one sign at ${at}: the box's own edge carries none beside the pin`).toBe(0);
    }
    await expect(row.locator("[data-trades]")).toBeInViewport({ ratio: 1 });
    await box.evaluate((b) => { b.scrollLeft = 0; });
    // THE ROW IS THE WAY IN: a press on a cell, not on the chevron, and a second closes it.
    await row.locator("td").nth(1).click();
    await expect(chevron).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator("#main .detail-row:not([hidden]) .detail-pane > *").first())
      .toBeInViewport({ ratio: 1 });
    await row.locator("td").nth(1).click();
    await expect(chevron).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator("#main .detail-row:not([hidden])")).toHaveCount(0);
    // A DOUBLE PRESS THAT SELECTS A WORD, to copy it, leaves the row as it was.
    await row.locator("td").nth(1).dblclick();
    await expect(chevron).toHaveAttribute("aria-expanded", "false");
    // A HEADING THAT SORTS SHOWS IT before it is pressed, and its arrow once it is.
    const heading = page.locator("#main table[data-links] > thead th.sortable").first();
    await expect(heading.locator(".arrow.idle")).toBeVisible();
    await heading.click();
    await expect(heading.locator(".arrow:not(.idle)")).toBeVisible();
    // A HEADING REACHED BY TAB IS CLEAR OF THE PINNED COLUMNS, and inside its box, both ways
    // across the table: the browser leaves one that is partly in view under a pin.
    const heads = page.locator("#main table[data-links] > thead th[tabindex]");
    const clear = () => page.evaluate(() => {
      const el = document.activeElement, b = el.closest(".scroll"), r = el.getBoundingClientRect();
      const cells = b.querySelector(":scope > table > tbody > tr:not(.detail-row)").children;
      const left = cells[0].getBoundingClientRect().right;
      const right = Math.min(cells[cells.length - 1].getBoundingClientRect().left,
                             b.getBoundingClientRect().left + b.clientLeft + b.clientWidth);
      return r.left >= left - 1 && r.right <= right + 1;
    });
    const count = await heads.count();
    await box.evaluate((b) => { b.scrollTop = 0; b.scrollLeft = 0; });
    await heads.nth(0).focus();
    for (const [key, from, to] of [["Tab", 1, count], ["Shift+Tab", count - 2, 0]]) {
      for (let i = from; key === "Tab" ? i < to : i > to; i += key === "Tab" ? 1 : -1) {
        await page.keyboard.press(key);
        await expect(heads.nth(i)).toBeFocused();
        await expect.poll(clear, `${key} to heading ${i} leaves it clear of the pins`).toBe(true);
      }
    }
    // A PINNED CELL IS IN VIEW ALREADY: a Tab from the chevron to Trades does not swing the box.
    await chevron.focus();
    await settled(box);
    await box.evaluate((b) => { b.scrollLeft = 200; });
    await page.keyboard.press("Tab");
    await expect(row.locator("[data-trades]")).toBeFocused();
    expect(await settled(box), "the box did not move").toBe(200);
    // NOR DOES A TAB ON INTO THE ROW'S DETAIL, which is held at the box's left edge, where the
    // detail holds a control (a holding's leads to its company's life).
    await chevron.click();
    await expect(chevron).toHaveAttribute("aria-expanded", "true");
    const pane = page.locator("#main .detail-row:not([hidden]) .detail-pane");
    if (await pane.locator("a, button").count()) {
      await row.locator("[data-trades]").focus();
      await settled(box);
      await box.evaluate((b) => { b.scrollLeft = 200; });
      await page.keyboard.press("Tab");
      await expect(pane.locator(":focus")).toHaveCount(1);
      expect(await settled(box), "the box did not move into the detail").toBe(200);
    }
  });
}

test("a box with nothing pinned at its right says so on its own edge, and a box that fits says nothing", async ({ page }) => {
  await test.step("reconcile", async () => {
    await open(page, "reconcile");
    const box = page.locator("#main .scroll.overflows").first();
    await expect(box, "Reconcile's table is wider than its box").toBeVisible();
    const right = () => box.evaluate((b) => {
      const s = getComputedStyle(b);
      return s.borderRightColor === "rgba(0, 0, 0, 0)" ? 0 : parseFloat(s.borderRightWidth);
    });
    const first = box.locator(":scope > table > thead > tr > :first-child");
    await expect.poll(right, "the box's right edge at rest").toBe(2);
    await expect.poll(() => edge(first), "the first column's edge at rest").toBe(1);
    await box.evaluate((b) => { b.scrollLeft = b.scrollWidth; });
    await expect.poll(right, "the box's right edge at the end").toBe(0);
    await expect.poll(() => edge(first), "the first column's edge at the end").toBe(2);
  });
  await test.step("accounts", async () => {
    await open(page, "accounts");
    const boxes = page.locator("#main .scroll");
    expect(await boxes.count(), "Accounts draws a box").toBeGreaterThan(0);
    expect(await boxes.evaluateAll((bs) => bs.filter((b) =>
      parseFloat(getComputedStyle(b).borderRightWidth) > 0 ||
      [...b.querySelectorAll(":scope > table > * > tr > *")]
        .some((c) => getComputedStyle(c).boxShadow !== "none")).length),
    "a box that fits carries no sign").toBe(0);
  });
});

// AN OPEN DETAIL LEAVES ITS TABLE'S WIDTH AS IT WAS, on the pages whose tables are narrower than
// the box, where a detail wider than its table runs past it, whole, as far as the box.
for (const name of ["performance", "accounts"]) {
  test(`${name}: an open detail leaves its table's width as it was, and runs whole as far as the box`, async ({ page }) => {
    await open(page, name);
    const rows = page.locator("#main .scroll > table > tbody > tr.has-detail:not(.detail-pane *)");
    const count = await rows.count();
    expect(count, `${name} has a row with a detail`).toBeGreaterThan(0);
    // THE ROW'S TABLE: its width, and where each of its headings starts.
    const stands = (row) => row.evaluate((r) => {
      const t = r.closest("table");
      return [t.getBoundingClientRect().width,
              ...[...t.tHead.rows[0].cells].map((c) => c.getBoundingClientRect().left)].map(Math.round);
    });
    for (let i = 0; i < count; i++) {
      const row = rows.nth(i), chevron = row.locator(".detail-toggle");
      const was = await stands(row);
      await chevron.click();
      await expect(chevron).toHaveAttribute("aria-expanded", "true");
      expect(await stands(row), `row ${i}: the table's width and its columns stay`).toEqual(was);
      // EACH PART INSIDE THE BOX, and whole: neither the pane nor its cell cuts it, and each box
      // in the detail shows its table whole, or is as wide as the box allows.
      const parts = await row.evaluate((r) => {
        const pane = r.nextElementSibling.querySelector(".detail-pane");
        const box = r.closest(".scroll");
        const edge = box.getBoundingClientRect().left + box.clientLeft + box.clientWidth;
        const most = parseFloat(getComputedStyle(pane).maxWidth);
        return {
          inside: [...pane.children].every((p) => p.getBoundingClientRect().right <= edge + 1),
          whole: [pane, pane.parentElement].every((e) => getComputedStyle(e).overflowX === "visible") &&
            [...pane.querySelectorAll(".scroll")].every((s) =>
              s.scrollWidth <= s.clientWidth + 1 || s.getBoundingClientRect().width >= most - 1),
        };
      });
      expect(parts, `row ${i}: the detail is inside the box and whole`).toEqual({ inside: true, whole: true });
      await chevron.click();
      await expect(chevron).toHaveAttribute("aria-expanded", "false");
    }
  });
}

test("a holding's detail leads to its company's life", async ({ page }) => {
  await open(page, "holdings");
  const row = page.locator("#main table[data-links] tbody tr:not(.detail-row)").first();
  await row.locator(".detail-toggle").click();
  const link = page.locator("#main .detail-row:not([hidden]) [data-life]");
  await expect(link).toHaveClass("go");
  const company = await link.getAttribute("data-life");
  // BY KEYBOARD, the company's answer held: the heading holds focus through the page's redraw.
  let release;
  const held = new Promise((r) => { release = r; });
  await page.route("**/api/round-trips?*", async (route) => { await held; await route.continue(); });
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main .page-head h1")).toBeFocused();
  release();
  await expect(page.locator("#rt-view")).toHaveValue("life");
  await expect(page.locator("#rt-company")).toHaveValue(company);
  await expect(page.locator("#main .scroll > table > tbody > tr:not(.detail-row)")).toHaveCount(1);
  await expect(page.locator("#main .page-head h1")).toBeFocused();
});
