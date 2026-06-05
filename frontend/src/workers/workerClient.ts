import { frontendPerformanceFlagEnabled } from "../config/frontendPerformanceFlags";
import { recordWorkerComputeTelemetry, workerInputCount } from "./telemetry";
import {
  downsampleChartPointsSync,
  filterSortStrategyTrackingSync,
  normalizeMonitorPrioritySync,
  rankAnalysisBatchSync,
} from "./computeSync";
import type {
  AnalysisBatchRankRequest,
  AnalysisBatchRankResponse,
  ChartDownsampleRequest,
  ChartDownsampleResponse,
  MonitorPriorityNormalizeRequest,
  MonitorPriorityNormalizeResponse,
  StrategyTrackingFilterSortRequest,
  StrategyTrackingFilterSortResponse,
  WorkerEnvelope,
  WorkerRequestMap,
  WorkerResponseMap,
  WorkerResult,
  WorkerTaskKind,
} from "./protocol";

type Resolver<K extends WorkerTaskKind> = {
  reject: (error: Error) => void;
  resolve: (value: TimedWorkerResponse<K>) => void;
  timeout: number;
};

type TimedWorkerResponse<K extends WorkerTaskKind> = WorkerResponseMap[K] & {
  __worker_elapsed_ms?: number;
};

let workerInstance: Worker | null = null;
const pending = new Map<string, Resolver<WorkerTaskKind>>();
let sequence = 0;

export function normalizeMonitorPriority(
  request: MonitorPriorityNormalizeRequest,
): Promise<MonitorPriorityNormalizeResponse> {
  return computeWithWorker("monitorPriorityNormalize", request, normalizeMonitorPrioritySync);
}

export function filterSortStrategyTracking(
  request: StrategyTrackingFilterSortRequest,
): Promise<StrategyTrackingFilterSortResponse> {
  return computeWithWorker("strategyTrackingFilterSort", request, filterSortStrategyTrackingSync);
}

export function rankAnalysisBatch(
  request: AnalysisBatchRankRequest,
): Promise<AnalysisBatchRankResponse> {
  return computeWithWorker("analysisBatchRank", request, rankAnalysisBatchSync);
}

export function downsampleChartPoints(
  request: ChartDownsampleRequest,
): Promise<ChartDownsampleResponse> {
  return computeWithWorker("chartDownsample", request, downsampleChartPointsSync);
}

export async function computeWithWorker<K extends WorkerTaskKind>(
  kind: K,
  payload: WorkerRequestMap[K],
  fallback: (payload: WorkerRequestMap[K]) => WorkerResponseMap[K],
  timeoutMs = 1200,
): Promise<WorkerResponseMap[K]> {
  const inputCount = workerInputCount(kind, payload);
  if (!frontendPerformanceFlagEnabled("frontend_worker_compute_enabled") || !canUseWorker(payload)) {
    const startedAt = performanceNow();
    const result = fallback(payload);
    recordWorkerComputeTelemetry({
      elapsed_ms: roundMs(performanceNow() - startedAt),
      input_count: inputCount,
      kind,
      source: "sync_fallback",
      total_ms: roundMs(performanceNow() - startedAt),
    });
    return stripWorkerElapsed(result);
  }
  const startedAt = performanceNow();
  try {
    const result = await requestWorker(kind, payload, timeoutMs);
    recordWorkerComputeTelemetry({
      elapsed_ms: result.__worker_elapsed_ms ?? roundMs(performanceNow() - startedAt),
      input_count: inputCount,
      kind,
      source: "worker",
      total_ms: roundMs(performanceNow() - startedAt),
    });
    delete result.__worker_elapsed_ms;
    return result;
  } catch {
    const fallbackStartedAt = performanceNow();
    const result = fallback(payload);
    recordWorkerComputeTelemetry({
      elapsed_ms: roundMs(performanceNow() - fallbackStartedAt),
      input_count: inputCount,
      kind,
      source: "worker_error_fallback",
      total_ms: roundMs(performanceNow() - startedAt),
    });
    return result;
  }
}

export function resetFrontendComputeWorkerForTests(): void {
  workerInstance?.terminate();
  workerInstance = null;
  for (const resolver of pending.values()) {
    globalThis.clearTimeout(resolver.timeout);
  }
  pending.clear();
}

function requestWorker<K extends WorkerTaskKind>(
  kind: K,
  payload: WorkerRequestMap[K],
  timeoutMs: number,
): Promise<TimedWorkerResponse<K>> {
  const worker = getWorker();
  if (!worker) {
    return Promise.reject(new Error("worker unavailable"));
  }
  const id = `${kind}:${Date.now()}:${sequence += 1}`;
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      pending.delete(id);
      reject(new Error(`worker timeout: ${kind}`));
    }, timeoutMs);
    pending.set(id, { reject, resolve: resolve as Resolver<WorkerTaskKind>["resolve"], timeout });
    worker.postMessage({ id, kind, payload } satisfies WorkerEnvelope<K>);
  });
}

function getWorker(): Worker | null {
  if (typeof Worker === "undefined") {
    return null;
  }
  if (workerInstance) {
    return workerInstance;
  }
  workerInstance = new Worker(new URL("./monitorCompute.worker.ts", import.meta.url), { type: "module" });
  workerInstance.onmessage = (event: MessageEvent<WorkerResult>) => {
    const result = event.data;
    const resolver = pending.get(result.id);
    if (!resolver) {
      return;
    }
    window.clearTimeout(resolver.timeout);
    pending.delete(result.id);
    if (result.error || !result.payload) {
      resolver.reject(new Error(result.error || `worker failed: ${result.kind}`));
      return;
    }
    resolver.resolve({ ...result.payload, __worker_elapsed_ms: result.elapsed_ms } as TimedWorkerResponse<WorkerTaskKind>);
  };
  workerInstance.onerror = () => {
    workerInstance?.terminate();
    workerInstance = null;
    rejectPendingWorkerRequests(new Error("worker error"));
  };
  return workerInstance;
}

function rejectPendingWorkerRequests(error: Error): void {
  for (const [id, resolver] of pending.entries()) {
    window.clearTimeout(resolver.timeout);
    pending.delete(id);
    resolver.reject(error);
  }
}

function canUseWorker(payload: unknown): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const size = Array.isArray((payload as { items?: unknown[] }).items)
    ? (payload as { items: unknown[] }).items.length
    : Array.isArray((payload as { points?: unknown[] }).points)
      ? (payload as { points: unknown[] }).points.length
      : Array.isArray((payload as { board?: { items?: unknown[] } }).board?.items)
        ? ((payload as { board: { items: unknown[] } }).board.items.length)
        : 0;
  return size >= 80;
}

function performanceNow(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}

function roundMs(value: number): number {
  return Number(value.toFixed(3));
}

function stripWorkerElapsed<K extends WorkerTaskKind>(result: TimedWorkerResponse<K>): WorkerResponseMap[K] {
  const { __worker_elapsed_ms: _elapsed, ...payload } = result;
  return payload as WorkerResponseMap[K];
}
