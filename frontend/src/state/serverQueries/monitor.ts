import { queryOptions, useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/httpClient";
import { queryKeys } from "./queryKeys";
import type { MonitorSnapshotResponse, MonitorWorkspaceResponse } from "./types";

interface MonitorWorkspaceOptionsArgs {
  priorityLimit?: number;
  view?: "full" | "action" | "market";
  fetchMonitorWorkspace?: (priorityLimit: number, view: "full" | "action" | "market") => Promise<MonitorWorkspaceResponse>;
}

export function monitorSnapshotOptions({
  priorityLimit = 12,
  view = "full",
  fetchMonitorWorkspace = fetchMonitorWorkspaceBff,
}: MonitorWorkspaceOptionsArgs = {}) {
  return queryOptions({
    queryKey: queryKeys.monitorWorkspace(priorityLimit, view),
    queryFn: () => fetchMonitorWorkspace(priorityLimit, view),
    staleTime: 20_000,
    select: (payload): MonitorSnapshotResponse | null => payload.monitor_snapshot ?? null,
  });
}

export function useMonitorSnapshotQuery(priorityLimit = 12) {
  return useQuery(monitorSnapshotOptions({ priorityLimit }));
}

function fetchMonitorWorkspaceBff(priorityLimit: number, view: "full" | "action" | "market" = "full") {
  return apiClient.requestCached<MonitorWorkspaceResponse>(
    `/bff/v1/workspace/monitor?priority_limit=${priorityLimit}&sector_limit=8&per_sector_limit=8&hedge_limit=4&view=${view}`,
    10_000,
  );
}
