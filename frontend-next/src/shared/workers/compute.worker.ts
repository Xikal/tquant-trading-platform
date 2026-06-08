import type { ComputeRequest, ComputeResponse } from "./protocol";
import { deriveSummary, downsample, filterItems, sortItems } from "./computeSync";
import { redactSensitiveText } from "../security/redaction";

self.onmessage = (event: MessageEvent<ComputeRequest>) => {
  const started = performance.now();
  const request = event.data;
  try {
    const result =
      request.kind === "filter"
        ? filterItems(request.payload as Parameters<typeof filterItems>[0])
        : request.kind === "downsample"
          ? downsample(request.payload as Parameters<typeof downsample>[0])
          : request.kind === "sort"
            ? sortItems(request.payload as Parameters<typeof sortItems>[0])
            : deriveSummary(request.payload as Array<Record<string, unknown>>);
    const response: ComputeResponse = {
      id: request.id,
      ok: true,
      duration_ms: performance.now() - started,
      result,
    };
    self.postMessage(response);
  } catch (error) {
    const response: ComputeResponse = {
      id: request.id,
      ok: false,
      duration_ms: performance.now() - started,
      error: redactSensitiveText(error),
    };
    self.postMessage(response);
  }
};
