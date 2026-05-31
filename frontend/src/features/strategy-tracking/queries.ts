import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../app/query/queryKeys";
import type { StrategyTrackingParams } from "../../types";

const STRATEGY_TRACKING_STALE_TIME_MS = 60_000;
const STRATEGY_TRACKING_DETAIL_STALE_TIME_MS = 30_000;

export function useStrategyTrackingItems(params: StrategyTrackingParams) {
  return useQuery({
    queryKey: queryKeys.strategyTracking(params as Record<string, unknown>),
    queryFn: () => api.getStrategyTrackingSnapshot(params),
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useStrategyTrackingDetail(itemId: string | null) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingDetail(itemId),
    queryFn: () => api.getStrategyTrackingDetail(itemId || ""),
    enabled: Boolean(itemId),
    staleTime: STRATEGY_TRACKING_DETAIL_STALE_TIME_MS,
  });
}

export function useStrategyTrackingReport(type: "daily" | "weekly", params: StrategyTrackingParams, enabled = true) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingReport(type, params as Record<string, unknown>),
    queryFn: () => api.getStrategyTrackingReport(type, params),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useStrategyTrackingHoldingAnalysis(params: StrategyTrackingParams, enabled = true) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingHoldingAnalysis(params as Record<string, unknown>),
    queryFn: () => api.getStrategyTrackingHoldingAnalysis(params),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useStrategyPromotionReview(strategyKey: string, enabled = true) {
  return useQuery({
    queryKey: ["strategy-promotion-review", strategyKey],
    queryFn: () => api.getStrategyPromotionReview(strategyKey),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useTrackRecordDrift(windowDays = 60, enabled = true) {
  return useQuery({
    queryKey: queryKeys.trackRecordDrift(windowDays),
    queryFn: () => api.getTrackRecordDrift(windowDays),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}
