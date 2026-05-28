export interface EtfT0MinuteBarInput {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
}

export interface EtfT0BacktestRequest {
  symbol: string;
  name?: string;
  quantity: number;
  max_trades_per_day: number;
  min_signal_bars: number;
  params?: Record<string, number | string | boolean | null>;
  bars: EtfT0MinuteBarInput[];
}

export interface EtfT0BacktestTrade {
  symbol: string;
  side: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  gross_pnl: number;
  total_fee: number;
  net_pnl: number;
  net_return_pct: number;
  exit_reason: string;
  signal_snapshot?: Record<string, unknown>;
}

export interface EtfT0BacktestResponse {
  symbol: string;
  name: string;
  version: string;
  bar_count: number;
  trade_count: number;
  win_rate_pct: number;
  gross_pnl: number;
  net_pnl: number;
  avg_net_return_pct: number;
  profit_factor?: number | null;
  max_drawdown_pct: number;
  baseline_hold_return_pct: number;
  baseline_no_trade_return_pct: number;
  turnover: number;
  rejected_signal_count: number;
  trades: EtfT0BacktestTrade[];
  notes: string[];
}

export interface EtfT0MarketRegimeSegmentInput {
  regime: string;
  start_time: string;
  end_time: string;
}

export interface EtfT0ResearchRequest extends EtfT0BacktestRequest {
  vwap_deviation_values?: number[];
  oversold_rsi_values?: number[];
  market_regime_segments?: EtfT0MarketRegimeSegmentInput[];
}

export interface EtfT0HeatmapCell {
  buy_vwap_deviation_pct: number;
  sell_vwap_deviation_pct: number;
  oversold_rsi: number;
  overbought_rsi: number;
  trade_count: number;
  win_rate_pct: number;
  net_pnl: number;
  profit_factor?: number | null;
  max_drawdown_pct: number;
  baseline_hold_return_pct: number;
  score: number;
  pass_gate: boolean;
  notes: string[];
}

export interface EtfT0RegimeValidation {
  regime: string;
  start_time: string;
  end_time: string;
  bar_count: number;
  trade_count: number;
  win_rate_pct: number;
  net_pnl: number;
  profit_factor?: number | null;
  max_drawdown_pct: number;
  baseline_hold_return_pct: number;
  verdict: string;
  notes: string[];
}

export interface EtfT0ResearchResponse {
  symbol: string;
  name: string;
  version: string;
  research_only: boolean;
  base_report: EtfT0BacktestResponse;
  heatmap: EtfT0HeatmapCell[];
  regime_validations: EtfT0RegimeValidation[];
  notes: string[];
}
