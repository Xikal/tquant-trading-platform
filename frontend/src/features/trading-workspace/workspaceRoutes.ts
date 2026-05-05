import { PATH_PAGE_MAP } from "./workspaceConstants";
import type { Page } from "./workspaceTypes";

const LEGACY_STRATEGY_PATHS = new Set(["/backtests", "/research"]);

export function pageFromLocation(): Page {
  if (typeof window === "undefined") {
    return "monitor";
  }
  return PATH_PAGE_MAP[window.location.pathname] ?? "monitor";
}

export function normalizeLegacyWorkspacePath(): boolean {
  if (typeof window === "undefined" || !LEGACY_STRATEGY_PATHS.has(window.location.pathname)) {
    return false;
  }
  const nextSearch = window.location.pathname === "/backtests" ? "?tab=backtest" : "?tab=replay";
  window.history.replaceState({}, "", `/strategy${nextSearch}`);
  return true;
}
