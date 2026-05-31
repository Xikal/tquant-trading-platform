import { queryOptions, useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/httpClient";
import { queryKeys } from "./queryKeys";
import type { PaperWorkspaceResponse } from "./types";

export function paperWorkspaceOptions(fetchPaperWorkspace: () => Promise<PaperWorkspaceResponse> = fetchPaperWorkspaceBff) {
  return queryOptions({
    queryKey: queryKeys.paperWorkspace,
    queryFn: fetchPaperWorkspace,
    staleTime: 15_000,
  });
}

export function usePaperWorkspaceQuery() {
  return useQuery(paperWorkspaceOptions());
}

export function paperPositionsOptions(fetchPaperWorkspace: () => Promise<PaperWorkspaceResponse> = fetchPaperWorkspaceBff) {
  return queryOptions({
    ...paperWorkspaceOptions(fetchPaperWorkspace),
    select: (payload) => payload.positions ?? [],
  });
}

export function usePaperPositionsQuery() {
  return useQuery(paperPositionsOptions());
}

function fetchPaperWorkspaceBff() {
  return apiClient.request<PaperWorkspaceResponse>("/bff/v1/workspace/paper?order_limit=80&trade_limit=300&run_limit=20");
}
