import type { PaperAccount, PaperAutoTradingStatus, PaperTrade } from "../../types";
import type { MetricItem } from "../workspace-shared/workspaceTypes";

export function resolveAutoManagedStatus(
  account: PaperAccount | null,
  autoTradingStatus: PaperAutoTradingStatus | null,
): { label: string; tone: MetricItem["tone"] | "warn" } {
  if (!account) return { label: "--", tone: "neutral" };
  if (paperAccountNeedsResume(account, autoTradingStatus)) return { label: "暂停新增委托", tone: "warn" };
  if (autoTradingStatus?.circuit_open) return { label: "熔断保护", tone: "warn" };
  if (autoTradingStatus?.trading_time) {
    return autoTradingStatus.running
      ? { label: "自动交易中", tone: "down" }
      : { label: "等待自动启动", tone: "warn" };
  }
  return { label: "非交易时段静默", tone: "neutral" };
}

export function autoTradingSkipNotice(
  autoTradingStatus: PaperAutoTradingStatus | null,
): { title: string; text: string; time?: string; tone: "warn" | "neutral" } | null {
  if (!autoTradingStatus) return null;
  const blockingReason = String(autoTradingStatus.blocking_reason || "").trim();
  if (blockingReason) {
    return { title: "未买原因", text: blockingReason, time: autoTradingStatus.last_skip_at, tone: "warn" };
  }
  const skipReason = String(autoTradingStatus.last_skip_reason || "").trim();
  if (!skipReason) return null;
  const symbol = String(autoTradingStatus.last_skip_symbol || "").trim();
  return {
    title: "最近跳过",
    text: symbol ? `${symbol}：${skipReason}` : skipReason,
    time: autoTradingStatus.last_skip_at,
    tone: "neutral",
  };
}

export function paperAccountNeedsResume(
  account: PaperAccount | null,
  autoTradingStatus: PaperAutoTradingStatus | null,
) {
  return account?.status === "paused"
    || autoTradingStatus?.account_status === "paused"
    || Boolean(String(autoTradingStatus?.blocking_reason || "").trim());
}

export interface PaperTradingPageStatusInput {
  account: PaperAccount | null;
  autoTradingStatus: PaperAutoTradingStatus | null;
  trades: PaperTrade[];
  loading: string;
  tradingExperienceFlags?: Record<string, boolean>;
}

export interface PaperTradingPageStatus {
  needsResumeOrder: boolean;
  paused: boolean;
  paperLoading: boolean;
  orderLoading: boolean;
  autoTradingRunning: boolean;
  holdingEnabled: boolean;
  tTradeEnabled: boolean;
  lastOrderAction: { type: "buy" | "sell"; symbol: string; timestamp: number } | null;
}

export function buildPaperTradingPageStatus(input: PaperTradingPageStatusInput): PaperTradingPageStatus {
  const flags = input.tradingExperienceFlags ?? {};
  const needsResumeOrder = paperAccountNeedsResume(input.account, input.autoTradingStatus);
  return {
    needsResumeOrder,
    paused: needsResumeOrder,
    paperLoading: input.loading === "paper",
    orderLoading: input.loading === "paper-order",
    autoTradingRunning: Boolean(input.autoTradingStatus?.running),
    holdingEnabled: Boolean(flags.trading_experience_suite_enabled && flags.holding_discipline_assistant_enabled),
    tTradeEnabled: Boolean(flags.trading_experience_suite_enabled && flags.t_trade_discipline_enabled),
    lastOrderAction: buildLastOrderAction(input.trades),
  };
}

function buildLastOrderAction(trades: PaperTrade[]): PaperTradingPageStatus["lastOrderAction"] {
  const latestTrade = trades[0];
  if (!latestTrade) return null;
  const timestamp = Date.parse(latestTrade.trade_time);
  if (!Number.isFinite(timestamp)) return null;
  return {
    type: latestTrade.side === "sell" ? "sell" : "buy",
    symbol: latestTrade.symbol,
    timestamp,
  };
}
