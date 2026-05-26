export type ActionType = "positive_t" | "negative_t" | "hold";
export type RiskLevel = "low" | "medium" | "high";

export interface Instrument {
  symbol: string;
  name: string;
  market: string;
  instrument_type: string;
  sector_name?: string | null;
}

export interface InstrumentSyncStatus {
  run_id: string;
  kind: string;
  status: "idle" | "queued" | "running" | "succeeded" | "failed" | string;
  progress_pct: number;
  message: string;
  result: Record<string, number>;
  error?: string;
  task_id?: number | null;
  updated_at: string;
}

export interface InstrumentSyncStartResponse {
  message: string;
  run_id: string;
  task_id?: number | null;
  status: InstrumentSyncStatus;
}

export interface QuoteSnapshot {
  symbol: string;
  name: string;
  market: string;
  instrument_type: string;
  last_price: number;
  change_pct: number;
  change_amount: number;
  open_price: number;
  high_price: number;
  low_price: number;
  prev_close: number;
  volume: number;
  amount: number;
  turnover_rate?: number | null;
  volume_ratio?: number | null;
  timestamp: string;
  data_source?: string | null;
  source_quality?: string | null;
  is_stale?: boolean;
}

export interface KlineBar {
  timestamp: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  amount: number;
  amplitude?: number | null;
  change_pct?: number | null;
  turnover?: number | null;
}

export interface TradingRule {
  symbol: string;
  turnaround_mode: "t0" | "t1";
  supports_positive_t: boolean;
  supports_negative_t: boolean;
  same_day_sell_allowed: boolean;
  requires_base_position: boolean;
  notes: string;
}

export interface SectorSnapshot {
  sector_name: string;
  sector_strength: number;
  market_strength: number;
  alignment_score: number;
  notes: string;
}

export interface MarketEvent {
  title: string;
  risk_level: RiskLevel;
  description: string;
  source: string;
  event_time: string;
}

export interface MicrostructureSnapshot {
  available: boolean;
  buy_pressure: number;
  sell_pressure: number;
  large_order_flow: number;
  notes: string;
}

export interface MarketBreadth {
  updated_at: string;
  state: string;
  state_text: string;
  emotion_temperature?: string;
  emotion_temperature_text?: string;
  emotion_temperature_score?: number;
  breadth_ready: boolean;
  emotion_ready: boolean;
  stock_up_ratio: number;
  stock_median_change: number;
  largecap_change: number;
  smallcap_change: number;
  style_divergence: number;
  limit_up_count: number;
  limit_down_count?: number | null;
  broken_board_ratio: number;
  promotion_ratio: number;
  board_height: number;
  hot_industries: string[];
  hot_turnover: number;
  hot_overlap_ratio: number;
  data_quality?: string;
  data_quality_text: string;
  autofill_details?: Array<{ source: string; method?: string; detail: string; filled_at?: string; [key: string]: unknown }>;
  hourly_all_market_snapshot?: {
    ok?: boolean;
    reason?: string;
    updated_at?: string;
    snapshot_count?: number;
    stock_up_ratio?: number;
    stock_down_ratio?: number;
    stock_flat_count?: number;
    stock_median_change?: number;
    strong_count?: number;
    weak_count?: number;
    market_strength_score?: number;
    market_strength_text?: string;
    source?: string;
    data_quality_text?: string;
  };
}

export interface MarketHourlySnapshotHistoryItem {
  id: number;
  trade_date: string;
  snapshot_bucket: string;
  data_quality: "fresh" | "stale" | "partial" | "unavailable" | string;
  snapshot_count: number;
  market_strength_score: number;
  payload: {
    updated_at?: string;
    market_strength_text?: string;
    stock_up_ratio?: number;
    stock_down_ratio?: number;
    stock_median_change?: number;
    strong_count?: number;
    weak_count?: number;
    data_quality_text?: string;
    [key: string]: unknown;
  };
  created_at: string;
  updated_at: string;
}

export interface MarketHourlySnapshotHistoryResponse {
  items: MarketHourlySnapshotHistoryItem[];
  total: number;
}

export interface IntradayMarketPulse {
  updated_at: string;
  data_quality: "fresh" | "stale" | "partial" | "unavailable" | string;
  data_quality_text: string;
  market_strength_text: string;
  leader_strength_text: string;
  emotion_text: string;
  hourly_snapshot_text: string;
  pulse_level: string;
  pulse_text: string;
  suggested_action: string;
  partial_errors: Array<{ source: string; detail: string }>;
  market_breadth_summary: Record<string, unknown>;
  leader_strength_summary: Record<string, unknown>;
  emotion_summary: Record<string, unknown>;
  hourly_snapshot_summary: Record<string, unknown>;
  autofill_details?: Array<{ source: string; method?: string; detail: string; filled_at?: string; [key: string]: unknown }>;
}

