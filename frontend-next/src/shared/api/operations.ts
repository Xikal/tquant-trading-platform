import type { paths } from "../../generated/api-types";

export type ApiFeature =
  | "auth"
  | "workspace"
  | "monitor"
  | "analysis"
  | "playbook"
  | "strategy-tracking"
  | "backtest"
  | "data-console"
  | "settings";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type OperationContractStatus = "ready" | "shadow-only" | "live-smoke" | "blocked_contract_needed";
export type OperationWriteMode = "shadow" | "isolated-live-smoke" | "live";
export type QueryValue = string | number | boolean | null | undefined;

type ApiPath = keyof paths & string;
export interface ApiOperationDefinition {
  feature: ApiFeature;
  method: HttpMethod;
  path: ApiPath;
  contractStatus: OperationContractStatus;
  backendOperationId?: string;
  defaultStaleTimeMs?: number;
  invalidates?: readonly string[];
  requiresAdmin?: boolean;
}

function http(
  feature: ApiFeature,
  method: HttpMethod,
  path: ApiPath,
  backendOperationId: string,
  options: Omit<ApiOperationDefinition, "feature" | "method" | "path" | "backendOperationId"> = { contractStatus: "ready" },
): ApiOperationDefinition {
  return { feature, method, path, backendOperationId, ...options };
}

