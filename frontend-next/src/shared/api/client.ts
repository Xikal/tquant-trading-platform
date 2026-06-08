import { buildAuthHeaders, currentRefreshTokenRemembered, getAuthRefreshToken, setAuthAccessToken, setAuthRefreshToken } from "./auth";
import { ApiError, ApiTransportError } from "./errors";
import { operationPath, type ApiOperationName, type OperationPathOptions, type QueryValue } from "./operations";
import { recordTelemetry } from "../telemetry/clientTelemetry";
import type {
  AnalyzeBatchResponse,
  AnalyzeSymbolResponse,
  AdminMetricsResponse,
  AdminTasksResponse,
  AuthTokenResponse,
  BacktestRunDetailResponse,
  BacktestRunEquityResponse,
  BacktestRunTradesResponse,
  BacktestRunsResponse,
  DataQualityCoverageResponse,
  DataQualitySlaResponse,
  FactorWeightsResponse,
  FeatureFlagAuditResponse,
  FeatureFlagsResponse,
  IntradayAnomalyResponse,
  KlineResponse,
  LowBuyPriorityBoardResponse,
  LowBuyQuotesResponse,
  LowBuyScreenerResponse,
  LowBuyStrategiesResponse,
  MonitorWorkspaceResponse,
  PaperAccountResponse,
  PaperAutoTradingRunsResponse,
  PaperAutoTradingStatusResponse,
  PaperOrdersResponse,
  PaperPerformanceDashboardResponse,
  PaperPositionsResponse,
  PaperRiskEventsResponse,
  PaperTradesResponse,
  PaperWorkspaceResponse,
  QuantParametersResponse,
  QuoteResponse,
  RelativeStrengthResponse,
  RuntimeTaskSummaryResponse,
  RuntimeTasksResponse,
  SectorExclusionsResponse,
  SettingsResponse,
  SettingsRuntimeResponse,
  SettingsWorkspaceResponse,
  StockKeyLevelsResponse,
  StrategyMetaResponse,
  StrategyTrackingDetailResponse,
  StrategyTrackingHoldingAnalysisResponse,
  StrategyTrackingItemsResponse,
  StrategyTrackingPerformanceResponse,
  StrategyTrackingReviewResponse,
  StrategyTrackingSummaryResponse,
  StrategyWorkspaceResponse,
  TradeJournalResponse,
} from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
export type StrategyVariant = "baseline" | "front_row_weighted" | "front_row_only";
const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;
const MAX_RETRY_AFTER_MS = 2_000;
const RETRYABLE_READ_STATUSES = new Set([429, 500, 502, 503, 504]);

export interface RequestJsonOptions extends RequestInit {
  timeoutMs?: number;
  retry?: boolean | number;
}

export async function requestJson<T>(path: string, init: RequestJsonOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, retry, signal, ...requestInit } = init;
  const started = performance.now();
  const method = requestInit.method ?? "GET";
  const headers: Record<string, string> = {
    ...buildAuthHeaders(),
    ...((requestInit.headers as Record<string, string> | undefined) ?? {}),
  };
  if (requestInit.body !== undefined && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const attempts = retryAttempts(requestInit.method, retry);
  let lastError: unknown;
  let attempt = 0;
  let authRefreshTried = false;
  while (attempt < attempts) {
    const attemptNumber = attempt + 1;
    try {
      const response = await fetchWithTimeout(`${API_BASE}${path}`, {
        ...requestInit,
        headers,
        credentials: "include",
        signal,
      }, timeoutMs);
      if (response.ok) {
        recordApiTelemetry(path, method, response.status, attemptNumber, started, "ok");
        return response.json() as Promise<T>;
      }
      if (response.status === 401 && !authRefreshTried && shouldRefreshAuth(path, requestInit.method)) {
        authRefreshTried = true;
        const refreshed = await refreshAccessToken(timeoutMs, signal);
        if (refreshed) {
          Object.assign(headers, buildAuthHeaders(), (requestInit.headers as Record<string, string> | undefined) ?? {});
          continue;
        }
      }
      const error = await responseError(response);
      if (attemptNumber < attempts && shouldRetryResponse(requestInit.method, error)) {
        attempt += 1;
        await waitForRetry(error.retryAfterMs ?? retryDelayMs(attemptNumber - 1), signal);
        continue;
      }
      recordApiTelemetry(path, method, error.status, attemptNumber, started, "http_error");
      throw error;
    } catch (error) {
      lastError = normalizeTransportError(error, signal);
      if (attemptNumber < attempts && lastError instanceof ApiTransportError && lastError.kind === "network" && isReadMethod(requestInit.method)) {
        attempt += 1;
        await waitForRetry(retryDelayMs(attemptNumber - 1), signal);
        continue;
      }
      if (!(lastError instanceof ApiError)) {
        recordApiTelemetry(path, method, undefined, attemptNumber, started, lastError instanceof ApiTransportError ? lastError.kind : "error");
      }
      throw lastError;
    }
  }
  throw lastError;
}

