import { Badge, Button, Dropdown, Space, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
import type { AuthUser, LowBuyPriorityBoardResult } from "../../types";
import type { Page, StockCardView } from "../workspace-shared/workspaceTypes";

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
  const [pulse, setPulse] = useState(() => realTimePulse());
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
    const timer = window.setInterval(() => setPulse(realTimePulse()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <header className={`topbar ${page === "monitor" ? "monitor-topbar" : "section-topbar"}`}>
      <div className="brand">
        <Typography.Text strong>维斯量化交易平台</Typography.Text>
      </div>
      <nav className="topbar-nav" aria-label="主导航">
        {menuItems.map((item) => (
          <button
            key={item.key}
            type="button"
            className={page === item.key ? "active" : ""}
            disabled={item.disabled}
            title={item.title}
            aria-current={page === item.key ? "page" : undefined}
            onClick={() => setPage(item.key)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <Space className="desk-chips" size={10}>
        {page === "paper" && onPaperRefresh ? (
          <Button type="primary" size="small" onClick={onPaperRefresh} loading={paperRefreshLoading}>
            {paperRefreshLoading ? "刷新中" : "刷新"}
          </Button>
        ) : null}
        <Badge count={priorityBoard?.total_candidates ?? 0} showZero color="#d92d20">
          <span className="desk-chip opportunity"><small>机会</small></span>
        </Badge>
        <Badge count={riskCount} showZero color="#b42318">
          <span className="desk-chip risk"><small>风险</small></span>
        </Badge>
        <span className="desk-chip pulse"><small>脉冲</small><strong>{pulse}</strong></span>
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
          <Button className={page === "settings" ? "active" : ""}>
            {userName}
          </Button>
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
