import { create } from "zustand";

export type ThemeMode = "light" | "dark";

const STORAGE_KEY = "tq-theme-mode";

function readInitialMode(): ThemeMode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") {
      return saved;
    }
  } catch {
    /* localStorage 不可用时忽略 */
  }
  // Phase 5 暗色模式仅保留结构，当前 Web 端态固定浅色，不跟随系统自动上线。
  return "light";
}

function applyMode(mode: ThemeMode) {
  if (typeof document !== "undefined") {
    if (mode === "dark") {
      document.documentElement.dataset.theme = "dark";
    } else {
      delete document.documentElement.dataset.theme;
    }
  }
}

interface ThemeStore {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  toggleMode: () => void;
}

export const useThemeStore = create<ThemeStore>((set, get) => {
  const mode = readInitialMode();
  applyMode(mode);
  return {
    mode,
    setMode: (next) => {
      applyMode(next);
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* 持久化失败时忽略 */
      }
      set({ mode: next });
    },
    toggleMode: () => get().setMode(get().mode === "dark" ? "light" : "dark"),
  };
});
