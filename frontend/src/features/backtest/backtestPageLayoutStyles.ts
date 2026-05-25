import type { CSSProperties } from "react";

export function backtestDashboardGridStyle(isWide: boolean): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: isWide ? "minmax(350px, 430px) minmax(0, 1fr)" : "1fr",
    gridTemplateAreas: isWide
      ? `"hero hero"
         "submit runs"
         "submit detail"
         "equity equity"
         "trades trades"
         "research research"`
      : `"hero"
         "submit"
         "runs"
         "detail"
         "equity"
         "trades"
         "research"`,
    gap: 12,
    alignItems: "start",
  };
}

export function backtestHeroStyle(isWide: boolean): CSSProperties {
  return {
    display: "grid",
    gridTemplateColumns: isWide ? "minmax(0, 1fr) minmax(320px, 520px)" : "1fr",
    gap: 18,
    alignItems: "end",
    minHeight: 154,
    borderColor: "rgba(103, 232, 249, 0.28)",
    background:
      "linear-gradient(135deg, rgba(11, 20, 34, 0.96), rgba(17, 27, 45, 0.94)), radial-gradient(circle at 78% 12%, rgba(103, 232, 249, 0.2), transparent 34%)",
    color: "#ecfeff",
    boxShadow: "inset 0 0 0 1px rgba(214, 165, 92, 0.14), 0 14px 38px rgba(11, 20, 34, 0.14)",
  };
}

export const BACKTEST_KICKER_STYLE: CSSProperties = {
  display: "inline-flex",
  marginBottom: 8,
  color: "#f4d08a",
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 11,
  fontWeight: 900,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
};

export const BACKTEST_HERO_TITLE_STYLE: CSSProperties = {
  margin: 0,
  fontSize: "clamp(28px, 4vw, 46px)",
  letterSpacing: "-0.06em",
};

export const BACKTEST_HERO_TEXT_STYLE: CSSProperties = {
  maxWidth: 620,
  margin: "8px 0 0",
  color: "#aeb8c7",
};

export const BACKTEST_STATUS_RAIL_STYLE: CSSProperties = {
  padding: 10,
  border: "1px solid rgba(148, 163, 184, 0.18)",
  borderRadius: 14,
  background: "rgba(255, 255, 255, 0.05)",
};

export const BACKTEST_STATUS_RAIL_SUMMARY_STYLE: CSSProperties = {
  cursor: "pointer",
  fontSize: 12,
  fontWeight: 800,
  color: "#dbeafe",
};

export const BACKTEST_STATUS_RAIL_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(78px, 1fr))",
  gap: 8,
  marginTop: 10,
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
  borderRadius: 14,
  padding: 10,
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
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "10px 12px",
  marginTop: 10,
  alignItems: "end",
};

export const BACKTEST_ADVANCED_GRID_COMPACT_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "10px 12px",
  marginTop: 10,
  alignItems: "end",
};
