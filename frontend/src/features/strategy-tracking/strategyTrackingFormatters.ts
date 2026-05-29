import type { StrategyTrackingItem, StrategyTrackingParams } from "../../types";
import { formatPct, formatPrice } from "../workspace-shared/workspaceFormatters";

export function entryZoneText(item: StrategyTrackingItem): string {
  if (item.entry_zone_low == null || item.entry_zone_high == null) {
    return "--";
  }
  return `${formatPrice(item.entry_zone_low)} ~ ${formatPrice(item.entry_zone_high)}`;
}

export function trackingTone(value?: number | null): "success" | "error" | "warning" | "default" {
  if (typeof value !== "number" || !Number.isFinite(value)) return "default";
  if (value > 0) return "success";
  if (value < -3) return "error";
  return "warning";
}

export function boolParam(value: string): boolean | null {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

export function tabParams(tab: string): Pick<StrategyTrackingParams, "status" | "stopped"> {
  if (tab === "active") return { status: "active" };
  if (tab === "risk") return { stopped: true };
  return {};
}

export function displayReturn(value?: number | null): string {
  return formatPct(value, 2);
}

export function holdingBucketText(value: string): string {
  const labels: Record<string, string> = {
    short_1_3d: "短线1-3天",
    swing_4_10d: "波段4-10天",
    trend_11_30d: "趋势11-30天",
    midlong_31_120d: "中长31-120天",
    unavailable: "暂无持有窗口",
  };
  return labels[value] || value || "暂无持有窗口";
}

export function exitQualityTone(value: string): "success" | "error" | "warning" | "default" {
  if (value === "excellent" || value === "acceptable") return "success";
  if (value === "drawdown_excessive" || value === "no_profit") return "error";
  if (value === "late_exit") return "warning";
  return "default";
}

export function holdExtensionTone(value: string): "success" | "error" | "warning" | "default" {
  if (value === "qualified") return "success";
  if (value === "risk_off" || value === "not_qualified") return "error";
  if (value === "watch") return "warning";
  return "default";
}

export function suggestedPlanText(value: string): string {
  const labels: Record<string, string> = {
    short_take_profit: "短线止盈",
    swing_hold: "波段持有",
    trend_hold: "趋势持有",
    midlong_hold: "中长线观察",
    exit_review: "退出复盘",
    unavailable: "暂无建议",
  };
  return labels[value] || value || "暂无建议";
}
