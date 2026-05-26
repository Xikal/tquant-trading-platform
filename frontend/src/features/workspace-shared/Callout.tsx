import type { CSSProperties, ReactNode } from "react";
import type { Tone } from "./workspaceTypes";

const CALLOUT_TONE_STYLES: Record<Tone, CSSProperties> = {
  up: { background: "#f0fbf4", borderColor: "rgba(34, 197, 94, 0.34)" },
  down: { background: "#fff1f0", borderColor: "#f2b8b5", color: "#9f1d1d" },
  neutral: { background: "#fff", borderColor: "rgba(148, 163, 184, 0.24)" },
  warn: { background: "#fff8e8", borderColor: "rgba(214, 165, 92, 0.38)" },
};

const CALLOUT_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  marginTop: 6,
  padding: "8px 10px",
  border: "1px solid rgba(148, 163, 184, 0.24)",
  borderRadius: 8,
};

const COMPACT_CALLOUT_STYLE: CSSProperties = {
  margin: "6px 0",
  padding: "6px 8px",
  borderRadius: 7,
  fontSize: 12,
  lineHeight: 1.45,
};

const PRIMARY_CALLOUT_STYLE: CSSProperties = {
  minHeight: 72,
  padding: "10px 12px",
  borderWidth: 2,
  boxShadow: "0 8px 20px rgba(15, 23, 42, 0.06)",
};

const CALLOUT_LABEL_STYLE: CSSProperties = { color: "#64748b", fontSize: 11 };
const CALLOUT_TITLE_STYLE: CSSProperties = { color: "#0f172a", fontSize: 12 };
const PRIMARY_CALLOUT_TITLE_STYLE: CSSProperties = { color: "#0f172a", fontSize: 12 };
const WARNING_CALLOUT_TITLE_STYLE: CSSProperties = { display: "block", marginBottom: 2 };

const COMPACT_CALLOUT_TITLE_STYLE: CSSProperties = {
  display: "block",
  color: "#0f172a",
  fontSize: 12,
  lineHeight: 1.35,
};

const COMPACT_CALLOUT_DETAIL_STYLE: CSSProperties = {
  display: "block",
  color: "#64748b",
};

const CALLOUT_DESCRIPTION_STYLE: CSSProperties = {
  color: "#334155",
  fontSize: 12,
  lineHeight: 1.42,
};

export function Callout({
  title,
  label,
  detail,
  tone = "neutral",
  primary = false,
  compact = false,
  action,
  style,
}: {
  title: ReactNode;
  label?: ReactNode;
  detail?: ReactNode;
  tone?: Tone;
  primary?: boolean;
  compact?: boolean;
  action?: ReactNode;
  style?: CSSProperties;
}) {
  const rootStyle = {
    ...CALLOUT_STYLE,
    ...(compact ? COMPACT_CALLOUT_STYLE : null),
    ...(primary ? PRIMARY_CALLOUT_STYLE : null),
    ...CALLOUT_TONE_STYLES[tone],
    ...style,
  };
  const titleStyle = tone === "down"
    ? WARNING_CALLOUT_TITLE_STYLE
    : compact
      ? COMPACT_CALLOUT_TITLE_STYLE
      : primary
        ? PRIMARY_CALLOUT_TITLE_STYLE
        : CALLOUT_TITLE_STYLE;
  const detailStyle = compact
    ? tone === "down" ? undefined : COMPACT_CALLOUT_DETAIL_STYLE
    : CALLOUT_DESCRIPTION_STYLE;
  return (
    <div style={rootStyle}>
      {label ? <span style={CALLOUT_LABEL_STYLE}>{label}</span> : null}
      <strong style={titleStyle}>{title}</strong>
      {detail ? <span style={detailStyle}>{detail}</span> : null}
      {action ? <div>{action}</div> : null}
    </div>
  );
}
