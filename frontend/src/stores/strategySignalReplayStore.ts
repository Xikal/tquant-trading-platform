import { create } from "zustand";
import type { StrategySignalReplayItem } from "../api/strategies";

interface StrategySignalReplayState {
  symbol: string;
  strategy: string;
  lookbackDays: string;
  onlyFailures: boolean;
  items: StrategySignalReplayItem[];
  loading: boolean;
  error: string;
  setSymbol: (symbol: string) => void;
  setStrategy: (strategy: string) => void;
  setLookbackDays: (lookbackDays: string) => void;
  toggleOnlyFailures: () => void;
  setItems: (items: StrategySignalReplayItem[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string) => void;
}

export const useStrategySignalReplayStore = create<StrategySignalReplayState>((set) => ({
  symbol: "",
  strategy: "first_board",
  lookbackDays: "60",
  onlyFailures: false,
  items: [],
  loading: false,
  error: "",
  setSymbol: (symbol) => set({ symbol }),
  setStrategy: (strategy) => set({ strategy }),
  setLookbackDays: (lookbackDays) => set({ lookbackDays }),
  toggleOnlyFailures: () => set((state) => ({ onlyFailures: !state.onlyFailures })),
  setItems: (items) => set({ items }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
