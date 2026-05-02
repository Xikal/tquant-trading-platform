import type { AuthUser, LowBuyPriorityBoardResult } from "../../types";
import { shortTime } from "./workspaceFormatters";
import type { Page, StockCardView } from "./workspaceTypes";

export function Topbar({
  page,
  setPage,
  priorityBoard,
  watchCards,
  currentUser,
  onLogout,
}: {
  page: Page;
  setPage: (page: Page) => void;
  priorityBoard: LowBuyPriorityBoardResult | null;
  watchCards: StockCardView[];
  currentUser: AuthUser;
  onLogout: () => void;
}) {
  const nav: Array<[Page, string]> = [
    ["monitor", "实时监控"],
    ["analysis", "量化分析"],
    ["playbook", "选股宝典"],
    ["research", "研究复盘"],
    ["paper", "模拟盘"],
    ["settings", "系统配置"],
  ];
  const riskCount = watchCards.filter((item) => item.riskText.includes("高")).length;
  const pulse = shortTime(priorityBoard?.updated_at) || new Date().toLocaleTimeString("zh-CN", { hour12: false, timeZone: "Asia/Shanghai" });
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
        <span>{currentUser.display_name || currentUser.username}</span>
        <span>机会 {priorityBoard?.total_candidates ?? "--"}</span>
        <span>风险 {riskCount}</span>
        <span>脉冲 {pulse}</span>
        <button type="button" className="topbar-logout" onClick={onLogout}>退出</button>
      </div>
    </header>
  );
}