export const apiOperations = {
  authLogin: http("auth", "POST", "/api/auth/login", "login_api_auth_login_post"),
  authRegister: http("auth", "POST", "/api/auth/register", "register_api_auth_register_post"),
  authRefresh: http("auth", "POST", "/api/auth/refresh", "refresh_api_auth_refresh_post"),
  authLogout: http("auth", "POST", "/api/auth/logout", "logout_api_auth_logout_post"),
  authMe: http("auth", "GET", "/api/auth/me", "me_api_auth_me_get", { contractStatus: "ready", defaultStaleTimeMs: 30_000 }),
  authTotpSetup: http("auth", "POST", "/api/auth/mfa/totp/setup", "setup_totp_mfa_api_auth_mfa_totp_setup_post"),
  authTotpEnable: http("auth", "POST", "/api/auth/mfa/totp/enable", "enable_totp_mfa_api_auth_mfa_totp_enable_post"),
  authTotpDisable: http("auth", "POST", "/api/auth/mfa/totp/disable", "disable_totp_mfa_api_auth_mfa_totp_disable_post"),
  bffManifest: http("workspace", "GET", "/api/bff/v1/manifest", "bff_manifest_api_bff_v1_manifest_get"),
  monitorWorkspace: http("workspace", "GET", "/api/bff/v1/workspace/monitor", "monitor_workspace_bff_api_bff_v1_workspace_monitor_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 10_000,
  }),
  strategyWorkspace: http("workspace", "GET", "/api/bff/v1/workspace/strategy", "strategy_workspace_bff_api_bff_v1_workspace_strategy_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 10_000,
  }),
  settingsWorkspace: http("workspace", "GET", "/api/bff/v1/workspace/settings", "settings_workspace_bff_api_bff_v1_workspace_settings_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 15_000,
  }),

  monitorSnapshot: http("monitor", "GET", "/api/monitor/snapshot", "monitor_snapshot_api_monitor_snapshot_get", { contractStatus: "ready", defaultStaleTimeMs: 15_000 }),
  marketTradingSession: http("monitor", "GET", "/api/market/trading-session", "market_trading_session_api_market_trading_session_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 60_000,
  }),
  marketBreadth: http("monitor", "GET", "/api/market/breadth", "market_breadth_api_market_breadth_get", { contractStatus: "ready", defaultStaleTimeMs: 10_000 }),
  marketSectorRelativeStrength: http("monitor", "GET", "/api/market/sector-relative-strength", "sector_relative_strength_api_market_sector_relative_strength_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 20_000,
  }),
  marketIntradayKeyLevels: http("monitor", "GET", "/api/market/intraday-key-levels/{symbol}", "intraday_key_levels_api_market_intraday_key_levels__symbol__get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 10_000,
  }),
  stockKeyLevels: http("monitor", "GET", "/api/key-levels/stock/{symbol}", "stock_key_levels_api_key_levels_stock__symbol__get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 20_000,
  }),
  marketReviewSummary: http("monitor", "GET", "/api/market/review-summary", "market_review_summary_api_market_review_summary_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 30_000,
  }),
  watchlist: http("monitor", "GET", "/api/watchlist", "list_watchlist_api_watchlist_get", { contractStatus: "ready", defaultStaleTimeMs: 15_000 }),
  watchlistUpsert: http("monitor", "POST", "/api/watchlist", "upsert_watchlist_api_watchlist_post", {
    contractStatus: "ready",
    invalidates: ["watchlist", "watchlistSignals", "watchlistQuotes", "monitorWorkspace"],
  }),
  watchlistRemove: http("monitor", "DELETE", "/api/watchlist/{symbol}", "remove_watchlist_api_watchlist__symbol__delete", {
    contractStatus: "ready",
    invalidates: ["watchlist", "watchlistSignals", "watchlistQuotes", "monitorWorkspace"],
  }),
  watchlistSignals: http("monitor", "GET", "/api/watchlist/signals", "watchlist_signals_api_watchlist_signals_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 9_000,
  }),
  watchlistQuotes: http("monitor", "GET", "/api/watchlist/quotes", "watchlist_quotes_api_watchlist_quotes_get", { contractStatus: "ready", defaultStaleTimeMs: 6_000 }),

  analyzeSymbol: http("analysis", "POST", "/api/analyze", "analyze_symbol_api_analyze_post"),
  analyzeBatch: http("analysis", "POST", "/api/analyze/batch", "analyze_batch_api_analyze_batch_post"),
  aiDecisionSupport: http("analysis", "POST", "/api/ai/decision-support", "build_decision_support_api_ai_decision_support_post"),
  quote: http("analysis", "GET", "/api/quote/{symbol}", "get_quote_api_quote__symbol__get", { contractStatus: "ready", defaultStaleTimeMs: 8_000 }),
  symbolSearch: http("analysis", "GET", "/api/symbols/search", "search_symbols_api_symbols_search_get", { contractStatus: "ready", defaultStaleTimeMs: 30_000 }),
  kline: http("analysis", "GET", "/api/kline/{symbol}", "get_kline_api_kline__symbol__get", { contractStatus: "ready", defaultStaleTimeMs: 20_000 }),
  marketIntradayAnomaly: http("analysis", "GET", "/api/market/intraday-anomaly/{symbol}", "intraday_anomaly_api_market_intraday_anomaly__symbol__get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 15_000,
  }),

  lowBuyScreener: http("playbook", "GET", "/api/screeners/low-buy", "low_buy_screener_view_api_screeners_low_buy_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 45_000,
  }),
  lowBuyPriorityBoard: http("playbook", "GET", "/api/screeners/low-buy/priority-board", "low_buy_priority_board_view_api_screeners_low_buy_priority_board_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 15_000,
  }),
  lowBuyQuotes: http("playbook", "GET", "/api/screeners/low-buy/quotes", "low_buy_quote_refresh_view_api_screeners_low_buy_quotes_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 6_000,
  }),
  lowBuyHistory: http("playbook", "GET", "/api/screeners/low-buy/history", "low_buy_history_view_api_screeners_low_buy_history_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 60_000,
  }),
  lowBuyLifecycle: http("playbook", "GET", "/api/screeners/low-buy/lifecycle", "low_buy_lifecycle_view_api_screeners_low_buy_lifecycle_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 30_000,
  }),
  lowBuyLifecycleUpdate: http("playbook", "PATCH", "/api/screeners/low-buy/lifecycle/{symbol}", "update_low_buy_lifecycle_view_api_screeners_low_buy_lifecycle__symbol__patch", {
    contractStatus: "ready",
    invalidates: ["lowBuyLifecycle", "lowBuyPriorityBoard", "monitorWorkspace"],
  }),
  lowBuyStrategies: http("playbook", "GET", "/api/screeners/low-buy/strategies", "low_buy_strategy_governance_view_api_screeners_low_buy_strategies_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 30_000,
  }),
  lowBuyStrategyUpdate: http("playbook", "PATCH", "/api/screeners/low-buy/strategies/{strategy_key}", "low_buy_strategy_governance_update_view_api_screeners_low_buy_strategies__strategy_key__patch", {
    contractStatus: "ready",
    invalidates: ["lowBuyStrategies", "lowBuyScreener", "monitorWorkspace", "settingsWorkspace"],
  }),
  strategiesMeta: http("playbook", "GET", "/api/strategies/meta", "list_strategy_meta_api_strategies_meta_get", { contractStatus: "ready", defaultStaleTimeMs: 60_000 }),
  strategyPresets: http("playbook", "GET", "/api/strategy/presets", "list_strategy_presets_api_strategy_presets_get", { contractStatus: "ready", defaultStaleTimeMs: 60_000 }),

  strategyTrackingItems: http("strategy-tracking", "GET", "/api/strategy-tracking/items", "strategy_tracking_items_view_api_strategy_tracking_items_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 12_000,
  }),
  strategyTrackingDetail: http("strategy-tracking", "GET", "/api/strategy-tracking/items/{item_id}", "strategy_tracking_detail_view_api_strategy_tracking_items__item_id__get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 12_000,
  }),
  strategyTrackingSummary: http("strategy-tracking", "GET", "/api/strategy-tracking/summary", "strategy_tracking_summary_view_api_strategy_tracking_summary_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 12_000,
  }),
  strategyTrackingPerformance: http("strategy-tracking", "GET", "/api/strategy-tracking/performance", "strategy_tracking_performance_view_api_strategy_tracking_performance_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 12_000,
  }),
  strategyTrackingHoldingAnalysis: http("strategy-tracking", "GET", "/api/strategy-tracking/holding-analysis", "strategy_tracking_holding_analysis_view_api_strategy_tracking_holding_analysis_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 12_000,
  }),
  strategyTrackingReview: http("strategy-tracking", "GET", "/api/strategy-tracking/review", "strategy_tracking_review_view_api_strategy_tracking_review_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 12_000,
  }),
  strategyTrackingRefresh: http("strategy-tracking", "POST", "/api/strategy-tracking/refresh", "strategy_tracking_refresh_view_api_strategy_tracking_refresh_post", {
    contractStatus: "ready",
    invalidates: ["strategyWorkspace", "strategyTrackingItems", "strategyTrackingSummary"],
  }),
  strategyReviewRecord: http("strategy-tracking", "POST", "/api/strategy-tracking/review-records", "create_strategy_review_record_api_strategy_tracking_review_records_post", {
    contractStatus: "ready",
    invalidates: ["strategyTrackingReview", "strategyWorkspace"],
  }),
  tradeJournal: http("strategy-tracking", "GET", "/api/trading-experience/trade-journal", "get_trade_journal_api_trading_experience_trade_journal_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 12_000,
  }),
  tradeJournalCreate: http("strategy-tracking", "POST", "/api/trading-experience/trade-journal", "create_trade_journal_api_trading_experience_trade_journal_post", {
    contractStatus: "ready",
    invalidates: ["tradeJournal", "strategyTrackingReview"],
  }),
  relativeStrength: http("strategy-tracking", "GET", "/api/trading-experience/relative-strength", "get_relative_strength_api_trading_experience_relative_strength_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 12_000,
  }),

  backtestRuns: http("backtest", "GET", "/api/backtests/runs", "list_backtest_runs_api_backtests_runs_get", { contractStatus: "ready", defaultStaleTimeMs: 15_000 }),
  backtestRunCreate: http("backtest", "POST", "/api/backtests", "create_backtest_run_api_backtests_post", {
    contractStatus: "blocked_contract_needed",
    invalidates: ["backtestRuns"],
  }),
  backtestRunDetail: http("backtest", "GET", "/api/backtests/{run_id}", "get_backtest_run_api_backtests__run_id__get", { contractStatus: "ready", defaultStaleTimeMs: 15_000 }),
  backtestRunCancel: http("backtest", "POST", "/api/backtests/{run_id}/cancel", "cancel_backtest_run_api_backtests__run_id__cancel_post", {
    contractStatus: "blocked_contract_needed",
    invalidates: ["backtestRuns", "backtestRunDetail"],
  }),
  backtestRunEquity: http("backtest", "GET", "/api/backtests/{run_id}/equity", "get_backtest_equity_api_backtests__run_id__equity_get", { contractStatus: "ready", defaultStaleTimeMs: 30_000 }),
  backtestRunTrades: http("backtest", "GET", "/api/backtests/{run_id}/trades", "get_backtest_trades_api_backtests__run_id__trades_get", { contractStatus: "ready", defaultStaleTimeMs: 30_000 }),
  backtestValidationCreate: http("backtest", "POST", "/api/backtests/validate", "create_backtest_validation_api_backtests_validate_post", {
    contractStatus: "blocked_contract_needed",
    invalidates: ["backtestRuns"],
  }),
  backtestOptimizationCreate: http("backtest", "POST", "/api/backtests/optimize", "create_backtest_optimization_api_backtests_optimize_post", {
    contractStatus: "blocked_contract_needed",
    invalidates: ["backtestRuns"],
  }),

  dataQualityCoverage: http("data-console", "GET", "/api/data-quality/coverage", "get_data_quality_coverage_api_data_quality_coverage_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 30_000,
  }),
  dataQualitySla: http("data-console", "GET", "/api/data-quality/sla", "list_data_quality_sla_api_data_quality_sla_get", { contractStatus: "ready", defaultStaleTimeMs: 30_000 }),
  dataQualityBackfill: http("data-console", "POST", "/api/data-quality/backfill", "enqueue_data_quality_backfill_api_data_quality_backfill_post", {
    contractStatus: "ready",
    requiresAdmin: true,
    invalidates: ["dataQualityCoverage", "runtimeTasks", "runtimeTaskSummary"],
  }),
  dataQualityRepair: http("data-console", "POST", "/api/data-quality/repair", "enqueue_data_repair_api_data_quality_repair_post", {
    contractStatus: "ready",
    requiresAdmin: true,
    invalidates: ["dataQualityCoverage", "runtimeTasks", "runtimeTaskSummary"],
  }),
  dataJobSubmit: http("data-console", "POST", "/api/runtime-tasks", "enqueue_runtime_task_api_runtime_tasks_post", {
    contractStatus: "ready",
    requiresAdmin: true,
    invalidates: ["runtimeTasks", "runtimeTaskSummary"],
  }),
  runtimeTasks: http("data-console", "GET", "/api/runtime-tasks", "list_runtime_tasks_api_runtime_tasks_get", { contractStatus: "ready", defaultStaleTimeMs: 15_000 }),
  runtimeTaskSummary: http("data-console", "GET", "/api/runtime-tasks/summary", "get_runtime_task_summary_api_runtime_tasks_summary_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 15_000,
  }),
  runtimeTaskCreate: http("data-console", "POST", "/api/runtime-tasks", "enqueue_runtime_task_api_runtime_tasks_post", {
    contractStatus: "ready",
    requiresAdmin: true,
    invalidates: ["runtimeTasks", "runtimeTaskSummary"],
  }),
  adminMetrics: http("data-console", "GET", "/api/admin/metrics", "get_admin_metrics_api_admin_metrics_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 15_000,
    requiresAdmin: true,
  }),
  adminTasks: http("data-console", "GET", "/api/admin/tasks", "get_admin_tasks_api_admin_tasks_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 15_000,
    requiresAdmin: true,
  }),

  settings: http("settings", "GET", "/api/settings", "get_settings_api_settings_get", { contractStatus: "ready", defaultStaleTimeMs: 20_000 }),
  settingsUpdate: http("settings", "PUT", "/api/settings", "update_settings_api_settings_put", {
    contractStatus: "ready",
    invalidates: ["settings", "settingsWorkspace"],
  }),
  settingsRuntime: http("settings", "GET", "/api/settings/runtime", "get_runtime_status_api_settings_runtime_get", { contractStatus: "ready", defaultStaleTimeMs: 10_000 }),
  sectorExclusions: http("settings", "GET", "/api/settings/sector-exclusions", "get_sector_exclusions_api_settings_sector_exclusions_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 30_000,
  }),
  sectorExclusionsUpdate: http("settings", "PUT", "/api/settings/sector-exclusions", "update_sector_exclusions_api_settings_sector_exclusions_put", {
    contractStatus: "ready",
    invalidates: ["sectorExclusions", "settingsWorkspace", "lowBuyScreener", "monitorWorkspace"],
  }),
  factorWeights: http("settings", "GET", "/api/settings/factor-weights", "get_factor_weights_api_settings_factor_weights_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 30_000,
  }),
  factorWeightsUpdate: http("settings", "PUT", "/api/settings/factor-weights", "update_factor_weights_api_settings_factor_weights_put", {
    contractStatus: "ready",
    invalidates: ["factorWeights", "settingsWorkspace", "lowBuyScreener", "monitorWorkspace"],
  }),
  featureFlags: http("settings", "GET", "/api/settings/feature-flags", "get_feature_flags_api_settings_feature_flags_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 20_000,
  }),
  featureFlagAudit: http("settings", "GET", "/api/settings/feature-flags/audit", "get_feature_flag_audit_api_settings_feature_flags_audit_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 30_000,
  }),
  featureFlagUpdate: http("settings", "PUT", "/api/settings/feature-flags/{key}", "put_feature_flag_api_settings_feature_flags__key__put", {
    contractStatus: "ready",
    requiresAdmin: true,
    invalidates: ["featureFlags", "featureFlagAudit", "settingsWorkspace"],
  }),
  databaseCheck: http("settings", "POST", "/api/settings/database/check", "check_database_api_settings_database_check_post", { contractStatus: "ready", requiresAdmin: true }),
  databaseMigrate: http("settings", "POST", "/api/settings/database/migrate", "migrate_database_api_settings_database_migrate_post", { contractStatus: "blocked_contract_needed", requiresAdmin: true }),
  quantParameters: http("settings", "GET", "/api/quant/parameters", "list_quant_parameter_sets_api_quant_parameters_get", {
    contractStatus: "ready",
    defaultStaleTimeMs: 60_000,
  }),
} as const;

