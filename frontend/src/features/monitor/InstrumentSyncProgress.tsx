import type { CSSProperties } from "react";
import type { InstrumentSyncStatus } from "../../types";

const SYNC_PROGRESS_STYLE: CSSProperties = {
  display: "grid",
  gap: 7,
  marginTop: 10,
  padding: 10,
  border: "1px solid rgba(148, 163, 184, 0.24)",
  borderRadius: 10,
  background: "rgba(248, 250, 252, 0.9)",
};

const SYNC_PROGRESS_FAILED_STYLE: CSSProperties = {
  borderColor: "rgba(220, 38, 38, 0.32)",
  background: "#fff7f7",
};

const SYNC_PROGRESS_ROW_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
};

const SYNC_PROGRESS_TITLE_STYLE: CSSProperties = {
  color: "#0f172a",
  fontSize: 13,
};

const SYNC_PROGRESS_SIDE_TEXT_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 12,
  whiteSpace: "nowrap",
};

const SYNC_PROGRESS_MESSAGE_STYLE: CSSProperties = {
  minWidth: 0,
  color: "#475569",
  fontSize: 12,
};

const SYNC_PROGRESS_BAR_STYLE: CSSProperties = {
  height: 8,
  overflow: "hidden",
  borderRadius: 999,
  background: "rgba(148, 163, 184, 0.18)",
};

const SYNC_PROGRESS_VALUE_STYLE: CSSProperties = {
  display: "block",
  height: "100%",
  borderRadius: "inherit",
  background: "linear-gradient(90deg, #d6a55c, #38bdf8)",
  transition: "width 0.35s ease",
};

export function InstrumentSyncProgress({ status, loading }: { status: InstrumentSyncStatus | null; loading: boolean }) {
  if (!status && !loading) {
    return null;
  }
  const progress = clampProgress(status?.progress_pct ?? (loading ? 5 : 0));
  const isRunning = loading || status?.status === "queued" || status?.status === "running";
  const failed = status?.status === "failed";
  const message = failed ? status?.error || status?.message : status?.message || "正在更新股票库";
  return (
    <div style={{ ...SYNC_PROGRESS_STYLE, ...(failed ? SYNC_PROGRESS_FAILED_STYLE : null) }}>
      <div style={SYNC_PROGRESS_ROW_STYLE}>
        <strong style={SYNC_PROGRESS_TITLE_STYLE}>{failed ? "股票库更新失败" : isRunning ? "股票库更新中" : "股票库已更新"}</strong>
        <span style={SYNC_PROGRESS_SIDE_TEXT_STYLE}>{Math.round(progress)}%</span>
      </div>
      <div style={SYNC_PROGRESS_BAR_STYLE} aria-label="股票库更新进度">
        <i style={{ ...SYNC_PROGRESS_VALUE_STYLE, width: `${progress}%` }} />
      </div>
      <div style={SYNC_PROGRESS_ROW_STYLE}>
        <span style={SYNC_PROGRESS_MESSAGE_STYLE}>{message}</span>
        {status?.result ? <small style={SYNC_PROGRESS_SIDE_TEXT_STYLE}>股票 {status.result.stock ?? 0} / ETF {status.result.etf ?? 0}</small> : null}
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
