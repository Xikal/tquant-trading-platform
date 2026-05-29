import type { LowBuyCandidate, LowBuyNextDayEventPlan, LowBuyPortfolioRisk, MainForceAdvice } from "./playbookCore";

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
  win_rate_2d?: number;
  win_rate_3d: number;
  win_rate_4d?: number;
  win_rate_5d: number;
  avg_return_1d: number;
  avg_return_2d?: number;
  avg_return_3d: number;
  avg_return_4d?: number;
  avg_return_5d: number;
  avg_max_gain_5d: number;
  avg_max_drawdown_5d: number;
  target_profit_pct: number;
  updated_at: string;
  data_insufficient?: boolean;
  attribution_notes: string[];
  sector_attribution: LowBuyPerformanceBucket[];
  retracement_attribution: LowBuyPerformanceBucket[];
  market_state_attribution: LowBuyPerformanceBucket[];
  industry_tier_attribution: LowBuyPerformanceBucket[];
}

export interface LowBuyCloseReviewItem {
  symbol: string;
  name: string;
  signal_state: "buy_now" | "soft_buy_now" | "observe_confirmed" | "near_entry" | "watch" | "avoid";
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
  buy_signal_state: "buy_now" | "soft_buy_now" | "observe_confirmed" | "near_entry" | "watch" | "avoid";
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
  buy_signal_state: "buy_now" | "soft_buy_now" | "observe_confirmed" | "near_entry" | "watch" | "avoid";
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
  leader_strength_score?: number;
  leader_strength_rank?: number;
  leader_strength_text?: string;
  mainline_rank?: number;
  mainline_tier?: string;
  mainline_tier_text?: string;
  execution_quality_score?: number;
  execution_quality_text?: string;
  strategy_performance_text?: string;
  kelly_half_position_pct?: number;
  kelly_position_text?: string;
  atr_pct?: number;
  volatility_position_pct?: number;
  final_position_cap_pct?: number;
  position_cap_reason?: string;
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
  multi_timeframe_resonance_score?: number;
  multi_timeframe_resonance_text?: string;
  simple_bucket?: "buy_now" | "wait_price" | "give_up";
  simple_bucket_text?: string;
  next_action_text?: string;
  exit_plan_text?: string;
  main_force_advice?: MainForceAdvice;
  main_force_rank_bonus?: number;
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
  data_quality?: string;
  data_quality_text?: string;
  data_quality_tags?: string[];
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
