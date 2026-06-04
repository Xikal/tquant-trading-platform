import type { LowBuyPriorityBoardResult } from "./playbook";
import type { IntradayMarketPulse, MarketBreadth, MarketHourlySnapshotHistoryItem, MarketReviewReport, MarketReviewStatus, PairedHedgeResearchResponse, SectorEtfT0Response, SectorRelativeStrengthResponse } from "./market";
import type { RuntimeStatus } from "./settings";
import type { WatchlistSignal } from "./watchlist";

export interface MonitorSnapshot {
  updated_at: string;
  watchlist_signals: WatchlistSignal[];
  priority_board: LowBuyPriorityBoardResult;
  sector_etf_t0?: SectorEtfT0Response;
}

export interface BffPartialError {
  source: string;
  detail: string;
  reason?: string;
  status_code?: number | null;
  timeout_ms?: number | null;
  fallback_source?: string;
  message?: string;
}

export interface MonitorWorkspaceBffResponse {
  api_version: string;
  schema_version?: string;
  generated_at: string;
  monitor_snapshot?: MonitorSnapshot | null;
  market_breadth?: MarketBreadth | null;
  market_pulse?: IntradayMarketPulse | null;
  hourly_snapshot_history?: MarketHourlySnapshotHistoryItem[];
  review_status?: MarketReviewStatus | null;
  review_reports?: MarketReviewReport[];
  sector_relative_strength?: SectorRelativeStrengthResponse | null;
  paired_hedge?: PairedHedgeResearchResponse | null;
  runtime?: RuntimeStatus | null;
  partial_errors: BffPartialError[];
}
