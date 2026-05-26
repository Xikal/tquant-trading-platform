import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const baseUrl = (process.env.FRONTEND_SMOKE_URL || "http://127.0.0.1:4173").replace(/\/$/, "");
const requireAuth = process.env.SMOKE_REQUIRE_AUTH === "1";
const mockAuth = process.env.SMOKE_MOCK_AUTH === "1";
const viewports = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 960 },
];
const paths = ["/monitor", "/emotion", "/paper", "/backtest", "/settings"];
const reportPath = resolve("dist", "responsive-smoke-report.json");

const mockUser = {
  id: 1,
  username: "smoke",
  display_name: "Smoke",
  can_paper_trade: true,
  roles: ["admin"],
  created_at: "2026-05-26T00:00:00+08:00",
};

const emptyList = { items: [], total: 0 };
const now = "2026-05-26T10:30:00+08:00";
const mockPaperAccount = {
  id: 1,
  name: "Smoke 模拟盘",
  initial_cash: 100000,
  cash_available: 100000,
  frozen_cash: 0,
  market_value: 0,
  total_assets: 100000,
  realized_pnl: 0,
  unrealized_pnl: 0,
  total_return_pct: 0,
  max_drawdown_pct: 0,
  status: "active",
  today_return_pct: 0,
};
const mockPaperPerformance = {
  total_return_pct: 0,
  max_drawdown_pct: 0,
  win_rate_pct: 0,
  net_win_rate_pct: 0,
  avg_trade_return_pct: 0,
  avg_win_pct: 0,
  avg_loss_pct: 0,
  profit_factor: null,
  stop_loss_rate_pct: 0,
  total_trades: 0,
  avg_hold_days: 0,
  win_loss_ratio: null,
};
const mockPaperStockPnl = {
  items: [],
  summary: {
    item_count: 0,
    account_total_pnl: 0,
    stock_total_pnl: 0,
    realized_pnl: 0,
    unrealized_pnl: 0,
    reconciliation_gap: 0,
  },
};
const mockPaperSectorEtfT0Performance = {
  simulated_trades: 0,
  simulated_closed_trades: 0,
  simulated_win_rate_pct: 0,
  simulated_net_win_rate_pct: 0,
  simulated_avg_return_pct: 0,
  simulated_profit_factor: null,
  shadow_sample_count: 0,
  shadow_settled_count: 0,
  shadow_pending_count: 0,
  shadow_success_rate_pct: 0,
  shadow_avg_return_1d_pct: 0,
  shadow_avg_return_3d_pct: 0,
  notes: [],
};
const mockPaperAutoTradingStatus = {
  running: false,
  engine_running: false,
  trading_time: true,
  dry_run: true,
  account_status: "active",
  interval_seconds: 60,
  last_cycle_summary: "smoke",
  total_cycles: 0,
  total_executed: 0,
  total_errors: 0,
};
const mockPaperWorkspace = {
  api_version: "v1",
  schema_version: "smoke",
  generated_at: now,
  account: mockPaperAccount,
  positions: [],
  orders: [],
  trades: [],
  stock_pnl: mockPaperStockPnl,
  performance: mockPaperPerformance,
  sector_etf_t0_performance: mockPaperSectorEtfT0Performance,
  strategy_performance: [],
  market_performance: [],
  tag_performance: [],
  risk_events: [],
  auto_trading_status: mockPaperAutoTradingStatus,
  auto_trading_runs: [],
  partial_errors: [],
};
const mockPaperDashboard = {
  account: {
    id: 1,
    total_assets: 100000,
    total_return_pct: 0,
    sharpe_ratio: 0,
  },
  equity_curve: [],
  win_rate_trend: [],
  strategy_trend: [],
  market_perf_heatmap: [],
  strategy_market_matrix: [],
  strategy_correlation: {
    strategies: [],
    sample_days: 0,
    matrix: [],
    rows: [],
    notes: [],
  },
  today_report: null,
  review_reports: [],
  updated_at: now,
};

