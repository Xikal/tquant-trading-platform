import type { StrategyTrackingListResponse } from "../../types";

export function StrategyTrackingFriendlySummary({ result, range }: { result: StrategyTrackingListResponse; range: number }) {
  const summary = result.summary;
  const riskCount = summary.stopped_count + summary.needs_review_count + summary.abnormal_return_count;
  return (
    <section className="panel strategy-tracking-friendly-summary">
      <strong>
        {range === 1 ? "今日" : `近 ${range} 日`}共有 {summary.tracking_count} 条跟踪信号，其中 {summary.in_entry_zone_count} 条到达计划买点，
        {summary.stopped_count} 条已跌破风险线，{riskCount} 条需要优先复核。
      </strong>
      <span>只有“确定可买”和“小仓试买”属于买入类；“接近买点”和“观察确认”只用于提醒和复盘。</span>
    </section>
  );
}
