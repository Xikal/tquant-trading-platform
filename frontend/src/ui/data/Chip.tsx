import type { ReactNode } from "react";

export type ChipTone = "neutral" | "brand" | "success" | "warning" | "danger" | "marketUp" | "marketDown";

interface ChipProps {
  children: ReactNode;
  className?: string;
  dot?: boolean;
  tone?: ChipTone;
}

export function Chip({ children, className, dot = false, tone = "neutral" }: ChipProps) {
  return (
    <span className={`tq-chip tq-chip--${tone} ${className ?? ""}`.trim()}>
      {dot ? <i aria-hidden="true" className="tq-chip__dot" /> : null}
      <span>{children}</span>
    </span>
  );
}
