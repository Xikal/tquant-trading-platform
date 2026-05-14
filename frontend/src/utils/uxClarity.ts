export function scoreStars(scoreText?: string): string {
  const score = Number(scoreText);
  if (!Number.isFinite(score)) return "☆☆☆☆☆";
  const filled = Math.max(1, Math.min(5, Math.round(score / 20)));
  return "★★★★★".slice(0, filled) + "☆☆☆☆☆".slice(filled);
}

export function directActionTitle(actionText?: string): string {
  const text = (actionText ?? "").trim();
  if (!text || text === "暂不操作") return "先不动";
  if (text.includes("确定") || text.includes("买入") || text.includes("按计划")) return "可以按计划";
  if (text.includes("正") || text.includes("先买")) return "等回落企稳后先买";
  if (text.includes("反") || text.includes("先卖")) return "冲高变弱先卖";
  if (text.includes("观察") || text.includes("等待") || text.includes("接近")) return "等确认";
  return text;
}

export function playbookActionLabel(state?: string): string {
  if (state === "buy_now") return "现在可买";
  if (state === "soft_buy_now") return "小仓试买";
  if (state === "near_entry") return "等确认";
  if (state === "watch") return "继续观察";
  if (state === "avoid") return "今天放弃";
  return "等待";
}

export interface BacktestVerdictThresholds {
  minReturnPct: number;
  minSharpe: number;
  maxDrawdownPct: number;
  cautiousMinReturnPct: number;
  cautiousMaxDrawdownPct: number;
}

export function backtestVerdict(
  totalReturn: number | undefined,
  sharpe: number | undefined,
  maxDrawdown: number | undefined,
  thresholds: BacktestVerdictThresholds,
): {
  title: string;
  detail: string;
  tone: "ok" | "warn" | "bad";
} {
  if (typeof totalReturn !== "number" || !Number.isFinite(totalReturn)) {
    return { title: "结果生成中", detail: "任务完成后优先看收益、回撤和胜率。", tone: "warn" };
  }
  if (
    totalReturn > thresholds.minReturnPct
    && (sharpe ?? 0) >= thresholds.minSharpe
    && (maxDrawdown ?? 0) > thresholds.maxDrawdownPct
  ) {
    return { title: "值得继续验证", detail: "收益为正且回撤可控，可进入样本外和小仓模拟验证。", tone: "ok" };
  }
  if (totalReturn >= thresholds.cautiousMinReturnPct && (maxDrawdown ?? 0) > thresholds.cautiousMaxDrawdownPct) {
    return { title: "谨慎使用", detail: "收益没有明显恶化，但仍需检查成交明细、手续费和极端回撤。", tone: "warn" };
  }
  return { title: "不建议使用", detail: "当前回测收益或回撤不达标，先不要进入自动交易。", tone: "bad" };
}
