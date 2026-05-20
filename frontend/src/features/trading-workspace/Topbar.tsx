import { useEffect, useState } from "react";
import type { FocusEvent } from "react";
import type { AuthUser, LowBuyPriorityBoardResult } from "../../types";
import type { Page, StockCardView } from "./workspaceTypes";

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
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [pulse, setPulse] = useState(() => realTimePulse());
  const nav: Array<[Page, string]> = [
    ["monitor", "实时监控"],
    ["emotion", "市场情绪"],
    ["analysis", "量化分析"],
    ["playbook", "选股宝典"],
    ["strategy", "策略工作台"],
    ["paper", "模拟盘"],
  ];
  const riskCount = watchCards.filter((item) => item.riskText.includes("高")).length;
  const userName = currentUser.display_name || currentUser.username;

  useEffect(() => {
    const timer = window.setInterval(() => setPulse(realTimePulse()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  function closeUserMenuOnBlur(event: FocusEvent<HTMLDivElement>) {
    const nextTarget = event.relatedTarget;
    if (!nextTarget || !event.currentTarget.contains(nextTarget as Node)) {
      setUserMenuOpen(false);
    }
  }

  function openSettings() {
    setUserMenuOpen(false);
    setPage("settings");
  }

  function logout() {
    setUserMenuOpen(false);
    onLogout();
  }

  return (
    <header className={`topbar ${page === "monitor" ? "monitor-topbar" : "section-topbar"}`}>
      <div className="brand">
        <strong>维斯量化交易平台</strong>
      </div>
      <nav aria-label="主导航">
        {nav.map(([key, label]) => {
          const paperBlocked = key === "paper" && !currentUser.can_paper_trade;
          return (
            <button
              className={page === key ? "active" : ""}
              disabled={paperBlocked}
              onClick={() => setPage(key)}
              title={paperBlocked ? "模拟盘需申请白名单权限" : ""}
              key={key}
            >
              {paperBlocked ? "模拟盘需申请" : label}
            </button>
          );
        })}
      </nav>
      <div className="desk-chips">
        {page === "paper" && onPaperRefresh ? (
          <button type="button" className="topbar-refresh-card" onClick={onPaperRefresh} disabled={paperRefreshLoading}>
            {paperRefreshLoading ? "刷新中" : "刷新"}
          </button>
        ) : null}
        <span className="desk-chip opportunity"><small>机会</small><strong>{priorityBoard?.total_candidates ?? "--"}</strong></span>
        <span className="desk-chip risk"><small>风险</small><strong>{riskCount}</strong></span>
        <span className="desk-chip pulse"><small>脉冲</small><strong>{pulse}</strong></span>
        <div className="topbar-user-menu" onBlur={closeUserMenuOnBlur}>
          <button
            type="button"
            className={`topbar-user-button${page === "settings" ? " active" : ""}`}
            aria-haspopup="menu"
            aria-expanded={userMenuOpen}
            onClick={() => setUserMenuOpen((open) => !open)}
          >
            {userName}
          </button>
          {userMenuOpen ? (
            <div className="topbar-user-dropdown" role="menu">
              <button type="button" role="menuitem" onClick={openSettings}>
                系统配置
              </button>
              <button type="button" role="menuitem" onClick={logout}>
                退出登录
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function realTimePulse(): string {
  return new Date().toLocaleTimeString("zh-CN", {
    hour12: false,
    timeZone: "Asia/Shanghai",
  });
}
