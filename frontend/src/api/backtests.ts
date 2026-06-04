import { invalidateCache } from "./base";
import {
  buildListQuery,
  normalizeMonthlyReturns,
  normalizeStrategyCorrelation,
  toBackendStatus,
} from "./backtests.helpers";
import {
  normalizeBacktestListResponse,
  normalizeBacktestRun,
  normalizeCompareResponse,
  normalizeEquityPoints,
  normalizeOptimization,
  normalizeResearchListResponse,
  normalizeTradesResponse,
  normalizeValidation,
} from "./backtests.normalizers";
import { apiClient } from "./httpClient";
import type { RuntimeTaskOut } from "./runtimeTasks";
import type { paths } from "../generated/api-types";

import type {
  BacktestStatus,
  BacktestExecutionModel,
  BacktestRiskLimits,
  BacktestCreateRequest,
  BacktestSubmitResponse,
  BacktestSummaryMetrics,
  BacktestRunSummary,
  BacktestRunDetail,
  BacktestListResponse,
  EquityPoint,
  BacktestEquityResponse,
  BacktestTrade,
  BacktestTradesResponse,
  BacktestParamGrid,
  BacktestOptimizationCreateRequest,
  BacktestOptimizationSummary,
  BacktestOptimizationDetail,
  BacktestOptimizationListResponse,
  BacktestValidationCreateRequest,
  BacktestValidationSummary,
  BacktestValidationDetail,
  BacktestValidationListResponse,
  BacktestCompareItem,
  BacktestCompareResponse,
  BacktestMonthlyReturnsResponse,
  BacktestAttributionResponse,
  BacktestStrategyCorrelationResponse,
  PortfolioOptimizationResponse,
  PositionPolicyResearchResponse,
  LiveBacktestComparisonResponse,
  BacktestListParams,
  BacktestTradesParams,
  BacktestVerdictThresholdsResponse,
  StrategyImprovementReportResponse,
  EtfT0BacktestRequest,
  EtfT0BacktestResponse,
  EtfT0ResearchRequest,
  EtfT0ResearchResponse,
  ResearchListParams
} from "./backtestTypes";

export type * from "./backtestTypes";

const request = apiClient.request;

type ApiOperation<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends infer Operation ? Operation : never;

type ApiJson<Path extends keyof paths, Method extends keyof paths[Path]> =
  ApiOperation<Path, Method> extends { responses: { 200: { content: { "application/json": infer Payload } } } } ? Payload : never;

type ApiRequestBody<Path extends keyof paths, Method extends keyof paths[Path]> =
  paths[Path][Method] extends { requestBody: { content: { "application/json": infer Payload } } } ? Payload : never;

type BacktestRunCreateDto = ApiRequestBody<"/api/backtests", "post">;
type BacktestRunDetailDto = ApiJson<"/api/backtests", "post">;
type BacktestRunListDto = ApiJson<"/api/backtests", "get">;
type BacktestEquityDto = ApiJson<"/api/backtests/{run_id}/equity", "get">;
type BacktestTradesDto = ApiJson<"/api/backtests/{run_id}/trades", "get">;

function toBacktestRunCreateDto(payload: BacktestCreateRequest): BacktestRunCreateDto {
  return {
    benchmark: payload.benchmark ?? "000300",
    data_version: "",
    end_date: payload.end_date,
    engine_version: "backtest-v2",
    fee_model_version: "",
    initial_capital: payload.initial_capital,
    max_duration_seconds: 1800,
    name: payload.name,
    params: {
      execution_model: payload.execution_model,
      risk_limits: payload.risk_limits,
      param_overrides: payload.param_overrides ?? {},
    },
    resource_tier: payload.resource_tier ?? "full",
    slippage_bps: 8,
    start_date: payload.start_date,
    strategies: payload.strategies,
    strategy_version: "",
  };
}

