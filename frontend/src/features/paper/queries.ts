import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../app/query/queryKeys";

export function usePaperSummaryQuery() {
  return useQuery({
    queryKey: queryKeys.paperWorkspace,
    queryFn: () => api.getPaperWorkspaceBff(),
    placeholderData: (previous) => previous,
    refetchOnMount: false,
    refetchOnReconnect: true,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

export function useHoldingDiscipline(accountId?: number | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.tradingExperienceHoldingDiscipline(accountId),
    queryFn: () => api.getHoldingDiscipline(accountId),
    enabled,
    placeholderData: (previous) => previous,
    refetchOnMount: false,
    refetchOnReconnect: true,
    staleTime: 60_000,
  });
}

export function useTTradeAttribution(accountId?: number | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.tradingExperienceTTrade(accountId),
    queryFn: () => api.getTTradeAttribution(accountId, 30),
    enabled,
    placeholderData: (previous) => previous,
    refetchOnMount: false,
    refetchOnReconnect: true,
    staleTime: 60_000,
  });
}
