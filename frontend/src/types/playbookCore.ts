export interface LowBuyExitPlan {
  stop_loss: number;
  first_take_profit: number;
  trailing_stop: number;
  max_holding_days: number;
  time_stop_text: string;
  invalid_condition: string;
  exit_rules: string[];
}

export interface LowBuyHardRisk {
  level: "clear" | "note" | "degrade" | "block";
  score_penalty: number;
  execution_blocked: boolean;
  reasons: string[];
  tags: string[];
}

export interface LowBuyNextDayEventPlan {
  state: "none" | "watch" | "near_entry" | "weak_to_strong_candidate" | "take_profit_watch" | "failed_confirmation";
  state_text: string;
  next_day_action: string;
  t2_action: string;
  first_take_profit_pct: number;
  second_take_profit_pct: number;
  max_holding_days: number;
  position_pct: number;
  confirmation_rules: string[];
  exit_rules: string[];
  risk_notes: string[];
}

export interface LowBuyPortfolioRisk {
  total_planned_position_pct: number;
  holding_position_pct?: number;
  max_single_position_pct: number;
  active_signal_count: number;
  holding_signal_count?: number;
  industry_concentration_pct: number;
  top_industry: string;
  recommended_total_cap_pct: number;
  risk_level: "clear" | "note" | "degrade" | "block";
  notes: string[];
}

export interface LowBuyExecutionBacktestItem {
  symbol: string;
  name: string;
  strategy_key: string;
  signal_trade_date: string;
  entry_trade_date?: string | null;
  exit_trade_date?: string | null;
  status: "filled" | "not_filled" | "invalid";
  entry_price: number;
  exit_price: number;
  net_return_pct: number;
  max_gain_pct: number;
  max_drawdown_pct: number;
  exit_reason: string;
  data_quality?: string;
  data_quality_text?: string;
  data_quality_tags?: string[];
}

export interface LowBuyExecutionBacktestResult {
  strategy_key: string;
  lookback_days: number;
  evaluated_signals: number;
  filled_signals: number;
  not_filled_signals?: number;
  invalid_signals?: number;
  win_rate: number;
  net_win_rate?: number;
  not_filled_rate?: number;
  stop_loss_count?: number;
  stop_loss_rate?: number;
  take_profit_count?: number;
  take_profit_rate?: number;
  time_exit_count?: number;
  time_exit_rate?: number;
  avg_net_return_pct: number;
  avg_max_gain_pct: number;
  avg_max_drawdown_pct: number;
  max_adverse_pct?: number;
  avg_loss_pct?: number;
  win_loss_ratio?: number;
  profit_factor: number;
  data_quality?: string;
  data_quality_text?: string;
  data_quality_tags?: string[];
  pbo?: {
    pbo?: number;
    real_sharpe?: number;
    pseudo_sharpe_mean?: number;
    pseudo_sharpe_95pct?: number;
    n_permutations?: number;
    verdict?: string;
  } | null;
  crisis_scenario?: {
    scenario?: string;
    crisis_count?: number;
    crisis_ratio_pct?: number;
    crisis_extra_loss_pct?: number;
    original_avg_return?: number;
    crisis_avg_return?: number;
    impact_pct?: number;
  } | null;
  notes: string[];
  items: LowBuyExecutionBacktestItem[];
}

export interface LowBuyTradeLifecycle {
  symbol: string;
  name: string;
  strategy_key: string;
  signal_trade_date: string;
  status: "planned" | "entered" | "holding" | "exited" | "invalid";
  signal_state: "buy_now" | "soft_buy_now" | "observe_confirmed" | "near_entry" | "watch" | "avoid";
  entry_plan_low: number;
  entry_plan_high: number;
  stop_loss: number;
  take_profit: number;
  max_holding_days: number;
  entry_price?: number | null;
  entry_trade_date?: string | null;
  exit_price?: number | null;
  exit_trade_date?: string | null;
  exit_reason: string;
  realized_return_pct: number;
  max_gain_pct: number;
  max_drawdown_pct: number;
  attribution_note: string;
  updated_at: string;
}

export interface LowBuyCandidate {
  strategy_key: string;
  strategy_title: string;
  symbol: string;
  name: string;
  market: string;
  instrument_type: string;
  sector_name?: string | null;
  latest_price: number;
  change_pct: number;
  quote_timestamp: string;
  data_quality?: string;
  data_quality_text?: string;
  data_quality_tags?: string[];
  data_source?: string | null;
  source_quality?: string | null;
  is_stale?: boolean;
  board_date: string;
  board_count: number;
  retracement_days: number;
  score: number;
  entry_zone_low: number;
  entry_zone_high: number;
  stop_loss: number;
  take_profit: number;
  ma5: number;
  ma10: number;
  ma20: number;
  volume_burst_ratio: number;
  volume_shrink_ratio: number;
  support_distance_pct: number;
  distribution_risk_score: number;
  trend_fatigue_score?: number;
  false_breakout_flag: boolean;
  stall_after_volume_flag: boolean;
  intraday_reversal_flag: boolean;
  execution_ready: boolean;
  execution_note: string;
  stage_scores?: Record<string, number>;
  factor_scores?: Record<string, number>;
  stage_text?: string;
  risk_tier?: "block" | "degrade" | "note";
  trigger_condition?: string;
  invalid_condition?: string;
  next_watch_price?: number | null;
  leader_rank?: string;
  mainline_rank?: number;
  mainline_tier?: string;
  mainline_tier_text?: string;
  execution_quality_score?: number;
  execution_quality_text?: string;
  dynamic_threshold_adjustment?: number;
  dynamic_position_multiplier?: number;
  industry_tier?: string;
  industry_tier_text?: string;
  industry_position_multiplier?: number;
  position_breakdown_text?: string;
  atr_pct?: number;
  volatility_position_pct?: number;
  final_position_cap_pct?: number;
  position_cap_reason?: string;
  hard_risk?: LowBuyHardRisk;
  next_day_event_plan?: LowBuyNextDayEventPlan;
  exit_plan?: LowBuyExitPlan;
  entry_distance_pct: number;
  suggested_position_pct: number;
  suggested_position_text: string;
  market_state: string;
  market_state_text: string;
  market_state_category?: string;
  market_state_category_text?: string;
  market_state_strength: number;
  market_position_multiplier: number;
  confirmed_trade_date?: string | null;
  summary_reason: string;
  buy_signal_state: "buy_now" | "soft_buy_now" | "observe_confirmed" | "near_entry" | "watch" | "avoid";
  buy_signal_text: string;
  buy_signal_hint: string;
  recommendation_start_date?: string | null;
  recommendation_days?: number;
  strategy_recommendation_days?: Record<string, number>;
  recommendation_duration_text?: string;
  reasons: string[];
  risks: string[];
  tags: string[];
}
