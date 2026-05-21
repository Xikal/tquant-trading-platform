import type { InstrumentSyncStatus } from "../../types";

export function InstrumentSyncProgress({ status, loading }: { status: InstrumentSyncStatus | null; loading: boolean }) {
  if (!status && !loading) {
    return null;
  }
  const progress = clampProgress(status?.progress_pct ?? (loading ? 5 : 0));
  const isRunning = loading || status?.status === "queued" || status?.status === "running";
  const failed = status?.status === "failed";
  const message = failed ? status?.error || status?.message : status?.message || "正在更新股票库";
  return (
    <div className={`instrument-sync-progress ${failed ? "failed" : isRunning ? "running" : "done"}`}>
      <div className="instrument-sync-progress__head">
        <strong>{failed ? "股票库更新失败" : isRunning ? "股票库更新中" : "股票库已更新"}</strong>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="instrument-sync-progress__bar" aria-label="股票库更新进度">
        <i style={{ width: `${progress}%` }} />
      </div>
      <div className="instrument-sync-progress__meta">
        <span>{message}</span>
        {status?.result ? <small>股票 {status.result.stock ?? 0} / ETF {status.result.etf ?? 0}</small> : null}
      </div>
    </div>
  );
}

function clampProgress(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}
