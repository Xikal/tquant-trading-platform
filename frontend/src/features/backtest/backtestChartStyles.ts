import type { CSSProperties } from "react";

export const BACKTEST_CHART_WRAP_STYLE: CSSProperties = {
  display: "grid",
  gap: 10,
  padding: 12,
  borderRadius: 16,
  background: "#08111f",
};

export const BACKTEST_CHART_SVG_STYLE: CSSProperties = {
  display: "block",
  width: "100%",
  minHeight: 220,
};

export const BACKTEST_CHART_FALLBACK_STYLE: CSSProperties = {
  display: "grid",
  minHeight: 140,
  placeItems: "center",
  border: "1px dashed #d9e2ef",
  borderRadius: 14,
  color: "#64748b",
  fontSize: 12,
};

export const BACKTEST_CHART_LEGEND_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  color: "#aeb8c7",
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 12,
};

export const BACKTEST_CHART_LEGEND_ITEM_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
};

export const BACKTEST_CHART_LEGEND_MARK_STYLE: CSSProperties = {
  width: 20,
  height: 3,
  borderRadius: 999,
};

export const BACKTEST_CHART_LEGEND_STRATEGY_STYLE: CSSProperties = {
  ...BACKTEST_CHART_LEGEND_MARK_STYLE,
  background: "#67e8f9",
};

export const BACKTEST_CHART_LEGEND_BENCHMARK_STYLE: CSSProperties = {
  ...BACKTEST_CHART_LEGEND_MARK_STYLE,
  background: "#d6a55c",
};
