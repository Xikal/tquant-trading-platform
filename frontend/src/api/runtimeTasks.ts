import { apiClient } from "./httpClient";

export interface RuntimeTaskOut {
  id: number;
  task_type: string;
  status: string;
  progress_pct: number;
  payload?: Record<string, unknown>;
  result?: Record<string, unknown>;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface RuntimeTaskListResponse {
  items: RuntimeTaskOut[];
  limit: number;
  offset: number;
  total: number;
}

export interface RuntimeTaskCreate {
  task_type: string;
  payload?: Record<string, unknown>;
  priority?: number;
  idempotency_key?: string;
  max_attempts?: number;
}

export const runtimeTasksApi = {
  list: (status = "", limit = 50) =>
    apiClient.request<RuntimeTaskListResponse>(
      `/runtime-tasks?limit=${limit}${status ? `&status=${encodeURIComponent(status)}` : ""}`,
    ),
  get: (taskId: number) => apiClient.request<RuntimeTaskOut>(`/runtime-tasks/${taskId}`),
  enqueue: (payload: RuntimeTaskCreate) => apiClient.request<RuntimeTaskOut>("/runtime-tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
};
