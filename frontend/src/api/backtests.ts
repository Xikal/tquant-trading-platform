import { invalidateCache } from "./base";
import { apiClient } from "./httpClient";

import type {
  BacktestStatus,
  BacktestExecutionModel,
  BacktestRiskLimits,
  BacktestCreateRequest,
  BacktestSubmitResponse,
  BacktestAttributionBucket,
  BacktestAttribution,
  BacktestSummaryMetrics,
  BacktestRunSummary,
  BacktestRunDetail,
  BacktestListResponse,
  EquityPoint,
  BacktestEquityResponse,
  BacktestTrade,
  BacktestTradesResponse,
  BacktestParamValue,
  BacktestParamGrid,
  BacktestOptimizationCreateRequest,
  BacktestOptimizationCandidate,
  BacktestOptimizationSummary,
  BacktestOptimizationDetail,
  BacktestOptimizationListResponse,
  BacktestValidationCreateRequest,
  BacktestValidationWindow,
  BacktestValidationSummary,
  BacktestValidationDetail,
  BacktestValidationListResponse,
  BacktestCompareItem,
  BacktestCompareResponse,
  BacktestMonthlyReturn,
  BacktestMonthlyReturnsResponse,
  BacktestAttributionResponse,
  BacktestStrategyCorrelationResponse,
  PortfolioOptimizationResponse,
  PositionPolicyResearchResponse,
  BacktestListParams,
  BacktestTradesParams,
  RawRecord,
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

  getPortfolioOptimization: (runId: number, method: "hrp" | "risk_adjusted" | "markowitz" = "markowitz") =>
    request<PortfolioOptimizationResponse>(`/backtests/${runId}/portfolio-optimization?method=${method}`),

  getPositionPolicyResearch: (runId: number) =>
    request<PositionPolicyResearchResponse>(`/backtests/${runId}/position-policy-research`),
};

function buildListQuery({ page, pageSize, limit, offset, status }: ResearchListParams = {}): URLSearchParams {
  const params = new URLSearchParams();
  const resolvedLimit = limit ?? pageSize ?? 20;
  const resolvedOffset = offset ?? ((page ?? 1) - 1) * resolvedLimit;
  params.set("limit", String(resolvedLimit));
  params.set("offset", String(Math.max(0, resolvedOffset)));
  if (status && status !== "all") {
    params.set("status", status);
  }
  return params;
}

function normalizeBacktestListResponse(payload: BacktestListResponse): BacktestListResponse {
  const limit = payload.limit ?? payload.page_size ?? payload.items?.length ?? 20;
  const offset = payload.offset ?? ((payload.page ?? 1) - 1) * limit;
  return {
    ...payload,
    limit,
    offset,
    page: payload.page ?? Math.floor(offset / Math.max(limit, 1)) + 1,
    page_size: payload.page_size ?? limit,
    items: (payload.items ?? []).map(normalizeBacktestRun),
  };
}

function normalizeBacktestRun<T extends BacktestRunSummary | BacktestRunDetail>(run: T): T {
  const params = isRecord(run.params) ? run.params : {};
  const riskLimits = isRecord(params.risk_limits) ? params.risk_limits : null;
  const result = isRecord(run.result) ? run.result : {};
  const resultMetrics = isRecord(result.metrics) ? result.metrics : null;
  const resultSummary = isRecord(result.summary) ? result.summary : null;
  return {
    ...run,
    status: normalizeBacktestStatus(run.status),
    progress: numberOrNull(run.progress ?? run.progress_pct),
    strategies: run.strategies ?? run.strategy_keys ?? [],
    initial_capital: numberOrNull(run.initial_capital ?? run.initial_cash),
    benchmark: stringOrNull(run.benchmark ?? run.benchmark_symbol),
    execution_model: stringOrNull(run.execution_model ?? params.execution_model),
    risk_limits: run.risk_limits ?? riskLimits,
    summary: run.summary ?? resultMetrics ?? resultSummary ?? null,
    completed_at: run.completed_at ?? run.finished_at,
  };
}

function normalizeBacktestStatus(status: BacktestStatus): BacktestStatus {
  return status;
}

function toBackendStatus(status: BacktestStatus): BacktestStatus {
  if (status === "pending") return "queued";
  if (status === "completed") return "succeeded";
  return status;
}

