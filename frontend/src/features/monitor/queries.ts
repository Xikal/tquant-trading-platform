import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../app/query/queryKeys";

export function useMonitorQuery(priorityLimit = 12) {
  return useQuery({
    queryKey: queryKeys.monitorWorkspace(priorityLimit),
    queryFn: () => api.getMonitorWorkspaceBff(priorityLimit),
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
}
