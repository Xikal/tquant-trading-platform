import { create } from "zustand";
import { STRATEGY_OPTIONS, type StrategyOption } from "../constants/strategies";
import {
  initialBacktestForm,
  initialOptimizationForm,
  initialValidationForm,
  type BacktestFormState,
  type OptimizationFormState,
  type ValidationFormState,
} from "../features/backtest/backtestForms";

type BacktestMode = "quick" | "expert";
type StateValue<T> = T | ((current: T) => T);

interface BacktestUiStore {
  mode: BacktestMode;
  verdictThresholdVersion: number;
  strategyOptions: StrategyOption[];
  form: BacktestFormState;
  loading: string;
  error: string;
  notice: string;
  optimizationForm: OptimizationFormState;
  selectedOptimizationId: number | null;
  validationForm: ValidationFormState;
  selectedValidationId: number | null;
  compareRunIds: string;
  researchLoading: string;
  researchError: string;
  researchNotice: string;
  setMode: (mode: BacktestMode) => void;
  setStrategyOptions: (strategyOptions: StrategyOption[]) => void;
  setForm: (form: StateValue<BacktestFormState>) => void;
  setLoading: (loading: string) => void;
  setError: (error: string) => void;
  setNotice: (notice: string) => void;
  setOptimizationForm: (form: StateValue<OptimizationFormState>) => void;
  setSelectedOptimizationId: (id: number | null) => void;
  setValidationForm: (form: StateValue<ValidationFormState>) => void;
  setSelectedValidationId: (id: number | null) => void;
  setCompareRunIds: (compareRunIds: string) => void;
  setResearchLoading: (researchLoading: string) => void;
  setResearchError: (researchError: string) => void;
  setResearchNotice: (researchNotice: string) => void;
  bumpVerdictThresholdVersion: () => void;
}

export const useBacktestUiStore = create<BacktestUiStore>((set) => ({
  mode: "quick",
  verdictThresholdVersion: 0,
  strategyOptions: [...STRATEGY_OPTIONS],
  form: initialBacktestForm,
  loading: "",
  error: "",
  notice: "",
  optimizationForm: initialOptimizationForm,
  selectedOptimizationId: null,
  validationForm: initialValidationForm,
  selectedValidationId: null,
  compareRunIds: "",
  researchLoading: "",
  researchError: "",
  researchNotice: "",
  setMode: (mode) => set({ mode }),
  setStrategyOptions: (strategyOptions) => set({ strategyOptions }),
  setForm: (form) => set((state) => ({ form: typeof form === "function" ? form(state.form) : form })),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setNotice: (notice) => set({ notice }),
  setOptimizationForm: (optimizationForm) => set((state) => ({
    optimizationForm: typeof optimizationForm === "function" ? optimizationForm(state.optimizationForm) : optimizationForm,
  })),
  setSelectedOptimizationId: (selectedOptimizationId) => set({ selectedOptimizationId }),
  setValidationForm: (validationForm) => set((state) => ({
    validationForm: typeof validationForm === "function" ? validationForm(state.validationForm) : validationForm,
  })),
  setSelectedValidationId: (selectedValidationId) => set({ selectedValidationId }),
  setCompareRunIds: (compareRunIds) => set({ compareRunIds }),
  setResearchLoading: (researchLoading) => set({ researchLoading }),
  setResearchError: (researchError) => set({ researchError }),
  setResearchNotice: (researchNotice) => set({ researchNotice }),
  bumpVerdictThresholdVersion: () => set((state) => ({ verdictThresholdVersion: state.verdictThresholdVersion + 1 })),
}));
