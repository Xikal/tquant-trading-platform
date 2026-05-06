import { GENERATED_STRATEGY_META_FALLBACK } from "../generated/strategyMetaFallback";

export const FALLBACK_STRATEGY_META = GENERATED_STRATEGY_META_FALLBACK;
export const STRATEGY_OPTIONS = FALLBACK_STRATEGY_META.map((item) => [item.key, item.label] as const);

export type StrategyOption = readonly [string, string];
