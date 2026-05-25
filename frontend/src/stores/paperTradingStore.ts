import { create } from "zustand";
import type {
  PaperAccount,
  PaperAgentRun,
  PaperAutoTradingStatus,
  PaperGroupedPerformance,
  PaperLedgerRepairResponse,
  PaperOrder,
  PaperPerformance,
  PaperPosition,
  PaperSectorEtfT0Performance,
  PaperStockPnlItem,
  PaperStockPnlSummary,
  PaperTagPerformance,
  PaperTrade,
  PaperTradeTag,
  RiskEventItem,
} from "../types";
import type { PaperOrderDraft } from "../features/workspace-shared/workspaceTypes";

export const DEFAULT_PAPER_ORDER_DRAFT: PaperOrderDraft = {
  symbol: "",
  name: "",
  side: "buy",
  order_type: "market",
  quantity: "100",
  price: "",
  current_price: "",
  strategy_key: "",
  reason: "",
  require_intraday_confirmation: false,
};

interface PaperTradingStore {
  account: PaperAccount | null;
  positions: PaperPosition[];
  orders: PaperOrder[];
  trades: PaperTrade[];
  stockPnl: PaperStockPnlItem[];
  stockPnlSummary: PaperStockPnlSummary | null;
  performance: PaperPerformance | null;
  sectorEtfT0Performance: PaperSectorEtfT0Performance | null;
  strategyPerformance: PaperGroupedPerformance[];
  marketPerformance: PaperGroupedPerformance[];
  tagPerformance: PaperTagPerformance[];
  tradeTags: Record<number, PaperTradeTag[]>;
  riskEvents: RiskEventItem[];
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  ledgerRepairStatus: PaperLedgerRepairResponse | null;
  draft: PaperOrderDraft;
  setAccount: (account: PaperAccount | null) => void;
  setPositions: (positions: PaperPosition[]) => void;
  setOrders: (orders: PaperOrder[]) => void;
  setTrades: (trades: PaperTrade[]) => void;
  setStockPnl: (items: PaperStockPnlItem[]) => void;
  setStockPnlSummary: (summary: PaperStockPnlSummary | null) => void;
  setPerformance: (performance: PaperPerformance | null) => void;
  setSectorEtfT0Performance: (performance: PaperSectorEtfT0Performance | null) => void;
  setStrategyPerformance: (performance: PaperGroupedPerformance[]) => void;
  setMarketPerformance: (performance: PaperGroupedPerformance[]) => void;
  setTagPerformance: (performance: PaperTagPerformance[]) => void;
  setTradeTags: (tags: Record<number, PaperTradeTag[]> | ((current: Record<number, PaperTradeTag[]>) => Record<number, PaperTradeTag[]>)) => void;
  setRiskEvents: (items: RiskEventItem[]) => void;
  setAutoTradingStatus: (status: PaperAutoTradingStatus | null) => void;
  setAutoTradingRuns: (runs: PaperAgentRun[]) => void;
  setLedgerRepairStatus: (status: PaperLedgerRepairResponse | null) => void;
  setDraft: (draft: PaperOrderDraft | ((current: PaperOrderDraft) => PaperOrderDraft)) => void;
  clearPaperData: () => void;
}

export const usePaperTradingStore = create<PaperTradingStore>((set) => ({
  account: null,
  positions: [],
  orders: [],
  trades: [],
  stockPnl: [],
  stockPnlSummary: null,
  performance: null,
  sectorEtfT0Performance: null,
  strategyPerformance: [],
  marketPerformance: [],
  tagPerformance: [],
  tradeTags: {},
  riskEvents: [],
  autoTradingStatus: null,
  autoTradingRuns: [],
  ledgerRepairStatus: null,
  draft: DEFAULT_PAPER_ORDER_DRAFT,
  setAccount: (account) => set({ account }),
  setPositions: (positions) => set({ positions }),
  setOrders: (orders) => set({ orders }),
  setTrades: (trades) => set({ trades }),
  setStockPnl: (stockPnl) => set({ stockPnl }),
  setStockPnlSummary: (stockPnlSummary) => set({ stockPnlSummary }),
  setPerformance: (performance) => set({ performance }),
  setSectorEtfT0Performance: (sectorEtfT0Performance) => set({ sectorEtfT0Performance }),
  setStrategyPerformance: (strategyPerformance) => set({ strategyPerformance }),
  setMarketPerformance: (marketPerformance) => set({ marketPerformance }),
  setTagPerformance: (tagPerformance) => set({ tagPerformance }),
  setTradeTags: (tradeTags) => set((state) => ({
    tradeTags: typeof tradeTags === "function" ? tradeTags(state.tradeTags) : tradeTags,
  })),
  setRiskEvents: (riskEvents) => set({ riskEvents }),
  setAutoTradingStatus: (autoTradingStatus) => set({ autoTradingStatus }),
  setAutoTradingRuns: (autoTradingRuns) => set({ autoTradingRuns }),
  setLedgerRepairStatus: (ledgerRepairStatus) => set({ ledgerRepairStatus }),
  setDraft: (draft) => set((state) => ({
    draft: typeof draft === "function" ? draft(state.draft) : draft,
  })),
  clearPaperData: () => set({
    account: null,
    positions: [],
    orders: [],
    trades: [],
    stockPnl: [],
    stockPnlSummary: null,
    performance: null,
    sectorEtfT0Performance: null,
    strategyPerformance: [],
    marketPerformance: [],
    tagPerformance: [],
    tradeTags: {},
    riskEvents: [],
    autoTradingStatus: null,
    autoTradingRuns: [],
    ledgerRepairStatus: null,
  }),
}));
