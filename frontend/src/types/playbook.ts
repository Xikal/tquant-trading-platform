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
  signal_state: "buy_now" | "soft_buy_now" | "near_entry" | "watch" | "avoid";
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
  buy_signal_state: "buy_now" | "soft_buy_now" | "near_entry" | "watch" | "avoid";
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

export interface LowBuyHistorySection {
  title: string;
  description: string;
  candidates: LowBuyCandidate[];
}

export interface LowBuyHistoryResult {
  as_of_date: string;
  latest_trade_date: string;
  history_sections: LowBuyHistorySection[];
}

export interface LowBuyPerformanceBucket {
  label: string;
  sample_count: number;
  hit_count: number;
  hit_rate: number;
  avg_return_3d: number;
  avg_return_5d: number;
}

export interface LowBuyStrategyPerformance {
  lookback_days: number;
  signal_count: number;
  evaluated_signals: number;
  filled_signals?: number;
  not_filled_signals?: number;
  pending_signals: number;
  hit_count: number;
  hit_rate: number;
  net_win_rate?: number;
  not_filled_rate?: number;
  stop_loss_rate?: number;
  avg_net_return_pct?: number;
  avg_win_pct?: number;
  avg_loss_pct?: number;
  profit_factor?: number;
  cvar_5pct?: number;
  kelly_half_position_pct?: number;
  win_rate_1d: number;
  win_rate_3d: number;
  win_rate_5d: number;
  avg_return_1d: number;
  avg_return_3d: number;
  avg_return_5d: number;
  avg_max_gain_5d: number;
  avg_max_drawdown_5d: number;
  target_profit_pct: number;
  updated_at: string;
  attribution_notes: string[];
  sector_attribution: LowBuyPerformanceBucket[];
  retracement_attribution: LowBuyPerformanceBucket[];
  market_state_attribution: LowBuyPerformanceBucket[];
  industry_tier_attribution: LowBuyPerformanceBucket[];
}

export interface LowBuyCloseReviewItem {
  symbol: string;
  name: string;
  signal_state: "buy_now" | "soft_buy_now" | "near_entry" | "watch" | "avoid";
  signal_text: string;
  review_trade_date: string;
  close_price: number;
  change_pct: number;
  amplitude_pct: number;
  entry_zone_low: number;
  entry_zone_high: number;
  stop_loss: number;
  entry_distance_pct: number;
  entry_distance_text: string;
  close_vs_stop_pct: number;
  review_level: "good" | "neutral" | "risk";
  review_text: string;
}

export interface LowBuyScreenerResult {
  strategy_key: string;
  strategy_title: string;
  strategy_subtitle: string;
  strategy_logic: string;
  requested_mode: "quick" | "full";
  response_mode: "quick" | "full";
  as_of_date: string;
  latest_trade_date: string;
  pool_size: number;
  scanned_count: number;
  matched_count: number;
  requested_scan_limit: number;
  active_scan_limit: number;
  full_scan_ready: boolean;
  full_scan_in_progress: boolean;
  full_scan_updated_at?: string | null;
  market_state: string;
  market_state_text: string;
  market_state_category?: string;
  market_state_category_text?: string;
  data_quality?: string;
  data_quality_text?: string;
  data_quality_tags?: string[];
  market_bonus: number;
  market_state_strength: number;
  regime_confidence: number;
  state_persistence_days: number;
  transition_risk: number;
  breadth_ready: boolean;
  emotion_ready: boolean;
  stock_up_ratio: number;
  stock_median_change: number;
  style_divergence: number;
  hot_turnover: number;
  hot_overlap_ratio: number;
  limit_down_count?: number | null;
  limit_up_count: number;
  board_height: number;
  previous_board_height: number;
  promotion_ratio: number;
  broken_board_ratio: number;
  promotion_break_gap: number;
  promotion_break_pressure: number;
  high_flyer_retreat_ratio: number;
  high_flyer_gap_speed: number;
  distribution_pressure: number;
  hot_industries: string[];
  hot_industry_source: string;
  hot_industry_source_text: string;
  mainline_lifecycle_state?: string;
  mainline_lifecycle_text?: string;
  portfolio_risk?: LowBuyPortfolioRisk;
  retracement_distribution: Record<string, number>;
  filters: Record<string, string | number | boolean>;
  strategy_notes: string[];
  performance?: LowBuyStrategyPerformance | null;
  close_review_trade_date?: string | null;
  close_review_updated_at?: string | null;
  close_review_items: LowBuyCloseReviewItem[];
  confirmed_candidates: LowBuyCandidate[];
  history_sections: LowBuyHistorySection[];
  candidates: LowBuyCandidate[];
}

export interface LowBuyQuoteRefreshItem {
  latest_price: number;
  change_pct: number;
  quote_timestamp: string;
  data_source?: string | null;
  source_quality?: string | null;
  is_stale?: boolean;
  data_quality?: string;
  data_quality_text?: string;
  data_quality_tags?: string[];
  in_entry_zone: boolean;
  distance_to_entry_pct: number;
  stop_confirmed: boolean;
  suggested_position_pct: number;
  suggested_position_text: string;
  position_breakdown_text?: string;
  execution_quality_score?: number;
  execution_quality_text?: string;
  buy_signal_state: "buy_now" | "soft_buy_now" | "near_entry" | "watch" | "avoid";
  buy_signal_text: string;
  buy_signal_hint: string;
  trigger_condition?: string;
  invalid_condition?: string;
  risk_tier?: "block" | "degrade" | "note";
  next_watch_price?: number | null;
}

