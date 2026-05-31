import type { CSSProperties } from "react";
import type { Tone } from "./workspaceTypes";

export const DISPLAY_TONE_VALUE_STYLES: Record<Tone, CSSProperties | undefined> = {
  up: { color: "var(--price-up, #c62828)" },
  down: { color: "var(--price-down, #1f8b4c)" },
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
  up: { background: "#fff7f4", borderColor: "#f0c9bf" },
  down: { background: "#f2fbf5", borderColor: "#b8dbc7" },
  warn: { background: "#fbf4e6", borderColor: "#ecd59a" },
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
