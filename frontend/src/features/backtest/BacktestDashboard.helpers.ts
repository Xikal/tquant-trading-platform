import type { BacktestRunSummary, BacktestStatus } from "../../api/backtests";

export const STATUS_META: Record<BacktestStatus, { label: string; tone: string }> = {
  pending: { label: "待运行", tone: "pending" },
  queued: { label: "队列中", tone: "pending" },
  running: { label: "运行中", tone: "running" },
  completed: { label: "已完成", tone: "completed" },
  succeeded: { label: "已完成", tone: "completed" },
  failed: { label: "失败", tone: "failed" },
  cancelled: { label: "已取消", tone: "cancelled" },
  deleted: { label: "已删除", tone: "cancelled" },
  timeout: { label: "已超时", tone: "failed" },
};

export function statusMeta(status: BacktestStatus): { label: string; tone: string } {
  return STATUS_META[status] ?? STATUS_META.pending;
}

export function isCancellableStatus(status: BacktestStatus): boolean {
  return status === "queued" || status === "pending" || status === "running";
}

export function dateRange(run: BacktestRunSummary): string {
  if (!run.start_date && !run.end_date) {
    return "--";
  }
  return `${run.start_date ?? "--"} → ${run.end_date ?? "--"}`;
}

export function formatProgress(progress: number | null | undefined, status: BacktestStatus): string {
  if (status === "completed" || status === "succeeded") return "100%";
  if (typeof progress !== "number" || !Number.isFinite(progress)) {
    return status === "running" ? "运行中" : "--";
  }
  return `${Math.round(progress)}%`;
}

export function formatWaitSeconds(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "--";
  if (value < 60) return `${Math.round(value)} 秒`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return seconds > 0 ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分`;
}
