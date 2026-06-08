import { expect, test, type Page } from "@playwright/test";
import { installE2eAuthState } from "./auth-state";

test("/next/analysis runs symbol and batch analysis without trading writes", async ({ page }) => {
  await installE2eAuthState(page);
  const writes = collectWrites(page);
  await installAnalysisRoutes(page);

  await page.goto("/next/analysis");
  await expect(page.getByRole("heading", { name: "输入控制" })).toBeVisible();
  await page.getByLabel("分析代码").fill("600000");
  await page.getByTestId("analysis-control-start").click();
  await expect(page.getByText("600000 分析完成")).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前行动建议细则点" })).toBeVisible();
  await expect(page.locator(".tq-analysis-page__key-levels")).toContainText("8.5");
  await expect(page.getByRole("heading", { name: "盘中异常提醒" })).toBeVisible();
  await expect(page.locator(".tq-analysis-page__anomaly")).toContainText("暂无异常");
  await expect(page.locator(".analysis-kline-frame .chart-frame canvas").first()).toBeVisible();
  await expect(page.locator(".analysis-kline-header")).toContainText("8.72");

  const quoteRequestsAfterAnalysis: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/quote/")) quoteRequestsAfterAnalysis.push(url.pathname);
  });
  await page.getByLabel("分析代码").fill("000001");
  await page.waitForTimeout(300);
  expect(quoteRequestsAfterAnalysis).toEqual([]);
  await expect(page.locator(".analysis-kline-header")).toContainText("8.72");
  await page.getByLabel("分析代码").fill("600000");

  await page.getByLabel("批量代码").fill("000001,600000");
  await page.getByTestId("analysis-batch").click();
  await expect(page.getByText("2 个标的批量分析完成")).toBeVisible();
  await expect(page.getByTestId("analysis-batch-results")).toContainText("600000");
  await expect(page.getByTestId("analysis-batch-results").locator("tbody tr").first()).toContainText("600000");
  expect(writes()).toEqual(["POST /api/analyze", "POST /api/analyze/batch"]);
});

test("/next/analysis opens a paper shadow order draft from the analyzed result", async ({ page }) => {
  await installE2eAuthState(page);
  const writes = collectWrites(page);
  await installAnalysisRoutes(page);
  await page.route("**/api/bff/v1/workspace/paper", (route) => route.fulfill({ status: 200, json: paperWorkspaceFixture }));

  await page.goto("/next/analysis");
  await page.getByLabel("分析代码").fill("600000");
  await page.getByTestId("analysis-control-start").click();
  await expect(page.getByText("600000 分析完成")).toBeVisible();
  await page.getByTestId("analysis-open-paper").click();

  await expect(page).toHaveURL(/\/next\/paper.*source=analysis/);
  await expect(page.getByRole("dialog", { name: "模拟委托" })).toBeVisible();
  await expect(page.getByLabel("代码")).toHaveValue("600000");
  await expect(page.getByLabel("名称")).toHaveValue("浦发银行");
  await expect(page.getByLabel("数量")).toHaveValue("1000");
  await expect(page.getByLabel("价格")).toHaveValue("8.72");
  await expect(page.getByLabel("策略")).toHaveValue("auto");
  await expect(page.getByLabel("理由")).toHaveValue("接近支撑位");
  await expect(page.getByText(/金额/)).toBeVisible();
  expect(writes()).toEqual(["POST /api/analyze"]);
});

test("/next/playbook reads low-buy workflow and blocks lifecycle writes", async ({ page }) => {
  await installE2eAuthState(page);
  const writes = collectWrites(page);
  await installPlaybookRoutes(page);

  await page.goto("/next/playbook");
  await expect(page.getByRole("heading", { name: "今日注目核心标的" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "候选分层" })).toBeVisible();
  await expect(page.getByText("载入模拟推荐")).toHaveCount(0);
  await expect(page.getByText("贵州茅台")).toHaveCount(0);
  await expect(page.getByText("比亚迪")).toHaveCount(0);
  const candidatePanel = page.locator(".playbook-candidates-panel");
  await expect(candidatePanel.getByText("平安银行").first()).toBeVisible();
  await candidatePanel.getByRole("button").filter({ hasText: "浦发银行" }).click();
  await expect(page.getByTestId("playbook-detail")).toContainText("600000");
  await page.getByTestId("playbook-refresh").click();
  await expect(page.getByText("刷新全量")).toBeVisible();
  await page.getByTestId("playbook-open-analysis").click();
  await expect(page).toHaveURL(/\/next\/analysis\?symbol=600000$/);
  await expect(page.getByLabel("分析代码")).toHaveValue("600000");
  await page.goBack();
  await expect(page.getByTestId("playbook-detail")).toContainText("600000");
  await page.getByTestId("playbook-detail").locator("..").getByRole("button", { name: "记录状态" }).click();
  await expect(page.getByText("状态更新已记录")).toBeVisible();
  expect(writes()).toEqual([]);
});

