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
