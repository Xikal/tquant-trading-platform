import type { ReactNode } from "react";

export function EmptyPlaceholder({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="tq-feedback tq-feedback--empty">
      <strong>{title}</strong>
      {description ? <span>{description}</span> : null}
      {action}
    </div>
  );
}

export function LoadingSpinner({ label = "加载中..." }: { label?: string }) {
  return <div className="tq-feedback tq-feedback--loading" role="status" aria-label={label}>{label}</div>;
}

export function SkeletonBlock({ rows = 4, title = false }: { rows?: number; title?: boolean }) {
  return (
    <div className="tq-skeleton" role="status" aria-label="加载中">
      {title ? <span className="wide" /> : null}
      {Array.from({ length: rows }).map((_, index) => (
        <span className={index % 3 === 1 ? "medium" : ""} key={index} />
      ))}
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="tq-feedback tq-feedback--error">
      <span>{message}</span>
      {onRetry ? <button type="button" onClick={onRetry} aria-label="重试加载">重试</button> : null}
    </div>
  );
}

export function InlineValidation({ message }: { message?: string }) {
  return message ? <span className="tq-inline-error">{message}</span> : null;
}
