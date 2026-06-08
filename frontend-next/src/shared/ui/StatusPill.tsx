import { Tag } from "./Tag";

export type StatusPillTone = "neutral" | "up" | "down" | "warn" | "danger" | "info";

export function StatusPill(props: {
  label: string;
  value?: string | number | null;
  tone?: StatusPillTone;
  title?: string;
  ariaLabel?: string;
  "aria-label"?: string;
}) {
  const value = () => props.value ?? "--";
  const tone = () => (props.tone === "danger" ? "down" : props.tone === "info" ? "neutral" : props.tone);
  return (
    <Tag tone={tone()} title={props.title} aria-label={props.ariaLabel ?? props["aria-label"] ?? `${props.label} ${value()}`}>
      <span>{props.label}</span>
      <strong style={{ "font-weight": 700 }}>{value()}</strong>
    </Tag>
  );
}
