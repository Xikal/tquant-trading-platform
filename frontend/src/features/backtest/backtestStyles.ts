import type { CSSProperties } from "react";

export const BACKTEST_FORM_STACK_STYLE: CSSProperties = {
  width: "100%",
  display: "flex",
  flexDirection: "column",
  gap: 12,
};

export const BACKTEST_SEGMENTED_STYLE: CSSProperties = {
  marginBottom: 8,
  border: "1px solid rgba(148, 163, 184, 0.24)",
  background: "#fff",
};

export const BACKTEST_HELP_STYLE: CSSProperties = {
  margin: "0 0 10px",
  color: "#64748b",
  fontSize: 12,
  lineHeight: 1.45,
};

export const BACKTEST_LABEL_STYLE: CSSProperties = {
  color: "#475569",
  fontSize: 12,
  fontWeight: 800,
};

export const BACKTEST_STRATEGY_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
};

export const BACKTEST_STRATEGY_ITEM_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: 8,
  width: "100%",
  padding: "8px 10px",
  textAlign: "left",
  border: "1px solid #dce5f0",
  borderRadius: 10,
  background: "#f8fafc",
};

export const BACKTEST_STRATEGY_ITEM_ACTIVE_STYLE: CSSProperties = {
  borderColor: "rgba(214, 165, 92, 0.7)",
  background: "#fff8e8",
};

export const BACKTEST_STRATEGY_TITLE_STYLE: CSSProperties = {
  color: "var(--text)",
  fontSize: 12,
  fontWeight: 800,
};

export const BACKTEST_STRATEGY_KEY_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 10,
};

export const BACKTEST_EXPERT_FIELDS_STYLE: CSSProperties = {
  width: "100%",
};

export const BACKTEST_WARNING_LIST_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  alignItems: "end",
};

export const BACKTEST_WARNING_ITEM_STYLE: CSSProperties = {
  padding: "7px 9px",
  border: "1px solid rgba(214, 165, 92, 0.36)",
  borderRadius: 10,
  background: "#fff7e6",
  color: "#9a5b00",
  fontSize: 12,
  fontWeight: 800,
};

export const BACKTEST_CAPACITY_CONTROLS_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  alignItems: "end",
};

export const BACKTEST_CAPACITY_FIELD_STYLE: CSSProperties = {
  flex: "1 1 320px",
  minWidth: "min(360px, 100%)",
};

export const BACKTEST_CAPACITY_BUTTON_STYLE: CSSProperties = {
  minHeight: 34,
};

export const BACKTEST_FRONTIER_AXIS_STYLE: CSSProperties = {
  stroke: "#cbd5e1",
};

export const BACKTEST_FRONTIER_POINT_STYLE: CSSProperties = {
  fill: "#d6a55c",
  opacity: 0.78,
};

export const BACKTEST_STATUS_BASE_STYLE: CSSProperties = {
  display: "inline-grid",
  gap: 2,
  minWidth: 82,
  padding: "6px 8px",
  border: "1px solid #dce5f0",
  borderRadius: 10,
  background: "#f8fafc",
  color: "#475569",
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 11,
  fontWeight: 900,
  textAlign: "left",
};

export const BACKTEST_STATUS_LABEL_STYLE: CSSProperties = {
  color: "inherit",
  fontFamily: '"IBM Plex Sans", "PingFang SC", sans-serif',
  fontSize: 10,
  opacity: 0.76,
};

const BACKTEST_STATUS_TONE_STYLES: Record<string, CSSProperties> = {
  pending: {
    borderColor: "rgba(214, 165, 92, 0.4)",
    background: "#fff8e8",
    color: "#a16207",
  },
  running: {
    borderColor: "rgba(103, 232, 249, 0.38)",
    background: "#ecfeff",
    color: "#036672",
  },
  completed: {
    borderColor: "rgba(31, 139, 76, 0.28)",
    background: "#f0fbf4",
    color: "#166534",
  },
  failed: {
    borderColor: "rgba(195, 74, 54, 0.28)",
    background: "#fff4f1",
    color: "#991b1b",
  },
  cancelled: {
    borderColor: "rgba(100, 116, 139, 0.25)",
    background: "#f1f5f9",
    color: "#475569",
  },
};

