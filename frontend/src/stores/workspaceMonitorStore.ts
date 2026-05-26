import { create } from "zustand";
import type {
  InstrumentSyncStatus,
  IntradayKeyLevelResponse,
  IntradayMarketPulse,
  LowBuyPriorityBoardResult,
  MarketBreadth,
  MarketHourlySnapshotHistoryItem,
  MarketReviewReport,
  MarketReviewStatus,
  PairedHedgeResearchResponse,
  RuntimeStatus,
  SectorEtfT0Response,
  SectorRelativeStrengthResponse,
  WatchlistSignal,
} from "../types";

interface WorkspaceMonitorStore {
  priorityBoard: LowBuyPriorityBoardResult | null;
  marketBreadth: MarketBreadth | null;
  marketPulse: IntradayMarketPulse | null;
  hourlySnapshotHistory: MarketHourlySnapshotHistoryItem[];
  reviewStatus: MarketReviewStatus | null;
  reviewReports: MarketReviewReport[];
  sectorRelativeStrength: SectorRelativeStrengthResponse | null;
  keyLevelAlerts: IntradayKeyLevelResponse[];
  watchlistSignals: WatchlistSignal[];
  sectorEtfT0: SectorEtfT0Response | null;
  pairedHedge: PairedHedgeResearchResponse | null;
  runtime: RuntimeStatus | null;
  instrumentSyncStatus: InstrumentSyncStatus | null;
  setPriorityBoard: (value: LowBuyPriorityBoardResult | null | ((current: LowBuyPriorityBoardResult | null) => LowBuyPriorityBoardResult | null)) => void;
  setMarketBreadth: (value: MarketBreadth | null) => void;
  setMarketPulse: (value: IntradayMarketPulse | null) => void;
  setHourlySnapshotHistory: (value: MarketHourlySnapshotHistoryItem[]) => void;
  setReviewStatus: (value: MarketReviewStatus | null) => void;
  setReviewReports: (value: MarketReviewReport[]) => void;
  setSectorRelativeStrength: (value: SectorRelativeStrengthResponse | null) => void;
  setKeyLevelAlerts: (value: IntradayKeyLevelResponse[]) => void;
  setWatchlistSignals: (value: WatchlistSignal[] | ((current: WatchlistSignal[]) => WatchlistSignal[])) => void;
  setSectorEtfT0: (value: SectorEtfT0Response | null | ((current: SectorEtfT0Response | null) => SectorEtfT0Response | null)) => void;
  setPairedHedge: (value: PairedHedgeResearchResponse | null) => void;
  setRuntime: (value: RuntimeStatus | null) => void;
  setInstrumentSyncStatus: (value: InstrumentSyncStatus | null) => void;
  resetMonitorData: () => void;
}

export const useWorkspaceMonitorStore = create<WorkspaceMonitorStore>((set) => ({
  priorityBoard: null,
  marketBreadth: null,
  marketPulse: null,
  hourlySnapshotHistory: [],
  reviewStatus: null,
  reviewReports: [],
  sectorRelativeStrength: null,
  keyLevelAlerts: [],
  watchlistSignals: [],
  sectorEtfT0: null,
  pairedHedge: null,
  runtime: null,
  instrumentSyncStatus: null,
  setPriorityBoard: (value) => set((state) => ({
    priorityBoard: typeof value === "function" ? value(state.priorityBoard) : value,
  })),
  setMarketBreadth: (marketBreadth) => set({ marketBreadth }),
  setMarketPulse: (marketPulse) => set({ marketPulse }),
  setHourlySnapshotHistory: (hourlySnapshotHistory) => set({ hourlySnapshotHistory }),
  setReviewStatus: (reviewStatus) => set({ reviewStatus }),
  setReviewReports: (reviewReports) => set({ reviewReports }),
  setSectorRelativeStrength: (sectorRelativeStrength) => set({ sectorRelativeStrength }),
  setKeyLevelAlerts: (keyLevelAlerts) => set({ keyLevelAlerts }),
  setWatchlistSignals: (value) => set((state) => ({
    watchlistSignals: typeof value === "function" ? value(state.watchlistSignals) : value,
  })),
  setSectorEtfT0: (value) => set((state) => ({
    sectorEtfT0: typeof value === "function" ? value(state.sectorEtfT0) : value,
  })),
  setPairedHedge: (pairedHedge) => set({ pairedHedge }),
  setRuntime: (runtime) => set({ runtime }),
  setInstrumentSyncStatus: (instrumentSyncStatus) => set({ instrumentSyncStatus }),
  resetMonitorData: () => set({
    priorityBoard: null,
    marketBreadth: null,
    marketPulse: null,
    hourlySnapshotHistory: [],
    reviewStatus: null,
    reviewReports: [],
    sectorRelativeStrength: null,
    keyLevelAlerts: [],
    watchlistSignals: [],
    sectorEtfT0: null,
    pairedHedge: null,
  }),
}));
