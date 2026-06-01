import type { CSSProperties } from "react";
import type { Tone } from "./workspaceTypes";

export const DISPLAY_TONE_VALUE_STYLES: Record<Tone, CSSProperties | undefined> = {
  up: { color: "var(--price-up)" },
  down: { color: "var(--price-down)" },
  warn: { color: "var(--warning)" },
  neutral: undefined,
};

export const METRIC_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: 8,
};

export const METRIC_GRID_COMPACT_STYLE: CSSProperties = {
  gap: 6,
};

export const METRIC_STYLE: CSSProperties = {
  minHeight: 62,
  display: "grid",
  gap: 4,
  alignContent: "center",
  padding: 8,
  border: "1px solid var(--line)",
  borderRadius: 8,
  background: "var(--muted-bg)",
};

export const METRIC_COMPACT_STYLE: CSSProperties = {
  minHeight: 48,
  gap: 2,
  padding: 6,
  borderRadius: 7,
};

export const METRIC_TONE_STYLES: Partial<Record<Tone, CSSProperties>> = {
  up: { background: "var(--mkt-up-soft)", borderColor: "color-mix(in srgb, var(--mkt-up) 24%, transparent)" },
  down: { background: "var(--mkt-down-soft)", borderColor: "color-mix(in srgb, var(--mkt-down) 24%, transparent)" },
  warn: { background: "color-mix(in srgb, var(--warning) 12%, transparent)", borderColor: "color-mix(in srgb, var(--warning) 24%, transparent)" },
};

export const METRIC_TEXT_STYLE: CSSProperties = {
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 12,
};

export const METRIC_TEXT_COMPACT_STYLE: CSSProperties = {
  fontSize: 12,
};

export const METRIC_VALUE_STYLE: CSSProperties = {
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 12,
};

export const METRIC_VALUE_COMPACT_STYLE: CSSProperties = {
  fontSize: 13,
};

export const INFO_PILL_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  padding: 8,
  border: "1px solid var(--line)",
  borderRadius: 8,
  background: "var(--muted-bg)",
};

export const INFO_PILL_COMPACT_STYLE: CSSProperties = {
  gap: 2,
  padding: 6,
  borderRadius: 7,
};

export const INFO_PILL_TEXT_STYLE: CSSProperties = {
  fontFamily: '"IBM Plex Mono", monospace',
  fontSize: 12,
};

export const INFO_PILL_TEXT_COMPACT_STYLE: CSSProperties = {
  fontSize: 12,
};
