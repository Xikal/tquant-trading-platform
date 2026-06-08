import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("frontend-next quote SSE client", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("shares a same-url EventSource and closes it after the final cleanup", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const { startQuoteSse } = await import("../sseClient");
    const { liveQuoteSignals } = await import("../liveQuoteSignals");
    liveQuoteSignals.reset();

    const cleanupA = startQuoteSse("/api/quotes/stream");
    const cleanupB = startQuoteSse("/api/quotes/stream");

    expect(FakeEventSource.instances).toHaveLength(1);
    expect(liveQuoteSignals.connectionState()).toBe("connecting");

    FakeEventSource.instances[0].onopen?.(new Event("open"));
    expect(liveQuoteSignals.connectionState()).toBe("open");

    cleanupA();
    expect(FakeEventSource.instances[0].closed).toBe(false);
    expect(liveQuoteSignals.connectionState()).toBe("open");

    cleanupB();
    expect(FakeEventSource.instances[0].closed).toBe(true);
    expect(liveQuoteSignals.connectionState()).toBe("closed");
  });

  it("upserts quote messages and flags invalid payloads as errors", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const { startQuoteSse } = await import("../sseClient");
    const { liveQuoteSignals } = await import("../liveQuoteSignals");
    liveQuoteSignals.reset();

    const cleanup = startQuoteSse("/api/quotes/stream");
    const source = FakeEventSource.instances[0];
    source.onmessage?.({ data: JSON.stringify({ quotes: [{ symbol: "000001", price: 12.3 }] }) } as MessageEvent);
    expect(liveQuoteSignals.quotes()["000001"]).toMatchObject({ symbol: "000001", price: 12.3 });

    source.onmessage?.({ data: "not-json" } as MessageEvent);
    expect(liveQuoteSignals.connectionState()).toBe("error");

    cleanup();
  });

  it("reconnects with backoff after stream errors without creating duplicate active sources", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", FakeEventSource);
    const { startQuoteSse } = await import("../sseClient");
    const { liveQuoteSignals } = await import("../liveQuoteSignals");
    liveQuoteSignals.reset();

    const cleanup = startQuoteSse("/api/quotes/stream");
    const firstSource = FakeEventSource.instances[0];
    firstSource.onopen?.(new Event("open"));
    firstSource.onerror?.(new Event("error"));

    expect(firstSource.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(liveQuoteSignals.connectionState()).toBe("error");

    await vi.advanceTimersByTimeAsync(1_000);

    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[1].url).toBe("/api/quotes/stream");
    expect(liveQuoteSignals.connectionState()).toBe("connecting");

    cleanup();
    vi.useRealTimers();
  });

  it("cancels pending reconnects after the final subscriber cleanup", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", FakeEventSource);
    const { startQuoteSse } = await import("../sseClient");
    const { liveQuoteSignals } = await import("../liveQuoteSignals");
    liveQuoteSignals.reset();

    const cleanup = startQuoteSse("/api/quotes/stream");
    FakeEventSource.instances[0].onerror?.(new Event("error"));

    cleanup();
    await vi.advanceTimersByTimeAsync(1_000);

    expect(FakeEventSource.instances).toHaveLength(1);
    expect(liveQuoteSignals.connectionState()).toBe("closed");
    vi.useRealTimers();
  });
});

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  closed = false;

  constructor(public readonly url: string, public readonly init?: EventSourceInit) {
    FakeEventSource.instances.push(this);
  }

  close() {
    this.closed = true;
  }
}
