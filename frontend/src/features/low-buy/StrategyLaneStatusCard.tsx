import { Alert, Tag } from "antd";
import type { LowBuyPriorityBoardResult, StrategyVariant } from "../../types";

interface StrategyLaneStatusCardProps {
  board: LowBuyPriorityBoardResult | null;
  activeLane: StrategyVariant;
}

export function StrategyLaneStatusCard({ board, activeLane }: StrategyLaneStatusCardProps) {
  const content = resolveLaneStatus(board, activeLane);
  return (
    <Alert
      type={content.type}
      showIcon
      message={(
        <span>
          {content.title} <Tag>{content.tag}</Tag>
        </span>
      )}
      description={`${content.reason}。${content.nextStep}。`}
    />
  );
}

function resolveLaneStatus(board: LowBuyPriorityBoardResult | null, activeLane: StrategyVariant) {
  const plain = board?.readiness_summary?.plain_status;
  if (activeLane === "front_row_weighted") {
    return {
      type: "warning" as const,
      title: plain?.conclusion || "只做验证，暂不影响真实排序",
      reason: plain?.reason || "样本外验证不足、滚动验证不稳定、成交数据不足",
      nextStep: plain?.next_step || "继续影子验证和模拟盘观察",
      tag: "影子跟踪 / 模拟盘",
    };
  }
  if (activeLane === "front_row_only") {
    return {
      type: "info" as const,
      title: plain?.conclusion || "只做提醒，不参与生产排序",
      reason: plain?.reason || "信号很少，可能连续多天没有票",
      nextStep: plain?.next_step || "继续作为强前排观察提醒，不是买入建议",
      tag: "仅观察",
    };
  }
  return {
    type: "success" as const,
    title: plain?.conclusion || "保持旧策略排序",
    reason: plain?.reason || "原低吸策略是大分组，里面仍保留各自具体策略名称",
    nextStep: plain?.next_step || "继续作为当前生产观察基准",
    tag: "旧排序",
  };
}
