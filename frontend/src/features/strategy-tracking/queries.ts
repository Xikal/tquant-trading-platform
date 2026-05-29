import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../app/query/queryKeys";
import type { StrategyTrackingParams } from "../../types";

export function useStrategyTrackingItems(params: StrategyTrackingParams) {
  return useQuery({
    queryKey: queryKeys.strategyTracking(params as Record<string, unknown>),
    queryFn: () => api.getStrategyTrackingItems(params),
    staleTime: 12_000,
  });
}

export function useStrategyTrackingDetail(itemId: string | null) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingDetail(itemId),
    queryFn: () => api.getStrategyTrackingDetail(itemId || ""),
    enabled: Boolean(itemId),
    staleTime: 30_000,
  });
}

export function useStrategyTrackingReport(type: "daily" | "weekly", params: StrategyTrackingParams, enabled = true) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingReport(type, params as Record<string, unknown>),
    queryFn: () => api.getStrategyTrackingReport(type, params),
    enabled,
    staleTime: 30_000,
  });
}

export function useStrategyTrackingHoldingAnalysis(params: StrategyTrackingParams, enabled = true) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingHoldingAnalysis(params as Record<string, unknown>),
    queryFn: () => api.getStrategyTrackingHoldingAnalysis(params),
    enabled,
    staleTime: 30_000,
  });
}
