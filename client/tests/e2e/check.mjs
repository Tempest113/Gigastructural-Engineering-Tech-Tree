#!/usr/bin/env node
// Committed version of the per-session headless Playwright check (Item 2, client
// test-infrastructure task): 0 console errors, 0 failed requests, 0 invariant violations across
// the six checks main.ts's own `window.__tt` test-hook API already exposes for exactly this
// (name-bounds, indicator-bounds, gate-label-bounds, edge-containment, min-stub, tier-badge).
// This had been run by hand every session and never committed before now.
//
// **LOCAL-ONLY, like tools/build_dataset.py -- never run in CI.** It needs the FULL real dataset
// (`client/public/dataset/`, D-15-gated: requires vendor/ populated, which requires a Steam
// account) served by a real running dev/preview server. See this directory's README.md for the
// full prerequisite/run steps. `playwright` is deliberately NOT a client/package.json
// devDependency -- `npm ci` (what CI runs) must never try to install a browser download for a
// check CI can never run; install it yourself once (see README.md) before using this script.
//
// Run: `node tests/e2e/check.mjs [baseUrl]` (baseUrl defaults to http://localhost:5173).

import { setTimeout as sleep } from "node:timers/promises";

const BASE_URL = process.argv[2] ?? "http://localhost:5173";

// The six invariant checks named in this task, mapped to their real window.__tt method names
// (client/src/main.ts's own test-hook API -- see that file's `(window as ...).__tt = {` block).
const INVARIANT_CHECKS = [
  ["name-bounds", "checkNameBounds"],
  ["indicator-bounds", "checkIndicatorBounds"],
  ["gate-label-bounds", "checkGateLabelFontAndCollision"],
  ["edge-containment", "checkEdgeEndpointsInCards"],
  ["min-stub", "checkMinStubLength"],
  ["tier-badge", "checkTierBadgeMatchesBand"],
];

async function main() {
  let playwright;
  try {
    playwright = await import("playwright");
  } catch {
    console.error(
      "playwright is not installed. This is a LOCAL-ONLY check (see tests/e2e/README.md) -- " +
        "run `npm install -D playwright && npx playwright install chromium` once, then re-run this script."
    );
    process.exitCode = 1;
    return;
  }

  const consoleErrors = [];
  const failedRequests = [];

  const browser = await playwright.chromium.launch();
  const page = await browser.newPage();
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("requestfailed", (req) => {
    failedRequests.push(`${req.method()} ${req.url()} -- ${req.failure()?.errorText ?? "unknown error"}`);
  });
  page.on("pageerror", (err) => {
    consoleErrors.push(`pageerror: ${err.message}`);
  });

  console.log(`Loading ${BASE_URL} ...`);
  try {
    await page.goto(BASE_URL, { waitUntil: "load", timeout: 30000 });
  } catch (err) {
    console.error(`Failed to load ${BASE_URL}: ${err.message}`);
    console.error("Is a dev/preview server running? See tests/e2e/README.md.");
    await browser.close();
    process.exitCode = 1;
    return;
  }

  // window.__tt is installed once initial render completes -- poll rather than a fixed sleep.
  const ttReady = await page.waitForFunction(() => Boolean(window.__tt), { timeout: 30000 }).then(
    () => true,
    () => false
  );
  if (!ttReady) {
    console.error("window.__tt never appeared -- the app failed to render (see console errors below).");
  }
  // A settle window for any async work (icon atlas fetch, LOD update) that could still throw or
  // fail a request just after window.__tt is installed.
  await sleep(1000);

  const report = { consoleErrors: [...consoleErrors], failedRequests: [...failedRequests], invariants: {} };
  let anyFailed = consoleErrors.length > 0 || failedRequests.length > 0 || !ttReady;

  if (ttReady) {
    for (const [label, method] of INVARIANT_CHECKS) {
      const result = await page.evaluate((m) => window.__tt[m](), method);
      const ok = result?.ok === true;
      report.invariants[label] = result;
      if (!ok) anyFailed = true;
    }
  }

  await browser.close();

  console.log(`\nConsole errors: ${report.consoleErrors.length}`);
  for (const e of report.consoleErrors) console.log(`  ${e}`);
  console.log(`Failed requests: ${report.failedRequests.length}`);
  for (const r of report.failedRequests) console.log(`  ${r}`);
  console.log("\nInvariant checks:");
  for (const [label] of INVARIANT_CHECKS) {
    const r = report.invariants[label];
    if (!r) {
      console.log(`  ${label}: SKIPPED (window.__tt never appeared)`);
      continue;
    }
    const count = r.violations?.length ?? 0;
    console.log(`  ${label}: ${r.ok ? "OK" : `FAILED (${count} violation(s))`}${r.checked !== undefined ? ` [checked ${r.checked}]` : ""}`);
    if (!r.ok) {
      for (const v of (r.violations ?? []).slice(0, 10)) console.log(`    ${JSON.stringify(v)}`);
      if (count > 10) console.log(`    ... and ${count - 10} more`);
    }
  }

  if (anyFailed) {
    console.error("\nFAILED -- see above.");
    process.exitCode = 1;
  } else {
    console.log("\nOK -- 0 console errors, 0 failed requests, 0 invariant violations.");
  }
}

await main();
