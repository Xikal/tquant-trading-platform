import type {
  BacktestAttribution,
  BacktestExecutionModel,
  BacktestListParams,
  BacktestParamGrid,
  BacktestParamValue,
  BacktestStatus,
  BacktestSummaryMetrics,
  EquityPoint,
} from "./backtestBaseTypes";

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
  auto_promote_state_params?: boolean;
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

export interface PortfolioOptimizationWeight {
  strategy_key: string;
  weight_pct: number;
  avg_return_pct?: number | null;
  posterior_return_pct?: number | null;
  sample_avg_return_pct?: number | null;
  volatility_pct?: number | null;
  sample_count?: number | null;
}

export interface EfficientFrontierPoint {
  expected_return_pct: number;
  volatility_pct: number;
  sharpe: number;
}

export interface PortfolioOptimizationResponse {
  run_id: number;
  method: string;
  method_label?: string;
  weights: PortfolioOptimizationWeight[];
  expected_return_pct?: number | null;
  volatility_pct?: number | null;
  portfolio_sharpe?: number | null;
  efficient_frontier?: EfficientFrontierPoint[];
  summary?: string;
}

export interface PositionPolicyResearchResponse {
  run_id: number;
  production_enabled: boolean;
  algorithm: string;
  policy?: Array<Record<string, unknown>>;
  shadow_reinforcement_learning?: Record<string, unknown>;
  summary?: string;
}

export interface LiveBacktestComparisonItem {
  strategy_key: string;
  live_trade_count: number;
  backtest_trade_count: number;
  live_avg_return_pct: number;
  backtest_avg_return_pct: number;
  return_gap_pct: number;
  status: "ok" | "degraded" | "insufficient_live" | string;
  message: string;
}

export interface LiveBacktestComparisonResponse {
  ok: boolean;
  account_id?: number;
  lookback_days?: number;
  items: LiveBacktestComparisonItem[];
  alerts: Array<{ strategy_key: string; level: string; message: string }>;
  summary: string;
  generated_at?: string;
}

export type ResearchListParams = BacktestListParams;
