import { Button, Tag, Typography } from "antd";
import { useMemo } from "react";
import { DataTable, PercentCell } from "../../ui/table/DataTable";
import { TqEmpty } from "../../ui/feedback/StateViews";
import type { RelativeStrengthItem, RelativeStrengthResponse } from "../../types";
import { filterMainBoardItems, nextBoardFilter, type BoardFilter } from "./boardFilters";

export function RelativeStrengthBoard({
  data,
  loading,
  boardFilter = "include_all",
  onBoardFilterChange,
}: {
  data?: RelativeStrengthResponse;
  loading: boolean;
  boardFilter?: BoardFilter;
  onBoardFilterChange?: (boardFilter: BoardFilter) => void;
}) {
  const items = useMemo(() => filterMainBoardItems(data?.items ?? [], boardFilter), [data?.items, boardFilter]);
  if (data && !data.enabled) {
    return <TqEmpty title="抗跌榜未开启" description="当前功能开关关闭，监控和策略跟踪保持既有展示。" />;
  }
  return (
    <div className="strategy-tracking-analysis-stack">
      <div className="strategy-tracking-tab-toolbar">
        <Typography.Text type="secondary">相对强度只展示信号日事实，不预测后续涨跌。</Typography.Text>
        <Button
          size="small"
          type={boardFilter === "main_only" ? "primary" : "default"}
          onClick={() => onBoardFilterChange?.(nextBoardFilter(boardFilter))}
        >
          只看主板
        </Button>
      </div>
      <DataTable<RelativeStrengthItem>
        rowKey={(item) => `${item.trade_date}-${item.symbol}`}
        loading={loading}
        dataSource={items}
        defaultScrollY={320}
        columns={[
          { title: "代码", dataIndex: "symbol", width: 96 },
          { title: "日期", dataIndex: "trade_date", width: 120 },
          { title: "个股", dataIndex: "stock_pct", width: 100, render: (value) => <PercentCell value={value as number} /> },
          { title: "市场", dataIndex: "index_pct", width: 100, render: (value) => <PercentCell value={value as number} /> },
          { title: "板块", dataIndex: "sector_pct", width: 100, render: (value) => <PercentCell value={value as number} /> },
          { title: "相对市场", dataIndex: "rs_vs_index", width: 110, render: (value) => <PercentCell value={value as number} /> },
          { title: "事实标签", dataIndex: "resilience_flag", width: 120, render: flagTag },
          { title: "数据", dataIndex: "data_quality", width: 110 },
        ]}
      />
    </div>
  );
}

function flagTag(value: unknown) {
  if (value === "resilient") return <Tag color="green">抗跌</Tag>;
  if (value === "follow_down") return <Tag color="orange">跟随下行</Tag>;
  return <Tag>中性</Tag>;
}
