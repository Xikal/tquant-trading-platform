export interface SettingsPayload {
  llm_provider: string;
  llm_api_key: string;
  llm_base_url: string;
  llm_model: string;
  data_source: string;
  data_source_base_url: string;
  database_url: string;
  risk_max_single_loss_pct: number;
  risk_max_daily_loss_pct: number;
  risk_pause_after_losses: number;
  walk_forward_window_size: number;
  event_risk_enabled: boolean;
  microstructure_enabled: boolean;
  strategy_min_amount_stock: number;
  strategy_min_amount_etf: number;
  strategy_min_amplitude_pct: number;
  strategy_max_amplitude_pct: number;
  strategy_max_atr_pct: number;
  strategy_open_phase_min_tradability: number;
  strategy_min_profit_pct: number;
  strategy_min_profit_stock_pct: number;
  strategy_min_profit_etf_pct: number;
  strategy_slippage_stock_bps: number;
  strategy_slippage_etf_bps: number;
  llm_api_key_configured?: boolean;
  database_url_configured?: boolean;
  admin_auth_required?: boolean;
}

export interface DatabaseCheckResult {
  ok: boolean;
  dialect: string;
  database: string;
  masked_url: string;
  tables: string[];
  message: string;
}

export interface DatabaseMigrationResult {
  ok: boolean;
  source_database_url: string;
  target_database_url: string;
  copied_rows: Record<string, number>;
  total_rows: number;
  activated_on_restart: boolean;
  message: string;
}

export interface RuntimeStatus {
  app_name: string;
  api_prefix: string;
  database_backend: string;
  database_url_masked: string;
  runtime_env_path: string;
  runtime_env_exists: boolean;
  runtime_database_override: boolean;
  frontend_dist_path: string;
  frontend_dist_ready: boolean;
  llm_configured: boolean;
  data_source: string;
  data_source_base_url: string;
  cors_origins: string[];
  ready_checks: Record<string, boolean>;
}

export interface FactorSpec {
  name: string;
  weight: number;
  data_dependencies: string[];
  applicable_strategies: string[];
  activation_condition: string;
  status: "active" | "stub" | "experimental" | "deprecated" | "disabled" | string;
  status_text: string;
}

export interface FactorWeightsResponse {
  weights: Record<string, number>;
  defaults: Record<string, number>;
  factors: FactorSpec[];
}

export interface AdminTaskStatus {
  name: string;
  interval_seconds: number;
  running: boolean;
  enabled: boolean;
  last_started_at?: string | null;
  last_finished_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  duration_ms?: number | null;
  rows_processed?: number | null;
  run_count: number;
}

export interface AdminTasksResponse {
  items: AdminTaskStatus[];
}

export interface LowBuyStrategyGovernanceItem {
  strategy_key: string;
  strategy_title: string;
  subtitle: string;
  tier: "core" | "auxiliary" | "research" | "factor" | string;
  layer: "production" | "research" | "factor" | string;
  status: "active" | "watch" | "paused" | "research" | "deprecated" | string;
  status_text: string;
  enabled: boolean;
  participates_priority_board: boolean;
  strong_buy_paused: boolean;
  requires_mainline_industry: boolean;
  pool_key: string;
  pool_title: string;
  pool_source: string;
  pool_max_size: number;
  uses_daily_scan_pool: boolean;
  max_holding_days: number;
  holding_brief: string;
  strategy_health_score: number;
  strategy_health_text: string;
  performance_sample_count: number;
  notes: string[];
}

export interface LowBuyStrategyGovernanceResponse {
  default_strategy: string;
  production_strategies: string[];
  items: LowBuyStrategyGovernanceItem[];
}
