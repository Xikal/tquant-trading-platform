import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  emptyList,
  mockAnalysis,
  mockDataQualitySla,
  mockDataSources,
  mockEtfUniverseAdmin,
  mockLowBuy,
  mockLowBuyCandidate,
  mockRuntimeTasks,
  mockStrategyMeta,
  mockStrategyTrackingItem,
  mockStrategyTrackingList,
  mockStrategyTrackingPerformance,
  mockStrategyTrackingSnapshot,
  mockStrategyTrackingSummary,
  mockTradeGate,
  mockUser,
  now,
} from "./smoke-responsive-fixtures.mjs";

const baseUrl = (process.env.FRONTEND_SMOKE_URL || "http://127.0.0.1:4173").replace(/\/$/, "");
const requireAuth = process.env.SMOKE_REQUIRE_AUTH === "1";
const mockAuth = process.env.SMOKE_MOCK_AUTH === "1";
const viewports = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 960 },
];
const paths = ["/monitor", "/emotion", "/analysis", "/playbook", "/strategy-tracking", "/strategy", "/data", "/settings"];
const reportPath = resolve("dist", "responsive-smoke-report.json");

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
    if (path === "/market/hourly-snapshots/history") return response({ items: [], total: 0 });
    if (path === "/market/trading-session") return response({ updated_at: now, is_trading_day: true, is_trading_now: true, current_time: now, timezone: "Asia/Shanghai", data_quality_text: "fresh" });
    if (path.startsWith("/market/intraday-anomaly/")) return response({ symbol: "510300", anomaly_level: "low", anomaly_text: "正常", score: 12, reasons: [], updated_at: now });
    if (path === "/strategies/meta") return response({ strategies: mockStrategyMeta });
    if (path === "/strategy/presets") return response({ presets: [] });
    if (path === "/strategy-tracking/snapshot") return response(mockStrategyTrackingSnapshot);
    if (path === "/strategy-tracking/summary") return response(mockStrategyTrackingSummary);
    if (path === "/strategy-tracking/items") return response(mockStrategyTrackingList);
    if (path === "/strategy-tracking/performance") return response([mockStrategyTrackingPerformance]);
    if (path === "/strategy/promotion-review") return response({
      strategy_key: url.searchParams.get("strategy") || "n_pattern_long_wash",
      current_tier: "research",
      recommended_tier: "research",
      recommendation: "stay_research",
      evidence: {
        sample_count: 0,
        profit_factor: null,
        average_trade_pct: 0,
        max_drawdown_pct: 0,
        max5_return_pct: 0,
        max10_return_pct: 0,
        quarterly_stability: 0,
      },
      blocking_reasons: ["research_only"],
      can_apply_override: false,
    });
    if (path.startsWith("/strategy-tracking/items/")) return response({
      item: mockStrategyTrackingItem,
      timeline: [
        { trade_date: "2026-05-26", open: 3.42, high: 3.48, low: 3.4, close: 3.45, pct_chg: 0.88, current_return_pct: 0.88, max_return_pct: 1.75, max_drawdown_pct: -0.58, hit_entry_zone: true, hit_stop_loss: false, hit_target: false, lifecycle_status: "active", data_quality: "ok" },
      ],
      markers: [{ kind: "first_signal", trade_date: "2026-05-25", price: 3.42, label: "首次信号" }],
      signal_snapshot: { summary_reason: "主线 ETF 回踩承接" },
      review_text: mockStrategyTrackingItem.review_text,
      partial_errors: [],
      production_writeable: false,
    });
    if (path === "/bff/v1/workspace/strategy") return response({
      api_version: "v1",
      schema_version: "smoke",
      generated_at: now,
      strategy_meta: { strategies: mockStrategyMeta },
      presets: { presets: [] },
      recent_runs: { items: [], total: 0, limit: 20, offset: 0 },
      verdict_thresholds: { thresholds: {} },
      partial_errors: [],
    });
    if (path.startsWith("/strategy/signals/replay")) return response({ items: [], total: 0 });
    if (path === "/screeners/low-buy/strategies") {
      return response({
        default_strategy: "first_board",
        production_strategies: ["first_board"],
        items: mockStrategyMeta.map((item) => ({
          strategy_key: item.key,
          strategy_title: item.display_name,
          subtitle: item.description,
          tier: item.tier,
          layer: "production",
          status: "active",
          status_text: "启用",
          enabled: true,
          participates_priority_board: true,
          strong_buy_paused: false,
          requires_mainline_industry: false,
          pool_key: "default",
          pool_title: "默认池",
          pool_source: "smoke",
          pool_max_size: 100,
          uses_daily_scan_pool: true,
          max_holding_days: 5,
        })),
      });
    }
    if (path === "/screeners/low-buy/priority-board") return response({ strategy: "first_board", trade_date: "2026-05-26", items: [mockLowBuyCandidate], total: 1 });
    if (path === "/screeners/low-buy") return response(mockLowBuy);
    if (path === "/screeners/low-buy/quotes") return response({ items: { "510300": { latest_price: 3.45, change_pct: 0.6, quote_timestamp: now, in_entry_zone: true, distance_to_entry_pct: -0.2, stop_confirmed: false, buy_signal_state: "near_entry", buy_signal_text: "接近买点（观察类·未到买入）", buy_signal_hint: "等待承接确认，不是买入建议" } } });
    if (path === "/analyze") return response(mockAnalysis);
    if (path === "/analyze/batch") return response([mockAnalysis]);
    if (path === "/ai/decision-support") return response({ enabled: false, summary: "smoke", suggestions: [], warnings: [] });
    if (path === "/bff/v1/workspace/settings") return response({
      api_version: "v1",
      schema_version: "smoke",
      generated_at: now,
      settings: {
        llm_provider: "openai",
        llm_api_key: "********",
        llm_base_url: "https://api.example.invalid/v1",
        llm_model: "smoke",
        data_source: "local",
        data_source_base_url: "",
        database_url: "sqlite:///smoke.db",
        risk_max_single_loss_pct: 2,
        risk_max_daily_loss_pct: 5,
        risk_pause_after_losses: 3,
        walk_forward_window_size: 20,
        event_risk_enabled: false,
        microstructure_enabled: false,
        strategy_min_amount_stock: 50000000,
        strategy_min_amount_etf: 10000000,
        strategy_min_amplitude_pct: 1,
        strategy_max_amplitude_pct: 12,
        strategy_max_atr_pct: 8,
        strategy_open_phase_min_tradability: 60,
        strategy_min_profit_pct: 1.2,
        strategy_min_profit_stock_pct: 3,
        strategy_min_profit_etf_pct: 1.2,
        strategy_slippage_stock_bps: 8,
        strategy_slippage_etf_bps: 3,
        llm_api_key_configured: true,
        database_url_configured: true,
        admin_auth_required: false,
      },
      sector_exclusions: { available_sectors: ["机器人", "半导体"], excluded_sectors: [], excluded_count: 0, updated_at: now },
      strategy_governance: { default_strategy: "first_board", production_strategies: ["first_board"], items: [] },
      runtime: { app_name: "TQuant", api_prefix: "/api", database_backend: "sqlite", database_url_masked: "sqlite:///smoke.db", runtime_database_url_masked: "sqlite:///smoke.db", runtime_env_path: ".runtime", runtime_env_exists: true, runtime_database_override: false, runtime_database_matches_settings: true, runtime_llm_secret_persisted: true, settings_consistency_status: "ok", settings_consistency_text: "配置一致", frontend_dist_path: "dist", frontend_dist_ready: true, llm_configured: true, data_source: "local", data_source_base_url: "", cors_origins: [], ready_checks: { database: true, frontend_dist: true } },
      factor_weights: { weights: {}, defaults: {}, factors: [] },
      admin_tasks: { items: [] },
      admin_metrics: {},
      admin_enabled: true,
      partial_errors: [],
    });
    if (path === "/settings/runtime") return response({ app_name: "TQuant", api_prefix: "/api", database_backend: "sqlite", database_url_masked: "sqlite:///smoke.db", runtime_database_url_masked: "sqlite:///smoke.db", runtime_env_path: ".runtime", runtime_env_exists: true, runtime_database_override: false, runtime_database_matches_settings: true, runtime_llm_secret_persisted: true, settings_consistency_status: "ok", settings_consistency_text: "配置一致", frontend_dist_path: "dist", frontend_dist_ready: true, llm_configured: true, data_source: "local", data_source_base_url: "", cors_origins: [], ready_checks: { database: true, frontend_dist: true } });
    if (path === "/settings/sector-exclusions") return response({ available_sectors: ["机器人", "半导体"], excluded_sectors: [], excluded_count: 0, updated_at: now });
    if (path === "/settings/factor-weights") return response({ weights: {}, defaults: {}, factors: [] });
    if (path === "/admin/tasks") return response({ items: [] });
    if (path === "/admin/metrics") return response({});
    if (path === "/operation-audit") return response({ items: [], total: 0, limit: 20, offset: 0 });
    if (path === "/quant/parameters/current") return response({ id: 1, version: "smoke", name: "Smoke", scope: "global", status: "active", params: {}, description: "smoke", created_by: "smoke", created_at: now, activated_at: now });
    if (path === "/quant/parameters/schema") return response({});
    if (path === "/ml/signals/online-learning/status") return response({ generated_at: now, paper_sample_count: 0, closed_trade_sample_count: 0, positive_sample_count: 0, negative_sample_count: 0, ready_for_training: false, min_samples: 100, feature_names: [], sequence_feature_names: [], production_model_key: "smoke", latest_incremental_task_status: "idle", latest_incremental_task_progress_pct: 0, next_training_rule: "manual", warnings: [] });
    if (path === "/ml/signals/capacity") return response({ generated_at: now, capital_levels: [], items: [], assumptions: {} });
    if (path === "/data-quality/sla") return response(mockDataQualitySla);
    if (path === "/data-quality/coverage") return response({ dataset_key: url.searchParams.get("dataset_key") || "daily_bars", scope: url.searchParams.get("scope") || "all", missing_symbols: [], missing_dates: [] });
    if (path === "/data-quality/trade-gate") return response(mockTradeGate);
    if (path === "/data-quality/repair") return response({ id: 2, task_type: "data_repair_run", status: "queued", progress_pct: 0, payload: {}, created_at: now, updated_at: now });
    if (path === "/data-quality/backfill") return response({ id: 3, task_type: "data_quality_backfill", status: "queued", progress_pct: 0, payload: {}, created_at: now, updated_at: now });
    if (path === "/market/data-sources/health") return response(mockDataSources);
    if (path === "/runtime-tasks") return response(mockRuntimeTasks);
    if (path === "/market/etf-universe/admin") return response(mockEtfUniverseAdmin);
    if (path === "/market/etf-universe/validate") return response(mockEtfUniverseAdmin);
    if (path === "/market/etf-universe/repair-draft") return response({ draft_overrides: {}, validation: { error_count: 0, warning_count: 0, info_count: 0, issues: [] }, notes: ["smoke"] });
    if (path === "/market/etf-universe/apply" || path === "/market/etf-universe/rollback") return response({ admin: mockEtfUniverseAdmin, message: "ok" });
    if (path.startsWith("/quote/")) return response({ symbol: "510300", name: "沪深300ETF", market: "SH", instrument_type: "etf", last_price: 3.45, change_pct: 0.6, change_amount: 0.02, open_price: 3.43, high_price: 3.48, low_price: 3.41, prev_close: 3.43, volume: 1200000, amount: 4140000, timestamp: now, data_source: "smoke", source_quality: "ok", is_stale: false });
    if (path.startsWith("/kline/")) return response({ symbol: "510300", period: "5m", bars: [{ timestamp: now, open: 3.42, close: 3.45, high: 3.48, low: 3.41, volume: 1000, amount: 3450 }] });
    if (/^\/instruments\/[^/]+\/rules$/.test(path)) return response({ symbol: "510300", turnaround_mode: "t0", supports_positive_t: true, supports_negative_t: true, same_day_sell_allowed: true, requires_base_position: true, notes: "ETF T+0" });
    if (/^\/instruments\/[^/]+\/sector$/.test(path)) return response({ sector_name: "ETF", sector_strength: 58, market_strength: 52, alignment_score: 61, notes: "smoke" });
    if (/^\/instruments\/[^/]+\/events$/.test(path)) return response({ symbol: "510300", events: [] });
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
    const visibleTextLength = await page.locator("body").innerText().then((value) => value.trim().length).catch(() => 0);
    const mainRegionCount = await page.locator("main, section, .panel, [role='main']").count().catch(() => 0);
    const ok = status > 0 && status < 500 && overflowX <= 2 && pageErrors.length === 0 && visibleTextLength >= 20 && mainRegionCount > 0 && (!requireAuth || !loginGate);
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
      visible_text_length: visibleTextLength,
      main_region_count: mainRegionCount,
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
