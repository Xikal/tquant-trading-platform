import { chromium } from "playwright";
import { URL } from "node:url";
import { resolve } from "node:path";
import { authStatusFromEnv, detectAuthGate, ensureAccessToken, installAuthState, startServer, stopServer } from "./script-utils.mjs";

const pagePairs = [
  ["/monitor", "/next/monitor"],
  ["/monitor/market", "/next/monitor/market"],
  ["/paper", "/next/paper"],
  ["/strategy-tracking", "/next/strategy-tracking"],
  ["/analysis", "/next/analysis"],
  ["/playbook", "/next/playbook"],
  ["/backtest", "/next/backtest"],
  ["/data", "/next/data"],
  ["/settings", "/next/settings"],
];

const nextRouteBudgets = new Map([
  ["/next/monitor", { maxApi: 2, maxUniqueApi: 2, maxEventSource: 0 }],
  ["/next/monitor/market", { maxApi: 2, maxUniqueApi: 2, maxEventSource: 0 }],
  ["/next/paper", { maxApi: 2, maxUniqueApi: 2, maxEventSource: 0 }],
  ["/next/strategy-tracking", { maxApi: 2, maxUniqueApi: 2, maxEventSource: 0, forbiddenApiPathIncludes: ["/api/strategy-tracking/items", "/api/strategy-tracking/summary", "/api/strategy-tracking/performance"] }],
  ["/next/analysis", { maxApi: 1, maxUniqueApi: 1, maxEventSource: 0 }],
  ["/next/playbook", { maxApi: 6, maxUniqueApi: 6, maxEventSource: 0 }],
  ["/next/backtest", { maxApi: 2, maxUniqueApi: 2, maxEventSource: 0 }],
  ["/next/data", { maxApi: 1, maxUniqueApi: 1, maxEventSource: 0 }],
  ["/next/settings", { maxApi: 2, maxUniqueApi: 2, maxEventSource: 0 }],
]);

const shouldStartLegacy = process.env.START_LEGACY_FRONTEND === "1";
const oldBaseURL = process.env.LEGACY_FRONTEND_URL || null;
const tracePort = Number(process.env.FRONTEND_NEXT_TRACE_PORT || 5177);
const apiBase = process.env.API_BASE || "http://127.0.0.1:8000";

async function main() {
  const server = process.env.FRONTEND_NEXT_URL
    ? null
    : await startServer(tracePort, {
        env: { FRONTEND_NEXT_API_TARGET: process.env.FRONTEND_NEXT_API_TARGET || apiBase },
      });
  const legacyServer = oldBaseURL || !shouldStartLegacy ? null : await startServer(5178, { cwd: resolve("../frontend") });
  const nextBaseURL = process.env.FRONTEND_NEXT_URL || server.baseURL;
  const legacyBaseURL = oldBaseURL || legacyServer?.baseURL || null;
  await ensureAccessToken(apiBase);
  const browser = await chromium.launch();
  try {
    const results = [];
    for (const [legacyRoute, nextRoute] of pagePairs) {
      const legacyTrace = legacyBaseURL ? await traceRoute(browser, `${legacyBaseURL}${legacyRoute}`) : null;
      const nextTrace = await traceRoute(browser, `${nextBaseURL}${nextRoute}`);
      results.push({ legacyRoute, nextRoute, legacyTrace, nextTrace, delta: compareTrace(legacyTrace, nextTrace), budget: checkRouteBudget(nextRoute, nextTrace) });
    }
    const failed = results.filter((item) => item.nextTrace?.navigation_error || !item.budget.ok);
    const report = {
      ok: failed.length === 0,
      oldBaseURL: legacyBaseURL,
      nextBaseURL,
      auth_status: authStatusFromEnv(),
      summary: {
        route_count: results.length,
        failed_count: failed.length,
      },
      results,
    };
    console.log(JSON.stringify(report, null, 2));
    if (!report.ok) process.exit(1);
  } finally {
    await browser.close();
    stopServer(legacyServer);
    stopServer(server);
  }
}

async function traceRoute(browser, url) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await installAuthState(page);
  await installEventSourceCounter(page);
  const requests = [];
  const onRequest = (request) => {
    const requestUrl = request.url();
    const parsed = new URL(requestUrl);
    if (parsed.pathname.startsWith("/api/")) requests.push(requestUrl);
  };
  page.on("request", onRequest);
  const started = Date.now();
  let navigationError = null;
  try {
    await page
      .goto(url, { waitUntil: "domcontentloaded", timeout: 10_000 })
      .catch((error) => {
        navigationError = error instanceof Error ? error.message : String(error);
      });
    await page.waitForLoadState("networkidle", { timeout: 1_500 }).catch(() => undefined);
    navigationError = navigationError || (await detectAuthGate(page));
    const eventSourceCount = await page.evaluate(() => window.__eventSourceCount || 0).catch(() => 0);
    return {
      elapsed_ms: Date.now() - started,
      final_url: page.url(),
      navigation_error: navigationError,
      api_request_count: requests.length,
      unique_api_request_count: new Set(requests).size,
      event_source_count: eventSourceCount,
      requests,
    };
  } finally {
    page.off("request", onRequest);
    await context.close();
  }
}

function compareTrace(legacyTrace, nextTrace) {
  if (!legacyTrace) return { status: "legacy-not-run" };
  return {
    status: "compared",
    api_request_delta: nextTrace.api_request_count - legacyTrace.api_request_count,
    unique_api_request_delta: nextTrace.unique_api_request_count - legacyTrace.unique_api_request_count,
    event_source_delta: nextTrace.event_source_count - legacyTrace.event_source_count,
  };
}

function checkRouteBudget(route, trace) {
  const budget = nextRouteBudgets.get(route);
  if (!budget || !trace) return { ok: true, status: "not-configured" };
  const violations = [];
  if (trace.api_request_count > budget.maxApi) violations.push(`api_request_count ${trace.api_request_count} > ${budget.maxApi}`);
  if (trace.unique_api_request_count > budget.maxUniqueApi) violations.push(`unique_api_request_count ${trace.unique_api_request_count} > ${budget.maxUniqueApi}`);
  if (trace.event_source_count > budget.maxEventSource) violations.push(`event_source_count ${trace.event_source_count} > ${budget.maxEventSource}`);
  for (const forbidden of budget.forbiddenApiPathIncludes ?? []) {
    if (trace.requests.some((requestUrl) => new URL(requestUrl).pathname.includes(forbidden))) {
      violations.push(`forbidden api path matched ${forbidden}`);
    }
  }
  return {
    ok: violations.length === 0,
    status: violations.length ? "failed" : "ok",
    ...budget,
    violations,
  };
}

async function installEventSourceCounter(page) {
  await page.addInitScript(() => {
    window.__eventSourceCount = 0;
    const NativeEventSource = window.EventSource;
    if (NativeEventSource) {
      window.EventSource = class CountingEventSource extends NativeEventSource {
        constructor(...args) {
          window.__eventSourceCount = (window.__eventSourceCount || 0) + 1;
          super(...args);
        }
      };
    }
  });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