test("/next/playbook refreshes candidate quote prices without refreshing the whole screener", async ({ page }) => {
  await installE2eAuthState(page);
  let screenerRequests = 0;
  let quoteRequests = 0;
  await installPlaybookRoutes(page, {
    onScreener: () => {
      screenerRequests += 1;
    },
    quotePrice: (symbol) => {
      if (symbol !== "600000") return undefined;
      quoteRequests += 1;
      return quoteRequests <= 1 ? 8.72 : 8.91;
    },
  });

  await page.goto("/next/playbook");
  const candidatePanel = page.locator(".playbook-candidates-panel");
  const row = candidatePanel.getByRole("row").filter({ hasText: "浦发银行" });
  await expect(row).toContainText("8.72");
  await expect.poll(() => quoteRequests, { timeout: 9_000 }).toBeGreaterThan(1);
  await expect(row).toContainText("8.91");
  expect(screenerRequests).toBe(1);
});

function collectWrites(page: Page) {
  const writes: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/") && ["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) {
      writes.push(`${request.method()} ${url.pathname}`);
    }
  });
  return () => writes;
}

async function installAnalysisRoutes(page: Page) {
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
  await page.route("**/api/market/intraday-anomaly/*", (route) => route.fulfill({ status: 200, json: anomalyFixture(routeSymbol(route.request().url())) }));
}

async function installPlaybookRoutes(page: Page, options: { onScreener?: () => void; quotePrice?: (symbol: string) => number | undefined } = {}) {
  await page.route("**/api/screeners/low-buy?**", (route) => {
    options.onScreener?.();
    return route.fulfill({ status: 200, json: lowBuyResponseFixture });
  });
  await page.route("**/api/screeners/low-buy/priority-board?**", (route) => route.fulfill({ status: 200, json: priorityBoardFixture }));
  await page.route("**/api/screeners/low-buy/quotes?**", (route) =>
    route.fulfill({
      status: 200,
      json: { updated_at: "09:45:00", quotes: [quoteFixture("000001", options.quotePrice), quoteFixture("600000", options.quotePrice)] },
    }),
  );
  await page.route("**/api/screeners/low-buy/strategies", (route) => route.fulfill({ status: 200, json: strategiesFixture }));
  await page.route("**/api/strategies/meta", (route) => route.fulfill({ status: 200, json: metaFixture }));
}

function analysisResponse(symbol: string) {
  return {
    symbol,
    instrument: { symbol, name: symbol === "600000" ? "浦发银行" : "平安银行" },
    quote: quoteFixture(symbol),
    bars: klineFixture(),
    assumptions: ["量价配合"],
    compliance_notes: [],
    events: [],
    metrics: { signal_score: symbol === "600000" ? 91 : 82 },
    microstructure: { available: true, buy_pressure: 0.62, sell_pressure: 0.31, large_order_flow: 0.2, notes: "买盘占优" },
    rules: { symbol, requires_base_position: true, same_day_sell_allowed: false, supports_negative_t: false, supports_positive_t: true, turnaround_mode: "t1", notes: "" },
    sector: {},
    ai: { enabled: true, confidence: 0.7, summary: "量价结构改善", suggestions: ["等待回踩确认"], warnings: [] },
    suggestion: {
      action: "positive_t",
      effective_action: "positive_t",
      plain_action_text: "轻仓低吸",
      plain_action_reason: "接近支撑位",
      plain_execution_text: "分批执行",
      plain_invalid_condition: "跌破支撑",
      position_pct: 0.2,
      signal_score: symbol === "600000" ? 91 : 82,
      risk_level: "medium",
      reasons: ["关键位有效"],
    },
  };
}

function quoteFixture(symbol: string, priceOverride?: (symbol: string) => number | undefined) {
  const price = priceOverride?.(symbol) ?? (symbol === "600000" ? 8.72 : 12.3);
  return {
    symbol,
    name: symbol === "600000" ? "浦发银行" : "平安银行",
    last_price: price,
    latest_price: price,
    change_pct: symbol === "600000" ? 0.012 : -0.004,
    volume_ratio: 1.2,
    data_quality: "fresh",
    timestamp: "2026-06-06T01:45:00Z",
  };
}

function klineFixture() {
  return Array.from({ length: 16 }, (_, index) => ({
    timestamp: `2026-05-${String(index + 10).padStart(2, "0")}`,
    close: 8.4 + index * 0.03,
    open: 8.3,
    high: 8.8,
    low: 8.2,
    volume: 10000,
    amount: 100000,
    liquidity_tier: "normal",
    tracking_index_symbol: "000300",
  }));
}

