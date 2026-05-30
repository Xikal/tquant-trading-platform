import { Segmented } from "antd";
import type { DisplayLane } from "../../types";

interface StrategyLaneTabsProps {
  value: DisplayLane;
  onChange: (value: DisplayLane) => void;
}

const OPTIONS = [
  { label: "原低吸策略", value: "baseline" },
  { label: "前排加权", value: "front_row_weighted" },
  { label: "前排极精选", value: "front_row_only" },
] as const;

export function StrategyLaneTabs({ value, onChange }: StrategyLaneTabsProps) {
  return (
    <Segmented
      size="small"
      value={value}
      options={[...OPTIONS]}
      onChange={(next) => onChange(next as DisplayLane)}
    />
  );
}
