import { create } from "zustand";
import type { StrategyVariant } from "../types";

export type MonitorMoreTab = "etf" | "review" | "snapshot";

interface WorkspaceMonitorStore {
  activeStrategyLane: StrategyVariant;
  activeFamilyDetailKey: string;
  holdingDrawerOpen: boolean;
  moreTab: MonitorMoreTab;
  setActiveStrategyLane: (value: StrategyVariant) => void;
  setActiveFamilyDetailKey: (value: string) => void;
  setHoldingDrawerOpen: (value: boolean) => void;
  setMoreTab: (value: MonitorMoreTab) => void;
  resetMonitorData: () => void;
}

export const useWorkspaceMonitorStore = create<WorkspaceMonitorStore>((set) => ({
  activeStrategyLane: "baseline",
  activeFamilyDetailKey: "",
  holdingDrawerOpen: false,
  moreTab: "etf",
  setActiveStrategyLane: (activeStrategyLane) => set({ activeStrategyLane }),
  setActiveFamilyDetailKey: (activeFamilyDetailKey) => set({ activeFamilyDetailKey }),
  setHoldingDrawerOpen: (holdingDrawerOpen) => set({ holdingDrawerOpen }),
  setMoreTab: (moreTab) => set({ moreTab }),
  resetMonitorData: () => set({
    activeStrategyLane: "baseline",
    activeFamilyDetailKey: "",
    holdingDrawerOpen: false,
    moreTab: "etf",
  }),
}));
