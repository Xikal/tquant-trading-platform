export interface StrategyTrackingSummary {
  tracking_count: number;
  active_count: number;
  today_new_count: number;
  in_entry_zone_count: number;
  stopped_count: number;
  needs_review_count: number;
  abnormal_return_count: number;
  shadow_observation_count: number;
  avg_current_return_pct: number;
  median_max_gain_pct: number;
  data_quality: string;
  data_quality_text: string;
  generated_at: string;
}

export interface StrategyTrackingPerformance {
  strategy_key: string;
  strategy_name: string;
  strategy_family: string;
  recommendation_count: number;
  entry_touched_count: number;
  entry_touch_rate: number;
  win_rate_3d: number;
  win_rate_5d: number;
  win_rate_10d: number;
  avg_current_return_pct: number;
  avg_max_gain_pct: number;
  avg_max_drawdown_pct: number;
  profit_loss_ratio: number;
  stop_loss_rate: number;
  active_count: number;
  health_score: number;
  health_grade: string;
  sample_quality: string;
  health_reasons: string[];
  health_risks: string[];
}

export interface StrategyTrackingHoldingAnalysis {
  strategy_key: string;
  strategy_name: string;
  strategy_family: string;
  sample_count: number;
  avg_best_holding_days: number;
  median_best_holding_days: number;
  dominant_holding_bucket: string;
  dominant_holding_bucket_text: string;
  short_hold_ratio: number;
  swing_hold_ratio: number;
  trend_hold_ratio: number;
  midlong_hold_ratio: number;
  avg_best_exit_return_pct: number;
  avg_best_exit_drawdown_pct: number;
  avg_giveback_from_peak_pct: number;
  extension_qualified_ratio: number;
  conclusion: string;
}

export interface StrategyTrackingSegment {
  strategy_key: string;
  strategy_name: string;
  market_state: string;
  market_state_text: string;
  sector_state: string;
  sector_state_text: string;
  recommendation_count: number;
  entry_touch_rate: number;
  win_rate_5d: number;
  avg_max_gain_pct: number;
  avg_max_drawdown_pct: number;
  stop_loss_rate: number;
  return_drawdown_ratio: number;
}

export interface StrategyTrackingShadowObservation {
  model_key: string;
  model_version: string;
  observation_count: number;
  latest_observed_at: string | null;
  linked_tracking_count: number;
  no_sample_reason: string;
  no_sample_reason_text: string;
  actionable_count: number;
  settled_count: number;
  success_rate_pct: number;
}

export interface StrategyTrackingItem {
  id: string;
  symbol: string;
  name: string;
  strategy_key: string;
  strategy_name: string;
  strategy_family: string;
  signal_state: string;
  signal_text: string;
  observe_only: boolean;
  lifecycle_status: string;
  lifecycle_status_text: string;
  first_signal_date: string;
  latest_signal_date: string;
  first_signal_price: number | null;
  entry_zone_low: number | null;
  entry_zone_high: number | null;
  stop_loss: number | null;
  target_price: number | null;
  current_price: number | null;
  latest_trade_date: string;
  recommendation_days: number;
  distance_to_entry_pct: number | null;
  current_return_pct: number | null;
  max_price_after_signal: number | null;
  max_gain_pct: number | null;
  max_drawdown_pct: number | null;
  actual_low_price: number | null;
  actual_low_date: string | null;
  actual_high_date: string | null;
  spike_retrace_pct: number | null;
  best_holding_days: number;
  best_exit_date: string | null;
  best_exit_return_pct: number | null;
  best_exit_drawdown_pct: number | null;
  return_drawdown_ratio: number | null;
  giveback_from_peak_pct: number | null;
  holding_bucket: string;
  exit_quality: string;
  exit_reason: string;
  hold_extension_state: string;
  hold_extension_text: string;
  hold_extension_score: number;
  hold_extension_reasons: string[];
  hold_extension_risks: string[];
  suggested_holding_plan: string;
  entry_touched: boolean;
  stop_triggered: boolean;
  stop_triggered_date: string | null;
  target_touched: boolean;
  target_touched_date: string | null;
  invalidated_date: string | null;
  conclusion: string;
  failure_reason: string;
  failure_tags: string[];
  failure_reason_text: string;
  market_state: string;
  market_state_text: string;
  sector_state: string;
  sector_state_text: string;
  signal_generated_at: string;
  data_cutoff_at: string;
  lookback_start_date: string;
  lookback_end_date: string;
  posterior_start_date: string;
  posterior_end_date: string;
  market_data_source: string;
  market_data_updated_at: string;
  future_leak_check: string;
  audit_flags: string[];
  abnormal_return: boolean;
  needs_review: boolean;
  review_priority: string;
  review_text: string;
  data_quality: string;
  data_quality_text: string;
  source: string;
  detail_available: boolean;
  board_type: string;
  board_type_text: string;
  industry_sectors: string[];
  concept_sectors: string[];
  display_sectors: string[];
  user_friendly_status: string;
  user_friendly_status_text: string;
  user_friendly_reason: string;
  plain_language_summary: string;
  sector_detail: Record<string, unknown>;
}

