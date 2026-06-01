import { queryOptions, useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/httpClient";
import { queryKeys } from "./queryKeys";
import type { MonitorSnapshotResponse, MonitorWorkspaceResponse } from "./types";

interface MonitorWorkspaceOptionsArgs {
  priorityLimit?: number;
  fetchMonitorWorkspace?: (priorityLimit: number) => Promise<MonitorWorkspaceResponse>;
}

export function monitorSnapshotOptions({
  priorityLimit = 12,
  fetchMonitorWorkspace = fetchMonitorWorkspaceBff,
}: MonitorWorkspaceOptionsArgs = {}) {
  return queryOptions({
    queryKey: queryKeys.monitorWorkspace(priorityLimit),
    queryFn: () => fetchMonitorWorkspace(priorityLimit),
    staleTime: 20_000,
    select: (payload): MonitorSnapshotResponse | null => payload.monitor_snapshot ?? null,
  });
}

export function useMonitorSnapshotQuery(priorityLimit = 12) {
  return useQuery(monitorSnapshotOptions({ priorityLimit }));
}

function fetchMonitorWorkspaceBff(priorityLimit: number) {
  return apiClient.requestCached<MonitorWorkspaceResponse>(
    `/bff/v1/workspace/monitor?priority_limit=${priorityLimit}&sector_limit=8&per_sector_limit=8&hedge_limit=4`,
    10_000,
  );
}
