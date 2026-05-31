import { signal, type Signal } from "@preact/signals-react";

export type LiveQuoteField = "price" | "changePct" | "signalState";

export interface LiveQuoteSignalSet {
  price: Signal<number | null>;
  changePct: Signal<number | null>;
  signalState: Signal<string>;
}

export interface LiveQuotePatch {
  price?: number | null;
  changePct?: number | null;
  signalState?: string | null;
}

export interface LiveQuoteSnapshot {
  price: number | null;
  changePct: number | null;
  signalState: string;
}

type RenderProbe = {
  count: (symbol: string, field: LiveQuoteField) => number;
  reset: () => void;
  watch: (symbol: string, field: LiveQuoteField) => () => void;
};

const quoteSignals = new Map<string, LiveQuoteSignalSet>();
const renderProbeCounts = new Map<string, number>();
const renderProbeWatchers = new Map<string, Set<LiveQuoteField>>();

export function liveQuoteSignalsFor(symbol: string): LiveQuoteSignalSet {
  const key = normalizeSymbol(symbol);
  const existing = quoteSignals.get(key);
  if (existing) {
    return existing;
  }
  const created: LiveQuoteSignalSet = {
    price: signal<number | null>(null),
    changePct: signal<number | null>(null),
    signalState: signal(""),
  };
  quoteSignals.set(key, created);
  return created;
}

export function updateLiveQuoteSignal(symbol: string, patch: LiveQuotePatch): void {
  const key = normalizeSymbol(symbol);
  if (!key) {
    return;
  }
  const signals = liveQuoteSignalsFor(key);
  updateField(key, "price", signals.price, patch.price);
  updateField(key, "changePct", signals.changePct, patch.changePct);
  if (patch.signalState !== undefined) {
    const next = patch.signalState ?? "";
    if (signals.signalState.value !== next) {
      signals.signalState.value = next;
      markProbeRender(key, "signalState");
    }
  }
}

export function seedLiveQuoteSignal(symbol: string, snapshot: LiveQuoteSnapshot): void {
  updateLiveQuoteSignal(symbol, snapshot);
}

export function liveQuoteSnapshot(symbol: string): LiveQuoteSnapshot {
  const signals = liveQuoteSignalsFor(symbol);
  return {
    price: signals.price.value,
    changePct: signals.changePct.value,
    signalState: signals.signalState.value,
  };
}

export function clearLiveQuoteSignals(): void {
  quoteSignals.clear();
  renderProbeCounts.clear();
  renderProbeWatchers.clear();
}

export function createLiveQuoteRenderProbe(): RenderProbe {
  return {
    count: (symbol, field) => renderProbeCounts.get(probeKey(symbol, field)) ?? 0,
    reset: () => renderProbeCounts.clear(),
    watch: (symbol, field) => {
      const key = normalizeSymbol(symbol);
      const fields = renderProbeWatchers.get(key) ?? new Set<LiveQuoteField>();
      fields.add(field);
      renderProbeWatchers.set(key, fields);
      return () => {
        const current = renderProbeWatchers.get(key);
        current?.delete(field);
        if (current?.size === 0) {
          renderProbeWatchers.delete(key);
        }
      };
    },
  };
}

function updateField(
  symbol: string,
  field: Exclude<LiveQuoteField, "signalState">,
  target: Signal<number | null>,
  value: number | null | undefined,
): void {
  if (value === undefined) {
    return;
  }
  const next = normalizeNumber(value);
  if (target.value !== next) {
    target.value = next;
    markProbeRender(symbol, field);
  }
}

function normalizeNumber(value: number | null): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalizeSymbol(symbol: string): string {
  return symbol.trim().toUpperCase();
}

function markProbeRender(symbol: string, field: LiveQuoteField): void {
  const key = normalizeSymbol(symbol);
  if (!renderProbeWatchers.get(key)?.has(field)) {
    return;
  }
  const itemKey = probeKey(key, field);
  renderProbeCounts.set(itemKey, (renderProbeCounts.get(itemKey) ?? 0) + 1);
}

function probeKey(symbol: string, field: LiveQuoteField): string {
  return `${normalizeSymbol(symbol)}:${field}`;
}
