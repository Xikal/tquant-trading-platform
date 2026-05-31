import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const baseUrl = (process.env.FRONTEND_PERF_URL || "http://127.0.0.1:4173").replace(/\/$/, "");
const reportPath = resolve("dist", "render-performance-profile.json");
const now = "2026-05-30T10:30:00+08:00";
const symbols = Array.from({ length: 180 }, (_, index) => `${510300 + index}`);
const mockUser = {
  id: 1,
  username: "perf",
  display_name: "Perf",
  can_paper_trade: true,
  roles: ["viewer"],
  created_at: now,
};

const baseCandidate = {
  strategy_key: "first_board",
  strategy_title: "首板低吸",
  strategy_titles: ["首板低吸"],
  strategy_count: 1,
  family_count: 1,
  strategy_family_text: "核心策略",
  market: "SH",
  instrument_type: "etf",
  sector_name: "ETF",
  latest_price: 3.45,
  change_pct: 0.6,
  quote_timestamp: now,
  data_quality: "fresh",
  data_quality_text: "fresh",
  board_date: "2026-05-29",
  board_count: 1,
  retracement_days: 2,
  score: 82,
  priority_score: 82,
  strategy_weight_score: 18,
  industry_rotation_bonus: 8,
  industry_rotation_text: "主线温和修复",
  action_summary: "等待买点确认",
  blocked_reason: "",
  entry_zone_low: 3.38,
  entry_zone_high: 3.48,
  stop_loss: 3.31,
  take_profit: 3.62,
  ma5: 3.42,
  ma10: 3.39,
  ma20: 3.36,
  volume_burst_ratio: 1.5,
  volume_shrink_ratio: 0.72,
  support_distance_pct: 1.2,
  distribution_risk_score: 18,
  false_breakout_flag: false,
  stall_after_volume_flag: false,
  intraday_reversal_flag: false,
  execution_ready: true,
  execution_note: "回踩承接确认",
  entry_distance_pct: -0.4,
  suggested_position_pct: 0.12,
  suggested_position_text: "12%",
  market_state: "repair",
  market_state_text: "震荡修复",
  market_state_strength: 58,
  market_position_multiplier: 0.8,
  confirmed_trade_date: "2026-05-30",
  summary_reason: "主线 ETF 回踩承接",
  buy_signal_state: "near_entry",
  buy_signal_text: "接近买点",
  buy_signal_hint: "等待价格进入买点区",
  recommendation_days: 1,
  reasons: ["回踩承接"],
  risks: [],
  tags: ["ETF", "主线"],
};

const priorityItems = symbols.map((symbol, index) => ({
  ...baseCandidate,
  symbol,
  name: `性能样本${index + 1}`,
  latest_price: Number((3.2 + index * 0.01).toFixed(3)),
  change_pct: Number((((index % 13) - 6) * 0.28).toFixed(2)),
  score: 92 - (index % 38),
  priority_score: 92 - (index % 38),
  entry_zone_low: Number((3.1 + index * 0.01).toFixed(3)),
  entry_zone_high: Number((3.18 + index * 0.01).toFixed(3)),
  stop_loss: Number((3.02 + index * 0.01).toFixed(3)),
  buy_signal_state: index % 5 === 0 ? "buy_now" : index % 3 === 0 ? "observe_confirmed" : "near_entry",
  buy_signal_text: index % 5 === 0 ? "现在可买" : index % 3 === 0 ? "观察确认" : "接近买点",
}));

