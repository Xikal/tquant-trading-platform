import { create } from "zustand";
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
  batchSymbols: string;
  setDraft: (draft: AnalysisDraft | ((current: AnalysisDraft) => AnalysisDraft)) => void;
  setBatchSymbols: (symbols: string) => void;
}

export const useWorkspaceAnalysisStore = create<WorkspaceAnalysisStore>((set) => ({
  draft: DEFAULT_ANALYSIS_DRAFT,
  batchSymbols: "",
  setDraft: (draft) => set((state) => ({
    draft: typeof draft === "function" ? draft(state.draft) : draft,
  })),
  setBatchSymbols: (batchSymbols) => set({ batchSymbols }),
}));
