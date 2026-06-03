export const queryKeys = {
  monitor: ["monitor"] as const,
  monitorWorkspace: (priorityLimit: number) => ["monitor", "workspace", priorityLimit] as const,
  monitorSnapshot: (priorityLimit: number) => ["monitor", "snapshot", priorityLimit] as const,
  holdings: ["holdings"] as const,
  priorityBoard: (strategy: string, limit: number) => ["playbook", "priority", strategy, limit] as const,
  paper: ["paper"] as const,
  paperWorkspace: ["paper", "workspace"] as const,
  settings: ["settings"] as const,
  settingsWorkspace: ["settings", "workspace"] as const,
  backtestRuns: (limit: number) => ["backtest", "runs", limit] as const,
  strategyTracking: (params: Record<string, unknown>) => ["strategy-tracking", params] as const,
  strategyTrackingDetail: (itemId: string | null) => ["strategy-tracking", "detail", itemId] as const,
  strategyTrackingHoldingAnalysis: (params: Record<string, unknown>) =>
    ["strategy-tracking", "holding-analysis", params] as const,
  strategyTrackingReport: (type: string, params: Record<string, unknown>) =>
    ["strategy-tracking", "report", type, params] as const,
  trackRecordDrift: (windowDays: number) => ["track-record", "drift", windowDays] as const,
  tradingExperienceReadiness: ["trading-experience", "readiness"] as const,
  tradingExperienceReview: ["trading-experience", "review"] as const,
  tradingExperienceJournal: (accountId?: number | null) => ["trading-experience", "journal", accountId] as const,
  tradingExperienceVolumeTags: (symbol?: string | null) => ["trading-experience", "volume-tags", symbol] as const,
  tradingExperienceRelativeStrength: ["trading-experience", "relative-strength"] as const,
  tradingExperienceHoldingDiscipline: (accountId?: number | null) =>
    ["trading-experience", "holding-discipline", accountId] as const,
  tradingExperienceLimitUp: ["trading-experience", "limit-up"] as const,
  tradingExperienceTTrade: (accountId?: number | null) => ["trading-experience", "t-trade", accountId] as const,
};
