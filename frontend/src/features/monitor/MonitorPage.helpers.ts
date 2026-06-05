import type { LowBuyPriorityBoardResult } from "../../types";
import { directActionTitle } from "../../utils/uxClarity";
import { average, shortTime } from "../workspace-shared/workspaceFormatters";
import type { MetricItem, StockCardView } from "../workspace-shared/workspaceTypes";

export function buildMonitorMetrics({
  priorityBoard,
  priorityCards,
  watchCards,
}: {
  priorityBoard: LowBuyPriorityBoardResult | null;
  priorityCards: StockCardView[];
  watchCards: StockCardView[];
}): MetricItem[] {
  const executableCount = watchCards.filter((card) => card.actionText !== "暂不操作").length;
  const avgScore = average(priorityCards.map((card) => Number(card.scoreText))).toFixed(1);
  return [
    { label: "已持仓自选", value: String(watchCards.length), tone: "neutral" },
    { label: "今天可操作", value: String(executableCount), tone: executableCount ? "up" : "neutral" },
    { label: "需要避险", value: String(watchCards.filter((card) => card.riskText.includes("高")).length), tone: "down" },
    { label: "平均质量分", value: Number.isFinite(Number(avgScore)) ? avgScore : "--", tone: "warn" },
    { label: "生产榜 / 刷新", value: `${priorityBoard?.items.length ?? 0} / ${shortTime(priorityBoard?.updated_at) || "--"}`, tone: "neutral" },
  ];
}

export function buildBoardDistribution(boardHeight: number): Array<{ label: string; height: number }> {
  const current = Math.max(0, Math.min(6, Math.round(boardHeight || 0)));
  return ["1板", "2板", "3板", "4板", "5+"].map((label, index) => ({
    label,
    height: Math.max(12, index + 1 <= current ? 28 + index * 14 : 12),
  }));
}

export function dataQualityTone(value?: string | null): "up" | "warn" | "down" | "neutral" {
  if (value === "ok") return "up";
  if (value === "partial" || value === "stale" || value === "degraded") return "warn";
  if (value === "limited" || value === "unavailable") return "down";
  return "neutral";
}

export function formatRatioPct(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const normalized = Math.abs(value) <= 1 ? value * 100 : value;
  return `${normalized.toFixed(0)}%`;
}

export function resolveTodayAction(
  watchCards: StockCardView[],
  priorityCards: StockCardView[],
  priorityBoard: LowBuyPriorityBoardResult | null,
): { title: string; detail: string; tone: "up" | "warn" | "neutral"; source: "holding" | "priority" | "none" } {
  const actionableHolding = watchCards.find((card) => card.actionText !== "暂不操作");
  if (actionableHolding) {
    return {
      title: `${actionableHolding.name}：${directActionTitle(actionableHolding.actionText)}`,
      detail: actionableHolding.executionHint || actionableHolding.details || "按卡片价格区间执行，失效条件触发就不做。",
      tone: "up",
      source: "holding",
    };
  }
  const immediateCount = priorityBoard?.immediate_count ?? countConfirmedBuyItems(priorityBoard);
  const observeCount = (priorityBoard?.focus_count ?? 0) + (priorityBoard?.track_count ?? 0);
  if (priorityBoard && immediateCount <= 0) {
    const market = priorityBoard.market_state_text || priorityBoard.daily_decision?.market_plain_text || "当前市场";
    if ((priorityBoard.total_candidates ?? 0) <= 0 && !isPriorityBoardRefreshing(priorityBoard)) {
      return {
        title: "当前无生产买入信号",
        detail: `${market}，生产层候选未同时满足买点、承接、风控和交易范围；研究观察只做提醒，不能当作买入建议。`,
        tone: "warn",
        source: "priority",
      };
    }
    return {
      title: "当前无确认买入",
      detail: observeCount > 0
        ? `${market}，系统仅保留 ${observeCount} 只观察票，不能当作买入建议。`
        : `${market}，没有股票同时满足买点、承接和风控条件。`,
      tone: "warn",
      source: "priority",
    };
  }
  const priority = priorityCards[0];
  if (priority) {
    return {
      title: `${priority.name}：${directActionTitle(priority.actionText)}`,
      detail: priority.details || "先看买点区和止损位，不满足承接确认就等待。",
      tone: "warn",
      source: "priority",
    };
  }
  return { title: "今天先不动", detail: "暂无明确可执行信号，等待榜单或持仓信号刷新。", tone: "neutral", source: "none" };
}

