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
  buy_signal_text: "接近买点（观察类·未到买入）",
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
  buy_signal_text: index % 5 === 0 ? "现在可买" : index % 3 === 0 ? "观察确认" : "接近买点（观察类·未到买入）",
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

const equityPoints = Array.from({ length: 1800 }, (_, index) => {
  const nav = 1 + index * 0.0009 + Math.sin(index / 13) * 0.018;
  return {
    date: `2021-${String(Math.floor(index / 30) % 12 + 1).padStart(2, "0")}-${String(index % 28 + 1).padStart(2, "0")}`,
    nav: Number(nav.toFixed(4)),
    benchmark_nav: Number((1 + index * 0.00045).toFixed(4)),
    drawdown_pct: Number((-Math.abs(Math.sin(index / 19)) * 3.5).toFixed(2)),
    total_value: Number((100000 * nav).toFixed(2)),
  };
});

const backtestTrades = priorityItems.slice(0, 120).map((item, index) => ({
  id: index + 1,
  trade_date: "2026-05-30",
  symbol: item.symbol,
  name: item.name,
  side: index % 2 === 0 ? "buy" : "sell",
  quantity: 100 + (index % 6) * 100,
  price: item.latest_price,
  net_amount: Number((item.latest_price * (100 + (index % 6) * 100)).toFixed(2)),
  strategy: "first_board",
  strategy_key: "first_board",
  return_pct: Number((((index % 9) - 3) * 0.35).toFixed(2)),
  pnl_pct: Number((((index % 9) - 3) * 0.35).toFixed(2)),
}));

const backtestRun = {
  id: 1,
  name: "性能样本回测",
  status: "completed",
  progress: 100,
  start_date: "2024-01-01",
  end_date: "2026-05-30",
  initial_capital: 100000,
  final_equity: 128600,
  strategies: ["first_board"],
  execution_model: "next_open",
  benchmark: "000300",
  resource_tier: "full",
  summary: {
    total_return_pct: 28.6,
    benchmark_return_pct: 10.8,
    benchmark_alpha_pct: 17.8,
    sharpe: 1.36,
    max_drawdown_pct: -6.2,
    win_rate_pct: 58.4,
    trade_count: backtestTrades.length,
    profit_factor: 1.52,
  },
  created_at: now,
  completed_at: now,
  execution_model_preview: {
    mode: "preview",
    source: "perf",
    replacement_enabled: false,
    blocked_reason: "no_daily_return_path",
    notes: ["perf mock"],
  },
};

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

function backtestList() {
  return {
    items: [backtestRun],
    total: 1,
    limit: 20,
    offset: 0,
  };
}

function backtestOptimizationList() {
  return {
    items: [{
      id: 1,
      name: "性能参数优化",
      strategy: "first_board",
      status: "completed",
      progress: 100,
      progress_pct: 100,
      best_params: { max_position_pct: 0.12 },
      best_is_score: 1.4,
      best_oos_score: 1.1,
      optimization_target: "sharpe",
      search_method: "grid",
      candidates: [],
      created_at: now,
      completed_at: now,
    }],
    total: 1,
    limit: 20,
    offset: 0,
  };
}

function backtestValidationList() {
  return {
    items: [{
      id: 1,
      name: "性能滚动验证",
      strategy: "first_board",
      status: "completed",
      progress: 100,
      progress_pct: 100,
      window_count: 4,
      oos_pass_rate: 0.75,
      avg_oos_sharpe: 1.05,
      pbo_risk: "low",
      stability_conclusion: "stable",
      windows: [],
      created_at: now,
      completed_at: now,
    }],
    total: 1,
    limit: 20,
    offset: 0,
  };
}

