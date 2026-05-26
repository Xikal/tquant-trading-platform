import type { CSSProperties } from "react";

export function backtestDashboardGridStyle(_isWide: boolean): CSSProperties {
  return {
    display: "grid",
    gap: 8,
    alignItems: "start",
    minWidth: 0,
    fontSize: 11,
    lineHeight: 1.32,
  };
}

export function backtestHeroStyle(isWide: boolean): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: isWide ? "minmax(150px, 220px) minmax(0, 1fr) minmax(120px, 180px)" : "1fr",
    gap: 8,
    alignItems: "center",
    minHeight: 0,
    minWidth: 0,
    padding: 8,
    borderColor: "rgba(103, 232, 249, 0.28)",
    background:
      "linear-gradient(135deg, rgba(11, 20, 34, 0.96), rgba(17, 27, 45, 0.94))",
    color: "#ecfeff",
    boxShadow: "inset 0 0 0 1px rgba(214, 165, 92, 0.14)",
  };
}

export const BACKTEST_HEADER_TITLE_WRAP_STYLE: CSSProperties = {
  display: "grid",
  gap: 2,
  minWidth: 0,
};

export const BACKTEST_HEADER_TITLE_STYLE: CSSProperties = {
  color: "#f8fafc",
  fontSize: 13,
  fontWeight: 900,
  lineHeight: 1.2,
};

export const BACKTEST_HEADER_SUMMARY_STYLE: CSSProperties = {
  color: "#aeb8c7",
  fontSize: 11,
  lineHeight: 1.32,
};

export const BACKTEST_HEADER_METRICS_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(76px, 1fr))",
  gap: 6,
  minWidth: 0,
};

export const BACKTEST_HEADER_PILL_STYLE: CSSProperties = {
  display: "grid",
  gap: 2,
  minWidth: 0,
  minHeight: 34,
  padding: "5px 7px",
  border: "1px solid rgba(148, 163, 184, 0.2)",
  borderRadius: 7,
  background: "rgba(255, 255, 255, 0.06)",
};

export const BACKTEST_HEADER_PILL_LABEL_STYLE: CSSProperties = {
  color: "#94a3b8",
  fontSize: 10,
  fontWeight: 800,
};

export const BACKTEST_HEADER_PILL_VALUE_STYLE: CSSProperties = {
  color: "#f8fafc",
  fontSize: 12,
  fontWeight: 900,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

export const BACKTEST_HEADER_ACTIONS_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  minWidth: 0,
};

export const BACKTEST_TABS_STYLE: CSSProperties = {
  minWidth: 0,
};

export const BACKTEST_TAB_BODY_STYLE: CSSProperties = {
  minWidth: 0,
};

export function backtestSubmitTabGridStyle(isWide: boolean): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: isWide ? "minmax(280px, 360px) minmax(0, 1fr)" : "1fr",
    gap: 8,
    minWidth: 0,
    alignItems: "start",
  };
}

export function backtestOverviewTabGridStyle(isWide: boolean): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: isWide ? "minmax(280px, 0.88fr) minmax(360px, 1.12fr)" : "1fr",
    gap: 8,
    minWidth: 0,
    alignItems: "start",
  };
}

export const BACKTEST_KICKER_STYLE: CSSProperties = {
  display: "inline-flex",
  marginBottom: 8,
  color: "#f4d08a",
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 11,
  fontWeight: 900,
  letterSpacing: 0,
  textTransform: "uppercase",
};

export const BACKTEST_HERO_TITLE_STYLE: CSSProperties = {
  margin: 0,
  fontSize: 13,
  lineHeight: 1.15,
  letterSpacing: 0,
};

export const BACKTEST_HERO_TEXT_STYLE: CSSProperties = {
  maxWidth: 620,
  margin: "4px 0 0",
  color: "#aeb8c7",
  fontSize: 12,
  lineHeight: 1.45,
};

export const BACKTEST_STATUS_RAIL_STYLE: CSSProperties = {
  minWidth: 0,
  width: "100%",
  padding: 0,
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: 8,
  background: "rgba(255, 255, 255, 0.05)",
};

export const BACKTEST_STATUS_RAIL_SUMMARY_STYLE: CSSProperties = {
  cursor: "pointer",
  fontSize: 11,
  fontWeight: 800,
  color: "#dbeafe",
};

export const BACKTEST_STATUS_RAIL_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(58px, 1fr))",
  gap: 4,
  marginTop: 6,
};

export const BACKTEST_SECTION_META_STYLE: CSSProperties = {
  color: "var(--muted)",
  fontSize: 12,
  fontWeight: 800,
};

export const BACKTEST_NOTICE_STYLE: CSSProperties = {
  marginBottom: 10,
  border: "1px solid rgba(31, 139, 76, 0.24)",
  background: "#f0fbf4",
  color: "#166534",
  padding: "9px 10px",
  borderRadius: 10,
  fontSize: 12,
};

export const BACKTEST_ERROR_STYLE: CSSProperties = {
  marginBottom: 10,
  border: "1px solid rgba(195, 74, 54, 0.26)",
  background: "#fff4f1",
  color: "#991b1b",
  padding: "9px 10px",
  borderRadius: 10,
  fontSize: 12,
};

export const BACKTEST_EMPTY_STYLE: CSSProperties = {
  border: "1px dashed #cbd5e1",
  background: "#f8fafc",
  color: "var(--muted)",
  fontSize: 12,
  padding: "9px 10px",
  borderRadius: 10,
};

export const BACKTEST_CHART_EMPTY_STYLE: CSSProperties = {
  border: "1px dashed #cbd5e1",
  background: "#f8fafc",
  color: "var(--muted)",
  fontSize: 12,
  padding: "9px 10px",
  borderRadius: 10,
};

export const BACKTEST_ADVANCED_FIELDS_STYLE: CSSProperties = {
  gridColumn: "1 / -1",
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: 8,
  padding: 8,
  minWidth: 0,
};

export const BACKTEST_ADVANCED_FIELDS_SUMMARY_STYLE: CSSProperties = {
  cursor: "pointer",
  fontSize: 12,
  fontWeight: 800,
  listStylePosition: "inside",
};

export const BACKTEST_ADVANCED_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: 8,
  marginTop: 8,
  alignItems: "end",
};

export const BACKTEST_ADVANCED_GRID_COMPACT_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: 8,
  marginTop: 8,
  alignItems: "end",
};

export const BACKTEST_PANEL_SURFACE_STYLE: CSSProperties = {
  minWidth: 0,
  alignSelf: "start",
  height: "100%",
};
