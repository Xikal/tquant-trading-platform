import { color } from "../../ui/theme/tokens";

export const backtestChartColor = {
  strategy: color.info,
  benchmark: color.accentGold,
  drawdown: color.error,
  success: color.success,
  warning: color.warning,
  textPrimary: color.text1,
  textSecondary: color.text2,
  textMuted: color.text3,
  border: color.border,
  surface: color.bgElevated,
} as const;

export const backtestComparePalette = [
  backtestChartColor.strategy,
  backtestChartColor.benchmark,
  backtestChartColor.drawdown,
  backtestChartColor.success,
  backtestChartColor.warning,
  color.brandHover,
] as const;

export function withAlpha(hexColor: string, alpha: number): string {
  const normalized = hexColor.replace("#", "");
  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}
