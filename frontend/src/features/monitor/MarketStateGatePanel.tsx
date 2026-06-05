import { Alert, Collapse, Progress, Space, Tag, Typography } from "antd";
import type { LowBuyPriorityBoardResult } from "../../types";

const GATE_LABELS: Record<string, string> = {
  allow: "正常火力",
  reduce: "降权运行",
  block: "生产阻断",
  research_only: "仅研究",
  no_data: "数据缺失",
};

const GATE_STATUS: Record<string, "success" | "warning" | "error" | "default"> = {
  allow: "success",
  reduce: "warning",
  block: "error",
  research_only: "default",
  no_data: "default",
};

export function MarketStateGatePanel({
  board,
  defaultOpen = false,
}: {
  board: LowBuyPriorityBoardResult | null;
  defaultOpen?: boolean;
}) {
  const decision = board?.market_gate_decision ?? "allow";
  const score = board?.market_gate_score ?? 100;
  const multiplier = board?.market_firepower_multiplier ?? 1;
  const reasons = board?.market_gate_reasons ?? [];

  return (
    <Collapse
      size="small"
      defaultActiveKey={defaultOpen ? ["market-state-gate"] : []}
      items={[
        {
          key: "market-state-gate",
          label: "市场状态总闸",
          children: (
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              <Space wrap>
                <Tag color={GATE_STATUS[decision] ?? "default"}>{GATE_LABELS[decision] ?? decision}</Tag>
                <Tag>火力 {Math.round(multiplier * 100)}%</Tag>
                <Typography.Text type="secondary">市场：{board?.market_state_text || "--"}</Typography.Text>
              </Space>
              <Progress percent={Math.round(score)} size="small" status={decision === "block" ? "exception" : decision === "allow" ? "success" : "normal"} />
              {reasons.length ? (
                <Alert type={decision === "block" ? "error" : "warning"} showIcon message={reasons.join("；")} />
              ) : (
                <Typography.Text type="secondary">市场门控未命中额外阻断。</Typography.Text>
              )}
            </Space>
          ),
        },
      ]}
    />
  );
}
