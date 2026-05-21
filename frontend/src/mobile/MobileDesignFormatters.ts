type Tone = "positive" | "negative" | "neutral" | "warning";

export function splitPriorityItems<T extends { buy_signal_state?: string }>(items: T[]) {
  const buyNow = items.filter((item) => item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now");
  const nearEntry = items.filter((item) => item.buy_signal_state === "observe_confirmed" || item.buy_signal_state === "near_entry");
  const watch = items.filter((item) => !buyNow.includes(item) && !nearEntry.includes(item));
  return { buyNow, nearEntry, watch };
}

export function formatPrice(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value >= 100 ? value.toFixed(2) : value.toFixed(3);
}

export function formatAmountCompact(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits: 0
  });
}

export function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function formatRatioPercent(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${(value * 100).toFixed(0)}%`;
}

export function formatSigned(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

export function signedTone(value: number | null | undefined): Tone {
  if (typeof value !== "number" || !Number.isFinite(value)) return "neutral";
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

export function signalTone(action: string | undefined): Tone {
  if (action === "positive_t" || action === "buy_now" || action === "soft_buy_now") return "positive";
  if (action === "negative_t" || action === "avoid") return "negative";
  if (action === "observe_confirmed" || action === "near_entry") return "warning";
  return "neutral";
}

export function actionLabel(action: string | undefined) {
  switch (action) {
    case "positive_t":
      return "先买后卖";
    case "negative_t":
      return "先卖后接回";
    case "buy_now":
      return "买入";
    case "soft_buy_now":
      return "买入";
    case "observe_confirmed":
      return "观察确认";
    case "near_entry":
      return "等待";
    case "watch":
      return "观察";
    case "avoid":
      return "放弃";
    case "hold":
      return "观望";
    default:
      return action || "--";
  }
}

export function riskLabel(level: string) {
  switch (level) {
    case "low":
      return "低";
    case "medium":
      return "中";
    case "high":
      return "高";
    default:
      return level;
  }
}
