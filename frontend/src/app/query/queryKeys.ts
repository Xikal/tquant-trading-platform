export const queryKeys = {
  monitor: ["monitor"] as const,
  monitorWorkspace: (priorityLimit: number) => ["monitor", "workspace", priorityLimit] as const,
  holdings: ["holdings"] as const,
  priorityBoard: (strategy: string, limit: number) => ["playbook", "priority", strategy, limit] as const,
  paper: ["paper"] as const,
  paperWorkspace: ["paper", "workspace"] as const,
  settings: ["settings"] as const,
  strategyTracking: (params: Record<string, unknown>) => ["strategy-tracking", params] as const,
  strategyTrackingDetail: (itemId: string | null) => ["strategy-tracking", "detail", itemId] as const,
  strategyTrackingHoldingAnalysis: (params: Record<string, unknown>) => ["strategy-tracking", "holding-analysis", params] as const,
  strategyTrackingReport: (type: string, params: Record<string, unknown>) => ["strategy-tracking", "report", type, params] as const,
  factorMining: ["factor-mining"] as const,
};
