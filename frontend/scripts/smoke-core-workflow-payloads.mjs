import {
  mockLowBuy,
  mockLowBuyCandidate,
  mockStrategyMeta,
  mockUser,
  now,
} from "./smoke-responsive-fixtures.mjs";

export function authRefreshPayload() {
  return {
    access_token: "smoke-token",
    refresh_token: "smoke-refresh",
    token_type: "bearer",
    expires_in: 3600,
    user: mockUser,
  };
}

export function tradingReadinessPayload() {
  return {
    flags: {
      trading_experience_suite_enabled: false,
      vp_position_tags_enabled: false,
    },
    ready: false,
    generated_at: now,
  };
}

export function monitorWorkspacePayload(staleScenario) {
  return {
    api_version: "v1",
    schema_version: "smoke",
    generated_at: now,
    stale: staleScenario,
    refresh_queued: false,
    monitor_snapshot: monitorSnapshotPayload(staleScenario),
    market_breadth: marketBreadthPayload(staleScenario),
    market_pulse: {
      data_quality: staleScenario ? "stale" : "fresh",
      data_quality_text: staleScenario ? "偏旧" : "fresh",
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

export function monitorSnapshotPayload(staleScenario) {
  return {
    updated_at: now,
    generated_at: now,
    priority_board: priorityBoardPayload(staleScenario),
    watchlist_signals: [],
    sector_etf_t0: { items: [], opportunities: [] },
  };
}

export function priorityBoardPayload(staleScenario) {
  return {
    strategy_variant: "baseline",
    display_lane: "baseline",
    display_lane_title: "生产优先榜",
    display_lane_subtitle: "旧前端核心链路 smoke",
    as_of_date: "2026-05-26",
    latest_trade_date: staleScenario ? "2026-05-20" : "2026-05-26",
    latest_available_trade_date: "2026-05-26",
    snapshot_warning: staleScenario ? "当前榜单停留在 2026-05-20，距最新交易日 2026-05-26 已落后，仅供复盘。" : "",
    updated_at: now,
    stale: staleScenario,
    stale_reason: staleScenario ? "当前榜单停留在 2026-05-20，距最新交易日 2026-05-26 已落后，仅供复盘，不作为今日观察依据。" : "",
    refresh_queued: false,
    read_path: "smoke",
    total_candidates: 1,
    immediate_count: 0,
    focus_count: 1,
    track_count: 0,
    market_state: "repair",
    market_state_text: "震荡修复",
    market_state_category: "neutral",
    market_state_category_text: "中性偏暖",
    data_quality: staleScenario ? "stale" : "ok",
    data_quality_text: staleScenario ? "偏旧" : "可用",
    market_gate_decision: staleScenario ? "reduce" : "allow",
    market_gate_score: 72,
    market_gate_reasons: [],
    market_firepower_multiplier: staleScenario ? 0.5 : 1,
    directional_bias: "positive_t",
    directional_bias_text: "正T",
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
    items: [priorityBoardItem(staleScenario)],
  };
}

export function lowBuyPayload(staleScenario) {
  if (!staleScenario) return mockLowBuy;
  return {
    ...mockLowBuy,
    latest_trade_date: "2026-05-20",
    as_of_date: "2026-05-26",
    stale: true,
    stale_reason: "当前选股宝典停留在 2026-05-20，距最新交易日 2026-05-26 已落后，仅供复盘。",
    data_quality: "stale",
    data_quality_text: "偏旧",
  };
}

export function marketBreadthPayload(staleScenario) {
  return {
    updated_at: now,
    data_quality: staleScenario ? "stale" : "fresh",
    data_quality_text: staleScenario ? "偏旧" : "fresh",
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
      data_quality_text: staleScenario ? "偏旧" : "fresh",
      updated_at: now,
    },
  };
}

export function quoteRefreshPayload() {
  return {
    items: {
      "510300": {
        latest_price: 3.45,
        change_pct: 0.6,
        quote_timestamp: now,
        in_entry_zone: true,
        distance_to_entry_pct: -0.2,
        stop_confirmed: false,
        buy_signal_state: "near_entry",
        buy_signal_text: "接近买点（观察类·未到买入）",
        buy_signal_hint: "等待承接确认，不是买入建议",
      },
    },
  };
}

export function lowBuyStrategiesPayload() {
  return {
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
  };
}

export function backtestRunsPayload() {
  return {
    items: [{
      id: 1,
      name: "核心链路 smoke 回测",
      strategies: ["first_board"],
      status: "completed",
      start_date: "2026-01-01",
      end_date: "2026-05-26",
      created_at: now,
      updated_at: now,
      metrics: { total_return_pct: 3.2, max_drawdown_pct: -1.1, win_rate_pct: 58, total_trades: 8 },
    }],
    total: 1,
    limit: 20,
    offset: 0,
  };
}

export function settingsWorkspacePayload() {
  return {
    api_version: "v1",
    schema_version: "smoke",
    generated_at: now,
    settings: settingsPayload(),
    sector_exclusions: sectorExclusionsPayload(),
    strategy_governance: lowBuyStrategiesPayload(),
    runtime: runtimePayload(),
    factor_weights: { weights: {}, defaults: {}, factors: [] },
    admin_tasks: { items: [] },
    admin_metrics: {},
    admin_enabled: true,
    partial_errors: [],
  };
}

export function runtimePayload() {
  return {
    app_name: "TQuant",
    api_prefix: "/api",
    database_backend: "sqlite",
    database_url_masked: "sqlite:///smoke.db",
    runtime_database_url_masked: "sqlite:///smoke.db",
    runtime_env_path: ".runtime",
    runtime_env_exists: true,
    runtime_database_override: false,
    runtime_database_matches_settings: true,
    runtime_llm_secret_persisted: true,
    settings_consistency_status: "ok",
    settings_consistency_text: "配置一致",
    frontend_dist_path: "dist",
    frontend_dist_ready: true,
    llm_configured: true,
    data_source: "local",
    data_source_base_url: "",
    cors_origins: [],
    ready_checks: { database: true, frontend_dist: true },
  };
}

export function sectorExclusionsPayload() {
  return { available_sectors: ["机器人", "半导体"], excluded_sectors: [], excluded_count: 0, updated_at: now };
}

export function tradingSessionPayload() {
  return {
    updated_at: now,
    is_trading_day: true,
    is_trading_now: true,
    current_time: now,
    timezone: "Asia/Shanghai",
    data_quality_text: "fresh",
  };
}

export function quantParametersPayload() {
  return {
    id: 1,
    version: "smoke",
    name: "Smoke",
    scope: "global",
    status: "active",
    params: {},
    description: "smoke",
    created_by: "smoke",
    created_at: now,
    activated_at: now,
  };
}

export function quotePayload() {
  return {
    symbol: "510300",
    name: "沪深300ETF",
    market: "SH",
    instrument_type: "etf",
    last_price: 3.45,
    change_pct: 0.6,
    change_amount: 0.02,
    open_price: 3.43,
    high_price: 3.48,
    low_price: 3.41,
    prev_close: 3.43,
    volume: 1200000,
    amount: 4140000,
    timestamp: now,
    data_source: "smoke",
    source_quality: "ok",
    is_stale: false,
  };
}

export function klinePayload() {
  return { symbol: "510300", period: "5m", bars: [{ timestamp: now, open: 3.42, close: 3.45, high: 3.48, low: 3.41, volume: 1000, amount: 3450 }] };
}

export function instrumentRulesPayload() {
  return {
    symbol: "510300",
    turnaround_mode: "t0",
    supports_positive_t: true,
    supports_negative_t: true,
    same_day_sell_allowed: true,
    requires_base_position: true,
    notes: "ETF T+0",
  };
}

export function emptyPagedList() {
  return { items: [], total: 0, limit: 20, offset: 0 };
}

function priorityBoardItem(staleScenario) {
  return {
    ...mockLowBuyCandidate,
    strategy_titles: ["首板低吸"],
    strategy_count: 1,
    family_count: 1,
    strategy_family: "core",
    strategy_family_text: "核心策略",
    data_quality: staleScenario ? "stale" : "fresh",
    data_quality_text: staleScenario ? "偏旧" : "fresh",
    priority_score: 82,
    production_score: 71.2,
    strategy_weight_score: 70,
    industry_rotation_bonus: 5,
    industry_rotation_text: "主线轮动",
    action_summary: staleScenario ? "过期快照仅复盘，不作为今日交易依据" : "回踩承接确认，继续观察买点",
    blocked_reason: "",
    risk_tier: "note",
    next_action_text: staleScenario ? "仅供复盘" : "等待承接确认",
    display_lane: "baseline",
  };
}

function settingsPayload() {
  return {
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
  };
}
