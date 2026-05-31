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
      size="small"
      title="当前持仓"
      extra={<Typography.Text type="secondary">{positions.length ? `共 ${positions.length} 只，首屏直接处理` : "暂无持仓"}</Typography.Text>}
      variant="borderless"
      styles={{ body: { padding: 6, minHeight: 0, fontSize: 12 } }}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : positions.length ? (
        <List
          split={false}
          style={{
            maxHeight: positions.length > 6 ? 300 : undefined,
            overflowY: positions.length > 6 ? "auto" : "visible",
            paddingRight: positions.length > 6 ? 4 : 0,
          }}
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
  const model = item.exit_model_shadow;
  const modelText = model?.fallback_reason
    ? `模型旁路：${model.fallback_reason}`
    : model?.action && model.action !== "hold"
      ? `模型旁路：${model.action} · ${(Number(model.confidence || 0) * 100).toFixed(0)}%`
      : "模型旁路：只观察";
  const mainForce = item.main_force_paper_advice;
  const mainForceText = mainForce?.visible
    ? `主力：${[mainForce.stage_text, mainForce.model_action_text, mainForce.action_text].filter(Boolean).join(" · ")}`
    : "主力：旁路观察";
  return (
    <List.Item
      style={{
        border: "1px solid rgba(100, 116, 139, 0.18)",
        borderRadius: 8,
        boxShadow: `inset 3px 0 0 ${toneColor(tone)}`,
        marginBottom: 5,
        padding: "5px 6px",
      }}
    >
      <List.Item.Meta
        title={<Typography.Text strong style={{ fontSize: 12 }}>{item.name || item.symbol}</Typography.Text>}
        description={<Typography.Text type="secondary" style={{ fontSize: 12 }}>{item.symbol}</Typography.Text>}
      />
      <Space size={6} wrap style={{ fontSize: 12 }}>
        <Typography.Text style={{ fontSize: 12 }}>持仓 {formatInteger(item.quantity)} / 可卖 {formatInteger(item.available_quantity)}</Typography.Text>
        <Typography.Text style={{ fontSize: 12 }}>成本 {formatPrice(item.cost_basis)} / 现价 {formatPrice(item.latest_price)}</Typography.Text>
        <Tag color="blue">{actionText}</Tag>
        <Tag color={model?.safety_blocked ? "red" : model?.fallback_reason ? "default" : "purple"}>{modelText}</Tag>
        <Tag color={mainForce?.suggestion_enabled ? "gold" : mainForce?.risk_flags?.length ? "default" : "cyan"}>
          {mainForceText}
        </Tag>
        <Typography.Text strong style={{ color: toneColor(tone), fontSize: 12 }}>{formatPct(item.unrealized_pnl_pct)}</Typography.Text>
      </Space>
    </List.Item>
  );
}

function toneColor(tone: string): string {
  if (tone === "up") return "#c62828";
  if (tone === "down") return "#1f8b4c";
  return "#162235";
}
