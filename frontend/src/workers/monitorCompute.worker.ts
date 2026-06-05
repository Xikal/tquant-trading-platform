import {
  downsampleChartPointsSync,
  filterSortStrategyTrackingSync,
  normalizeMonitorPrioritySync,
  rankAnalysisBatchSync,
} from "./computeSync";
import type { WorkerEnvelope, WorkerResult } from "./protocol";

self.onmessage = (event: MessageEvent<WorkerEnvelope>) => {
  const startedAt = performance.now();
  const request = event.data;
  try {
    const payload = compute(request);
    self.postMessage({
      elapsed_ms: Number((performance.now() - startedAt).toFixed(3)),
      id: request.id,
      kind: request.kind,
      payload,
    } satisfies WorkerResult);
  } catch (error) {
    self.postMessage({
      elapsed_ms: Number((performance.now() - startedAt).toFixed(3)),
      error: error instanceof Error ? error.message : String(error),
      id: request.id,
      kind: request.kind,
    } satisfies WorkerResult);
  }
};

function compute(request: WorkerEnvelope) {
  if (request.kind === "monitorPriorityNormalize") {
    return normalizeMonitorPrioritySync(request.payload as WorkerEnvelope<"monitorPriorityNormalize">["payload"]);
  }
  if (request.kind === "strategyTrackingFilterSort") {
    return filterSortStrategyTrackingSync(request.payload as WorkerEnvelope<"strategyTrackingFilterSort">["payload"]);
  }
  if (request.kind === "analysisBatchRank") {
    return rankAnalysisBatchSync(request.payload as WorkerEnvelope<"analysisBatchRank">["payload"]);
  }
  if (request.kind === "chartDownsample") {
    return downsampleChartPointsSync(request.payload as WorkerEnvelope<"chartDownsample">["payload"]);
  }
  throw new Error(`unknown worker task: ${request.kind}`);
}
