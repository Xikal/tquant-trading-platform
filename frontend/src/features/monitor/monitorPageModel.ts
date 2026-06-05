import type {
  IntradayMarketPulse,
  LowBuyPriorityBoardResult,
  MarketBreadth,
  SectorEtfT0Response,
} from "../../types";
import type { StockCardView } from "../workspace-shared/workspaceTypes";

export interface MonitorActionModelInput {
  priorityBoard: LowBuyPriorityBoardResult | null;
  priorityCards: StockCardView[];
  watchCards: StockCardView[];
}

export interface MonitorMarketModelInput {
  marketBreadth: MarketBreadth | null;
  marketPulse: IntradayMarketPulse | null;
  sectorEtfT0: SectorEtfT0Response | null;
}

export function buildMonitorActionModel({ priorityBoard, priorityCards, watchCards }: MonitorActionModelInput) {
  return {
    priorityCount: priorityCards.length,
    watchCount: watchCards.length,
    immediateCount: priorityBoard?.immediate_count ?? 0,
    observeCount: (priorityBoard?.focus_count ?? 0) + (priorityBoard?.track_count ?? 0),
    hasActionContext: Boolean(priorityCards.length || watchCards.length || priorityBoard),
  };
}

export function buildMonitorMarketModel({ marketBreadth, marketPulse, sectorEtfT0 }: MonitorMarketModelInput) {
  const etfOpportunityCount = sectorEtfT0?.opportunities?.length ?? 0;
  return {
    hasMarketContext: Boolean(marketBreadth || marketPulse || etfOpportunityCount),
    etfOpportunityCount,
    breadthReady: Boolean(marketBreadth?.breadth_ready),
    pulseQuality: marketPulse?.data_quality ?? "no_data",
  };
}
