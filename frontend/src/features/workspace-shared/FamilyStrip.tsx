import type { CSSProperties } from "react";
import { useMemo, useState } from "react";
import { Button, Modal } from "antd";
import type { LowBuyPriorityBoardResult, LowBuyPriorityFamilySection } from "../../types";
import { familyStripQualityText } from "./workspaceFamilyQuality";
import { formatPct, plainTradingText } from "./workspaceFormatters";

const FAMILY_STRIP_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: 8,
  margin: "8px 0",
};

const FAMILY_TILE_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
};

const INFO_PILL_STYLE: CSSProperties = {
  display: "grid",
  gap: 2,
  border: "1px solid var(--border)",
  borderRadius: 8,
  background: "var(--panel)",
  padding: 8,
};

const INFO_PILL_COMPACT_STYLE: CSSProperties = {
  padding: "5px 7px",
};

const INFO_LABEL_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 11,
};

const INFO_VALUE_STYLE: CSSProperties = {
  color: "var(--text)",
  fontSize: 12,
  lineHeight: 1.35,
};

const INFO_WARN_VALUE_STYLE: CSSProperties = {
  color: "#a16207",
};

const DETAIL_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
};

const DETAIL_SECTION_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
};

const DETAIL_TITLE_STYLE: CSSProperties = {
  margin: 0,
  fontSize: 13,
};

const DETAIL_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  margin: 0,
  paddingLeft: 16,
};

const DETAIL_ITEM_STYLE: CSSProperties = {
  color: "var(--text)",
  fontSize: 12,
  lineHeight: 1.45,
};

export function FamilyStrip({ priorityBoard }: { priorityBoard: LowBuyPriorityBoardResult | null }) {
  const sections = priorityBoard?.family_sections ?? [];
  const [activeKey, setActiveKey] = useState("");
  const activeSection = useMemo(
    () => sections.find((section) => section.family_key === activeKey) ?? null,
    [activeKey, sections],
  );
  if (!sections.length) {
    return null;
  }
  return (
    <>
      <div style={FAMILY_STRIP_STYLE}>
        {sections.slice(0, 4).map((section) => (
          <div key={section.family_key} style={FAMILY_TILE_STYLE}>
            <InfoPill label={section.family_text} value={familyValue(priorityBoard, section)} />
            <Button size="small" type="text" onClick={() => setActiveKey(section.family_key)}>
              查看明细
            </Button>
          </div>
        ))}
      </div>
      <Modal
        open={Boolean(activeSection)}
        title={activeSection?.family_text ?? "策略族明细"}
        footer={null}
        onCancel={() => setActiveKey("")}
      >
        {activeSection ? <FamilyDetail priorityBoard={priorityBoard} section={activeSection} /> : null}
      </Modal>
    </>
  );
}

function FamilyDetail({
  priorityBoard,
  section,
}: {
  priorityBoard: LowBuyPriorityBoardResult | null;
  section: LowBuyPriorityFamilySection;
}) {
  const quality = familyStripQualityText(priorityBoard, section) || section.data_quality_text || priorityBoard?.data_quality_text || "数据可用";
  const fallbackItems = section.items.filter((item) => item.main_force_advice?.fallback_reason);
  const weakQualityItems = section.items.filter((item) => item.data_quality && !["fresh", "ok", "complete", "verified"].includes(item.data_quality));
  return (
    <div style={DETAIL_GRID_STYLE}>
      <div style={DETAIL_SECTION_STYLE}>
        <h4 style={DETAIL_TITLE_STYLE}>族维度概览</h4>
        <InfoPill compact label="候选" value={`${section.total_candidates} 只`} />
        <InfoPill compact label="立即/重点/跟踪" value={`${section.immediate_count}/${section.focus_count}/${section.track_count}`} />
        <InfoPill compact label="净胜优势" value={formatPct(section.performance?.net_win_rate, 0)} />
        <InfoPill compact label="数据质量" value={quality} tone={quality === "数据可用" ? "neutral" : "warn"} />
      </div>
      <DetailList title="代表策略" items={section.top_strategy_titles.length ? section.top_strategy_titles : section.items.flatMap((item) => item.strategy_titles).slice(0, 6)} />
      <DetailList title="主力旁路 fallback" items={fallbackItems.map((item) => `${item.name || item.symbol}：${item.main_force_advice?.fallback_reason}`)} empty="无 fallback" />
      <DetailList title="弱数据候选" items={weakQualityItems.map((item) => `${item.name || item.symbol}：${item.data_quality_text || item.data_quality}`)} empty="无弱数据候选" />
      <DetailList title="高分候选" items={section.items.slice(0, 6).map(candidateLine)} empty="无候选" />
    </div>
  );
}

function DetailList({ title, items, empty = "无" }: { title: string; items: string[]; empty?: string }) {
  const visibleItems = items.filter(Boolean).slice(0, 8);
  return (
    <div style={DETAIL_SECTION_STYLE}>
      <h4 style={DETAIL_TITLE_STYLE}>{title}</h4>
      <ul style={DETAIL_LIST_STYLE}>
        {(visibleItems.length ? visibleItems : [empty]).map((item) => (
          <li key={item} style={DETAIL_ITEM_STYLE}>{plainTradingText(item)}</li>
        ))}
      </ul>
    </div>
  );
}

function InfoPill({
  label,
  value,
  compact = false,
  tone = "neutral",
}: {
  label: string;
  value: string;
  compact?: boolean;
  tone?: "neutral" | "warn";
}) {
  return (
    <div style={{ ...INFO_PILL_STYLE, ...(compact ? INFO_PILL_COMPACT_STYLE : undefined) }}>
      <span style={INFO_LABEL_STYLE}>{label}</span>
      <strong style={{ ...INFO_VALUE_STYLE, ...(tone === "warn" ? INFO_WARN_VALUE_STYLE : undefined) }}>{value}</strong>
    </div>
  );
}

function familyValue(priorityBoard: LowBuyPriorityBoardResult | null, section: LowBuyPriorityFamilySection): string {
  return [
    `${section.total_candidates} 只`,
    `净胜优势 ${formatPct(section.performance?.net_win_rate, 0)}`,
    familyStripQualityText(priorityBoard, section),
  ].filter(Boolean).join(" / ");
}

function candidateLine(item: LowBuyPriorityFamilySection["items"][number]): string {
  return [
    item.name || item.symbol,
    item.buy_signal_text || item.action_summary,
    item.strategy_performance_text,
    item.execution_quality_text,
  ].filter(Boolean).join(" / ");
}
