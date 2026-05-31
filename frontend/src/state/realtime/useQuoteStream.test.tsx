import { describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { LiveCell } from "../../ui/realtime/LiveCell";
import { clearLiveQuoteSignals, liveQuoteSnapshot } from "./liveQuoteSignals";
import { startQuoteStream } from "./useQuoteStream";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  onerror: (() => void) | null = null;
  readonly listeners = new Map<string, Array<(event: MessageEvent) => void>>();
  closed = false;

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, payload: unknown, lastEventId = "") {
    const event = { data: JSON.stringify(payload), lastEventId } as MessageEvent;
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

describe("quote SSE stream", () => {
  it("writes intraday SSE ticks into live quote signals so LiveCell updates", async () => {
    clearLiveQuoteSignals();
    FakeEventSource.instances = [];
    const controller = startQuoteStream({
      symbols: ["600000"],
      apiBase: "/api",
      createEventSource: (url) => new FakeEventSource(url) as unknown as EventSource,
      requestStreamToken: async () => ({ stream_token: "token-1", expires_in: 3600 }),
    });
    await controller.ready;

    FakeEventSource.instances[0].emit("intraday_confirmations", {
      items: [{
        symbol: "600000",
        latest_price: 10.88,
        tick: { change_pct: 1.56 },
        confirmed: true,
      }],
    }, "evt-1");

    expect(liveQuoteSnapshot("600000")).toEqual({
      price: 10.88,
      changePct: 1.56,
      signalState: "confirmed",
    });
    expect(renderToString(<LiveCell symbol="600000" field="price" fallback="--" />)).toContain("10.880");
    controller.close();
  });

  it("falls back to polling after the SSE connection drops and keeps the page path non-blocking", async () => {
    clearLiveQuoteSignals();
    FakeEventSource.instances = [];
    const fallbackPoll = vi.fn();
    const controller = startQuoteStream({
      symbols: ["600000"],
      apiBase: "/api",
      reconnectLimit: 0,
      createEventSource: (url) => new FakeEventSource(url) as unknown as EventSource,
      fallbackPoll,
      requestStreamToken: async () => ({ stream_token: "token-1", expires_in: 3600 }),
    });
    await controller.ready;

    expect(() => FakeEventSource.instances[0].onerror?.()).not.toThrow();
    await controller.fallbackReady;

    expect(fallbackPoll).toHaveBeenCalledTimes(1);
    expect(FakeEventSource.instances[0].closed).toBe(true);
    controller.close();
  });
});
