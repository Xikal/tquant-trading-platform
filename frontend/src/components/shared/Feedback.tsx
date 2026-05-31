import type { CSSProperties, ReactNode } from "react";
import { Skeleton } from "antd";

const FEEDBACK_EMPTY_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
  padding: "12px 14px",
  border: "1px dashed #dbe3ef",
  borderRadius: 12,
  background: "#f8fafc",
  color: "#64748b",
};

const FEEDBACK_LOADING_STYLE: CSSProperties = {
  padding: "12px 14px",
  borderRadius: 12,
  background: "#f8fafc",
  color: "#64748b",
};

const FEEDBACK_ERROR_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  padding: "12px 14px",
  border: "1px solid #fecaca",
  borderRadius: 12,
  background: "#fff1f1",
  color: "#b91c1c",
};

const FEEDBACK_ERROR_BUTTON_STYLE: CSSProperties = {
  alignSelf: "flex-start",
  background: "transparent",
  border: 0,
  color: "#b91c1c",
  cursor: "pointer",
  padding: 0,
};

const INLINE_VALIDATION_STYLE: CSSProperties = {
  color: "#d62f2f",
  fontSize: 12,
};

const SKELETON_TITLE_STYLE: CSSProperties = { gridColumn: "1 / -1" };

export function EmptyPlaceholder({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div style={FEEDBACK_EMPTY_STYLE}>
      <strong>{title}</strong>
      {description ? <span>{description}</span> : null}
      {action}
    </div>
  );
}

export function LoadingSpinner({ label = "加载中..." }: { label?: string }) {
  return <div style={FEEDBACK_LOADING_STYLE} role="status" aria-label={label}>{label}</div>;
}

export function SkeletonBlock({ rows = 4, title = false }: { rows?: number; title?: boolean }) {
  return (
    <Skeleton active paragraph={{ rows }} title={title} />
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div style={FEEDBACK_ERROR_STYLE}>
      <span>{message}</span>
      {onRetry ? <button type="button" onClick={onRetry} aria-label="重试加载" style={FEEDBACK_ERROR_BUTTON_STYLE}>重试</button> : null}
    </div>
  );
}

export function InlineValidation({ message }: { message?: string }) {
  return message ? <span style={INLINE_VALIDATION_STYLE}>{message}</span> : null;
}
