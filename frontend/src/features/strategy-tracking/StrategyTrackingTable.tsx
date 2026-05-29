import { Button, Table, Tag } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import type { StrategyTrackingItem } from "../../types";
import { formatPct, formatPrice } from "../workspace-shared/workspaceFormatters";
import {
  displayReturn,
  entryZoneText,
  exitQualityTone,
  holdingBucketText,
  holdExtensionTone,
  suggestedPlanText,
  trackingTone,
} from "./strategyTrackingFormatters";

interface StrategyTrackingTableProps {
  items: StrategyTrackingItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  onPageChange: (page: number, pageSize: number) => void;
  onOpenDetail: (itemId: string) => void;
}

export function StrategyTrackingTable({
  items,
  total,
  page,
  pageSize,
  loading,
  onPageChange,
  onOpenDetail,
}: StrategyTrackingTableProps) {
  return (
    <Table
      rowKey="id"
      size="small"
      loading={loading}
      dataSource={items}
      columns={columns(onOpenDetail)}
      scroll={{ x: 1360 }}
      pagination={{
        current: page,
        pageSize,
        total,
        showSizeChanger: true,
        pageSizeOptions: [20, 30, 50],
      }}
      onChange={(pagination: TablePaginationConfig) => onPageChange(pagination.current || 1, pagination.pageSize || 30)}
    />
  );
}

function columns(onOpenDetail: (itemId: string) => void): ColumnsType<StrategyTrackingItem> {
  return [
    {
      title: "股票",
      dataIndex: "symbol",
      fixed: "left",
      width: 150,
      render: (_, item) => (
        <Button className="strategy-tracking-stock-link" type="link" size="small" onClick={() => onOpenDetail(item.id)}>
          <span>{item.name || item.symbol}</span>
          <small>{item.symbol}</small>
        </Button>
      ),
    },
    {
      title: "策略/状态",
      width: 170,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <strong>{item.strategy_name}</strong>
          <span>{item.lifecycle_status_text}</span>
        </div>
      ),
    },
    {
      title: "信号",
      width: 110,
      render: (_, item) => <Tag color={item.observe_only ? "default" : "blue"}>{item.signal_text}</Tag>,
    },
    {
      title: "价格",
      width: 170,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <span>现价 {formatPrice(item.current_price)}</span>
          <span>推荐 {formatPrice(item.first_signal_price)} · {item.first_signal_date}</span>
        </div>
      ),
    },
    {
      title: "买点/止损",
      width: 180,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <span>{entryZoneText(item)}</span>
          <span>距买点 {formatPct(item.distance_to_entry_pct)} · 止损 {formatPrice(item.stop_loss)}</span>
        </div>
      ),
    },
    {
      title: "表现",
      width: 180,
      render: (_, item) => (
        <div className="strategy-tracking-tag-row">
          <Tag color={trackingTone(item.current_return_pct)}>现 {displayReturn(item.current_return_pct)}</Tag>
          <Tag color={trackingTone(item.max_gain_pct)}>高 {displayReturn(item.max_gain_pct)}</Tag>
          <Tag>撤 {formatPct(item.max_drawdown_pct)}</Tag>
        </div>
      ),
    },
    {
      title: "持有优化",
      width: 190,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <span>{item.best_holding_days ? `最优 ${item.best_holding_days}天` : "暂无持有窗口"}</span>
          <div className="strategy-tracking-tag-row">
            <Tag color={exitQualityTone(item.exit_quality)}>{displayReturn(item.best_exit_return_pct)}</Tag>
            <Tag>{holdingBucketText(item.holding_bucket)}</Tag>
          </div>
        </div>
      ),
    },
    {
      title: "延长持有",
      width: 180,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <Tag color={holdExtensionTone(item.hold_extension_state)}>{item.hold_extension_text}</Tag>
          <span>{suggestedPlanText(item.suggested_holding_plan)} · {item.hold_extension_score}分</span>
        </div>
      ),
    },
    {
      title: "触发",
      width: 120,
      render: (_, item) => (
        <div className="strategy-tracking-tag-row">
          {item.entry_touched ? <Tag color="green">买点触达</Tag> : <Tag>未触达</Tag>}
          {item.stop_triggered ? <Tag color="red">止损</Tag> : null}
        </div>
      ),
    },
    {
      title: "归因/审计",
      width: 220,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <strong>{item.conclusion}</strong>
          <span>{item.failure_reason_text || item.data_quality_text}</span>
          {item.needs_review ? <Tag color="orange">需复核</Tag> : null}
        </div>
      ),
    },
  ];
}
