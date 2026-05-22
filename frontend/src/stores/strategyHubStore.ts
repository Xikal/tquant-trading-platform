import { create } from "zustand";
import type { BacktestExecutionModel, BacktestRunSummary } from "../api/backtests";
import type { StrategyMeta, StrategyPreset } from "../api/strategies";

export type StrategyHubTab = "quick" | "signals" | "optimize" | "validate" | "compare" | "capacity" | "factor" | "history";

export interface StrategyQuickForm {
  name: string;
  start_date: string;
  end_date: string;
  initial_capital: string;
  execution_model: BacktestExecutionModel;
  max_position_pct: string;
  max_single_order_pct: string;
  max_positions: string;
  max_daily_loss_pct: string;
  min_cash_reserve: string;
  benchmark: string;
  strategies: string[];
}

export const DEFAULT_STRATEGY_FORM: StrategyQuickForm = {
  name: "策略快速回测",
  start_date: shiftDate(-183),
  end_date: shiftDate(0),
  initial_capital: "500000",
  execution_model: "conservative_slippage",
  max_position_pct: "30",
  max_single_order_pct: "15",
  max_positions: "8",
  max_daily_loss_pct: "5",
  min_cash_reserve: "5000",
  benchmark: "000300",
  strategies: ["first_board", "volume_shrink"],
};

interface StrategyHubUiStore {
  tab: StrategyHubTab;
  confirmOpen: boolean;
  strategies: StrategyMeta[];
  presets: StrategyPreset[];
  runs: BacktestRunSummary[];
  form: StrategyQuickForm;
  loading: string;
  error: string;
  notice: string;
  setTab: (tab: StrategyHubTab) => void;
  setConfirmOpen: (open: boolean) => void;
  setStrategies: (strategies: StrategyMeta[]) => void;
  setPresets: (presets: StrategyPreset[]) => void;
  setRuns: (runs: BacktestRunSummary[]) => void;
  setForm: (form: StrategyQuickForm | ((current: StrategyQuickForm) => StrategyQuickForm)) => void;
  setLoading: (loading: string | ((current: string) => string)) => void;
  setError: (error: string) => void;
  setNotice: (notice: string) => void;
}

export const useStrategyHubUiStore = create<StrategyHubUiStore>((set) => ({
  tab: initialStrategyHubTab(),
  confirmOpen: false,
  strategies: [],
  presets: [],
  runs: [],
  form: DEFAULT_STRATEGY_FORM,
  loading: "",
  error: "",
  notice: "",
  setTab: (tab) => set({ tab }),
  setConfirmOpen: (confirmOpen) => set({ confirmOpen }),
  setStrategies: (strategies) => set({ strategies }),
  setPresets: (presets) => set({ presets }),
  setRuns: (runs) => set({ runs }),
  setForm: (form) => set((state) => ({ form: typeof form === "function" ? form(state.form) : form })),
  setLoading: (loading) => set((state) => ({ loading: typeof loading === "function" ? loading(state.loading) : loading })),
  setError: (error) => set({ error }),
  setNotice: (notice) => set({ notice }),
}));

function initialStrategyHubTab(): StrategyHubTab {
  if (typeof window === "undefined") return "quick";
  const raw = new URLSearchParams(window.location.search).get("tab") || "";
  if (raw === "replay" || raw === "signals") return "signals";
  if (raw === "optimize") return "optimize";
  if (raw === "validate") return "validate";
  if (raw === "compare") return "compare";
  if (raw === "factor" || raw === "factor-mining") return "factor";
  if (raw === "capacity" || raw === "ml") return "capacity";
  if (raw === "history" || raw === "backtest") return "history";
  return "quick";
}

function shiftDate(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}
