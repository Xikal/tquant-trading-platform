export type StrategyCommandTarget = "playbook" | "strategy-tracking";

export interface StrategyCommand {
  key: string;
  label: string;
  target: StrategyCommandTarget;
  scopeLabel: string;
  aliases: readonly string[];
}

// Navigation-only registry. Strategy truth, ranking and production eligibility stay backend-owned.
export const strategyCommandRegistry: readonly StrategyCommand[] = [
  {
    key: "first_board",
    label: "首板回调",
    target: "playbook",
    scopeLabel: "生产策略",
    aliases: ["首板", "first_board", "first board"],
  },
  {
    key: "volume_shrink",
    label: "量能低吸",
    target: "playbook",
    scopeLabel: "生产策略",
    aliases: ["量能", "缩量", "volume_shrink", "volume shrink"],
  },
  {
    key: "late_session_strong_support",
    label: "尾盘强支撑",
    target: "playbook",
    scopeLabel: "观察策略",
    aliases: ["尾盘", "强支撑", "late_session_strong_support"],
  },
  {
    key: "n_pattern_long_wash",
    label: "N形洗盘研究",
    target: "strategy-tracking",
    scopeLabel: "研究只读",
    aliases: ["n形", "n字", "n_pattern_long_wash", "n pattern"],
  },
] as const;

export function strategyCommandSearchText(command: StrategyCommand): string {
  return [command.key, command.label, command.scopeLabel, ...command.aliases].join(" ").toLowerCase();
}

export function normalizedStrategyKey(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed.length > 80) return null;
  return /^[a-z0-9_:-]+$/i.test(trimmed) ? trimmed : null;
}
