import { queryOptions, useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { apiClient } from "../../api/httpClient";
import type { StrategyTrackingParams } from "../../types";
import { queryKeys } from "./queryKeys";
import type { StrategyTrackingSnapshotResponse } from "./types";

const STRATEGY_TRACKING_STALE_TIME_MS = 60_000;
const STRATEGY_TRACKING_DETAIL_STALE_TIME_MS = 30_000;

export function strategyTrackingSnapshotOptions(
  params: StrategyTrackingParams,
  fetchSnapshot: (params: StrategyTrackingParams) => Promise<StrategyTrackingSnapshotResponse> =
    fetchStrategyTrackingSnapshot,
) {
  return queryOptions({
    queryKey: queryKeys.strategyTracking(params as Record<string, unknown>),
    queryFn: () => fetchSnapshot(params),
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useStrategyTrackingSnapshotQuery(params: StrategyTrackingParams) {
  return useQuery(strategyTrackingSnapshotOptions(params));
}

export function useStrategyTrackingDetailQuery(itemId: string | null) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingDetail(itemId),
    queryFn: () => api.getStrategyTrackingDetail(itemId || ""),
    enabled: Boolean(itemId),
    staleTime: STRATEGY_TRACKING_DETAIL_STALE_TIME_MS,
  });
}

export function useStrategyTrackingReportQuery(
  type: "daily" | "weekly",
  params: StrategyTrackingParams,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingReport(type, params as Record<string, unknown>),
    queryFn: () => api.getStrategyTrackingReport(type, params),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useStrategyTrackingHoldingAnalysisQuery(params: StrategyTrackingParams, enabled = true) {
  return useQuery({
    queryKey: queryKeys.strategyTrackingHoldingAnalysis(params as Record<string, unknown>),
    queryFn: () => api.getStrategyTrackingHoldingAnalysis(params),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useStrategyPromotionReviewQuery(strategyKey: string, enabled = true) {
  return useQuery({
    queryKey: ["strategy-promotion-review", strategyKey],
    queryFn: () => api.getStrategyPromotionReview(strategyKey),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

export function useTrackRecordDriftQuery(windowDays = 60, enabled = true) {
  return useQuery({
    queryKey: queryKeys.trackRecordDrift(windowDays),
    queryFn: () => api.getTrackRecordDrift(windowDays),
    enabled,
    staleTime: STRATEGY_TRACKING_STALE_TIME_MS,
  });
}

function fetchStrategyTrackingSnapshot(params: StrategyTrackingParams = {}) {
  return apiClient.requestCached<StrategyTrackingSnapshotResponse>(
    `/strategy-tracking/snapshot?${strategyTrackingQuery(params)}`,
    12_000,
  );
}

function strategyTrackingQuery(params: StrategyTrackingParams): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    query.set(key, String(value));
  });
  return query.toString();
}
