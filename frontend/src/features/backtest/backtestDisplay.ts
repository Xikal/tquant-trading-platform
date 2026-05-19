import type { BacktestExecutionModel, BacktestResourceTier } from "../../api/backtests";
import { STRATEGY_OPTIONS, type StrategyOption } from "../../constants/strategies";
import { formatPct } from "../../utils/backtestFormatters";
export {
  backtestVerdictThresholds,
  currentBacktestVerdictThresholds,
  loadBacktestVerdictThresholds,
  type BacktestVerdictThresholdMap,
} from "./backtestVerdictThresholds";
export { formatBacktestStrategy, formatBacktestStrategies, formatPct } from "../../utils/backtestFormatters";

export const BACKTEST_STRATEGY_OPTIONS = STRATEGY_OPTIONS;
export type BacktestStrategyOption = StrategyOption;

export const BACKTEST_EXECUTION_MODELS: Array<[BacktestExecutionModel, string]> = [
  ["conservative_slippage", "保守滑点成交"],
  ["open_price", "开盘价加滑点"],
  ["next_open", "次日保守成交"],
  ["close_price", "收盘价加滑点"],
  ["vwap", "VWAP 加滑点"],
  ["market_impact", "市场冲击成本"],
];

export const BACKTEST_RESOURCE_TIER_OPTIONS: Array<[BacktestResourceTier, string]> = [
  ["light", "轻量验证"],
  ["full", "标准回测"],
  ["walk_forward", "重型 Walk-forward"],
];

export const BACKTEST_RESOURCE_TIER_HINTS: Record<BacktestResourceTier, string> = {
  light: "轻量：快速判断参数方向，速度最快，适合初筛，不作为上线依据。",
  full: "标准：覆盖完整交易成本和风控口径，适合对比生产策略。",
  walk_forward: "Walk-forward：样本外稳健性验证，耗时最长，适合上线前确认过拟合风险。",
};

export const OPTIMIZATION_TARGET_OPTIONS = [
  ["sharpe", "Sharpe"],
  ["total_return_pct", "总收益"],
  ["profit_factor", "利润因子"],
  ["win_rate_pct", "胜率"],
] as const;

export function pboRiskMeta(value?: string | null): { label: string; tone: string } {
  const key = String(value || "").toLowerCase();
  if (key === "low") return { label: "低风险", tone: "low" };
  if (key === "medium") return { label: "中风险", tone: "medium" };
  if (key === "high") return { label: "高风险", tone: "high" };
  return { label: "--", tone: "unknown" };
}

export function formatNumber(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2);
}

export function formatInteger(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export function formatMoney(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export function formatPrice(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toFixed(3);
}

export function formatRatioPct(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return formatPct(Math.abs(value) <= 1 ? value * 100 : value, 1);
}

export function formatMoneyOrPct(money?: number | null, pct?: number | null): string {
  if (typeof money === "number" && Number.isFinite(money)) {
    return formatMoney(money);
  }
  return formatPct(pct);
}

export function percentFromRatio(value?: number | null): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.abs(value) <= 1 ? value * 100 : value;
}

export function toneFromNumber(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral";
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatResourceTier(value?: string | null): string {
  const tier = String(value || "").trim().toLowerCase();
  const matched = BACKTEST_RESOURCE_TIER_OPTIONS.find(([key]) => key === tier);
  return matched?.[1] || "标准回测";
}

export function resourceTierHint(value?: BacktestResourceTier | string | null): string {
  const tier = normalizeResourceTier(value);
  return BACKTEST_RESOURCE_TIER_HINTS[tier];
}

function normalizeResourceTier(value?: BacktestResourceTier | string | null): BacktestResourceTier {
  const tier = String(value || "").trim().toLowerCase();
  if (tier === "light" || tier === "walk_forward") {
    return tier;
  }
  return "full";
}
