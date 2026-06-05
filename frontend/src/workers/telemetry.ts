import type { WorkerComputeTelemetrySample, WorkerTaskKind } from "./protocol";

const MAX_SAMPLES = 200;

export function recordWorkerComputeTelemetry(sample: WorkerComputeTelemetrySample): void {
  if (typeof window === "undefined") {
    return;
  }
  window.__TQUANT_FRONTEND_PERF__ ??= { commits: [], workerTasks: [] };
  const target = window.__TQUANT_FRONTEND_PERF__.workerTasks ?? [];
  target.push(sample);
  window.__TQUANT_FRONTEND_PERF__.workerTasks = target;
  if (target.length > MAX_SAMPLES) {
    target.splice(0, target.length - MAX_SAMPLES);
  }
}

export function workerInputCount(kind: WorkerTaskKind, payload: unknown): number {
  if (kind === "monitorPriorityNormalize") {
    return Array.isArray((payload as { board?: { items?: unknown[] } }).board?.items)
      ? (payload as { board: { items: unknown[] } }).board.items.length
      : 0;
  }
  if (kind === "chartDownsample") {
    return Array.isArray((payload as { points?: unknown[] }).points)
      ? (payload as { points: unknown[] }).points.length
      : 0;
  }
  return Array.isArray((payload as { items?: unknown[] }).items)
    ? (payload as { items: unknown[] }).items.length
    : 0;
}