export interface MarketReviewReport {
  id: number;
  report_date: string;
  report_slot?: "midday" | "close" | string;
  review_subject?: string;
  source_scope?: "market" | string;
  overall_summary: string;
  strategy_highlights: Array<{
    strategy: string;
    comment: string;
    trend: "improving" | "stable" | "declining" | "new" | string;
  }>;
  risk_alerts: Array<{
    level: "info" | "warning" | "danger" | string;
    content: string;
  }>;
  suggestion: string;
  generated_at: string;
  llm_model: string;
  missing_data?: Array<{ source: string; name?: string; detail?: string; [key: string]: unknown }>;
  autofill_details?: Array<{ source: string; method?: string; detail: string; filled_at?: string; [key: string]: unknown }>;
}

export interface MarketReviewStatus {
  trade_date: string;
  status: string;
  status_text: string;
  review_subject?: string;
  source_scope?: "market" | string;
  has_midday: boolean;
  has_close: boolean;
  next_trigger_at: string;
  risk_alert_count: number;
  suggested_action: string;
}

export interface MarketTradingSession {
  updated_at: string;
  is_trading_day: boolean;
  is_trading_now: boolean;
  current_time: string;
  timezone: string;
  data_quality_text: string;
}

export interface SectorRelativeStrengthItem {
  sector_name: string;
  symbol: string;
  name: string;
  latest_price: number;
  change_pct: number;
  sector_median_change_pct: number;
  relative_strength_ratio?: number | null;
  volume_ratio: number;
  turnover_proxy: number;
  leader_score: number;
  rank: number;
  data_quality_text?: string;
}

export interface SectorRelativeStrengthResponse {
  updated_at: string;
  trade_date: string;
  sector_count: number;
  items: SectorRelativeStrengthItem[];
  notes: string[];
}

export interface IntradayKeyLevelItem {
  level_type: string;
  level_text: string;
  price: number;
  distance_pct: number;
  alert: boolean;
}

export interface IntradayKeyLevelResponse {
  symbol: string;
  name: string;
  updated_at: string;
  latest_price: number;
  vwap: number;
  entry_zone_low?: number | null;
  entry_zone_high?: number | null;
  alert_threshold_pct: number;
  alert_triggered: boolean;
  alert_text: string;
  levels: IntradayKeyLevelItem[];
  data_quality_text?: string;
}

export interface SectorEtfT0Opportunity {
  sector_name: string;
  etf_symbol: string;
  etf_name: string;
  source_signal_symbol: string;
  source_signal_name: string;
  source_signal_state?: string;
  source_strategy: string;
  source_signal_text: string;
  last_price: number;
  change_pct: number;
  bias: "positive_t" | "negative_t" | "hold" | string;
  bias_text: string;
  confidence: number;
  entry_zone: string;
  sell_zone: string;
  stop_loss?: number | null;
  expected_edge_pct: number;
  reason: string;
  risk: string;
  data_quality_text?: string;
}

export interface SectorEtfT0Response {
  updated_at: string;
  market_state: string;
  market_state_text: string;
  total: number;
  opportunities: SectorEtfT0Opportunity[];
  notes: string[];
}

export interface IntradayAnomalyResponse {
  symbol: string;
  name: string;
  anomaly_level: "normal" | "watch" | "medium" | "high" | "data_unavailable" | string;
  anomaly_text: string;
  score: number;
  pattern: string;
  action_hint: string;
  reasons: string[];
  risk_notes: string[];
  data_quality_text?: string;
  updated_at: string;
}

export interface PairedHedgeLeg {
  role: string;
  symbol: string;
  name: string;
  side: string;
  notional_ratio: number;
  latest_price: number;
  change_pct: number;
  reason: string;
}

export interface PairedHedgeIdea {
  source_signal_symbol: string;
  source_signal_name: string;
  source_strategy: string;
  sector_name: string;
  confidence: number;
  hedge_ratio: number;
  gross_exposure_pct: number;
  net_exposure_pct: number;
  estimated_beta: number;
  hedge_cost_pct: number;
  tracking_error_pct: number;
  legs: PairedHedgeLeg[];
  risk_notes: string[];
}

export interface PairedHedgeResearchResponse {
  updated_at: string;
  mode: "research_only" | string;
  total: number;
  disclaimer?: string;
  ideas: PairedHedgeIdea[];
  notes: string[];
}

export interface AlternativeSentimentEvent {
  title: string;
  risk_level: string;
  source: string;
  event_time: string;
  score: number;
}

export interface AlternativeSentimentItem {
  symbol: string;
  event_count: number;
  sentiment_score: number;
  sentiment_label: "positive" | "negative" | "neutral" | string;
  source_mix: Record<string, number>;
  latest_events: AlternativeSentimentEvent[];
}

export interface AlternativeSentimentResponse {
  generated_at: string;
  mode: "research_only" | string;
  source: string;
  items: AlternativeSentimentItem[];
  summary: string;
  notes: string[];
}

export interface MultiExchangeArbitrageResearchResponse {
  generated_at: string;
  mode: "research_only" | string;
  production_enabled: boolean;
  tradable: boolean;
  symbols: string[];
  opportunities: unknown[];
  required_before_production: string[];
  summary: string;
}
