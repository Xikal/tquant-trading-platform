import type { StrategyTrackingItem } from "../../types";

export function signalStateText(item: Pick<StrategyTrackingItem, "signal_state" | "signal_text">): string {
  return item.signal_text || signalStateLabel(item.signal_state);
}

export function signalStateKindText(signalState: string): string {
  if (signalState === "buy_now") return "买入类：确定买入";
  if (signalState === "soft_buy_now") return "买入类：小仓试买";
  if (signalState === "near_entry") return "观察类：接近买点，不是买入推荐";
  if (signalState === "observe_confirmed") return "观察类：只提醒观察，不进生产买入排行";
  return "跟踪类：仅用于复盘";
}

export function signalStateHelpText(signalState: string): string {
  if (signalState === "buy_now") return "价格、结构和风控已满足，属于生产买入类信号。";
  if (signalState === "soft_buy_now") return "只适合小仓试买，仍需按仓位和止损执行。";
  if (signalState === "near_entry") return "接近买点只代表快到观察区，不能提前买。";
  if (signalState === "observe_confirmed") return "观察确认只用于后续触发，不代表可以买入。";
  return "该信号只用于后验跟踪和复盘。";
}

function signalStateLabel(signalState: string): string {
  if (signalState === "buy_now") return "确定可买";
  if (signalState === "soft_buy_now") return "小仓试买";
  if (signalState === "near_entry") return "接近买点";
  if (signalState === "observe_confirmed") return "观察确认";
  return signalState || "未知信号";
}
