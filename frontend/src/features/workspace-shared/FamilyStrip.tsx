import { useMemo } from "react";
import { Button, Modal } from "antd";
import { useWorkspaceMonitorStore } from "../../stores/workspaceMonitorStore";
import type { LowBuyPriorityBoardResult, LowBuyPriorityFamilySection } from "../../types";
import { familyStripQualityText } from "./workspaceFamilyQuality";
import { formatPct, plainTradingText } from "./workspaceFormatters";

export function FamilyStrip({ priorityBoard }: { priorityBoard: LowBuyPriorityBoardResult | null }) {
  const sections = priorityBoard?.family_sections ?? [];
  const activeKey = useWorkspaceMonitorStore((state) => state.activeFamilyDetailKey);
  const setActiveKey = useWorkspaceMonitorStore((state) => state.setActiveFamilyDetailKey);
  const activeSection = useMemo(
    () => sections.find((section) => section.family_key === activeKey) ?? null,
    [activeKey, sections],
  );
  if (!sections.length) {
    return null;
  }
  return (
    <>
      <div className="tq-family-strip">
        {sections.slice(0, 4).map((section) => (
          <div key={section.family_key} className="tq-family-strip__tile">
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
    <div className="tq-family-detail">
      <div className="tq-family-detail__section">
        <h4 className="tq-family-detail__title">族维度概览</h4>
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
    <div className="tq-family-detail__section">
      <h4 className="tq-family-detail__title">{title}</h4>
      <ul className="tq-family-detail__list">
        {(visibleItems.length ? visibleItems : [empty]).map((item) => (
          <li key={item} className="tq-family-detail__item">{plainTradingText(item)}</li>
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
    <div className={`tq-info-pill ${compact ? "tq-info-pill--compact" : ""}`.trim()}>
      <span className="tq-info-pill__label">{label}</span>
      <strong className={`tq-info-pill__value ${tone === "warn" ? "tq-info-pill__value--warn" : ""}`.trim()}>{value}</strong>
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
