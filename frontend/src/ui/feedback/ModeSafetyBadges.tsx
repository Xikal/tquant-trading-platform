import type { CSSProperties } from "react";
import { Tag, Tooltip } from "antd";

export type ModeSafetyKind = "shadow" | "preview" | "research" | "paper" | "watch";

interface ModeSafetyBadgeDefinition {
  kind: ModeSafetyKind;
  label: string;
  tooltip: string;
  docHref: string;
  color: string;
}

export const MODE_SAFETY_BADGES: Record<ModeSafetyKind, ModeSafetyBadgeDefinition> = {
  shadow: {
    kind: "shadow",
    label: "影子对照",
    tooltip: "只做长期差异统计，不进入生产排序。",
    docHref: "/docs/reports/platform-architecture-strategy-engine-parity-2026-06-04.md",
    color: "blue",
  },
  preview: {
    kind: "preview",
    label: "预览验证",
    tooltip: "只展示一致性校验，不替换事实源。",
    docHref: "/docs/reports/platform-architecture-execution-model-parity-2026-06-04.md",
    color: "cyan",
  },
  research: {
    kind: "research",
    label: "研究模式",
    tooltip: "用于研究和样本外验证，不绕过生产门。",
    docHref: "/docs/architecture/current-boundary-map.md",
    color: "purple",
  },
  paper: {
    kind: "paper",
    label: "模拟盘",
    tooltip: "模拟成交用于复盘，不作为生产事实源。",
    docHref: "/docs/architecture/current-boundary-map.md",
    color: "gold",
  },
  watch: {
    kind: "watch",
    label: "观察提醒",
    tooltip: "near_entry / watch / watch_only 只提醒观察，不进入生产收益排行。",
    docHref: "/docs/architecture/current-boundary-map.md",
    color: "default",
  },
};

const BADGE_LIST_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 4,
  minWidth: 0,
};

export function ModeSafetyBadges({ kinds }: { kinds: ModeSafetyKind[] }) {
  return (
    <div style={BADGE_LIST_STYLE} aria-label="模式边界说明">
      {kinds.map((kind) => {
        const badge = MODE_SAFETY_BADGES[kind];
        return (
          <Tooltip key={kind} title={`${badge.tooltip} ${badge.docHref}`}>
            <Tag color={badge.color}>{badge.label}</Tag>
          </Tooltip>
        );
      })}
    </div>
  );
}
