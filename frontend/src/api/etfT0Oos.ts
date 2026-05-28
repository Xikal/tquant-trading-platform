import { apiClient } from "./httpClient";
import type {
  EtfT0OosDataset,
  EtfT0OosDatasetListResponse,
  EtfT0OosLatestResponse,
  EtfT0OosPromoteCheckResponse,
  EtfT0OosValidationRequest,
  EtfT0OosValidationResponse,
} from "../types/etfT0Oos";

const request = apiClient.request;
const requestCached = apiClient.requestCached;

export const etfT0OosApi = {
  listDatasets: () => requestCached<EtfT0OosDatasetListResponse>("/backtests/etf-t0-oos/datasets", 60_000),
  getDataset: (datasetKey: string) =>
    requestCached<EtfT0OosDataset>(`/backtests/etf-t0-oos/datasets/${encodeURIComponent(datasetKey)}`, 60_000),
  validate: (payload: EtfT0OosValidationRequest) =>
    request<EtfT0OosValidationResponse>("/backtests/etf-t0-oos/validate", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 30_000,
    }),
  promoteCheck: (payload: EtfT0OosValidationRequest) =>
    request<EtfT0OosPromoteCheckResponse>("/backtests/etf-t0-oos/promote-check", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 30_000,
    }),
  latest: () => requestCached<EtfT0OosLatestResponse>("/backtests/etf-t0-oos/latest", 15_000),
};
