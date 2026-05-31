import { apiClient } from "./httpClient";

export interface DataQualitySnapshotItem {
  dataset_key: string;
  as_of_date: string;
  scope: string;
  expected_days: number;
  actual_days: number;
  missing_days: number;
  invalid_rows: number;
  duplicate_rows: number;
  stale: boolean;
  coverage_pct: number;
  status: string;
  blockers: string[];
  checked_at?: string | null;
}

export interface DataRepairAuditItem {
  id: number;
  repair_id: string;
  dataset_key: string;
  reason: string;
  backup_path: string;
  refetch_result: string;
  deleted_rows_count: number;
  fabricated: boolean;
  operator: string;
  created_at?: string | null;
}

export interface DataQualitySlaResponse {
  items: DataQualitySnapshotItem[];
  latest_repair_audits: DataRepairAuditItem[];
  total: number;
}

export interface DataRepairRunResponse {
  id: number;
  task_type: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export const dataQualityApi = {
  sla: () => apiClient.request<DataQualitySlaResponse>("/data-quality/sla"),
  repairDryRun: () => apiClient.request<DataRepairRunResponse>("/data-quality/repair", {
    method: "POST",
    body: JSON.stringify({ dataset_key: "daily_bars", dry_run: true }),
  }),
};
