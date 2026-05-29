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
