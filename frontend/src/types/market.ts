export type ActionType = "positive_t" | "negative_t" | "hold";
export type RiskLevel = "low" | "medium" | "high";

export interface Instrument {
  symbol: string;
  name: string;
  market: string;
  instrument_type: string;
  sector_name?: string | null;
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
}

export interface SectorEtfT0Opportunity {
  sector_name: string;
  etf_symbol: string;
  etf_name: string;
  source_signal_symbol: string;
  source_signal_name: string;
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
  ideas: PairedHedgeIdea[];
  notes: string[];
}