function analysisResponse(symbol = "510300", index = 0) {
  const item = priorityItems[index % priorityItems.length];
  return {
    symbol,
    instrument: {
      symbol,
      name: item.name,
      market: "SH",
      instrument_type: "etf",
      sector_name: "ETF",
    },
    quote: {
      symbol,
      name: item.name,
      market: "SH",
      instrument_type: "etf",
      last_price: item.latest_price,
      change_pct: item.change_pct,
      change_amount: 0.02,
      open_price: item.latest_price - 0.01,
      high_price: item.latest_price + 0.05,
      low_price: item.latest_price - 0.04,
      prev_close: item.latest_price - 0.02,
      volume: 12345678,
      amount: 43210000,
      turnover_rate: 1.2,
      volume_ratio: 1.1,
      timestamp: now,
      data_source: "perf",
      source_quality: "fresh",
    },
    rules: {
      symbol,
      turnaround_mode: "t0",
      supports_positive_t: true,
      supports_negative_t: true,
      same_day_sell_allowed: false,
      requires_base_position: true,
      notes: "perf",
    },
    sector: {
      sector_name: "ETF",
      sector_strength: 72,
      market_strength: 58,
      alignment_score: 64,
      notes: "主线修复",
    },
    events: [],
    microstructure: {
      available: true,
      buy_pressure: 0.58,
      sell_pressure: 0.42,
      large_order_flow: 0.12,
      notes: "承接正常",
    },
    bars: equityPoints.slice(0, 120).map((point, barIndex) => ({
      timestamp: point.date,
      open: 3 + barIndex * 0.002,
      close: 3.02 + barIndex * 0.002,
      high: 3.05 + barIndex * 0.002,
      low: 2.98 + barIndex * 0.002,
      volume: 1000000 + barIndex * 1000,
      amount: 3000000 + barIndex * 3000,
    })),
    metrics: { signal_score: 78, tradability_score: 74 },
    suggestion: {
      action: "hold",
      position_pct: 0.12,
      risk_level: "medium",
      signal_score: 78 - (index % 5),
      tradability_score: 74,
      confidence: 0.72,
      expected_profit_pct: 1.5,
      scenario: "低吸观察",
      reasons: ["回踩承接"],
      blocking_rules: [],
      strategy_notes: "等待确认",
      is_actionable: index % 3 === 0,
      plain_action_text: "观察",
      plain_action_reason: "买点未完全确认。",
      plain_execution_text: "仅提醒，不自动下单。",
      plain_invalid_condition: "跌破止损放弃。",
    },
    ai: { enabled: false, summary: "", confidence: 0, suggestions: [], warnings: [] },
    compliance_notes: [],
    assumptions: [],
    analysis_log_id: null,
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
    if (path === "/backtests") return response(backtestList());
    if (path === "/backtests/optimize") return response(backtestOptimizationList());
    if (path === "/backtests/optimize/1") return response(backtestOptimizationList().items[0]);
    if (path === "/backtests/validate") return response(backtestValidationList());
    if (path === "/backtests/validate/1") return response(backtestValidationList().items[0]);
    if (path === "/backtests/1") return response(backtestRun);
    if (path === "/backtests/1/equity") return response({ items: equityPoints, total: equityPoints.length });
    if (path === "/backtests/1/trades") return response({ items: backtestTrades, total: backtestTrades.length, limit: 50, offset: 0 });
    if (path === "/backtests/1/monthly-returns") return response({
      items: [
        { month: "2026-01", return_pct: 2.1 },
        { month: "2026-02", return_pct: -0.8 },
        { month: "2026-03", return_pct: 3.4 },
      ],
      summary: { best_month: "2026-03", worst_month: "2026-02" },
    });
    if (path === "/backtests/1/attribution") return response({
      version: "perf",
      by_strategy: [{ bucket: "first_board", label: "首板低吸", trade_count: 82, win_rate_pct: 58, return_pct: 18.6 }],
      industry: [{ bucket: "ETF", label: "ETF", trade_count: 36, win_rate_pct: 60, return_pct: 8.2 }],
      notes: [],
    });
    if (path === "/backtests/1/strategy-correlation") return response({ strategies: ["first_board"], matrix: [[1]], rows: [], notes: [] });
    if (path === "/backtests/compare") return response({ items: [], notes: [] });
    if (path === "/backtests/verdict-thresholds") return response({
      thresholds: {
        light: { min_return_pct: 5, min_sharpe: 0.8, max_drawdown_pct: -12, cautious_min_return_pct: 3, cautious_max_drawdown_pct: -15 },
        full: { min_return_pct: 8, min_sharpe: 1, max_drawdown_pct: -10, cautious_min_return_pct: 5, cautious_max_drawdown_pct: -12 },
        walk_forward: { min_return_pct: 6, min_sharpe: 0.9, max_drawdown_pct: -11, cautious_min_return_pct: 4, cautious_max_drawdown_pct: -13 },
      },
    });
    if (path === "/backtests/strategy-improvement-report") return response({
      summary: { overall_status: "watch_only", formal_backtest_allowed: false, generated_at: now },
      data_coverage: { status: "partial", coverage_pct: 88 },
      minute_coverage: { status: "blocked", blocked_reason: "perf_mock" },
      strategy_governance: { status: "shadow" },
    });
    if (path === "/analyze") return response(analysisResponse());
    if (path === "/analyze/batch") return response(Array.from({ length: 8 }, (_, index) => analysisResponse(priorityItems[index].symbol, index)));
    if (path.startsWith("/market/intraday-anomaly/")) return response({
      symbol: path.split("/").pop() ?? "510300",
      name: "性能样本",
      anomaly_level: "normal",
      anomaly_text: "无异常",
      score: 0,
      pattern: "normal",
      action_hint: "观察",
      reasons: [],
      risk_notes: [],
      data_quality_text: "fresh",
      updated_at: now,
    });
    if (path.startsWith("/market") || path.startsWith("/settings") || path.startsWith("/admin") || path.startsWith("/screeners") || path.startsWith("/bff")) return response({});
    return response({});
  });
}