export interface StrategyTrackingTimelinePoint {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  pct_chg: number;
  current_return_pct: number | null;
  max_return_pct: number | null;
  max_drawdown_pct: number | null;
  holding_day: number;
  is_best_exit: boolean;
  hold_extension_state: string;
  hit_entry_zone: boolean;
  hit_stop_loss: boolean;
  hit_target: boolean;
  lifecycle_status: string;
  data_quality: string;
}

export interface StrategyTrackingMarker {
  kind: string;
  trade_date: string;
  price: number | null;
  label: string;
}

export interface StrategyTrackingListResponse {
  items: StrategyTrackingItem[];
  total: number;
  limit: number;
  offset: number;
  sort: string;
  summary: StrategyTrackingSummary;
  performance: StrategyTrackingPerformance[];
  market_segments: StrategyTrackingSegment[];
  shadow_observations: StrategyTrackingShadowObservation[];
  partial_errors: string[];
  production_writeable: boolean;
  read_path: string;
  rust_math_used: boolean;
  notes: string[];
}

export interface StrategyTrackingSnapshotAudit {
  future_leak_check: string;
  checked_count: number;
  violation_count: number;
  abnormal_return_count: number;
  needs_review_count: number;
  audit_flags: string[];
}

export interface StrategyTrackingSnapshotPayload {
  summary: StrategyTrackingSummary;
  items: StrategyTrackingItem[];
  performance: StrategyTrackingPerformance[];
  market_segments: StrategyTrackingSegment[];
  holding_summary: StrategyTrackingHoldingAnalysisResponse;
  shadow_observations: StrategyTrackingShadowObservation[];
  audit: StrategyTrackingSnapshotAudit;
}

export interface StrategyTrackingSnapshotResponse {
  status: "fresh" | "stale" | "building" | "missing" | "failed" | string;
  stale: boolean;
  generated_at: string;
  source_data_cutoff: string;
  data_version: string;
  snapshot_key: string;
  as_of_date: string;
  payload: StrategyTrackingSnapshotPayload;
  total: number;
  limit: number;
  offset: number;
  sort: string;
  partial_errors: string[];
  production_writeable: boolean;
  read_path: string;
  notes: string[];
}

export interface StrategyTrackingDetailResponse {
  item: StrategyTrackingItem;
  timeline: StrategyTrackingTimelinePoint[];
  markers: StrategyTrackingMarker[];
  signal_snapshot: Record<string, unknown>;
  review_text: string;
  partial_errors: string[];
  production_writeable: boolean;
}

export interface StrategyTrackingReviewResponse {
  summary: StrategyTrackingSummary;
  performance: StrategyTrackingPerformance[];
  market_segments: StrategyTrackingSegment[];
  failure_tags: Record<string, number>;
  needs_review_items: StrategyTrackingItem[];
  abnormal_return_items: StrategyTrackingItem[];
}

export interface StrategyTrackingHoldingAnalysisResponse {
  items: StrategyTrackingHoldingAnalysis[];
  generated_at: string;
  data_quality: string;
  production_writeable: boolean;
}

export interface StrategyTrackingReport {
  report_type: string;
  generated_at: string;
  window_start: string;
  window_end: string;
  data_quality: string;
  summary: StrategyTrackingSummary;
  new_signals: StrategyTrackingItem[];
  entry_touched: StrategyTrackingItem[];
  stopped: StrategyTrackingItem[];
  spike_retraced: StrategyTrackingItem[];
  abnormal_returns: StrategyTrackingItem[];
  shadow_observations: StrategyTrackingShadowObservation[];
  markdown: string;
}

export interface StrategyTrackingParams {
  range?: number;
  status?: string;
  signal_state?: string;
  strategy_key?: string;
  strategy_family?: string;
  data_quality?: string;
  hit_entry?: boolean | null;
  stopped?: boolean | null;
  exclude_chinext?: boolean;
  exclude_star?: boolean;
  board_filter?: string;
  user_status?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}
