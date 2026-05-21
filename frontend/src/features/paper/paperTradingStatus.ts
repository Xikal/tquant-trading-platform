import type { PaperAccount, PaperAutoTradingStatus } from "../../types";
import type { MetricItem } from "../workspace-shared/workspaceTypes";

export function resolveAutoManagedStatus(
  account: PaperAccount | null,
  autoTradingStatus: PaperAutoTradingStatus | null,
): { label: string; tone: MetricItem["tone"] | "warn" } {
  if (!account) return { label: "--", tone: "neutral" };
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
