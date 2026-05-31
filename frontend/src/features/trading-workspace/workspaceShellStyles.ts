import type { CSSProperties } from "react";

/* ===== 应用外壳：固定左侧栏 + 内容列 ===== */
export const SIDEBAR_WIDTH = 220;
export const SIDEBAR_COLLAPSED_WIDTH = 64;

export const WORKSPACE_SHELL_STYLE: CSSProperties = {
  minHeight: "100vh",
  background: "var(--bg-base)",
};

export const WORKSPACE_APP_STYLE: CSSProperties = {
  minHeight: "100vh",
  maxWidth: "100vw",
  overflowX: "hidden",
  padding: "clamp(8px, 1vw, 16px)",
};

export const WORKSPACE_AUTH_LOADING_STYLE: CSSProperties = {
  ...WORKSPACE_APP_STYLE,
  display: "grid",
  minHeight: "100vh",
  placeItems: "center",
};

export function sidebarStyle(collapsed: boolean): CSSProperties {
  return {
    position: "fixed",
    top: 0,
    left: 0,
    bottom: 0,
    width: collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH,
    display: "flex",
    flexDirection: "column",
    background: "var(--brand-ink)",
    zIndex: 101,
    overflow: "hidden",
    transition: "width var(--dur-base) var(--ease)",
  };
}

export const SIDEBAR_INNER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100%",
  minHeight: 0,
};

export function sidebarBrandStyle(collapsed: boolean): CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    justifyContent: collapsed ? "center" : "flex-start",
    height: 56,
    flexShrink: 0,
    padding: collapsed ? "0" : "0 18px",
    color: "rgba(255, 255, 255, 0.95)",
    fontSize: "var(--fs-md)",
    fontWeight: 700,
    letterSpacing: "0.02em",
    whiteSpace: "nowrap",
    overflow: "hidden",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
  };
}

export const SIDEBAR_MENU_STYLE: CSSProperties = {
  flex: 1,
  minHeight: 0,
  overflowY: "auto",
  overflowX: "hidden",
  background: "transparent",
  borderInlineEnd: "none",
  paddingTop: "var(--sp-2)",
};

export const SIDEBAR_FOOTER_STYLE: CSSProperties = {
  flexShrink: 0,
  padding: "var(--sp-2)",
  borderTop: "1px solid rgba(255, 255, 255, 0.08)",
};

export const SIDEBAR_COLLAPSE_BTN_STYLE: CSSProperties = {
  width: "100%",
  color: "rgba(255, 255, 255, 0.72)",
};

export const DRAWER_BODY_STYLE: CSSProperties = {
  padding: 0,
  background: "var(--brand-ink)",
};

export function contentColStyle(marginLeft: number): CSSProperties {
  return {
    marginLeft,
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    transition: "margin-left var(--dur-base) var(--ease)",
  };
}

export const CONTENT_MAIN_STYLE: CSSProperties = {
  flex: 1,
  minWidth: 0,
  overflowX: "hidden",
  padding: "var(--sp-5)",
};

export const CONTENT_INNER_STYLE: CSSProperties = {
  width: "100%",
  maxWidth: 1440,
  margin: "0 auto",
};

/* ===== 顶栏：瘦身浅色上下文条 ===== */
export const TOPBAR_STYLE: CSSProperties = {
  position: "sticky",
  top: 0,
  zIndex: 100,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  height: 56,
  flexShrink: 0,
  padding: "0 var(--sp-4)",
  background: "var(--bg-elevated)",
  borderBottom: "1px solid var(--line)",
  boxShadow: "var(--shadow-1)",
};

export const TOPBAR_LEFT_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  minWidth: 0,
};

export const TOPBAR_TITLE_STYLE: CSSProperties = {
  color: "var(--text-1)",
  fontSize: "var(--fs-md)",
  fontWeight: 600,
  whiteSpace: "nowrap",
};

export const TOPBAR_ICON_BTN_STYLE: CSSProperties = {
  color: "var(--text-1)",
};

export const TOPBAR_RIGHT_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
};

export const TOPBAR_CHIP_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  height: 30,
  padding: "0 10px",
  border: "1px solid var(--line)",
  borderRadius: "var(--radius-pill)",
  background: "var(--bg-subtle)",
  color: "var(--text-2)",
  fontWeight: 600,
  fontSize: "var(--fs-micro)",
  lineHeight: 1,
};

export const TOPBAR_CHIP_VALUE_STYLE: CSSProperties = {
  color: "var(--text-1)",
  fontWeight: 700,
  fontVariantNumeric: "tabular-nums",
};

/* ===== 监控页栅格（沿用，未改动） ===== */
export function monitorGridStyle(stacked: boolean): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: stacked ? "1fr" : "minmax(0, 1fr) minmax(360px, 440px)",
    gridTemplateAreas: stacked
      ? `"summary"
         "input"
         "priority"
         "etf"`
      : `"summary input"
         "priority input"
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
