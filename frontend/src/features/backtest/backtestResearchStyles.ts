import type { CSSProperties } from "react";

export function backtestResearchPanelStyle(focused: boolean): CSSProperties {
  return {
    gridArea: "research",
    display: "grid",
    gap: focused ? 8 : 10,
    minWidth: 0,
    padding: focused ? 0 : undefined,
    border: focused ? 0 : undefined,
    background: focused ? "transparent" : "linear-gradient(180deg, #ffffff, #f8fafc)",
  };
}

export const BACKTEST_RESEARCH_HERO_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  alignItems: "center",
  gap: 10,
  minWidth: 0,
  padding: 10,
  border: "1px solid rgba(214, 165, 92, 0.24)",
  borderRadius: 8,
  background: "#0b1422",
  color: "#ecfeff",
};

export const BACKTEST_RESEARCH_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(360px, 100%), 1fr))",
  gap: 10,
  minWidth: 0,
};

export const BACKTEST_RESEARCH_CARD_STYLE: CSSProperties = {
  display: "grid",
  alignContent: "start",
  gap: 10,
  minWidth: 0,
  padding: 10,
  border: "1px solid #e3eaf3",
  borderRadius: 8,
  background: "rgba(255, 255, 255, 0.92)",
};

export const BACKTEST_RESEARCH_CARD_WIDE_STYLE: CSSProperties = {
  gridColumn: "1 / -1",
};

export const BACKTEST_RESEARCH_TITLE_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto auto",
  alignItems: "center",
  gap: 10,
  minWidth: 0,
};

export const BACKTEST_RESEARCH_TITLE_HEADING_STYLE: CSSProperties = {
  margin: 0,
  fontSize: 12,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export const BACKTEST_RESEARCH_TITLE_META_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 12,
  fontWeight: 700,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export const BACKTEST_RESEARCH_NOTE_STYLE: CSSProperties = {
  padding: "7px 8px",
  border: "1px solid rgba(31, 139, 76, 0.24)",
  borderRadius: 8,
  background: "#f0fbf4",
  color: "#166534",
  fontSize: 12,
  fontWeight: 700,
};

export const BACKTEST_RUN_PICKER_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
};

export const BACKTEST_RUN_PICKER_BUTTON_STYLE: CSSProperties = {
  minHeight: 28,
  fontSize: 12,
};

export const BACKTEST_COMPARE_ACTIONS_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  marginTop: 8,
};

export const BACKTEST_COMPARE_ACTIONS_META_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 12,
  fontWeight: 700,
};

export const BACKTEST_TONE_UP_STYLE: CSSProperties = {
  color: "var(--up)",
  fontWeight: 700,
};

export const BACKTEST_TONE_DOWN_STYLE: CSSProperties = {
  color: "var(--down)",
  fontWeight: 700,
};

export function backtestToneTextStyle(tone: string): CSSProperties {
  if (tone === "up") return BACKTEST_TONE_UP_STYLE;
  if (tone === "down") return BACKTEST_TONE_DOWN_STYLE;
  return {};
}

export const BACKTEST_WINDOW_PRESETS_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  gridColumn: "1 / -1",
};

export const BACKTEST_WINDOW_PRESET_LABEL_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 12,
  fontWeight: 700,
};

export const BACKTEST_WINDOW_PRESET_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(112px, 1fr))",
  gap: 6,
};

export const BACKTEST_WINDOW_PRESET_BUTTON_STYLE: CSSProperties = {
  minHeight: 50,
  padding: 8,
  textAlign: "left",
};

export const BACKTEST_WINDOW_PRESET_TEXT_STYLE: CSSProperties = {
  display: "block",
};

export const BACKTEST_WINDOW_PRESET_HINT_STYLE: CSSProperties = {
  display: "block",
  marginTop: 3,
  color: "var(--muted)",
  fontSize: 12,
};

export const BACKTEST_WINDOW_CARD_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  padding: 10,
  border: "1px solid #e8eef6",
  borderRadius: 12,
  background: "#f8fafc",
};

export const BACKTEST_WINDOW_CARD_META_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 12,
};

export const BACKTEST_WINDOW_CARD_BADGE_ROW_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 6,
};

export const BACKTEST_WINDOW_CARD_BADGE_STYLE: CSSProperties = {
  padding: "3px 6px",
  borderRadius: 999,
  background: "#fff",
  fontSize: 12,
};

export const BACKTEST_FRONTIER_CARD_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  padding: "10px 12px",
  border: "1px solid #d9e2ef",
  borderRadius: 14,
  background: "#fff",
};

export const BACKTEST_FRONTIER_TITLE_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 8,
  color: "#0b1422",
  fontSize: 12,
};

export const BACKTEST_FRONTIER_TITLE_META_STYLE: CSSProperties = {
  color: "#64748b",
};

export const BACKTEST_FRONTIER_SVG_STYLE: CSSProperties = {
  width: "100%",
  minHeight: 150,
};

export const BACKTEST_RESEARCH_FORM_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(126px, 1fr))",
  gap: 8,
  alignItems: "end",
  minWidth: 0,
};

export const BACKTEST_RESULT_BLOCK_STYLE: CSSProperties = {
  display: "grid",
  gap: 10,
};

export const BACKTEST_MINI_METRICS_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: 6,
};

export const BACKTEST_MINI_METRIC_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  minHeight: 50,
  minWidth: 0,
  padding: 8,
  border: "1px solid #e8eef6",
  borderRadius: 8,
  background: "#f8fafc",
};

export const BACKTEST_MINI_METRIC_LOW_STYLE: CSSProperties = {
  borderColor: "rgba(31, 139, 76, 0.28)",
  background: "#edfdf4",
  color: "#166534",
};

export const BACKTEST_MINI_METRIC_MEDIUM_STYLE: CSSProperties = {
  borderColor: "rgba(214, 165, 92, 0.36)",
  background: "#fff7e6",
  color: "#9a5b00",
};

export const BACKTEST_MINI_METRIC_LABEL_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 12,
  fontWeight: 700,
};

export const BACKTEST_MINI_METRIC_VALUE_STYLE: CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export const BACKTEST_TASK_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  maxHeight: 240,
  overflowY: "auto",
  paddingRight: 2,
};

export const BACKTEST_TASK_ROW_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) 54px 44px",
  gap: 6,
  alignItems: "center",
  minWidth: 0,
  padding: 6,
  border: "1px solid #e8eef6",
  borderRadius: 8,
  background: "#fff",
};

export const BACKTEST_TASK_ROW_ACTIVE_STYLE: CSSProperties = {
  borderColor: "rgba(214, 165, 92, 0.7)",
  background: "#fff8e8",
};

export const BACKTEST_TASK_BUTTON_STYLE: CSSProperties = {
  display: "grid",
  gap: 3,
  minWidth: 0,
  border: 0,
  background: "transparent",
  color: "var(--text)",
  padding: 0,
  textAlign: "left",
};

export const BACKTEST_TASK_META_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 12,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export const BACKTEST_WINDOW_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
  gap: 8,
};
