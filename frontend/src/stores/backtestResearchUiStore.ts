import { create } from "zustand";

export type BacktestCompareSortKey = "return" | "sharpe" | "drawdown";

interface EtfT0BacktestUiState {
  symbol: string;
  name: string;
  quantity: string;
  maxTrades: string;
  minBars: string;
  barsText: string;
  loading: boolean;
  researchLoading: boolean;
  error: string;
}

interface BacktestResearchUiState {
  compareSortKey: BacktestCompareSortKey;
  etfT0: EtfT0BacktestUiState;
  capacityStrategies: string;
  capacityRunId: string;
  strategyImprovementLoading: boolean;
  strategyImprovementError: string;
  capacityLoading: string;
  capacityError: string;
  setCompareSortKey: (compareSortKey: BacktestCompareSortKey) => void;
  setEtfT0: (patch: Partial<EtfT0BacktestUiState>) => void;
  setCapacityStrategies: (capacityStrategies: string) => void;
  setCapacityRunId: (capacityRunId: string) => void;
  setStrategyImprovement: (patch: Partial<Pick<BacktestResearchUiState, "strategyImprovementLoading" | "strategyImprovementError">>) => void;
  setCapacityLoading: (loading: string) => void;
  setCapacityError: (error: string) => void;
}

export const useBacktestResearchUiStore = create<BacktestResearchUiState>((set) => ({
  compareSortKey: "return",
  etfT0: {
    symbol: "510300",
    name: "沪深300ETF",
    quantity: "10000",
    maxTrades: "3",
    minBars: "20",
    barsText: "",
    loading: false,
    researchLoading: false,
    error: "",
  },
  capacityStrategies: "",
  capacityRunId: "",
  strategyImprovementLoading: false,
  strategyImprovementError: "",
  capacityLoading: "",
  capacityError: "",
  setCompareSortKey: (compareSortKey) => set({ compareSortKey }),
  setEtfT0: (patch) => set((state) => ({ etfT0: { ...state.etfT0, ...patch } })),
  setCapacityStrategies: (capacityStrategies) => set({ capacityStrategies }),
  setCapacityRunId: (capacityRunId) => set({ capacityRunId }),
  setStrategyImprovement: (patch) => set(patch),
  setCapacityLoading: (capacityLoading) => set({ capacityLoading }),
  setCapacityError: (capacityError) => set({ capacityError }),
}));
