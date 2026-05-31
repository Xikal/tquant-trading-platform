import { Progress, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { StrategyTrackingHoldingAnalysis } from "../../types";
import { TqEmpty } from "../../ui/feedback/StateViews";
import { DataTable } from "../../ui/table/DataTable";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function StrategyTrackingHoldingAnalysisPanel({ items, loading }: { items: StrategyTrackingHoldingAnalysis[]; loading: boolean }) {
  if (!items.length && !loading) {
    return <TqEmpty title="暂无持有分析" description="当前筛选条件下还没有足够样本生成策略持有结论。" />;
  }
  return (
    <DataTable<StrategyTrackingHoldingAnalysis>
      rowKey="strategy_key"
      loading={loading}
      dataSource={items}
      columns={columns}
      paginated
      pagination={{ pageSize: 10 }}
      scroll={{ x: 900 }}
      defaultScrollY={420}
    />
  );
}

const columns: ColumnsType<StrategyTrackingHoldingAnalysis> = [
  {
    title: "策略 / 结论",
    width: 260,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <strong>{item.strategy_name || item.strategy_key}</strong>
        <span>{item.conclusion || "样本不足，暂不能判断。"}</span>
      </div>
    ),
  },
  {
    title: "信号次数",
    dataIndex: "sample_count",
    width: 90,
  },
  {
    title: "最适合持有",
    width: 150,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <Tag color={item.dominant_holding_bucket === "unavailable" ? "default" : "blue"}>{item.dominant_holding_bucket_text}</Tag>
        <span>平均最优 {item.avg_best_holding_days || "--"} 天</span>
      </div>
    ),
  },
  {
    title: "持有分布",
    width: 220,
    render: (_, item) => (
      <div className="strategy-tracking-holding-bars">
        <MiniBar label="短线" value={item.short_hold_ratio} />
        <MiniBar label="波段" value={item.swing_hold_ratio} />
        <MiniBar label="趋势" value={item.trend_hold_ratio} />
        <MiniBar label="中长" value={item.midlong_hold_ratio} />
      </div>
    ),
  },
  {
    title: "收益 / 回撤",
    width: 170,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <span>平均最优收益 {formatPct(item.avg_best_exit_return_pct)}</span>
        <span>平均承受回撤 {formatPct(item.avg_best_exit_drawdown_pct)}</span>
        <span>利润回吐 {formatPct(item.avg_giveback_from_peak_pct)}</span>
      </div>
    ),
  },
  {
    title: "延长持有",
    width: 130,
    render: (_, item) => <Tag color={item.extension_qualified_ratio >= 40 ? "green" : "default"}>{formatPct(item.extension_qualified_ratio)} 样本可延长</Tag>,
  },
];

function MiniBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span>{label} {Math.round(value)}%</span>
      <Progress percent={Math.round(value)} showInfo={false} size="small" />
    </div>
  );
}
