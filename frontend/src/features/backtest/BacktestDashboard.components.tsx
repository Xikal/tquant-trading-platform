import type { ReactNode } from "react";
import type { BacktestStatus } from "../../api/backtests";
import { formatProgress, formatWaitSeconds } from "./BacktestDashboard.helpers";

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
    <span className="backtest-progress-cell">
      <i><b style={{ width: `${normalized}%` }} /></i>
      <small>{formatProgress(progress, status)}{waitSeconds ? ` · 约${formatWaitSeconds(waitSeconds)}` : ""}</small>
    </span>
  );
}

export function PanelHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="backtest-panel-title">
      <h2>{title}</h2>
      {action ? <div>{action}</div> : null}
    </div>
  );
}

export function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: string }) {
  return (
    <div className={`backtest-metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function EmptyLine({ text }: { text: string }) {
  return <div className="backtest-empty">{text}</div>;
}
