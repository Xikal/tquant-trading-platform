import { apiClient } from "./httpClient";
import type { components } from "../generated/api-types";

export type RuntimeTaskOut = components["schemas"]["RuntimeTaskOut"];

export type RuntimeTaskListResponse = components["schemas"]["RuntimeTaskListResponse"];

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
  get: (taskId: number) => apiClient.request<RuntimeTaskOut>(`/runtime-tasks/${taskId}`),
  enqueue: (payload: RuntimeTaskCreateInput) => apiClient.request<RuntimeTaskOut>("/runtime-tasks", {
    method: "POST",
    body: JSON.stringify({ idempotency_key: "", ...payload }),
  }),
};
