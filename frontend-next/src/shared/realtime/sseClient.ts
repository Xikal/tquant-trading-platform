import { liveQuoteSignals, type LiveQuote } from "./liveQuoteSignals";
import { recordTelemetry } from "../telemetry/clientTelemetry";

let activeSource: EventSource | null = null;
let activeUrl = "";
let subscriberCount = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectAttempt = 0;
let activeSessionId = 0;

const RECONNECT_BASE_DELAY_MS = 1_000;
const RECONNECT_MAX_DELAY_MS = 15_000;

export function startQuoteSse(url: string): () => void {
  if (activeUrl && activeUrl !== url) {
    recordTelemetry({ kind: "sse", name: "quote-stream", status: "replace" });
    closeActiveConnection(true);
  }
  if (!activeUrl) {
    activeUrl = url;
    activeSessionId += 1;
  }
  const sessionId = activeSessionId;
  const shared = activeSource || reconnectTimer;
  if (shared && activeUrl === url) {
    subscriberCount += 1;
    recordTelemetry({ kind: "sse", name: "quote-stream", status: "shared", meta: { subscribers: subscriberCount } });
    let closed = false;
    return () => {
      if (closed) return;
      closed = true;
      releaseSubscription(url, sessionId);
    };
  }
  subscriberCount = 1;
  connectSource(url);
  let closed = false;
  return () => {
    if (closed) return;
    closed = true;
    releaseSubscription(url, sessionId);
  };
}

function connectSource(url: string) {
  if (subscriberCount <= 0 || activeUrl !== url) return;
  clearReconnectTimer();
  liveQuoteSignals.setConnectionState("connecting");
  const source = new EventSource(url, { withCredentials: true });
  activeSource = source;
  recordTelemetry({ kind: "sse", name: "quote-stream", status: "connecting", meta: { attempt: reconnectAttempt } });
  source.onopen = () => {
    if (activeSource !== source) return;
    reconnectAttempt = 0;
    liveQuoteSignals.setConnectionState("open");
    recordTelemetry({ kind: "sse", name: "quote-stream", status: "open" });
  };
  source.onerror = () => {
    if (activeSource !== source) return;
    source.close();
    activeSource = null;
    liveQuoteSignals.setConnectionState("error");
    recordTelemetry({ kind: "sse", name: "quote-stream", status: "error" });
    scheduleReconnect(url);
  };
  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as { quotes?: LiveQuote[]; items?: LiveQuote[] };
      const quotes = payload.quotes ?? payload.items ?? [];
      liveQuoteSignals.upsert(quotes);
      recordTelemetry({ kind: "sse", name: "quote-stream", status: "message", meta: { items: quotes.length } });
    } catch {
      liveQuoteSignals.setConnectionState("error");
      recordTelemetry({ kind: "sse", name: "quote-stream", status: "parse-error" });
    }
  };
}

function scheduleReconnect(url: string) {
  if (subscriberCount <= 0 || activeUrl !== url || reconnectTimer) return;
  const delayMs = Math.min(RECONNECT_BASE_DELAY_MS * 2 ** reconnectAttempt, RECONNECT_MAX_DELAY_MS);
  reconnectAttempt += 1;
  recordTelemetry({ kind: "sse", name: "quote-stream", status: "reconnect-scheduled", meta: { delay_ms: delayMs, attempt: reconnectAttempt } });
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectSource(url);
  }, delayMs);
}

function releaseSubscription(url: string, sessionId: number) {
  if (activeUrl !== url || activeSessionId !== sessionId) return;
  subscriberCount = Math.max(0, subscriberCount - 1);
  if (subscriberCount > 0) return;
  closeActiveConnection();
}

function closeActiveConnection(replaced = false) {
  clearReconnectTimer();
  activeSource?.close();
  activeSource = null;
  activeUrl = "";
  subscriberCount = 0;
  reconnectAttempt = 0;
  activeSessionId += 1;
  liveQuoteSignals.setConnectionState("closed");
  recordTelemetry({ kind: "sse", name: "quote-stream", status: replaced ? "closed-replaced" : "closed" });
}

function clearReconnectTimer() {
  if (!reconnectTimer) return;
  clearTimeout(reconnectTimer);
  reconnectTimer = null;
}
