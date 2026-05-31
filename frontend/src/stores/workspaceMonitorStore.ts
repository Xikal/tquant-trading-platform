import { create } from "zustand";
import type { StrategyVariant } from "../types";

interface WorkspaceMonitorStore {
  activeStrategyLane: StrategyVariant;
  activeFamilyDetailKey: string;
  setActiveStrategyLane: (value: StrategyVariant) => void;
  setActiveFamilyDetailKey: (value: string) => void;
  resetMonitorData: () => void;
}

export const useWorkspaceMonitorStore = create<WorkspaceMonitorStore>((set) => ({
  activeStrategyLane: "baseline",
  activeFamilyDetailKey: "",
  setActiveStrategyLane: (activeStrategyLane) => set({ activeStrategyLane }),
  setActiveFamilyDetailKey: (activeFamilyDetailKey) => set({ activeFamilyDetailKey }),
  resetMonitorData: () => set({
    activeStrategyLane: "baseline",
    activeFamilyDetailKey: "",
  }),
}));