function normalizeEquityPoints(payload: BacktestEquityResponse): EquityPoint[] {
  const source = payload.items ?? payload.points ?? [];
  const firstEquity = source
    .map((point) => {
      const raw = point as unknown as RawRecord;
      return numberOrNull(raw.equity ?? raw.total_value ?? point.nav);
    })
    .find((value): value is number => typeof value === "number" && value > 0);
  let benchmarkNav = 1;
  return source.map((point, index) => {
    const raw = point as EquityPoint & RawRecord;
    const equityValue = numberOrNull(raw.equity ?? raw.total_value ?? raw.nav);
    if (index > 0 && typeof raw.benchmark_nav !== "number") {
      benchmarkNav *= 1 + numberOrDefault(raw.benchmark_return_pct, 0) / 100;
    }
    return {
      date: String(raw.date ?? raw.trade_date ?? ""),
      nav: numberOrDefault(raw.nav, firstEquity && equityValue ? equityValue / firstEquity : 0),
      benchmark_nav: numberOrNull(raw.benchmark_nav) ?? benchmarkNav,
      drawdown_pct: numberOrNull(raw.drawdown_pct),
      total_value: numberOrNull(raw.total_value ?? raw.equity),
    };
  });
}

function normalizeTradesResponse(payload: BacktestTradesResponse): BacktestTradesResponse {
  const limit = payload.limit ?? payload.page_size ?? payload.items?.length ?? 50;
  const offset = payload.offset ?? ((payload.page ?? 1) - 1) * limit;
  return {
    ...payload,
    limit,
    offset,
    page: payload.page ?? Math.floor(offset / Math.max(limit, 1)) + 1,
    page_size: payload.page_size ?? limit,
    items: (payload.items ?? []).map(normalizeTrade),
  };
}

function normalizeResearchListResponse<T, R extends {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
  limit?: number;
  offset?: number;
}>(payload: R, normalizeItem: (item: T) => T): R {
  const limit = payload.limit ?? payload.page_size ?? payload.items?.length ?? 20;
  const offset = payload.offset ?? ((payload.page ?? 1) - 1) * limit;
  return {
    ...payload,
    limit,
    offset,
    page: payload.page ?? Math.floor(offset / Math.max(limit, 1)) + 1,
    page_size: payload.page_size ?? limit,
    items: (payload.items ?? []).map(normalizeItem),
  };
}

function normalizeOptimization<T extends BacktestOptimizationSummary | BacktestOptimizationDetail>(item: T): T {
  const raw = item as T & RawRecord;
  const result = recordUnknown(raw.result);
  const bestIs = recordUnknown(raw.best_is ?? result?.best_is);
  const bestOos = recordUnknown(raw.best_oos ?? result?.best_oos);
  return {
    ...item,
    strategy: stringOrDefault(raw.strategy, stringOrDefault(raw.strategy_key, "")),
    status: normalizeBacktestStatus(item.status),
    progress: numberOrNull(item.progress ?? item.progress_pct),
    progress_pct: numberOrNull(item.progress_pct ?? item.progress),
    best_params: recordOrNull(raw.best_params ?? raw.best_params_json ?? bestOos?.params ?? bestIs?.params),
    best_is_score: numberOrNull(raw.best_is_score ?? bestIs?.score),
    best_is_metrics: metricsOrNull(raw.best_is_metrics ?? raw.best_is_metrics_json ?? bestIs?.metrics),
    best_oos_score: numberOrNull(raw.best_oos_score ?? bestOos?.score),
    best_oos_metrics: metricsOrNull(raw.best_oos_metrics ?? raw.best_oos_metrics_json ?? bestOos?.metrics),
    oos_downgrade: booleanOrNumber(raw.oos_downgrade ?? result?.oos_downgrade),
    optimization_target: stringOrNull(raw.optimization_target ?? result?.optimization_target),
    search_method: stringOrNull(raw.search_method ?? result?.search_method) ?? "grid",
    candidates: arrayOrEmpty<BacktestOptimizationCandidate>(
      raw.candidates ?? raw.candidates_json ?? result?.candidates
    ),
  };
}

