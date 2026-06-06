import type { MonitorWorkspaceData, MonitorWorkspaceView } from "./useMonitorWorkspaceBff";
import { fetchMonitorPriorityBoardFallback, isMonitorBffDisabled } from "./useMonitorWorkspaceBff";
import type { Page } from "../workspace-shared/workspaceTypes";
import type { LowBuyPriorityBoardResult, RuntimeStatus } from "../../types";

export type MonitorFirstScreenLoadSource = "bff" | "legacy";

export interface MonitorFirstScreenLoadResult {
  source: MonitorFirstScreenLoadSource;
  workspace?: MonitorWorkspaceData;
  legacy?: unknown;
  priorityBoardFallback?: LowBuyPriorityBoardResult | null;
  fallbackResults: PromiseSettledResult<unknown>[];
}

export interface MonitorFirstScreenLoadOptions {
  page: Page;
  priorityLimit: number;
  includeRuntime: boolean;
  bffEnabled: boolean;
  fetchWorkspace: (priorityLimit: number, view: MonitorWorkspaceView) => Promise<MonitorWorkspaceData>;
  fetchLegacy: (includeRuntime: boolean) => Promise<unknown>;
  fetchPriorityBoard: (
    limit: number,
    strategyVariant: "baseline",
    refresh: "cache",
  ) => Promise<LowBuyPriorityBoardResult>;
  fetchHourlyHistory: () => Promise<unknown>;
  fetchRuntime: () => Promise<RuntimeStatus>;
  hasAdminToken: () => boolean;
}

export async function loadMonitorWorkspaceFirstScreen(
  options: MonitorFirstScreenLoadOptions,
): Promise<MonitorFirstScreenLoadResult> {
  if (!options.bffEnabled) {
    return {
      source: "legacy",
      legacy: await options.fetchLegacy(options.includeRuntime),
      fallbackResults: [],
    };
  }

  try {
    const workspace = await options.fetchWorkspace(options.priorityLimit, monitorWorkspaceViewForPage(options.page));
    const fallbackRequests: Promise<unknown>[] = [];
    if (!workspace.hourly_snapshot_history) {
      fallbackRequests.push(options.fetchHourlyHistory());
    }
    if (shouldLoadRuntimeFallback(workspace, options.includeRuntime, options.hasAdminToken)) {
      fallbackRequests.push(options.fetchRuntime());
    }
    const [priorityBoardFallback, fallbackResults] = await Promise.all([
      fetchMonitorPriorityBoardFallback(workspace, options.fetchPriorityBoard),
      Promise.allSettled(fallbackRequests),
    ]);
    return {
      source: "bff",
      workspace,
      priorityBoardFallback,
      fallbackResults,
    };
  } catch (error) {
    if (isMonitorBffDisabled(error)) {
      return {
        source: "legacy",
        legacy: await options.fetchLegacy(options.includeRuntime),
        fallbackResults: [],
      };
    }
    throw error;
  }
}

export function monitorWorkspaceViewForPage(page: Page): MonitorWorkspaceView {
  if (page === "monitor") return "action";
  if (page === "monitor-market") return "market";
  return "full";
}

function shouldLoadRuntimeFallback(
  workspace: MonitorWorkspaceData,
  includeRuntime: boolean,
  hasAdminToken: () => boolean,
): boolean {
  return includeRuntime && hasAdminToken() && !("runtime" in workspace);
}
