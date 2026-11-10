// THE DESK WALKED, IN CHROMIUM: the demo desk `desk_walk.py` serves, at 1440 × 900. Each page is
// opened by its tab and must draw no error, hold no accessibility fault but the `KNOWN`, and look
// as its baseline does; a finding is followed to its page; a wide table's links are in view, and
// its detail opens in view. It writes nothing, and does not prove a figure is right.
//
//     npm ci --prefix tools && npm --prefix tools run browser      # once: Playwright, its Chromium
//     npm --prefix tools run walk
//     npm --prefix tools run walk -- --update-snapshots            # a look changed on purpose
import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { DAY } from "./playwright.config.mjs";

// THE ACCESSIBILITY FAULTS ON FILE, each an axe rule and the pages it fires on. A fault not
// listed fails, and so does a listed one that has gone: the list only shrinks.
const KNOWN = {
  "html-has-lang": ["dashboard", "bench", "price-refresh", "what-changed", "reconcile",
                    "performance", "holdings", "round-trips", "trades", "accounts", "reports",
                    "method", "access"],
  "select-name": ["bench"],
  "label": ["price-refresh"],
  "empty-table-header": ["performance", "holdings", "round-trips", "trades", "accounts", "access"],
};

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
      // The screenshot waits for the page to stop moving, so it comes before axe reads it.
      await expect.soft(page).toHaveScreenshot(`${name}.png`, {
        fullPage: true, mask: [page.locator("footer.foot")],      // the footer names the commit
      });
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

for (const name of ["holdings", "round-trips"]) {
  test(`${name}: a row's links are in view, and its detail opens in view`, async ({ page }) => {
    await open(page, name);
    const row = page.locator("#main table[data-links] tbody tr:not(.detail-row)").first();
    await expect(row.locator("[data-trades]")).toBeInViewport({ ratio: 1 });
    await expect(row.locator(".detail-toggle")).toBeInViewport({ ratio: 1 });
    await row.locator(".detail-toggle").click();
    await expect(page.locator("#main .detail-row:not([hidden]) .detail-pane > *").first())
      .toBeInViewport({ ratio: 1 });
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
