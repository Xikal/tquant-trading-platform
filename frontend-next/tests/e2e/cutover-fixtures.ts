import type { Page } from "@playwright/test";

export function captureApiWrites(page: Page): () => string[] {
  const writes: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/") && ["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) {
      writes.push(`${request.method()} ${url.pathname}`);
    }
  });
  return () => writes;
}

export async function installMonitorActionFixture(page: Page) {
  await page.route("**/api/bff/v1/workspace/monitor?**", (route) =>
    route.fulfill({
      status: 200,
      json: {
        api_version: "v1",
        monitor_snapshot: {
          latest_trade_date: "2026-06-07",
          priority_board: {
            display_lane_title: "生产优先榜",
            immediate_count: 1,
            focus_count: 1,
            total_candidates: 2,
            market_firepower_multiplier: 0.82,
            market_gate_decision: "pass",
            market_state_text: "震荡可做",
            data_quality_text: "正常",
            directional_bias_text: "偏多观察",
            hot_industries: ["半导体", "银行"],
            portfolio_risk: { risk_level: "可控" },
            plain_language_summary: "生产优先榜按服务端顺序展示。",
            items: priorityItems,
          },
          watchlist_signals: [priorityItems[1]],
        },
        stock_key_levels: { items: [{ type: "支撑", price: 8.5, summary: "低吸观察位" }] },
        positions: [{ symbol: "000001", name: "平安银行", quantity: 1000, cost_price: 12.1, pnl_pct: 0.016 }],
        instrument_sync_status: { status: "ok" },
        runtime: { database_backend: "sqlite", status: "ok" },
        data_quality: { status: "ok", coverage_ratio: "98%" },
      },
    }),
  );
}

export async function installAnalysisFixture(page: Page) {
  await page.route("**/api/analyze", async (route) => {
    const body = route.request().postDataJSON() as { symbol: string };
    await route.fulfill({ status: 200, json: analysisResponse(body.symbol) });
  });
  await page.route("**/api/analyze/batch?**", async (route) => {
    const body = route.request().postDataJSON() as Array<{ symbol: string }>;
    await route.fulfill({ status: 200, json: body.map((item) => analysisResponse(item.symbol)) });
  });
  await page.route("**/api/quote/*", (route) => route.fulfill({ status: 200, json: quoteFixture(routeSymbol(route.request().url())) }));
  await page.route("**/api/kline/*", (route) => route.fulfill({ status: 200, json: { bars: klineFixture() } }));
  await page.route("**/api/key-levels/stock/*", (route) => route.fulfill({ status: 200, json: keyLevelFixture }));
  await page.route("**/api/market/intraday-anomaly/*", (route) => route.fulfill({ status: 200, json: { anomaly_level: "normal", anomaly_text: "暂无异常", data_quality_text: "正常" } }));
}

export async function installPlaybookFixture(page: Page) {
  await page.route("**/api/screeners/low-buy?**", (route) => route.fulfill({ status: 200, json: { priority_board: priorityBoardFixture, strategy: { strategy_key: "n_pattern_long_wash" } } }));
  await page.route("**/api/screeners/low-buy/priority-board?**", (route) => route.fulfill({ status: 200, json: priorityBoardFixture }));
  await page.route("**/api/screeners/low-buy/quotes?**", (route) => route.fulfill({ status: 200, json: { quotes: [quoteFixture("000001"), quoteFixture("600000")] } }));
  await page.route("**/api/screeners/low-buy/strategies", (route) => route.fulfill({ status: 200, json: { default_strategy: "n_pattern_long_wash", production_strategies: ["n_pattern_long_wash"], items: [{ strategy_key: "n_pattern_long_wash", strategy_title: "N形洗盘低吸", layer: "production", status_text: "运行" }] } }));
  await page.route("**/api/strategies/meta", (route) => route.fulfill({ status: 200, json: { strategies: [{ key: "n_pattern_long_wash", display_name: "N形洗盘低吸", tier: "core" }] } }));
}

export async function installPaperFixture(page: Page) {
  await page.route("**/api/bff/v1/workspace/paper", (route) => route.fulfill({ status: 200, json: paperWorkspaceFixture }));
}

