import { invalidateCache, request } from "./base";

export type BacktestStatus = "pending" | "queued" | "running" | "completed" | "succeeded" | "failed" | "cancelled" | "deleted" | "timeout";

export type BacktestExecutionModel = "open_price" | "close_price" | "next_open" | "vwap" | "market_impact";

export interface BacktestRiskLimits {
  max_position_pct: number;
  max_positions: number;
  max_daily_loss_pct?: number | null;
  max_single_order_pct?: number | null;
  min_cash_reserve?: number | null;
}

export interface BacktestCreateRequest {
  name: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  strategies: string[];
  execution_model: BacktestExecutionModel;
  risk_limits: BacktestRiskLimits;
  benchmark?: string;
  param_overrides?: Record<string, Record<string, number | string | boolean | null>>;
}

export interface BacktestSubmitResponse {
  run_id?: number;
  id?: number;
  status: BacktestStatus;
  message?: string;
}

export interface BacktestAttributionBucket {
  bucket: string;
  label?: string;
  signal_count?: number | null;
  filled_order_count?: number | null;
  rejected_order_count?: number | null;
  trade_count?: number | null;
  win_count?: number | null;
  win_rate_pct?: number | null;
  avg_return_pct?: number | null;
  net_pnl?: number | null;
  fee_amount?: number | null;
  contribution_pct?: number | null;
  return_pct?: number | null;
  sharpe?: number | null;
}

export interface BacktestAttribution {
  version?: string;
  strategy?: BacktestAttributionBucket[];
  by_strategy?: BacktestAttributionBucket[];
  industry?: BacktestAttributionBucket[];
  market_state?: BacktestAttributionBucket[];
  data_quality?: BacktestAttributionBucket[];
  failure_reasons?: BacktestAttributionBucket[];
  data_quality_summary?: Record<string, unknown>;
  notes?: string[];
}

export interface BacktestSummaryMetrics {
  total_return_pct?: number | null;
  benchmark_return_pct?: number | null;
  benchmark_alpha_pct?: number | null;
  annual_return_pct?: number | null;
  sharpe?: number | null;
  sharpe_ratio?: number | null;
  sortino?: number | null;
  sortino_ratio?: number | null;
  calmar?: number | null;
  calmar_ratio?: number | null;
  information_ratio?: number | null;
  max_drawdown_pct?: number | null;
  win_rate_pct?: number | null;
  total_trades?: number | null;
  trade_count?: number | null;
  profit_factor?: number | null;
  attribution?: BacktestAttribution | null;
}

export interface BacktestRunSummary {
  id: number;
  name: string;
  status: BacktestStatus;
  progress?: number | null;
  progress_pct?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  initial_capital?: number | null;
  initial_cash?: number | null;
  final_equity?: number | null;
  strategies?: string[];
  strategy_keys?: string[];
  execution_model?: string | null;
  benchmark?: string | null;
  benchmark_symbol?: string | null;
  risk_limits?: Partial<BacktestRiskLimits> | null;
  summary?: BacktestSummaryMetrics | null;
  attribution?: BacktestAttribution | null;
  result?: {
    attribution?: BacktestAttribution | null;
    metrics?: BacktestSummaryMetrics | null;
    summary?: BacktestSummaryMetrics | null;
    [key: string]: unknown;
  } | null;
  params?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
}

export type BacktestRunDetail = BacktestRunSummary;

export interface BacktestListResponse {
  items: BacktestRunSummary[];
  total: number;
  page?: number;
  page_size?: number;
  limit?: number;
  offset?: number;
}

export interface EquityPoint {
  date: string;
  nav: number;
  benchmark_nav?: number | null;
  drawdown_pct?: number | null;
  total_value?: number | null;
}

export interface BacktestEquityResponse {
  run_id?: number;
  items?: Array<EquityPoint & RawRecord>;
  points?: EquityPoint[];
}

export interface BacktestTrade {
  id: number;
  trade_date: string;
  symbol: string;
  side: "buy" | "sell" | string;
  quantity: number;
  price: number;
  gross_amount?: number | null;
  commission?: number | null;
  stamp_tax?: number | null;
  transfer_fee?: number | null;
  net_amount: number;
  strategy: string;
  strategy_key?: string | null;
  entry_date?: string | null;
  entry_price?: number | null;
  holding_days?: number | null;
  return_pct?: number | null;
  pnl_pct?: number | null;
  exit_reason?: string | null;
}

export interface BacktestTradesResponse {
  items: BacktestTrade[];
  total: number;
  page?: number;
  page_size?: number;
  limit?: number;
  offset?: number;
}

export type BacktestParamValue = number | string | boolean | null;
export type BacktestParamGrid = Record<string, BacktestParamValue[]>;

