// THE DESK DRAWN, IN NODE: the page and its script from `desk_smoke.py`'s answers loaded into
// jsdom, every fetch answered from them, then each panel's tab clicked in turn. Fails on any error,
// rejected promise, error box or unanswered fetch, at start-up and on each panel. It checks that a
// page draws, not that its figures are right, and clicks nothing inside a page.
//
//     npm ci --prefix tools                     # once: jsdom
//     python3 tools/desk_smoke.py answers.json && node tools/desk_smoke.mjs answers.json
import { JSDOM, VirtualConsole } from "jsdom";
import { readFileSync } from "node:fs";

const ORIGIN = "http://127.0.0.1:8765";
const answers = JSON.parse(readFileSync(process.argv[2], "utf8"));
const problems = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => problems.push(`jsdom: ${e.message}`));
vc.on("error", (...a) => problems.push(`console.error: ${a.join(" ")}`));

// "outside-only": the page's own <script> tag never runs, so the script runs once, by eval below.
const script = answers[answers["/"].script].body;
const dom = new JSDOM(answers["/"].body, { url: `${ORIGIN}/`, runScripts: "outside-only",
                                           pretendToBeVisual: true, virtualConsole: vc });
const w = dom.window, doc = w.document;
w.scrollTo = () => {};                       // jsdom lays nothing out, so has nothing to scroll
w.fetch = async (url, opts = {}) => {
  const method = opts.method ?? "GET", path = String(url).replace(ORIGIN, "");
  const a = method === "GET" && answers[path];
  if (!a) problems.push(`not recorded: ${method} ${path}`);
  return new Response(a ? a.body : '{"detail":"not recorded"}', { status: a ? a.status : 404 });
};
w.addEventListener("error", (e) => problems.push(`error: ${e.message}`));
w.addEventListener("unhandledrejection", (e) => problems.push(`rejection: ${e.reason?.stack ?? e.reason}`));
// A draw is done once the page has been still for 100 ms (5 s at most), however slow the machine.
const settle = () => new Promise((done) => {
  let quiet;
  const stop = () => { seen.disconnect(); clearTimeout(cap); clearTimeout(quiet); done(); };
  const calm = () => { clearTimeout(quiet); quiet = setTimeout(stop, 100); };
  const seen = new w.MutationObserver(calm), cap = setTimeout(stop, 5000);
  seen.observe(doc, { subtree: true, childList: true, attributes: true, characterData: true });
  calm();
});
const errorBox = (where) => {
  const box = doc.querySelector("pre.error:not([hidden])");
  if (box) problems.push(`${where}: drew an error: ${box.textContent.slice(0, 200)}`);
};

try { w.eval(script); } catch (e) { problems.push(`load: ${e.stack ?? e}`); }
await settle();
errorBox("start");
if (problems.length) problems.push("  ^ at start-up");

const panels = JSON.parse(answers["/api/state"].body).panels.map((p) => p.name);
const drawn = [];
for (const name of panels) {
  const before = problems.length;
  const tab = [...doc.querySelectorAll("#tabs button")].find((b) => b.dataset.name === name);
  if (tab) tab.click(); else problems.push(`${name}: no tab`);
  await settle();
  if (w.location.hash !== `#${name}`) problems.push(`${name}: its tab did not open it`);
  errorBox(name);
  if (problems.length === before) drawn.push(name);
  else problems.push(`  ^ while drawing ${name}`);
}
console.log(`drawn ${drawn.length}/${panels.length}: ${drawn.join(", ")}`);
for (const p of problems) console.log(`PROBLEM ${p}`);
process.exit(problems.length ? 1 : 0);