export interface LowBuyPriorityBoardItem {
  symbol: string;
  name: string;
  sector_name?: string | null;
  strategy_key: string;
  strategy_title: string;
  strategy_titles: string[];
  strategy_count: number;
  family_count?: number;
  strategy_family?: string;
  strategy_family_text?: string;
  latest_price: number;
  change_pct: number;
  quote_timestamp: string;
  data_quality?: string;
  data_quality_text?: string;
  data_quality_tags?: string[];
  market_state_category?: string;
  market_state_category_text?: string;
  buy_signal_state: "buy_now" | "soft_buy_now" | "near_entry" | "watch" | "avoid";
  buy_signal_text: string;
  priority_score: number;
  strategy_weight_score: number;
  industry_rotation_bonus: number;
  industry_rotation_text: string;
  industry_tier?: string;
  industry_tier_text?: string;
  industry_position_multiplier?: number;
  position_breakdown_text?: string;
  action_summary: string;
  blocked_reason: string;
  trigger_condition?: string;
  invalid_condition?: string;
  risk_tier?: "block" | "degrade" | "note";
  next_watch_price?: number | null;
  leader_rank?: string;
  mainline_rank?: number;
  mainline_tier?: string;
  mainline_tier_text?: string;
  execution_quality_score?: number;
  execution_quality_text?: string;
  strategy_performance_text?: string;
  next_day_event_plan?: LowBuyNextDayEventPlan;
  entry_zone_low: number;
  entry_zone_high: number;
  stop_loss: number;
  suggested_position_pct: number;
  suggested_position_text: string;
  recommendation_start_date?: string | null;
  recommendation_days?: number;
  strategy_recommendation_days?: Record<string, number>;
  recommendation_duration_text?: string;
  simple_bucket?: "buy_now" | "wait_price" | "give_up";
  simple_bucket_text?: string;
  next_action_text?: string;
  exit_plan_text?: string;
}

export interface LowBuyDailyDecision {
  key: "tradable" | "observe_only" | "wait";
  title: string;
  message: string;
  market_plain_text: string;
  risk_level: "low" | "medium" | "high";
  action_steps: string[];
}

export interface LowBuySimpleBucket {
  key: "buy_now" | "wait_price" | "give_up";
  title: string;
  description: string;
  count: number;
  symbols: string[];
}

export interface LowBuyPriorityFamilyPerformance {
  family_key: string;
  family_text: string;
  strategy_count: number;
  evaluated_signals: number;
  filled_signals: number;
  not_filled_signals: number;
  hit_count: number;
  net_win_rate: number;
  avg_net_return_pct: number;
  not_filled_rate: number;
  stop_loss_rate: number;
  hit_rate: number;
}

export interface LowBuyPriorityFamilySection {
  family_key: string;
  family_text: string;
  total_candidates: number;
  immediate_count: number;
  focus_count: number;
  track_count: number;
  avg_priority_score: number;
  top_strategy_titles: string[];
  performance?: LowBuyPriorityFamilyPerformance | null;
  items: LowBuyPriorityBoardItem[];
}

export interface LowBuyPriorityBoardResult {
  as_of_date: string;
  latest_trade_date: string;
  latest_available_trade_date?: string;
  snapshot_warning?: string;
  updated_at: string;
  total_candidates: number;
  immediate_count: number;
  focus_count: number;
  track_count: number;
  market_state: string;
  market_state_text: string;
  market_state_category?: string;
  market_state_category_text?: string;
  data_quality?: string;
  data_quality_text?: string;
  data_quality_tags?: string[];
  directional_bias?: "positive_t" | "negative_t" | "neutral";
  directional_bias_text?: string;
  market_bonus: number;
  market_state_strength: number;
  regime_confidence: number;
  state_persistence_days: number;
  transition_risk: number;
  breadth_ready: boolean;
  emotion_ready: boolean;
  stock_up_ratio: number;
  stock_median_change: number;
  style_divergence: number;
  hot_turnover: number;
  hot_overlap_ratio: number;
  limit_down_count?: number | null;
  limit_up_count: number;
  board_height: number;
  previous_board_height: number;
  promotion_ratio: number;
  broken_board_ratio: number;
  promotion_break_gap: number;
  promotion_break_pressure: number;
  high_flyer_retreat_ratio: number;
  high_flyer_gap_speed: number;
  distribution_pressure: number;
  hot_industries: string[];
  hot_industry_source: string;
  hot_industry_source_text: string;
  mainline_lifecycle_state?: string;
  mainline_lifecycle_text?: string;
  portfolio_risk?: LowBuyPortfolioRisk;
  missing_strategies?: string[];
  stale_strategies?: string[];
  family_sections?: LowBuyPriorityFamilySection[];
  daily_decision?: LowBuyDailyDecision;
  simple_buckets?: LowBuySimpleBucket[];
  items: LowBuyPriorityBoardItem[];
}
