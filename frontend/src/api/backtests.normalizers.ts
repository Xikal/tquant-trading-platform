import { normalizeBacktestStatus } from "./backtests.helpers";
import type {
  BacktestAttributionResponse,
  BacktestCompareResponse,
  BacktestEquityResponse,
  BacktestListResponse,
  BacktestOptimizationCandidate,
  BacktestOptimizationDetail,
  BacktestOptimizationListResponse,
  BacktestOptimizationSummary,
  BacktestParamValue,
  BacktestRunDetail,
  BacktestRunSummary,
  BacktestSummaryMetrics,
  BacktestTrade,
  BacktestTradesResponse,
  BacktestValidationDetail,
  BacktestValidationListResponse,
  BacktestValidationSummary,
  BacktestValidationWindow,
  RawRecord,
} from "./backtestTypes";

export function normalizeBacktestListResponse(payload: BacktestListResponse): BacktestListResponse {
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

export function normalizeBacktestRun<T extends BacktestRunSummary | BacktestRunDetail>(run: T): T {
  const params = isRecord(run.params) ? run.params : {};
  const riskLimits = isRecord(params.risk_limits) ? params.risk_limits : null;
  const result = isRecord(run.result) ? run.result : {};
  const resultMetrics = isRecord(result.metrics) ? result.metrics : null;
  const resultSummary = isRecord(result.summary) ? result.summary : null;
  const summary = normalizeBacktestSummary({
    runSummary: run.summary,
    resultMetrics,
    resultSummary,
    initialCapital: run.initial_capital ?? run.initial_cash,
    finalEquity: run.final_equity,
  });
  return {
    ...run,
    status: normalizeBacktestStatus(run.status),
    progress: numberOrNull(run.progress ?? run.progress_pct),
    strategies: run.strategies ?? run.strategy_keys ?? [],
    initial_capital: numberOrNull(run.initial_capital ?? run.initial_cash),
    benchmark: stringOrNull(run.benchmark ?? run.benchmark_symbol),
    execution_model: stringOrNull(run.execution_model ?? params.execution_model),
    risk_limits: run.risk_limits ?? riskLimits,
    summary,
    completed_at: run.completed_at ?? run.finished_at,
  };
}

export function normalizeEquityPoints(payload: BacktestEquityResponse) {
  const source = payload.items ?? payload.points ?? [];
  const firstEquity = source
    .map((point) => {
      const raw = point as unknown as RawRecord;
      return numberOrNull(raw.equity ?? raw.total_value ?? point.nav);
    })
    .find((value): value is number => typeof value === "number" && value > 0);
  let benchmarkNav = 1;
  return source.map((point, index) => {
    const raw = point as unknown as RawRecord;
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

export function normalizeTradesResponse(payload: BacktestTradesResponse): BacktestTradesResponse {
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

export function normalizeResearchListResponse<T, R extends {
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

export function normalizeOptimization<T extends BacktestOptimizationSummary | BacktestOptimizationDetail>(item: T): T {
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

export function normalizeValidation<T extends BacktestValidationSummary | BacktestValidationDetail>(item: T): T {
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

export function normalizeCompareResponse(payload: BacktestCompareResponse): BacktestCompareResponse {
  return {
    ...payload,
    items: (payload.items ?? []).map((item) => ({
      ...item,
      status: item.status ? normalizeBacktestStatus(item.status) : item.status,
      equity: item.equity ?? [],
    })),
  };
}

export function normalizeAttributionResponse(payload: BacktestAttributionResponse): BacktestAttributionResponse {
  return payload;
}

function normalizeBacktestSummary({
  runSummary,
  resultMetrics,
  resultSummary,
  initialCapital,
  finalEquity,
}: {
  runSummary?: BacktestSummaryMetrics | null;
  resultMetrics?: RawRecord | null;
  resultSummary?: RawRecord | null;
  initialCapital?: number | null;
  finalEquity?: number | null;
}): BacktestSummaryMetrics | null {
  const merged: RawRecord = {};
  for (const source of [resultSummary, resultMetrics, runSummary]) {
    if (isRecord(source)) Object.assign(merged, source);
  }
  normalizeMetricAlias(merged, "total_return_pct", ["total_return", "return_pct"]);
  normalizeMetricAlias(merged, "win_rate_pct", ["win_rate"]);
  normalizeMetricAlias(merged, "max_drawdown_pct", ["max_drawdown"]);
  normalizeMetricAlias(merged, "trade_count", ["total_trades"]);
  const initial = numberOrNull(initialCapital ?? merged.initial_cash ?? merged.initial_capital);
  const finalValue = numberOrNull(finalEquity ?? merged.final_equity);
  if (typeof initial === "number" && initial > 0 && typeof finalValue === "number" && finalValue > 0) {
    merged.initial_cash = initial;
    merged.final_equity = finalValue;
    const computedReturn = ((finalValue - initial) / initial) * 100;
    if (!Number.isFinite(numberOrNull(merged.total_return_pct) ?? NaN) || Math.abs(computedReturn) > 0.0001) {
      merged.total_return_pct = computedReturn;
    }
  }
  return Object.keys(merged).length ? (merged as BacktestSummaryMetrics) : null;
}

function normalizeMetricAlias(target: RawRecord, canonical: string, aliases: string[]): void {
  if (typeof target[canonical] === "number") return;
  for (const alias of aliases) {
    const value = numberOrNull(target[alias]);
    if (typeof value !== "number") continue;
    target[canonical] = alias === "win_rate" && Math.abs(value) <= 1 ? value * 100 : value;
    return;
  }
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
