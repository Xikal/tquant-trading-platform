import { Segmented, Space, Tag } from "antd";
import type { StrategyTrackingViewMode } from "../../stores/strategyTrackingStore";

interface StrategyTrackingModeToggleProps {
  viewMode: StrategyTrackingViewMode;
  onChange: (value: StrategyTrackingViewMode) => void;
}

export function StrategyTrackingModeToggle({ viewMode, onChange }: StrategyTrackingModeToggleProps) {
  return (
    <Space wrap size={8} className="strategy-tracking-mode-toggle">
      <Segmented
        size="small"
        value={viewMode}
        onChange={(value) => onChange(value as StrategyTrackingViewMode)}
        options={[
          { label: "小白模式", value: "beginner" },
          { label: "专业模式", value: "professional" },
        ]}
      />
      <Tag color={viewMode === "beginner" ? "green" : "blue"}>
        {viewMode === "beginner" ? "默认隐藏专业审计" : "显示完整审计信息"}
      </Tag>
    </Space>
  );
}
