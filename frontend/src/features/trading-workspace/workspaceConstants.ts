import type { Page } from "./workspaceTypes";
import { FALLBACK_STRATEGY_META } from "../../constants/strategies";

export const DEFAULT_PLAYBOOK_STRATEGY = "first_board";

export const CORE_PLAYBOOK_TABS = FALLBACK_STRATEGY_META.filter((item) => item.tier === "core");

export const AUXILIARY_PLAYBOOK_TABS = FALLBACK_STRATEGY_META.filter((item) => item.tier === "auxiliary");

export const RESEARCH_PLAYBOOK_TABS = [
  { key: "limit_up_breakout_retrace", label: "涨停突破回踩", tier: "research" },
  { key: "divergence_consensus", label: "分歧转一致", tier: "research" },
  { key: "classic_retrace", label: "原始低吸", tier: "research" },
  { key: "ma_support", label: "均线支撑", tier: "factor" },
  { key: "breakout_support", label: "位置支撑", tier: "factor" },
  { key: "deep_pullback", label: "深度低吸", tier: "factor" },
  { key: "trend_rebound", label: "趋势龙回头", tier: "factor" },
] as const;

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
