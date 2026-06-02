import { useEffect } from "react";
import { API_BASE, request } from "../../api/base";
import { updateLiveQuoteSignal, type LiveQuotePatch } from "./liveQuoteSignals";

interface StreamTokenResponse {
  stream_token: string;
  expires_in: number;
}

interface QuoteStreamOptions {
  active?: boolean;
  apiBase?: string;
  createEventSource?: (url: string) => EventSource;
  fallbackPoll?: () => Promise<unknown> | unknown;
  reconnectDelayMs?: number;
  reconnectLimit?: number;
  requestStreamToken?: () => Promise<StreamTokenResponse>;
  symbols: string[];
}

interface QuoteStreamController {
  close: () => void;
  fallbackReady: Promise<void>;
  ready: Promise<void>;
}

interface IntradayConfirmationPayload {
  items?: IntradayConfirmationStreamItem[];
}

interface IntradayConfirmationStreamItem {
  symbol?: string;
  latest_price?: number | null;
  tick?: Record<string, unknown> | null;
  confirmed?: boolean | null;
  late_confirmed?: boolean | null;
}

const DEFAULT_RECONNECT_LIMIT = 2;
const DEFAULT_RECONNECT_DELAY_MS = 1000;

export function useQuoteStream(options: QuoteStreamOptions): void {
  const symbolsKey = normalizedSymbols(options.symbols).join(",");
  useEffect(() => {
    if (options.active === false || !symbolsKey || liveQuoteSignalsDisabled()) {
      return undefined;
    }
    const controller = startQuoteStream({ ...options, symbols: symbolsKey.split(",") });
    return () => controller.close();
  }, [options.active, symbolsKey, options.fallbackPoll]);
}

export function startQuoteStream({
  apiBase = API_BASE,
  createEventSource = (url) => new EventSource(url),
  fallbackPoll,
  reconnectDelayMs = DEFAULT_RECONNECT_DELAY_MS,
  reconnectLimit = DEFAULT_RECONNECT_LIMIT,
  requestStreamToken = defaultRequestStreamToken,
  symbols,
}: QuoteStreamOptions): QuoteStreamController {
  let closed = false;
  let source: EventSource | undefined;
  let reconnectTimer: ReturnType<typeof globalThis.setTimeout> | undefined;
  let reconnects = 0;
  let lastEventId = "";
  const cleanedSymbols = normalizedSymbols(symbols);
  let resolveReady: () => void = () => undefined;
  let resolveFallback: () => void = () => undefined;
  const ready = new Promise<void>((resolve) => {
    resolveReady = resolve;
  });
  const fallbackReady = new Promise<void>((resolve) => {
    resolveFallback = resolve;
  });

  const close = () => {
    closed = true;
    if (reconnectTimer !== undefined) {
      globalThis.clearTimeout(reconnectTimer);
    }
    source?.close();
  };

  const fallback = () => {
    void Promise.resolve(fallbackPoll?.()).finally(() => {
      resolveReady();
      resolveFallback();
    });
  };

  const scheduleReconnect = () => {
    if (closed) {
      return;
    }
    if (reconnects >= reconnectLimit) {
      fallback();
      return;
    }
    reconnects += 1;
    reconnectTimer = globalThis.setTimeout(open, reconnectDelayMs);
  };

  const open = () => {
    void requestStreamToken()
      .then((payload) => {
        if (closed || !payload.stream_token || !cleanedSymbols.length) {
          resolveReady();
          return;
        }
        const url = quoteStreamUrl({
          apiBase,
          lastEventId,
          streamToken: payload.stream_token,
          symbols: cleanedSymbols,
        });
        source = createEventSource(url);
        source.addEventListener("intraday_confirmations", (event) => {
          lastEventId = (event as MessageEvent).lastEventId || lastEventId;
          applyIntradayConfirmationEvent((event as MessageEvent).data);
        });
        source.onerror = () => {
          source?.close();
          scheduleReconnect();
        };
        resolveReady();
      })
      .catch(() => {
        scheduleReconnect();
      });
  };

  if (!cleanedSymbols.length || liveQuoteSignalsDisabled()) {
    resolveReady();
  } else {
    open();
  }

  return { close, fallbackReady, ready };
}

export function applyIntradayConfirmationEvent(rawData: string): void {
  try {
    const payload = JSON.parse(rawData) as IntradayConfirmationPayload;
    for (const item of payload.items ?? []) {
      const symbol = item.symbol?.trim();
      if (!symbol) {
        continue;
      }
      const patch = quotePatchFromIntradayItem(item);
      updateLiveQuoteSignal(symbol, patch);
    }
  } catch {
    // Keep the last known hot values when the stream sends a malformed frame.
  }
}

export function quotePatchFromIntradayItem(item: IntradayConfirmationStreamItem): LiveQuotePatch {
  return {
    price: numberFromUnknown(item.latest_price),
    changePct: numberFromUnknown(item.tick?.change_pct ?? item.tick?.pct_chg ?? item.tick?.change_percent),
    signalState: item.confirmed ? "confirmed" : item.late_confirmed ? "late_confirmed" : "watch",
  };
}

function quoteStreamUrl({
  apiBase,
  lastEventId,
  streamToken,
  symbols,
}: {
  apiBase: string;
  lastEventId: string;
  streamToken: string;
  symbols: string[];
}): string {
  const normalizedBase = apiBase.replace(/\/$/, "");
  const base = normalizedBase.endsWith("/api") ? normalizedBase : `${normalizedBase}/api`;
  const params = new URLSearchParams({
    symbols: symbols.join(","),
    client_id: "web-monitor-live-quotes",
    stream_token: streamToken,
    interval_seconds: "15",
  });
  if (lastEventId) {
    params.set("last_event_id", lastEventId);
  }
  return `${base}/intraday/stream?${params.toString()}`;
}

function defaultRequestStreamToken(): Promise<StreamTokenResponse> {
  return request<StreamTokenResponse>("/intraday/subscribe", { method: "POST" });
}

function normalizedSymbols(symbols: string[]): string[] {
  return [...new Set(symbols.map((item) => item.trim().toUpperCase()).filter(Boolean))].slice(0, 30);
}

function numberFromUnknown(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function liveQuoteSignalsDisabled(): boolean {
  return import.meta.env.VITE_LIVE_QUOTE_SIGNALS === "false";
}