function profiledUrl(path) {
  const url = new URL(path, `${baseUrl}/`);
  url.searchParams.set("perf_profile", "1");
  return url.toString();
}

async function gotoMeasured(page, path) {
  const startedAt = Date.now();
  await page.goto(profiledUrl(path), { waitUntil: "networkidle", timeout: 30_000 });
  return Date.now() - startedAt;
}

async function routeSwitchMeasured(page, path) {
  const startedAt = Date.now();
  await page.evaluate((nextPath) => {
    const anchor = document.createElement("a");
    anchor.href = `${nextPath}${nextPath.includes("?") ? "&" : "?"}perf_profile=1`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  }, path);
  await page.waitForURL((url) => url.pathname === path, { timeout: 30_000 }).catch(() => {});
  await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {});
  await page.waitForTimeout(250);
  return Date.now() - startedAt;
}

async function scenario(page, path, name, locatorText, fromPath = "/monitor") {
  const firstEntryMs = await gotoMeasured(page, path);
  await page.waitForTimeout(250);
  const secondEntryMs = await gotoMeasured(page, path);
  let routeSwitchMs = secondEntryMs;
  if (fromPath !== path) {
    await gotoMeasured(page, fromPath);
    routeSwitchMs = await routeSwitchMeasured(page, path);
  }
  await page.waitForTimeout(500);
  await page.evaluate(() => {
    if (window.__TQUANT_FRONTEND_PERF__) {
      window.__TQUANT_FRONTEND_PERF__.commits = [];
    }
  }).catch(() => {});
  if (name === "strategy_tracking_table_scroll") {
    await page.waitForSelector("text=性能样本1", { timeout: 10_000 }).catch(() => {});
  } else if (name === "paper_trades_table_scroll") {
    await page.getByText("成交记录").click({ force: true }).catch(() => {});
    await page.waitForSelector("text=510300", { timeout: 10_000 }).catch(() => {});
  } else if (name === "backtest_dashboard_dense_chart") {
    await page.waitForSelector("text=性能样本回测", { timeout: 10_000 }).catch(() => {});
    await page.waitForFunction(() => (window.__TQUANT_FRONTEND_PERF__?.workerTasks ?? []).some((item) => item.kind === "chartDownsample"), null, { timeout: 5_000 }).catch(() => {});
  } else if (name === "analysis_workspace_entry") {
    await page.waitForSelector("text=智能分析", { timeout: 10_000 }).catch(() => {});
  }
  let scrollTarget;
  if (name === "monitor_refresh_virtual_cards" && locatorText) {
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
  const domBefore = await page.evaluate(() => document.querySelectorAll("*").length);
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
  const domAfter = await page.evaluate(() => document.querySelectorAll("*").length);
  const chartResizeFrameMs = await page.evaluate(async () => {
    if (!document.querySelector("canvas")) {
      return 0;
    }
    const start = performance.now();
    window.dispatchEvent(new Event("resize"));
    await new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame)));
    return Number((performance.now() - start).toFixed(2));
  });
  const longTasks = await page.evaluate(() => performance.getEntriesByType("longtask").map((entry) => entry.duration));
  const reactCommits = await page.evaluate(() => window.__TQUANT_FRONTEND_PERF__?.commits ?? []).catch(() => []);
  const workerTasks = await page.evaluate(() => window.__TQUANT_FRONTEND_PERF__?.workerTasks ?? []).catch(() => []);
  const reactDurations = reactCommits.map((item) => item.actualDuration).filter((item) => Number.isFinite(item));
  const avgScrollMs = Number((durations.reduce((sum, item) => sum + item, 0) / durations.length).toFixed(2));
  const maxScrollMs = Math.max(...durations);
  const longtaskMaxMs = longTasks.length ? Number(Math.max(...longTasks).toFixed(2)) : 0;
  const reactCommitP95 = percentile(reactDurations, 0.95);
  return {
    name,
    path,
    ok: durations.every((item) => item < 80) && reactCommitP95 < 80 && longtaskMaxMs < 120,
    first_entry_ms: firstEntryMs,
    second_entry_ms: secondEntryMs,
    route_switch_ms: routeSwitchMs,
    max_scroll_frame_ms: maxScrollMs,
    avg_scroll_frame_ms: avgScrollMs,
    scroll_fps_estimate: Number((1000 / Math.max(avgScrollMs, 1)).toFixed(1)),
    rendered_node_count_before: startRows,
    rendered_node_count_after: endRows,
    dom_node_count_before: domBefore,
    dom_node_count_after: domAfter,
    dom_node_peak: Math.max(domBefore, domAfter),
    chart_count: await page.locator("canvas").count().catch(() => 0),
    chart_refresh_ms: chartResizeFrameMs,
    react_commit_count: reactDurations.length,
    react_commit_p95_ms: reactCommitP95,
    react_commit_max_ms: percentile(reactDurations, 1),
    worker_tasks: summarizeWorkerTasks(workerTasks),
    longtask_count: longTasks.length,
    longtask_max_ms: longtaskMaxMs,
    bottleneck: classifyBottleneck({
      chartRefreshMs: chartResizeFrameMs,
      entryMs: secondEntryMs,
      longtaskMaxMs,
      maxScrollMs,
      reactCommitP95,
    }),
  };
}

