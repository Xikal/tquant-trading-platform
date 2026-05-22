import { create } from "zustand";
import type {
  FactorDefinition,
  FactorEvalResult,
  FactorHealthItem,
  FactorHypothesis,
} from "../api/factorMining";

export interface FactorDraft {
  key: string;
  name: string;
  hypothesis: string;
  code: string;
}

interface FactorMiningUiState {
  selectedKey: string;
  hypothesisTopic: string;
  useLlm: boolean;
  draft: FactorDraft;
  factors: FactorDefinition[];
  healthItems: FactorHealthItem[];
  activation: Record<string, boolean>;
  activationSaving: Record<string, boolean>;
  result: FactorEvalResult | null;
  hypothesisItems: FactorHypothesis[];
  loading: string;
  hypothesisLoading: string;
  error: string;
  hypothesisError: string;
  setSelectedKey: (selectedKey: string) => void;
  setHypothesisTopic: (topic: string) => void;
  setUseLlm: (useLlm: boolean) => void;
  setDraft: (draft: FactorDraft) => void;
  setFactors: (factors: FactorDefinition[] | ((current: FactorDefinition[]) => FactorDefinition[])) => void;
  setHealthItems: (healthItems: FactorHealthItem[]) => void;
  setActivation: (activation: Record<string, boolean> | ((current: Record<string, boolean>) => Record<string, boolean>)) => void;
  setActivationSaving: (factorKey: string, saving: boolean) => void;
  setResult: (result: FactorEvalResult | null) => void;
  setHypothesisItems: (items: FactorHypothesis[]) => void;
  setLoading: (loading: string) => void;
  setHypothesisLoading: (loading: string) => void;
  setError: (error: string) => void;
  setHypothesisError: (error: string) => void;
}

const EMPTY_DRAFT: FactorDraft = {
  key: "",
  name: "",
  hypothesis: "",
  code: "",
};

export const useFactorMiningUiStore = create<FactorMiningUiState>((set) => ({
  selectedKey: "",
  hypothesisTopic: "量价结构与板块接力",
  useLlm: true,
  draft: EMPTY_DRAFT,
  factors: [],
  healthItems: [],
  activation: {},
  activationSaving: {},
  result: null,
  hypothesisItems: [],
  loading: "load",
  hypothesisLoading: "",
  error: "",
  hypothesisError: "",
  setSelectedKey: (selectedKey) => set({ selectedKey }),
  setHypothesisTopic: (hypothesisTopic) => set({ hypothesisTopic }),
  setUseLlm: (useLlm) => set({ useLlm }),
  setDraft: (draft) => set({ draft }),
  setFactors: (factors) => set((state) => ({
    factors: typeof factors === "function" ? factors(state.factors) : factors,
  })),
  setHealthItems: (healthItems) => set({ healthItems }),
  setActivation: (activation) => set((state) => ({
    activation: typeof activation === "function" ? activation(state.activation) : activation,
  })),
  setActivationSaving: (factorKey, saving) => set((state) => ({
    activationSaving: { ...state.activationSaving, [factorKey]: saving },
  })),
  setResult: (result) => set({ result }),
  setHypothesisItems: (hypothesisItems) => set({ hypothesisItems }),
  setLoading: (loading) => set({ loading }),
  setHypothesisLoading: (hypothesisLoading) => set({ hypothesisLoading }),
  setError: (error) => set({ error }),
  setHypothesisError: (hypothesisError) => set({ hypothesisError }),
}));
