import type {
  AnalysisResponse,
  AiDecisionSupportRequest,
  AiDecisionSupportResponse,
  BacktestResult,
  BacktestRunListResponse,
  DatabaseCheckResult,
  DatabaseMigrationResult,
  LowBuyScreenerResult,
  LowBuyHistoryResult,
  LowBuyQuoteRefreshItem,
  LowBuyPriorityBoardResult,
  LowBuyExecutionBacktestResult,
  LowBuyTradeLifecycle,
  MarketBreadth,
  EtfMinuteSnapshotBatchResponse,
  EtfUniverseResponse,
  MarketHourlySnapshotHistoryResponse,
  MonitorWorkspaceBffResponse,
  MarketTradingSession,
  SectorRelativeStrengthResponse,
  IntradayKeyLevelResponse,
  AlternativeSentimentResponse,
  MultiExchangeArbitrageResearchResponse,
  PairedHedgeResearchResponse,
  SectorEtfT0Response,
  IntradayAnomalyResponse,
  MonitorSnapshot,
  PaperAccount,
  PaperGroupedPerformance,
  PaperOrder,
  PaperOrderCreate,
  PaperAccessResponse,
  PaperAutoTradingStatus,
  PaperAgentRun,
  PaperPerformance,
  PaperPerformanceDashboard,
  PaperWorkspaceBffResponse,
  PaperLedgerRepairResponse,
  PaperSectorEtfT0Performance,
  PaperStrategyMarketPerformance,
  PaperPositionsResponse,
  PaperStockPnlResponse,
  PaperTagPerformance,
  PaperTradeTag,
  PaperTradeTagCreate,
  PaperTradesResponse,
  RuntimeStatus,
  FactorWeightsResponse,
  SettingsWorkspaceBffResponse,
  AdminTasksResponse,
  AdminMetricsResponse,
  AdminLatestDataRefreshResponse,
  Instrument,
  InstrumentSyncStatus,
  InstrumentSyncStartResponse,
  IntradayConfirmationItem,
  LowBuyStrategyGovernanceResponse,
  ReplayItem,
  RiskEventItem,
  SettingsPayload,
  UserSectorExclusionsResponse,
  StrategyValidationReport,
  StrategyTrackingDetailResponse,
  StrategyTrackingHoldingAnalysisResponse,
  StrategyTrackingListResponse,
  StrategyTrackingParams,
  StrategyTrackingReport,
  StrategyPromotionReview,
  StrategyTrackingReviewResponse,
  StrategyTrackingSnapshotResponse,
  WatchlistItem,
  WatchlistQuoteItem,
  WatchlistSignal,
  StrategyVariant
} from "../types";
import { invalidateCache } from "./base";
import { apiClient } from "./httpClient";

const request = apiClient.request;
const requestCached = apiClient.requestCached;

