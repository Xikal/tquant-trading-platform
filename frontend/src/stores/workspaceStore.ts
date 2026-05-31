import { create } from "zustand";
import type { AuthDraft, Page, StockCardView, WatchDraft } from "../features/workspace-shared/workspaceTypes";

interface WorkspaceStore {
  page: Page;
  authDraft: AuthDraft;
  watchDraft: WatchDraft;
  editingWatchSymbol: string;
  commandQuery: string;
  authReady: boolean;
  notice: string;
  error: string;
  commandOpen: boolean;
  aiDialogOpen: boolean;
  selectedStock: StockCardView | null;
  topbarPulse: string;
  sidebarCollapsed: boolean;
  mobileNavOpen: boolean;
  setPage: (page: Page) => void;
  setAuthDraft: (draft: AuthDraft | ((current: AuthDraft) => AuthDraft)) => void;
  setWatchDraft: (draft: WatchDraft | ((current: WatchDraft) => WatchDraft)) => void;
  setEditingWatchSymbol: (symbol: string) => void;
  setCommandQuery: (query: string) => void;
  setAuthReady: (ready: boolean) => void;
  setNotice: (notice: string) => void;
  setError: (error: string) => void;
  setCommandOpen: (open: boolean) => void;
  setAiDialogOpen: (open: boolean) => void;
  setSelectedStock: (stock: StockCardView | null) => void;
  setTopbarPulse: (pulse: string) => void;
  toggleSidebarCollapsed: () => void;
  setMobileNavOpen: (open: boolean) => void;
  clearTransientUi: () => void;
}

export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  page: "monitor",
  authDraft: {
    username: "",
    password: "",
    remember: true,
  },
  watchDraft: {
    symbol: "",
    name: "",
    base_position: "0",
    available_position: "0",
    cost_basis: "",
    memo: "",
  },
  editingWatchSymbol: "",
  commandQuery: "",
  authReady: false,
  notice: "",
  error: "",
  commandOpen: false,
  aiDialogOpen: false,
  selectedStock: null,
  topbarPulse: new Date().toLocaleTimeString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" }),
  sidebarCollapsed: false,
  mobileNavOpen: false,
  setPage: (page) => set({ page }),
  setAuthDraft: (draft) => set((state) => ({
    authDraft: typeof draft === "function" ? draft(state.authDraft) : draft,
  })),
  setWatchDraft: (draft) => set((state) => ({
    watchDraft: typeof draft === "function" ? draft(state.watchDraft) : draft,
  })),
  setEditingWatchSymbol: (editingWatchSymbol) => set({ editingWatchSymbol }),
  setCommandQuery: (commandQuery) => set({ commandQuery }),
  setAuthReady: (authReady) => set({ authReady }),
  setNotice: (notice) => set({ notice }),
  setError: (error) => set({ error }),
  setCommandOpen: (commandOpen) => set({ commandOpen }),
  setAiDialogOpen: (aiDialogOpen) => set({ aiDialogOpen }),
  setSelectedStock: (selectedStock) => set({ selectedStock }),
  setTopbarPulse: (topbarPulse) => set({ topbarPulse }),
  toggleSidebarCollapsed: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
  clearTransientUi: () => set({ aiDialogOpen: false, commandOpen: false, selectedStock: null, error: "", mobileNavOpen: false }),
}));