async function installMockAuth(page) {
  if (!mockAuth) return;
  await page.addInitScript(() => {
    localStorage.setItem("tquant:auth:persistence_mode", "session");
    sessionStorage.setItem("tquant:auth:access_token", "smoke-token");
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, "");
    const response = (body, status = 200) => route.fulfill({
      status,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(body),
    });
    if (path === "/auth/me") return response({ user: mockUser });
    if (path === "/auth/refresh") return response({ access_token: "smoke-token", refresh_token: "smoke-refresh", token_type: "bearer", expires_in: 3600, user: mockUser });
    if (path === "/monitor/snapshot" || path === "/bff/v1/workspace/monitor") {
      return response({
        generated_at: now,
        priority_board: { strategy: "first_board", trade_date: "2026-05-26", items: [], total: 0 },
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
        review_status: {
          status_text: "午盘已生成，收盘等待触发",
          next_trigger_at: "2026-05-26T15:05:00+08:00",
          has_midday: true,
          has_close: false,
          risk_alert_count: 1,
          suggested_action: "下午降低追高频率，优先看已确认主线。",
        },
        review_reports: [{
          report_slot: "midday",
          report_date: "2026-05-26",
          generated_at: "2026-05-26T11:40:00+08:00",
          overall_summary: "上午市场修复但分化明显。",
          suggestion: "下午控制仓位，不追弱转强失败标的。",
          risk_alerts: [{ content: "炸板率抬升" }],
        }],
        sector_relative_strength: { trade_date: "2026-05-26", items: [] },
        hourly_snapshot_history: [],
        key_level_alerts: [],
        sector_etf_t0: { items: [] },
        paired_hedge: null,
        watch_cards: [],
        priority_cards: [],
        runtime: null,
        instrument_sync_status: null,
        partial_errors: [],
      });
    }
    if (path === "/strategies/meta") return response({ strategies: [] });
    if (path === "/backtests") return response({ items: [], total: 0, limit: 20, offset: 0 });
    if (path.startsWith("/backtests/")) return response(emptyList);
    if (path === "/backtests/optimize" || path === "/backtests/validate") return response({ items: [], total: 0, limit: 20, offset: 0 });
    if (path === "/bff/v1/workspace/paper") return response(mockPaperWorkspace);
    if (path === "/paper/account") return response(mockPaperAccount);
    if (path === "/paper/positions" || path === "/paper/positions/refresh") {
      return response({ positions: [], total_market_value: 0, total_unrealized_pnl: 0 });
    }
    if (path === "/paper/orders") return response([]);
    if (path === "/paper/trades") return response({ trades: [] });
    if (path === "/paper/performance") return response(mockPaperPerformance);
    if (path === "/paper/performance/stock-pnl") return response(mockPaperStockPnl);
    if (path === "/paper/performance/dashboard") return response(mockPaperDashboard);
    if (path === "/paper/performance/sector-etf-t0") return response(mockPaperSectorEtfT0Performance);
    if (path === "/paper/performance/by-strategy") return response([]);
    if (path === "/paper/performance/by-market-state") return response([]);
    if (path === "/paper/performance/by-strategy-market-state") return response([]);
    if (path === "/paper/performance/by-tag") return response([]);
    if (path === "/paper/risk/events") return response([]);
    if (path === "/paper/auto-trading/status") return response(mockPaperAutoTradingStatus);
    if (path === "/paper/auto-trading/runs") return response([]);
    if (path.startsWith("/paper") || path.startsWith("/app/paper")) return response(emptyList);
    if (path.startsWith("/settings") || path.startsWith("/admin")) return response({});
    if (path.startsWith("/market") || path.startsWith("/bff") || path.startsWith("/app") || path.startsWith("/strategy") || path.startsWith("/factor")) return response(emptyList);
    return response({});
  });
}

const browser = await chromium.launch({ headless: true });
const results = [];
let failed = false;

for (const viewport of viewports) {
  for (const path of paths) {
    const context = await browser.newContext({ viewport, serviceWorkers: "block" });
    const page = await context.newPage();
    await installMockAuth(page);
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(String(error.message || error)));
    page.on("console", (message) => {
      if (message.type() === "error") {
        pageErrors.push(message.text());
      }
    });
    const url = `${baseUrl}${path}`;
    const started = Date.now();
    let status = 0;
    let loginGate = false;
    let overflowX = 0;
    let title = "";
    try {
      const response = await page.goto(url, { waitUntil: "networkidle", timeout: 20_000 });
      status = response?.status() || 0;
      await page.waitForTimeout(250);
      title = await page.title();
      loginGate = await page
        .locator('button:has-text("登录进入工作台"), input[autocomplete="username"], input[autocomplete="current-password"]')
        .first()
        .isVisible()
        .catch(() => false);
      overflowX = await page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - window.innerWidth));
    } catch (error) {
      pageErrors.push(String(error?.message || error));
    }
    const ok = status > 0 && status < 500 && overflowX <= 2 && pageErrors.length === 0 && (!requireAuth || !loginGate);
    if (!ok) {
      failed = true;
    }
    results.push({
      path,
      viewport: viewport.name,
      width: viewport.width,
      status,
      ok,
      login_gate: loginGate,
      auth_required: requireAuth,
      mock_auth: mockAuth,
      overflow_x: overflowX,
      page_error_count: pageErrors.length,
      title,
      elapsed_ms: Date.now() - started,
      errors: pageErrors.slice(0, 3),
    });
    await context.close();
  }
}

await browser.close();
await mkdir(resolve("dist"), { recursive: true });
await writeFile(
  reportPath,
  `${JSON.stringify(
    {
      ok: !failed,
      base_url: baseUrl,
      generated_at: new Date().toISOString(),
      authenticated: !results.some((item) => item.login_gate),
      auth_required: requireAuth,
      mock_auth: mockAuth,
      results,
    },
    null,
    2,
  )}\n`,
  "utf8",
);
console.log(reportPath);
process.exit(failed ? 1 : 0);
