import { Space, Tag, Typography } from "antd";
import type { LowBuyPriorityBoardResult } from "../../types";

export function RiskFilterBadges({ board }: { board: LowBuyPriorityBoardResult | null }) {
  const blocked = board?.items.filter((item) => item.risk_tier === "block").length ?? 0;
  const degraded = board?.items.filter((item) => item.risk_tier === "degrade").length ?? 0;
  const dataQuality = board?.data_quality_text || "数据状态未知";

  return (
    <Space wrap size={6}>
      <Tag color={blocked ? "error" : "success"}>硬阻断 {blocked}</Tag>
      <Tag color={degraded ? "warning" : "default"}>降权 {degraded}</Tag>
      <Tag>{dataQuality}</Tag>
      <Typography.Text type="secondary">避坑过滤只做阻断/降权标记，不改写策略规则。</Typography.Text>
    </Space>
  );
}
