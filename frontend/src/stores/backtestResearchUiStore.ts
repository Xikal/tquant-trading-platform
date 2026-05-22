import { create } from "zustand";
import type { PortfolioOptimizationResponse, PositionPolicyResearchResponse } from "../api/backtests";
import type { MLSignalOnlineLearningStatus, StrategyCapacityResponse } from "../api/mlSignals";

export type BacktestCompareSortKey = "return" | "sharpe" | "drawdown";

interface BacktestResearchUiState {
  compareSortKey: BacktestCompareSortKey;
  capacityStrategies: string;
  capacityRunId: string;
  mlStatus: MLSignalOnlineLearningStatus | null;
  capacity: StrategyCapacityResponse | null;
  markowitz: PortfolioOptimizationResponse | null;
  blackLitterman: PortfolioOptimizationResponse | null;
  policy: PositionPolicyResearchResponse | null;
  capacityLoading: string;
  capacityError: string;
  setCompareSortKey: (compareSortKey: BacktestCompareSortKey) => void;
  setCapacityStrategies: (capacityStrategies: string) => void;
  setCapacityRunId: (capacityRunId: string) => void;
  setMlStatus: (status: MLSignalOnlineLearningStatus | null) => void;
  setCapacity: (capacity: StrategyCapacityResponse | null) => void;
  setMarkowitz: (markowitz: PortfolioOptimizationResponse | null) => void;
  setBlackLitterman: (blackLitterman: PortfolioOptimizationResponse | null) => void;
  setPolicy: (policy: PositionPolicyResearchResponse | null) => void;
  setCapacityLoading: (loading: string) => void;
  setCapacityError: (error: string) => void;
}

export const useBacktestResearchUiStore = create<BacktestResearchUiState>((set) => ({
  compareSortKey: "return",
  capacityStrategies: "",
  capacityRunId: "",
  mlStatus: null,
  capacity: null,
  markowitz: null,
  blackLitterman: null,
  policy: null,
  capacityLoading: "",
  capacityError: "",
  setCompareSortKey: (compareSortKey) => set({ compareSortKey }),
  setCapacityStrategies: (capacityStrategies) => set({ capacityStrategies }),
  setCapacityRunId: (capacityRunId) => set({ capacityRunId }),
  setMlStatus: (mlStatus) => set({ mlStatus }),
  setCapacity: (capacity) => set({ capacity }),
  setMarkowitz: (markowitz) => set({ markowitz }),
  setBlackLitterman: (blackLitterman) => set({ blackLitterman }),
  setPolicy: (policy) => set({ policy }),
  setCapacityLoading: (capacityLoading) => set({ capacityLoading }),
  setCapacityError: (capacityError) => set({ capacityError }),
}));
