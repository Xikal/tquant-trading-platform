import { create } from "zustand";
import type { EtfT0BacktestResponse, EtfT0ResearchResponse, PortfolioOptimizationResponse, PositionPolicyResearchResponse, StrategyImprovementReportResponse } from "../api/backtests";
import type { MLSignalOnlineLearningStatus, StrategyCapacityResponse } from "../api/mlSignals";

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
  result: EtfT0BacktestResponse | null;
  researchResult: EtfT0ResearchResponse | null;
}

interface BacktestResearchUiState {
  compareSortKey: BacktestCompareSortKey;
  etfT0: EtfT0BacktestUiState;
  capacityStrategies: string;
  capacityRunId: string;
  mlStatus: MLSignalOnlineLearningStatus | null;
  capacity: StrategyCapacityResponse | null;
  strategyImprovementReport: StrategyImprovementReportResponse | null;
  strategyImprovementLoading: boolean;
  strategyImprovementError: string;
  markowitz: PortfolioOptimizationResponse | null;
  blackLitterman: PortfolioOptimizationResponse | null;
  policy: PositionPolicyResearchResponse | null;
  capacityLoading: string;
  capacityError: string;
  setCompareSortKey: (compareSortKey: BacktestCompareSortKey) => void;
  setEtfT0: (patch: Partial<EtfT0BacktestUiState>) => void;
  setCapacityStrategies: (capacityStrategies: string) => void;
  setCapacityRunId: (capacityRunId: string) => void;
  setMlStatus: (status: MLSignalOnlineLearningStatus | null) => void;
  setCapacity: (capacity: StrategyCapacityResponse | null) => void;
  setStrategyImprovement: (patch: Partial<Pick<BacktestResearchUiState, "strategyImprovementReport" | "strategyImprovementLoading" | "strategyImprovementError">>) => void;
  setMarkowitz: (markowitz: PortfolioOptimizationResponse | null) => void;
  setBlackLitterman: (blackLitterman: PortfolioOptimizationResponse | null) => void;
  setPolicy: (policy: PositionPolicyResearchResponse | null) => void;
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
    result: null,
    researchResult: null,
  },
  capacityStrategies: "",
  capacityRunId: "",
  mlStatus: null,
  capacity: null,
  strategyImprovementReport: null,
  strategyImprovementLoading: false,
  strategyImprovementError: "",
  markowitz: null,
  blackLitterman: null,
  policy: null,
  capacityLoading: "",
  capacityError: "",
  setCompareSortKey: (compareSortKey) => set({ compareSortKey }),
  setEtfT0: (patch) => set((state) => ({ etfT0: { ...state.etfT0, ...patch } })),
  setCapacityStrategies: (capacityStrategies) => set({ capacityStrategies }),
  setCapacityRunId: (capacityRunId) => set({ capacityRunId }),
  setMlStatus: (mlStatus) => set({ mlStatus }),
  setCapacity: (capacity) => set({ capacity }),
  setStrategyImprovement: (patch) => set(patch),
  setMarkowitz: (markowitz) => set({ markowitz }),
  setBlackLitterman: (blackLitterman) => set({ blackLitterman }),
  setPolicy: (policy) => set({ policy }),
  setCapacityLoading: (capacityLoading) => set({ capacityLoading }),
  setCapacityError: (capacityError) => set({ capacityError }),
}));
