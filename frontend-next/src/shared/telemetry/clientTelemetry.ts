import { isSensitiveFieldName, redactSensitiveText } from "../security/redaction";

export type TelemetryKind = "api" | "sse" | "worker" | "chart" | "mutation" | "ui";

export interface TelemetryEvent {
  kind: TelemetryKind;
  name: string;
  ts: number;
  durationMs?: number;
  status?: string;
  route?: string;
  meta?: Record<string, string | number | boolean | null>;
}

export interface TelemetrySnapshot {
  total: number;
  byKind: Record<TelemetryKind, number>;
  recent: TelemetryEvent[];
}

const MAX_EVENTS = 200;
const EMPTY_COUNTS: Record<TelemetryKind, number> = {
  api: 0,
  sse: 0,
  worker: 0,
  chart: 0,
  mutation: 0,
  ui: 0,
};

const events: TelemetryEvent[] = [];

export function recordTelemetry(event: Omit<TelemetryEvent, "ts" | "route"> & { ts?: number; route?: string }): void {
  events.push({
    ...event,
    ts: event.ts ?? Date.now(),
    route: event.route ?? currentRoute(),
    meta: event.meta ? sanitizeMeta(event.meta) : undefined,
  });
  if (events.length > MAX_EVENTS) events.splice(0, events.length - MAX_EVENTS);
}

export function telemetrySnapshot(limit = 50): TelemetrySnapshot {
  const byKind = { ...EMPTY_COUNTS };
  for (const event of events) byKind[event.kind] += 1;
  return {
    total: events.length,
    byKind,
    recent: events.slice(-Math.max(0, limit)),
  };
}

export function resetTelemetry(): void {
  events.length = 0;
}

export function exposeTelemetryForDiagnostics(): void {
  if (typeof window === "undefined") return;
  const target = window as Window & { __FRONTEND_NEXT_TELEMETRY__?: () => TelemetrySnapshot };
  target.__FRONTEND_NEXT_TELEMETRY__ = () => telemetrySnapshot();
}

function currentRoute(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return window.location?.pathname;
}

function sanitizeMeta(meta: Record<string, string | number | boolean | null>): Record<string, string | number | boolean | null> {
  return Object.fromEntries(
    Object.entries(meta).map(([key, value]) => {
      if (isSensitiveFieldName(key)) return [key, "[redacted]"];
      if (typeof value === "string") {
        const redacted = redactSensitiveText(value);
        if (redacted.length > 120) return [key, `${redacted.slice(0, 117)}...`];
        return [key, redacted];
      }
      return [key, value];
    }),
  );
}

declare global {
  interface Window {
    __FRONTEND_NEXT_TELEMETRY__?: () => TelemetrySnapshot;
  }
}
