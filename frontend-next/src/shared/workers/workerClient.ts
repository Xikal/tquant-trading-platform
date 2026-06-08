import type { ComputeRequest, ComputeResponse, DownsamplePayload, FilterPayload, SortPayload } from "./protocol";
import { deriveSummary, downsample, filterItems, sortItems } from "./computeSync";
import { redactSensitiveText } from "../security/redaction";
import { recordTelemetry } from "../telemetry/clientTelemetry";

let worker: Worker | null = null;
let sequence = 0;

function getWorker(): Worker | null {
  if (typeof Worker === "undefined") return null;
  if (!worker) {
    worker = new Worker(new URL("./compute.worker.ts", import.meta.url), { type: "module" });
  }
  return worker;
}

export async function runCompute<TPayload, TResult>(kind: ComputeRequest<TPayload>["kind"], payload: TPayload): Promise<ComputeResponse<TResult>> {
  const id = `compute-${++sequence}`;
  const started = performance.now();
  const instance = getWorker();
  if (!instance) {
    recordTelemetry({ kind: "worker", name: kind, status: "sync-fallback-unavailable" });
    return syncFallback(kind, id, payload, started);
  }
  return new Promise((resolve) => {
    let settled = false;
    const timeout = globalThis.setTimeout(() => {
      cleanup();
      recordTelemetry({ kind: "worker", name: kind, status: "timeout-fallback", durationMs: Math.round(performance.now() - started) });
      resolve(syncFallback(kind, id, payload, started));
    }, 1500);
    const cleanup = () => {
      if (settled) return;
      settled = true;
      globalThis.clearTimeout(timeout);
      instance.removeEventListener("message", handleMessage as EventListener);
      instance.removeEventListener("error", handleError);
      instance.removeEventListener("messageerror", handleError);
    };
    const handleMessage = (event: MessageEvent<ComputeResponse<TResult>>) => {
      if (event.data.id !== id) return;
      cleanup();
      if (!event.data.ok) {
        recordTelemetry({
          kind: "worker",
          name: kind,
          status: "error-fallback",
          durationMs: Math.round(event.data.duration_ms),
          meta: event.data.error ? { error: redactSensitiveText(event.data.error) } : undefined,
        });
        resolve(syncFallback(kind, id, payload, started));
        return;
      }
      recordTelemetry({ kind: "worker", name: kind, status: "ok", durationMs: Math.round(event.data.duration_ms) });
      resolve(event.data);
    };
    const handleError = () => {
      cleanup();
      recordTelemetry({ kind: "worker", name: kind, status: "error-fallback", durationMs: Math.round(performance.now() - started) });
      resolve(syncFallback(kind, id, payload, started));
    };
    instance.addEventListener("message", handleMessage as EventListener);
    instance.addEventListener("error", handleError);
    instance.addEventListener("messageerror", handleError);
    try {
      instance.postMessage({ id, kind, payload } satisfies ComputeRequest<TPayload>);
    } catch (error) {
      cleanup();
      recordTelemetry({
        kind: "worker",
        name: kind,
        status: "postmessage-fallback",
        durationMs: Math.round(performance.now() - started),
        meta: { error: redactSensitiveText(error) },
      });
      resolve(syncFallback(kind, id, payload, started));
    }
  });
}

function syncFallback<TPayload, TResult>(kind: ComputeRequest<TPayload>["kind"], id: string, payload: TPayload, started: number): ComputeResponse<TResult> {
  const result =
    kind === "filter"
      ? filterItems(payload as FilterPayload<Record<string, unknown>>)
      : kind === "downsample"
        ? downsample(payload as DownsamplePayload)
        : kind === "sort"
          ? sortItems(payload as SortPayload<Record<string, unknown>>)
          : deriveSummary(payload as Array<Record<string, unknown>>);
  return {
    id,
    ok: true,
    duration_ms: performance.now() - started,
    result: result as TResult,
  };
}

export function filterDisplayItems<T extends Record<string, unknown>>(payload: FilterPayload<T>) {
  return runCompute<FilterPayload<T>, T[]>("filter", payload);
}

export function downsamplePoints(payload: DownsamplePayload) {
  return runCompute<DownsamplePayload, DownsamplePayload["points"]>("downsample", payload);
}

export function sortDisplayItems<T extends object>(payload: SortPayload<T>) {
  return runCompute<SortPayload<T>, T[]>("sort", payload);
}

export function disposeComputeWorker(): void {
  if (worker) recordTelemetry({ kind: "worker", name: "compute-worker", status: "disposed" });
  worker?.terminate();
  worker = null;
}
