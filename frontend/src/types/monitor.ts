import type { LowBuyPriorityBoardResult } from "./playbook";
import type { WatchlistSignal } from "./watchlist";

export interface MonitorSnapshot {
  updated_at: string;
  watchlist_signals: WatchlistSignal[];
  priority_board: LowBuyPriorityBoardResult;
}
