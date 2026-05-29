import type { StrategyTrackingListResponse } from "../../types";

export function StrategyTrackingFriendlySummary({ result, range }: { result: StrategyTrackingListResponse; range: number }) {
  const summary = result.summary;
  const riskCount = summary.stopped_count + summary.needs_review_count + summary.abnormal_return_count;
  return (
    <section className="panel strategy-tracking-friendly-summary">
      <strong>
        {range === 1 ? "今日" : `近 ${range} 日`}共有 {summary.tracking_count} 条推荐，其中 {summary.in_entry_zone_count} 条到达计划买点，
        {summary.stopped_count} 条已跌破风险线，{riskCount} 条需要优先复核。
      </strong>
      <span>当前更适合先看“可以重点看”和“已经走弱”的样本，持有分析仅用于复盘观察。</span>
    </section>
  );
}
