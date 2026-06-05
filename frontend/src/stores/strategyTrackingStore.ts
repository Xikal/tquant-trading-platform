import { create } from "zustand";

export type StrategyTrackingAnalysisTab = "performance" | "holding" | "drift" | "diagnostics" | "review-workspace" | "trade-review" | "trade-journal" | "relative-strength";
export type StrategyTrackingTab = "active" | "gain" | "risk" | StrategyTrackingAnalysisTab;
export type StrategyTrackingViewMode = "beginner" | "professional";
export type StrategyTrackingLane = "" | "baseline" | "front_row_weighted" | "front_row_only";
export type StrategyTrackingSummaryGroup = "overview" | "analysis";

interface StrategyTrackingStore {
  tab: StrategyTrackingTab;
  overviewTab: "active" | "gain" | "risk";
  analysisTab: StrategyTrackingAnalysisTab;
  viewMode: StrategyTrackingViewMode;
  summaryGroup: StrategyTrackingSummaryGroup;
  filtersDrawerOpen: boolean;
  range: number;
  strategyKey: string;
  strategyVariant: StrategyTrackingLane;
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
  reviewWorkspaceSelectedKey: string | null;
  setTab: (tab: StrategyTrackingTab) => void;
  setOverviewTab: (tab: "active" | "gain" | "risk") => void;
  setAnalysisTab: (tab: StrategyTrackingAnalysisTab) => void;
  setViewMode: (viewMode: StrategyTrackingViewMode) => void;
  setSummaryGroup: (summaryGroup: StrategyTrackingSummaryGroup) => void;
  setFiltersDrawerOpen: (open: boolean) => void;
  setRange: (range: number) => void;
  setStrategyKey: (strategyKey: string) => void;
  setStrategyVariant: (strategyVariant: StrategyTrackingLane) => void;
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
  setReviewWorkspaceSelectedKey: (reviewWorkspaceSelectedKey: string | null) => void;
}

const resetPage = { page: 1 };

export const useStrategyTrackingStore = create<StrategyTrackingStore>((set) => ({
  tab: "active",
  overviewTab: "active",
  analysisTab: "diagnostics",
  viewMode: "beginner",
  summaryGroup: "overview",
  filtersDrawerOpen: false,
  range: 30,
  strategyKey: "",
  strategyVariant: "",
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
  reviewWorkspaceSelectedKey: null,
  setTab: (tab) => set({
    tab,
    ...(isOverviewTab(tab) ? { overviewTab: tab, summaryGroup: "overview" as const } : { analysisTab: tab as StrategyTrackingStore["analysisTab"], summaryGroup: "analysis" as const }),
    sort: sortForTab(tab),
    page: resetPage.page,
  }),
  setOverviewTab: (overviewTab) => set({
    tab: overviewTab,
    overviewTab,
    summaryGroup: "overview",
    sort: sortForTab(overviewTab),
    ...resetPage,
  }),
  setAnalysisTab: (analysisTab) => set({
    analysisTab,
    summaryGroup: "analysis",
  }),
  setViewMode: (viewMode) =>
    set({
      viewMode,
      excludeChinext: viewMode === "beginner",
      excludeStar: viewMode === "beginner",
      ...resetPage,
    }),
  setSummaryGroup: (summaryGroup) => set({ summaryGroup }),
  setFiltersDrawerOpen: (filtersDrawerOpen) => set({ filtersDrawerOpen }),
  setRange: (range) => set({ range, ...resetPage }),
  setStrategyKey: (strategyKey) => set({ strategyKey, ...resetPage }),
  setStrategyVariant: (strategyVariant) => set({ strategyVariant, ...resetPage }),
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
  setReviewWorkspaceSelectedKey: (reviewWorkspaceSelectedKey) => set({ reviewWorkspaceSelectedKey }),
}));

function sortForTab(tab: StrategyTrackingTab): string {
  if (tab === "risk") return "risk_desc";
  if (tab === "active") return "latest_desc";
  if (tab === "holding") return "best_holding_desc";
  if (tab === "drift") return "max_gain_desc";
  if (tab === "performance") return "max_gain_desc";
  return "max_gain_desc";
}

function isOverviewTab(tab: StrategyTrackingTab): tab is "active" | "gain" | "risk" {
  return tab === "active" || tab === "gain" || tab === "risk";
}
