import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../app/query/queryKeys";
import type { StrategyVariant } from "../../types";

export function usePriorityBoardQuery(strategy: StrategyVariant = "baseline", limit = 20) {
  return useQuery({
    queryKey: queryKeys.priorityBoard(strategy, limit),
    queryFn: () => api.getLowBuyPriorityBoard(limit, strategy),
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
}