function recordApiTelemetry(path: string, method: string, statusCode: number | undefined, attempts: number, started: number, status: string): void {
  recordTelemetry({
    kind: "api",
    name: "request",
    status,
    durationMs: Math.round(performance.now() - started),
    meta: {
      method,
      path: redactPath(path),
      status_code: statusCode ?? null,
      attempts,
    },
  });
}

function redactPath(path: string): string {
  return path.split("?")[0];
}

export function requestOperation<T>(name: ApiOperationName, options: OperationPathOptions = {}, init: RequestJsonOptions = {}): Promise<T> {
  return requestJson<T>(operationPath(name, options), init);
}

export const apiClient = {
  monitorWorkspace: (view: "action" | "market" | "full" = "full", priorityLimit = 12, init: RequestJsonOptions = {}) =>
    requestOperation<MonitorWorkspaceResponse>(
      "monitorWorkspace",
      {
        query: {
          priority_limit: priorityLimit,
          sector_limit: 8,
          per_sector_limit: 8,
          hedge_limit: 4,
          view,
        },
      },
      init,
    ),
  paperWorkspace: (init: RequestJsonOptions = {}) => requestOperation<PaperWorkspaceResponse>("paperWorkspace", {}, init),
  strategyWorkspace: (init: RequestJsonOptions = {}) => requestOperation<StrategyWorkspaceResponse>("strategyWorkspace", {}, init),
  settingsWorkspace: (init: RequestJsonOptions = {}) => requestOperation<SettingsWorkspaceResponse>("settingsWorkspace", {}, init),
  backtestRuns: (limit?: number, init: RequestJsonOptions = {}) => requestOperation<BacktestRunsResponse>("backtestRuns", { query: { limit: limit as QueryValue } }, init),
  featureFlags: (init: RequestJsonOptions = {}) => requestOperation<FeatureFlagsResponse>("featureFlags", {}, init),
  analyzeSymbol: (payload: unknown, init: RequestJsonOptions = {}) =>
    requestOperation<AnalyzeSymbolResponse>("analyzeSymbol", {}, { ...init, method: "POST", body: JSON.stringify(payload) }),
  analyzeBatch: (payload: unknown, queue = false, init: RequestJsonOptions = {}) =>
    requestOperation<AnalyzeBatchResponse>("analyzeBatch", { query: { queue } }, { ...init, method: "POST", body: JSON.stringify(payload) }),
  quote: (symbol: string, init: RequestJsonOptions = {}) => requestOperation<QuoteResponse>("quote", { path: { symbol } }, init),
  kline: (symbol: string, period = "daily", limit = 120, init: RequestJsonOptions = {}) => requestOperation<KlineResponse>("kline", { path: { symbol }, query: { period, limit } }, init),
  stockKeyLevels: (symbol: string, init: RequestJsonOptions = {}) => requestOperation<StockKeyLevelsResponse>("stockKeyLevels", { path: { symbol } }, init),
  marketIntradayAnomaly: (symbol: string, init: RequestJsonOptions = {}) => requestOperation<IntradayAnomalyResponse>("marketIntradayAnomaly", { path: { symbol } }, init),
  lowBuyScreener: (query: Record<string, QueryValue | QueryValue[]> = {}, init: RequestJsonOptions = {}) => requestOperation<LowBuyScreenerResponse>("lowBuyScreener", { query }, init),
  lowBuyPriorityBoard: (limit = 12, strategyVariant: StrategyVariant = "baseline", refresh: "cache" | "async" | "sync" = "cache", init: RequestJsonOptions = {}) =>
    requestOperation<LowBuyPriorityBoardResponse>("lowBuyPriorityBoard", {
      query: { limit: priorityBoardLimit(limit), refresh, strategy_variant: strategyVariant },
    }, init),
  lowBuyQuotes: (symbols: string[] = [], strategy?: string, init: RequestJsonOptions = {}) => requestOperation<LowBuyQuotesResponse>("lowBuyQuotes", { query: { symbols, strategy } }, init),
  lowBuyStrategies: (init: RequestJsonOptions = {}) => requestOperation<LowBuyStrategiesResponse>("lowBuyStrategies", {}, init),
  strategiesMeta: (init: RequestJsonOptions = {}) => requestOperation<StrategyMetaResponse>("strategiesMeta", {}, init),
  paperAccount: (init: RequestJsonOptions = {}) => requestOperation<PaperAccountResponse>("paperAccount", {}, init),
  paperOrders: (limit = 50, init: RequestJsonOptions = {}) => requestOperation<PaperOrdersResponse>("paperOrders", { query: { limit } }, init),
  paperPositions: (init: RequestJsonOptions = {}) => requestOperation<PaperPositionsResponse>("paperPositions", {}, init),
  paperPerformanceDashboard: (days = 30, init: RequestJsonOptions = {}) => requestOperation<PaperPerformanceDashboardResponse>("paperPerformanceDashboard", { query: { days } }, init),
  paperTrades: (limit = 50, init: RequestJsonOptions = {}) => requestOperation<PaperTradesResponse>("paperTrades", { query: { limit } }, init),
  paperRiskEvents: (init: RequestJsonOptions = {}) => requestOperation<PaperRiskEventsResponse>("paperRiskEvents", {}, init),
  paperAutoTradingStatus: (init: RequestJsonOptions = {}) => requestOperation<PaperAutoTradingStatusResponse>("paperAutoTradingStatus", {}, init),
  paperAutoTradingRuns: (limit = 20, init: RequestJsonOptions = {}) => requestOperation<PaperAutoTradingRunsResponse>("paperAutoTradingRuns", { query: { limit } }, init),
  strategyTrackingItems: (query: Record<string, QueryValue | QueryValue[]> = {}, init: RequestJsonOptions = {}) => requestOperation<StrategyTrackingItemsResponse>("strategyTrackingItems", { query }, init),
  strategyTrackingDetail: (itemId: string | number, init: RequestJsonOptions = {}) =>
    requestOperation<StrategyTrackingDetailResponse>("strategyTrackingDetail", { path: { item_id: itemId } }, init),
  strategyTrackingSummary: (query: Record<string, QueryValue | QueryValue[]> = {}, init: RequestJsonOptions = {}) => requestOperation<StrategyTrackingSummaryResponse>("strategyTrackingSummary", { query }, init),
  strategyTrackingPerformance: (query: Record<string, QueryValue | QueryValue[]> = {}, init: RequestJsonOptions = {}) =>
    requestOperation<StrategyTrackingPerformanceResponse>("strategyTrackingPerformance", { query }, init),
  strategyTrackingHoldingAnalysis: (query: Record<string, QueryValue | QueryValue[]> = {}, init: RequestJsonOptions = {}) =>
    requestOperation<StrategyTrackingHoldingAnalysisResponse>("strategyTrackingHoldingAnalysis", { query }, init),
  strategyTrackingReview: (query: Record<string, QueryValue | QueryValue[]> = {}, init: RequestJsonOptions = {}) => requestOperation<StrategyTrackingReviewResponse>("strategyTrackingReview", { query }, init),
  tradeJournal: (query: Record<string, QueryValue | QueryValue[]> = {}, init: RequestJsonOptions = {}) => requestOperation<TradeJournalResponse>("tradeJournal", { query }, init),
  relativeStrength: (limit = 30, init: RequestJsonOptions = {}) => requestOperation<RelativeStrengthResponse>("relativeStrength", { query: { limit } }, init),
  backtestRunDetail: (runId: string | number, init: RequestJsonOptions = {}) => requestOperation<BacktestRunDetailResponse>("backtestRunDetail", { path: { run_id: runId } }, init),
  backtestRunEquity: (runId: string | number, init: RequestJsonOptions = {}) => requestOperation<BacktestRunEquityResponse>("backtestRunEquity", { path: { run_id: runId } }, init),
  backtestRunTrades: (runId: string | number, init: RequestJsonOptions = {}) => requestOperation<BacktestRunTradesResponse>("backtestRunTrades", { path: { run_id: runId } }, init),
  dataQualityCoverage: (init: RequestJsonOptions = {}) => requestOperation<DataQualityCoverageResponse>("dataQualityCoverage", {}, init),
  dataQualitySla: (init: RequestJsonOptions = {}) => requestOperation<DataQualitySlaResponse>("dataQualitySla", {}, init),
  runtimeTasks: (init: RequestJsonOptions = {}) => requestOperation<RuntimeTasksResponse>("runtimeTasks", {}, init),
  runtimeTaskSummary: (init: RequestJsonOptions = {}) => requestOperation<RuntimeTaskSummaryResponse>("runtimeTaskSummary", {}, init),
  adminMetrics: (init: RequestJsonOptions = {}) => requestOperation<AdminMetricsResponse>("adminMetrics", {}, init),
  adminTasks: (init: RequestJsonOptions = {}) => requestOperation<AdminTasksResponse>("adminTasks", {}, init),
  settings: (init: RequestJsonOptions = {}) => requestOperation<SettingsResponse>("settings", {}, init),
  settingsRuntime: (init: RequestJsonOptions = {}) => requestOperation<SettingsRuntimeResponse>("settingsRuntime", {}, init),
  sectorExclusions: (init: RequestJsonOptions = {}) => requestOperation<SectorExclusionsResponse>("sectorExclusions", {}, init),
  factorWeights: (init: RequestJsonOptions = {}) => requestOperation<FactorWeightsResponse>("factorWeights", {}, init),
  featureFlagAudit: (init: RequestJsonOptions = {}) => requestOperation<FeatureFlagAuditResponse>("featureFlagAudit", {}, init),
  quantParameters: (init: RequestJsonOptions = {}) => requestOperation<QuantParametersResponse>("quantParameters", {}, init),
};

