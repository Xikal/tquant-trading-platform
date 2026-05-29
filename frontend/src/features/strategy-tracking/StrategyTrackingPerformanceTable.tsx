import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { StrategyTrackingPerformance } from "../../types";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function StrategyTrackingPerformanceTable({ items }: { items: StrategyTrackingPerformance[] }) {
  return (
    <Table
      rowKey="strategy_key"
      size="small"
      dataSource={items}
      columns={columns}
      pagination={false}
      scroll={{ x: 960 }}
    />
  );
}

const columns: ColumnsType<StrategyTrackingPerformance> = [
  { title: "策略", dataIndex: "strategy_name", width: 150 },
  { title: "推荐次数", dataIndex: "recommendation_count", width: 90 },
  { title: "买点次数", dataIndex: "entry_touched_count", width: 90 },
  { title: "买点触达率", dataIndex: "entry_touch_rate", width: 100, render: (value) => formatPct(value) },
  { title: "3 日胜率", dataIndex: "win_rate_3d", width: 100, render: (value) => formatPct(value) },
  { title: "5 日胜率", dataIndex: "win_rate_5d", width: 100, render: (value) => formatPct(value) },
  { title: "10 日胜率", dataIndex: "win_rate_10d", width: 100, render: (value) => formatPct(value) },
  { title: "平均收益", dataIndex: "avg_current_return_pct", width: 100, render: (value) => formatPct(value) },
  { title: "平均最高涨幅", dataIndex: "avg_max_gain_pct", width: 120, render: (value) => formatPct(value) },
  { title: "平均最大回撤", dataIndex: "avg_max_drawdown_pct", width: 120, render: (value) => formatPct(value) },
  { title: "盈亏比", dataIndex: "profit_loss_ratio", width: 90 },
  { title: "止损率", dataIndex: "stop_loss_rate", width: 90, render: (value) => formatPct(value) },
  { title: "当前有效", dataIndex: "active_count", width: 90 },
];