export function backtestStatusToneStyle(tone: string): CSSProperties {
  return BACKTEST_STATUS_TONE_STYLES[tone] ?? {};
}

export const BACKTEST_RUN_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
};

export const BACKTEST_RUN_ROW_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "110px minmax(150px, 1fr) minmax(180px, 0.9fr) 84px 92px",
  gap: 10,
  alignItems: "center",
  width: "100%",
  borderRadius: 12,
  background: "#fff",
  textAlign: "left",
};

export const BACKTEST_RUN_ROW_ACTIVE_STYLE: CSSProperties = {
  borderColor: "rgba(214, 165, 92, 0.72)",
  background: "linear-gradient(90deg, #fff8e8, #fff)",
};

export const BACKTEST_RUN_ROW_TEXT_STYLE: CSSProperties = {
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export const BACKTEST_RUN_ROW_META_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 12,
};

export const BACKTEST_SUMMARY_LINE_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  marginBottom: 10,
};

export const BACKTEST_SUMMARY_ITEM_STYLE: CSSProperties = {
  padding: "5px 8px",
  borderRadius: 999,
  background: "#f1f5f9",
  color: "#475569",
  fontSize: 12,
  fontWeight: 800,
};

export const BACKTEST_ATTRIBUTION_STRIP_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 7,
  marginTop: 10,
  paddingTop: 10,
  borderTop: "1px solid #e8eef6",
};

export const BACKTEST_ATTRIBUTION_TITLE_STYLE: CSSProperties = {
  padding: "5px 8px",
  borderRadius: 999,
  background: "#0b1422",
  color: "#f4d08a",
  fontSize: 12,
};

export const BACKTEST_ATTRIBUTION_ITEM_STYLE: CSSProperties = {
  padding: "5px 8px",
  borderRadius: 999,
  background: "#f8fafc",
  color: "#475569",
  fontSize: 12,
  fontWeight: 800,
};

export const BACKTEST_METRIC_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
  gap: 8,
};

export const BACKTEST_METRIC_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  minHeight: 58,
  padding: "9px 10px",
  border: "1px solid var(--line)",
  borderRadius: 10,
  background: "#f8fafc",
};

export const BACKTEST_METRIC_LABEL_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 11,
  fontWeight: 800,
};

export const BACKTEST_METRIC_VALUE_STYLE: CSSProperties = {
  fontSize: 18,
};

export const BACKTEST_METRIC_UP_STYLE: CSSProperties = {
  borderColor: "#f2b8aa",
  background: "#fff4f1",
  color: "var(--up)",
};

export const BACKTEST_METRIC_DOWN_STYLE: CSSProperties = {
  borderColor: "#b8e5c7",
  background: "#f0fbf4",
  color: "var(--down)",
};

export const BACKTEST_NUMBER_SETTING_STYLE: CSSProperties = {
  width: "min(150px, 100%)",
};

export const BACKTEST_NUMBER_INPUT_STYLE: CSSProperties = {
  width: "100%",
};

export const BACKTEST_SUBMIT_BUTTON_STYLE: CSSProperties = {
  minHeight: 38,
  borderRadius: 10,
  background: "linear-gradient(90deg, #d6a55c 0%, #0b1422 48%, #0b1422 100%)",
  fontWeight: 900,
};

export const BACKTEST_ECHARTS_STYLE: CSSProperties = {
  width: "100%",
  minHeight: 300,
  borderRadius: 16,
  background: "#08111f",
};

export const BACKTEST_ECHARTS_COMPACT_STYLE: CSSProperties = {
  minHeight: 230,
};

export const BACKTEST_ECHARTS_ALT_STYLE: CSSProperties = {
  minHeight: 250,
  margin: "10px 0",
  background: "#ffffff",
  border: "1px solid #e3e9f2",
};

export function combineBacktestStyles(...styles: Array<CSSProperties | undefined>): CSSProperties {
  return Object.assign({}, ...styles.filter(Boolean));
}
