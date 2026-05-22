import { create } from "zustand";
import type {
  BacktestAttributionResponse,
  BacktestCompareResponse,
  BacktestMonthlyReturnsResponse,
  BacktestOptimizationDetail,
  BacktestOptimizationSummary,
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestStrategyCorrelationResponse,
  BacktestTrade,
  BacktestValidationDetail,
  BacktestValidationSummary,
  EquityPoint,
} from "../api/backtests";
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
  runs: BacktestRunSummary[];
  selectedRun: BacktestRunDetail | null;
  equity: EquityPoint[];
  trades: BacktestTrade[];
  loading: string;
  error: string;
  notice: string;
  monthlyReturns: BacktestMonthlyReturnsResponse | null;
  attribution: BacktestAttributionResponse | null;
  correlation: BacktestStrategyCorrelationResponse | null;
  optimizationForm: OptimizationFormState;
  optimizations: BacktestOptimizationSummary[];
  selectedOptimizationId: number | null;
  selectedOptimization: BacktestOptimizationDetail | null;
  validationForm: ValidationFormState;
  validations: BacktestValidationSummary[];
  selectedValidationId: number | null;
  selectedValidation: BacktestValidationDetail | null;
  compareRunIds: string;
  compareResult: BacktestCompareResponse | null;
  researchLoading: string;
  researchError: string;
  researchNotice: string;
  setMode: (mode: BacktestMode) => void;
  setStrategyOptions: (strategyOptions: StrategyOption[]) => void;
  setForm: (form: StateValue<BacktestFormState>) => void;
  setRuns: (runs: StateValue<BacktestRunSummary[]>) => void;
  setSelectedRun: (run: StateValue<BacktestRunDetail | null>) => void;
  setEquity: (equity: EquityPoint[]) => void;
  setTrades: (trades: BacktestTrade[]) => void;
  setLoading: (loading: string) => void;
  setError: (error: string) => void;
  setNotice: (notice: string) => void;
  setMonthlyReturns: (monthlyReturns: BacktestMonthlyReturnsResponse | null) => void;
  setAttribution: (attribution: BacktestAttributionResponse | null) => void;
  setCorrelation: (correlation: BacktestStrategyCorrelationResponse | null) => void;
  setOptimizationForm: (form: StateValue<OptimizationFormState>) => void;
  setOptimizations: (optimizations: StateValue<BacktestOptimizationSummary[]>) => void;
  setSelectedOptimizationId: (id: number | null) => void;
  setSelectedOptimization: (optimization: StateValue<BacktestOptimizationDetail | null>) => void;
  setValidationForm: (form: StateValue<ValidationFormState>) => void;
  setValidations: (validations: StateValue<BacktestValidationSummary[]>) => void;
  setSelectedValidationId: (id: number | null) => void;
  setSelectedValidation: (validation: StateValue<BacktestValidationDetail | null>) => void;
  setCompareRunIds: (compareRunIds: string) => void;
  setCompareResult: (compareResult: BacktestCompareResponse | null) => void;
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
  runs: [],
  selectedRun: null,
  equity: [],
  trades: [],
  loading: "",
  error: "",
  notice: "",
  monthlyReturns: null,
  attribution: null,
  correlation: null,
  optimizationForm: initialOptimizationForm,
  optimizations: [],
  selectedOptimizationId: null,
  selectedOptimization: null,
  validationForm: initialValidationForm,
  validations: [],
  selectedValidationId: null,
  selectedValidation: null,
  compareRunIds: "",
  compareResult: null,
  researchLoading: "",
  researchError: "",
  researchNotice: "",
  setMode: (mode) => set({ mode }),
  setStrategyOptions: (strategyOptions) => set({ strategyOptions }),
  setForm: (form) => set((state) => ({ form: typeof form === "function" ? form(state.form) : form })),
  setRuns: (runs) => set((state) => ({ runs: typeof runs === "function" ? runs(state.runs) : runs })),
  setSelectedRun: (selectedRun) => set((state) => ({
    selectedRun: typeof selectedRun === "function" ? selectedRun(state.selectedRun) : selectedRun,
  })),
  setEquity: (equity) => set({ equity }),
  setTrades: (trades) => set({ trades }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setNotice: (notice) => set({ notice }),
  setMonthlyReturns: (monthlyReturns) => set({ monthlyReturns }),
  setAttribution: (attribution) => set({ attribution }),
  setCorrelation: (correlation) => set({ correlation }),
  setOptimizationForm: (optimizationForm) => set((state) => ({
    optimizationForm: typeof optimizationForm === "function" ? optimizationForm(state.optimizationForm) : optimizationForm,
  })),
  setOptimizations: (optimizations) => set((state) => ({
    optimizations: typeof optimizations === "function" ? optimizations(state.optimizations) : optimizations,
  })),
  setSelectedOptimizationId: (selectedOptimizationId) => set({ selectedOptimizationId }),
  setSelectedOptimization: (selectedOptimization) => set((state) => ({
    selectedOptimization: typeof selectedOptimization === "function" ? selectedOptimization(state.selectedOptimization) : selectedOptimization,
  })),
  setValidationForm: (validationForm) => set((state) => ({
    validationForm: typeof validationForm === "function" ? validationForm(state.validationForm) : validationForm,
  })),
  setValidations: (validations) => set((state) => ({
    validations: typeof validations === "function" ? validations(state.validations) : validations,
  })),
  setSelectedValidationId: (selectedValidationId) => set({ selectedValidationId }),
  setSelectedValidation: (selectedValidation) => set((state) => ({
    selectedValidation: typeof selectedValidation === "function" ? selectedValidation(state.selectedValidation) : selectedValidation,
  })),
  setCompareRunIds: (compareRunIds) => set({ compareRunIds }),
  setCompareResult: (compareResult) => set({ compareResult }),
  setResearchLoading: (researchLoading) => set({ researchLoading }),
  setResearchError: (researchError) => set({ researchError }),
  setResearchNotice: (researchNotice) => set({ researchNotice }),
  bumpVerdictThresholdVersion: () => set((state) => ({ verdictThresholdVersion: state.verdictThresholdVersion + 1 })),
}));
