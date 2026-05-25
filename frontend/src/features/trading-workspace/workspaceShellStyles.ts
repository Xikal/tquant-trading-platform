import type { CSSProperties } from "react";

export const WORKSPACE_APP_STYLE: CSSProperties = {
  padding: "clamp(8px, 1vw, 16px)",
};

export const WORKSPACE_AUTH_LOADING_STYLE: CSSProperties = {
  ...WORKSPACE_APP_STYLE,
  display: "grid",
  minHeight: "100vh",
  placeItems: "center",
};

export const WORKSPACE_MAIN_STYLE: CSSProperties = {
  width: "min(1440px, calc(100vw - 16px))",
  margin: "0 auto",
  paddingTop: 10,
};

export function topbarStyle(stacked: boolean): CSSProperties {
  return {
    position: "sticky",
    top: 0,
    zIndex: 10,
    display: "grid",
    gridTemplateColumns: stacked ? "1fr" : "minmax(180px, 260px) minmax(360px, 1fr) auto",
    gap: 12,
    alignItems: "center",
    minHeight: 60,
    borderRadius: 10,
    background: "var(--deep)",
    color: "#fff",
    padding: "10px 14px",
  };
}

export const TOPBAR_BRAND_STYLE: CSSProperties = {
  display: "grid",
  gap: 2,
};

export const TOPBAR_BRAND_TEXT_STYLE: CSSProperties = {
  color: "#f8fafc",
  fontSize: 14,
};

export const TOPBAR_NAV_STYLE: CSSProperties = {
  display: "flex",
  minWidth: 0,
  justifyContent: "flex-start",
  gap: 6,
  overflowX: "auto",
  scrollbarWidth: "thin",
};

export const TOPBAR_NAV_STACKED_STYLE: CSSProperties = {
  width: "100%",
  flexWrap: "wrap",
};

export const TOPBAR_NAV_BUTTON_STYLE: CSSProperties = {
  minHeight: 34,
  borderColor: "transparent",
  background: "transparent",
  color: "#aeb8c7",
  fontSize: 11,
  whiteSpace: "nowrap",
};

export const TOPBAR_NAV_ACTIVE_STYLE: CSSProperties = {
  borderColor: "rgba(214, 165, 92, 0.72)",
  background: "var(--accent)",
  color: "var(--deep)",
};

export const TOPBAR_NAV_SECTION_ACTIVE_STYLE: CSSProperties = {
  borderColor: "transparent",
  background: "transparent",
  color: "#fff",
};

export const TOPBAR_CHIPS_STYLE: CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: 8,
  color: "#aeb8c7",
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 11,
};

export const TOPBAR_CHIP_STYLE: CSSProperties = {
  display: "inline-grid",
  gridTemplateColumns: "auto auto",
  alignItems: "center",
  minHeight: 34,
  gap: 6,
  border: "1px solid rgba(148, 163, 184, 0.2)",
  borderRadius: 9,
  background: "rgba(255, 255, 255, 0.06)",
  color: "#cbd5e1",
  fontWeight: 800,
  lineHeight: 1,
  padding: "5px 9px",
  boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.05)",
};

export const TOPBAR_CHIP_LABEL_STYLE: CSSProperties = {
  color: "#7f8fa3",
  fontSize: 10,
  fontWeight: 900,
};

export const TOPBAR_CHIP_VALUE_STYLE: CSSProperties = {
  color: "#f8fafc",
  fontSize: 13,
};

export const TOPBAR_OPPORTUNITY_CHIP_STYLE: CSSProperties = {
  ...TOPBAR_CHIP_STYLE,
  borderColor: "rgba(214, 165, 92, 0.42)",
  background: "linear-gradient(135deg, rgba(214, 165, 92, 0.16), rgba(214, 165, 92, 0.05))",
};

export const TOPBAR_RISK_CHIP_STYLE: CSSProperties = {
  ...TOPBAR_CHIP_STYLE,
  borderColor: "rgba(198, 40, 40, 0.4)",
  background: "linear-gradient(135deg, rgba(198, 40, 40, 0.12), rgba(15, 23, 42, 0.1))",
};

export const TOPBAR_PULSE_CHIP_STYLE: CSSProperties = {
  ...TOPBAR_CHIP_STYLE,
  borderColor: "rgba(59, 130, 246, 0.42)",
  background: "linear-gradient(135deg, rgba(59, 130, 246, 0.13), rgba(6, 182, 212, 0.08))",
};

export const TOPBAR_OPPORTUNITY_VALUE_STYLE: CSSProperties = {
  ...TOPBAR_CHIP_VALUE_STYLE,
  color: "#f4d08a",
};

export const TOPBAR_RISK_VALUE_STYLE: CSSProperties = {
  ...TOPBAR_CHIP_VALUE_STYLE,
  color: "#ff6b6b",
};

export const TOPBAR_PULSE_VALUE_STYLE: CSSProperties = {
  ...TOPBAR_CHIP_VALUE_STYLE,
  color: "#67e8f9",
};

export function monitorGridStyle(stacked: boolean): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: stacked ? "1fr" : "minmax(0, 1fr) minmax(360px, 440px)",
    gridTemplateAreas: stacked
      ? `"summary"
         "input"
         "priority"
         "watch"
         "etf"`
      : `"summary input"
         "priority input"
         "watch input"
         "etf input"`,
    gridAutoRows: "min-content",
    gap: "clamp(12px, 1vw, 16px)",
    minHeight: "calc(100vh - 88px)",
  };
}

export const MONITOR_SUMMARY_STYLE: CSSProperties = {
  gridArea: "summary",
  alignSelf: "start",
};

export const MONITOR_INPUT_STYLE: CSSProperties = {
  gridArea: "input",
};

export const MONITOR_PRIORITY_STYLE: CSSProperties = {
  gridArea: "priority",
  alignSelf: "start",
};

export const MONITOR_WATCH_STYLE: CSSProperties = {
  gridArea: "watch",
  alignSelf: "start",
};

export const MONITOR_ETF_STYLE: CSSProperties = {
  gridArea: "etf",
  alignSelf: "start",
};
