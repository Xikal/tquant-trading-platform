import { apiClient } from "./httpClient";
import type { components } from "../generated/api-types";

export type RuntimeTaskOut = components["schemas"]["RuntimeTaskOut"];

export type RuntimeTaskListResponse = components["schemas"]["RuntimeTaskListResponse"];
export type RuntimeTaskSummaryResponse = components["schemas"]["RuntimeTaskSummaryResponse"];
type GeneratedRuntimeTaskWorkerListResponse = components["schemas"]["RuntimeTaskWorkerListResponse"];
type GeneratedRuntimeTaskFailureResponse = components["schemas"]["RuntimeTaskFailureResponse"];
type GeneratedRuntimeTaskArtifactResponse = components["schemas"]["RuntimeTaskArtifactResponse"];
type GeneratedRuntimeTaskAnalyticsReportResponse = components["schemas"]["RuntimeTaskAnalyticsReportResponse"];
export type RuntimeTaskWorkerListResponse = Omit<GeneratedRuntimeTaskWorkerListResponse, "items"> & {
  items: components["schemas"]["RuntimeTaskWorkerOut"][];
};
export type RuntimeTaskFailureResponse = Omit<GeneratedRuntimeTaskFailureResponse, "items"> & {
  items: RuntimeTaskOut[];
};
export type RuntimeTaskArtifactResponse = Omit<GeneratedRuntimeTaskArtifactResponse, "items"> & {
  items: components["schemas"]["RuntimeTaskArtifactOut"][];
};
export type RuntimeTaskAnalyticsReportResponse = Omit<GeneratedRuntimeTaskAnalyticsReportResponse, "items"> & {
  items: components["schemas"]["RuntimeTaskAnalyticsReportOut"][];
};

export type RuntimeTaskCreate = components["schemas"]["RuntimeTaskCreate"];
export type RuntimeTaskCreateInput = Omit<RuntimeTaskCreate, "idempotency_key"> & { idempotency_key?: string };

export function isRuntimeTask(value: unknown): value is RuntimeTaskOut {
  return Boolean(value && typeof value === "object" && "task_type" in value && "status" in value && "id" in value);
}

export const runtimeTasksApi = {
  list: (status = "", limit = 50) =>
    apiClient.request<RuntimeTaskListResponse>(
      `/runtime-tasks?limit=${limit}${status ? `&status=${encodeURIComponent(status)}` : ""}`,
    ).then((payload) => ({ ...payload, items: payload.items ?? [] })),
  summary: () => apiClient.request<RuntimeTaskSummaryResponse>("/runtime-tasks/summary"),
  workers: () => apiClient.request<GeneratedRuntimeTaskWorkerListResponse>("/runtime-tasks/workers").then((payload) => ({ ...payload, items: payload.items ?? [] })),
  failures: (limit = 20) => apiClient.request<GeneratedRuntimeTaskFailureResponse>(`/runtime-tasks/failures?limit=${limit}`).then((payload) => ({ ...payload, items: payload.items ?? [] })),
  artifacts: (limit = 50) => apiClient.request<GeneratedRuntimeTaskArtifactResponse>(`/runtime-tasks/artifacts?limit=${limit}`).then((payload) => ({ ...payload, items: payload.items ?? [] })),
  analyticsReports: (limit = 20) => apiClient.request<GeneratedRuntimeTaskAnalyticsReportResponse>(`/runtime-tasks/analytics-reports?limit=${limit}`).then((payload) => ({ ...payload, items: payload.items ?? [] })),
  get: (taskId: number) => apiClient.request<RuntimeTaskOut>(`/runtime-tasks/${taskId}`),
  enqueue: (payload: RuntimeTaskCreateInput) => apiClient.request<RuntimeTaskOut>("/runtime-tasks", {
    method: "POST",
    body: JSON.stringify({ idempotency_key: "", ...payload }),
  }),
};
