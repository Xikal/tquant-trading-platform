import type { LowBuyPriorityBoardResult } from "./playbook";
import type { SectorEtfT0Response } from "./market";
import type { WatchlistSignal } from "./watchlist";

export interface MonitorSnapshot {
  updated_at: string;
  watchlist_signals: WatchlistSignal[];
  priority_board: LowBuyPriorityBoardResult;
  sector_etf_t0?: SectorEtfT0Response;
}
