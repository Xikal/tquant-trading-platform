import type { CSSProperties } from "react";
import { Badge, Button, Dropdown, Grid, Space, Typography } from "antd";
import { useEffect, useMemo } from "react";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import type { AuthUser, LowBuyPriorityBoardResult } from "../../types";
import type { Page, StockCardView } from "../workspace-shared/workspaceTypes";
import {
  TOPBAR_BRAND_STYLE,
  TOPBAR_BRAND_TEXT_STYLE,
  TOPBAR_CHIP_LABEL_STYLE,
  TOPBAR_CHIPS_STYLE,
  TOPBAR_NAV_ACTIVE_STYLE,
  TOPBAR_NAV_BUTTON_STYLE,
  TOPBAR_NAV_SECTION_ACTIVE_STYLE,
  TOPBAR_NAV_STACKED_STYLE,
  TOPBAR_NAV_STYLE,
  TOPBAR_OPPORTUNITY_CHIP_STYLE,
  TOPBAR_PULSE_CHIP_STYLE,
  TOPBAR_PULSE_VALUE_STYLE,
  TOPBAR_RISK_CHIP_STYLE,
  topbarStyle,
} from "./workspaceShellStyles";

const { useBreakpoint } = Grid;

export function Topbar({
  page,
  setPage,
  priorityBoard,
  watchCards,
  currentUser,
  onLogout,
  onPaperRefresh,
  paperRefreshLoading = false,
}: {
  page: Page;
  setPage: (page: Page) => void;
  priorityBoard: LowBuyPriorityBoardResult | null;
  watchCards: StockCardView[];
  currentUser: AuthUser;
  onLogout: () => void;
  onPaperRefresh?: () => void;
  paperRefreshLoading?: boolean;
}) {
  const pulse = useWorkspaceStore((state) => state.topbarPulse);
  const setTopbarPulse = useWorkspaceStore((state) => state.setTopbarPulse);
  const screens = useBreakpoint();
  const stacked = !screens.lg;
  const nav: Array<[Page, string]> = useMemo(() => [
    ["monitor", "实时监控"],
    ["emotion", "市场情绪"],
    ["analysis", "量化分析"],
    ["playbook", "选股宝典"],
    ["strategy", "策略工作台"],
    ["paper", "模拟盘"],
  ], []);
  const riskCount = watchCards.filter((item) => item.riskText.includes("高")).length;
  const userName = currentUser.display_name || currentUser.username;
  const menuItems = nav.map(([key, label]) => {
    const paperDisabled = key === "paper" && !currentUser.can_paper_trade;
    return {
      key,
      label: paperDisabled ? "模拟盘需申请" : label,
      disabled: paperDisabled,
      title: paperDisabled ? "模拟盘需申请白名单权限" : "",
    };
  });

  useEffect(() => {
    const timer = window.setInterval(() => setTopbarPulse(realTimePulse()), 1000);
    return () => window.clearInterval(timer);
  }, [setTopbarPulse]);

  return (
    <header style={topbarStyle(stacked)}>
      <div style={TOPBAR_BRAND_STYLE}>
        <Typography.Text strong style={TOPBAR_BRAND_TEXT_STYLE}>维斯量化交易平台</Typography.Text>
      </div>
      <nav style={{ ...TOPBAR_NAV_STYLE, ...(stacked ? TOPBAR_NAV_STACKED_STYLE : undefined) }} aria-label="主导航">
        {menuItems.map((item) => (
          <Button
            key={item.key}
            htmlType="button"
            size="small"
            style={navButtonStyle(page, item.key)}
            disabled={item.disabled}
            title={item.title}
            aria-current={page === item.key ? "page" : undefined}
            onClick={() => setPage(item.key)}
          >
            {item.label}
          </Button>
        ))}
      </nav>
      <Space style={TOPBAR_CHIPS_STYLE} size={10}>
        {page === "paper" && onPaperRefresh ? (
          <Button type="primary" size="small" onClick={onPaperRefresh} loading={paperRefreshLoading}>
            {paperRefreshLoading ? "刷新中" : "刷新"}
          </Button>
        ) : null}
        <Badge count={priorityBoard?.total_candidates ?? 0} showZero color="#d92d20">
          <span style={TOPBAR_OPPORTUNITY_CHIP_STYLE}><small style={TOPBAR_CHIP_LABEL_STYLE}>机会</small></span>
        </Badge>
        <Badge count={riskCount} showZero color="#b42318">
          <span style={TOPBAR_RISK_CHIP_STYLE}><small style={TOPBAR_CHIP_LABEL_STYLE}>风险</small></span>
        </Badge>
        <span style={TOPBAR_PULSE_CHIP_STYLE}><small style={TOPBAR_CHIP_LABEL_STYLE}>脉冲</small><strong style={TOPBAR_PULSE_VALUE_STYLE}>{pulse}</strong></span>
        <Dropdown
          menu={{
            items: [
              { key: "settings", label: "系统配置" },
              { key: "logout", label: "退出登录", danger: true },
            ],
            onClick: ({ key }) => (key === "logout" ? onLogout() : setPage("settings")),
          }}
          trigger={["click"]}
        >
          <Button type={page === "settings" ? "primary" : "default"}>
            {userName}
          </Button>
        </Dropdown>
      </Space>
    </header>
  );
}

function navButtonStyle(currentPage: Page, itemKey: string): CSSProperties {
  if (currentPage !== itemKey) {
    return TOPBAR_NAV_BUTTON_STYLE;
  }
  return {
    ...TOPBAR_NAV_BUTTON_STYLE,
    ...(currentPage === "monitor" ? TOPBAR_NAV_ACTIVE_STYLE : TOPBAR_NAV_SECTION_ACTIVE_STYLE),
  };
}

function realTimePulse(): string {
  return new Date().toLocaleTimeString("zh-CN", {
    hour12: false,
    timeZone: "Asia/Shanghai",
  });
}