function normalizeValidation<T extends BacktestValidationSummary | BacktestValidationDetail>(item: T): T {
  const raw = item as T & RawRecord;
  const result = recordUnknown(raw.result);
  return {
    ...item,
    strategy: stringOrDefault(raw.strategy, stringOrDefault(raw.strategy_key, "")),
    status: normalizeBacktestStatus(item.status),
    progress: numberOrNull(item.progress ?? item.progress_pct),
    progress_pct: numberOrNull(item.progress_pct ?? item.progress),
    window_count: numberOrNull(raw.window_count ?? result?.window_count),
    optimization_target: stringOrNull(raw.optimization_target ?? result?.optimization_target),
    oos_pass_rate: numberOrNull(raw.oos_pass_rate ?? result?.oos_pass_rate),
    avg_oos_sharpe: numberOrNull(raw.avg_oos_sharpe ?? result?.avg_oos_sharpe),
    avg_is_sharpe: numberOrNull(raw.avg_is_sharpe ?? result?.avg_is_sharpe),
    pbo_risk: stringOrNull(raw.pbo_risk ?? result?.pbo_risk),
    downgrade_review: booleanOrNumber(
      raw.downgrade_review
        ?? raw.downgrade_review_required
        ?? result?.downgrade_review
        ?? result?.downgrade_review_required
    ),
    stability_conclusion: stringOrNull(raw.stability_conclusion ?? result?.stability_conclusion),
    windows: arrayOrEmpty<BacktestValidationWindow>(raw.windows ?? raw.windows_json ?? result?.windows),
  };
}

function normalizeCompareResponse(payload: BacktestCompareResponse): BacktestCompareResponse {
  return {
    ...payload,
    items: (payload.items ?? []).map((item) => ({
      ...item,
      status: item.status ? normalizeBacktestStatus(item.status) : item.status,
      equity: item.equity ?? [],
    })),
  };
}

function normalizeMonthlyReturns(payload: BacktestMonthlyReturnsResponse): BacktestMonthlyReturnsResponse {
  return {
    ...payload,
    items: payload.items ?? [],
  };
}

function normalizeStrategyCorrelation(payload: BacktestStrategyCorrelationResponse): BacktestStrategyCorrelationResponse {
  return {
    ...payload,
    strategies: payload.strategies ?? [],
    matrix: payload.matrix ?? [],
  };
}

function normalizeTrade(trade: BacktestTrade): BacktestTrade {
  const raw = trade as BacktestTrade & RawRecord;
  const strategy = stringOrDefault(raw.strategy, stringOrDefault(raw.strategy_key, "--"));
  return {
    ...trade,
    trade_date: stringOrDefault(raw.trade_date, stringOrDefault(raw.date, "")),
    symbol: stringOrDefault(raw.symbol, ""),
    side: stringOrDefault(raw.side, ""),
    quantity: numberOrDefault(raw.quantity, 0),
    price: numberOrDefault(raw.price, 0),
    net_amount: numberOrDefault(raw.net_amount, 0),
    strategy,
    strategy_key: stringOrNull(raw.strategy_key),
    return_pct: numberOrNull(raw.return_pct ?? raw.pnl_pct),
    pnl_pct: numberOrNull(raw.pnl_pct),
  };
}

function stringOrDefault(value: unknown, fallback: string): string {
  return typeof value === "string" && value ? value : fallback;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

function numberOrDefault(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function recordOrNull(value: unknown): Record<string, BacktestParamValue> | null {
  const parsed = parseJsonMaybe(value);
  return isRecord(parsed) ? (parsed as Record<string, BacktestParamValue>) : null;
}

function recordUnknown(value: unknown): Record<string, unknown> | null {
  const parsed = parseJsonMaybe(value);
  return isRecord(parsed) ? parsed : null;
}

function metricsOrNull(value: unknown): BacktestSummaryMetrics | null {
  const parsed = parseJsonMaybe(value);
  return isRecord(parsed) ? (parsed as BacktestSummaryMetrics) : null;
}

function arrayOrEmpty<T>(value: unknown): T[] {
  const parsed = parseJsonMaybe(value);
  return Array.isArray(parsed) ? parsed as T[] : [];
}

function parseJsonMaybe(value: unknown): unknown {
  if (typeof value !== "string") {
    return value;
  }
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function booleanOrNumber(value: unknown): boolean | number | null {
  if (typeof value === "boolean") return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return null;
}
