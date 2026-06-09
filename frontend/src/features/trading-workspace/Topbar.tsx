import { Badge, Button, Dropdown, Grid, Segmented, Space, Typography } from "antd";
import { useEffect } from "react";
import { useSignals } from "@preact/signals-react/runtime";
import { frontendPerformanceFlagEnabled } from "../../config/frontendPerformanceFlags";
import { topbarPulseSignal, updateTopbarPulse } from "../../state/realtime/topbarClockSignal";
import { MenuOutlined } from "../../ui/icons";
import type { AuthUser, LowBuyPriorityBoardResult } from "../../types";
import type { Page, StockCardView } from "../workspace-shared/workspaceTypes";
import { pageTitle } from "./navConfig";
import {
  TOPBAR_CHIP_STYLE,
  TOPBAR_CHIP_VALUE_STYLE,
  TOPBAR_ICON_BTN_STYLE,
  TOPBAR_LEFT_STYLE,
  TOPBAR_RIGHT_STYLE,
  TOPBAR_STYLE,
  TOPBAR_TITLE_STYLE,
} from "./workspaceShellStyles";

const { useBreakpoint } = Grid;

export function Topbar({
  page,
  currentUser,
  priorityBoard,
  watchCards,
  onLogout,
  onNavigate,
  onOpenNav,
}: {
  page: Page;
  currentUser: AuthUser;
  priorityBoard: LowBuyPriorityBoardResult | null;
  watchCards: StockCardView[];
  onLogout: () => void;
  onNavigate: (page: Page) => void;
  onOpenNav: () => void;
}) {
  useSignals();
  const pulse = topbarPulseSignal.value;
  const screens = useBreakpoint();
  const isMobile = !screens.lg;
  const riskCount = watchCards.filter((item) => item.riskText.includes("高")).length;
  const opportunityCount = priorityBoard?.total_candidates ?? priorityBoard?.items.length ?? 0;
  const userName = currentUser.display_name || currentUser.username;
  const showMonitorSwitch = page === "monitor" || page === "monitor-market";

  useEffect(() => {
    if (!topbarRealtimePulseEnabled()) {
      return undefined;
    }
    const timer = window.setInterval(() => updateTopbarPulse(realTimePulse()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <header style={TOPBAR_STYLE}>
      <div style={TOPBAR_LEFT_STYLE}>
        {isMobile ? (
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={onOpenNav}
            aria-label="打开导航菜单"
            style={TOPBAR_ICON_BTN_STYLE}
          />
        ) : null}
        <Typography.Text strong style={TOPBAR_TITLE_STYLE}>{pageTitle(page)}</Typography.Text>
        {showMonitorSwitch ? (
          <Segmented
            size="small"
            value={page}
            options={[
              { label: "实时行动", value: "monitor" },
              { label: "市场环境", value: "monitor-market" },
            ]}
            onChange={(value) => onNavigate(value as Page)}
          />
        ) : null}
      </div>
      <Space style={TOPBAR_RIGHT_STYLE} size={8}>
        <Badge count={opportunityCount} showZero color="var(--mkt-up)">
          <span style={TOPBAR_CHIP_STYLE}>机会</span>
        </Badge>
        <Badge count={riskCount} showZero color="var(--error)">
          <span style={TOPBAR_CHIP_STYLE}>风险</span>
        </Badge>
        {screens.xl ? (
          <span style={TOPBAR_CHIP_STYLE}>脉冲<strong style={TOPBAR_CHIP_VALUE_STYLE}>{pulse}</strong></span>
        ) : null}
        <Dropdown
          menu={{
            items: [
              { key: "settings", label: "系统配置" },
              { key: "logout", label: "退出登录", danger: true },
            ],
            onClick: ({ key }) => {
              if (key === "logout") {
                onLogout();
                return;
              }
              onNavigate("settings");
            },
          }}
          trigger={["click"]}
        >
          <Button type={page === "settings" ? "primary" : "default"}>{userName}</Button>
        </Dropdown>
      </Space>
    </header>
  );
}

function realTimePulse(): string {
  return new Date().toLocaleTimeString("zh-CN", {
    hour12: false,
    timeZone: "Asia/Shanghai",
  });
}

export function topbarRealtimePulseEnabled(): boolean {
  return frontendPerformanceFlagEnabled("frontend_realtime_signals_island_enabled");
}
