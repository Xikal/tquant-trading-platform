import { Alert, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { UseQueryResult } from "@tanstack/react-query";
import type { StrategyTrackingViewMode } from "../../stores/strategyTrackingStore";
import type {
  StrategyTrackingListResponse,
  StrategyTrackingReport,
  StrategyTrackingSegment,
  StrategyTrackingShadowObservation,
} from "../../types";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function StrategyTrackingDiagnosticsPanel({
  result,
  weeklyReport,
  viewMode = "beginner",
}: {
  result: StrategyTrackingListResponse;
  weeklyReport?: UseQueryResult<StrategyTrackingReport, Error>;
  viewMode?: StrategyTrackingViewMode;
}) {
  const failureTags = failureTagCounts(result);
  const zeroShadow = result.shadow_observations.filter((item) => item.observation_count === 0);
  return (
    <section className="strategy-tracking-diagnostics">
      {viewMode === "professional" && zeroShadow.length ? (
        <Alert
          type="warning"
          showIcon
          title="影子观察样本为 0"
          description={zeroShadow.map((item) => `${item.model_key}: ${item.no_sample_reason_text || item.no_sample_reason}`).join("；")}
        />
      ) : null}
      <div className="strategy-tracking-tag-row">
        <Tag color={result.summary.needs_review_count ? "orange" : "green"}>需复核 {result.summary.needs_review_count}</Tag>
        <Tag color={result.summary.abnormal_return_count ? "red" : "green"}>异常收益 {result.summary.abnormal_return_count}</Tag>
        {failureTags.map(([tag, count]) => <Tag key={tag}>{failureTagText(tag)} {count}</Tag>)}
      </div>
      {viewMode === "professional" && weeklyReport?.data?.markdown ? (
        <Alert type="info" showIcon title="策略跟踪周报" description={weeklyReport.data.markdown} />
      ) : null}
      <VirtualGrid<StrategyTrackingSegment>
        rowKey={(item) => `${item.strategy_key}:${item.market_state}:${item.sector_state}`}
        dataSource={result.market_segments}
        columns={segmentColumns}
        paginated
        pagination={{ pageSize: 8 }}
        scroll={{ x: 820 }}
        defaultScrollY={360}
      />
    </section>
  );
}

function failureTagCounts(result: StrategyTrackingListResponse): Array<[string, number]> {
  const counts = new Map<string, number>();
  for (const item of result.items) {
    for (const tag of item.failure_tags) {
      counts.set(tag, (counts.get(tag) || 0) + 1);
    }
  }
  return Array.from(counts.entries()).sort((left, right) => right[1] - left[1]).slice(0, 6);
}

function failureTagText(tag: string): string {
  const labels: Record<string, string> = {
    no_entry_touch: "未触达",
    fast_support_break: "破支撑",
    spike_without_take_profit: "冲高回落",
    sector_retreat: "板块退潮",
    market_mismatch: "环境不配",
    data_insufficient: "数据不足",
    abnormal_return: "异常收益",
    stop_loss_triggered: "止损",
  };
  return labels[tag] || tag;
}

const segmentColumns: ColumnsType<StrategyTrackingSegment> = [
  {
    title: "策略",
    width: 160,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <strong>{item.strategy_name || item.strategy_key}</strong>
        <span>{item.strategy_key}</span>
      </div>
    ),
  },
  {
    title: "市场/板块",
    width: 180,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <span>{item.market_state_text}</span>
        <span>{item.sector_state_text}</span>
      </div>
    ),
  },
  { title: "样本", dataIndex: "recommendation_count", width: 70 },
  { title: "买点", dataIndex: "entry_touch_rate", width: 80, render: (value) => formatPct(value) },
  { title: "5日胜率", dataIndex: "win_rate_5d", width: 90, render: (value) => formatPct(value) },
  { title: "均高", dataIndex: "avg_max_gain_pct", width: 80, render: (value) => formatPct(value) },
  { title: "均撤", dataIndex: "avg_max_drawdown_pct", width: 80, render: (value) => formatPct(value) },
  { title: "止损", dataIndex: "stop_loss_rate", width: 80, render: (value) => formatPct(value) },
];

export function shadowReasonText(items: StrategyTrackingShadowObservation[]): string {
  return items.map((item) => item.no_sample_reason_text || item.no_sample_reason).filter(Boolean).join("；");
}
