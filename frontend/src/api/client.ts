import type {
  AnalysisResponse,
  AiDecisionSupportRequest,
  AiDecisionSupportResponse,
  BacktestResult,
  DatabaseCheckResult,
  DatabaseMigrationResult,
  LowBuyScreenerResult,
  LowBuyHistoryResult,
  LowBuyQuoteRefreshItem,
  LowBuyPriorityBoardResult,
  LowBuyExecutionBacktestResult,
  LowBuyTradeLifecycle,
  PaperAccount,
  PaperGroupedPerformance,
  PaperOrder,
  PaperOrderCreate,
  PaperAccessResponse,
  PaperPerformance,
  PaperPositionsResponse,
  PaperTradesResponse,
  RuntimeStatus,
  Instrument,
  IntradayConfirmationItem,
  ReplayItem,
  RiskEventItem,
  SettingsPayload,
  StrategyValidationReport,
  WatchlistItem,
  WatchlistSignal
} from "../types";
import { invalidateCache, request, requestCached } from "./base";

export const api = {
  listInstruments: (keyword = "", kind = "all") =>
    request<{ items: Instrument[]; total: number }>(
      `/instruments?keyword=${encodeURIComponent(keyword)}&kind=${kind}&page=1&page_size=20`
    ),
  syncInstruments: () => request<{ message: string; result: Record<string, number> }>(`/instruments/sync`, { method: "POST" }),
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
  updateSettings: (payload: Partial<SettingsPayload>) =>
    request<{ message: string; settings: SettingsPayload; restart_required: boolean }>("/settings", {
      method: "PUT",
      body: JSON.stringify(payload)
    }).then((result) => {
      invalidateCache(["/settings/runtime"]);
      return result;
    }),
  checkDatabase: (database_url: string) =>
    request<DatabaseCheckResult>("/settings/database/check", {
      method: "POST",
      body: JSON.stringify({ database_url })
    }),
  getRuntimeStatus: () => requestCached<RuntimeStatus>("/settings/runtime", 10000),
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
  getLowBuyPriorityBoard: (limit = 12) =>
    requestCached<LowBuyPriorityBoardResult>(`/screeners/low-buy/priority-board?limit=${limit}`, 3000),
  getLowBuyLifecycle: (strategy?: string, sync = false, limit = 100) =>
    request<{ items: LowBuyTradeLifecycle[] }>(
      `/screeners/low-buy/lifecycle?limit=${limit}&sync=${sync ? "true" : "false"}${strategy ? `&strategy=${encodeURIComponent(strategy)}` : ""}`
    ),
  getLowBuyExecutionBacktest: (strategy = "first_board", lookbackDays = 60, limit = 200) =>
    request<LowBuyExecutionBacktestResult>(
      `/screeners/low-buy/execution-backtest?strategy=${encodeURIComponent(strategy)}&lookback_days=${lookbackDays}&limit=${limit}`
    ),
  getPaperAccount: () => request<PaperAccount>("/paper/account"),
  pausePaperAccount: () => request<PaperAccount>("/paper/account/pause", { method: "POST" }),
  resumePaperAccount: () => request<PaperAccount>("/paper/account/resume", { method: "POST" }),
  getPaperPositions: () => request<PaperPositionsResponse>("/paper/positions"),
  refreshPaperPositions: () =>
    request<PaperPositionsResponse>("/paper/positions/refresh", { method: "POST" }),
  getPaperOrders: (limit = 50) => request<PaperOrder[]>(`/paper/orders?limit=${limit}`),
  getPaperTrades: (limit = 50) => request<PaperTradesResponse>(`/paper/trades?limit=${limit}`),
  getPaperPerformance: () => request<PaperPerformance>("/paper/performance"),
  getPaperPerformanceByStrategy: () => request<PaperGroupedPerformance[]>("/paper/performance/by-strategy"),
  getPaperPerformanceByMarketState: () => request<PaperGroupedPerformance[]>("/paper/performance/by-market-state"),
  evaluatePaperRiskEvents: () => request<RiskEventItem[]>("/paper/risk/evaluate", { method: "POST" }),
  getPaperRiskEvents: () => request<RiskEventItem[]>("/paper/risk/events"),
  createPaperOrder: (payload: PaperOrderCreate) =>
    request<PaperOrder>("/paper/orders", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
};
