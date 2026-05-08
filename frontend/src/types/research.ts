import type { ActionType } from "./market";

export interface ReplayItem {
  id: number;
  symbol: string;
  outcome: string;
  pnl_pct: number;
  max_favorable_excursion: number;
  max_adverse_excursion: number;
  review_notes: string;
  created_at: string;
}

export interface BacktestTrade {
  timestamp: string;
  action: ActionType;
  entry_price: number;
  exit_price: number;
  pnl_pct: number;
  signal_score: number;
}

export interface BacktestResult {
  run_id?: number | null;
  symbol: string;
  total_trades: number;
  win_rate: number;
  avg_pnl_pct: number;
  profit_factor: number;
  max_drawdown: number;
  walk_forward_score: number;
  trades: BacktestTrade[];
}

export interface BacktestRun {
  id: number;
  name: string;
  params: Record<string, unknown>;
  result: Record<string, unknown>;
  created_at: string;
}

export interface BacktestRunListResponse {
  runs: BacktestRun[];
}

export interface StrategyValidationItem {
  strategy_key: string;
  evaluated_signals: number;
  filled_signals: number;
  win_rate_pct: number;
  net_win_rate_pct: number;
  avg_return_pct: number;
  in_sample_return_pct?: number;
  out_sample_return_pct?: number;
  out_sample_win_rate_pct?: number;
  profit_factor?: number | null;
  max_drawdown_pct: number;
  pbo_risk: string;
  pbo_probability?: number | null;
  by_market_state: Record<string, unknown>;
}

export interface StrategyValidationReport {
  run_id?: number | null;
  validation_mode?: "quick_replay";
  validation_mode_text?: string;
  engine_note?: string;
  generated_at: string;
  lookback_days: number;
  strategy_count: number;
  total_filled_signals: number;
  items: StrategyValidationItem[];
  summary: string;
}

export interface IntradayConfirmationItem {
  symbol: string;
  name: string;
  trade_date: string;
  vwap: number;
  latest_price: number;
  above_vwap: boolean;
  confirmed: boolean;
  late_confirmed: boolean;
  score: number;
  reason: string;
  profile: Record<string, unknown>;
  big_order: Record<string, unknown>;
  tick: Record<string, unknown>;
  updated_at?: string | null;
}

export interface RiskEventItem {
  id: number;
  account_id?: number | null;
  symbol: string;
  event_type: string;
  severity: string;
  status: string;
  message: string;
  triggered_at: string;
}
