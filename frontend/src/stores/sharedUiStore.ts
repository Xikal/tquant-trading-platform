import { create } from "zustand";
import type { SymbolSearchItem } from "../api/strategies";

export type ToastTone = "info" | "success" | "warning" | "error";

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  tone?: ToastTone;
  sticky?: boolean;
}

interface SymbolSearchState {
  items: SymbolSearchItem[];
  total: number;
  open: boolean;
  error: string;
}

interface SharedUiStore {
  symbolSearch: Record<string, SymbolSearchState>;
  toasts: ToastMessage[];
  setSymbolSearch: (key: string, patch: Partial<SymbolSearchState>) => void;
  resetSymbolSearch: (key: string) => void;
  addToast: (message: Omit<ToastMessage, "id">) => string;
  removeToast: (id: string) => void;
}

const EMPTY_SYMBOL_SEARCH: SymbolSearchState = {
  items: [],
  total: 0,
  open: false,
  error: "",
};

export const useSharedUiStore = create<SharedUiStore>((set) => ({
  symbolSearch: {},
  toasts: [],
  setSymbolSearch: (key, patch) => set((state) => ({
    symbolSearch: {
      ...state.symbolSearch,
      [key]: { ...(state.symbolSearch[key] ?? EMPTY_SYMBOL_SEARCH), ...patch },
    },
  })),
  resetSymbolSearch: (key) => set((state) => ({
    symbolSearch: {
      ...state.symbolSearch,
      [key]: { ...EMPTY_SYMBOL_SEARCH },
    },
  })),
  addToast: (message) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    set((state) => ({
      toasts: [{ ...message, id }, ...state.toasts].slice(0, 3),
    }));
    return id;
  },
  removeToast: (id) => set((state) => ({
    toasts: state.toasts.filter((item) => item.id !== id),
  })),
}));
