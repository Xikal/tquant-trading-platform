import { queryOptions, useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/httpClient";
import { queryKeys } from "./queryKeys";
import type { BacktestRunListResponse } from "./types";

export function backtestRunsOptions(
  limit = 20,
  fetchRuns: (limit: number) => Promise<BacktestRunListResponse> = fetchBacktestRuns,
) {
  return queryOptions({
    queryKey: queryKeys.backtestRuns(limit),
    queryFn: () => fetchRuns(limit),
    staleTime: 20_000,
  });
}

export function useBacktestRunsQuery(limit = 20) {
  return useQuery(backtestRunsOptions(limit));
}

function fetchBacktestRuns(limit: number) {
  return apiClient.request<BacktestRunListResponse>(`/backtests/runs?limit=${limit}`);
}