export async function installStrategyFixture(page: Page) {
  await page.route("**/api/bff/v1/workspace/strategy", (route) => route.fulfill({ status: 200, json: { items: strategyItems, summary: { total: 2, needs_review_count: 1 } } }));
  await page.route("**/api/strategy-tracking/items*", (route) => route.fulfill({ status: 200, json: { items: strategyItems, total: 2, limit: 50, offset: 0 } }));
  await page.route("**/api/strategy-tracking/summary*", (route) => route.fulfill({ status: 200, json: { total: 2, needs_review_count: 1 } }));
  await page.route("**/api/strategy-tracking/performance*", (route) => route.fulfill({ status: 200, json: [{ strategy_key: "n_pattern", strategy_name: "N形洗盘低吸", recommendation_count: 12, win_rate_5d: 0.64 }] }));
  await page.route("**/api/strategy-tracking/holding-analysis*", (route) => route.fulfill({ status: 200, json: { items: [{ strategy_key: "n_pattern", conclusion: "短线 1-3 天" }] } }));
  await page.route("**/api/strategy-tracking/review*", (route) => route.fulfill({ status: 200, json: { needs_review_items: [strategyItems[1]], abnormal_return_items: [strategyItems[1]], failure_tags: { 回落过快: 1 } } }));
  await page.route("**/api/strategy-tracking/items/item-600000", (route) => route.fulfill({ status: 200, json: { item: strategyItems[1], timeline: [] } }));
  await page.route("**/api/trading-experience/trade-journal*", (route) => route.fulfill({ status: 200, json: { enabled: true, items: [{ entry_id: 1, symbol: "600000", action: "note", reason_text: "等待确认" }] } }));
  await page.route("**/api/trading-experience/relative-strength*", (route) => route.fulfill({ status: 200, json: { enabled: true, items: [{ symbol: "600000", rs_vs_index: 0.008 }] } }));
}

export async function installBacktestFixture(page: Page) {
  await page.route("**/api/backtests/runs**", (route) => route.fulfill({ status: 200, json: { items: [{ id: 101, name: "frontend-next 低吸回测", status: "finished", strategy_keys: ["n_pattern_long_wash"], final_equity: 128900 }] } }));
  await page.route("**/api/backtests/101", (route) => route.fulfill({ status: 200, json: { id: 101, name: "frontend-next 低吸回测", status: "finished", progress_pct: 100, final_equity: 128900, summary: { total_return: 0.289 } } }));
  await page.route("**/api/backtests/101/equity", (route) => route.fulfill({ status: 200, json: { items: [{ date: "2025-01-01", equity: 100000 }, { date: "2026-06-05", equity: 128900 }] } }));
  await page.route("**/api/backtests/101/trades", (route) => route.fulfill({ status: 200, json: { items: [{ trade_date: "2025-02-03", symbol: "000001", side: "buy", quantity: 1000, price: 10.2, reason: "突破确认" }] } }));
}

export async function installDataSettingsFixtures(page: Page, status = 200) {
  const maybeError = (payload: unknown) => (status >= 400 ? { status, json: { detail: "cutover readiness fixture error" } } : { status: 200, json: payload });
  await page.route("**/api/data-quality/coverage", (route) => route.fulfill(maybeError({ missing_dates: ["2026-06-05"], missing_symbols: [{ symbol: "000001", name: "平安银行", missing_days: 1 }] })));
  await page.route("**/api/data-quality/sla", (route) => route.fulfill(maybeError({ items: [{ dataset_key: "daily_bars", status: "ok", coverage_pct: 0.98 }] })));
  await page.route("**/api/runtime-tasks**", (route) => route.fulfill(maybeError({ items: [{ id: 501, task_type: "data_backfill", status: "queued" }] })));
  await page.route("**/api/admin/metrics", (route) => route.fulfill(maybeError({ status: "ok", worker_count: 1, failed_count: 0 })));
  await page.route("**/api/admin/tasks", (route) => route.fulfill(maybeError({ workers: [{ worker_id: "runtime-worker-1", status: "running" }], tasks: [] })));
  await page.route("**/api/settings/runtime", (route) => route.fulfill(maybeError({ settings_consistency_status: "ok", data_source: "akshare_eastmoney", database_backend: "sqlite", llm_configured: true })));
  await page.route("**/api/settings/sector-exclusions", (route) => route.fulfill(maybeError({ available_sectors: ["银行", "房地产"], excluded_sectors: ["房地产"] })));
  await page.route("**/api/settings/factor-weights", (route) => route.fulfill(maybeError({ weights: { volume_price: 0.4 }, factors: [{ factor_key: "volume_price", name: "量价确认", weight: 0.4 }] })));
  await page.route("**/api/settings/feature-flags/audit**", (route) => route.fulfill(maybeError({ items: [] })));
  await page.route("**/api/settings/feature-flags", (route) => route.fulfill(maybeError({ frontend_solid_island_enabled: true })));
  await page.route("**/api/settings", (route) => route.fulfill(maybeError({ llm_provider: "dashscope", llm_model: "qwen-plus", risk_max_single_loss_pct: 1, admin_auth_required: true })));
  await page.route("**/api/quant/parameters**", (route) => route.fulfill(maybeError({ items: [{ id: 1, name: "低吸默认参数", params: { risk: 1 } }] })));
  await page.route("**/api/bff/v1/workspace/settings**", (route) => route.fulfill(maybeError({ strategy_governance: { items: [] } })));
}

