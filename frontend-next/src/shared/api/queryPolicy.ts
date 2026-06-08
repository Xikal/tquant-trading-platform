import { apiOperations, type ApiOperationName } from "./operations";

const DEFAULT_STALE_TIME_MS = 10_000;

const realtimeOperationIntervals: Partial<Record<ApiOperationName, number>> = {
  monitorWorkspace: 10_000,
  monitorSnapshot: 15_000,
  marketBreadth: 10_000,
  marketSectorRelativeStrength: 20_000,
  watchlistSignals: 9_000,
  watchlistQuotes: 6_000,
  paperWorkspace: 10_000,
  paperAccount: 10_000,
  paperPositions: 10_000,
  paperOrders: 10_000,
  paperRiskEvents: 20_000,
  quote: 8_000,
  marketIntradayAnomaly: 15_000,
  lowBuyPriorityBoard: 15_000,
  lowBuyQuotes: 6_000,
  strategyWorkspace: 12_000,
  strategyTrackingItems: 12_000,
  strategyTrackingSummary: 12_000,
  strategyTrackingPerformance: 12_000,
  strategyTrackingHoldingAnalysis: 12_000,
  relativeStrength: 12_000,
};

export function operationStaleTimeMs(queryKey: readonly unknown[]): number {
  const name = operationNameFromQueryKey(queryKey);
  if (!name) return DEFAULT_STALE_TIME_MS;
  return apiOperations[name].defaultStaleTimeMs ?? DEFAULT_STALE_TIME_MS;
}

export function realtimeRefetchIntervalMs(queryKey: readonly unknown[]): number | false {
  const name = operationNameFromQueryKey(queryKey);
  if (!name) return false;
  return realtimeOperationIntervals[name] ?? false;
}

export function refetchOnWindowFocus(queryKey: readonly unknown[]): boolean | "always" {
  return realtimeRefetchIntervalMs(queryKey) ? "always" : false;
}

function operationNameFromQueryKey(queryKey: readonly unknown[]): ApiOperationName | null {
  if (queryKey[0] !== "frontend-next" || queryKey[1] !== "operation") return null;
  const candidate = queryKey[2];
  if (typeof candidate !== "string" || !(candidate in apiOperations)) return null;
  return candidate as ApiOperationName;
}