export const api = {
  listInstruments: (keyword = "", kind = "all") =>
    request<{ items: Instrument[]; total: number }>(
      `/instruments?keyword=${encodeURIComponent(keyword)}&kind=${kind}&page=1&page_size=20`
    ),
  syncInstruments: () => request<InstrumentSyncStartResponse>(`/instruments/sync`, { method: "POST" }),
  getInstrumentSyncStatus: (runId?: string) =>
    request<InstrumentSyncStatus>(`/instruments/sync/status${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`),
  getWatchlist: () => request<WatchlistItem[]>("/watchlist"),
  upsertWatchlist: (payload: Omit<WatchlistItem, "created_at">) =>
    request<{ message: string; symbol: string }>("/watchlist", {
      method: "POST",
      body: JSON.stringify(payload)
    }).then((result) => {
      invalidateCache(["/watchlist", "/watchlist/signals"]);
      return result;
    }),
  deleteWatchlist: (symbol: string) =>
    request<{ message: string }>(`/watchlist/${symbol}`, { method: "DELETE" }).then((result) => {
      invalidateCache(["/watchlist", "/watchlist/signals"]);
      return result;
    }),
  getWatchlistSignals: () => requestCached<WatchlistSignal[]>("/watchlist/signals", 9000),
  getWatchlistQuotes: () => request<WatchlistQuoteItem[]>("/watchlist/quotes"),
  getMarketBreadth: () => requestCached<MarketBreadth>("/market/breadth", 10000),
  getMarketHourlySnapshotsHistory: (limit = 8) =>
    requestCached<MarketHourlySnapshotHistoryResponse>(`/market/hourly-snapshots/history?limit=${limit}`, 20000),
  getMarketTradingSession: () => requestCached<MarketTradingSession>("/market/trading-session", 60000),
  getSectorRelativeStrength: (limit = 8, perSectorLimit = 10) =>
    requestCached<SectorRelativeStrengthResponse>(
      `/market/sector-relative-strength?limit=${limit}&per_sector_limit=${perSectorLimit}`,
      20000,
    ),
  getIntradayKeyLevels: (symbol: string) =>
    requestCached<IntradayKeyLevelResponse>(`/market/intraday-key-levels/${encodeURIComponent(symbol)}`, 10000),
  getSectorEtfT0: (limit = 8) => requestCached<SectorEtfT0Response>(`/market/sector-etf-t0?limit=${limit}`, 20000),
  getEtfUniverse: (category = "", t0Only = false) =>
    requestCached<EtfUniverseResponse>(
      `/market/etf-universe?category=${encodeURIComponent(category)}&t0_only=${t0Only ? "true" : "false"}`,
      60000,
    ),
  getEtfMinuteSnapshots: (symbols: string[], period: "1m" | "5m" | "15m" = "1m", limit = 30) =>
    requestCached<EtfMinuteSnapshotBatchResponse>(
      `/market/etf-minute-snapshots?symbols=${encodeURIComponent(symbols.join(","))}&period=${period}&limit=${limit}`,
      15000,
    ),
  getPairedHedgeResearch: (limit = 8) =>
    requestCached<PairedHedgeResearchResponse>(`/market/paired-hedge-research?limit=${limit}`, 30000),
  getAlternativeSentiment: (symbols: string[] = [], limit = 80) =>
    requestCached<AlternativeSentimentResponse>(
      `/market/alternative-sentiment?symbols=${encodeURIComponent(symbols.join(","))}&limit=${limit}`,
      30000,
    ),
  getMultiExchangeArbitrageResearch: (symbols: string[] = []) =>
    requestCached<MultiExchangeArbitrageResearchResponse>(
      `/market/multi-exchange-arbitrage/research?symbols=${encodeURIComponent(symbols.join(","))}`,
      60000,
    ),
  getIntradayAnomaly: (symbol: string) =>
    requestCached<IntradayAnomalyResponse>(`/market/intraday-anomaly/${encodeURIComponent(symbol)}`, 15000),
  getMonitorSnapshot: (priorityLimit = 12) =>
    requestCached<MonitorSnapshot>(`/monitor/snapshot?priority_limit=${priorityLimit}`, 15000),
  getMonitorWorkspaceBff: (priorityLimit = 12) =>
    requestCached<MonitorWorkspaceBffResponse>(
      `/bff/v1/workspace/monitor?priority_limit=${priorityLimit}&sector_limit=8&per_sector_limit=8&hedge_limit=4`,
      10000
    ),
  getPaperAccess: () => request<PaperAccessResponse>("/auth/paper-access"),
  analyze: (payload: {
    symbol: string;
    prefer_strategy: "auto" | "positive_t" | "negative_t";
    base_position: number;
    available_position: number;
    cost_basis?: number | null;
    include_ai: boolean;
    include_events: boolean;
    include_microstructure: boolean;
  }) =>
    request<AnalysisResponse>("/analyze", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  analyzeBatch: (
    payloads: {
      symbol: string;
      prefer_strategy: "auto" | "positive_t" | "negative_t";
      base_position: number;
      available_position: number;
      cost_basis?: number | null;
      include_ai: boolean;
      include_events: boolean;
      include_microstructure: boolean;
    }[]
  ) =>
    request<AnalysisResponse[]>("/analyze/batch", {
      method: "POST",
      body: JSON.stringify(payloads)
    }),
  buildAiDecisionSupport: (payload: AiDecisionSupportRequest) =>
    request<AiDecisionSupportResponse>("/ai/decision-support", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getSettings: () => request<SettingsPayload>("/settings"),
  getSettingsWorkspaceBff: () => request<SettingsWorkspaceBffResponse>("/bff/v1/workspace/settings"),
  getSectorExclusions: () => request<UserSectorExclusionsResponse>("/settings/sector-exclusions"),
  updateSectorExclusions: (excluded_sectors: string[]) =>
    request<UserSectorExclusionsResponse>("/settings/sector-exclusions", {
      method: "PUT",
      body: JSON.stringify({ excluded_sectors })
    }).then((result) => {
      invalidateCache([
        "/settings/sector-exclusions",
        "/bff/v1/workspace/settings",
        "/screeners/low-buy",
        "/screeners/low-buy/priority-board",
        "/monitor/snapshot",
        "/bff/v1/workspace/monitor",
        "/market/sector-etf-t0",
        "/app/low-buy",
      ]);
      return result;
    }),
  getFactorWeights: () => request<FactorWeightsResponse>("/settings/factor-weights"),
  updateFactorWeights: (weights: Record<string, number>) =>
    request<FactorWeightsResponse>("/settings/factor-weights", {
      method: "PUT",
      body: JSON.stringify({ weights })
    }).then((result) => {
      invalidateCache(["/screeners/low-buy", "/monitor/snapshot", "/bff/v1/workspace/monitor", "/bff/v1/workspace/settings"]);
      return result;
    }),
  updateSettings: (payload: Partial<SettingsPayload>) =>
    request<{ message: string; settings: SettingsPayload; restart_required: boolean }>("/settings", {
      method: "PUT",
      body: JSON.stringify(payload)
    }).then((result) => {
      invalidateCache(["/settings/runtime", "/bff/v1/workspace/settings"]);
      return result;
    }),
  checkDatabase: (database_url: string) =>
    request<DatabaseCheckResult>("/settings/database/check", {
      method: "POST",
      body: JSON.stringify({ database_url })
    }),
  getRuntimeStatus: () => requestCached<RuntimeStatus>("/settings/runtime", 10000),
  getAdminTasks: () => request<AdminTasksResponse>("/admin/tasks"),
  getAdminMetrics: () => request<AdminMetricsResponse>("/admin/metrics"),
  refreshLatestLowBuyData: () =>
    request<AdminLatestDataRefreshResponse>("/admin/latest-data/refresh", { method: "POST" }).then((result) => {
      invalidateCache(["/admin/metrics", "/monitor/snapshot", "/bff/v1/workspace/monitor", "/screeners/low-buy"]);
      return result;
    }),
  getLowBuyStrategies: () =>
    requestCached<LowBuyStrategyGovernanceResponse>("/screeners/low-buy/strategies", 30000),
  updateLowBuyStrategyGovernance: (strategyKey: string, payload: { status: "active" | "watch" | "paused"; reason?: string }) =>
    request<LowBuyStrategyGovernanceResponse>(`/screeners/low-buy/strategies/${encodeURIComponent(strategyKey)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }).then((result) => {
      invalidateCache([
        "/screeners/low-buy/strategies",
        "/screeners/low-buy",
        "/monitor/snapshot",
        "/bff/v1/workspace/monitor",
        "/bff/v1/workspace/settings",
      ]);
      return result;
    }),
  migrateDatabase: (payload: {
    target_database_url: string;
    source_database_url?: string;
    overwrite?: boolean;
    activate_on_restart?: boolean;
  }) =>
    request<DatabaseMigrationResult>("/settings/database/migrate", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listReplays: () => request<ReplayItem[]>("/replays"),
  runBacktest: (payload: {
    symbol: string;
    lookback_bars: number;
    bar_period: "1m" | "5m" | "15m";
    initial_position: number;
    walk_forward_windows: number;
  }) =>
    request<BacktestResult>("/backtests", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listBacktestRuns: (limit = 20) => request<BacktestRunListResponse>(`/backtests/runs?limit=${limit}`),
  runStrategyValidation: (payload: {
    strategies: string[];
    lookback_days: number;
    initial_cash?: number;
    max_signals_per_day?: number;
  }) =>
    request<StrategyValidationReport>("/strategy-validation", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  buildIntradayConfirmations: (payload: { symbols: string[]; period?: "1m" | "5m"; limit?: number }) =>
    request<IntradayConfirmationItem[]>("/intraday/confirmations", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getLowBuyCandidates: (
    strategy = "first_board",
    limit = 16,
    scanLimit = 48,
    includeHistory = false,
    scanMode: "quick" | "full" = "full"
  ) =>
    requestCached<LowBuyScreenerResult>(
      `/screeners/low-buy?strategy=${encodeURIComponent(strategy)}&limit=${limit}&scan_limit=${scanLimit}&scan_mode=${scanMode}&include_history=${includeHistory ? "true" : "false"}`,
      45000
    ),
  getLowBuyHistory: (strategy = "first_board") =>
    requestCached<LowBuyHistoryResult>(
      `/screeners/low-buy/history?strategy=${encodeURIComponent(strategy)}`,
      60000
    ),
  getLowBuyQuoteRefresh: (strategy: string, symbols: string[]) =>
    request<{ items: Record<string, LowBuyQuoteRefreshItem> }>(
      `/screeners/low-buy/quotes?strategy=${encodeURIComponent(strategy)}&symbols=${encodeURIComponent(symbols.join(","))}`
    ),
  getLowBuyPriorityBoard: (limit = 12, strategyVariant: StrategyVariant = "baseline", refresh: "cache" | "async" | "sync" = "cache") =>
    requestCached<LowBuyPriorityBoardResult>(
      `/screeners/low-buy/priority-board?limit=${limit}&refresh=${refresh}&strategy_variant=${strategyVariant}`,
      15000
    ),
  getLowBuyLifecycle: (strategy?: string, sync = false, limit = 100) =>
    request<{ items: LowBuyTradeLifecycle[] }>(
      `/screeners/low-buy/lifecycle?limit=${limit}&sync=${sync ? "true" : "false"}${strategy ? `&strategy=${encodeURIComponent(strategy)}` : ""}`
    ),
  getLowBuyExecutionBacktest: (strategy = "first_board", lookbackDays = 60, limit = 200) =>
    request<LowBuyExecutionBacktestResult>(
      `/screeners/low-buy/execution-backtest?strategy=${encodeURIComponent(strategy)}&lookback_days=${lookbackDays}&limit=${limit}`
    ),
  getStrategyTrackingItems: (params: StrategyTrackingParams = {}) =>
    requestCached<StrategyTrackingListResponse>(`/strategy-tracking/items?${strategyTrackingQuery(params)}`, 12000),
  getStrategyTrackingSnapshot: (params: StrategyTrackingParams = {}) =>
    requestCached<StrategyTrackingSnapshotResponse>(`/strategy-tracking/snapshot?${strategyTrackingQuery(params)}`, 12000),
  getStrategyTrackingDetail: (itemId: string) =>
    requestCached<StrategyTrackingDetailResponse>(`/strategy-tracking/items/${encodeURIComponent(itemId)}`, 12000),
  getStrategyTrackingReview: (params: StrategyTrackingParams = {}) =>
    requestCached<StrategyTrackingReviewResponse>(`/strategy-tracking/review?${strategyTrackingQuery(params)}`, 12000),
  getStrategyTrackingAudit: (params: StrategyTrackingParams = {}) =>
    requestCached<StrategyTrackingReviewResponse>(`/strategy-tracking/leakage-audit?${strategyTrackingQuery(params)}`, 12000),
  getStrategyTrackingHoldingAnalysis: (params: StrategyTrackingParams = {}) =>
    requestCached<StrategyTrackingHoldingAnalysisResponse>(`/strategy-tracking/holding-analysis?${strategyTrackingQuery(params)}`, 12000),
  getStrategyTrackingReport: (type: "daily" | "weekly", params: StrategyTrackingParams = {}) =>
    requestCached<StrategyTrackingReport>(`/strategy-tracking/reports/${type}?${strategyTrackingQuery(params)}`, 12000),
  getStrategyPromotionReview: (strategy = "n_pattern_long_wash") =>
    requestCached<StrategyPromotionReview>(`/strategy/promotion-review?strategy=${encodeURIComponent(strategy)}`, 12000),
  getPaperAccount: () => request<PaperAccount>("/paper/account"),
  getPaperWorkspaceBff: () =>
    request<PaperWorkspaceBffResponse>("/bff/v1/workspace/paper?order_limit=80&trade_limit=300&run_limit=20"),
  pausePaperAccount: () => request<PaperAccount>("/paper/account/pause", { method: "POST" }),
  resumePaperAccount: () => request<PaperAccount>("/paper/account/resume", { method: "POST" }),
  getPaperPositions: () => request<PaperPositionsResponse>("/paper/positions"),
  refreshPaperPositions: () =>
    request<PaperPositionsResponse>("/paper/positions/refresh", { method: "POST" }),
  getPaperOrders: (limit = 50) => request<PaperOrder[]>(`/paper/orders?limit=${limit}`),
  getPaperTrades: (limit = 50) => request<PaperTradesResponse>(`/paper/trades?limit=${limit}`),
  getPaperStockPnl: () => request<PaperStockPnlResponse>("/paper/performance/stock-pnl"),
  reconcilePaperAccount: (payload: { account_id?: number; apply: boolean }) =>
    request<PaperLedgerRepairResponse>("/paper/account/reconcile", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getPaperTradeTags: (tradeId: number) => request<PaperTradeTag[]>(`/paper/trades/${tradeId}/tags`),
  getPaperTradeTagsBatch: (tradeIds: number[]) =>
    request<{ items: Record<string, PaperTradeTag[]> }>(
      `/paper/trades/tags?trade_ids=${encodeURIComponent(tradeIds.join(","))}`,
    ),
  addPaperTradeTag: (tradeId: number, payload: PaperTradeTagCreate) =>
    request<PaperTradeTag>(`/paper/trades/${tradeId}/tags`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deletePaperTradeTag: (tradeId: number, tagId: number) =>
    request<{ message: string; tag_id: number }>(`/paper/trades/${tradeId}/tags/${tagId}`, { method: "DELETE" }),
  getPaperPerformance: () => request<PaperPerformance>("/paper/performance"),
  getPaperPerformanceByStrategy: () => request<PaperGroupedPerformance[]>("/paper/performance/by-strategy"),
  getPaperPerformanceByMarketState: () => request<PaperGroupedPerformance[]>("/paper/performance/by-market-state"),
  getPaperPerformanceByStrategyMarketState: () =>
    request<PaperStrategyMarketPerformance[]>("/paper/performance/by-strategy-market-state"),
  getPaperPerformanceByTag: () => request<PaperTagPerformance[]>("/paper/performance/by-tag"),
  getPaperPerformanceDashboard: (days = 30) =>
    request<PaperPerformanceDashboard>(`/paper/performance/dashboard?days=${days}`),
  getPaperSectorEtfT0Performance: () =>
    request<PaperSectorEtfT0Performance>("/paper/performance/sector-etf-t0"),
  archivePaperPerformance: () =>
    request<{ account_id: number; date: string; strategies_saved: number; market_states_saved: number; report_saved: boolean }>(
      "/paper/performance/archive",
      { method: "POST" }
    ),
  evaluatePaperRiskEvents: () => request<RiskEventItem[]>("/paper/risk/evaluate", { method: "POST" }),
  getPaperRiskEvents: () => request<RiskEventItem[]>("/paper/risk/events"),
  getPaperAutoTradingStatus: () => request<PaperAutoTradingStatus>("/paper/auto-trading/status"),
  getPaperAutoTradingRuns: (limit = 20) => request<PaperAgentRun[]>(`/paper/auto-trading/runs?limit=${limit}`),
  createPaperOrder: (payload: PaperOrderCreate) =>
    request<PaperOrder>("/paper/orders", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
};

function strategyTrackingQuery(params: StrategyTrackingParams): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    query.set(key, String(value));
  }
  if (!query.has("limit")) {
    query.set("limit", "30");
  }
  if (!query.has("offset")) {
    query.set("offset", "0");
  }
  return query.toString();
}
