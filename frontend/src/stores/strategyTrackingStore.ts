import { create } from "zustand";

export type StrategyTrackingTab = "active" | "gain" | "risk" | "performance" | "holding" | "diagnostics";
export type StrategyTrackingViewMode = "beginner" | "professional";

interface StrategyTrackingStore {
  tab: StrategyTrackingTab;
  viewMode: StrategyTrackingViewMode;
  range: number;
  strategyKey: string;
  strategyFamily: string;
  signalState: string;
  lifecycleStatus: string;
  dataQuality: string;
  hitEntry: string;
  stopped: string;
  userStatus: string;
  excludeChinext: boolean;
  excludeStar: boolean;
  boardFilter: "include_all" | "main_only";
  sort: string;
  page: number;
  pageSize: number;
  selectedItemId: string | null;
  setTab: (tab: StrategyTrackingTab) => void;
  setViewMode: (viewMode: StrategyTrackingViewMode) => void;
  setRange: (range: number) => void;
  setStrategyKey: (strategyKey: string) => void;
  setStrategyFamily: (strategyFamily: string) => void;
  setSignalState: (signalState: string) => void;
  setLifecycleStatus: (lifecycleStatus: string) => void;
  setDataQuality: (dataQuality: string) => void;
  setHitEntry: (hitEntry: string) => void;
  setStopped: (stopped: string) => void;
  setUserStatus: (userStatus: string) => void;
  setExcludeChinext: (excludeChinext: boolean) => void;
  setExcludeStar: (excludeStar: boolean) => void;
  setBoardFilter: (boardFilter: "include_all" | "main_only") => void;
  setSort: (sort: string) => void;
  setPagination: (page: number, pageSize: number) => void;
  setSelectedItemId: (selectedItemId: string | null) => void;
}

const resetPage = { page: 1 };

export const useStrategyTrackingStore = create<StrategyTrackingStore>((set) => ({
  tab: "active",
  viewMode: "beginner",
  range: 30,
  strategyKey: "",
  strategyFamily: "",
  signalState: "",
  lifecycleStatus: "",
  dataQuality: "",
  hitEntry: "",
  stopped: "",
  userStatus: "",
  excludeChinext: true,
  excludeStar: true,
  boardFilter: "include_all",
  sort: "max_gain_desc",
  page: 1,
  pageSize: 30,
  selectedItemId: null,
  setTab: (tab) => set({ tab, sort: sortForTab(tab), ...resetPage }),
  setViewMode: (viewMode) =>
    set({
      viewMode,
      excludeChinext: viewMode === "beginner",
      excludeStar: viewMode === "beginner",
      ...resetPage,
    }),
  setRange: (range) => set({ range, ...resetPage }),
  setStrategyKey: (strategyKey) => set({ strategyKey, ...resetPage }),
  setStrategyFamily: (strategyFamily) => set({ strategyFamily, ...resetPage }),
  setSignalState: (signalState) => set({ signalState, ...resetPage }),
  setLifecycleStatus: (lifecycleStatus) => set({ lifecycleStatus, ...resetPage }),
  setDataQuality: (dataQuality) => set({ dataQuality, ...resetPage }),
  setHitEntry: (hitEntry) => set({ hitEntry, ...resetPage }),
  setStopped: (stopped) => set({ stopped, ...resetPage }),
  setUserStatus: (userStatus) => set({ userStatus, ...resetPage }),
  setExcludeChinext: (excludeChinext) => set({ excludeChinext, ...resetPage }),
  setExcludeStar: (excludeStar) => set({ excludeStar, ...resetPage }),
  setBoardFilter: (boardFilter) => set({ boardFilter, ...resetPage }),
  setSort: (sort) => set({ sort, ...resetPage }),
  setPagination: (page, pageSize) => set({ page, pageSize }),
  setSelectedItemId: (selectedItemId) => set({ selectedItemId }),
}));

function sortForTab(tab: StrategyTrackingTab): string {
  if (tab === "risk") return "risk_desc";
  if (tab === "active") return "latest_desc";
  if (tab === "holding") return "best_holding_desc";
  if (tab === "performance") return "max_gain_desc";
  return "max_gain_desc";
}