function priorityBoardLimit(limit: number): number {
  return Math.min(Math.max(Math.trunc(limit), 1), 30);
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  if (typeof navigator !== "undefined" && "onLine" in navigator && navigator.onLine === false) {
    throw new ApiTransportError("offline", "网络离线，已暂停请求");
  }
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort("timeout"), timeoutMs);
  const upstreamSignal = init.signal;
  const abortFromUpstream = () => controller.abort(upstreamSignal?.reason ?? "aborted");
  if (upstreamSignal?.aborted) abortFromUpstream();
  else upstreamSignal?.addEventListener("abort", abortFromUpstream, { once: true });
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    globalThis.clearTimeout(timeout);
    upstreamSignal?.removeEventListener("abort", abortFromUpstream);
  }
}

async function responseError(response: Response): Promise<ApiError> {
  const body = await response.text();
  let detail: unknown;
  try {
    detail = body ? JSON.parse(body) : undefined;
  } catch {
    detail = body;
  }
  return new ApiError(response.status, detail, undefined, parseRetryAfter(response.headers.get("Retry-After")));
}

function retryAttempts(method: string | undefined, retry: boolean | number | undefined): number {
  if (!isReadMethod(method)) return 1;
  if (typeof retry === "number") return Math.max(1, Math.min(Math.trunc(retry) + 1, 3));
  if (retry === false) return 1;
  return 2;
}

