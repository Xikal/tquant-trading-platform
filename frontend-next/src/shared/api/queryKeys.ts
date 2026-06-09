import type { ApiFeature, ApiOperationName, OperationPathOptions } from "./operations";

const ROOT = "frontend-next";

export function operationQueryKey(name: ApiOperationName, options: OperationPathOptions = {}) {
  return [ROOT, "operation", name, options] as const;
}

export const queryKeys = {
  root: [ROOT] as const,
  feature: (feature: ApiFeature) => [ROOT, "feature", feature] as const,
  operation: operationQueryKey,

  authMe: operationQueryKey("authMe"),

  monitorWorkspace: (view: "action" | "market" | "full") => operationQueryKey("monitorWorkspace", { query: { view } }),
  monitorSnapshot: (priorityLimit = 12) => operationQueryKey("monitorSnapshot", { query: { priority_limit: priorityLimit } }),
  marketTradingSession: operationQueryKey("marketTradingSession"),
  marketBreadth: operationQueryKey("marketBreadth"),
  marketSectorRelativeStrength: (limit = 8, perSectorLimit = 10) =>
    operationQueryKey("marketSectorRelativeStrength", { query: { limit, per_sector_limit: perSectorLimit } }),
  watchlist: operationQueryKey("watchlist"),
  watchlistSignals: operationQueryKey("watchlistSignals"),
  watchlistQuotes: operationQueryKey("watchlistQuotes"),

  strategyWorkspace: operationQueryKey("strategyWorkspace"),
  strategyTrackingItems: (query: OperationPathOptions["query"] = {}) => operationQueryKey("strategyTrackingItems", { query }),
  strategyTrackingDetail: (itemId: string) => operationQueryKey("strategyTrackingDetail", { path: { item_id: itemId } }),
  strategyTrackingSummary: (query: OperationPathOptions["query"] = {}) => operationQueryKey("strategyTrackingSummary", { query }),
  strategyTrackingPerformance: (query: OperationPathOptions["query"] = {}) => operationQueryKey("strategyTrackingPerformance", { query }),
  strategyTrackingReview: (query: OperationPathOptions["query"] = {}) => operationQueryKey("strategyTrackingReview", { query }),
  tradeJournal: (query: OperationPathOptions["query"] = {}) => operationQueryKey("tradeJournal", { query }),
  relativeStrength: (limit = 30) => operationQueryKey("relativeStrength", { query: { limit } }),

  analyzeSymbol: (symbol: string) => operationQueryKey("analyzeSymbol", { query: { symbol } }),
  analyzeBatch: operationQueryKey("analyzeBatch"),
  quote: (symbol: string) => operationQueryKey("quote", { path: { symbol } }),
  symbolSearch: (keyword = "") => operationQueryKey("symbolSearch", { query: { keyword } }),
  kline: (symbol: string) => operationQueryKey("kline", { path: { symbol } }),

  lowBuyScreener: (query: OperationPathOptions["query"] = {}) => operationQueryKey("lowBuyScreener", { query }),
  lowBuyPriorityBoard: (limit = 12) => operationQueryKey("lowBuyPriorityBoard", { query: { limit } }),
  lowBuyQuotes: (symbols: string[] = [], strategy?: string) => operationQueryKey("lowBuyQuotes", { query: { symbols, strategy } }),
  lowBuyStrategies: operationQueryKey("lowBuyStrategies"),
  strategiesMeta: operationQueryKey("strategiesMeta"),

  settingsWorkspace: operationQueryKey("settingsWorkspace"),
  settings: operationQueryKey("settings"),
  settingsRuntime: operationQueryKey("settingsRuntime"),
  sectorExclusions: operationQueryKey("sectorExclusions"),
  factorWeights: operationQueryKey("factorWeights"),
  featureFlags: operationQueryKey("featureFlags"),
  featureFlagAudit: operationQueryKey("featureFlagAudit"),
  quantParameters: operationQueryKey("quantParameters"),

  backtestRuns: operationQueryKey("backtestRuns"),
  backtestRunDetail: (runId: string | number) => operationQueryKey("backtestRunDetail", { path: { run_id: runId } }),
  backtestRunEquity: (runId: string | number) => operationQueryKey("backtestRunEquity", { path: { run_id: runId } }),
  backtestRunTrades: (runId: string | number) => operationQueryKey("backtestRunTrades", { path: { run_id: runId } }),

  dataQualityCoverage: operationQueryKey("dataQualityCoverage"),
  dataQualitySla: operationQueryKey("dataQualitySla"),
  runtimeTasks: operationQueryKey("runtimeTasks"),
  runtimeTaskSummary: operationQueryKey("runtimeTaskSummary"),
  adminMetrics: operationQueryKey("adminMetrics"),
  adminTasks: operationQueryKey("adminTasks"),
};
