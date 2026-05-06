import type { Page } from "./workspaceTypes";
import { FALLBACK_STRATEGY_META } from "../../constants/strategies";

export const DEFAULT_PLAYBOOK_STRATEGY = "first_board";

const isFullEnabledStrategy = (item: (typeof FALLBACK_STRATEGY_META)[number]) =>
  item.enabled !== false && item.visibility === "full";

export const CORE_PLAYBOOK_TABS = FALLBACK_STRATEGY_META.filter(
  (item) => isFullEnabledStrategy(item) && item.tier === "core"
);

export const AUXILIARY_PLAYBOOK_TABS = FALLBACK_STRATEGY_META.filter(
  (item) => isFullEnabledStrategy(item) && item.tier === "auxiliary"
);

export const RESEARCH_PLAYBOOK_TABS = FALLBACK_STRATEGY_META.filter(
  (item) => isFullEnabledStrategy(item) && (item.tier === "research" || item.tier === "factor")
);

export const PRODUCTION_PLAYBOOK_TABS = [
  ...CORE_PLAYBOOK_TABS,
  ...AUXILIARY_PLAYBOOK_TABS,
] as const;

export const ALL_PLAYBOOK_TABS = [
  ...CORE_PLAYBOOK_TABS,
  ...AUXILIARY_PLAYBOOK_TABS,
  ...RESEARCH_PLAYBOOK_TABS,
] as const;

export const PAGE_PATHS: Record<Page, string> = {
  monitor: "/",
  analysis: "/analysis",
  playbook: "/low-buy",
  strategy: "/strategy",
  research: "/research",
  backtests: "/backtests",
  paper: "/paper",
  performance: "/performance",
  settings: "/settings",
};

export const PATH_PAGE_MAP: Record<string, Page> = {
  "/": "monitor",
  "/analysis": "analysis",
  "/low-buy": "playbook",
  "/strategy": "strategy",
  "/research": "strategy",
  "/backtests": "strategy",
  "/paper": "paper",
  "/performance": "performance",
  "/settings": "settings",
};

export const MONITOR_REFRESH_INTERVAL_MS = 10_000;
export const PLAYBOOK_QUOTE_REFRESH_INTERVAL_MS = 15_000;
export const PLAYBOOK_QUOTE_REFRESH_LIMIT = 60;
