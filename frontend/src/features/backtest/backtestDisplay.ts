import type { BacktestExecutionModel } from "../../api/backtests";

export const BACKTEST_STRATEGY_OPTIONS = [
  ["first_board", "首板回调"],
  ["volume_shrink", "量能低吸"],
  ["late_session_strong_support", "收盘强势承接"],
  ["core_midcap_vwap_ma5_retrace", "中军回踩"],
  ["sector_mainline_first_divergence_low_buy", "主线首分歧"],
] as const;

export const BACKTEST_EXECUTION_MODELS: Array<[BacktestExecutionModel, string]> = [
  ["open_price", "开盘价成交"],
  ["next_open", "次日开盘"],
  ["close_price", "收盘价成交"],
  ["vwap", "VWAP 近似"],
];

export const OPTIMIZATION_TARGET_OPTIONS = [
  ["sharpe", "Sharpe"],
  ["total_return_pct", "总收益"],
  ["profit_factor", "利润因子"],
  ["win_rate_pct", "胜率"],
] as const;

const STRATEGY_LABELS = Object.fromEntries(BACKTEST_STRATEGY_OPTIONS) as Record<string, string>;

export function formatBacktestStrategy(value?: string | null): string {
  if (!value) return "--";
  return STRATEGY_LABELS[value] ?? value;
}

export function formatBacktestStrategies(values?: string[] | null): string {
  if (!values?.length) return "--";
  return values.map(formatBacktestStrategy).join(" / ");
}

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

export function formatPct(value?: number | null, digits = 2): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
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
