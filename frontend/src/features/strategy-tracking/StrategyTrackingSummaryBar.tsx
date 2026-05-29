import { Alert, Space, Statistic } from "antd";
import type { StrategyTrackingSummary } from "../../types";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function StrategyTrackingSummaryBar({ summary }: { summary: StrategyTrackingSummary }) {
  return (
    <section className="workspace-panel compact-panel">
      {summary.data_quality !== "ok" ? (
        <Alert type="warning" showIcon title={summary.data_quality_text} style={{ marginBottom: 10 }} />
      ) : null}
      <Space wrap size={18}>
        <Statistic title="当前跟踪" value={summary.tracking_count} />
        <Statistic title="今日新增" value={summary.today_new_count} />
        <Statistic title="仍在买点" value={summary.in_entry_zone_count} />
        <Statistic title="平均涨幅" value={formatPct(summary.avg_current_return_pct)} />
        <Statistic title="最高涨幅中位数" value={formatPct(summary.median_max_gain_pct)} />
        <Statistic title="跌破止损" value={summary.stopped_count} />
      </Space>
    </section>
  );
}
