import { afterEach, describe, expect, it } from "vitest";
import { exposeTelemetryForDiagnostics, recordTelemetry, resetTelemetry, telemetrySnapshot } from "../clientTelemetry";

describe("frontend-next client telemetry", () => {
  afterEach(() => {
    resetTelemetry();
    delete window.__FRONTEND_NEXT_TELEMETRY__;
  });

  it("records bounded in-memory events by kind", () => {
    recordTelemetry({ kind: "api", name: "request", status: "ok", durationMs: 12 });
    recordTelemetry({ kind: "worker", name: "filter", status: "fallback" });

    expect(telemetrySnapshot()).toMatchObject({
      total: 2,
      byKind: {
        api: 1,
        worker: 1,
      },
    });
  });

  it("redacts sensitive metadata and exposes a diagnostic snapshot", () => {
    recordTelemetry({
      kind: "api",
      name: "request",
      meta: {
        token: "secret-token",
        operation: "monitorWorkspace",
        error: "Authorization: Bearer access-token-123 refresh_token=refresh-token-456 password=unsafe",
        long_value: "x".repeat(140),
      },
    });
    exposeTelemetryForDiagnostics();

    const snapshot = window.__FRONTEND_NEXT_TELEMETRY__?.();

    expect(snapshot?.recent[0].meta).toMatchObject({
      token: "[redacted]",
      operation: "monitorWorkspace",
      error: "Authorization: Bearer [redacted] refresh_token=[redacted] password=[redacted]",
    });
    expect(String(snapshot?.recent[0].meta?.error)).not.toContain("access-token-123");
    expect(String(snapshot?.recent[0].meta?.error)).not.toContain("refresh-token-456");
    expect(String(snapshot?.recent[0].meta?.error)).not.toContain("unsafe");
    expect(String(snapshot?.recent[0].meta?.long_value).length).toBeLessThanOrEqual(120);
  });
});
