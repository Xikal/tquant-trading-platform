import type { CSSProperties, ReactNode } from "react";
import type { Tone } from "./workspaceTypes";

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
  return (
    <div className={[
      "tq-callout",
      `tq-callout--tone-${tone}`,
      primary ? "tq-callout--primary" : "",
      compact ? "tq-callout--compact" : "",
    ].filter(Boolean).join(" ")} style={style}>
      {label ? <span className="tq-callout__label">{label}</span> : null}
      <strong className="tq-callout__title">{title}</strong>
      {detail ? <span className="tq-callout__detail">{detail}</span> : null}
      {action ? <div className="tq-callout__action">{action}</div> : null}
    </div>
  );
}
