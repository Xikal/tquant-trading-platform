import { create } from "zustand";
import type { AiDecisionSupportResponse, AuthUser } from "../types";
import type { StrategyMeta } from "../api/strategies";
import type { AuthDraft, Page, StockCardView, WatchDraft } from "../features/workspace-shared/workspaceTypes";

interface WorkspaceStore {
  page: Page;
  authDraft: AuthDraft;
  watchDraft: WatchDraft;
  editingWatchSymbol: string;
  commandQuery: string;
  authReady: boolean;
  currentUser: AuthUser | null;
  notice: string;
  error: string;
  commandOpen: boolean;
  aiDialogOpen: boolean;
  selectedStock: StockCardView | null;
  aiResult: AiDecisionSupportResponse | null;
  commandStrategies: StrategyMeta[];
  strategyMeta: StrategyMeta[];
  topbarPulse: string;
  setPage: (page: Page) => void;
  setAuthDraft: (draft: AuthDraft | ((current: AuthDraft) => AuthDraft)) => void;
  setWatchDraft: (draft: WatchDraft | ((current: WatchDraft) => WatchDraft)) => void;
  setEditingWatchSymbol: (symbol: string) => void;
  setCommandQuery: (query: string) => void;
  setAuthReady: (ready: boolean) => void;
  setCurrentUser: (user: AuthUser | null) => void;
  setNotice: (notice: string) => void;
  setError: (error: string) => void;
  setCommandOpen: (open: boolean) => void;
  setAiDialogOpen: (open: boolean) => void;
  setSelectedStock: (stock: StockCardView | null) => void;
  setAiResult: (result: AiDecisionSupportResponse | null) => void;
  setCommandStrategies: (strategies: StrategyMeta[]) => void;
  setStrategyMeta: (strategies: StrategyMeta[]) => void;
  setTopbarPulse: (pulse: string) => void;
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
  currentUser: null,
  notice: "",
  error: "",
  commandOpen: false,
  aiDialogOpen: false,
  selectedStock: null,
  aiResult: null,
  commandStrategies: [],
  strategyMeta: [],
  topbarPulse: new Date().toLocaleTimeString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" }),
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
  setCurrentUser: (currentUser) => set({ currentUser }),
  setNotice: (notice) => set({ notice }),
  setError: (error) => set({ error }),
  setCommandOpen: (commandOpen) => set({ commandOpen }),
  setAiDialogOpen: (aiDialogOpen) => set({ aiDialogOpen }),
  setSelectedStock: (selectedStock) => set({ selectedStock }),
  setAiResult: (aiResult) => set({ aiResult }),
  setCommandStrategies: (commandStrategies) => set({ commandStrategies }),
  setStrategyMeta: (strategyMeta) => set({ strategyMeta }),
  setTopbarPulse: (topbarPulse) => set({ topbarPulse }),
  clearTransientUi: () => set({ aiDialogOpen: false, commandOpen: false, selectedStock: null, error: "" }),
}));
