import { afterEach, describe, expect, it, vi } from "vitest";

describe("frontend-next worker client", () => {
  afterEach(async () => {
    const { disposeComputeWorker } = await import("../workerClient");
    disposeComputeWorker();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.resetModules();
  });

  it("cleans listeners and falls back to sync compute after worker timeout", async () => {
    vi.useFakeTimers();
    const worker = new FakeWorker();
    vi.stubGlobal("Worker", workerConstructor(worker));

    const { filterDisplayItems } = await import("../workerClient");
    const request = filterDisplayItems({
      items: [
        { symbol: "000001", name: "平安银行" },
        { symbol: "600000", name: "浦发银行" },
      ],
      keyword: "浦发",
      fields: ["name"],
    });

    expect(worker.listenerCount("message")).toBe(1);
    await vi.advanceTimersByTimeAsync(1500);
    await expect(request).resolves.toMatchObject({ ok: true, result: [{ symbol: "600000", name: "浦发银行" }] });
    expect(worker.listenerCount("message")).toBe(0);
    expect(worker.listenerCount("error")).toBe(0);
    expect(worker.listenerCount("messageerror")).toBe(0);
  });

  it("terminates the retained worker on dispose", async () => {
    const worker = new FakeWorker();
    vi.stubGlobal("Worker", workerConstructor(worker));

    const { disposeComputeWorker, filterDisplayItems } = await import("../workerClient");
    const request = filterDisplayItems({ items: [], keyword: "" });
    worker.reply({ id: worker.lastMessage.id, ok: true, duration_ms: 1, result: [] });
    await request;

    disposeComputeWorker();
    expect(worker.terminated).toBe(true);
  });

  it("falls back to sync sorting when the worker reports an error", async () => {
    const worker = new FakeWorker();
    vi.stubGlobal("Worker", workerConstructor(worker));

    const { sortDisplayItems } = await import("../workerClient");
    const { resetTelemetry, telemetrySnapshot } = await import("../../telemetry/clientTelemetry");
    resetTelemetry();
    const request = sortDisplayItems({
      items: [
        { symbol: "000001", score: 82 },
        { symbol: "600000", score: 91 },
      ],
      key: "score",
      direction: "desc",
      numeric: true,
    });
    worker.reply({ id: worker.lastMessage.id, ok: false, duration_ms: 2, error: "worker failed access_token=secret-token-123 password=unsafe" });

    await expect(request).resolves.toMatchObject({
      ok: true,
      result: [
        { symbol: "600000", score: 91 },
        { symbol: "000001", score: 82 },
      ],
    });
    expect(telemetrySnapshot().recent).toContainEqual(
      expect.objectContaining({
        kind: "worker",
        status: "error-fallback",
        meta: expect.objectContaining({
          error: "worker failed access_token=[redacted] password=[redacted]",
        }),
      }),
    );
    expect(JSON.stringify(telemetrySnapshot().recent)).not.toContain("secret-token-123");
    expect(JSON.stringify(telemetrySnapshot().recent)).not.toContain("unsafe");
  });

  it("cleans listeners and falls back when posting to the worker throws", async () => {
    const worker = new FakeWorker();
    worker.postMessageError = new Error("post failed refresh_token=refresh-789 password=unsafe");
    vi.stubGlobal("Worker", workerConstructor(worker));

    const { filterDisplayItems } = await import("../workerClient");
    const { resetTelemetry, telemetrySnapshot } = await import("../../telemetry/clientTelemetry");
    resetTelemetry();

    await expect(
      filterDisplayItems({
        items: [
          { symbol: "000001", name: "平安银行" },
          { symbol: "600000", name: "浦发银行" },
        ],
        keyword: "平安",
        fields: ["name"],
      }),
    ).resolves.toMatchObject({ ok: true, result: [{ symbol: "000001", name: "平安银行" }] });

    expect(worker.listenerCount("message")).toBe(0);
    expect(worker.listenerCount("error")).toBe(0);
    expect(worker.listenerCount("messageerror")).toBe(0);
    expect(telemetrySnapshot().recent).toContainEqual(
      expect.objectContaining({
        kind: "worker",
        status: "postmessage-fallback",
        meta: expect.objectContaining({
          error: "post failed refresh_token=[redacted] password=[redacted]",
        }),
      }),
    );
    expect(JSON.stringify(telemetrySnapshot().recent)).not.toContain("refresh-789");
    expect(JSON.stringify(telemetrySnapshot().recent)).not.toContain("unsafe");
  });
});

function workerConstructor(worker: FakeWorker) {
  return vi.fn(function WorkerMock() {
    return worker;
  });
}

class FakeWorker {
  listeners = new Map<string, Set<EventListener>>();
  lastMessage: { id: string; kind: string; payload: unknown } = { id: "", kind: "", payload: null };
  postMessageError: Error | null = null;
  terminated = false;

  addEventListener(type: string, listener: EventListener) {
    const listeners = this.listeners.get(type) ?? new Set<EventListener>();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: EventListener) {
    this.listeners.get(type)?.delete(listener);
  }

  postMessage(message: { id: string; kind: string; payload: unknown }) {
    if (this.postMessageError) throw this.postMessageError;
    this.lastMessage = message;
  }

  terminate() {
    this.terminated = true;
  }

  reply(data: unknown) {
    this.listeners.get("message")?.forEach((listener) => listener({ data } as MessageEvent));
  }

  listenerCount(type: string): number {
    return this.listeners.get(type)?.size ?? 0;
  }
}
