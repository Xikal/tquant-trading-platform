import { GENERATED_STRATEGY_META_FALLBACK } from "../generated/strategyMetaFallback";

export interface StrategyMetaFallback {
  key: string;
  name: string;
  display_name: string;
  label: string;
  description: string;
  tier: "core" | "auxiliary" | "research" | "factor" | string;
  category_key: string;
  category: string;
  display_category: string;
  risk_level: string;
  typical_holding_days: string;
  sort_order: number;
  enabled?: boolean;
  probe_status?: string;
  probe_summary?: string;
  visibility?: "full" | "backtest_only" | "hidden" | string;
}

export const FALLBACK_STRATEGY_META: StrategyMetaFallback[] = [...GENERATED_STRATEGY_META_FALLBACK];
export const STRATEGY_OPTIONS = FALLBACK_STRATEGY_META
  .filter((item) => item.enabled !== false && item.visibility !== "hidden")
  .map((item) => [item.key, `${item.label}${item.visibility === "backtest_only" ? "（仅回测研究）" : ""}`] as const);

export type StrategyOption = readonly [string, string];
