import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { URL } from "node:url";
import { authStatusFromEnv, installAuthState, startServer, stopServer } from "./script-utils.mjs";

const routes = ["/next/monitor", "/next/monitor/market", "/next/paper", "/next/strategy-tracking"];
const ownsServer = !process.env.FRONTEND_NEXT_URL;
const baseURL = process.env.FRONTEND_NEXT_URL || "http://127.0.0.1:5175";
const reportPath = resolve("../docs/reports/frontend-next-perf-compare-2026-06-08.json");

async function main() {
  const server = ownsServer ? await startServer(5175) : null;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const authStatus = await installAuthState(page);
  const results = [];
  for (const route of routes) {
    const apiRequests = [];
    let strategyItems422Count = 0;
    const onRequest = (request) => {
      const path = pathname(request.url());
      if (path.startsWith("/api/")) apiRequests.push(request.url());
    };
    const onResponse = (response) => {
      const path = pathname(response.url());
      if (path.includes("/api/strategy-tracking/items") && response.status() === 422) {
        strategyItems422Count += 1;
      }
    };
    page.on("request", onRequest);
    page.on("response", onResponse);
    const started = Date.now();
    try {
      await page.goto(`${baseURL}${route}`, { waitUntil: "networkidle" }).catch(() => undefined);
      results.push({
        route,
        elapsed_ms: Date.now() - started,
        dom_nodes: await page.locator("*").count().catch(() => 0),
        dom_breakdown: await domBreakdown(page, route),
        api_request_count: apiRequests.length,
        unique_api_request_count: new Set(apiRequests).size,
        api_requests: apiRequests,
        strategy_items_422_count: strategyItems422Count,
        telemetry: await page.evaluate(() => window.__FRONTEND_NEXT_TELEMETRY__?.()).catch(() => null),
        note: "local shadow profile; backend/API availability may affect networkidle",
      });
    } finally {
      page.off("request", onRequest);
      page.off("response", onResponse);
    }
  }
  await browser.close();
  stopServer(server);
  const report = {
    generated_at: new Date().toISOString(),
    baseURL,
    auth_status: authStatusFromEnv(),
    authStatus,
    results,
    strategy_tracking: strategyEvidence(results),
    paper: paperEvidence(results),
  };
  mkdirSync(resolve("../docs/reports"), { recursive: true });
  writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

async function domBreakdown(page, route) {
  if (route !== "/next/paper") return null;
  const entries = [
    ["mecha_descendants", ".paper-mecha-action-panel *"],
    ["page_descendants", ".paper-console-page *"],
    ["page_non_mecha_descendants", ".paper-console-page *:not(.paper-mecha-action-panel):not(.paper-mecha-action-panel *)"],
    ["workflow_lazy_descendants", ".paper-workflow-lazy *"],
    ["workflow_panel_descendants", ".paper-workflow-panel *"],
  ];
  const result = {};
  for (const [key, selector] of entries) {
    result[key] = await page.locator(selector).count().catch(() => 0);
  }
  return result;
}

function strategyEvidence(results) {
  const route = results.find((item) => item.route === "/next/strategy-tracking") || {};
  return {
    elapsed_ms: route.elapsed_ms,
    api_request_count: route.api_request_count,
    items_422_count: route.strategy_items_422_count,
    forbidden_legacy_requests: (route.api_requests || []).filter((requestUrl) =>
      pathname(requestUrl).includes("/api/strategy-tracking/items")
    ),
    telemetry: route.telemetry || {},
  };
}

function paperEvidence(results) {
  const route = results.find((item) => item.route === "/next/paper") || {};
  const breakdown = route.dom_breakdown || {};
  return {
    elapsed_ms: route.elapsed_ms,
    dom_nodes: route.dom_nodes,
    non_mecha_descendants: breakdown.page_non_mecha_descendants,
    mecha_descendants: breakdown.mecha_descendants,
    workflow_panel_descendants: breakdown.workflow_panel_descendants,
  };
}

function pathname(rawUrl) {
  try {
    return new URL(rawUrl).pathname;
  } catch {
    return "";
  }
}
