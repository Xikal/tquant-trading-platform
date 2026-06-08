import type { NextPage, NextRoute } from "../shared/config/routes";
import { nextRoutes } from "../shared/config/routes";

export type LegacyNavIcon = "fund" | "line" | "read" | "aim" | "experiment" | "wallet" | "database" | "setting";

export interface LegacyNavItem extends NextRoute {
  icon: LegacyNavIcon;
}

const iconByPage: Record<NextPage, LegacyNavIcon> = {
  monitor: "fund",
  "monitor-market": "line",
  analysis: "line",
  playbook: "read",
  "strategy-tracking": "aim",
  backtest: "experiment",
  paper: "wallet",
  data: "database",
  settings: "setting",
};

export const legacyNavItems: LegacyNavItem[] = nextRoutes.map((route) => ({
  ...route,
  icon: iconByPage[route.page],
}));

export const legacyPageTitle: Record<NextPage, string> = {
  monitor: "实时行动台",
  "monitor-market": "市场环境台",
  analysis: "量化分析",
  playbook: "选股宝典",
  "strategy-tracking": "策略跟踪",
  backtest: "回测页",
  paper: "模拟盘",
  data: "数据中心",
  settings: "系统配置",
};
