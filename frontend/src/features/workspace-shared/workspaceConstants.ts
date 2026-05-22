import { FALLBACK_STRATEGY_META } from "../../constants/strategies";
import type { Page } from "./workspaceTypes";

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

export const OBSERVATION_PLAYBOOK_KEYS = new Set<string>();

export const OBSERVATION_PLAYBOOK_TABS = [] as const;

export const PRODUCTION_PLAYBOOK_TABS = [
  ...CORE_PLAYBOOK_TABS,
  ...AUXILIARY_PLAYBOOK_TABS,
] as const;

export const WEB_PLAYBOOK_TABS = [
  ...PRODUCTION_PLAYBOOK_TABS,
] as const;

export const ALL_PLAYBOOK_TABS = [
  ...CORE_PLAYBOOK_TABS,
  ...AUXILIARY_PLAYBOOK_TABS,
  ...RESEARCH_PLAYBOOK_TABS,
] as const;

export const PAGE_PATHS: Record<Page, string> = {
  monitor: "/monitor",
  emotion: "/emotion",
  analysis: "/analysis",
  playbook: "/playbook",
  strategy: "/strategy",
  paper: "/paper",
  settings: "/settings",
};

export const PATH_PAGE_MAP: Record<string, Page> = {
  "/": "monitor",
  "/monitor": "monitor",
  "/emotion": "emotion",
  "/analysis": "analysis",
  "/low-buy": "playbook",
  "/playbook": "playbook",
  "/strategy": "strategy",
  "/paper": "paper",
  "/performance": "paper",
  "/settings": "settings",
};

export const MONITOR_REFRESH_INTERVAL_MS = 20_000;
export const PLAYBOOK_QUOTE_REFRESH_INTERVAL_MS = 15_000;
export const PLAYBOOK_QUOTE_REFRESH_LIMIT = 60;
