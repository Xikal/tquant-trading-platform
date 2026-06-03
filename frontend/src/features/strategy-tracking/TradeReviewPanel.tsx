import { Button, Tag, Typography } from "antd";
import { DataTable, PercentCell } from "../../ui/table/DataTable";
import { TqEmpty } from "../../ui/feedback/StateViews";
import type { ReviewPoolItem, ReviewPoolResponse } from "../../types";
import { nextBoardFilter, type BoardFilter } from "./boardFilters";

export function TradeReviewPanel({
  data,
  loading,
  boardFilter = "include_all",
  onBoardFilterChange,
}: {
  data?: ReviewPoolResponse;
  loading: boolean;
  boardFilter?: BoardFilter;
  onBoardFilterChange?: (boardFilter: BoardFilter) => void;
}) {
  if (data && !data.enabled) {
    return <TqEmpty title="复盘入口未开启" description="当前功能开关关闭，策略跟踪保持既有展示。" />;
  }
  return (
    <div className="strategy-tracking-analysis-stack">
      <div className="strategy-tracking-tab-toolbar">
        <Typography.Text type="secondary">观察池只用于收盘复盘、次日剔除和三日留存，不进入生产排序。</Typography.Text>
        <Button
          size="small"
          type={boardFilter === "main_only" ? "primary" : "default"}
          onClick={() => onBoardFilterChange?.(nextBoardFilter(boardFilter))}
        >
          只看主板
        </Button>
      </div>
      <DataTable<ReviewPoolItem>
        rowKey={(item) => `${item.pool_date}-${item.symbol}`}
        loading={loading}
        dataSource={data?.items ?? []}
        defaultScrollY={320}
        columns={[
          { title: "代码", dataIndex: "symbol", width: 96 },
          { title: "名称", dataIndex: "name", width: 120 },
          { title: "市场板", dataIndex: "board_name", width: 90 },
          { title: "状态", dataIndex: "status", width: 110, render: statusTag },
          { title: "信号日涨幅", dataIndex: "entry_pct", width: 120, render: (value) => <PercentCell value={value as number} /> },
          { title: "量比", dataIndex: "volume_ratio", width: 100, render: (value) => Number(value || 0).toFixed(2) },
          { title: "跟踪日", dataIndex: "tracked_days", width: 90 },
          { title: "剔除原因", dataIndex: "drop_reason", ellipsis: true },
          { title: "数据", dataIndex: "data_quality", width: 110 },
        ]}
      />
    </div>
  );
}

function statusTag(status: unknown) {
  const value = String(status);
  if (value === "retained") return <Tag color="green">留存</Tag>;
  if (value === "dropped") return <Tag color="orange">剔除</Tag>;
  return <Tag>观察池</Tag>;
}
