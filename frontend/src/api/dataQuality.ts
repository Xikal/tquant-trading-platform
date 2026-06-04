import { apiClient } from "./httpClient";
import type { components, paths } from "../generated/api-types";

type ApiOperation<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends infer Operation ? Operation : never;

type ApiJson<Path extends keyof paths, Method extends keyof paths[Path]> =
  ApiOperation<Path, Method> extends { responses: { 200: { content: { "application/json": infer Payload } } } } ? Payload : never;

type ApiRequestBody<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends { requestBody: { content: { "application/json": infer Payload } } } ? Payload : never;

export type DataQualitySnapshotItem = components["schemas"]["DataQualitySnapshotOut"];
export type DataRepairAuditItem = components["schemas"]["DataRepairAuditOut"];
export type DataQualityMissingSymbol = components["schemas"]["DataQualityMissingSymbolOut"];
type GeneratedDataQualitySlaResponse = ApiJson<"/api/data-quality/sla", "get">;
type GeneratedDataQualityCoverageResponse = ApiJson<"/api/data-quality/coverage", "get">;
type GeneratedDataRepairRunRequest = ApiRequestBody<"/api/data-quality/repair", "post">;
type GeneratedTradeDataGateResponse = ApiJson<"/api/data-quality/trade-gate", "get">;
type GeneratedRuntimeFallbackStatus = ApiJson<"/api/data-quality/runtime-fallback", "get">;
export type DataQualitySlaResponse = Omit<GeneratedDataQualitySlaResponse, "items" | "latest_repair_audits"> & {
  items: DataQualitySnapshotItem[];
  latest_repair_audits: DataRepairAuditItem[];
};
export type DataQualityCoverageResponse = Omit<GeneratedDataQualityCoverageResponse, "missing_symbols" | "missing_dates"> & {
  missing_symbols: DataQualityMissingSymbol[];
  missing_dates: string[];
};
export type DataQualityBackfillRequest = ApiRequestBody<"/api/data-quality/backfill", "post">;
export type DataRepairRunRequest = Pick<GeneratedDataRepairRunRequest, "dataset_key" | "dry_run"> & Partial<Omit<GeneratedDataRepairRunRequest, "dataset_key" | "dry_run">>;
export type DataRepairRunResponse = components["schemas"]["RuntimeTaskOut"];
export type TradeDataGateCheck = components["schemas"]["TradeDataGateCheckOut"];
export type TradeDataGateResponse = Omit<GeneratedTradeDataGateResponse, "checks"> & {
  checks: TradeDataGateCheck[];
};
export type RuntimeFallbackStatus = Omit<GeneratedRuntimeFallbackStatus, "recovery_actions"> & {
  recovery_actions: string[];
};

export const dataQualityApi = {
  sla: () => apiClient.request<GeneratedDataQualitySlaResponse>("/data-quality/sla").then(normalizeSlaResponse),
  coverage: ({ dataset_key, scope }: { dataset_key: string; scope: string }) =>
    apiClient.request<GeneratedDataQualityCoverageResponse>(
      `/data-quality/coverage?dataset_key=${encodeURIComponent(dataset_key)}&scope=${encodeURIComponent(scope)}`,
    ).then(normalizeCoverageResponse),
  backfill: (payload: DataQualityBackfillRequest) => apiClient.request<DataRepairRunResponse>("/data-quality/backfill", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  repair: (payload: DataRepairRunRequest) => apiClient.request<DataRepairRunResponse>("/data-quality/repair", {
    method: "POST",
    body: JSON.stringify(toRepairRunRequest(payload)),
  }),
  repairDryRun: () => apiClient.request<DataRepairRunResponse>("/data-quality/repair", {
    method: "POST",
    body: JSON.stringify(toRepairRunRequest({ dataset_key: "daily_bars", dry_run: true })),
  }),
  tradeGate: () => apiClient.request<GeneratedTradeDataGateResponse>("/data-quality/trade-gate").then(normalizeTradeGateResponse),
  runtimeFallback: () => apiClient.request<GeneratedRuntimeFallbackStatus>("/data-quality/runtime-fallback").then(normalizeRuntimeFallbackStatus),
};

function normalizeSlaResponse(payload: GeneratedDataQualitySlaResponse): DataQualitySlaResponse {
  return {
    ...payload,
    items: payload.items ?? [],
    latest_repair_audits: payload.latest_repair_audits ?? [],
  };
}

function normalizeCoverageResponse(payload: GeneratedDataQualityCoverageResponse): DataQualityCoverageResponse {
  return {
    ...payload,
    missing_symbols: payload.missing_symbols ?? [],
    missing_dates: payload.missing_dates ?? [],
  };
}

function normalizeTradeGateResponse(payload: GeneratedTradeDataGateResponse): TradeDataGateResponse {
  return {
    ...payload,
    checks: payload.checks ?? [],
  };
}

function normalizeRuntimeFallbackStatus(payload: GeneratedRuntimeFallbackStatus): RuntimeFallbackStatus {
  return {
    ...payload,
    recovery_actions: payload.recovery_actions ?? [],
  };
}

function toRepairRunRequest(payload: DataRepairRunRequest): GeneratedDataRepairRunRequest {
  return {
    backup_dir: "",
    output_path: "",
    refetch: true,
    ...payload,
  };
}
