import { Button, Tag } from "antd";
import { DataTable, PercentCell } from "../../ui/table/DataTable";
import type { ReviewWorkspaceItem } from "../../types";

export function ReviewWorkspaceQueue({
  items,
  loading,
  selectedKey,
  onSelect,
}: {
  items: ReviewWorkspaceItem[];
  loading: boolean;
  selectedKey: string | null;
  onSelect: (item: ReviewWorkspaceItem) => void;
}) {
  return (
    <div className="strategy-review-queue">
      <DataTable<ReviewWorkspaceItem>
        rowKey={(item) => item.review_key}
        loading={loading}
        dataSource={items}
        defaultScrollY={320}
        columns={[
          {
            title: "股票",
            dataIndex: ["pool_item", "symbol"],
            width: 160,
            render: (_, item) => `${item.pool_item.name || "--"} ${item.pool_item.symbol}`,
          },
          { title: "复盘状态", dataIndex: "review_status", width: 110, render: statusTag },
          {
            title: "信号日涨幅",
            dataIndex: ["pool_item", "entry_pct"],
            width: 110,
            render: (_, item) => <PercentCell value={item.pool_item.entry_pct} />,
          },
          {
            title: "跟踪日",
            dataIndex: ["pool_item", "tracked_days"],
            width: 90,
            render: (_, item) => item.pool_item.tracked_days,
          },
          {
            title: "动作",
            dataIndex: "next_action_label",
            width: 120,
            render: (_, item) => (
              <Button size="small" type={selectedKey === item.review_key ? "primary" : "default"} onClick={() => onSelect(item)}>
                {item.next_action_label}
              </Button>
            ),
          },
        ]}
      />
    </div>
  );
}

function statusTag(value: unknown) {
  if (value === "journaled") return <Tag color="green">已记录</Tag>;
  if (value === "retained") return <Tag color="blue">已留存</Tag>;
  if (value === "dropped") return <Tag color="orange">已剔除</Tag>;
  if (value === "data_issue") return <Tag color="red">数据不足</Tag>;
  return <Tag>待复盘</Tag>;
}