const watchSignals = priorityItems.slice(0, 120).map((item, index) => ({
  id: index + 1,
  symbol: item.symbol,
  name: item.name,
  base_position: 1000 + index * 10,
  available_position: 800 + index * 10,
  cost_basis: item.latest_price - 0.08,
  memo: "",
  quote: {
    symbol: item.symbol,
    name: item.name,
    last_price: item.latest_price,
    change_pct: item.change_pct,
    timestamp: now,
  },
  rules: {
    same_day_sell_allowed: false,
    supports_positive_t: true,
    supports_negative_t: true,
  },
  signal: {
    action: index % 4 === 0 ? "positive_t" : "hold",
    signal_score: 70 + (index % 18),
    tradability_score: 72,
    risk_level: index % 7 === 0 ? "high" : "medium",
    reason: "持仓做T监控",
    blocker: "",
    entry_price: item.entry_zone_low,
    exit_price: item.entry_zone_high,
    stop_loss: item.stop_loss,
    expected_profit_pct: 1.4,
    position_pct: 0.12,
  },
  plain_action_text: index % 4 === 0 ? "轻仓正T" : "暂不操作",
  plain_action_reason: "等待分时承接确认。",
  plain_execution_text: "仅提醒，不自动下单。",
  plain_invalid_condition: "跌破止损放弃。",
}));

const trackingItems = priorityItems.slice(0, 160).map((item, index) => ({
  id: `first_board:${item.symbol}:2026-05-29`,
  symbol: item.symbol,
  name: item.name,
  strategy_key: "first_board",
  strategy_name: "首板低吸",
  strategy_family: "core",
  signal_state: item.buy_signal_state,
  signal_text: item.buy_signal_text,
  observe_only: false,
  lifecycle_status: "active",
  lifecycle_status_text: "仍在跟踪",
  first_signal_date: "2026-05-29",
  latest_signal_date: "2026-05-30",
  first_signal_price: item.latest_price - 0.02,
  entry_zone_low: item.entry_zone_low,
  entry_zone_high: item.entry_zone_high,
  stop_loss: item.stop_loss,
  target_price: item.take_profit,
  current_price: item.latest_price,
  latest_trade_date: "2026-05-30",
  recommendation_days: 1,
  distance_to_entry_pct: 0,
  current_return_pct: item.change_pct,
  max_price_after_signal: item.latest_price + 0.08,
  max_gain_pct: 2.4 + (index % 8) * 0.25,
  max_drawdown_pct: -1.8,
  entry_touched: true,
  stop_triggered: false,
  stop_triggered_date: null,
  target_touched: false,
  target_touched_date: null,
  conclusion: "仍在买点区",
  failure_reason: "",
  review_text: "回踩承接仍有效，继续观察买点和止损线。",
  data_quality: "ok",
  data_quality_text: "数据完整",
  source: "perf",
  detail_available: true,
  user_friendly_status: "focus",
  user_friendly_status_text: "继续跟踪",
  user_friendly_reason: "买点触达，等待确认。",
  plain_language_summary: "买点触达，等待确认。",
  display_lane: "front_row_weighted",
  display_lane_title: "前排加权",
  matched_strategy_variants: ["front_row_weighted"],
  best_holding_days: 3,
  holding_bucket: "short",
  hold_extension_state: "observe",
  hold_extension_text: "观察",
  stop_loss_rate: 0,
  needs_review: false,
  failure_tags: [],
  display_sectors: ["ETF"],
  board_type: "etf",
  board_type_text: "ETF",
  future_leak_check: "passed",
}));

const paperTrades = priorityItems.slice(0, 150).map((item, index) => ({
  id: index + 1,
  order_id: index + 1,
  account_id: 1,
  symbol: item.symbol,
  side: index % 3 === 0 ? "sell" : "buy",
  price: item.latest_price,
  quantity: 100 + (index % 8) * 100,
  gross_amount: item.latest_price * (100 + (index % 8) * 100),
  commission: 1,
  stamp_tax: index % 3 === 0 ? 1 : 0,
  transfer_fee: 0,
  net_amount: item.latest_price * (100 + (index % 8) * 100),
  strategy_key: "first_board",
  entry_reason: "回踩承接确认",
  entry_reason_code: "support",
  exit_reason: "冲高兑现",
  exit_reason_code: "take_profit",
  commission_warning: "",
  trade_time: now,
}));

