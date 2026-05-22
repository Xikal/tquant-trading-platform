import { create } from "zustand";
import type { LowBuyScreenerResult } from "../types";
import { DEFAULT_PLAYBOOK_STRATEGY } from "../features/workspace-shared/workspaceConstants";

interface WorkspacePlaybookStore {
  strategy: string;
  playbook: LowBuyScreenerResult | null;
  cache: Record<string, LowBuyScreenerResult>;
  setStrategy: (strategy: string) => void;
  setPlaybook: (playbook: LowBuyScreenerResult | null | ((current: LowBuyScreenerResult | null) => LowBuyScreenerResult | null)) => void;
  cachePlaybook: (strategy: string, playbook: LowBuyScreenerResult) => void;
  resetPlaybook: () => void;
}

export const useWorkspacePlaybookStore = create<WorkspacePlaybookStore>((set) => ({
  strategy: DEFAULT_PLAYBOOK_STRATEGY,
  playbook: null,
  cache: {},
  setStrategy: (strategy) => set((state) => ({
    strategy,
    playbook: state.cache[strategy] ?? null,
  })),
  setPlaybook: (playbook) => set((state) => ({
    playbook: typeof playbook === "function" ? playbook(state.playbook) : playbook,
  })),
  cachePlaybook: (strategy, playbook) => set((state) => ({
    cache: { ...state.cache, [strategy]: playbook },
    playbook,
  })),
  resetPlaybook: () => set({ playbook: null, cache: {} }),
}));
