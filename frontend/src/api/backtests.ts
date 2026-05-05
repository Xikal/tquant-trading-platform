import { invalidateCache, request } from "./base";

export type BacktestStatus = "pending" | "queued" | "running" | "completed" | "succeeded" | "failed" | "cancelled" | "deleted";

export type BacktestExecutionModel = "open_price" | "close_price" | "next_open" | "vwap";

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
}

export interface BacktestAttribution {
  version?: string;
  industry?: BacktestAttributionBucket[];
  market_state?: BacktestAttributionBucket[];
  data_quality?: BacktestAttributionBucket[];
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
};

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
  return {
    ...run,
    status: normalizeBacktestStatus(run.status),
    progress: numberOrNull(run.progress ?? run.progress_pct),
    strategies: run.strategies ?? run.strategy_keys ?? [],
    initial_capital: numberOrNull(run.initial_capital ?? run.initial_cash),
    benchmark: stringOrNull(run.benchmark ?? run.benchmark_symbol),
    execution_model: stringOrNull(run.execution_model ?? params.execution_model),
    risk_limits: run.risk_limits ?? riskLimits,
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