function priorityBoard() {
  return {
    strategy: "first_board",
    trade_date: "2026-05-30",
    latest_trade_date: "2026-05-30",
    updated_at: now,
    strategy_key: "first_board",
    strategy_title: "首板低吸",
    display_lane: "front_row_weighted",
    display_lane_title: "生产优先榜",
    market_state_text: "震荡修复",
    directional_bias_text: "低吸优先",
    hot_industries: ["ETF", "半导体", "机器人"],
    stock_up_ratio: 0.56,
    limit_up_count: 48,
    immediate_count: 28,
    focus_count: 72,
    track_count: 80,
    total_candidates: priorityItems.length,
    data_quality: "fresh",
    data_quality_text: "fresh",
    portfolio_risk: { risk_level: "medium" },
    family_sections: [],
    items: priorityItems,
    total: priorityItems.length,
  };
}

function strategyTrackingList() {
  return {
    items: trackingItems,
    total: trackingItems.length,
    limit: 200,
    offset: 0,
    sort: "max_gain_desc",
    summary: {
      tracking_count: trackingItems.length,
      active_count: trackingItems.length,
      today_new_count: 12,
      in_entry_zone_count: 48,
      stopped_count: 0,
      needs_review_count: 0,
      abnormal_return_count: 0,
      shadow_observation_count: 0,
      avg_current_return_pct: 0.88,
      median_max_gain_pct: 1.75,
      data_quality: "ok",
      data_quality_text: "数据完整",
      generated_at: now,
    },
    performance: [],
    market_segments: [],
    shadow_observations: [],
    partial_errors: [],
    production_writeable: false,
    read_path: "perf",
    notes: [],
  };
}

function strategyTrackingSnapshot() {
  const list = strategyTrackingList();
  return {
    status: "fresh",
    stale: false,
    generated_at: now,
    source_data_cutoff: now,
    data_version: "perf",
    snapshot_key: "strategy-tracking:perf",
    as_of_date: "2026-05-30",
    payload: {
      summary: list.summary,
      items: list.items,
      performance: list.performance,
      market_segments: list.market_segments,
      holding_summary: { items: [], generated_at: now, data_quality: "ok", production_writeable: false },
      shadow_observations: list.shadow_observations,
      audit: {
        future_leak_check: "passed",
        checked_count: list.items.length,
        violation_count: 0,
        abnormal_return_count: 0,
        needs_review_count: 0,
        audit_flags: [],
      },
    },
    total: list.total,
    limit: list.limit,
    offset: list.offset,
    sort: list.sort,
    partial_errors: list.partial_errors,
    production_writeable: list.production_writeable,
    read_path: list.read_path,
    notes: list.notes,
  };
}

function paperWorkspace() {
  return {
    api_version: "v1",
    schema_version: "perf",
    generated_at: now,
    account: {
      id: 1,
      name: "Perf 模拟盘",
      initial_cash: 100000,
      cash_available: 90000,
      frozen_cash: 0,
      market_value: 12000,
      total_assets: 102000,
      realized_pnl: 1000,
      unrealized_pnl: 1000,
      total_return_pct: 2,
      max_drawdown_pct: -1,
      status: "active",
      today_return_pct: 0.3,
    },
    positions: [],
    orders: [],
    trades: paperTrades,
    stock_pnl: { items: [], summary: { item_count: 0, account_total_pnl: 2000, stock_total_pnl: 2000, realized_pnl: 1000, unrealized_pnl: 1000, reconciliation_gap: 0 } },
    performance: { total_return_pct: 2, max_drawdown_pct: -1, win_rate_pct: 55, net_win_rate_pct: 53, avg_trade_return_pct: 0.4, avg_win_pct: 1.1, avg_loss_pct: -0.6, profit_factor: 1.4, stop_loss_rate_pct: 2, total_trades: paperTrades.length, avg_hold_days: 2, win_loss_ratio: 1.3 },
    sector_etf_t0_performance: null,
    strategy_performance: [],
    market_performance: [],
    tag_performance: [],
    risk_events: [],
    auto_trading_status: { running: false, engine_running: false, trading_time: true, dry_run: true, account_status: "active", interval_seconds: 60, last_cycle_summary: "perf", total_cycles: 0, total_executed: 0, total_errors: 0 },
    auto_trading_runs: [],
    partial_errors: [],
  };
}

