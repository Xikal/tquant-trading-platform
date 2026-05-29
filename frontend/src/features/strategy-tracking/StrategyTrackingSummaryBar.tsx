import { Alert } from "antd";
import type { StrategyTrackingSummary } from "../../types";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function StrategyTrackingSummaryBar({ summary }: { summary: StrategyTrackingSummary }) {
  const metrics = [
    { label: "当前跟踪", value: summary.tracking_count },
    { label: "今日新增", value: summary.today_new_count },
    { label: "仍在买点", value: summary.in_entry_zone_count },
    { label: "平均涨幅", value: formatPct(summary.avg_current_return_pct) },
    { label: "最高涨幅中位数", value: formatPct(summary.median_max_gain_pct) },
    { label: "跌破止损", value: summary.stopped_count },
  ];
  return (
    <section className="panel strategy-tracking-summary">
      {summary.data_quality !== "ok" ? (
        <Alert type="warning" showIcon title={summary.data_quality_text} style={{ marginBottom: 10 }} />
      ) : null}
      <div className="strategy-tracking-metric-grid">
        {metrics.map((item) => (
          <div className="strategy-tracking-metric" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