function shouldRetryResponse(method: string | undefined, error: ApiError): boolean {
  return isReadMethod(method) && RETRYABLE_READ_STATUSES.has(error.status);
}

function isReadMethod(method: string | undefined): boolean {
  return !method || method === "GET" || method === "HEAD";
}

function shouldRefreshAuth(path: string, method: string | undefined): boolean {
  if (!isReadMethod(method)) return false;
  if (path === "/api/auth/me") return true;
  return !path.startsWith("/api/auth/");
}

async function refreshAccessToken(timeoutMs: number, signal?: AbortSignal | null): Promise<boolean> {
  const refreshToken = getAuthRefreshToken();
  if (!refreshToken) return false;
  try {
    const response = await fetchWithTimeout(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal,
    }, timeoutMs);
    if (!response.ok) return false;
    const result = (await response.json()) as AuthTokenResponse;
    setAuthAccessToken(result.access_token);
    setAuthRefreshToken(result.refresh_token, currentRefreshTokenRemembered());
    recordTelemetry({ kind: "api", name: "auth-refresh", status: "ok", meta: { path: "/api/auth/refresh" } });
    return true;
  } catch {
    recordTelemetry({ kind: "api", name: "auth-refresh", status: "failed", meta: { path: "/api/auth/refresh" } });
    return false;
  }
}

function normalizeTransportError(error: unknown, signal: AbortSignal | null | undefined): unknown {
  if (error instanceof ApiError || error instanceof ApiTransportError) return error;
  if (error instanceof DOMException && error.name === "AbortError") {
    if (signal?.aborted) return new ApiTransportError("aborted", "请求已取消");
    return new ApiTransportError("timeout", "请求超时，请稍后重试");
  }
  if (typeof navigator !== "undefined" && "onLine" in navigator && navigator.onLine === false) {
    return new ApiTransportError("offline", "网络离线，已暂停请求");
  }
  if (error instanceof Error) return new ApiTransportError("network", error.message || "网络请求失败");
  return new ApiTransportError("network", "网络请求失败");
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return capRetryDelay(seconds * 1000);
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return undefined;
  return capRetryDelay(timestamp - Date.now());
}

function retryDelayMs(attempt: number): number {
  return 300 * 2 ** attempt;
}

function capRetryDelay(ms: number): number {
  return Math.min(Math.max(0, ms), MAX_RETRY_AFTER_MS);
}

function waitForRetry(ms: number, signal?: AbortSignal | null): Promise<void> {
  if (signal?.aborted) return Promise.reject(new ApiTransportError("aborted", "请求已取消"));
  return new Promise((resolve, reject) => {
    const timeout = globalThis.setTimeout(done, ms);
    const abort = () => done(new ApiTransportError("aborted", "请求已取消"));
    function done(error?: ApiTransportError) {
      globalThis.clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
      if (error) reject(error);
      else resolve();
    }
    signal?.addEventListener("abort", abort, { once: true });
  });
}
