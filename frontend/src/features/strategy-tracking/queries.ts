import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../app/query/queryKeys";
import type { StrategyTrackingParams, TradeJournalEntryCreate } from "../../types";

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

export function useTradingExperienceReadiness() {
  return useQuery({
    queryKey: queryKeys.tradingExperienceReadiness,
    queryFn: () => api.getTradingExperienceReadiness(),
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useTradeReviewSuite(enabled = true) {
  return useQuery({
    queryKey: queryKeys.tradingExperienceReview,
    queryFn: () => api.getTradingExperienceReviewPool(30),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useTradeJournal(accountId?: number | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.tradingExperienceJournal(accountId),
    queryFn: () => api.getTradingExperienceTradeJournal(accountId),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useCreateTradeJournal(accountId?: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TradeJournalEntryCreate) => api.createTradingExperienceTradeJournal(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.tradingExperienceJournal(accountId) });
      if (accountId !== null) {
        await queryClient.invalidateQueries({ queryKey: queryKeys.tradingExperienceJournal(null) });
      }
    },
  });
}

export function useRelativeStrengthBoard(enabled = true) {
  return useQuery({
    queryKey: queryKeys.tradingExperienceRelativeStrength,
    queryFn: () => api.getTradingExperienceRelativeStrength(30),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useVolumePositionTags(symbol?: string | null, enabled = true) {
  const normalized = symbol?.trim() ?? "";
  return useQuery({
    queryKey: queryKeys.tradingExperienceVolumeTags(normalized),
    queryFn: () => api.getVolumePositionTags(normalized),
    enabled: enabled && Boolean(normalized),
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}
