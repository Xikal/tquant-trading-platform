import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../app/query/queryKeys";

export function usePriorityBoardQuery(strategy = "all", limit = 20) {
  return useQuery({
    queryKey: queryKeys.priorityBoard(strategy, limit),
    queryFn: () => api.getLowBuyPriorityBoard(limit),
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
}
