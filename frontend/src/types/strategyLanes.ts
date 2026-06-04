export type StrategyVariant = "baseline" | "front_row_weighted" | "front_row_only";
export type StrategyRole = "production_baseline" | "shadow_paper_candidate" | "elite_watch";
export type DisplayLane = StrategyVariant;

export interface StrategyLaneMeta {
  variant?: StrategyVariant;
  display_lane: DisplayLane;
  title: string;
  role: StrategyRole;
  subtitle?: string;
  production_enabled: boolean;
  paper_enabled: boolean;
  watch_only: boolean;
  production_sort_replaced: boolean;
}

export interface StrategyLanePlainStatus {
  conclusion?: string;
  reason?: string;
  next_step?: string;
}

export interface StrategyLaneReadinessSummary {
  status?: string;
  recommend_small_traffic_observation?: boolean;
  plain_status?: StrategyLanePlainStatus;
  blockers?: string[];
  blocker_texts?: string[];
  source_report?: string;
}

export interface StrategyEngineShadowPayload {
  strategy_key?: string;
  symbol?: string;
  signal_state?: string;
  production_score?: number | null;
  watch_score?: number | null;
  score_components?: Record<string, number>;
  exclusion_reasons?: string[];
  warning_tags?: string[];
  decision?: string;
  source?: string;
  metadata?: Record<string, unknown>;
  shadow_only?: boolean;
  replacement_enabled?: boolean;
  production_sort_replaced?: boolean;
  parity_status?: string;
  production_score_delta?: number | null;
  watch_score_delta?: number | null;
}

export interface StrategyLaneFields {
  strategy_variant?: StrategyVariant;
  strategy_role?: StrategyRole;
  display_lane?: DisplayLane;
  display_lane_title?: string;
  display_lane_subtitle?: string;
  production_sort_replaced?: boolean;
  production_enabled?: boolean;
  paper_enabled?: boolean;
  watch_only?: boolean;
  matched_strategy_variants?: StrategyVariant[];
  primary_lane_reason?: string;
  elite_watch_score?: number | null;
  readiness_status?: string;
  readiness_blockers?: string[];
  strategy_engine_shadow?: StrategyEngineShadowPayload | null;
  strategy_engine_decision?: string;
  strategy_engine_warning_tags?: string[];
  strategy_engine_exclusion_reasons?: string[];
  strategy_engine_score_delta?: number | null;
  strategy_engine_parity_status?: string;
}
