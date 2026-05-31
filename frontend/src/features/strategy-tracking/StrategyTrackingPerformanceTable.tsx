import type { ColumnsType } from "antd/es/table";
import type { StrategyTrackingPerformance } from "../../types";
import { DataTable } from "../../ui/table/DataTable";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function StrategyTrackingPerformanceTable({ items }: { items: StrategyTrackingPerformance[] }) {
  return (
    <DataTable<StrategyTrackingPerformance>
      rowKey="strategy_key"
      dataSource={items}
      columns={columns}
      scroll={{ x: 820 }}
      defaultScrollY={360}
    />
  );
}

const columns: ColumnsType<StrategyTrackingPerformance> = [
  {
    title: "策略",
    width: 170,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <strong>{item.strategy_name}</strong>
        <span>当前有效 {item.active_count}</span>
      </div>
    ),
  },
  {
    title: "信号/买点",
    width: 150,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <span>信号次数 {item.recommendation_count} · 买点 {item.entry_touched_count}</span>
        <span>买点触达率 {formatPct(item.entry_touch_rate)}</span>
      </div>
    ),
  },
  {
    title: "胜率",
    width: 150,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <span>3日 {formatPct(item.win_rate_3d)} · 5日 {formatPct(item.win_rate_5d)}</span>
        <span>10日 {formatPct(item.win_rate_10d)}</span>
      </div>
    ),
  },
  {
    title: "收益/回撤",
    width: 170,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <span>均值 {formatPct(item.avg_current_return_pct)} · 高点 {formatPct(item.avg_max_gain_pct)}</span>
        <span>回撤 {formatPct(item.avg_max_drawdown_pct)}</span>
      </div>
    ),
  },
  { title: "盈亏比", dataIndex: "profit_loss_ratio", width: 90 },
  { title: "止损率", dataIndex: "stop_loss_rate", width: 90, render: (value) => formatPct(value) },
];
