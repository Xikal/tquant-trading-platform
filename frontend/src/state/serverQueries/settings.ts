import { queryOptions, useQuery } from "@tanstack/react-query";
import { apiClient } from "../../api/httpClient";
import { queryKeys } from "./queryKeys";
import type { SettingsWorkspaceResponse } from "./types";

export function settingsWorkspaceOptions(
  fetchSettingsWorkspace: () => Promise<SettingsWorkspaceResponse> = fetchSettingsWorkspaceBff,
) {
  return queryOptions({
    queryKey: queryKeys.settingsWorkspace,
    queryFn: fetchSettingsWorkspace,
    staleTime: 30_000,
  });
}

export function useSettingsWorkspaceQuery() {
  return useQuery(settingsWorkspaceOptions());
}

function fetchSettingsWorkspaceBff() {
  return apiClient.request<SettingsWorkspaceResponse>("/bff/v1/workspace/settings");
}
