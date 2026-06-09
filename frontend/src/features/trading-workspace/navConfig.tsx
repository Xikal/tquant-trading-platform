import {
  AimOutlined,
  DatabaseOutlined,
  FundOutlined,
  LineChartOutlined,
  ReadOutlined,
  SettingOutlined,
  WalletOutlined,
} from "../../ui/icons";
import type { ReactNode } from "react";
import type { AuthUser } from "../../types";
import { isAdmin } from "../shared/strategyPermissions";
import type { Page } from "../workspace-shared/workspaceTypes";

export interface NavItem {
  key: Page;
  label: string;
  icon: ReactNode;
}

/** 侧边栏主导航（与原顶栏横排一致的 6 项）。 */
export const PRIMARY_NAV: NavItem[] = [
  { key: "monitor", label: "实时行动", icon: <FundOutlined /> },
  { key: "monitor-market", label: "市场环境", icon: <LineChartOutlined /> },
  { key: "analysis", label: "量化分析", icon: <LineChartOutlined /> },
  { key: "playbook", label: "选股宝典", icon: <ReadOutlined /> },
  { key: "strategy-tracking", label: "策略跟踪", icon: <AimOutlined /> },
  { key: "paper", label: "模拟盘", icon: <WalletOutlined /> },
];

export const DATA_NAV: NavItem = { key: "data", label: "数据中心", icon: <DatabaseOutlined /> };

/** 系统配置单列底部。 */
export const SETTINGS_NAV: NavItem = { key: "settings", label: "系统配置", icon: <SettingOutlined /> };

const TITLES: Record<Page, string> = {
  monitor: "实时行动台",
  "monitor-market": "市场环境台",
  analysis: "量化分析",
  playbook: "选股宝典",
  "strategy-tracking": "策略跟踪",
  paper: "模拟盘",
  data: "数据中心",
  settings: "系统配置",
};

export function pageTitle(page: Page): string {
  return TITLES[page] ?? "维斯量化交易平台";
}

export function visiblePrimaryNav(user: AuthUser): NavItem[] {
  return isAdmin(user) ? [...PRIMARY_NAV, DATA_NAV] : PRIMARY_NAV;
}