async function installRoutes(page) {
  await page.addInitScript(() => {
    localStorage.setItem("tquant:auth:persistence_mode", "session");
    localStorage.setItem("tquant:ritual:daily-blessing:1:2026-05-30", "seen");
    sessionStorage.setItem("tquant:auth:access_token", "perf-token");
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, "");
    const response = (body, status = 200) => route.fulfill({
      status,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(body),
    });
    if (path === "/auth/me" || path === "/auth/refresh") return response({ user: mockUser, access_token: "perf-token", token_type: "bearer", expires_in: 3600 });
    if (path === "/strategies/meta") return response({ strategies: [{ key: "first_board", display_name: "首板低吸", tier: "core", enabled: true }] });
    if (path === "/bff/v1/workspace/monitor") return response({
      monitor_snapshot: {
        priority_board: priorityBoard(),
        market_breadth: { updated_at: now, data_quality: "fresh", data_quality_text: "fresh", stock_up_ratio: 0.56, limit_up_count: 48, limit_down_count: 5, board_height: 4 },
        market_pulse: { data_quality: "fresh", data_quality_text: "fresh", pulse_level: "repair", pulse_text: "市场震荡修复", suggested_action: "低吸优先", market_strength_text: "偏暖", emotion_text: "中性", hourly_snapshot_text: "fresh" },
        review_status: { status_text: "午盘已生成", next_trigger_at: now, has_midday: true, has_close: false, risk_alert_count: 0, suggested_action: "控制仓位" },
        review_reports: [],
        key_level_alerts: [],
        sector_etf_t0: { opportunities: priorityItems.slice(0, 80).map((item) => ({ etf_symbol: item.symbol, etf_name: item.name, source_signal_symbol: item.symbol, source_signal_name: item.name, sector_name: "ETF", etf_category: "sector", t0_eligible: true, bias: "positive_t", bias_text: "正T", confidence: 0.72, intraday_signal_text: "低吸", intraday_signal_confidence: 0.66, last_price: item.latest_price, change_pct: item.change_pct, reason: "板块信号明确", entry_zone: "低吸区", sell_zone: "冲高区", min_amount: 10000000, risk: "流动性" })) },
        watchlist_signals: watchSignals,
        paired_hedge: null,
      },
    });
    if (path === "/market/hourly-snapshots/history") return response({ items: [], total: 0 });
    if (path === "/market/trading-session") return response({ updated_at: now, is_trading_day: true, is_trading_now: true, current_time: now, timezone: "Asia/Shanghai", data_quality_text: "fresh" });
    if (path === "/strategy-tracking/snapshot") return response(strategyTrackingSnapshot());
    if (path === "/strategy-tracking/items") return response(strategyTrackingList());
    if (path === "/strategy-tracking/summary") return response(strategyTrackingList().summary);
    if (path === "/strategy-tracking/performance") return response([]);
    if (path === "/bff/v1/workspace/paper") return response(paperWorkspace());
    if (path === "/paper/trades") return response({ trades: paperTrades });
    if (path === "/paper/trades/tags") return response({ items: {} });
    if (path.startsWith("/paper/trades/") && path.endsWith("/tags")) return response([]);
    if (path === "/paper/orders") return response([]);
    if (path === "/paper/positions") return response({ positions: [], total_market_value: 0, total_unrealized_pnl: 0 });
    if (path === "/paper/positions/refresh") return response({ positions: [], total_market_value: 0, total_unrealized_pnl: 0 });
    if (path === "/paper/account") return response(paperWorkspace().account);
    if (path === "/paper/performance") return response(paperWorkspace().performance);
    if (path === "/paper/performance/stock-pnl") return response(paperWorkspace().stock_pnl);
    if (path === "/paper/performance/dashboard") return response({ account: {}, equity_curve: [], win_rate_trend: [], strategy_trend: [], market_perf_heatmap: [], strategy_market_matrix: [], strategy_correlation: { strategies: [], matrix: [], rows: [], notes: [] }, today_report: null, review_reports: [], updated_at: now });
    if (path === "/paper/performance/sector-etf-t0") return response(null);
    if (path.startsWith("/paper/performance/by-") || path === "/paper/risk/events" || path === "/paper/auto-trading/runs") return response([]);
    if (path === "/paper/auto-trading/status") return response(paperWorkspace().auto_trading_status);
    if (path.startsWith("/market") || path.startsWith("/settings") || path.startsWith("/admin") || path.startsWith("/screeners") || path.startsWith("/bff")) return response({});
    return response({});
  });
}

