import { create } from "zustand";
import type {
  AppBootstrapResponse,
  AppHomeResponse,
  AppLowBuyDetailResponse,
  AppWatchlistResponse,
  LowBuyPriorityBoardResult,
} from "../types";

export type AppPreviewTab = "home" | "low_buy";

type StateValue<T> = T | ((current: T) => T);

interface AppPreviewStore {
  bootstrap: AppBootstrapResponse | null;
  home: AppHomeResponse | null;
  watchlist: AppWatchlistResponse | null;
  priorityBoard: LowBuyPriorityBoardResult | null;
  activeTab: AppPreviewTab;
  loading: boolean;
  tabLoading: boolean;
  detailLoading: boolean;
  actionLoading: boolean;
  detail: AppLowBuyDetailResponse | null;
  error: string;
  message: string;
  pulseTime: string;
  priorityPulseTime: string;
  setBootstrap: (value: AppBootstrapResponse | null) => void;
  setHome: (value: StateValue<AppHomeResponse | null>) => void;
  setWatchlist: (value: StateValue<AppWatchlistResponse | null>) => void;
  setPriorityBoard: (value: LowBuyPriorityBoardResult | null) => void;
  setActiveTab: (value: AppPreviewTab) => void;
  setLoading: (value: boolean) => void;
  setTabLoading: (value: boolean) => void;
  setDetailLoading: (value: boolean) => void;
  setActionLoading: (value: boolean) => void;
  setDetail: (value: StateValue<AppLowBuyDetailResponse | null>) => void;
  setError: (value: string) => void;
  setMessage: (value: string) => void;
  setPulseTime: (value: string) => void;
  setPriorityPulseTime: (value: string) => void;
}

export const useAppPreviewStore = create<AppPreviewStore>((set) => ({
  bootstrap: null,
  home: null,
  watchlist: null,
  priorityBoard: null,
  activeTab: "home",
  loading: true,
  tabLoading: false,
  detailLoading: false,
  actionLoading: false,
  detail: null,
  error: "",
  message: "",
  pulseTime: "--",
  priorityPulseTime: "--",
  setBootstrap: (bootstrap) => set({ bootstrap }),
  setHome: (home) => set((state) => ({ home: typeof home === "function" ? home(state.home) : home })),
  setWatchlist: (watchlist) => set((state) => ({
    watchlist: typeof watchlist === "function" ? watchlist(state.watchlist) : watchlist,
  })),
  setPriorityBoard: (priorityBoard) => set({ priorityBoard }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setLoading: (loading) => set({ loading }),
  setTabLoading: (tabLoading) => set({ tabLoading }),
  setDetailLoading: (detailLoading) => set({ detailLoading }),
  setActionLoading: (actionLoading) => set({ actionLoading }),
  setDetail: (detail) => set((state) => ({ detail: typeof detail === "function" ? detail(state.detail) : detail })),
  setError: (error) => set({ error }),
  setMessage: (message) => set({ message }),
  setPulseTime: (pulseTime) => set({ pulseTime }),
  setPriorityPulseTime: (priorityPulseTime) => set({ priorityPulseTime }),
}));