const keyLevelFixture = {
  data_quality: "ok",
  explanation: "关键位正常",
  key_level_candidates: [
    { direction: "support", level_type: "ma20", price: 8.5, strength_score: 82, zone_low: 8.45, zone_high: 8.55, invalid_condition: "跌破 8.45" },
    { direction: "resistance", level_type: "swing_high", price: 9.1, strength_score: 65, zone_low: 9.05, zone_high: 9.15, invalid_condition: "放量突破" },
  ],
};

function anomalyFixture(symbol: string) {
  return { symbol, name: quoteFixture(symbol).name, anomaly_level: "normal", anomaly_text: "暂无异常", pattern: "normal", score: 0, data_quality_text: "正常", updated_at: "09:45:00" };
}

const candidateBase = {
  data_quality_text: "数据完整",
  risk_tier: "note",
  strategy_title: "N形洗盘低吸",
  strategy_key: "n_pattern_long_wash",
  display_lane_title: "低吸候选",
  entry_zone_low: 8.5,
  entry_zone_high: 8.8,
  stop_loss: 8.35,
  suggested_position_pct: 0.2,
  trigger_condition: "回踩缩量",
  invalid_condition: "跌破支撑",
  strategy_performance_text: "近 60 日有效",
};

const priorityBoardFixture = {
  as_of_date: "2026-06-06",
  immediate_count: 1,
  focus_count: 1,
  total_candidates: 2,
  market_state_text: "震荡可做",
  portfolio_risk: { risk_level: "note", recommended_total_cap_pct: 0.4 },
  simple_buckets: [
    { key: "buy_now", title: "立即处理", count: 1, description: "信号进入执行区" },
    { key: "wait_price", title: "等待价格", count: 1, description: "等待回踩" },
  ],
  family_sections: [
    {
      family_key: "wash",
      family_text: "洗盘低吸",
      performance: { evaluated_signals: 12, hit_rate: 0.58, net_win_rate: 0.5, avg_net_return_pct: 0.026 },
      items: [
        { ...candidateBase, symbol: "000001", name: "平安银行", latest_price: 12.3, change_pct: -0.004, priority_score: 88, buy_signal_text: "立即处理", simple_bucket: "buy_now", simple_bucket_text: "立即处理", action_summary: "缩量回踩到位" },
        { ...candidateBase, symbol: "600000", name: "浦发银行", latest_price: 8.72, change_pct: 0.012, priority_score: 83, buy_signal_text: "等待回踩", simple_bucket: "buy_now", simple_bucket_text: "立即处理", action_summary: "接近支撑位" },
      ],
    },
  ],
};

const lowBuyResponseFixture = {
  updated_at: "2026-06-06T01:45:00Z",
  is_stale: false,
  summary: {},
  strategy: { strategy_key: "n_pattern_long_wash" },
  priority_board: priorityBoardFixture,
  confirmed_candidates: [],
  watch_candidates: [],
};

const strategiesFixture = {
  default_strategy: "n_pattern_long_wash",
  production_strategies: ["n_pattern_long_wash"],
  items: [
    { strategy_key: "n_pattern_long_wash", strategy_title: "N形洗盘低吸", layer: "production", status: "active", status_text: "生产观察", tier: "core" },
    { strategy_key: "sector_rotation", strategy_title: "板块轮动", layer: "research", status: "watch", status_text: "研究", tier: "research" },
  ],
};

const metaFixture = {
  strategies: [
    { key: "n_pattern_long_wash", display_name: "N形洗盘低吸", name: "N形洗盘低吸", tier: "core", category_key: "production", promotion_status_text: "生产观察" },
    { key: "sector_rotation", display_name: "板块轮动", name: "板块轮动", tier: "research", category_key: "research", promotion_status_text: "研究" },
  ],
};

function routeSymbol(url: string): string {
  const pathname = new URL(url).pathname;
  return decodeURIComponent(pathname.split("/").at(-1) ?? "000001");
}

const paperWorkspaceFixture = {
  api_version: "v1",
  schema_version: "v15",
  generated_at: "2026-06-06 09:45:00",
  account: {
    id: 1,
    name: "默认模拟账户",
    cash_available: 88000,
    frozen_cash: 0,
    initial_cash: 100000,
    market_value: 12000,
    status: "active",
    today_pnl: 80,
    total_assets: 100220,
    total_return_pct: 0.22,
  },
  positions: [],
  orders: [],
  trades: [],
  stock_pnl: { summary: {}, items: [] },
  performance: {},
  strategy_performance: [],
  market_performance: [],
  tag_performance: [],
  risk_events: [],
  auto_trading_status: { running: false, engine_running: false, trading_time: true },
  auto_trading_runs: [],
  partial_errors: [],
};