function summarizeWorkerTasks(samples) {
  const grouped = new Map();
  for (const sample of samples) {
    const key = sample.kind || "unknown";
    const current = grouped.get(key) ?? {
      count: 0,
      elapsed: [],
      input_count_max: 0,
      sources: {},
      total: [],
    };
    current.count += 1;
    current.elapsed.push(Number(sample.elapsed_ms || 0));
    current.total.push(Number(sample.total_ms || 0));
    current.input_count_max = Math.max(current.input_count_max, Number(sample.input_count || 0));
    current.sources[sample.source || "unknown"] = (current.sources[sample.source || "unknown"] ?? 0) + 1;
    grouped.set(key, current);
  }
  return Object.fromEntries([...grouped.entries()].map(([kind, item]) => [kind, {
    count: item.count,
    elapsed_p95_ms: percentile(item.elapsed, 0.95),
    elapsed_max_ms: percentile(item.elapsed, 1),
    input_count_max: item.input_count_max,
    sources: item.sources,
    total_p95_ms: percentile(item.total, 0.95),
  }]));
}

function percentile(values, p) {
  if (!values.length) {
    return 0;
  }
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * p) - 1));
  return Number(sorted[index].toFixed(2));
}

function classifyBottleneck({
  chartRefreshMs,
  entryMs,
  longtaskMaxMs,
  maxScrollMs,
  reactCommitP95,
}) {
  if (longtaskMaxMs >= 80) return "main_thread_long_task";
  if (reactCommitP95 >= 50) return "react_commit";
  if (chartRefreshMs >= 50) return "chart_refresh";
  if (maxScrollMs >= 50) return "scroll_render";
  if (entryMs >= 1200) return "network_or_serialization";
  return "within_budget";
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, serviceWorkers: "block" });
const page = await context.newPage();
await installRoutes(page);

const results = [];
results.push(await scenario(page, "/monitor", "monitor_refresh_virtual_cards", ".panel", "/analysis"));
results.push(await scenario(page, "/strategy-tracking", "strategy_tracking_table_scroll", ".ant-table-body"));
results.push(await scenario(page, "/paper", "paper_trades_table_scroll", ".ant-table-body"));
results.push(await scenario(page, "/backtest", "backtest_dashboard_dense_chart", ".ant-table-body"));
results.push(await scenario(page, "/analysis", "analysis_workspace_entry", ".analysis-panel"));

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
