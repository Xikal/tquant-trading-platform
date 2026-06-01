import type { ReactNode } from "react";

interface PanelProps {
  children: ReactNode;
  className?: string;
  extra?: ReactNode;
  padding?: "none" | "sm" | "md";
  title?: ReactNode;
}

export function Panel({ children, className = "", extra, padding = "md", title }: PanelProps) {
  return (
    <section className={`tq-panel ${className}`.trim()}>
      {title || extra ? (
        <div className="tq-panel__header">
          {title ? <div className="tq-panel__title">{title}</div> : <span />}
          {extra}
        </div>
      ) : null}
      <div className={`tq-panel__body tq-panel__body--${padding}`}>{children}</div>
    </section>
  );
}
