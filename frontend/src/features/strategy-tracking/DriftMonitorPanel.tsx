import { Alert, Collapse, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { TrackRecordDriftItem } from "../../types";
import { TqEmpty } from "../../ui/feedback/StateViews";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { PercentCell } from "../../ui/grid/VirtualGrid";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function DriftMonitorPanel({
  items,
  loading,
  total = 0,
  defaultOpen = false,
}: {
  items: TrackRecordDriftItem[];
  loading: boolean;
  total?: number;
  defaultOpen?: boolean;
}) {
  const advisoryCount = items.filter((item) => item.drift_flag === "decay_advisory").length;
  return (
    <Collapse
      size="small"
      defaultActiveKey={defaultOpen ? ["track-record-drift"] : []}
      items={[{
        key: "track-record-drift",
        label: `真实战绩漂移 · ${total || items.length}`,
        children: (
          <section className="strategy-tracking-drift-panel">
            {advisoryCount ? (
              <Alert type="warning" showIcon message={`漂移 advisory ${advisoryCount} 条`} />
            ) : null}
            {items.length ? (
              <VirtualGrid<TrackRecordDriftItem>
                rowKey={(item) => `${item.strategy_key}:${item.as_of_date}:${item.window_days}`}
                loading={loading}
                dataSource={items}
                columns={driftColumns}
                paginated
                pagination={{ pageSize: 8 }}
                scroll={{ x: 1080 }}
                defaultScrollY={360}
              />
            ) : (
              <TqEmpty title={loading ? "真实战绩加载中" : "暂无真实战绩漂移样本"} description="尚未生成 strategy_drift_snapshots。" />
            )}
          </section>
        ),
      }]}
    />
  );
}

const driftColumns: ColumnsType<TrackRecordDriftItem> = [
  {
    title: "策略",
    width: 160,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <strong>{item.strategy_key}</strong>
        <span>{item.as_of_date} / {item.window_days}日</span>
      </div>
    ),
  },
  { title: "样本", dataIndex: "sample_settled", width: 70 },
  {
    title: "利润因子",
    width: 120,
    render: (_, item) => (
      <Typography.Text>{numText(item.realized_pf)} / {numText(item.expected_pf)}</Typography.Text>
    ),
  },
  {
    title: "平均单笔",
    width: 130,
    render: (_, item) => <span>{formatPct(item.realized_avg)} / {formatPct(item.expected_avg)}</span>,
  },
  {
    title: "max5",
    width: 120,
    render: (_, item) => <span>{formatPct(item.realized_max5)} / {formatPct(item.backtest_max5)}</span>,
  },
  {
    title: "max10",
    width: 120,
    render: (_, item) => <span>{formatPct(item.realized_max10)} / {formatPct(item.backtest_max10)}</span>,
  },
  { title: "误差", dataIndex: "tracking_error", width: 90, render: (value) => <PercentCell value={Number(value || 0)} /> },
  { title: "衰减", dataIndex: "decay_pct", width: 90, render: (value) => <PercentCell value={Number(value || 0)} /> },
  {
    title: "标记",
    dataIndex: "drift_flag",
    width: 130,
    render: (value) => <Tag color={value === "decay_advisory" ? "orange" : value === "ok" ? "green" : "default"}>{String(value || "--")}</Tag>,
  },
];

function numText(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toFixed(2);
}
