// THE TRIAL SHELL'S FOUR BEHAVIOURS, checked in Chromium against a running `trial_shell.py` on the
// demo: an address for each object, tabs that keep their place, the find field, and a menu that
// stays while the page beside it changes. It prints one line a check and exits non-zero on a miss.
//
//     PORTFUSION_BOOK=demo python3 tools/trial_shell.py 8770 &
//     node tools/trial_shell/check.mjs 8770
import { chromium } from "@playwright/test";

const B = `http://127.0.0.1:${process.argv[2] || 8770}/next`;
const results = [];
const ok = (name, pass, detail = "") => { results.push([pass ? "PASS" : "FAIL", name, detail]); };

const b = await chromium.launch();
try {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 600 } });
  const p = await ctx.newPage();
  const errs = [];
  p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  p.on("pageerror", (e) => errs.push("PAGEERROR " + e.message));
  // A WAIT THAT IS NOT MET ANSWERS FALSE, so a miss is a FAIL line and the checks after it still run.
  const title = (n) => p.waitForFunction((n) => document.querySelector("main h1")?.textContent === n, n,
    { timeout: 10000 }).then(() => true, () => false);
  const state = () => p.evaluate(() => ({
    hash: decodeURIComponent(location.hash), y: Math.round(scrollY), h1: document.querySelector("main h1")?.textContent,
    tab: document.querySelector("#tabs a[aria-current]")?.dataset.tab, rows: document.querySelectorAll("#tab tbody tr, #rows tbody tr").length,
    focus: document.activeElement?.id || document.activeElement?.dataset?.tab || document.activeElement?.tagName,
    probe: window.__probe, menuProbe: document.querySelector("#menu").dataset.probe,
    menuCurrent: document.querySelector("#menu a[aria-current]")?.textContent.trim() }));

  // 1 · AN ADDRESS FOR EACH OBJECT: opened cold, the address alone draws the company and its tab.
  await p.goto(B + "#/company/Quenlan%20Robotics%20Inc./trades"); await title("Quenlan Robotics Inc.");
  let s = await state();
  ok("1a cold address draws the company and the tab", s.h1 === "Quenlan Robotics Inc." && s.tab === "trades" && s.rows === 4, JSON.stringify(s));
  await p.reload(); await title("Quenlan Robotics Inc."); s = await state();
  ok("1b a reload lands on the same screen", s.tab === "trades" && s.rows === 4, JSON.stringify(s));
  ok("1c the tab is in the page title", (await p.title()) === "Quenlan Robotics Inc. · Trades | PortFusion", await p.title());
  await p.goto(B + "#/company/Tarnwell%20Hotels%20plc"); await title("Tarnwell Hotels plc"); s = await state();
  ok("1d a sold company has its page", s.tab === "overview", JSON.stringify(s));
  await p.goto(B + "#/company/Nobody%20plc");
  ok("1e an unknown company says so", await title("No company of that name"));
  await p.goto(B + "#/nowhere");
  ok("1f an unknown address says so", await title("No page at this address"));
  await p.goto(B + "#/companies"); await title("Companies");
  await p.goto(B + "#/constructor");
  ok("1g and so does one named as something every object has", await title("No page at this address"));
  await p.goto(B + "#/company/Quenlan%20Robotics%20Inc./nonsense"); await title("Quenlan Robotics Inc."); s = await state();
  ok("1h a tab the page does not have is the first, and the address says so", s.tab === "overview" && s.hash === "#/company/Quenlan Robotics Inc./overview", s.hash);

  // 2 · TABS THAT KEEP THEIR PLACE.
  await p.goto(B + "#/company/Quenlan%20Robotics%20Inc."); await title("Quenlan Robotics Inc.");
  await p.evaluate(() => { window.__probe = "same document"; document.querySelector("#menu").dataset.probe = "same menu";
    document.querySelector(".object-head").dataset.probe = "same head"; window.scrollTo(0, 180); });
  await p.waitForTimeout(100);
  await p.focus('#tabs a[data-tab="round-trips"]'); await p.keyboard.press("Enter"); await p.waitForTimeout(150);
  s = await state();
  const headKept = await p.evaluate(() => document.querySelector(".object-head").dataset.probe);
  ok("2a a tab changes its region only: the head is the same node", headKept === "same head");
  ok("2b the page stays where it was scrolled", s.y === 180, "y=" + s.y);
  ok("2c the tab pressed keeps the focus", s.focus === "round-trips", String(s.focus));
  ok("2d the address names the tab", s.hash === "#/company/Quenlan Robotics Inc./round-trips" && s.tab === "round-trips", s.hash);
  await p.click('#tabs a[data-tab="reasoning"]'); await p.waitForTimeout(100);
  await p.goBack(); await p.waitForTimeout(150); s = await state();
  ok("2e back returns to the tab before", s.tab === "round-trips" && s.rows === 1, JSON.stringify(s));
  await p.goForward(); await p.waitForTimeout(150); s = await state();
  ok("2f forward returns to the tab after", s.tab === "reasoning", JSON.stringify(s));

  // 4 · A MENU THAT STAYS while the page beside it changes (checked here, on the same document).
  await p.click(".trail a"); await p.waitForSelector("#rows table"); s = await state();
  ok("4a the menu is the same node after three page changes", s.menuProbe === "same menu" && s.probe === "same document", JSON.stringify(s));
  ok("4b the menu marks the page", s.menuCurrent.startsWith("Companies"), s.menuCurrent);
  ok("4c a link opens a page at its top, the reader at its heading", s.y === 0 && s.focus === "H1", JSON.stringify(s));

  // 3 · THE FIND FIELD.
  await p.evaluate(() => { document.querySelector("#find").dataset.probe = "same box"; });
  await p.click("#find"); await p.keyboard.type("qn", { delay: 40 }); s = await state();
  const box = await p.evaluate(() => { const f = document.querySelector("#find"); return { probe: f.dataset.probe, value: f.value, caret: f.selectionStart, focused: document.activeElement === f }; });
  ok("3a typing narrows the list by ticker", s.rows === 1, "rows=" + s.rows);
  ok("3b the box keeps the focus and the caret", box.focused && box.caret === 2 && box.probe === "same box", JSON.stringify(box));
  ok("3c the address carries the search", s.hash === "#/companies?find=qn", s.hash);
  const chips = await p.evaluate(() => [...document.querySelectorAll("#shows a")].map((a) => a.textContent.trim()));
  ok("3d each choice counts what the search leaves", chips.join("|") === "Held · 1|Sold · 0|All · 1", chips.join("|"));
  await p.keyboard.press("Backspace"); await p.keyboard.press("Backspace"); await p.keyboard.type("tarn");
  await p.click('#shows a[data-show="sold"]'); await p.waitForTimeout(100); s = await state();
  ok("3e a choice keeps the search", s.hash === "#/companies?show=sold&find=tarn" && s.rows === 1, s.hash + " rows=" + s.rows);
  await p.click(".row-link"); await title("Tarnwell Hotels plc");
  await p.goBack(); await p.waitForSelector("#rows"); await p.waitForTimeout(700); s = await state();
  const again = await p.evaluate(() => document.querySelector("#find")?.value);
  ok("3f back returns to the list as it was searched", s.hash === "#/companies?show=sold&find=tarn" && again === "tarn" && s.rows === 1, s.hash + " box=" + again + " rows=" + s.rows);
  await p.reload(); await p.waitForSelector("#rows table"); s = await state();
  ok("3g a reload keeps the search", (await p.evaluate(() => document.querySelector("#find").value)) === "tarn" && s.rows === 1);
  await p.fill("#find", "zzz"); s = await state();
  ok("3h nothing found says so", (await p.textContent("#rows")).includes("No company sold matches “zzz”."), await p.textContent("#rows"));
  await p.fill("#find", "TARN.L"); s = await state();
  ok("3i a sold company is found by its ticker", s.rows === 1, "rows=" + s.rows);
  await p.goto(B + "#/companies"); await p.reload(); await p.waitForSelector("#rows table");
  await p.click("#shows a[data-show=\"all\"]"); await p.click("#find"); await p.keyboard.type("tarn");
  await p.goBack(); await p.waitForTimeout(150); s = await state();
  const left = await p.evaluate(() => document.querySelector("#find").value);
  ok("3j back puts the address's own search in the box, focused or not", s.hash === "#/companies" && left === "" && s.rows === 4, s.hash + " box=" + left + " rows=" + s.rows);

  // 5 · WHERE A PAGE WAS SCROLLED TO. A press here is the page's own `click()`, which does not
  // scroll the link into view first as Playwright's would; a reader presses what they can see.
  const press = (sel) => p.evaluate((sel) => document.querySelector(sel).click(), sel);
  const company = (n) => `#rows a[href="#/company/${encodeURIComponent(n)}"]`;
  const settle = async (heading) => { const met = await title(heading); await p.waitForTimeout(200); return met; };
  await p.setViewportSize({ width: 1280, height: 300 });
  await p.goto(B + "#/companies?show=all"); await p.reload(); await p.waitForSelector("#rows table");
  await p.evaluate(() => window.scrollTo(0, 140)); await p.waitForTimeout(100);
  await press(company("Kelstrand Foods plc")); await settle("Kelstrand Foods plc"); s = await state();
  ok("5a a page opened by a link starts at its top", s.y === 0, "y=" + s.y);
  await p.goBack(); await settle("Companies"); s = await state();
  ok("5b back puts the list where it was scrolled", s.y === 140, "y=" + s.y);
  await press(company("Quenlan Robotics Inc.")); await settle("Quenlan Robotics Inc.");
  await p.evaluate(() => window.scrollTo(0, 160)); await p.waitForTimeout(100);
  await press("#tabs a[data-tab=\"trades\"]"); await p.waitForTimeout(100);
  await press("#menu a[data-page=\"companies\"]"); await settle("Companies");
  await p.goBack(); await settle("Quenlan Robotics Inc."); s = await state();
  ok("5c back puts a page where it was left after a tab was pressed", s.y === 160 && s.tab === "trades", "y=" + s.y + " tab=" + s.tab);
  await p.reload(); await settle("Quenlan Robotics Inc."); s = await state();
  ok("5d a reload lands where the page was left", s.y === 160 && s.tab === "trades", "y=" + s.y + " tab=" + s.tab);
  await p.goBack(); await p.goBack(); await settle("Companies"); s = await state();
  ok("5e and after it, back still finds the page behind where it was left", s.y === 140, "y=" + s.y + " " + s.hash);
  await press(company("Quenlan Robotics Inc.")); await settle("Quenlan Robotics Inc."); s = await state();
  ok("5f a page opened by a link again starts at its top, not where it was once left", s.y === 0, "y=" + s.y);
  await p.evaluate(() => window.scrollTo(0, 80)); await p.waitForTimeout(100);
  await press("#menu a[data-page=\"companies\"]"); await settle("Companies");
  await p.goBack(); await settle("Quenlan Robotics Inc."); s = await state();
  ok("5g and back to it finds that visit's place", s.y === 80, "y=" + s.y);
  await p.goForward(); await settle("Companies");
  await p.evaluate(() => window.scrollTo(0, 60)); await p.waitForTimeout(100);
  await p.goBack(); await settle("Quenlan Robotics Inc."); await p.goBack(); await settle("Companies"); s = await state();
  ok("5h two steps that show one page keep a place each", s.y === 140 && s.hash === "#/companies?show=all", "y=" + s.y + " " + s.hash);
  await p.evaluate(() => { location.hash = "#/company/" + encodeURIComponent("Kelstrand Foods plc"); }); await settle("Kelstrand Foods plc");
  await p.evaluate(() => { location.hash = "#/companies?show=all"; }); await settle("Companies"); s = await state();
  ok("5i an address opened afresh starts at its top", s.y === 0, "y=" + s.y);
  await p.evaluate(() => window.scrollTo(0, 120)); await p.waitForTimeout(100);
  await press("#menu a.old[href=\"/#trades\"]"); await p.waitForURL(/\/#trades$/);
  // THE DOCUMENT IS LOADED AGAIN on the way back: Playwright's Chromium keeps no page to restore.
  await p.goBack(); await settle("Companies"); s = await state();
  ok("5j the way back from today's desk lands where the page was left", s.y === 120, "y=" + s.y);
  await p.goBack(); await settle("Kelstrand Foods plc"); await p.goBack(); await settle("Companies"); s = await state();
  ok("5k and the pages behind it are where they were left too", s.y === 140, "y=" + s.y + " " + s.hash);
  await p.goForward(); await settle("Kelstrand Foods plc"); await p.goForward(); await settle("Companies");
  await p.evaluate(() => history.go(-2)); await p.waitForTimeout(300); s = await state();
  ok("5n a jump between two steps at one address finds the earlier step's place", s.y === 140 && s.hash === "#/companies?show=all", "y=" + s.y + " " + s.hash);
  await p.evaluate(() => { window.scrollTo(0, 180); document.querySelector("#rows a.row-link").click(); });
  await p.waitForFunction(() => document.querySelector(".object-head")); await p.waitForTimeout(200);
  await p.goBack(); await settle("Companies"); s = await state();
  ok("5o a scroll and a press in one moment still keeps the place", s.y === 180, "y=" + s.y);
  await p.evaluate(() => { location.hash = "#/company/" + encodeURIComponent("Veldrome Metals Inc."); });
  await p.waitForTimeout(30);
  await p.evaluate(() => { location.hash = "#/company/" + encodeURIComponent("Bryncoed Minerals plc"); });
  await title("Bryncoed Minerals plc"); await p.waitForTimeout(1500); s = await state();
  ok("5l the latest page asked for is the one drawn", s.h1 === "Bryncoed Minerals plc", s.h1);
  await p.goto(B + "#/company/Quenlan%20Robotics%20Inc./trades/more"); await settle("Quenlan Robotics Inc."); s = await state();
  ok("5m a step past the tab is taken off the address", s.hash === "#/company/Quenlan Robotics Inc./trades" && s.tab === "trades", s.hash);
  await p.evaluate(() => window.scrollTo(0, 150)); await p.waitForTimeout(100);
  await p.evaluate(() => { location.hash = "#/company/" + encodeURIComponent("Quenlan Robotics Inc.") + "/trades/again"; });
  await p.waitForTimeout(200); await p.evaluate(() => window.scrollTo(0, 60)); await p.waitForTimeout(100);
  await p.goBack(); await p.waitForTimeout(300); s = await state();
  ok("5p back between two steps the shell put at one address finds the earlier place", s.y === 150, "y=" + s.y + " " + s.hash);
  await p.goto(B + "#/"); await settle("Companies"); s = await state();
  ok("5q an address that names no step is the first page's", s.hash === "#/companies" && s.rows === 4, s.hash);
  await p.evaluate(() => document.querySelector("#rows tbody tr td.num").click()); await settle("Veldrome Metals Inc."); s = await state();
  ok("5r a press anywhere on a row opens its company", s.h1 === "Veldrome Metals Inc.", s.h1);

  // 6 · THE NARROW WINDOW, and nothing refused by the page's own rules.
  await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(100);
  const folded = await p.evaluate(() => getComputedStyle(document.querySelector("#menu")).display);
  await p.click("#menu-toggle");
  const opened = await p.evaluate(() => getComputedStyle(document.querySelector("#menu")).display);
  ok("6a the menu folds behind one button on a phone", folded === "none" && opened === "flex", folded + " → " + opened);
  await p.goto(B + "#/companies"); await p.waitForSelector("#rows table"); await p.click("#menu-toggle");
  await p.click("#menu a[data-page=\"companies\"]"); await p.waitForTimeout(150);
  const refolded = await p.evaluate(() => getComputedStyle(document.querySelector("#menu")).display);
  ok("6c the open page's own entry folds the menu again", refolded === "none", refolded);
  const wide = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok("6b the page does not scroll sideways on a phone", wide === 0, "overflow " + wide);
  ok("7 no script error and nothing refused by the content policy", errs.length === 0, errs.join(" | "));
} catch (e) {
  ok("the walk ran to its end", false, e.message.split("\n")[0]);
} finally {
  await b.close();
}
for (const r of results) console.log(r.join("  "));
const missed = results.filter((r) => r[0] === "FAIL").length;
console.log(`${results.length - missed} of ${results.length} pass`);
process.exit(missed ? 1 : 0);
