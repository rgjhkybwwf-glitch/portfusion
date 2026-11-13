// THE DESK WALKED, IN CHROMIUM: the demo desk `desk_walk.py` serves, at 1440 × 900. Each page is
// opened by its tab and must draw no error, hold no accessibility fault but the `KNOWN`, and look
// as its baseline does; a finding is followed to its page; a wide table's button to Trades is in
// view, a press on a row opens its detail in view, and a heading that sorts shows it. It writes
// nothing, and does not prove a figure is right.
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
  });
}

test("a holding's detail leads to its company's life", async ({ page }) => {
  await open(page, "holdings");
  const row = page.locator("#main table[data-links] tbody tr:not(.detail-row)").first();
  await row.locator(".detail-toggle").click();
  const link = page.locator("#main .detail-row:not([hidden]) [data-life]");
  const company = await link.getAttribute("data-life");
  await link.click();
  await expect(page.locator("#rt-view")).toHaveValue("life");
  await expect(page.locator("#rt-company")).toHaveValue(company);
  await expect(page.locator("#main .scroll > table > tbody > tr:not(.detail-row)")).toHaveCount(1);
});
