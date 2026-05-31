import { Badge, Button, Dropdown, Grid, Space, Typography } from "antd";
import { MenuOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import { useThemeStore } from "../../stores/themeStore";
import type { AuthUser, LowBuyPriorityBoardResult } from "../../types";
import { RitualLuckyDraw, useRitualPreference } from "../ritual-ui";
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
  onPaperRefresh,
  paperRefreshLoading = false,
}: {
  page: Page;
  currentUser: AuthUser;
  priorityBoard: LowBuyPriorityBoardResult | null;
  watchCards: StockCardView[];
  onLogout: () => void;
  onNavigate: (page: Page) => void;
  onOpenNav: () => void;
  onPaperRefresh?: () => void;
  paperRefreshLoading?: boolean;
}) {
  const pulse = useWorkspaceStore((state) => state.topbarPulse);
  const setTopbarPulse = useWorkspaceStore((state) => state.setTopbarPulse);
  const screens = useBreakpoint();
  const ritual = useRitualPreference();
  const themeMode = useThemeStore((state) => state.mode);
  const toggleTheme = useThemeStore((state) => state.toggleMode);
  const isMobile = !screens.lg;
  const riskCount = watchCards.filter((item) => item.riskText.includes("高")).length;
  const userName = currentUser.display_name || currentUser.username;

  useEffect(() => {
    const timer = window.setInterval(() => setTopbarPulse(realTimePulse()), 1000);
    return () => window.clearInterval(timer);
  }, [setTopbarPulse]);

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
      </div>
      <Space style={TOPBAR_RIGHT_STYLE} size={8}>
        {page === "paper" && onPaperRefresh ? (
          <Button type="primary" size="small" onClick={onPaperRefresh} loading={paperRefreshLoading}>
            {paperRefreshLoading ? "刷新中" : "刷新"}
          </Button>
        ) : null}
        <Badge count={priorityBoard?.total_candidates ?? 0} showZero color="var(--mkt-up)">
          <span style={TOPBAR_CHIP_STYLE}>机会</span>
        </Badge>
        <Badge count={riskCount} showZero color="var(--error)">
          <span style={TOPBAR_CHIP_STYLE}>风险</span>
        </Badge>
        {screens.xl ? (
          <span style={TOPBAR_CHIP_STYLE}>脉冲<strong style={TOPBAR_CHIP_VALUE_STYLE}>{pulse}</strong></span>
        ) : null}
        <RitualLuckyDraw enabled={ritual.enabled} compact />
        <Dropdown
          menu={{
            items: [
              { key: "theme-toggle", label: themeMode === "dark" ? "切换浅色模式" : "切换深色模式" },
              { key: "ritual-toggle", label: ritual.enabled ? "关闭红运仪式" : "开启红运仪式" },
              { key: "settings", label: "系统配置" },
              { key: "logout", label: "退出登录", danger: true },
            ],
            onClick: ({ key }) => {
              if (key === "logout") {
                onLogout();
                return;
              }
              if (key === "theme-toggle") {
                toggleTheme();
                return;
              }
              if (key === "ritual-toggle") {
                ritual.setEnabled(!ritual.enabled);
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
