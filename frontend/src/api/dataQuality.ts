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

export interface DataQualityMissingSymbol {
  symbol: string;
  name: string;
  missing_days: number;
}

export interface DataQualityCoverageResponse {
  dataset_key: string;
  scope: string;
  missing_symbols: DataQualityMissingSymbol[];
  missing_dates: string[];
}

export interface DataQualityBackfillRequest {
  dataset_key: string;
  scope: string;
  start_date: string;
  end_date: string;
}

export interface DataRepairRunRequest {
  dataset_key: string;
  dry_run: boolean;
}

export interface DataRepairRunResponse {
  id: number;
  task_type: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  progress_pct?: number;
  error_message?: string;
}

export interface TradeDataGateCheck {
  key: string;
  label: string;
  ok: boolean;
  severity: "green" | "yellow" | "red";
  detail: string;
}

export interface TradeDataGateResponse {
  ok: boolean;
  checks: TradeDataGateCheck[];
}

export interface RuntimeFallbackStatus {
  worker_status: "running" | "stale" | "missing" | string;
  worker_id: string;
  heartbeat_updated_at: string;
  heartbeat_age_seconds: number | null;
  critical_queued_count: number;
  oldest_critical_queued_at: string;
  oldest_critical_queued_age_seconds: number | null;
  blocking: boolean;
  message: string;
  recovery_actions: string[];
}

export const dataQualityApi = {
  sla: () => apiClient.request<DataQualitySlaResponse>("/data-quality/sla"),
  coverage: ({ dataset_key, scope }: { dataset_key: string; scope: string }) =>
    apiClient.request<DataQualityCoverageResponse>(
      `/data-quality/coverage?dataset_key=${encodeURIComponent(dataset_key)}&scope=${encodeURIComponent(scope)}`,
    ),
  backfill: (payload: DataQualityBackfillRequest) => apiClient.request<DataRepairRunResponse>("/data-quality/backfill", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  repair: (payload: DataRepairRunRequest) => apiClient.request<DataRepairRunResponse>("/data-quality/repair", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  repairDryRun: () => apiClient.request<DataRepairRunResponse>("/data-quality/repair", {
    method: "POST",
    body: JSON.stringify({ dataset_key: "daily_bars", dry_run: true }),
  }),
  tradeGate: () => apiClient.request<TradeDataGateResponse>("/data-quality/trade-gate"),
  runtimeFallback: () => apiClient.request<RuntimeFallbackStatus>("/data-quality/runtime-fallback"),
};
