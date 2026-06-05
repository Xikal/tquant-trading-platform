import { useCallback } from "react";
import { api } from "../../api/client";
import type { components } from "../../generated/api-types";
import type { LowBuyPriorityBoardResult } from "../../types";
import type { MonitorWorkspaceBffResponse as LegacyMonitorWorkspaceBffResponse } from "../../types";
import { errorMessage } from "../workspace-shared/workspaceFormatters";

export type MonitorWorkspaceBffPayload = components["schemas"]["MonitorWorkspaceBffResponse"];
export type MonitorWorkspaceData = LegacyMonitorWorkspaceBffResponse;
export type MonitorWorkspaceView = "full" | "action" | "market";

export interface MonitorPriorityParityItem {
  symbol: string;
  priority_score: number | null;
  production_score: number | null;
  buy_signal_state: string;
  elite_watch_score: number | null;
}

export function useMonitorWorkspaceBff(
  fetchWorkspace: (priorityLimit?: number, view?: MonitorWorkspaceView) => Promise<MonitorWorkspaceData> = api.getMonitorWorkspaceBff,
) {
  const fetchMonitorWorkspace = useCallback(createMonitorWorkspaceFetcher(fetchWorkspace), [fetchWorkspace]);

  return {
    aggregateEnabled: monitorBffAggregateEnabled(),
    fetchMonitorWorkspace,
  };
}

export function createMonitorWorkspaceFetcher(
  fetchWorkspace: (priorityLimit?: number, view?: MonitorWorkspaceView) => Promise<MonitorWorkspaceData>,
) {
  return (priorityLimit = 12, view: MonitorWorkspaceView = "full") => fetchWorkspace(priorityLimit, view);
}

export function monitorBffAggregateEnabled(): boolean {
  return import.meta.env.VITE_MONITOR_BFF_AGGREGATE_ENABLED !== "false";
}

export function isMonitorBffDisabled(reason: unknown): boolean {
  const status = (reason as { status?: number } | null)?.status;
  return status === 404 && errorMessage(reason).includes("monitor BFF aggregate disabled");
}

export function monitorPriorityBoardParityProjection(
  board: { items?: Array<Record<string, unknown>> } | null | undefined,
): MonitorPriorityParityItem[] {
  return (board?.items ?? []).map((item) => ({
    symbol: typeof item.symbol === "string" ? item.symbol : "",
    priority_score: numberOrNull(item.priority_score),
    production_score: numberOrNull(item.production_score),
    buy_signal_state: typeof item.buy_signal_state === "string" ? item.buy_signal_state : "",
    elite_watch_score: numberOrNull(item.elite_watch_score),
  }));
}

export function stableMonitorPriorityParityPayload(
  board: { items?: Array<Record<string, unknown>> } | null | undefined,
): string {
  return JSON.stringify(monitorPriorityBoardParityProjection(board));
}

export function shouldFallbackMonitorPriorityBoard(
  workspace: Pick<MonitorWorkspaceData, "monitor_snapshot"> | null | undefined,
): boolean {
  return (workspace?.monitor_snapshot?.priority_board?.items ?? []).length <= 0;
}

export function fetchMonitorPriorityBoardFallback(
  workspace: Pick<MonitorWorkspaceData, "monitor_snapshot"> | null | undefined,
  fetchPriorityBoard: (
    limit: number,
    strategyVariant: "baseline",
    refresh: "cache",
  ) => Promise<LowBuyPriorityBoardResult>,
): Promise<LowBuyPriorityBoardResult | null> {
  if (!shouldFallbackMonitorPriorityBoard(workspace)) {
    return Promise.resolve(null);
  }
  return fetchPriorityBoard(12, "baseline", "cache");
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
