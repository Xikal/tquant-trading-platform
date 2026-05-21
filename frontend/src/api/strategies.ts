import { apiClient } from "./httpClient";
import type { BacktestListResponse, BacktestVerdictThresholdsResponse } from "./backtestTypes";

const request = apiClient.request;
const requestCached = apiClient.requestCached;

export interface StrategyMeta {
  key: string;
  name: string;
  display_name: string;
  description: string;
  tier: "core" | "auxiliary" | "research" | "factor" | string;
  category_key: "core" | "auxiliary" | "research" | "factor" | string;
  category: string;
  display_category: string;
  risk_level: string;
  typical_holding_days: string;
  sort_order: number;
  enabled?: boolean;
  probe_status?: string;
  probe_summary?: string;
  visibility?: string;
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
    max_single_order_pct?: number;
    max_positions?: number;
    max_daily_loss_pct?: number;
    min_cash_reserve?: number;
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

export interface StrategySignalReplayItem {
  latest_trade_date: string;
  strategy_key: string;
  symbol: string;
  name: string;
  buy_signal_state: string;
  buy_signal_text: string;
  score: number;
  latest_price?: number | null;
  change_pct?: number | null;
  entry_zone?: string;
  stop_loss?: number | null;
  suggested_position_text?: string;
  summary?: string;
  reasons?: string[];
  pnl_pct?: number | null;
  return_pct?: number | null;
  outcome?: string | null;
  signal_snapshot?: Record<string, unknown> | null;
  updated_at?: string;
}

export interface StrategyWorkspaceBffResponse {
  api_version: string;
  schema_version?: string;
  generated_at: string;
  strategy_meta: { strategies: StrategyMeta[] } | null;
  presets: { presets: StrategyPreset[] } | null;
  recent_runs: BacktestListResponse | null;
  verdict_thresholds: BacktestVerdictThresholdsResponse | null;
  partial_errors: Array<{ source: string; detail: string }>;
}

export const strategiesApi = {
  getStrategyWorkspaceBff: () =>
    request<StrategyWorkspaceBffResponse>("/bff/v1/workspace/strategy?run_limit=8"),
  getStrategyMeta: () =>
    requestCached<{ strategies: StrategyMeta[] }>("/strategies/meta", 60_000),
  getPresets: () =>
    requestCached<{ presets: StrategyPreset[] }>("/strategy/presets", 60_000),
  searchSymbols: (query: string, limit = 10) =>
    request<{ items: SymbolSearchItem[]; total: number }>(
      `/symbols/search?q=${encodeURIComponent(query)}&limit=${limit}`
    ),
  listSignalReplay: (strategy: string, symbol = "", limit = 20, lookbackDays = 60) => {
    const params = new URLSearchParams();
    params.set("strategy", strategy);
    params.set("limit", String(limit));
    params.set("lookback_days", String(lookbackDays));
    if (symbol.trim()) {
      params.set("symbol", symbol.trim());
    }
    return request<{ items: StrategySignalReplayItem[]; total: number }>(
      `/strategy/signals/replay?${params.toString()}`
    );
  },
  promoteStrategy: (payload: { strategy_key: string; target_tier: string; reason?: string; evidence_summary?: string }) =>
    request<{ ok: boolean; strategy_key: string; action: string; tier: string; message: string }>(
      "/strategy/governance/promote",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),
  demoteStrategy: (payload: { strategy_key: string; reason?: string; evidence_summary?: string }) =>
    request<{ ok: boolean; strategy_key: string; action: string; tier: string; message: string }>(
      "/strategy/governance/demote",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),
};
