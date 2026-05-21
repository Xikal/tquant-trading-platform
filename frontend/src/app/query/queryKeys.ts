export const queryKeys = {
  monitor: ["monitor"] as const,
  monitorWorkspace: (priorityLimit: number) => ["monitor", "workspace", priorityLimit] as const,
  holdings: ["holdings"] as const,
  priorityBoard: (strategy: string, limit: number) => ["playbook", "priority", strategy, limit] as const,
  paper: ["paper"] as const,
  paperWorkspace: ["paper", "workspace"] as const,
  settings: ["settings"] as const,
  strategyWorkspace: ["strategy", "workspace"] as const,
  factorMining: ["factor-mining"] as const,
};
