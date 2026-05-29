export interface StrategyTrackingSummary {
  tracking_count: number;
  active_count: number;
  today_new_count: number;
  in_entry_zone_count: number;
  stopped_count: number;
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
  entry_touched: boolean;
  stop_triggered: boolean;
  stop_triggered_date: string | null;
  target_touched: boolean;
  target_touched_date: string | null;
  conclusion: string;
  failure_reason: string;
  review_text: string;
  data_quality: string;
  data_quality_text: string;
  source: string;
  detail_available: boolean;
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
  partial_errors: string[];
  production_writeable: boolean;
  read_path: string;
  rust_math_used: boolean;
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

export interface StrategyTrackingParams {
  range?: number;
  status?: string;
  signal_state?: string;
  strategy_key?: string;
  strategy_family?: string;
  data_quality?: string;
  hit_entry?: boolean | null;
  stopped?: boolean | null;
  sort?: string;
  limit?: number;
  offset?: number;
}
