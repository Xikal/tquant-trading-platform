import { STRATEGY_OPTIONS } from "../constants/strategies";

const STRATEGY_LABELS = Object.fromEntries(STRATEGY_OPTIONS) as Record<string, string>;

export function formatBacktestStrategy(value?: string | null): string {
  if (!value) return "--";
  return STRATEGY_LABELS[value] ?? value;
}

export function formatBacktestStrategies(values?: string[] | null): string {
  if (!values?.length) return "--";
  return values.map(formatBacktestStrategy).join(" / ");
}

export function formatPct(value?: number | null, digits = 2): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}
