import { apiClient } from "./httpClient";
import type { DataSourceProbeResponse } from "../types";

export const dataSourcesApi = {
  health: () => apiClient.request<DataSourceProbeResponse>("/market/data-sources/health"),
};