async function scenario(page, path, name, locatorText) {
  await page.goto(`${baseUrl}${path}`, { waitUntil: "networkidle", timeout: 30_000 });
  await page.waitForTimeout(500);
  if (name === "strategy_tracking_table_scroll") {
    await page.waitForSelector("text=性能样本1", { timeout: 10_000 }).catch(() => {});
  } else if (name === "paper_trades_table_scroll") {
    await page.getByText("成交记录").click({ force: true }).catch(() => {});
    await page.waitForSelector("text=510300", { timeout: 10_000 }).catch(() => {});
  }
  let scrollTarget;
  if (name === "monitor_refresh_virtual_cards") {
    const target = page.locator(locatorText).first();
    await target.scrollIntoViewIfNeeded().catch(() => {});
    scrollTarget = await page.evaluateHandle((selector) => {
      const element = document.querySelector(selector);
      const candidates = [element, ...Array.from(document.querySelectorAll("*"))].filter(Boolean);
      return candidates.find((node) => node.scrollHeight > node.clientHeight + 40 && node.clientHeight > 120) || document.scrollingElement;
    }, locatorText);
  } else {
    scrollTarget = await page.evaluateHandle(() => document.scrollingElement);
  }
  const startRows = await page.locator(".ant-table-row, .ant-table-cell, article, [data-index]").count().catch(() => 0);
  const durations = [];
  for (let i = 0; i < 8; i += 1) {
    const duration = await page.evaluate(async (element) => {
      const start = performance.now();
      element.scrollTop = element.scrollTop + 420;
      await new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame)));
      return performance.now() - start;
    }, scrollTarget);
    durations.push(Number(duration.toFixed(2)));
  }
  const endRows = await page.locator(".ant-table-row, .ant-table-cell, article, [data-index]").count().catch(() => 0);
  const longTasks = await page.evaluate(() => performance.getEntriesByType("longtask").map((entry) => entry.duration));
  return {
    name,
    path,
    ok: durations.every((item) => item < 80),
    max_scroll_frame_ms: Math.max(...durations),
    avg_scroll_frame_ms: Number((durations.reduce((sum, item) => sum + item, 0) / durations.length).toFixed(2)),
    rendered_node_count_before: startRows,
    rendered_node_count_after: endRows,
    longtask_count: longTasks.length,
    longtask_max_ms: longTasks.length ? Number(Math.max(...longTasks).toFixed(2)) : 0,
  };
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, serviceWorkers: "block" });
const page = await context.newPage();
await installRoutes(page);

const results = [];
results.push(await scenario(page, "/monitor", "monitor_refresh_virtual_cards", ".panel"));
results.push(await scenario(page, "/strategy-tracking", "strategy_tracking_table_scroll", ".ant-table-body"));
results.push(await scenario(page, "/paper", "paper_trades_table_scroll", ".ant-table-body"));

await browser.close();
await mkdir(resolve("dist"), { recursive: true });
await writeFile(reportPath, `${JSON.stringify({
  ok: results.every((item) => item.ok),
  base_url: baseUrl,
  generated_at: new Date().toISOString(),
  scenarios: results,
}, null, 2)}\n`, "utf8");
console.log(reportPath);
process.exit(results.every((item) => item.ok) ? 0 : 1);
