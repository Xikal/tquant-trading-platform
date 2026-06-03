import { Tag, Tooltip } from "antd";
import type { VolumePositionTag } from "../../types";

export function VolumePositionTagStrip({ items }: { items: VolumePositionTag[] }) {
  if (!items.length) return null;
  return (
    <div className="volume-position-tag-strip">
      {items.map((item) => (
        <Tooltip key={`${item.symbol}-${item.tag_code}`} title={item.evidence.join("；") || item.explanation}>
          <Tag color={item.level === "warn" ? "orange" : "blue"}>{tagText(item.tag_code)} · {item.data_quality}</Tag>
        </Tooltip>
      ))}
    </div>
  );
}

function tagText(code: string) {
  const labels: Record<string, string> = {
    high_vol_distribution_risk: "高量分歧",
    low_vol_grind_down_risk: "缩量走弱",
    healthy_pullback_observe: "回落观察",
    up_shrink_down_expand_risk: "放量回落",
    blowoff_overheat_risk: "过热警惕",
    price_volume_divergence_risk: "价量背离",
    neutral_observe: "中性观察",
    insufficient_history: "历史不足",
    insufficient_key_level: "关键位不足",
  };
  return labels[code] || code;
}
