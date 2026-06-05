import type { components } from "../generated/api-types";

export type TradingExperienceDataQuality = "ok" | "insufficient" | "no_data" | "blocked" | "stale" | "research_only";
export type ReviewWorkspaceResponse = components["schemas"]["ReviewWorkspaceResponse"];
export type ReviewWorkspaceItem = components["schemas"]["ReviewWorkspaceItem"];
export type TradeJournalEntryUpdate = components["schemas"]["TradeJournalEntryUpdate"];

export interface TradingExperienceMeta {
  data_quality: TradingExperienceDataQuality;
  as_of: string;
  engine_version: string;
  source: string;
  research_only: boolean;
}

export interface TradingExperienceReadinessResponse extends TradingExperienceMeta {
  enabled: boolean;
  flags: Record<string, boolean>;
  disabled_reasons: string[];
  worker_task_types: string[];
}

export interface ReviewPoolItem {
  pool_date: string;
  symbol: string;
  name: string;
  board_type: string;
  board_name: string;
  status: "in_pool" | "retained" | "dropped";
  entry_pct: number;
  volume_ratio: number;
  mainline_state: string;
  sector_role: string;
  drop_reason: string;
  tracked_days: number;
  evidence: string[];
  data_quality: TradingExperienceDataQuality;
  as_of: string;
  engine_version: string;
}

export interface ReviewPoolResponse extends TradingExperienceMeta {
  enabled: boolean;
  pool_date: string | null;
  board_filter: "include_all" | "main_only";
  items: ReviewPoolItem[];
  total: number;
}

export interface TradeJournalEntryCreate {
  account_id?: number | null;
  symbol: string;
  action: "buy" | "sell" | "trim" | "add" | "t_trade" | "note";
  reason_text?: string;
  signal_source?: string;
  discipline_flags?: Record<string, boolean>;
  mistake_tags?: string[];
}

export interface TradeJournalEntry extends TradeJournalEntryCreate {
  entry_id: number;
  user_id: number | null;
  data_quality: TradingExperienceDataQuality;
  as_of: string;
  engine_version: string;
  source: string;
  research_only: boolean;
  created_at: string;
  updated_at: string;
}

export interface TradeJournalResponse extends TradingExperienceMeta {
  enabled: boolean;
  items: TradeJournalEntry[];
  total: number;
}

export interface VolumePositionTag {
  symbol: string;
  trade_date: string;
  tag_code: string;
  level: "info" | "warn";
  evidence: string[];
  explanation: string;
  data_quality: TradingExperienceDataQuality;
  as_of: string;
  engine_version: string;
}

export interface VolumePositionTagResponse extends TradingExperienceMeta {
  enabled: boolean;
  symbol: string;
  items: VolumePositionTag[];
}

export interface RelativeStrengthItem {
  symbol: string;
  trade_date: string;
  index_code: string;
  sector_code: string;
  stock_pct: number;
  index_pct: number;
  sector_pct: number;
  rs_vs_index: number;
  rs_vs_sector: number;
  sector_rank: number;
  resilience_flag: "resilient" | "follow_down" | "neutral";
  data_quality: TradingExperienceDataQuality;
  as_of: string;
}

export interface RelativeStrengthResponse extends TradingExperienceMeta {
  enabled: boolean;
  items: RelativeStrengthItem[];
  total: number;
}

export interface HoldingDisciplineHint {
  account_id: number;
  symbol: string;
  hint_code: "trailing_stop" | "no_add_down_warning" | "break_down" | "emotional_pullback" | "watch_cadence";
  level: "info" | "warn";
  evidence: string[];
  data_quality: TradingExperienceDataQuality;
  as_of: string;
}

export interface HoldingDisciplineResponse extends TradingExperienceMeta {
  enabled: boolean;
  account_id: number | null;
  items: HoldingDisciplineHint[];
  total: number;
}

export interface LimitUpFollowthroughItem {
  symbol: string;
  limit_up_date: string;
  pattern_code: string;
  days_since: number;
  evidence: string[];
  backtest_winrate: number | null;
  backtest_pf: number | null;
  backtest_max_drawdown?: number | null;
  sample_count: number;
  quarter_stability: string;
  status: "research_only" | "observed" | "blocked";
  data_quality: TradingExperienceDataQuality;
  as_of: string;
}

export interface LimitUpFollowthroughResponse extends TradingExperienceMeta {
  enabled: boolean;
  items: LimitUpFollowthroughItem[];
  total: number;
  backtest_gate: "blocked" | "passed" | "failed";
  gate_reasons: string[];
  backtest_window_months?: number;
}

export interface TTradeAttributionItem {
  account_id: number;
  symbol: string;
  period: string;
  t_trade_count: number;
  realized_cost_delta: number;
  win_rate: number;
  sell_fly_count: number;
  vs_no_t_trade_return_delta: number | null;
  minute_data_coverage: number;
  completeness_issues?: string[];
  comparison_method?: string;
  key_level_state?: string;
  discipline_notes?: string[];
  data_quality: TradingExperienceDataQuality;
  as_of: string;
}

export interface TTradeAttributionResponse extends TradingExperienceMeta {
  enabled: boolean;
  account_id: number | null;
  items: TTradeAttributionItem[];
  total: number;
}
