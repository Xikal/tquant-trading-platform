import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../app/query/queryKeys";

export function usePaperSummaryQuery() {
  return useQuery({
    queryKey: queryKeys.paperWorkspace,
    queryFn: () => api.getPaperWorkspaceBff(),
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
}
