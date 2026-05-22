import { create } from "zustand";
import type { AnalysisResponse, IntradayAnomalyResponse } from "../types";
import type { AnalysisDraft } from "../features/workspace-shared/workspaceTypes";

const DEFAULT_ANALYSIS_DRAFT: AnalysisDraft = {
  symbol: "510300",
  prefer_strategy: "auto",
  base_position: "3000",
  available_position: "3000",
  cost_basis: "",
};

interface WorkspaceAnalysisStore {
  draft: AnalysisDraft;
  result: AnalysisResponse | null;
  anomaly: IntradayAnomalyResponse | null;
  batchSymbols: string;
  batchResults: AnalysisResponse[];
  setDraft: (draft: AnalysisDraft | ((current: AnalysisDraft) => AnalysisDraft)) => void;
  setResult: (result: AnalysisResponse | null) => void;
  setAnomaly: (anomaly: IntradayAnomalyResponse | null) => void;
  setBatchSymbols: (symbols: string) => void;
  setBatchResults: (results: AnalysisResponse[]) => void;
}

export const useWorkspaceAnalysisStore = create<WorkspaceAnalysisStore>((set) => ({
  draft: DEFAULT_ANALYSIS_DRAFT,
  result: null,
  anomaly: null,
  batchSymbols: "",
  batchResults: [],
  setDraft: (draft) => set((state) => ({
    draft: typeof draft === "function" ? draft(state.draft) : draft,
  })),
  setResult: (result) => set({ result }),
  setAnomaly: (anomaly) => set({ anomaly }),
  setBatchSymbols: (batchSymbols) => set({ batchSymbols }),
  setBatchResults: (batchResults) => set({ batchResults }),
}));
