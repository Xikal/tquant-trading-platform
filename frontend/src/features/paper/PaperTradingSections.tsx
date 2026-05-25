import type {
  PaperPosition,
} from "../../types";
import { Card, List, Skeleton, Space, Tag, Typography } from "antd";
import { OrderEntryModal } from "./PaperOrderEntryModal";
import { EmptyState } from "../workspace-shared/WorkspaceComponents";
import { formatInteger, formatPct, formatPrice, toneFromChange } from "../workspace-shared/workspaceFormatters";
export { formatPaperDateTime } from "./paperTradingFormatters";

export { OrderEntryModal };

export function PaperPositionsPanel({
  positions,
  loading,
}: {
  positions: PaperPosition[];
  loading: boolean;
}) {
  return (
    <Card
      title="当前持仓"
      extra={<Typography.Text type="secondary">{positions.length ? `共 ${positions.length} 只，首屏直接处理` : "暂无持仓"}</Typography.Text>}
      variant="borderless"
      styles={{ body: { padding: 12 } }}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : positions.length ? (
        <List
          split={false}
          style={{ maxHeight: 420, overflowY: "auto", paddingRight: 4 }}
          dataSource={positions}
          renderItem={(item) => <PositionRow item={item} />}
        />
      ) : (
        <EmptyState text="暂无模拟持仓" />
      )}
    </Card>
  );
}
function PositionRow({ item }: { item: PaperPosition }) {
  const tone = item.latest_price == null ? "neutral" : toneFromChange(item.unrealized_pnl_pct);
  const actionText = item.smart_exit_text || item.smart_exit_action || "按计划持有";
  return (
    <List.Item
      style={{
        border: "1px solid rgba(100, 116, 139, 0.18)",
        borderRadius: 9,
        boxShadow: `inset 3px 0 0 ${toneColor(tone)}`,
        marginBottom: 8,
        padding: "8px 10px",
      }}
    >
      <List.Item.Meta
        title={<Typography.Text strong>{item.name || item.symbol}</Typography.Text>}
        description={item.symbol}
      />
      <Space size={12} wrap>
        <Typography.Text>持仓 {formatInteger(item.quantity)} / 可卖 {formatInteger(item.available_quantity)}</Typography.Text>
        <Typography.Text>成本 {formatPrice(item.cost_basis)} / 现价 {formatPrice(item.latest_price)}</Typography.Text>
        <Tag color="blue">{actionText}</Tag>
        <Typography.Text strong style={{ color: toneColor(tone) }}>{formatPct(item.unrealized_pnl_pct)}</Typography.Text>
      </Space>
    </List.Item>
  );
}

function toneColor(tone: string): string {
  if (tone === "up") return "#c62828";
  if (tone === "down") return "#1f8b4c";
  return "#162235";
}
