import { invalidateCache, request } from "./base";

export type BacktestStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

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

export interface BacktestSummaryMetrics {
  total_return_pct?: number | null;
  benchmark_return_pct?: number | null;
  annual_return_pct?: number | null;
  sharpe?: number | null;
  sortino?: number | null;
  calmar?: number | null;
  max_drawdown_pct?: number | null;
  win_rate_pct?: number | null;
  total_trades?: number | null;
  profit_factor?: number | null;
}

export interface BacktestRunSummary {
  id: number;
  name: string;
  status: BacktestStatus;
  progress?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  initial_capital?: number | null;
  strategies?: string[];
  execution_model?: string | null;
  benchmark?: string | null;
  risk_limits?: Partial<BacktestRiskLimits> | null;
  summary?: BacktestSummaryMetrics | null;
  error_message?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
}

export type BacktestRunDetail = BacktestRunSummary;

export interface BacktestListResponse {
  items: BacktestRunSummary[];
  total: number;
  page: number;
  page_size: number;
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
  points: EquityPoint[];
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
  entry_date?: string | null;
  entry_price?: number | null;
  holding_days?: number | null;
  return_pct?: number | null;
  exit_reason?: string | null;
}

export interface BacktestTradesResponse {
  items: BacktestTrade[];
  total: number;
  page: number;
  page_size: number;
}

export const backtestsApi = {
  createBacktest: (payload: BacktestCreateRequest) =>
    request<BacktestSubmitResponse>("/backtests", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((result) => {
      invalidateCache(["/backtests"]);
      return result;
    }),

  listBacktests: ({
    page = 1,
    pageSize = 20,
    status,
  }: {
    page?: number;
    pageSize?: number;
    status?: BacktestStatus | "all";
  } = {}) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (status && status !== "all") {
      params.set("status", status);
    }
    return request<BacktestListResponse>(`/backtests?${params.toString()}`);
  },

  getBacktest: (runId: number) => request<BacktestRunDetail>(`/backtests/${runId}`),

  getBacktestEquity: (runId: number) =>
    request<BacktestEquityResponse>(`/backtests/${runId}/equity`).then((payload) => payload.points ?? []),

  getBacktestTrades: (
    runId: number,
    {
      page = 1,
      pageSize = 50,
    }: {
      page?: number;
      pageSize?: number;
    } = {}
  ) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return request<BacktestTradesResponse>(`/backtests/${runId}/trades?${params.toString()}`);
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
