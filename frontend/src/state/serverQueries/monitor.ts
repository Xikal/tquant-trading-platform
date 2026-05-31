import { queryOptions, useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/httpClient";
import { queryKeys } from "./queryKeys";
import type { MonitorSnapshotResponse, MonitorWorkspaceResponse } from "./types";

interface MonitorWorkspaceOptionsArgs {
  priorityLimit?: number;
  fetchMonitorWorkspace?: (priorityLimit: number) => Promise<MonitorWorkspaceResponse>;
}

export function monitorWorkspaceOptions({
  priorityLimit = 12,
  fetchMonitorWorkspace = fetchMonitorWorkspaceBff,
}: MonitorWorkspaceOptionsArgs = {}) {
  return queryOptions({
    queryKey: queryKeys.monitorWorkspace(priorityLimit),
    queryFn: () => fetchMonitorWorkspace(priorityLimit),
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
}

export function monitorSnapshotOptions(args: MonitorWorkspaceOptionsArgs = {}) {
  return queryOptions({
    ...monitorWorkspaceOptions(args),
    select: (payload): MonitorSnapshotResponse | null => payload.monitor_snapshot ?? null,
  });
}

export function useMonitorWorkspaceQuery(priorityLimit = 12) {
  return useQuery(monitorWorkspaceOptions({ priorityLimit }));
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
