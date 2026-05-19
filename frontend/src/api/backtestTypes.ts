export type BacktestStatus = "pending" | "queued" | "running" | "completed" | "succeeded" | "failed" | "cancelled" | "deleted" | "timeout";

export type BacktestExecutionModel =
  | "conservative_slippage"
  | "open_price"
  | "close_price"
  | "next_open"
  | "vwap"
  | "market_impact";
export type BacktestResourceTier = "light" | "full" | "walk_forward";

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
  resource_tier?: BacktestResourceTier;
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
  queue_depth?: number | null;
  queue_position?: number | null;
  running_count?: number | null;
  estimated_wait_seconds?: number | null;
  resource_tier?: BacktestResourceTier | null;
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

export interface BacktestVerdictThresholdItem {
  min_return_pct: number;
  min_sharpe: number;
  max_drawdown_pct: number;
  cautious_min_return_pct: number;
  cautious_max_drawdown_pct: number;
}

export interface BacktestVerdictThresholdsResponse {
  thresholds: Record<BacktestResourceTier, BacktestVerdictThresholdItem>;
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

export type BacktestListParams = {
  page?: number;
  pageSize?: number;
  limit?: number;
  offset?: number;
  status?: BacktestStatus | "all";
};

export type BacktestTradesParams = {
  page?: number;
  pageSize?: number;
  limit?: number;
  offset?: number;
};

export type RawRecord = Record<string, unknown>;

export type ResearchListParams = BacktestListParams;
