import { Button, Table, Tag } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import type { StrategyTrackingItem } from "../../types";
import { formatPct, formatPrice } from "../workspace-shared/workspaceFormatters";
import { displayReturn, entryZoneText, trackingTone } from "./strategyTrackingFormatters";

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
      scroll={{ x: 1160 }}
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
      width: 130,
      render: (_, item) => (
        <Button type="link" size="small" onClick={() => onOpenDetail(item.id)}>
          {item.name || item.symbol} <small>{item.symbol}</small>
        </Button>
      ),
    },
    { title: "策略", dataIndex: "strategy_name", width: 130 },
    {
      title: "信号",
      dataIndex: "signal_text",
      width: 100,
      render: (_, item) => <Tag color={item.observe_only ? "default" : "blue"}>{item.signal_text}</Tag>,
    },
    { title: "状态", dataIndex: "lifecycle_status_text", width: 110 },
    { title: "首次推荐", dataIndex: "first_signal_date", width: 110 },
    { title: "推荐价", dataIndex: "first_signal_price", width: 90, render: formatPrice },
    { title: "当前价", dataIndex: "current_price", width: 90, render: formatPrice },
    { title: "买点区间", width: 130, render: (_, item) => entryZoneText(item) },
    { title: "距买点", dataIndex: "distance_to_entry_pct", width: 90, render: (value) => formatPct(value) },
    {
      title: "当前涨幅",
      dataIndex: "current_return_pct",
      width: 100,
      render: (value) => <Tag color={trackingTone(value)}>{displayReturn(value)}</Tag>,
    },
    {
      title: "最高涨幅",
      dataIndex: "max_gain_pct",
      width: 100,
      render: (value) => <Tag color={trackingTone(value)}>{displayReturn(value)}</Tag>,
    },
    { title: "最大回撤", dataIndex: "max_drawdown_pct", width: 100, render: (value) => formatPct(value) },
    {
      title: "触发",
      width: 130,
      render: (_, item) => (
        <>
          {item.entry_touched ? <Tag color="green">买点触达</Tag> : <Tag>未给买点</Tag>}
          {item.stop_triggered ? <Tag color="red">止损</Tag> : null}
        </>
      ),
    },
    { title: "结论", dataIndex: "conclusion", width: 160 },
    { title: "数据", dataIndex: "data_quality_text", width: 160 },
  ];
}
