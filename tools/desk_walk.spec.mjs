// THE DESK WALKED, IN CHROMIUM: the demo desk `desk_walk.py` serves, at 1440 × 900. Each page is
// opened by its tab and must draw no error, hold no accessibility fault but the `KNOWN`, and look
// as its baseline does; a finding is followed to its page; a wide table's button to Trades is in
// view, a press on a row opens its detail in view, and a heading that sorts shows it; an open
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

test("each page opens, holds no new accessibility fault and looks as it did", async ({ page }) => {
  const names = await page.locator("#tabs button").evaluateAll((bs) => bs.map((b) => b.dataset.name));
  const faults = {};
  for (const name of names) {
    await test.step(name, async () => {
      await open(page, name);
      await expect.soft(page.locator("pre.error:visible"), `${name} drew an error`).toHaveCount(0);
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

// THE FOCUSABLE ELEMENTS a Tab can reach, in the page: what the walk asks a Tab to land on.
const TABBABLE = "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), " +
  "select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex='-1'])";
// WHERE A BOX STANDS once the page has had two frames to scroll it.
const settled = (box) => box.evaluate((b) => new Promise((done) =>
  requestAnimationFrame(() => requestAnimationFrame(() => done(b.scrollLeft)))));
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
    const box = page.locator("#main .scroll:has(> table[data-links])").first();
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
