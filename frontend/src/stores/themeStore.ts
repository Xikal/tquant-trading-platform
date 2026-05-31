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
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

function applyMode(mode: ThemeMode) {
  if (typeof document !== "undefined") {
    document.documentElement.dataset.theme = mode;
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
