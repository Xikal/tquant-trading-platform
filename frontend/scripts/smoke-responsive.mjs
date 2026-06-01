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
const paths = ["/monitor", "/emotion", "/analysis", "/playbook", "/strategy-tracking", "/strategy", "/backtest", "/paper", "/settings"];
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
const mockStrategyMeta = [
  {
    key: "first_board",
    name: "首板低吸",
    display_name: "首板低吸",
    description: "首板回踩确认",
    tier: "core",
    category_key: "core",
    category: "核心",
    display_category: "核心策略",
    risk_level: "medium",
    typical_holding_days: "1-3",
    sort_order: 1,
    enabled: true,
    visibility: "full",
  },
  {
    key: "volume_shrink",
    name: "缩量回踩",
    display_name: "缩量回踩",
    description: "缩量回踩确认",
    tier: "auxiliary",
    category_key: "auxiliary",
    category: "辅助",
    display_category: "辅助策略",
    risk_level: "medium",
    typical_holding_days: "2-5",
    sort_order: 2,
    enabled: true,
    visibility: "full",
  },
];
const mockLowBuyCandidate = {
  strategy_key: "first_board",
  strategy_title: "首板低吸",
  symbol: "510300",
  name: "沪深300ETF",
  market: "SH",
  instrument_type: "etf",
  sector_name: "ETF",
  latest_price: 3.45,
  change_pct: 0.6,
  quote_timestamp: now,
  data_quality: "fresh",
  data_quality_text: "fresh",
  board_date: "2026-05-25",
  board_count: 1,
  retracement_days: 2,
  score: 82,
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
  confirmed_trade_date: "2026-05-26",
  summary_reason: "主线 ETF 回踩承接",
  buy_signal_state: "near_entry",
  buy_signal_text: "接近买点",
  buy_signal_hint: "等待价格进入买点区",
  recommendation_days: 1,
};
const mockLowBuyPerformance = {
  lookback_days: 60,
  signal_count: 24,
  evaluated_signals: 18,
  filled_signals: 12,
  pending_signals: 2,
  hit_count: 9,
  hit_rate: 0.5,
  win_rate_1d: 0.52,
  win_rate_3d: 0.58,
  win_rate_5d: 0.61,
  avg_return_1d: 0.6,
  avg_return_3d: 1.4,
  avg_return_5d: 2.1,
  avg_max_gain_5d: 4.2,
  avg_max_drawdown_5d: -1.3,
  target_profit_pct: 3,
  updated_at: now,
  attribution_notes: [],
  sector_attribution: [],
  retracement_attribution: [],
  market_state_attribution: [],
  industry_tier_attribution: [],
};
const mockStrategyTrackingItem = {
  id: "first_board:510300:2026-05-25",
  symbol: "510300",
  name: "沪深300ETF",
  strategy_key: "first_board",
  strategy_name: "首板低吸",
  strategy_family: "core",
  signal_state: "near_entry",
  signal_text: "接近买点",
  observe_only: false,
  lifecycle_status: "active",
  lifecycle_status_text: "仍在跟踪",
  first_signal_date: "2026-05-25",
  latest_signal_date: "2026-05-26",
  first_signal_price: 3.42,
  entry_zone_low: 3.38,
  entry_zone_high: 3.48,
  stop_loss: 3.31,
  target_price: 3.62,
  current_price: 3.45,
  latest_trade_date: "2026-05-26",
  recommendation_days: 1,
  distance_to_entry_pct: 0,
  current_return_pct: 0.88,
  max_price_after_signal: 3.48,
  max_gain_pct: 1.75,
  max_drawdown_pct: -0.58,
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
  source: "low_buy_result_snapshot",
  detail_available: true,
};
const mockStrategyTrackingPerformance = {
  strategy_key: "first_board",
  strategy_name: "首板低吸",
  strategy_family: "core",
  recommendation_count: 1,
  entry_touched_count: 1,
  entry_touch_rate: 100,
  win_rate_3d: 100,
  win_rate_5d: 100,
  win_rate_10d: 0,
  avg_current_return_pct: 0.88,
  avg_max_gain_pct: 1.75,
  avg_max_drawdown_pct: -0.58,
  profit_loss_ratio: 1.4,
  stop_loss_rate: 0,
  active_count: 1,
  health_score: 78,
  health_grade: "B",
  sample_quality: "thin",
  health_reasons: ["买点触达正常"],
  health_risks: [],
};
const mockStrategyTrackingSummary = {
  tracking_count: 1,
  active_count: 1,
  today_new_count: 0,
  in_entry_zone_count: 1,
  stopped_count: 0,
  needs_review_count: 0,
  abnormal_return_count: 0,
  shadow_observation_count: 0,
  avg_current_return_pct: 0.88,
  median_max_gain_pct: 1.75,
  data_quality: "ok",
  data_quality_text: "数据完整",
  generated_at: now,
};
const mockStrategyTrackingList = {
  items: [mockStrategyTrackingItem],
  total: 1,
  limit: 30,
  offset: 0,
  sort: "max_gain_desc",
  summary: mockStrategyTrackingSummary,
  performance: [mockStrategyTrackingPerformance],
  market_segments: [],
  shadow_observations: [],
  partial_errors: [],
  production_writeable: false,
  read_path: "smoke",
  rust_math_used: true,
  notes: [],
};
const mockStrategyTrackingSnapshot = {
  status: "fresh",
  stale: false,
  generated_at: now,
  source_data_cutoff: now,
  data_version: "smoke",
  snapshot_key: "strategy-tracking:smoke",
  as_of_date: "2026-05-26",
  payload: {
    summary: mockStrategyTrackingSummary,
    items: [mockStrategyTrackingItem],
    performance: [mockStrategyTrackingPerformance],
    market_segments: [],
    holding_summary: { items: [], generated_at: now, data_quality: "ok", production_writeable: false },
    shadow_observations: [],
    audit: {
      future_leak_check: "passed",
      checked_count: 1,
      violation_count: 0,
      abnormal_return_count: 0,
      needs_review_count: 0,
      audit_flags: [],
    },
  },
  total: 1,
  limit: 30,
  offset: 0,
  sort: "max_gain_desc",
  partial_errors: [],
  production_writeable: false,
  read_path: "strategy_tracking_snapshot",
  notes: [],
};
const mockLowBuy = {
  strategy_key: "first_board",
  strategy_title: "首板低吸",
  strategy_subtitle: "回踩承接",
  strategy_logic: "首板后回踩确认",
  requested_mode: "quick",
  response_mode: "quick",
  as_of_date: "2026-05-26",
  latest_trade_date: "2026-05-26",
  pool_size: 120,
  scanned_count: 48,
  matched_count: 1,
  requested_scan_limit: 48,
  active_scan_limit: 48,
  full_scan_ready: true,
  full_scan_in_progress: false,
  market_state: "repair",
  market_state_text: "震荡修复",
  market_state_category: "neutral",
  market_state_category_text: "中性偏暖",
  data_quality: "fresh",
  data_quality_text: "fresh",
  market_bonus: 0.2,
  market_state_strength: 58,
  regime_confidence: 0.72,
  state_persistence_days: 2,
  transition_risk: 0.2,
  breadth_ready: true,
  emotion_ready: true,
  stock_up_ratio: 0.56,
  stock_median_change: 0.42,
  style_divergence: 0.1,
  hot_turnover: 0.22,
  hot_overlap_ratio: 0.35,
  limit_down_count: 5,
  limit_up_count: 48,
  board_height: 4,
  previous_board_height: 3,
  promotion_ratio: 0.32,
  broken_board_ratio: 0.18,
  promotion_break_gap: 0.14,
  promotion_break_pressure: 0.2,
  high_flyer_retreat_ratio: 0.12,
  high_flyer_gap_speed: 0.1,
  distribution_pressure: 0.22,
  hot_industries: ["机器人", "半导体"],
  hot_industry_source: "market",
  hot_industry_source_text: "行情",
  retracement_distribution: { "2天": 8, "3天": 5 },
  filters: { scan_mode: "quick" },
  strategy_notes: ["smoke"],
  performance: mockLowBuyPerformance,
  close_review_trade_date: "2026-05-26",
  close_review_items: [],
  confirmed_candidates: [mockLowBuyCandidate],
  history_sections: [],
  candidates: [],
};
const mockAnalysis = {
  symbol: "510300",
  instrument: { symbol: "510300", name: "沪深300ETF", market: "SH", instrument_type: "etf", sector_name: "ETF" },
  quote: {
    symbol: "510300",
    name: "沪深300ETF",
    market: "SH",
    instrument_type: "etf",
    last_price: 3.45,
    change_pct: 0.6,
    change_amount: 0.02,
    open_price: 3.42,
    high_price: 3.48,
    low_price: 3.4,
    prev_close: 3.43,
    volume: 1200000,
    amount: 4140000,
    timestamp: now,
  },
  rules: {
    symbol: "510300",
    turnaround_mode: "t0",
    supports_positive_t: true,
    supports_negative_t: true,
    same_day_sell_allowed: true,
    requires_base_position: false,
    notes: "ETF 可做 T",
  },
  sector: { sector_name: "ETF", sector_strength: 60, market_strength: 58, alignment_score: 65, notes: "smoke" },
  events: [],
  microstructure: { available: true, buy_pressure: 0.6, sell_pressure: 0.4, large_order_flow: 0.1, notes: "smoke" },
  bars: [
    { timestamp: now, open: 3.42, close: 3.45, high: 3.48, low: 3.4, volume: 1000, amount: 3450 },
    { timestamp: now, open: 3.45, close: 3.46, high: 3.47, low: 3.44, volume: 900, amount: 3114 },
  ],
  metrics: { signal_score: 72, expected_profit_pct: 1.8, min_profit_pct: 1.2, slippage_bps: 3 },
  suggestion: {
    action: "positive_t",
    entry_price: 3.44,
    exit_price: 3.58,
    position_pct: 0.12,
    stop_loss: 3.31,
    risk_level: "medium",
    signal_score: 72,
    tradability_score: 76,
    confidence: 0.68,
    expected_profit_pct: 1.8,
    scenario: "pullback",
    signal_layer: "light_execute",
    signal_layer_text: "轻仓执行",
    reasons: ["回踩承接"],
    blocking_rules: [],
    take_profit: 3.62,
    strategy_notes: "smoke",
    plain_action_text: "轻仓正T",
    plain_action_reason: "ETF 回踩承接",
    plain_execution_text: "低吸后高抛",
    plain_invalid_condition: "跌破 3.31 放弃",
    is_actionable: true,
  },
  ai: { enabled: false, summary: "未启用", confidence: 0, suggestions: [], warnings: [] },
  compliance_notes: [],
  assumptions: [],
};
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
      markers: [{ kind: "first_signal", trade_date: "2026-05-25", price: 3.42, label: "首次推荐" }],
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
    if (path === "/screeners/low-buy/quotes") return response({ items: { "510300": { latest_price: 3.45, change_pct: 0.6, quote_timestamp: now, in_entry_zone: true, distance_to_entry_pct: -0.2, stop_confirmed: false, buy_signal_state: "near_entry", buy_signal_text: "接近买点", buy_signal_hint: "等待确认" } } });
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
    if (path === "/backtests") return response({ items: [], total: 0, limit: 20, offset: 0 });
    if (path === "/backtests/verdict-thresholds") return response({ thresholds: {} });
    if (path === "/backtests/compare") return response({ items: [] });
    if (path.startsWith("/backtests/") && path.endsWith("/equity")) return response({ items: [] });
    if (path.startsWith("/backtests/") && path.endsWith("/trades")) return response({ items: [], total: 0, limit: 50, offset: 0 });
    if (path.startsWith("/backtests/") && path.endsWith("/monthly-returns")) return response({ items: [] });
    if (path.startsWith("/backtests/") && path.endsWith("/attribution")) return response({});
    if (path.startsWith("/backtests/") && path.endsWith("/strategy-correlation")) return response({ strategies: [], matrix: [] });
    if (path.startsWith("/backtests/") && path.endsWith("/portfolio-optimization")) return response({ items: [] });
    if (path.startsWith("/backtests/") && path.endsWith("/position-policy-research")) return response({ items: [] });
    if (path.startsWith("/backtests/")) return response(emptyList);
    if (path === "/backtests/optimize" || path === "/backtests/validate") return response({ items: [], total: 0, limit: 20, offset: 0 });
    if (path === "/ml/signals/online-learning/status") return response({ generated_at: now, paper_sample_count: 0, closed_trade_sample_count: 0, positive_sample_count: 0, negative_sample_count: 0, ready_for_training: false, min_samples: 100, feature_names: [], sequence_feature_names: [], production_model_key: "smoke", latest_incremental_task_status: "idle", latest_incremental_task_progress_pct: 0, next_training_rule: "manual", warnings: [] });
    if (path === "/ml/signals/capacity") return response({ generated_at: now, capital_levels: [], items: [], assumptions: {} });
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
