import { Tag } from "antd";
import type { StrategyTrackingPerformance, StrategyTrackingSummary } from "../../types";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function StrategyTrackingReviewPanel({
  summary,
  performance,
}: {
  summary: StrategyTrackingSummary;
  performance: StrategyTrackingPerformance[];
}) {
  const best = [...performance].sort((left, right) => right.avg_max_gain_pct - left.avg_max_gain_pct)[0];
  const worst = [...performance].sort((left, right) => right.stop_loss_rate - left.stop_loss_rate)[0];
  const problemText = reviewProblem(summary, worst);
  const nextText = nextReviewFocus(summary, best, worst);
  return (
    <section className="panel strategy-tracking-review">
      <div className="strategy-tracking-review-head">
        <strong>一键复盘</strong>
        <span>样本 {summary.tracking_count} · 有效 {summary.active_count}</span>
      </div>
      <p>{problemText}</p>
      <div className="strategy-tracking-review-tags">
        {best ? <Tag color="green">最佳 {best.strategy_name} {formatPct(best.avg_max_gain_pct)}</Tag> : null}
        {worst ? <Tag color="red">风险 {worst.strategy_name} 止损率 {formatPct(worst.stop_loss_rate)}</Tag> : null}
        <Tag>{nextText}</Tag>
      </div>
    </section>
  );
}

function reviewProblem(summary: StrategyTrackingSummary, worst?: StrategyTrackingPerformance): string {
  if (!summary.tracking_count) {
    return "当前区间没有生产策略跟踪信号，复盘结论暂缓。";
  }
  if (summary.stopped_count > 0) {
    return `当前区间已有 ${summary.stopped_count} 条信号跌破止损，优先核对失败原因和入场过滤。`;
  }
  if (worst && worst.stop_loss_rate >= 20) {
    return `${worst.strategy_name} 的止损率偏高，需检查支撑确认和回踩深度阈值。`;
  }
  if (summary.avg_current_return_pct < 0) {
    return "当前区间信号后的平均收益为负，需降低弱市场状态下的信号权重。";
  }
  return "当前区间生产策略跟踪状态正常，继续观察买点触达和回撤变化。";
}

function nextReviewFocus(
  summary: StrategyTrackingSummary,
  best?: StrategyTrackingPerformance,
  worst?: StrategyTrackingPerformance,
): string {
  if (!summary.tracking_count) {
    return "下一阶段等待新增样本";
  }
  if (summary.data_quality !== "ok") {
    return "下一阶段先补数据质量";
  }
  if (worst && worst.stop_loss_rate >= 20) {
    return "下一阶段收紧风险榜复核";
  }
  if (best) {
    return `下一阶段跟踪 ${best.strategy_name}`;
  }
  return "下一阶段扩大样本外观察";
}
