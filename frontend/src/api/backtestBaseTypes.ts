export type BacktestStatus = "pending" | "queued" | "running" | "completed" | "succeeded" | "failed" | "cancelled" | "deleted" | "timeout";

export type BacktestExecutionModel =
  | "conservative_slippage"
  | "open_price"
  | "close_price"
  | "next_open"
  | "vwap"
  | "market_impact"
  | "twap"
  | "implementation_shortfall";
export type BacktestResourceTier = "light" | "full" | "walk_forward";
export type RawRecord = Record<string, unknown>;

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

export interface ExecutionModelPreview {
  ok?: boolean;
  mode?: string;
  source?: string;
  execution_model_version?: string;
  event_counts?: Record<string, number>;
  position_summary?: Record<string, number>;
  exit_reason_counts?: Record<string, number>;
  max_5?: BacktestSummaryMetrics & Record<string, unknown>;
  max_10?: BacktestSummaryMetrics & Record<string, unknown>;
  parity?: {
    max_5?: Record<string, boolean>;
    max_10?: Record<string, boolean>;
  };
  final_fact_source?: string;
  replacement_enabled?: boolean;
  blocked_reason?: string;
  forward_path_status?: string;
  notes?: string[];
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
  execution_model_preview?: ExecutionModelPreview | null;
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

export interface StrategyImprovementReportResponse {
  summary: {
    generated_at?: string;
    overall_status: string;
    formal_backtest_allowed: boolean;
    walk_forward_allowed?: boolean;
    production_parameter_change_allowed?: boolean;
    reason?: string;
  };
  data_coverage: {
    status: string;
    coverage_pct: number;
    full_market_trade_day_coverage_pct?: number;
    complete_trade_day_count?: number;
    trade_day_count?: number;
    symbol_count?: number;
    missing_detail_sample?: Array<Record<string, unknown>>;
  };
  data_quality?: {
    status?: string;
    metadata_coverage?: {
      status?: string;
      blocking_gap_count?: number;
      blocking_gaps?: string[];
    };
  };
  minute_coverage: {
    status: string;
    raw_data_status?: string;
    blocked_reason?: string;
    eligible_etf_count?: number;
    eligible_etf_with_minutes?: number;
    eligible_etf_with_sufficient_window_minutes?: number;
    eligible_etf_any_minute_coverage_pct?: number;
    eligible_etf_minute_coverage_pct?: number;
    expected_trade_day_count?: number;
    missing_etf_symbols?: Array<{ symbol: string; name?: string; category?: string; reason?: string; trade_day_coverage_pct?: number }>;
    provider_diagnostics?: {
      status?: string;
      report_path?: string;
      generated_at?: string;
      totals?: { ok?: number; skip?: number; empty?: number; error?: number };
      provider_errors_sample?: Array<{ symbol?: string; source?: string; message?: string }>;
      write_effect?: string;
      fake_data_policy?: string;
    };
  };
  strategy_governance: {
    status?: string;
    strategy_count?: number;
    state_counts?: Record<string, number>;
    items?: Array<{
      strategy_key: string;
      strategy_title?: string;
      strategy_family?: string;
      sample_count?: number;
      filled_count?: number;
      win_rate_pct?: number;
      profit_factor?: number | null;
      avg_trade_return_pct?: number;
      max_drawdown_pct?: number;
      stop_loss_rate_pct?: number;
      governance_state?: string;
      recommended_action?: string;
      constraints_to_test?: string[];
    }>;
    ranking?: Array<{
      strategy_key: string;
      strategy_title: string;
      governance_state: string;
      recommended_action: string;
      profit_factor?: number;
      win_rate_pct?: number;
      max_drawdown_pct?: number;
    }>;
  };
  walk_forward?: {
    status: string;
    blocked_reasons?: string[];
    candidate_strategy_count?: number;
    recommended_scheme?: string;
    time_series_split?: string;
    train_months?: number;
    validation_months?: number;
    oos_months?: number;
    rolling_step?: string;
    window_count?: number;
    random_split_allowed?: boolean;
    windows?: Array<{
      window_id?: number;
      train_start?: string;
      train_end?: string;
      validation_start?: string;
      validation_end?: string;
      oos_start?: string;
      oos_end?: string;
      train_trade_days?: number;
      validation_trade_days?: number;
      oos_trade_days?: number;
      split_order?: string;
    }>;
    controlled_parameter_grid?: Array<{ name: string; values: Array<string | number | boolean | null> }>;
    stability_checks?: Array<{ key: string; description?: string }>;
    overfit_risk_required?: string[];
  };
  constraint_policy?: {
    status: string;
    issue_count?: number;
    production_effect?: string;
    required_base_constraints?: string[];
    required_risk_constraints?: string[];
    issues?: Array<Record<string, unknown>>;
  };
  temporal_guard?: {
    status: string;
    issue_count?: number;
    checks?: string[];
    forbidden_feature_keywords?: string[];
    issues?: Array<Record<string, unknown>>;
  };
  auxiliary_model_shadow?: {
    status: string;
    record_count?: number;
    settled_count?: number;
    production_effect?: string;
    shadow_only?: boolean;
    hard_stop_override_allowed?: boolean;
    promotion_ready?: boolean;
    promotion_blockers?: string[];
    action_diff?: {
      same_as_rule?: number;
      more_aggressive_than_rule?: number;
      less_aggressive_than_rule?: number;
      fallback?: number;
      fallback_rate_pct?: number;
      hard_stop_override_risk_count?: number;
    };
    outcome_summary?: {
      settled_or_labeled_count?: number;
      avg_return_5d_pct?: number;
      avg_max_adverse_5d_pct?: number;
      sell_flying_count?: number;
      sell_flying_rate_pct?: number;
    };
  };
  gates: Array<{
    key: string;
    status: string;
    severity?: string;
    message?: string;
    evidence?: Record<string, unknown>;
  }>;
  next_actions?: string[];
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
