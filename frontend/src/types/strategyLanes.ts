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
}
