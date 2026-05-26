import type { CSSProperties, ReactNode } from "react";
import type { BacktestStatus } from "../../api/backtests";
import { formatProgress, formatWaitSeconds } from "./BacktestDashboard.helpers";
import {
  BACKTEST_METRIC_DOWN_STYLE,
  BACKTEST_METRIC_LABEL_STYLE,
  BACKTEST_METRIC_STYLE,
  BACKTEST_METRIC_UP_STYLE,
  BACKTEST_METRIC_VALUE_STYLE,
  combineBacktestStyles,
} from "./backtestStyles";

const BACKTEST_PROGRESS_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
};

const BACKTEST_PROGRESS_BAR_STYLE: CSSProperties = {
  height: 7,
  overflow: "hidden",
  borderRadius: 999,
  background: "rgba(148, 163, 184, 0.2)",
};

const BACKTEST_PROGRESS_FILL_STYLE: CSSProperties = {
  display: "block",
  height: "100%",
  borderRadius: "inherit",
  background: "linear-gradient(90deg, #d6a55c, #38bdf8)",
};

const BACKTEST_PANEL_TITLE_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  marginBottom: 10,
};

const BACKTEST_PANEL_TITLE_HEADING_STYLE: CSSProperties = {
  margin: 0,
  fontSize: 12,
};

const BACKTEST_EMPTY_STYLE: CSSProperties = {
  border: "1px dashed #cbd5e1",
  borderRadius: 10,
  background: "#f8fafc",
  color: "var(--muted)",
  fontSize: 12,
  padding: "9px 10px",
};

export function ProgressCell({
  progress,
  status,
  waitSeconds,
}: {
  progress: number | null | undefined;
  status: BacktestStatus;
  waitSeconds?: number | null;
}) {
  const normalized = status === "completed" || status === "succeeded"
    ? 100
    : typeof progress === "number" && Number.isFinite(progress)
      ? Math.max(0, Math.min(100, progress))
      : status === "running"
        ? 12
        : 0;
  return (
    <span style={BACKTEST_PROGRESS_STYLE}>
      <i style={BACKTEST_PROGRESS_BAR_STYLE}><b style={{ ...BACKTEST_PROGRESS_FILL_STYLE, width: `${normalized}%` }} /></i>
      <small>{formatProgress(progress, status)}{waitSeconds ? ` · 约${formatWaitSeconds(waitSeconds)}` : ""}</small>
    </span>
  );
}

export function PanelHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div style={BACKTEST_PANEL_TITLE_STYLE}>
      <h2 style={BACKTEST_PANEL_TITLE_HEADING_STYLE}>{title}</h2>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: string }) {
  return (
    <div style={combineBacktestStyles(BACKTEST_METRIC_STYLE, tone === "up" ? BACKTEST_METRIC_UP_STYLE : tone === "down" ? BACKTEST_METRIC_DOWN_STYLE : undefined)}>
      <span style={BACKTEST_METRIC_LABEL_STYLE}>{label}</span>
      <strong style={BACKTEST_METRIC_VALUE_STYLE}>{value}</strong>
    </div>
  );
}

export function EmptyLine({ text }: { text: string }) {
  return <div style={BACKTEST_EMPTY_STYLE}>{text}</div>;
}
