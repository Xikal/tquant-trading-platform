import { request, requestCached } from "./base";

export interface StrategyMeta {
  key: string;
  name: string;
  display_name: string;
  description: string;
  category: string;
  risk_level: string;
  typical_holding_days: string;
  sort_order: number;
}

export interface StrategyPreset {
  id?: number | null;
  key: string;
  name: string;
  description: string;
  config: {
    range?: "6m" | "12m" | "24m" | string;
    initial_capital?: number;
    strategies?: string[];
    execution_model?: string;
    max_position_pct?: number;
    max_positions?: number;
    stop_loss_pct?: number;
    take_profit_pct?: number;
    benchmark?: string;
  };
  sort_order: number;
}

export interface SymbolSearchItem {
  symbol: string;
  name: string;
  latest_price?: number | null;
  industry?: string;
  market?: string;
  instrument_type?: string;
}

export const strategiesApi = {
  getStrategyMeta: () =>
    requestCached<{ strategies: StrategyMeta[] }>("/strategies/meta", 60_000),
  getPresets: () =>
    requestCached<{ presets: StrategyPreset[] }>("/strategy/presets", 60_000),
  searchSymbols: (query: string, limit = 10) =>
    request<{ items: SymbolSearchItem[]; total: number }>(
      `/symbols/search?q=${encodeURIComponent(query)}&limit=${limit}`
    ),
};
