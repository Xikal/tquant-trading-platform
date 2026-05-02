import type { QuoteSnapshot, TradingRule } from "./market";
import type { StrategySuggestion } from "./analysis";

export interface WatchlistItem {
  symbol: string;
  name: string;
  base_position: number;
  available_position: number;
  cost_basis?: number | null;
  memo: string;
  created_at?: string;
}

export interface WatchlistSignal {
  symbol: string;
  name: string;
  base_position: number;
  available_position: number;
  cost_basis?: number | null;
  memo: string;
  signal: StrategySuggestion;
  quote: QuoteSnapshot;
  rules: TradingRule;
  error?: string | null;
}
