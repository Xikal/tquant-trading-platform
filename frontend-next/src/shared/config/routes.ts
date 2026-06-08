export type NextPage =
  | "monitor"
  | "monitor-market"
  | "analysis"
  | "playbook"
  | "strategy-tracking"
  | "backtest"
  | "paper"
  | "data"
  | "settings";

export interface NextRoute {
  page: NextPage;
  label: string;
  shortLabel: string;
  path: string;
  legacyPath: string;
  commandIndex?: number;
}

export const nextRoutes: NextRoute[] = [
  { page: "monitor", label: "实时行动", shortLabel: "行动台", path: "/next/monitor", legacyPath: "/monitor", commandIndex: 1 },
  { page: "monitor-market", label: "市场环境", shortLabel: "市场页", path: "/next/monitor/market", legacyPath: "/monitor/market", commandIndex: 2 },
  { page: "analysis", label: "量化分析", shortLabel: "分析页", path: "/next/analysis", legacyPath: "/analysis", commandIndex: 3 },
  { page: "playbook", label: "选股宝典", shortLabel: "宝典页", path: "/next/playbook", legacyPath: "/playbook", commandIndex: 4 },
  { page: "strategy-tracking", label: "策略跟踪", shortLabel: "复盘页", path: "/next/strategy-tracking", legacyPath: "/strategy-tracking", commandIndex: 5 },
  { page: "backtest", label: "回测页", shortLabel: "回测页", path: "/next/backtest", legacyPath: "/backtest", commandIndex: 6 },
  { page: "paper", label: "模拟盘", shortLabel: "账户页", path: "/next/paper", legacyPath: "/paper", commandIndex: 7 },
  { page: "data", label: "数据中心", shortLabel: "数据页", path: "/next/data", legacyPath: "/data", commandIndex: 8 },
  { page: "settings", label: "系统配置", shortLabel: "配置页", path: "/next/settings", legacyPath: "/settings" },
];

export const nextRouteByPage = Object.fromEntries(nextRoutes.map((route) => [route.page, route])) as Record<NextPage, NextRoute>;

export const compatibilityRoutes = [
  { from: "/next/emotion", to: "/next/monitor" },
  { from: "/next/low-buy", to: "/next/playbook" },
  { from: "/next/strategy", to: "/next/backtest" },
  { from: "/next/performance", to: "/next/paper" },
] as const;
