import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { mockStrategyMeta, mockUser, now } from "./smoke-responsive-fixtures.mjs";

const baseUrl = (process.env.FRONTEND_SMOKE_URL || "http://127.0.0.1:4173").replace(/\/$/, "");
const scenario = process.env.MONITOR_BFF_SMOKE_SCENARIO || "ok";
const reportPath = resolve("dist", "monitor-bff-smoke-report.json");

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: "block" });
const page = await context.newPage();
const requests = [];
const errors = [];

page.on("request", (request) => {
  const url = new URL(request.url());
  if (url.pathname.startsWith("/api/")) {
    requests.push(url.pathname);
  }
});
page.on("pageerror", (error) => errors.push(String(error.message || error)));

await page.addInitScript(() => {
  localStorage.setItem("tquant:auth:persistence_mode", "session");
  sessionStorage.setItem("tquant:auth:access_token", "smoke-token");
});

await page.route("**/api/**", async (route) => {
  const url = new URL(route.request().url());
  const path = url.pathname.replace(/^\/api/, "");
  const json = (body, status = 200) => route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(body),
  });

  if (scenario === "auth" && (path === "/auth/me" || path === "/auth/refresh")) {
    return json({ detail: "unauthorized" }, 401);
  }
  if (path === "/auth/me") return json({ user: mockUser });
  if (path === "/auth/refresh") return json({ access_token: "smoke-token", refresh_token: "smoke-refresh", token_type: "bearer", expires_in: 3600, user: mockUser });
  if (path === "/strategies/meta") return json({ strategies: mockStrategyMeta });
  if (path === "/strategy/presets") return json({ presets: [] });
  if (path === "/bff/v1/workspace/monitor") {
    if (scenario === "500") return json({ detail: "transient failure" }, 500);
    return json(monitorWorkspacePayload());
  }
  if (path === "/monitor/snapshot" || path.startsWith("/screeners/low-buy") || path.startsWith("/market/")) {
    return json({ detail: `legacy endpoint should not be requested: ${path}` }, 418);
  }
  return json({});
});

await page.goto(`${baseUrl}/monitor`, { waitUntil: "networkidle", timeout: 20_000 });
await waitForScenarioSignal(page);

const bodyText = await page.locator("body").innerText().catch(() => "");
const bffCount = requests.filter((item) => item === "/api/bff/v1/workspace/monitor").length;
const legacyMonitorCount = requests.filter((item) => item === "/api/monitor/snapshot" || item.startsWith("/api/screeners/low-buy") || item.startsWith("/api/market/")).length;
const loginVisible = bodyText.includes("登录进入工作台") || bodyText.includes("账号");
const retryVisible = bodyText.includes("加载失败，正在重试") || bodyText.includes("已保留上次可用数据");

const ok = scenario === "auth"
  ? loginVisible && bffCount === 0
  : scenario === "500"
    ? bffCount >= 1 && retryVisible
    : bffCount === 1 && legacyMonitorCount === 0 && !retryVisible && bodyText.includes("实时监控");

await context.close();
await browser.close();
await mkdir(resolve("dist"), { recursive: true });
const report = {
  ok,
  scenario,
  bff_count: bffCount,
  legacy_monitor_count: legacyMonitorCount,
  login_visible: loginVisible,
  retry_visible: retryVisible,
  requests,
  errors,
  generated_at: new Date().toISOString(),
};
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(reportPath);
if (!ok) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}

async function waitForScenarioSignal(page) {
  const predicate = (currentScenario) => {
    const text = document.body?.innerText || "";
    if (currentScenario === "auth") {
      return text.includes("登录进入工作台") || text.includes("账号");
    }
    if (currentScenario === "500") {
      return text.includes("加载失败，正在重试") || text.includes("已保留上次可用数据");
    }
    return text.includes("实时监控");
  };
  await page.waitForFunction(predicate, scenario, { timeout: 5_000 }).catch(() => undefined);
}

function monitorWorkspacePayload() {
  return {
    api_version: "v1",
    schema_version: "smoke",
    generated_at: now,
    stale: false,
    refresh_queued: false,
    monitor_snapshot: {
      updated_at: now,
      watchlist_signals: [],
      sector_etf_t0: { items: [] },
      priority_board: {
        strategy: "first_board",
        trade_date: "2026-05-26",
        latest_trade_date: "2026-05-26",
        updated_at: now,
        stale: false,
        data_quality: "ok",
        data_quality_text: "可用",
        items: [
          {
            symbol: "600000",
            name: "浦发银行",
            priority_score: 88.5,
            production_score: 71.2,
            buy_signal_state: "near_entry",
            latest_price: 10.1,
          },
        ],
        total: 1,
      },
    },
    market_breadth: {
      updated_at: now,
      data_quality: "fresh",
      data_quality_text: "fresh",
      state_text: "震荡修复",
      emotion_ready: true,
      emotion_temperature_text: "中性偏暖",
      emotion_temperature_score: 58,
      limit_up_count: 48,
      limit_down_count: 5,
      broken_board_ratio: 0.18,
      stock_up_ratio: 0.56,
      board_height: 4,
      hot_industries: ["机器人", "半导体"],
      hourly_all_market_snapshot: {
        snapshot_count: 5200,
        stock_up_ratio: 0.56,
        stock_down_ratio: 0.38,
        stock_median_change: 0.42,
        strong_count: 680,
        weak_count: 360,
        market_strength_score: 18,
        market_strength_text: "强弱分偏暖",
        data_quality_text: "fresh",
        updated_at: now,
      },
    },
    market_pulse: {
      data_quality: "fresh",
      data_quality_text: "fresh",
      pulse_level: "repair",
      pulse_text: "市场处于震荡修复",
      suggested_action: "下午只延续已验证方向。",
      market_strength_text: "宽度偏暖",
      leader_strength_text: "龙头强度中等",
      emotion_text: "情绪中性偏暖",
      hourly_snapshot_text: "小时快照 fresh",
      partial_errors: [],
    },
    review_status: null,
    review_reports: [],
    sector_relative_strength: { trade_date: "2026-05-26", items: [] },
    hourly_snapshot_history: [],
    key_level_alerts: [],
    paired_hedge: null,
    watch_cards: [],
    priority_cards: [],
    runtime: null,
    instrument_sync_status: null,
    partial_errors: [],
  };
}
