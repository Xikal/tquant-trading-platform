import type { LowBuyPriorityBoardResult, LowBuyPriorityFamilySection } from "../../types";

const HEALTHY_QUALITY = new Set(["", "fresh", "ok", "complete", "available", "verified"]);

export function familyStripQualityText(
  priorityBoard: LowBuyPriorityBoardResult | null,
  section: LowBuyPriorityFamilySection,
): string {
  const hints = new Set<string>();
  const boardQuality = normalize(priorityBoard?.data_quality);
  const boardQualityText = priorityBoard?.data_quality_text?.trim();
  if (boardQuality && !HEALTHY_QUALITY.has(boardQuality)) {
    hints.add(boardQualityText || `数据${priorityBoard?.data_quality}`);
  }
  if (priorityBoard?.missing_strategies?.length) {
    hints.add(`待补${priorityBoard.missing_strategies.length}策`);
  }
  if (priorityBoard?.stale_strategies?.length) {
    hints.add(`待刷新${priorityBoard.stale_strategies.length}策`);
  }

  const sectionQuality = normalize(section.data_quality);
  if (sectionQuality && !HEALTHY_QUALITY.has(sectionQuality)) {
    hints.add(section.data_quality_text?.trim() || `族数据${section.data_quality}`);
  }
  const weakItemCount = section.items.filter((item) => {
    const itemQuality = normalize(item.data_quality);
    return itemQuality && !HEALTHY_QUALITY.has(itemQuality);
  }).length;
  if (weakItemCount) {
    hints.add(`弱数据${weakItemCount}只`);
  }
  const fallbackCount = section.items.filter((item) => item.main_force_advice?.fallback_reason).length;
  if (fallbackCount) {
    hints.add(`旁路fallback ${fallbackCount}`);
  }
  return Array.from(hints).slice(0, 3).join(" / ");
}

function normalize(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}