export interface BacktestOptimizationCreateRequest {
  name: string;
  strategy: string;
  param_grid: BacktestParamGrid;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  optimization_target?: string;
  initial_capital: number;
  execution_model: BacktestExecutionModel;
}

export interface BacktestOptimizationCandidate {
  rank?: number | null;
  params?: Record<string, BacktestParamValue> | null;
  total_return_pct?: number | null;
  win_rate_pct?: number | null;
  stop_loss_rate_pct?: number | null;
  max_drawdown_pct?: number | null;
  profit_factor?: number | null;
  sharpe?: number | null;
  sharpe_ratio?: number | null;
  sample?: "is" | "oos" | string | null;
  is_oos?: boolean | null;
}

export interface BacktestOptimizationSummary {
  id: number;
  name: string;
  strategy: string;
  status: BacktestStatus;
  progress?: number | null;
  progress_pct?: number | null;
  total_combinations?: number | null;
  completed_combinations?: number | null;
  best_params?: Record<string, BacktestParamValue> | null;
  best_is_score?: number | null;
  best_is_metrics?: BacktestSummaryMetrics | null;
  best_oos_score?: number | null;
  best_oos_metrics?: BacktestSummaryMetrics | null;
  oos_downgrade?: boolean | number | null;
  oos_downgrade_reason?: string | null;
  candidates?: BacktestOptimizationCandidate[];
  train_start?: string | null;
  train_end?: string | null;
  test_start?: string | null;
  test_end?: string | null;
  optimization_target?: string | null;
  search_method?: string | null;
  duration_seconds?: number | null;
  error_message?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export type BacktestOptimizationDetail = BacktestOptimizationSummary;

export interface BacktestOptimizationListResponse {
  items: BacktestOptimizationSummary[];
  total: number;
  page?: number;
  page_size?: number;
  limit?: number;
  offset?: number;
}

export interface BacktestValidationCreateRequest {
  name: string;
  strategy: string;
  start_date: string;
  end_date: string;
  window_count?: number;
  train_ratio?: number;
  optimization_target?: string;
  initial_capital: number;
  execution_model: BacktestExecutionModel;
  param_grid?: BacktestParamGrid;
}

export interface BacktestValidationWindow {
  index?: number | null;
  window_index?: number | null;
  train_start?: string | null;
  train_end?: string | null;
  test_start?: string | null;
  test_end?: string | null;
  train_sharpe?: number | null;
  is_sharpe?: number | null;
  test_sharpe?: number | null;
  oos_sharpe?: number | null;
  test_return_pct?: number | null;
  oos_return_pct?: number | null;
  test_max_drawdown_pct?: number | null;
  oos_max_drawdown_pct?: number | null;
  best_params?: Record<string, BacktestParamValue> | null;
  pbo_flag?: boolean | null;
}

export interface BacktestValidationSummary {
  id: number;
  name: string;
  strategy: string;
  status: BacktestStatus;
  progress?: number | null;
  progress_pct?: number | null;
  window_count?: number | null;
  optimization_target?: string | null;
  oos_pass_rate?: number | null;
  avg_oos_sharpe?: number | null;
  avg_is_sharpe?: number | null;
  pbo_risk?: "low" | "medium" | "high" | string | null;
  downgrade_review?: boolean | number | null;
  downgrade_review_required?: boolean | number | null;
  stability_conclusion?: string | null;
  windows?: BacktestValidationWindow[];
  duration_seconds?: number | null;
  error_message?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export type BacktestValidationDetail = BacktestValidationSummary;

export interface BacktestValidationListResponse {
  items: BacktestValidationSummary[];
  total: number;
  page?: number;
  page_size?: number;
  limit?: number;
  offset?: number;
}

export interface BacktestCompareItem {
  run_id: number;
  name?: string | null;
  status?: BacktestStatus;
  strategy?: string | null;
  strategies?: string[];
  metrics?: BacktestSummaryMetrics | null;
  equity?: EquityPoint[];
}

export interface BacktestCompareResponse {
  items: BacktestCompareItem[];
  run_ids?: number[];
}

export interface BacktestMonthlyReturn {
  month: string;
  return_pct?: number | null;
  benchmark_return_pct?: number | null;
  alpha_pct?: number | null;
  trade_count?: number | null;
}

export interface BacktestMonthlyReturnsResponse {
  run_id?: number;
  items: BacktestMonthlyReturn[];
}

export type BacktestAttributionResponse = BacktestAttribution;

export interface BacktestStrategyCorrelationResponse {
  run_id?: number;
  strategies: string[];
  matrix: number[][];
}

type BacktestListParams = {
  page?: number;
  pageSize?: number;
  limit?: number;
  offset?: number;
  status?: BacktestStatus | "all";
};

type BacktestTradesParams = {
  page?: number;
  pageSize?: number;
  limit?: number;
  offset?: number;
};

type RawRecord = Record<string, unknown>;

type ResearchListParams = BacktestListParams;

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
