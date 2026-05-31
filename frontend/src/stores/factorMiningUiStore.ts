import { create } from "zustand";

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
  activation: Record<string, boolean>;
  activationSaving: Record<string, boolean>;
  loading: string;
  hypothesisLoading: string;
  error: string;
  hypothesisError: string;
  setSelectedKey: (selectedKey: string) => void;
  setHypothesisTopic: (topic: string) => void;
  setUseLlm: (useLlm: boolean) => void;
  setDraft: (draft: FactorDraft) => void;
  setActivation: (activation: Record<string, boolean> | ((current: Record<string, boolean>) => Record<string, boolean>)) => void;
  setActivationSaving: (factorKey: string, saving: boolean) => void;
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
  activation: {},
  activationSaving: {},
  loading: "load",
  hypothesisLoading: "",
  error: "",
  hypothesisError: "",
  setSelectedKey: (selectedKey) => set({ selectedKey }),
  setHypothesisTopic: (hypothesisTopic) => set({ hypothesisTopic }),
  setUseLlm: (useLlm) => set({ useLlm }),
  setDraft: (draft) => set({ draft }),
  setActivation: (activation) => set((state) => ({
    activation: typeof activation === "function" ? activation(state.activation) : activation,
  })),
  setActivationSaving: (factorKey, saving) => set((state) => ({
    activationSaving: { ...state.activationSaving, [factorKey]: saving },
  })),
  setLoading: (loading) => set({ loading }),
  setHypothesisLoading: (hypothesisLoading) => set({ hypothesisLoading }),
  setError: (error) => set({ error }),
  setHypothesisError: (hypothesisError) => set({ hypothesisError }),
}));