const priorityItems = [
  { symbol: "000001", name: "平安银行", latest_price: 12.3, change_pct: 0.012, production_score: 91, signal_state: "立即处理", strategy_name: "N形洗盘低吸", lane: "buy_now", risk_text: "风控通过", warning_tags: ["立即"] },
  { symbol: "600000", name: "浦发银行", latest_price: 8.72, change_pct: -0.004, production_score: 83, signal_state: "观察确认", strategy_name: "均值回归观察", lane: "observe", risk_text: "等待价格", warning_tags: ["观察"] },
];

const priorityBoardFixture = {
  as_of_date: "2026-06-07",
  immediate_count: 1,
  focus_count: 1,
  total_candidates: 2,
  market_state_text: "震荡可做",
  family_sections: [
    {
      family_key: "wash",
      family_text: "洗盘低吸",
      items: priorityItems.map((item) => ({
        ...item,
        priority_score: item.production_score,
        buy_signal_text: item.signal_state,
        simple_bucket: "buy_now",
        simple_bucket_text: "立即处理",
        action_summary: "接近支撑位",
        data_quality_text: "数据完整",
        strategy_key: "n_pattern_long_wash",
        strategy_title: "N形洗盘低吸",
      })),
    },
  ],
};

const keyLevelFixture = {
  data_quality: "ok",
  key_level_candidates: [{ direction: "support", level_type: "ma20", price: 8.5, strength_score: 82, zone_low: 8.45, zone_high: 8.55 }],
};

const paperWorkspaceFixture = {
  api_version: "v1",
  account: { id: 1, name: "默认模拟账户", cash_available: 88000, initial_cash: 100000, market_value: 12000, status: "active", total_assets: 100220, total_return_pct: 0.22 },
  positions: [{ id: 1, symbol: "600000", name: "浦发银行", quantity: 1000, available_quantity: 900, cost_basis: 8.6, latest_price: 8.72, market_value: 8720, unrealized_pnl: 120, unrealized_pnl_pct: 1.4 }],
  orders: [{ id: 10, symbol: "600000", name: "浦发银行", side: "buy", order_type: "limit", quantity: 100, status: "filled", reason: "策略买入" }],
  trades: [],
  stock_pnl: { summary: {}, items: [] },
  performance: { total_return_pct: 0.22, win_rate_pct: 55, max_drawdown_pct: 3.2 },
  strategy_performance: [],
  market_performance: [],
  tag_performance: [],
  risk_events: [],
  auto_trading_status: { running: false, engine_running: false, trading_time: true },
  auto_trading_runs: [],
  partial_errors: [],
};

const strategyItems = [
  { id: "item-000001", symbol: "000001", name: "平安银行", strategy_key: "n_pattern", strategy_name: "N形洗盘低吸", signal_state: "buy_ready", signal_text: "确定可买", lifecycle_status_text: "跟踪中", plain_language_summary: "回踩支撑后放量", current_return_pct: 0.034 },
  { id: "item-600000", symbol: "600000", name: "浦发银行", strategy_key: "mean_revert", strategy_name: "均值回归观察", signal_state: "watch", signal_text: "观察确认", lifecycle_status_text: "需复盘", plain_language_summary: "冲高回落", current_return_pct: -0.012, needs_review: true, abnormal_return: true },
];

function analysisResponse(symbol: string) {
  return {
    symbol,
    instrument: { symbol, name: symbol === "600000" ? "浦发银行" : "平安银行" },
    quote: quoteFixture(symbol),
    bars: klineFixture(),
    suggestion: { action: "positive_t", plain_action_text: "轻仓低吸", plain_action_reason: "接近支撑位", signal_score: symbol === "600000" ? 91 : 82, risk_level: "medium" },
    metrics: { signal_score: symbol === "600000" ? 91 : 82 },
    ai: { enabled: true, confidence: 0.7, summary: "量价结构改善", suggestions: [], warnings: [] },
  };
}

function quoteFixture(symbol: string) {
  return { symbol, name: symbol === "600000" ? "浦发银行" : "平安银行", last_price: symbol === "600000" ? 8.72 : 12.3, latest_price: symbol === "600000" ? 8.72 : 12.3, change_pct: 0.012, data_quality: "fresh" };
}

function klineFixture() {
  return Array.from({ length: 18 }, (_, index) => ({ timestamp: `2026-05-${String(index + 10).padStart(2, "0")}`, close: 8.4 + index * 0.03, open: 8.3, high: 8.8, low: 8.2, volume: 10000 }));
}

function routeSymbol(url: string): string {
  return decodeURIComponent(new URL(url).pathname.split("/").at(-1) ?? "000001");
}
