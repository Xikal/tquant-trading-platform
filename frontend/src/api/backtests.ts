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

export const backtestsApi = {
  createBacktest: (payload: BacktestCreateRequest) =>
    request<BacktestSubmitResponse>("/backtests", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => {
      invalidateCache(["/backtests"]);
      return result;
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
    return request<BacktestListResponse>(`/backtests?${params.toString()}`).then(normalizeBacktestListResponse);
  },

  getBacktest: (runId: number) => request<BacktestRunDetail>(`/backtests/${runId}`).then(normalizeBacktestRun),

  getBacktestEquity: (runId: number) =>
    request<BacktestEquityResponse>(`/backtests/${runId}/equity`).then(normalizeEquityPoints),

  getBacktestTrades: (
    runId: number,
    { page, pageSize, limit, offset }: BacktestTradesParams = {}
  ) => {
    const params = new URLSearchParams();
    const resolvedLimit = limit ?? pageSize ?? 50;
    const resolvedOffset = offset ?? ((page ?? 1) - 1) * resolvedLimit;
    params.set("limit", String(resolvedLimit));
    params.set("offset", String(Math.max(0, resolvedOffset)));
    return request<BacktestTradesResponse>(`/backtests/${runId}/trades?${params.toString()}`).then(normalizeTradesResponse);
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
    request<PortfolioOptimizationResponse>(`/backtests/${runId}/portfolio-optimization?method=${method}`),

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
    request<EtfT0BacktestResponse>("/backtests/etf-t0-minute", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  runEtfT0Research: (payload: EtfT0ResearchRequest) =>
    request<EtfT0ResearchResponse>("/backtests/etf-t0-research", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
