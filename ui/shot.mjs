import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const OUT = "C:\\Users\\marou\\WebstormProjects\\medical-office\\ui\\.shots";
mkdirSync(OUT, { recursive: true });

const BASE = "http://127.0.0.1:1420/#";
const routes = [
  ["tableau-de-bord", "/tableau-de-bord"],
  ["patients", "/patients"],
  ["patient-detail", "/patients/1"],
  ["finances", "/finances"],
  ["travaux", "/travaux"],
  ["job-detail", "/travaux/jobs/2"],
  ["prestataires", "/prestataires"],
  ["prestataire-detail", "/prestataires/1"],
  ["parametrage", "/parametrage"],
];

const VIEWPORT = { width: 1440, height: 900 };

const browser = await chromium.launch({ channel: "chrome", headless: true });
const ctx = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
const page = await ctx.newPage();

const report = [];
for (const [name, route] of routes) {
  const url = BASE + route;
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
  } catch (e) {
    // networkidle may not settle if SSE/polling; fall back
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
  }
  await page.waitForTimeout(1500); // let data + layout settle

  // Detect horizontal overflow against the viewport
  const overflow = await page.evaluate((vw) => {
    const issues = [];
    const docW = document.documentElement.scrollWidth;
    const all = document.querySelectorAll("*");
    for (const el of all) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      // element extends past the right viewport edge by > 2px
      if (r.right > vw + 2) {
        const cs = getComputedStyle(el);
        if (cs.position === "fixed") continue;
        issues.push({
          tag: el.tagName.toLowerCase(),
          cls: (el.className && el.className.toString().slice(0, 80)) || "",
          right: Math.round(r.right),
          width: Math.round(r.width),
          text: (el.textContent || "").trim().slice(0, 40),
        });
      }
    }
    // dedupe-ish: keep the 15 widest
    issues.sort((a, b) => b.right - a.right);
    return { docW, viewport: vw, overflowing: issues.slice(0, 15) };
  }, VIEWPORT.width);

  const file = `${OUT}\\${name}.png`;
  await page.screenshot({ path: file, fullPage: true });
  report.push({ name, route, ...overflow, file });
  console.log(`OK ${name} -> docW=${overflow.docW} vw=${overflow.viewport} overflow=${overflow.overflowing.length}`);
}

console.log("\n===REPORT JSON===");
console.log(JSON.stringify(report, null, 1));

await browser.close();