export type ApiOperationName = keyof typeof apiOperations;

export interface OperationPathOptions {
  path?: Record<string, QueryValue>;
  query?: Record<string, QueryValue | QueryValue[]>;
}

export function getOperation(name: ApiOperationName): ApiOperationDefinition {
  return apiOperations[name];
}

export function operationPath(name: ApiOperationName, options: OperationPathOptions = {}): string {
  const operation = getOperation(name);
  let path = operation.path as string;
  Object.entries(options.path ?? {}).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      throw new Error(`Missing path parameter ${key} for operation ${name}`);
    }
    path = path.replaceAll(`{${key}}`, encodeURIComponent(String(value)));
  });
  const missingParam = path.match(/{[^}]+}/);
  if (missingParam) {
    throw new Error(`Missing path parameter ${missingParam[0]} for operation ${name}`);
  }
  const queryString = encodeQuery(options.query);
  return queryString ? `${path}?${queryString}` : path;
}

export function encodeQuery(query: OperationPathOptions["query"] = {}): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      const values = value.filter((item) => item !== null && item !== undefined && item !== "").map(String);
      if (values.length) params.set(key, values.join(","));
      return;
    }
    if (value !== null && value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  return params.toString();
}

export function isWriteOperation(name: ApiOperationName): boolean {
  return getOperation(name).method !== "GET";
}

export function operationCanSendWhenWriteEnabled(name: ApiOperationName): boolean {
  const status = getOperation(name).contractStatus;
  return status === "ready" || status === "live-smoke";
}

export const featureOperations = Object.freeze(
  Object.entries(apiOperations).reduce<Record<ApiFeature, ApiOperationName[]>>(
    (acc, [name, operation]) => {
      acc[operation.feature].push(name as ApiOperationName);
      return acc;
    },
    {
      auth: [],
      workspace: [],
      monitor: [],
      analysis: [],
      playbook: [],
      "strategy-tracking": [],
      backtest: [],
      "data-console": [],
      settings: [],
    },
  ),
);
