import { Button } from "antd";
import type { IntradayMarketPulse, LowBuyPriorityBoardResult } from "../../types";
import { ConclusionBar } from "../../ui/surfaces";
import type { MarketReviewStatus } from "../../types";
import { formatRatioPct, resolveTodayAction } from "./MonitorPage.helpers";
import type { StockCardView } from "../workspace-shared/workspaceTypes";

export function MonitorConclusionBar({
  marketBreadthState,
  marketPulse,
  priorityBoard,
  priorityCards,
  reviewStatus,
  watchCards,
  onOpenHoldingDrawer,
  onRefresh,
  onSync,
}: {
  marketBreadthState: string | null;
  marketPulse: IntradayMarketPulse | null;
  priorityBoard: LowBuyPriorityBoardResult | null;
  priorityCards: StockCardView[];
  reviewStatus: MarketReviewStatus | null;
  watchCards: StockCardView[];
  onOpenHoldingDrawer: () => void;
  onRefresh: () => void;
  onSync: () => void;
}) {
  const primaryAction = resolveTodayAction(watchCards, priorityCards, priorityBoard);
  const observeCount = (priorityBoard?.focus_count ?? 0) + (priorityBoard?.track_count ?? 0);
  const riskCount = watchCards.filter((card) => card.riskText.includes("高")).length;
  const opportunityValue = `可买 ${priorityBoard?.immediate_count ?? 0} / 观察 ${observeCount}`;
  const riskValue = `高风险 ${riskCount}`;
  const marketValue = priorityBoard?.market_state_text || marketBreadthState || marketPulse?.pulse_text || "等待刷新";

  return (
    <ConclusionBar
      title="实时监控"
      summary={`${primaryAction.title} · ${primaryAction.detail}`}
      actions={(
        <>
          <Button type="primary" onClick={onOpenHoldingDrawer}>+ 录入持仓</Button>
          <Button onClick={onRefresh}>手动刷新</Button>
          <Button onClick={onSync}>更新股票库（较慢）</Button>
        </>
      )}
      items={[
        {
          key: "opportunity",
          label: "今日机会",
          value: opportunityValue,
          tone: priorityBoard?.immediate_count ? "up" : "warn",
          helper: reviewStatus?.status_text || "首屏先看可买和观察分布。",
        },
        {
          key: "risk",
          label: "持仓风险",
          value: riskValue,
          tone: riskCount ? "down" : "neutral",
          helper: `${priorityBoard?.market_gate_decision || "市场门控"} · ${formatRatioPct(priorityBoard?.market_firepower_multiplier)}`,
        },
        {
          key: "market",
          label: "大盘状态",
          value: marketValue,
          tone: marketPulse?.pulse_level === "strong" || marketPulse?.pulse_level === "risk_on" ? "up" : marketPulse?.pulse_level === "weak" || marketPulse?.pulse_level === "risk_off" ? "down" : "neutral",
          helper: marketPulse?.suggested_action || "Pulse 与门控只做观察提醒。",
        },
      ]}
    />
  );
}