export function buildPriorityNotice(
  priorityBoard: LowBuyPriorityBoardResult | null,
  visibleCount: number,
): { title: string; detail: string; tone: "warn" | "danger" } | null {
  if (!priorityBoard || countConfirmedBuyItems(priorityBoard) > 0) {
    return null;
  }
  const observeCount = (priorityBoard.focus_count ?? 0) + (priorityBoard.track_count ?? 0);
  const blockedMarket = priorityBoard.market_state === "risk_release" || priorityBoard.market_state === "high_flyer_retreat";
  const marketText = priorityBoard.market_state_text || priorityBoard.daily_decision?.market_plain_text || "当前市场";
  if ((priorityBoard.total_candidates ?? 0) <= 0 && !isPriorityBoardRefreshing(priorityBoard)) {
    return {
      title: "当前无生产买入信号",
      detail: blockedMarket
        ? `${marketText}，生产层候选已被买点、风险或交易范围过滤；这不是后台没刷新，研究观察也不能当作买入建议。`
        : "生产层没有股票同时满足价格区间、承接确认、风控和交易范围；研究观察只用于提醒，不进入生产买入排序。",
      tone: blockedMarket ? "danger" : "warn",
    };
  }
  if (blockedMarket) {
    return {
      title: "当前无确认买入：市场风控已收紧",
      detail: `${marketText}，系统已把弱主线、承接不足或风险偏高的股票降为放弃，仅展示 ${observeCount || visibleCount} 只观察候选。`,
      tone: "danger",
    };
  }
  return {
    title: "当前无确认买入",
    detail: observeCount > 0
      ? `当前只有 ${observeCount} 只观察候选，需要等价格进入买点区并完成承接确认后才会升级。`
      : "当前没有股票同时满足价格区间、承接确认和风控条件。",
    tone: "warn",
  };
}

export function buildPriorityEmptyText(priorityBoard: LowBuyPriorityBoardResult | null): string {
  if (!priorityBoard || isPriorityBoardRefreshing(priorityBoard)) {
    return "生产优先榜正在后台刷新，稍后自动更新。";
  }
  if ((priorityBoard.total_candidates ?? 0) <= 0) {
    return "当前无生产买入信号：候选未同时满足买点、承接、风控和交易范围；研究观察只做提醒。";
  }
  return "当前视图暂无可展示股票，请切换策略线或手动刷新。";
}

export function shouldShowPrioritySnapshotWarning(
  priorityBoard: LowBuyPriorityBoardResult | null,
  visibleCount: number,
): boolean {
  const warning = priorityBoard?.snapshot_warning?.trim() ?? "";
  if (!warning || visibleCount <= 0) {
    return false;
  }
  return !(
    warning.includes("后台刷新")
    || warning.includes("刷新任务已排队")
    || warning.includes("已排队")
  );
}

function isPriorityBoardRefreshing(priorityBoard: LowBuyPriorityBoardResult): boolean {
  const warning = priorityBoard.snapshot_warning || "";
  return (
    !priorityBoard.latest_trade_date
    || warning.includes("后台刷新")
    || warning.includes("刷新任务已排队")
  );
}

function countConfirmedBuyItems(priorityBoard: LowBuyPriorityBoardResult | null): number {
  return (priorityBoard?.items ?? []).filter((item) => (
    item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now"
  )).length;
}