export const backtestsApi = {
  createBacktest: (payload: BacktestCreateRequest) =>
    request<BacktestRunDetailDto>("/backtests", {
      method: "POST",
      body: JSON.stringify(toBacktestRunCreateDto(payload)),
    }).then((result) => {
      invalidateCache(["/backtests"]);
      return result as BacktestSubmitResponse;
    }),

  listBacktests: ({ page, pageSize, limit, offset, status }: BacktestListParams = {}) => {
    const params = new URLSearchParams();
    const resolvedLimit = limit ?? pageSize ?? 20;
    const resolvedOffset = offset ?? ((page ?? 1) - 1) * resolvedLimit;
    params.set("limit", String(resolvedLimit));
    params.set("offset", String(Math.max(0, resolvedOffset)));
    if (status && status !== "all") {
      params.set("status", toBackendStatus(status));
    }
    return request<BacktestRunListDto>(`/backtests?${params.toString()}`).then((payload) =>
      normalizeBacktestListResponse(payload as BacktestListResponse)
    );
  },

  getBacktest: (runId: number) => request<BacktestRunDetailDto>(`/backtests/${runId}`).then((payload) => normalizeBacktestRun(payload as BacktestRunDetail)),

  getBacktestEquity: (runId: number) =>
    request<BacktestEquityDto>(`/backtests/${runId}/equity`).then((payload) => normalizeEquityPoints(payload as BacktestEquityResponse)),

  getBacktestTrades: (
    runId: number,
    { page, pageSize, limit, offset }: BacktestTradesParams = {}
  ) => {
    const params = new URLSearchParams();
    const resolvedLimit = limit ?? pageSize ?? 50;
    const resolvedOffset = offset ?? ((page ?? 1) - 1) * resolvedLimit;
    params.set("limit", String(resolvedLimit));
    params.set("offset", String(Math.max(0, resolvedOffset)));
    return request<BacktestTradesDto>(`/backtests/${runId}/trades?${params.toString()}`).then((payload) => normalizeTradesResponse(payload as unknown as BacktestTradesResponse));
  },

  cancelBacktest: (runId: number) =>
    request<BacktestSubmitResponse>(`/backtests/${runId}/cancel`, {
      method: "POST",
      body: JSON.stringify({}),
    }).then((result) => {
      invalidateCache(["/backtests"]);
      return result;
    }),

  deleteBacktest: (runId: number) =>
    request<BacktestSubmitResponse>(`/backtests/${runId}`, {
      method: "DELETE",
    }).then((result) => {
      invalidateCache(["/backtests"]);
      return result;
    }),

  listOptimizations: (params?: ResearchListParams) =>
    request<BacktestOptimizationListResponse>(`/backtests/optimize?${buildListQuery(params).toString()}`)
      .then((payload) => normalizeResearchListResponse<BacktestOptimizationSummary, BacktestOptimizationListResponse>(payload, normalizeOptimization)),

  createOptimization: (payload: BacktestOptimizationCreateRequest) =>
    request<BacktestSubmitResponse>("/backtests/optimize", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => {
      invalidateCache(["/backtests/optimize"]);
      return result;
    }),

  getOptimization: (optimizationId: number) =>
    request<BacktestOptimizationDetail>(`/backtests/optimize/${optimizationId}`).then(normalizeOptimization),

  cancelOptimization: (optimizationId: number) =>
    request<BacktestSubmitResponse>(`/backtests/optimize/${optimizationId}/cancel`, {
      method: "POST",
      body: JSON.stringify({}),
    }).then((result) => {
      invalidateCache(["/backtests/optimize"]);
      return result;
    }),

  deleteOptimization: (optimizationId: number) =>
    request<BacktestSubmitResponse>(`/backtests/optimize/${optimizationId}`, {
      method: "DELETE",
    }).then((result) => {
      invalidateCache(["/backtests/optimize"]);
      return result;
    }),

  listValidations: (params?: ResearchListParams) =>
    request<BacktestValidationListResponse>(`/backtests/validate?${buildListQuery(params).toString()}`)
      .then((payload) => normalizeResearchListResponse<BacktestValidationSummary, BacktestValidationListResponse>(payload, normalizeValidation)),

  createValidation: (payload: BacktestValidationCreateRequest) =>
    request<BacktestSubmitResponse>("/backtests/validate", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => {
      invalidateCache(["/backtests/validate"]);
      return result;
    }),

  getValidation: (validationId: number) =>
    request<BacktestValidationDetail>(`/backtests/validate/${validationId}`).then(normalizeValidation),

  cancelValidation: (validationId: number) =>
    request<BacktestSubmitResponse>(`/backtests/validate/${validationId}/cancel`, {
      method: "POST",
      body: JSON.stringify({}),
    }).then((result) => {
      invalidateCache(["/backtests/validate"]);
      return result;
    }),

  deleteValidation: (validationId: number) =>
    request<BacktestSubmitResponse>(`/backtests/validate/${validationId}`, {
      method: "DELETE",
    }).then((result) => {
      invalidateCache(["/backtests/validate"]);
      return result;
    }),

  promoteValidationStateParams: (validationId: number, activate = true) =>
    request<Record<string, unknown>>(`/backtests/validate/${validationId}/promote-state-params?activate=${String(activate)}`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  compareBacktests: (runIds: number[]) =>
    request<BacktestCompareResponse>("/backtests/compare", {
      method: "POST",
      body: JSON.stringify({ run_ids: runIds }),
    }).then(normalizeCompareResponse),

  getMonthlyReturns: (runId: number) =>
    request<BacktestMonthlyReturnsResponse>(`/backtests/${runId}/monthly-returns`).then(normalizeMonthlyReturns),

  getAttribution: (runId: number) =>
    request<BacktestAttributionResponse>(`/backtests/${runId}/attribution`),

  getStrategyCorrelation: (runId: number) =>
    request<BacktestStrategyCorrelationResponse>(`/backtests/${runId}/strategy-correlation`).then(normalizeStrategyCorrelation),

  getPortfolioOptimization: (runId: number, method: "hrp" | "risk_adjusted" | "markowitz" | "black_litterman" = "markowitz") =>
    request<RuntimeTaskOut>(`/backtests/${runId}/portfolio-optimization?method=${method}`),

  getLiveBacktestComparison: (accountId?: number, days = 60) => {
    const params = new URLSearchParams();
    params.set("days", String(days));
    if (accountId) params.set("account_id", String(accountId));
    return request<LiveBacktestComparisonResponse>(`/backtests/live-comparison?${params.toString()}`);
  },

  getPositionPolicyResearch: (runId: number) =>
    request<PositionPolicyResearchResponse>(`/backtests/${runId}/position-policy-research`),

  getVerdictThresholds: () =>
    request<BacktestVerdictThresholdsResponse>("/backtests/verdict-thresholds"),

  getStrategyImprovementReport: () =>
    request<StrategyImprovementReportResponse>("/backtests/strategy-improvement-report"),

  runEtfT0MinuteBacktest: (payload: EtfT0BacktestRequest) =>
    request<EtfT0BacktestResponse | RuntimeTaskOut>("/backtests/etf-t0-minute", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  runEtfT0Research: (payload: EtfT0ResearchRequest) =>
    request<EtfT0ResearchResponse | RuntimeTaskOut>("/backtests/etf-t0-research", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
